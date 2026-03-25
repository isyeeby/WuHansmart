/**
 * 房源对比模块 API 服务
 */
import { apiClient } from '../config/api';

export interface ComparisonRequest {
  unit_ids: string[];
  comparison_type?: string;
}

export interface CompareListingScores {
  price: number;
  location: number;
  facility: number;
  rating: number;
  size: number;
}

export interface CompareListingResponse {
  unit_id: string;
  title: string;
  price: number;
  rating: number;
  total_reviews: number;
  district: string;
  bedrooms: number;
  bathrooms: number;
  area: number | null;
  image_url: string | null;
  facilities: string[];
  scores: CompareListingScores;
  value_score: number;
}

export interface ComparisonResult {
  unit_ids: string[];
  comparison_type: string;
  listings: CompareListingResponse[];
  summary: {
    price_range: { min: number; max: number; avg: number };
    rating_range: { min: number; max: number; avg: number };
    area_range: { min: number; max: number; avg: number };
  };
  radar_chart: {
    dimensions: string[];
    datasets: { name: string; values: number[] }[];
  };
  winner: {
    unit_id: string;
    title: string;      // 房源简称
    district: string;
    value_score: number;
    reason: string;
    highlights?: string[];  // 优势列表
  } | null;
  error?: string;
  scoring_methodology?: {
    description: string;
    price_score: { description: string; calculation: string; note: string };
    rating_score: { description: string; calculation: string; note: string };
    size_score: { description: string; calculation: string; note: string };
    facility_score: { description: string; calculation: string; note: string };
    location_score: { description: string; note: string };
    value_score: { description: string; calculation: string; note: string };
  };
}

export interface QuickComparison {
  unit_id1: string;
  unit_id2: string;
  comparisons: {
    dimension: string;
    unit1_value: number;
    unit2_value: number;
    difference: number;
    winner: number;
    note: string;
  }[];
  summary: {
    unit1_wins: number;
    unit2_wins: number;
    overall_winner: number;
  };
}

/**
 * 多房源对比
 */
export const compareListings = async (data: ComparisonRequest): Promise<ComparisonResult> => {
  const response = await apiClient.post('/api/compare/', data);
  return response.data;
};

/**
 * 快速对比两个房源
 */
export const quickCompare = async (unitId1: string, unitId2: string): Promise<QuickComparison> => {
  const response = await apiClient.get(`/api/compare/quick/${unitId1}/${unitId2}`);
  return response.data;
};

/**
 * 保存对比方案
 */
export const saveComparison = async (data: ComparisonRequest, name?: string): Promise<any> => {
  const response = await apiClient.post('/api/compare/save', data, {
    params: { name }
  });
  return response.data;
};

/**
 * 获取对比历史列表
 */
export const getComparisonList = async (): Promise<any> => {
  const response = await apiClient.get('/api/compare/list');
  return response.data;
};
