/**
 * 价格洼地分析 API（直连 /api/analysis/*）
 *
 * @deprecated 前端「价格洼地」已合并到「投资分析」页；请优先使用 investmentApi.getInvestmentOpportunities（/api/investment/opportunities，同源数据）。
 * 本文件保留供脚本或对照测试使用。
 */
import { apiClient } from '../config/api';

export interface PriceOpportunity {
  unit_id: string;
  title: string;
  district: string;
  current_price: number;
  predicted_price: number;
  /** 参考价 − 挂牌价（元） */
  price_gap?: number;
  gap_rate: number;
  rating: number;
  /** xgboost_daily | district_median */
  prediction_source?: string;
}

export interface PriceOpportunitiesMethodology {
  gap_formula?: string;
  reference_price?: string;
  model_call_cap?: number;
  eligibility_note?: string;
}

export interface PriceOpportunitiesResponse {
  items: PriceOpportunity[];
  methodology: PriceOpportunitiesMethodology;
}

export interface ROIRanking {
  district: string;
  roi_score: number;
  avg_price: number;
  occupancy_rate: number;
  recommendation: string;
  occupancy_basis?: string;
  calendar_sample_rows?: number | null;
  calendar_unavailable_share_pct?: number | null;
  estimated_roi?: number | null;
  revenue_intensity_ratio?: number | null;
  data_source_note?: string;
}

/**
 * 获取价格洼地房源（投资机会）
 * @param minGapRate 最小价差率，默认20%
 * @param limit 返回数量，默认20
 */
export const getPriceOpportunities = async (
  minGapRate: number = 20,
  limit: number = 20
): Promise<PriceOpportunitiesResponse> => {
  const response = await apiClient.get('/api/analysis/price-opportunities', {
    params: { min_gap_rate: minGapRate, limit }
  });
  const raw = response.data;
  if (raw?.items && Array.isArray(raw.items)) {
    return raw as PriceOpportunitiesResponse;
  }
  if (Array.isArray(raw)) {
    return { items: raw, methodology: {} };
  }
  return { items: [], methodology: {} };
};

/**
 * 获取投资收益率排名
 * @param limit 返回数量，默认50
 */
export const getROIRanking = async (limit: number = 50): Promise<ROIRanking[]> => {
  const response = await apiClient.get('/api/analysis/roi-ranking', {
    params: { limit }
  });
  const raw = response.data;
  if (Array.isArray(raw)) return raw;
  if (raw?.data && Array.isArray(raw.data)) return raw.data;
  return [];
};
