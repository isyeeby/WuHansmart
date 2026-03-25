import { apiClient } from '../config/api';

// ==================== 收藏模块 (Favorites) ====================

export interface FavoriteItem {
  id: number;
  user_id?: number;
  unit_id: string;
  folder_name?: string;
  created_at: string;
}

export interface FavoriteListing {
  unit_id: string;
  title: string;
  price: number;
  original_price?: number;
  rating: number;
  total_reviews?: number;
  tags: string[];
  image_url?: string;
  district: string;
  bedrooms?: number;
  bathrooms?: number;
  area?: number;
  price_change?: number;
  last_viewed?: string;
  folder_id?: string;
  alert_enabled?: boolean;
}

export interface FavoriteFolder {
  id?: string;
  name: string;
  count: number;
  alert_enabled?: boolean;
  created_at?: string;
}

export interface HistoryItem {
  unit_id: string;
  title: string;
  price: number;
  rating: number;
  image_url?: string;
  district: string;
  viewed_at: string;
}

export interface AlertSettings {
  price_drop_threshold?: number;
  price_increase_threshold?: number;
  notify_email?: boolean;
  notify_sms?: boolean;
}

export const addFavorite = async (unitId: string): Promise<FavoriteItem> => {
  const response = await apiClient.post(`/api/favorites/${unitId}`);
  return response.data;
};

export const removeFavorite = async (unitId: string): Promise<void> => {
  await apiClient.delete(`/api/favorites/${unitId}`);
};

export const getFavorites = async (): Promise<FavoriteItem[]> => {
  const response = await apiClient.get('/api/favorites');
  return response.data;
};

export const getFavoriteFolders = async (): Promise<FavoriteFolder[]> => {
  const response = await apiClient.get('/api/favorites/folders');
  return response.data;
};

/** 登记收藏夹名称（空夹无独立记录，移动房源到该名称后即计入统计） */
export const createFavoriteFolder = async (name: string): Promise<FavoriteFolder> => {
  const response = await apiClient.post('/api/user/me/favorites/folders', { name });
  return response.data;
};

/** folderName 为收藏夹名称字符串（非数字 id） */
export const moveFavoriteToFolder = async (unitId: string, folderName: string): Promise<void> => {
  await apiClient.put(`/api/user/me/favorites/${unitId}/folder`, null, {
    params: { folder_name: folderName },
  });
};

export const getHistory = async (limit?: number): Promise<HistoryItem[]> => {
  const response = await apiClient.get('/api/user/me/history', {
    params: { limit },
  });
  return response.data;
};

export const addToHistory = async (unitId: string): Promise<void> => {
  await apiClient.post('/api/user/me/history', { unit_id: unitId });
};

export const getAlertSettings = async (): Promise<AlertSettings> => {
  const response = await apiClient.get('/api/favorites/alerts');
  return response.data;
};

export const updateAlertSettings = async (
  unitId: string,
  enabled: boolean,
  threshold?: number
): Promise<void> => {
  await apiClient.put(`/api/favorites/${unitId}/alert`, null, {
    params: { enabled, threshold: threshold ?? 0.1 },
  });
};

export const setFavoriteAlert = async (
  unitId: string,
  enabled: boolean,
  threshold?: number
): Promise<void> => {
  await apiClient.put(`/api/favorites/${unitId}/alert`, null, {
    params: { enabled, threshold: threshold ?? 0.1 },
  });
};

/** @deprecated 使用 addFavorite */
export const addFavoriteNew = addFavorite;
/** @deprecated 使用 removeFavorite */
export const removeFavoriteNew = removeFavorite;
/** @deprecated 使用 getFavorites */
export const getFavoritesNew = getFavorites;
