/// <reference types="vite/client" />
import axios from 'axios';

// API 基础配置：开发默认空字符串走 Vite 代理；生产可通过 VITE_API_BASE_URL 指定跨域 API
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

// 创建 axios 实例
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动添加 JWT token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // 确保 Content-Type 正确设置
  if (!config.headers['Content-Type']) {
    config.headers['Content-Type'] = 'application/json';
  }
  return config;
});

// API 端点
export const API_ENDPOINTS = {
  LOGIN: '/api/auth/login',
};

// Token 响应类型
export interface TokenResponse {
  access_token: string;
  token_type?: string;
  expires_in?: number;
}
