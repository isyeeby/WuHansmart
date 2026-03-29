/**
 * 价格洼地分析 API 服务
 */
import { apiClient } from '../config/api';

export interface PriceOpportunity {
  unit_id: string;
  title: string;
  district: string;
  current_price: number;
  predicted_price: number;
  gap_rate: number;
  rating: number;
  /** xgboost | district_median */
  prediction_source?: string;
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
): Promise<PriceOpportunity[]> => {
  const response = await apiClient.get('/api/analysis/price-opportunities', {
    params: { min_gap_rate: minGapRate, limit }
  });
  return response.data;
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
