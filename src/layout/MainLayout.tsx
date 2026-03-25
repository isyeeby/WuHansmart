import { Layout, Menu, Dropdown, Space, Breadcrumb, Drawer, Grid } from 'antd';
import { Link, Outlet, useLocation } from 'react-router-dom';
import React, { useEffect, useState } from 'react';
import OnboardingModal from '../components/OnboardingModal';
import {
  PieChartOutlined,
  DesktopOutlined,
  HeatMapOutlined,
  ExperimentOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuOutlined,
  HeartOutlined,
  BarChartOutlined,
  SettingOutlined,
  CompassOutlined,
  HomeOutlined,
  PlusCircleOutlined,
  BugOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import { motion, AnimatePresence } from 'motion/react';

const { Header, Content, Footer, Sider } = Layout;
const { useBreakpoint } = Grid;

const MainLayout: React.FC = () => {
  const location = useLocation();
  const { user, logout, refreshUser } = useAuth();
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  useEffect(() => {
    if (user && user.onboarding_completed === false) {
      setOnboardingOpen(true);
    } else {
      setOnboardingOpen(false);
    }
  }, [user]);
  const [collapsed, setCollapsed] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.lg;

  // 获取当前选中的菜单项
  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path === '/') return ['/'];
    return [path];
  };

  // 获取展开的子菜单
  const getOpenKeys = () => {
    return [];
  };

  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: '首页', path: '/' },
    { key: '/dashboard', icon: <DesktopOutlined />, label: '经营驾驶舱', path: '/dashboard' },
    { key: '/listings', icon: <AppstoreOutlined />, label: '房源列表', path: '/listings' },
    { key: '/my-listings', icon: <PlusCircleOutlined />, label: '我的房源', path: '/my-listings' },
    { key: '/analysis', icon: <PieChartOutlined />, label: '商圈分析', path: '/analysis' },
    { key: '/competitor', icon: <CompassOutlined />, label: '竞品情报', path: '/competitor' },
    { key: '/prediction', icon: <ExperimentOutlined />, label: '智能定价', path: '/prediction' },
    { key: '/recommendation', icon: <HeatMapOutlined />, label: '个性化推荐', path: '/recommendation' },
    { key: '/favorites', icon: <HeartOutlined />, label: '我的收藏', path: '/favorites' },
    { key: '/api-test', icon: <BugOutlined />, label: '接口测试', path: '/api-test' },
  ];

  const userMenu = {
    items: [
      {
        key: 'profile',
        label: <Link to="/profile">个人信息</Link>,
        icon: <SettingOutlined />,
      },
      {
        type: 'divider' as const,
      },
      {
        key: 'logout',
        label: '退出登录',
        icon: <LogoutOutlined />,
        onClick: logout,
      },
    ],
  };

  const getPageTitle = () => {
    const path = location.pathname;
    // 子页面标题映射
    const pageTitles: Record<string, string> = {
      '/': '首页',
      '/dashboard': '经营驾驶舱',
      '/listings': '房源列表',
      '/my-listings': '我的房源',
      '/analysis': '商圈分析',
      '/competitor': '竞品情报',
      '/prediction': '智能定价预测',
      '/recommendation': '个性化推荐',
      '/favorites': '我的收藏',
      '/api-test': '接口测试',
      '/profile': '个人信息',
    };

    // 房源详情特殊处理
    if (path.startsWith('/listing/')) return '房源详情';

    return pageTitles[path] || '系统';
  };

  const getBreadcrumbItems = () => {
    const items = [{ title: '首页' }];
    if (location.pathname !== '/') {
      items.push({ title: getPageTitle() });
    }
    return items;
  };

  const MenuContent = (
    <div className="h-full flex flex-col" style={{ background: '#faf8f5' }}>
      {/* Logo */}
      <div className="px-6 py-8">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-10 h-10 border-2 border-[#1a1a1a] flex items-center justify-center flex-shrink-0">
            <span className="font-serif text-lg font-bold text-[#1a1a1a]">宿</span>
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="font-serif text-base font-semibold text-[#1a1a1a] leading-tight whitespace-nowrap">民宿智策</h1>
              <p className="text-[10px] text-[#999] tracking-wider uppercase whitespace-nowrap">Intelligence</p>
            </div>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <Menu
        mode="inline"
        selectedKeys={getSelectedKeys()}
        defaultOpenKeys={getOpenKeys()}
        items={menuItems.map(item => ({
          key: item.key,
          icon: item.icon,
          label: (
            <Link
              to={item.path}
              onClick={() => setDrawerVisible(false)}
              className="font-sans"
            >
              {item.label}
            </Link>
          ),
        }))}
        className="flex-1 border-none px-3"
        style={{ background: 'transparent' }}
      />

      {/* Footer */}
      {!collapsed && (
        <div className="px-6 py-6 border-t border-[#ebe7e0]">
          <p className="text-xs text-[#999] tracking-wide">
            Wuhan B&B<br />Intelligence System
          </p>
        </div>
      )}
    </div>
  );

  return (
    <Layout className="min-h-screen" style={{ background: '#faf8f5' }}>
      <OnboardingModal
        open={onboardingOpen}
        user={user}
        onDone={() => void refreshUser()}
      />
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          breakpoint="lg"
          width={260}
          collapsedWidth={80}
          trigger={null}
          className="!bg-[#faf8f5]"
          style={{
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
            zIndex: 100,
            boxShadow: '2px 0 20px rgba(0, 0, 0, 0.04)',
          }}
        >
          {MenuContent}
        </Sider>
      )}

      {isMobile && (
        <Drawer
          placement="left"
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={280}
          closable={false}
          styles={{ body: { padding: 0, background: '#faf8f5' } }}
        >
          {MenuContent}
        </Drawer>
      )}

      <Layout
        style={{
          marginLeft: isMobile ? 0 : (collapsed ? 80 : 260),
          transition: 'margin-left 0.3s ease',
        }}
      >
        {/* Header */}
        <Header
          className="!bg-white/80 backdrop-blur-sm border-b border-[#ebe7e0] sticky top-0 z-50"
          style={{
            padding: '0 32px',
            height: 72,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div className="flex items-center gap-6">
            {isMobile && (
              <MenuOutlined
                className="text-xl cursor-pointer text-[#4a4a4a] hover:text-[#1a1a1a] transition-colors"
                onClick={() => setDrawerVisible(true)}
              />
            )}
            <Breadcrumb
              items={getBreadcrumbItems()}
              className="text-sm"
            />
          </div>

          <Dropdown menu={userMenu} placement="bottomRight" arrow>
            <Space className="cursor-pointer hover:bg-[#f5f2ed] px-4 py-2 rounded transition-colors">
              <div className="w-8 h-8 rounded-full bg-[#1a1a1a] flex items-center justify-center">
                <UserOutlined className="text-white text-sm" />
              </div>
              <div className="hidden md:flex flex-col leading-tight">
                <span className="text-sm font-medium text-[#1a1a1a]">{user?.username || '管理员'}</span>
                <span className="text-xs text-[#999]">系统用户</span>
              </div>
            </Space>
          </Dropdown>
        </Header>

        {/* Content */}
        <Content style={{ margin: '32px', overflow: 'initial' }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </Content>

        {/* Footer */}
        <Footer className="!bg-transparent text-center py-8">
          <p className="text-xs text-[#999] tracking-wide">
            Wuhan B&B Intelligence System ©{new Date().getFullYear()}
          </p>
        </Footer>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
