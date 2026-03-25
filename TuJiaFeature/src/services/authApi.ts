import { apiClient } from '../config/api';

// 用户类型（与后端 UserResponse 对齐）
export interface User {
  id: number;
  username: string;
  phone?: string;
  full_name?: string;
  email?: string;
  is_active: boolean;
  created_at: string;
  preferred_district?: string;
  preferred_price_min?: number;
  preferred_price_max?: number;
  travel_purpose?: string;
  required_facilities?: string[];
  user_role?: string | null;
  onboarding_completed: boolean;
  onboarding_skipped_at?: string | null;
  persona_answers?: Record<string, unknown> | null;
  persona_summary?: string | null;
}

// 注册请求参数
export interface RegisterParams {
  username: string;
  password: string;
  phone?: string;
  full_name?: string;
}

// 登录请求参数
export interface LoginParams {
  username: string;
  password: string;
}

// 登录响应
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

/**
 * 用户注册
 * @param params 注册信息
 */
export const register = async (params: RegisterParams): Promise<User> => {
  const response = await apiClient.post('/api/auth/register', params);
  return response.data;
};

/**
 * 用户登录 (JSON方式)
 * @param params 登录信息
 */
export const loginJson = async (params: LoginParams): Promise<LoginResponse> => {
  const response = await apiClient.post('/api/auth/login-json', params);
  return response.data;
};

/**
 * 用户登录 (OAuth2表单方式)
 * @param username 用户名
 * @param password 密码
 */
export const login = async (username: string, password: string): Promise<LoginResponse> => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  
  const response = await apiClient.post('/api/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

/**
 * 获取当前登录用户信息
 */
export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get('/api/auth/me');
  return response.data;
};

/**
 * 刷新Token
 */
export const refreshToken = async (): Promise<LoginResponse> => {
  const response = await apiClient.post('/api/auth/refresh');
  return response.data;
};
