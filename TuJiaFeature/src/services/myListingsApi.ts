import { apiClient } from '../config/api';

// 我的房源类型
export interface MyListing {
  id: number;
  user_id: number;
  title: string;
  district: string;
  trade_area?: string;  // 商圈（更精细的位置）
  business_circle?: string;
  address?: string;
  longitude?: number;
  latitude?: number;
  bedroom_count: number;
  bed_count: number;
  bathroom_count: number;
  max_guests: number;
  area?: number;
  current_price: number;
  style_tags?: string[];
  facility_tags?: string[];
  location_tags?: string[];
  crowd_tags?: string[];
  status: 'active' | 'inactive';
  created_at: string;
}

// 创建房源请求参数
export interface CreateMyListingParams {
  title: string;
  district: string;
  business_circle?: string;
  address?: string;
  longitude?: number;
  latitude?: number;
  bedroom_count: number;
  bed_count: number;
  bathroom_count: number;
  max_guests: number;
  area?: number;
  current_price: number;
  style_tags?: string[];
  facility_tags?: string[];
  location_tags?: string[];
  crowd_tags?: string[];
}

// 竞品房源类型
export interface CompetitorListing {
  unit_id: string;
  title: string;
  final_price: number;
  rating: number;
  favorite_count: number;
  similarity_score: number;
  house_tags?: string | null;
  tag_list?: string[] | null;
  /** 与我的房源直线距离（公里），需双方均有坐标 */
  distance_km?: number | null;
}

// 市场定位类型
export interface MarketPosition {
  avg_price: number;
  my_price_rank: number;
  price_percentile: number;
  total_competitors?: number;
  geo_ranking_used?: boolean;
  selection_note?: string;
}

// 竞品分析结果
export interface CompetitorAnalysis {
  my_listing: {
    id: number;
    title: string;
    current_price: number;
    district: string;
  };
  market_position: MarketPosition;
  competitors: CompetitorListing[];
  analysis: {
    advantages: string[];
    disadvantages: string[];
    suggestions: string[];
  };
}

// 定价建议响应
export interface PriceSuggestion {
  current_price: number;
  suggested_price: number;
  price_difference: number;
  difference_percent: number;
  suggestion: '建议涨价' | '建议降价' | '建议保持';
  reasoning: string[];
  confidence: number;
}

/**
 * 创建我的房源
 * @param params 房源信息
 */
export const createMyListing = async (
  params: CreateMyListingParams
): Promise<MyListing> => {
  const response = await apiClient.post('/api/my-listings', params);
  return response.data;
};

/**
 * 获取我的房源列表
 */
export const getMyListings = async (): Promise<MyListing[]> => {
  const response = await apiClient.get('/api/my-listings');
  return response.data;
};

/**
 * 获取单个我的房源详情
 * @param listingId 房源ID
 */
export const getMyListingDetail = async (listingId: number): Promise<MyListing> => {
  const response = await apiClient.get(`/api/my-listings/${listingId}`);
  return response.data;
};

/**
 * 更新我的房源
 * @param listingId 房源ID
 * @param params 更新参数
 */
export const updateMyListing = async (
  listingId: number,
  params: Partial<CreateMyListingParams>
): Promise<MyListing> => {
  const response = await apiClient.put(`/api/my-listings/${listingId}`, params);
  return response.data;
};

/**
 * 删除我的房源
 * @param listingId 房源ID
 */
export const deleteMyListing = async (listingId: number): Promise<void> => {
  await apiClient.delete(`/api/my-listings/${listingId}`);
};

/**
 * 获取竞品对比分析
 * @param listingId 我的房源ID
 */
export const getCompetitorAnalysis = async (
  listingId: number
): Promise<CompetitorAnalysis> => {
  const response = await apiClient.get(`/api/my-listings/${listingId}/competitors`);
  return response.data;
};

/**
 * 获取定价建议
 * @param listingId 我的房源ID
 */
export const getPriceSuggestion = async (
  listingId: number
): Promise<PriceSuggestion> => {
  const response = await apiClient.post(`/api/my-listings/${listingId}/price-suggestion`);
  return response.data;
};

/**
 * 获取行政区和商圈映射数据
 */
export const getDistrictTradeAreas = async (): Promise<{
  districts: string[];
  trade_areas: Record<string, string[]>;
}> => {
  const response = await apiClient.get('/api/predict/district-trade-areas');
  return response.data;
};
