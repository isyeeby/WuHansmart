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
    <div className="mb-6 sm:mb-8">
      {/* 顶部导航区 */}
      {(showBack || extra) && (
        <div className="mb-4 flex items-center justify-between sm:mb-6">
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
      <div className="border-b border-[#ebe7e0] pb-4 sm:pb-6">
        <Space direction="vertical" size={8} className="w-full">
          {/* 分类标签 */}
          <Text className="text-[10px] font-medium uppercase tracking-[0.18em] text-[#999] sm:text-xs sm:tracking-[0.2em]">
            {category}
          </Text>

          {/* 主标题 */}
          <div className="flex flex-col items-stretch justify-between gap-4 sm:flex-row sm:items-start sm:gap-6">
            <div className="min-w-0 flex-1">
              <Title
                level={4}
                className="!m-0 font-serif text-xl font-semibold leading-tight text-[#1a1a1a] sm:text-2xl"
              >
                {title}
              </Title>

              {/* 副标题 */}
              {subtitle && (
                <p className="mt-2 max-w-3xl text-xs leading-relaxed text-[#6b6b6b] sm:mt-3 sm:text-sm">
                  {subtitle}
                </p>
              )}
            </div>

            {/* 额外的右侧内容 */}
            {children ? <div className="shrink-0 sm:self-start">{children}</div> : null}
          </div>
        </Space>
      </div>
    </div>
  );
};

export default PageHeader;
