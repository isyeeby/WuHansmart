import { apiClient } from '../config/api';
import { cachedRequest } from '../utils/requestCache';

const DASHBOARD_TTL_MS = 60_000;

// ==================== Dashboard 模块 ====================

// 核心指标汇总 - 对应 /api/dashboard/summary
export interface DashboardSummary {
  total_listings: number;
  avg_price: number;
  avg_rating: number;
  district_count: number;
  price_trend: number;
}

// 商圈对比数据项 - 对应 /api/dashboard/district-comparison
export interface DistrictComparisonItem {
  district: string;
  trade_area: string;
  avg_price: number;
  listing_count: number;
  avg_rating: number;
}

// 商圈对比响应
export interface DistrictComparisonResponse {
  items: DistrictComparisonItem[];
}

// KPI 数据类型 (兼容旧接口)
export interface KpiData {
  total_listings: number;
  avg_price: number;
  price_change_percent: number;
  district_count: number;
  occupancy_rate: number;
  avg_roi: number;
  kpi_definitions?: Record<string, string>;
}

// 热力图数据点 (兼容旧接口)
export interface HeatmapPoint {
  name: string;
  x: number;
  y: number;
  value: number;
}

// 热力图响应
export interface HeatmapResponse {
  data: HeatmapPoint[];
  series_note?: string;
}

// 热门商圈排行响应
export interface TopDistrictsResponse {
  items: TopDistrict[];
}

// 热门商圈 (兼容旧接口)
export interface TopDistrict {
  name: string;
  heat: number;
  avg_price: number;
  price_trend: number;
  listing_count: number;
}

// 趋势数据 (兼容旧接口)
export interface TrendData {
  dates: string[];
  prices: number[];
  listing_counts: number[];
  occupancy_rates: number[];
  series_note?: string;
}

// 预警项 (兼容旧接口)
export interface AlertItem {
  type: 'price_drop' | 'price_surge' | 'low_occupancy' | 'high_opportunity';
  title: string;
  message: string;
  district?: string;
  unit_id?: string;
  severity: 'low' | 'medium' | 'high';
  created_at: string;
}

/**
 * 获取核心指标汇总 (新接口)
 * 对应 /api/dashboard/summary
 */
export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const response = await apiClient.get('/api/dashboard/summary');
  return response.data;
};

/**
 * 获取商圈对比数据 (新接口)
 * 对应 /api/dashboard/district-comparison
 * @param limit 数量限制，默认10
 */
export const getDistrictComparison = async (
  limit?: number
): Promise<DistrictComparisonResponse> => {
  const response = await apiClient.get('/api/dashboard/district-comparison', {
    params: { limit }
  });
  return response.data;
};

/**
 * 获取核心指标看板 (兼容旧接口)
 */
export const getKpiDashboard = async (): Promise<KpiData> => {
  return cachedRequest('dashboard:kpi', DASHBOARD_TTL_MS, async () => {
    const response = await apiClient.get('/api/dashboard/kpi');
    return response.data;
  });
};

/**
 * 获取区域热力图数据
 * 响应格式: { data: HeatmapPoint[] }
 */
export const getHeatmapData = async (): Promise<{
  data: HeatmapPoint[];
  series_note?: string;
}> => {
  return cachedRequest('dashboard:heatmap', DASHBOARD_TTL_MS, async () => {
    const response = await apiClient.get<HeatmapResponse>('/api/dashboard/heatmap');
    return { data: response.data.data || [], series_note: response.data.series_note };
  });
};

/**
 * 获取热门商圈排行
 * @param limit 返回数量
 * 响应格式: { items: TopDistrict[] }
 */
export const getTopDistricts = async (limit?: number): Promise<TopDistrict[]> => {
  const key = `dashboard:top-districts:${limit ?? 'default'}`;
  return cachedRequest(key, DASHBOARD_TTL_MS, async () => {
    const response = await apiClient.get<TopDistrictsResponse>('/api/dashboard/top-districts', {
      params: { limit }
    });
    return response.data.items || [];
  });
};

/**
 * 获取平台趋势数据
 * @param days 时间范围（天）
 */
export const getDashboardTrends = async (days?: number): Promise<TrendData> => {
  const key = `dashboard:trends:${days ?? 'default'}`;
  return cachedRequest(key, DASHBOARD_TTL_MS, async () => {
    const response = await apiClient.get('/api/dashboard/trends', {
      params: { days }
    });
    return response.data;
  });
};

/**
 * 获取预警信息
 */
export const getDashboardAlerts = async (): Promise<AlertItem[]> => {
  const response = await apiClient.get('/api/dashboard/alerts');
  return response.data;
};
