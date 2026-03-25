import React from 'react';
import { Typography, Space, Button } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Text, Title } = Typography;

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  category?: string;
  showBack?: boolean;
  extra?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * 页面头部组件 - 墨白禅意风格
 * 统一处理页面标题、副标题、返回按钮和额外操作
 */
const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  category = 'System',
  showBack = false,
  extra,
  children,
}) => {
  const navigate = useNavigate();

  return (
    <div className="mb-8">
      {/* 顶部导航区 */}
      {(showBack || extra) && (
        <div className="flex items-center justify-between mb-6">
          {showBack && (
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate(-1)}
              className="text-[#6b6b6b] hover:text-[#1a1a1a] -ml-4"
            >
              返回
            </Button>
          )}
          {extra && <div className="flex items-center gap-3">{extra}</div>}
        </div>
      )}

      {/* 标题区 */}
      <div className="border-b border-[#ebe7e0] pb-6">
        <Space direction="vertical" size={8} className="w-full">
          {/* 分类标签 */}
          <Text className="text-xs uppercase tracking-[0.2em] text-[#999] font-medium">
            {category}
          </Text>

          {/* 主标题 */}
          <div className="flex items-start justify-between gap-6">
            <div className="flex-1">
              <Title
                level={4}
                className="!m-0 font-serif text-2xl font-semibold text-[#1a1a1a] leading-tight"
              >
                {title}
              </Title>

              {/* 副标题 */}
              {subtitle && (
                <p className="text-sm text-[#6b6b6b] mt-3 leading-relaxed max-w-3xl">
                  {subtitle}
                </p>
              )}
            </div>

            {/* 额外的右侧内容 */}
            {children}
          </div>
        </Space>
      </div>
    </div>
  );
};

export default PageHeader;
