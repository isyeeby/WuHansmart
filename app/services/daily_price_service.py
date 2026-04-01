# -*- coding: utf-8 -*-
"""
日级 XGBoost 14 天预测 + 分位数区间（加载 models/xgboost_price_daily*.pkl）。
若分位数模型缺失，则用验证集 MAE 的误差带（daily_forecast_meta.json）兜底。
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np

from app.ml.daily_price_inference import (
    build_daily_inference_dataframe,
    load_district_stats_daily,
    load_trade_area_stats_daily,
    prediction_request_to_features_dict,
)
from app.models.schemas import PredictionRequest

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODELS_DIR = _BACKEND_ROOT / "models"


class DailyPriceForecastService:
    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
        self._point = None
        self._q020 = None
        self._q050 = None
        self._q080 = None
        self._feature_names: Optional[List[str]] = None
        self._district_enc: Optional[Dict[str, int]] = None
        self._ta_enc: Optional[Dict[str, int]] = None
        self._ht_enc: Optional[Dict[str, int]] = None
        self._dist_stats: Dict[str, Dict[str, float]] = {}
        self._ta_stats: Dict[str, Dict[str, float]] = {}
        self._lag_defaults: Dict[str, float] = {}
        self._meta: Dict[str, Any] = {}
        self._loaded = False

    def available(self) -> bool:
        p = self.models_dir / "xgboost_price_daily_model.pkl"
        fn = self.models_dir / "feature_names_daily.json"
        return p.exists() and fn.exists()

    def _load(self) -> bool:
        if self._loaded:
            return self._point is not None
        if not self.available():
            logger.warning("日级模型或 feature_names_daily.json 不存在，跳过加载")
            self._loaded = True
            return False
        try:
            self._point = joblib.load(self.models_dir / "xgboost_price_daily_model.pkl")
            with open(self.models_dir / "feature_names_daily.json", "r", encoding="utf-8") as f:
                self._feature_names = json.load(f)
            for name, attr in [
                ("district_encoder_daily.pkl", "_district_enc"),
                ("trade_area_encoder_daily.pkl", "_ta_enc"),
                ("house_type_encoder_daily.pkl", "_ht_enc"),
            ]:
                path = self.models_dir / name
                if path.exists():
                    setattr(self, attr, joblib.load(path))
            self._dist_stats = load_district_stats_daily(str(self.models_dir / "district_stats_daily.json"))
            self._ta_stats = load_trade_area_stats_daily(str(self.models_dir / "trade_area_target_stats_daily.json"))
            lag_path = self.models_dir / "daily_lag_inference_defaults.json"
            if lag_path.exists():
                with open(lag_path, "r", encoding="utf-8") as f:
                    self._lag_defaults = {k: float(v) for k, v in json.load(f).items()}
            meta_path = self.models_dir / "daily_forecast_meta.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    self._meta = json.load(f)
            for suffix, attr in [
                ("q020", "_q020"),
                ("q050", "_q050"),
                ("q080", "_q080"),
            ]:
                qp = self.models_dir / f"xgboost_price_daily_{suffix}.pkl"
                if qp.exists():
                    setattr(self, attr, joblib.load(qp))
            self._loaded = True
            logger.info(
                "日级定价模型已加载: point=ok quantiles=%s",
                sum(1 for x in (self._q020, self._q050, self._q080) if x is not None),
            )
            return True
        except Exception as e:
            logger.exception("日级模型加载失败: %s", e)
            self._loaded = True
            return False

    def predict_forecast_14(
        self,
        req: PredictionRequest,
        n_days: int = 14,
        anchor: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._load() or self._point is None or not self._feature_names:
            return None
        anchor = anchor or datetime.now()
        feats = prediction_request_to_features_dict(req)
        dates = [(anchor + timedelta(days=i)).date() for i in range(n_days)]
        horizons = list(range(n_days))
        df = build_daily_inference_dataframe(
            feats,
            dates,
            horizons,
            self._feature_names,
            self._district_enc or {},
            self._ta_enc or {},
            self._ht_enc or {},
            self._dist_stats,
            self._ta_stats,
            self._lag_defaults,
        )
        x = df.to_numpy(dtype=np.float32)
        pred_log = self._point.predict(x)
        point = np.expm1(pred_log)

        q20 = q50 = q80 = None
        if self._q020 is not None:
            q20 = np.expm1(self._q020.predict(x))
        if self._q050 is not None:
            q50 = np.expm1(self._q050.predict(x))
        if self._q080 is not None:
            q80 = np.expm1(self._q080.predict(x))

        mae_band = float(self._meta.get("val_mae_price", 0) or 0)
        mult = float(self._meta.get("error_band_multiplier", 1.5))
        use_band = mae_band > 0 and (q20 is None or q80 is None)

        try:
            import chinesecalendar as _cal  # type: ignore
        except ImportError:
            _cal = None

        wd_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        forecasts: List[Dict[str, Any]] = []
        base_first = 0.0
        for i in range(n_days):
            d = dates[i]
            p_mid = float(np.clip(point[i], 50.0, 5000.0))
            if q20 is not None and q80 is not None:
                lo = float(np.clip(q20[i], 50.0, 5000.0))
                hi = float(np.clip(q80[i], 50.0, 5000.0))
                if lo > hi:
                    lo, hi = hi, lo
                interval_method = "quantile_xgb_20_80"
                # 点模型与分位数模型独立训练，建议价裁剪进 [q20,q80] 更易理解且避免「线在带外」
                p_show = float(min(max(p_mid, lo), hi))
            elif use_band:
                lo = float(np.clip(p_mid - mult * mae_band, 50.0, 5000.0))
                hi = float(np.clip(p_mid + mult * mae_band, 50.0, 5000.0))
                interval_method = f"mae_band_{mult}x_val_mae"
                p_show = p_mid
            else:
                lo = float(np.clip(p_mid * 0.85, 50.0, 5000.0))
                hi = float(np.clip(p_mid * 1.15, 50.0, 5000.0))
                interval_method = "fallback_percent_15"
                p_show = p_mid
            med = float(np.clip(q50[i], 50.0, 5000.0)) if q50 is not None else p_mid
            wk = d.weekday()
            is_holiday = False
            if _cal is not None:
                try:
                    is_holiday = bool(_cal.is_holiday(d))
                except Exception:
                    pass
            forecasts.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "weekday": wd_names[wk],
                    "predicted_price": round(p_show, 2),
                    "price_median_quantile": round(med, 2),
                    "price_low": round(lo, 2),
                    "price_high": round(hi, 2),
                    "interval_method": interval_method,
                    "is_weekend": wk in (5, 6),
                    "is_holiday": is_holiday,
                    "holiday_name": "",
                    "factors": {"xgboost_daily": 1.0},
                    "horizon_day": i,
                }
            )

        if forecasts:
            base_first = float(forecasts[0]["predicted_price"])

        return {
            "base_price": round(base_first, 2),
            "district": req.district,
            "model": "xgboost_daily",
            "anchor_date": dates[0].strftime("%Y-%m-%d"),
            "forecasts": forecasts,
            "avg_forecast_price": round(float(np.mean([f["predicted_price"] for f in forecasts])), 2),
            "max_price": max(f["predicted_price"] for f in forecasts),
            "min_price": min(f["predicted_price"] for f in forecasts),
            "pricing_strategy": {
                "weekend_premium": "日级模型已将周末、节假日与提前预订 horizon 纳入特征；曲线为逐日点预测。",
                "holiday_premium": "下方卡片可查看每日建议价与相对首日的涨跌；悬停可看区间（如有）。",
                "advance_discount": "",
            },
        }

    def get_meta(self) -> Dict[str, Any]:
        self._load()
        return dict(self._meta)

    def get_feature_importance_gain(self) -> Optional[Dict[str, float]]:
        """日级点模型的 gain 重要性，键为训练特征名；供因子页与房源级重要性对照。"""
        if not self._load() or self._point is None or not self._feature_names:
            return None
        try:
            booster = self._point.get_booster()
            scores = booster.get_score(importance_type="gain")
        except Exception:
            logger.debug("daily model get_score failed", exc_info=True)
            return None
        if not scores:
            return None
        out: Dict[str, float] = {}
        names = self._feature_names
        name_set = set(names)
        for k, v in scores.items():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if k in name_set:
                out[k] = fv
            elif k.startswith("f"):
                try:
                    idx = int(k[1:])
                except ValueError:
                    continue
                if 0 <= idx < len(names):
                    out[names[idx]] = fv
        return out if out else None

    def reload_from_disk(self) -> None:
        """丢弃内存中的日级模型与编码器，下次请求时从 models/ 目录重新加载。"""
        self._point = None
        self._q020 = None
        self._q050 = None
        self._q080 = None
        self._feature_names = None
        self._district_enc = None
        self._ta_enc = None
        self._ht_enc = None
        self._dist_stats = {}
        self._ta_stats = {}
        self._lag_defaults = {}
        self._meta = {}
        self._loaded = False


daily_forecast_service = DailyPriceForecastService()
