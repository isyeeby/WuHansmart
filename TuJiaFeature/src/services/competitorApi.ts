import { apiClient } from '../config/api';

// ==================== 竞品情报模块 (Competitor) ====================

// 竞品监测项
export interface CompetitorMonitorItem {
  rank: number;
  unit_id: string;
  district: string;
  price: number;
  price_diff_percent: number;
  rating: number;
  comment_count: number;
  heat_score: number;
  bedroom_count: number;
  area_sqm: number;
  facility_count: number;
  house_tags?: string;
  tag_list?: string[];
}

// 竞品监测响应
export interface CompetitorMonitoringResponse {
  my_listing_id: string;
  my_price: number;
  district: string;
  competitor_count: number;
  competitors: CompetitorMonitorItem[];
}

// 雷达图维度
export interface RadarData {
  dimensions: string[];
  my_listing: {
    name: string;
    values: number[];
  };
  district_average: {
    name: string;
    values: number[];
  };
  district_best: {
    name: string;
    values: number[];
  };
}

// 竞争力雷达图响应
export interface CompetitivenessRadarResponse {
  my_listing_id: string;
  district: string;
  radar_data: RadarData;
  raw_values: {
    my_price: number;
    avg_price: number;
    my_rating: number;
    avg_rating: number;
  };
}

// 经营诊断响应
export interface BusinessDiagnosisResponse {
  my_listing_id: string;
  district: string;
  overall_score: number;
  grade: string;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  priority_actions: string[];
}

// 竞品预警项
export interface CompetitorAlertItem {
  type: string;
  level: string;
  message: string;
  detail: string;
  date: string;
}

// 竞品预警响应
export interface CompetitorAlertsResponse {
  my_listing_id: string;
  alert_count: number;
  alerts: CompetitorAlertItem[];
}

/**
 * 获取竞品监测列表
 * @param myListingId 我的房源ID
 * @param radius 监测半径（公里），默认1.0
 */
export const getCompetitorMonitoring = async (
  myListingId: string,
  radius?: number
): Promise<CompetitorMonitoringResponse> => {
  const response = await apiClient.get(`/api/competitor/monitoring/${myListingId}`, {
    params: { radius }
  });
  return response.data;
};

/**
 * 获取竞争力雷达图数据
 * @param myListingId 我的房源ID
 */
export const getCompetitivenessRadar = async (
  myListingId: string
): Promise<CompetitivenessRadarResponse> => {
  const response = await apiClient.get(`/api/competitor/radar/${myListingId}`);
  return response.data;
};

/**
 * 获取经营诊断建议
 * @param myListingId 我的房源ID
 */
export const getBusinessDiagnosis = async (
  myListingId: string
): Promise<BusinessDiagnosisResponse> => {
  const response = await apiClient.get(`/api/competitor/diagnosis/${myListingId}`);
  return response.data;
};

/**
 * 获取竞品动态预警
 * @param myListingId 我的房源ID
 * @param days 最近N天，默认7
 */
export const getCompetitorAlerts = async (
  myListingId: string,
  days?: number
): Promise<CompetitorAlertsResponse> => {
  const response = await apiClient.get(`/api/competitor/alerts/${myListingId}`, {
    params: { days }
  });
  return response.data;
};

/**
 * 手动添加竞品监测
 * @param myListingId 我的房源ID
 * @param competitorId 竞品房源ID
 */
export const addCompetitorMonitor = async (
  myListingId: string,
  competitorId: string
): Promise<{ success: boolean; message: string }> => {
  const response = await apiClient.post('/api/competitor/add-monitor', null, {
    params: { my_listing_id: myListingId, competitor_id: competitorId }
  });
  return response.data;
};
