import { apiClient } from '../config/api';
import { cachedRequest } from '../utils/requestCache';

const DISTRICTS_TTL_MS = 120_000;
const PRICE_DIST_TTL_MS = 60_000;

// ==================== 商圈分析模块 (Analysis) ====================

// 商圈统计响应类型 - 对应 /api/analysis/districts
export interface DistrictStats {
  district: string;
  trade_area: string;
  listing_count: number;
  avg_price: number;
  avg_rating: number;
  avg_favorite_count: number;
  avg_comment_count: number;
  avg_bedroom_count: number;
  min_price: number;
  max_price: number;
}

// 设施溢价分析类型 - 对应 /api/analysis/facility-premium
export interface FacilityPremium {
  facility_name: string;
  avg_price_with: number;
  avg_price_without: number;
  premium_amount: number;
  premium_percent: number;
  listing_count: number;
}

// 设施溢价分析响应
export interface FacilityPremiumResponse {
  facilities: FacilityPremium[];
}

// 价格分布响应类型 (保留兼容)
export interface PriceDistribution {
  price_range: string;
  count: number;
  percentage: number;
}

// 价格洼地房源类型 (保留兼容)
export interface PriceOpportunity {
  unit_id: string;
  title: string;
  district: string;
  current_price: number;
  predicted_price: number;
  gap_rate: number;
  rating: number;
  prediction_source?: string;
}

// ROI 排名类型 (保留兼容)
export interface ROIRanking {
  district: string;
  roi_score: number;
  avg_price: number;
  occupancy_rate: number;
  recommendation: string;
}

// 房源列表项类型 (保留兼容)
export interface ListingItem {
  unit_id: string;
  title: string;
  district: string;
  price: number;
  rating: number;
  room_type: string;
  capacity: number;
  image_url?: string;
}

// 房源详情类型 (保留兼容)
export interface ListingDetail extends ListingItem {
  bedrooms: number;
  bathrooms: number;
  facilities: string[];
  description?: string;
  host_name?: string;
  total_reviews: number;
}

// 相似房源类型 (保留兼容)
export interface SimilarListing {
  unit_id: string;
  title: string;
  district: string;
  price: number;
  rating: number;
  similarity_score: number;
}


/**
 * 获取商圈列表及统计
 * @param district 按行政区筛选
 */
export const getDistricts = async (district?: string): Promise<DistrictStats[]> => {
  const key = `analysis:districts:${district ?? 'all'}`;
  return cachedRequest(key, DISTRICTS_TTL_MS, async () => {
    const response = await apiClient.get('/api/analysis/districts', {
      params: { district }
    });
    return response.data;
  });
};

/**
 * 获取设施溢价分析
 * 对应新接口 /api/analysis/facility-premium
 */
export const getFacilityPremium = async (): Promise<FacilityPremiumResponse> => {
  const response = await apiClient.get('/api/analysis/facility-premium');
  return response.data;
};

/**
 * 获取价格区间分布
 * @param district 商圈名称，不传则返回全局分布
 */
export const getPriceDistribution = async (district?: string): Promise<PriceDistribution[]> => {
  const key = `analysis:price-distribution:${district ?? 'all'}`;
  return cachedRequest(key, PRICE_DIST_TTL_MS, async () => {
    const response = await apiClient.get('/api/analysis/price-distribution', {
      params: { district }
    });
    return response.data;
  });
};

/**
 * 获取价格洼地房源（投资机会）
 * @param minGapRate 最小价差率(%)，默认20
 * @param limit 返回数量，默认20
 */
export const getPriceOpportunities = async (
  minGapRate?: number,
  limit?: number
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
export const getROIRanking = async (limit?: number): Promise<ROIRanking[]> => {
  const response = await apiClient.get('/api/analysis/roi-ranking', {
    params: { limit }
  });
  return response.data;
};
