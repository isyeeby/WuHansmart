import { apiClient } from '../config/api';

// ==================== 推荐模块 (Recommend) ====================

// 推荐房源项 - 对应 /api/recommend
export interface RecommendedListing {
  id: string;
  title: string;
  district: string;
  price: number;
  rating: number;
  match_score: number;
  reason: string;
  cover_image?: string | null;
}

// 个性化推荐响应
export interface RecommendResponse {
  recommendations: RecommendedListing[];
}

// 个性化推荐参数 - 对应 /api/recommend
export interface RecommendParams {
  user_id?: string;
  district?: string;
  trade_area?: string;
  price_min?: number;
  price_max?: number;
  capacity?: number;
  travel_purpose?: string;
  facilities?: string;
  bedroom_count?: number;
  top_k?: number;
}

// 旧版推荐房源项 (兼容旧接口)
export interface LegacyRecommendedListing {
  unit_id: string;
  title: string;
  price: number;
  rating: number;
  total_reviews: number;
  district: string;
  bedrooms: number;
  bathrooms: number;
  area: number;
  image_url?: string;
  tags: string[];
  match_score: number;
  match_reason: string;
}

// 旧版个性化推荐参数 (兼容旧接口)
export interface LegacyRecommendParams {
  budget_min?: number;
  budget_max?: number;
  districts?: string[];
  bedrooms?: number;
  purpose?: 'investment' | 'travel' | 'business';
  limit?: number;
}

/**
 * 获取个性化推荐 (新接口)
 * 对应 /api/recommend
 * @param params 推荐参数
 */
export const getRecommendations = async (
  params?: RecommendParams
): Promise<RecommendResponse> => {
  const response = await apiClient.get('/api/recommend', { params });
  return response.data;
};

/**
 * 获取个性化推荐 (兼容旧接口；首页「智能推荐」请用 homeApi.getHomeRecommendations)
 * 注意：后端 /api/recommend/personalized 不接受参数
 * 如果需要限制数量，请使用 getRecommendations
 * @param params 推荐参数 (仅用于兼容，实际不传给后端)
 */
export const getPersonalizedRecommendations = async (
  params?: LegacyRecommendParams
): Promise<LegacyRecommendedListing[]> => {
  // 使用 /api/recommend 接口，因为它更灵活
  const response = await apiClient.get('/api/recommend', {
    params: {
      top_k: params?.limit || 10
    }
  });
  // 后端返回 { recommendations: [...] }
  const recommendations = response.data?.recommendations || [];
  
  // 转换为 LegacyRecommendedListing 格式
  return recommendations.map((item: any) => ({
    unit_id: item.id || item.unit_id,
    title: item.title,
    price: item.price,
    rating: item.rating,
    total_reviews: item.total_reviews || 0,
    district: item.district,
    bedrooms: item.bedrooms || 1,
    bathrooms: item.bathrooms || 1,
    area: item.area || 50,
    image_url: item.cover_image || item.image_url,
    tags: item.facilities || [],
    match_score: item.match_score || 0.8,
    match_reason: item.reason || '为您推荐'
  }));
};

/**
 * 获取相似房源推荐
 * @param unitId 参考房源ID
 * @param limit 返回数量
 */
export const getSimilarListings = async (
  unitId: string,
  limit?: number
): Promise<LegacyRecommendedListing[]> => {
  const response = await apiClient.get(`/api/recommend/similar/${unitId}`, {
    params: { top_k: limit || 5 }
  });
  const recommendations = response.data?.recommendations || [];
  
  // 转换为 LegacyRecommendedListing 格式
  return recommendations.map((item: any) => ({
    unit_id: item.id || item.unit_id,
    title: item.title,
    price: item.price,
    rating: item.rating,
    total_reviews: item.total_reviews || 0,
    district: item.district,
    bedrooms: item.bedrooms || 1,
    bathrooms: item.bathrooms || 1,
    area: item.area || 50,
    image_url: item.cover_image || item.image_url,
    tags: item.facilities || [],
    match_score: item.match_score || 0.8,
    match_reason: item.reason || '相似房源'
  }));
};
