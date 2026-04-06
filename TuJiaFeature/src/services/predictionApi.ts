import { apiClient } from '../config/api';

// ==================== 价格预测模块 (Prediction) ====================

// 价格预测请求参数 - 对应 /api/predict/price
export interface PricePredictionParams {
  district: string;
  trade_area?: string;  // 商圈（更精细的位置）
  bedroom_count: number;
  bed_count: number;
  bathroom_count?: number;
  area?: number;
  capacity?: number;  // 可住人数
  has_metro?: boolean;
  has_kitchen?: boolean;
  has_projector?: boolean;
  has_washer?: boolean;
  has_smart_lock?: boolean;
  has_air_conditioner?: boolean;
  has_bathtub?: boolean;
  has_parking?: boolean;
  has_balcony?: boolean;
  near_metro?: boolean;
  has_elevator?: boolean;
  has_fridge?: boolean;
  has_view?: boolean;
  view_type?: string;  // 江景/湖景/山景
  has_terrace?: boolean;
  has_mahjong?: boolean;
  has_big_living_room?: boolean;
  has_tv?: boolean;
  has_heater?: boolean;
  pet_friendly?: boolean;
  // 景观特色
  river_view?: boolean;
  lake_view?: boolean;
  mountain_view?: boolean;
  garden?: boolean;
}

// 价格预测响应
export interface PricePredictionResponse {
  predicted_price: number;
  price_range: {
    lower: number;
    upper: number;
  };
  confidence: number;
  factors: {
    feature: string;
    impact: string;
    detail: string;
  }[];
  district_avg_price: number;
}

// 预测结果 (兼容旧接口)
export interface ForecastResult {
  dates: string[];
  prices: number[];
  confidence_lower: number[];
  confidence_upper: number[];
  trend: 'up' | 'down' | 'stable';
  trend_percent: number;
}

// 因子分解项 (兼容旧接口)
export interface FactorItem {
  name: string;
  value: number;
  impact: 'positive' | 'negative' | 'neutral';
  description: string;
}

// 因子分解结果 (兼容旧接口)
export interface FactorDecomposition {
  factors: FactorItem[];
  base_price: number;
  predicted_price: number;
  seasonality_factor: number;
  demand_factor: number;
  competition_factor: number;
}

/** 智能定价页：forecast / 因子分解 / 竞争力 共用参数 */
export type PredictionAnalysisParams = {
  district: string;
  trade_area?: string;
  room_type: string;
  capacity: number;
  bedrooms: number;
  bed_count?: number;
  area?: number;
  base_price?: number;
  /** 竞争力接口 current_price；未填时由页面用参考价兜底 */
  current_price?: number;
  has_wifi?: boolean;
  has_air_conditioning?: boolean;
  has_kitchen?: boolean;
  has_projector?: boolean;
  has_bathtub?: boolean;
  has_washer?: boolean;
  has_smart_lock?: boolean;
  has_tv?: boolean;
  has_heater?: boolean;
  near_metro?: boolean;
  near_station?: boolean;
  near_university?: boolean;
  near_ski?: boolean;
  has_elevator?: boolean;
  has_fridge?: boolean;
  has_view?: boolean;
  view_type?: string;
  has_terrace?: boolean;
  has_mahjong?: boolean;
  has_big_living_room?: boolean;
  has_parking?: boolean;
  pet_friendly?: boolean;
  river_view?: boolean;
  lake_view?: boolean;
  mountain_view?: boolean;
  garden?: boolean;
};

/**
 * 价格预测 (新接口)
 * 对应 /api/predict/price
 * @param params 房源特征参数
 */
export const predictPrice = async (
  params: PricePredictionParams
): Promise<PricePredictionResponse> => {
  const response = await apiClient.post('/api/predict/price', params);
  return response.data;
};

/**
 * 获取14天价格预测
 * 注意：后端需要 district, room_type, capacity, bedrooms, area 等参数
 * @param params 预测参数
 */
export const getForecast = async (params: PredictionAnalysisParams): Promise<any> => {
  const {
    current_price,
    base_price: explicitBase,
    river_view: _rv,
    lake_view: _lv,
    mountain_view: _mv,
    ...rest
  } = params;

  const q: Record<string, string | number | boolean | undefined> = {
    ...rest,
  };
  const anchor = explicitBase ?? current_price;
  if (anchor != null && Number(anchor) > 0 && Number.isFinite(Number(anchor))) {
    q.base_price = Number(anchor);
  }
  const cleaned = Object.fromEntries(
    Object.entries(q).filter(([, v]) => v !== undefined && v !== null)
  );
  const response = await apiClient.get('/api/predict/forecast', {
    params: cleaned,
  });
  return response.data;
};

/**
 * 获取价格因子分解
 * 注意：后端是 POST 方法，需要 PredictionRequest 参数
 * @param params 预测参数
 */
export const getFactorDecomposition = async (
  params: PredictionAnalysisParams
): Promise<any> => {
  const response = await apiClient.post('/api/predict/factor-decomposition', params);
  return response.data;
};

/**
 * 竞争力评估
 * @param params 房源参数
 */
export const getCompetitivenessAssessment = async (
  params: PredictionAnalysisParams
): Promise<{
  predicted_price: number;
  district_average: number;
  price_ratio: number;
  competitiveness_score: number;
  competitiveness_level: string;
  suggestions: string[];
}> => {
  const response = await apiClient.post('/api/predict/competitiveness', params);
  return response.data;
};

