import { apiClient } from '../config/api';

// 标签分类类型
export interface TagCategory {
  category: string;
  category_name: string;
  tags: string[];
}

// 热门标签项
export interface PopularTag {
  tag_name: string;
  usage_count: number;
  avg_price: number;
  premium_percent: number;
  percent: number;
}

// 热门标签响应
export interface PopularTagsResponse {
  district?: string;
  tags: PopularTag[];
}

/**
 * 获取标签分类
 * 获取所有标签分类及标签列表，用于房源上传时选择标签
 */
export const getTagCategories = async (): Promise<TagCategory[]> => {
  const response = await apiClient.get('/api/tags/categories');
  return response.data;
};

/**
 * 获取热门标签
 * @param district 行政区筛选
 * @param limit 数量限制，默认20
 */
export const getPopularTags = async (
  district?: string,
  limit?: number
): Promise<PopularTagsResponse> => {
  const response = await apiClient.get('/api/tags/popular', {
    params: { district, limit }
  });
  return response.data;
};
