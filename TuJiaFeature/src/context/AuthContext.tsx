import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { message } from 'antd';
import { login as apiLogin, getCurrentUser, type User } from '../services/authApi';

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
  token: string | null;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  // 初始化时检查 localStorage 并验证 token
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('token');
      
      if (storedToken) {
        setToken(storedToken);
        // 验证 token 是否有效，获取用户信息
        try {
          const userInfo = await getCurrentUser();
          setUser(userInfo);
          localStorage.setItem('user', JSON.stringify(userInfo));
        } catch (error) {
          console.error('Token 无效，清除登录状态:', error);
          setToken(null);
          setUser(null);
          localStorage.removeItem('token');
          localStorage.removeItem('user');
        }
      }
      setIsLoading(false);
    };
    
    initAuth();
  }, []);

  // 登录成功后获取用户信息
  const fetchUserInfo = async () => {
    try {
      const userInfo = await getCurrentUser();
      setUser(userInfo);
      localStorage.setItem('user', JSON.stringify(userInfo));
    } catch (error) {
      console.error('获取用户信息失败:', error);
      // 获取用户信息失败，清除 token
      setToken(null);
      localStorage.removeItem('token');
    }
  };

  const login = async (username: string, password: string) => {
    try {
      // 调用后端登录接口
      const response = await apiLogin(username, password);
      const accessToken = response.access_token;
      
      // 存储 token
      setToken(accessToken);
      localStorage.setItem('token', accessToken);
      
      // 获取用户信息
      await fetchUserInfo();
      
      message.success('登录成功');

      // 登录后跳转回之前的页面或首页
      const origin = (location.state as any)?.from?.pathname || '/';
      navigate(origin);
    } catch (error: any) {
      console.error('登录失败:', error);
      throw error; // 抛出错误让 Login 页面处理
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    message.info('已退出登录');
    navigate('/login');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        refreshUser: fetchUserInfo,
        isAuthenticated: !!user,
        token,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
