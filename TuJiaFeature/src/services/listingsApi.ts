import { apiClient } from '../config/api';

// 房源列表项类型
export interface ListingItem {
  unit_id: string;
  title: string;
  district: string;
  trade_area?: string | null;
  final_price: number;
  original_price?: number | null;
  discount_rate?: number | null;
  rating?: number | null;
  favorite_count?: number | null;
  pic_count?: number | null;
  cover_image?: string | null;
  house_tags?: string | null; // JSON格式标签数组
  comment_brief?: string | null;
  bedroom_count?: number | null;
  bed_count?: number | null;
  longitude?: number | null;
  latitude?: number | null;
}

/** 详情接口：含途家 dynamicModule 三模块（已解析为对象） */
export interface ListingDetail extends ListingItem {
  facility_module?: Record<string, unknown> | null;
  comment_module?: Record<string, unknown> | null;
  landlord_module?: Record<string, unknown> | null;
  detail_modules_note?: string | null;
}

// 房源列表响应类型
export interface ListingsResponse {
  total: number;
  page: number;
  size: number;
  items: ListingItem[];
}

// 房源列表查询参数
export interface ListingsQueryParams {
  district?: string;
  business_circle?: string;
  min_price?: number;
  max_price?: number;
  tags?: string; // 逗号分隔，如：近地铁,可做饭
  bedroom_count?: number;
  sort_by?: 'price_asc' | 'price_desc' | 'rating' | 'favorite_count';
  page?: number;
  size?: number;
}

// 图片分类类型
export interface ImageCategories {
  客厅: string[];
  卧室: string[];
  厨房: string[];
  卫生间: string[];
  阳台: string[];
  外景: string[];
  休闲: string[];
  其他: string[];
}

// 房源图片画廊响应
export interface ListingGallery {
  unit_id: string;
  title: string;
  total_pics: number;
  categories: ImageCategories;
}

// 相似房源类型
export interface SimilarListing {
  unit_id: string;
  title: string;
  district: string;
  final_price: number;
  rating: number;
  similarity_score: number;
  cover_image?: string | null;
}

// 价格日历单项
export interface PriceCalendarItem {
  date: string;
  price: number;
  can_booking: boolean;
}

// 价格统计
export interface PriceStats {
  min: number;
  max: number;
  avg: number;
}

// 日期范围
export interface DateRange {
  start: string;
  end: string;
}

// 价格日历响应
export interface PriceCalendarResponse {
  unit_id: string;
  title: string;
  date_range: DateRange;
  calendar: PriceCalendarItem[];
  price_stats: PriceStats;
}

/**
 * 获取房源列表
 * @param params 查询参数
 */
export const getListings = async (params?: ListingsQueryParams): Promise<ListingsResponse> => {
  const response = await apiClient.get('/api/listings', { params });
  return response.data;
};

/**
 * 获取房源详情
 * @param unitId 房源ID
 */
export const getListingDetail = async (unitId: string): Promise<ListingDetail> => {
  const response = await apiClient.get(`/api/listings/${unitId}`);
  return response.data;
};

/**
 * 获取房源图片画廊
 * @param unitId 房源ID
 */
export const getListingGallery = async (unitId: string): Promise<ListingGallery> => {
  const response = await apiClient.get(`/api/listings/${unitId}/gallery`);
  return response.data;
};

/**
 * 获取相似房源
 * @param unitId 房源ID
 * @param limit 数量限制，默认10
 */
export const getSimilarListings = async (
  unitId: string,
  limit?: number
): Promise<SimilarListing[]> => {
  const response = await apiClient.get(`/api/listings/${unitId}/similar`, {
    params: { limit }
  });
  return response.data;
};

/**
 * 获取热门房源排行
 * @param district 行政区筛选
 * @param limit 数量限制，默认10
 */
export const getHotListings = async (
  district?: string,
  limit?: number
): Promise<ListingItem[]> => {
  const response = await apiClient.get('/api/listings/hot/ranking', {
    params: { district, limit }
  });
  return response.data;
};

/**
 * 获取房源价格日历
 * @param unitId 房源ID
 * @param startDate 开始日期 (YYYY-MM-DD)
 * @param endDate 结束日期 (YYYY-MM-DD)
 * @param includeHistory true 时返回库内该房源全部日历日（含历史），不传 start/end 时与后端约定一致
 */
export const getListingPriceCalendar = async (
  unitId: string,
  startDate?: string,
  endDate?: string,
  includeHistory?: boolean
): Promise<PriceCalendarResponse> => {
  const params: Record<string, string | boolean> = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  if (includeHistory) params.include_history = true;
  const response = await apiClient.get(`/api/listings/${unitId}/calendar`, { params });
  return response.data;
};
