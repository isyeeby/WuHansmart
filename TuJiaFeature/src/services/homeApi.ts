/**
 * 首页数据 API 服务
 */
import { apiClient } from '../config/api';

export interface HomeStats {
  district_count: number;
  listing_count: number;
  data_days: number;
  avg_roi: number;
}

export interface HotDistrict {
  name: string;
  heat: number;
  avg_price: number;
  price_trend: number;
}

export interface HomeRecommendation {
  unit_id: string;
  title: string;
  district?: string | null;
  price: number;
  rating: number;
  tags: string[];
  image_url: string | null;
  /** 后端为 0–100 整数 */
  match_score: number;
}

export interface HeatmapPoint {
  name: string;
  x: number;
  y: number;
  value: number;
}

/**
 * 获取平台统计数据
 */
export const getHomeStats = async (): Promise<HomeStats> => {
  const response = await apiClient.get('/api/home/stats');
  return response.data;
};

/**
 * 获取热门商圈排行
 */
export const getHotDistricts = async (limit: number = 8): Promise<HotDistrict[]> => {
  const response = await apiClient.get('/api/home/hot-districts', {
    params: { limit }
  });
  return response.data.districts;
};

/**
 * 获取首页推荐房源
 */
export const getHomeRecommendations = async (limit: number = 6): Promise<HomeRecommendation[]> => {
  const response = await apiClient.get('/api/home/recommendations', {
    params: { limit }
  });
  return Array.isArray(response.data?.listings) ? response.data.listings : [];
};

/**
 * 获取商圈热力图数据（与首页一致，走 dashboard 热力接口）
 */
export const getHeatmapData = async (): Promise<HeatmapPoint[]> => {
  const response = await apiClient.get<{ data: HeatmapPoint[] }>('/api/dashboard/heatmap');
  return response.data.data || [];
};
