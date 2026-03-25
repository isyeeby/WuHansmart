import { apiClient } from '../config/api';

// 用户资料类型（与后端 UserResponse 对齐）
export interface UserProfile {
  id: number;
  username: string;
  phone?: string;
  full_name?: string;
  email?: string;
  is_active: boolean;
  preferred_district?: string;
  preferred_price_min?: number;
  preferred_price_max?: number;
  travel_purpose?: string;
  required_facilities?: string[];
  user_role?: string | null;
  onboarding_completed?: boolean;
  onboarding_skipped_at?: string | null;
  persona_answers?: Record<string, unknown> | null;
  persona_summary?: string | null;
}

// 用户偏好设置
export interface UserPreferences {
  preferred_district?: string;
  preferred_price_min?: number;
  preferred_price_max?: number;
  travel_purpose?:
    | '情侣'
    | '家庭'
    | '商务'
    | '考研'
    | '团建聚会'
    | '医疗陪护'
    | '宠物友好'
    | '长租'
    | '休闲';
  required_facilities?: string[];
}

/**
 * 获取当前用户信息
 */
export const getUserProfile = async (): Promise<UserProfile> => {
  const response = await apiClient.get('/api/user/me');
  return response.data;
};

/**
 * 更新用户资料
 * @param profile 用户资料
 */
export const updateUserProfile = async (
  profile: Partial<UserProfile>
): Promise<UserProfile> => {
  const response = await apiClient.put('/api/user/me', profile);
  return response.data;
};

/**
 * 获取用户偏好设置
 */
export const getUserPreferences = async (): Promise<UserPreferences> => {
  const response = await apiClient.get('/api/user/me/preferences');
  return response.data;
};

/**
 * 更新用户偏好设置
 * @param preferences 偏好设置
 */
export const updateUserPreferences = async (
  preferences: UserPreferences
): Promise<UserPreferences> => {
  const response = await apiClient.put('/api/user/me/preferences', preferences);
  return response.data;
};
