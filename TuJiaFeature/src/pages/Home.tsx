import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Card, Row, Col, Button, Typography, Tag, Spin, Tooltip, Alert } from 'antd';
import ReactECharts from 'echarts-for-react';
import { motion } from 'motion/react';
import {
  ArrowRightOutlined,
  EnvironmentOutlined,
  HomeOutlined,
  BarChartOutlined,
  StarOutlined,
  ThunderboltOutlined,
  PieChartOutlined,
  CompassOutlined,
  HeartOutlined,
  ArrowUpOutlined,
  QuestionCircleOutlined,
  HeatMapOutlined,
  AppstoreOutlined,
  PlusCircleOutlined,
} from '@ant-design/icons';
import { ZEN_COLORS, createLineOption } from '../utils/echartsTheme';
import { getKpiDashboard, getTopDistricts, getDashboardTrends, type KpiData, type TopDistrict, type TrendData } from '../services/dashboardApi';
import { getHomeRecommendations, type HomeRecommendation } from '../services/homeApi';
import { useAuth } from '../context/AuthContext';

const { Text, Title } = Typography;

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

const sectionMotion = (reduced: boolean) =>
  reduced
    ? { initial: false as const, animate: { opacity: 1 } }
    : {
        initial: { opacity: 0, y: 20 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, margin: '-48px' },
        transition: { duration: 0.45, ease: [0.4, 0, 0.2, 1] as const },
      };

type QuickLinkItem = {
  to: string;
  icon: React.ReactNode;
  title: string;
  desc: string;
  color: string;
  bgColor: string;
};

const QUICK_LINKS_BASE: QuickLinkItem[] = [
  {
    to: '/recommendation',
    icon: <HeatMapOutlined />,
    title: '个性化推荐',
    desc: '按问卷偏好',
    color: ZEN_COLORS.ochre,
    bgColor: 'rgba(196, 92, 62, 0.1)',
  },
  {
    to: '/listings',
    icon: <AppstoreOutlined />,
    title: '房源列表',
    desc: '全城浏览',
    color: ZEN_COLORS.gold,
    bgColor: 'rgba(184, 149, 110, 0.1)',
  },
  {
    to: '/my-listings',
    icon: <PlusCircleOutlined />,
    title: '我的房源',
    desc: '竞品与定价',
    color: ZEN_COLORS.jade,
    bgColor: 'rgba(90, 138, 110, 0.1)',
  },
  {
    to: '/prediction',
    icon: <PieChartOutlined />,
    title: '智能定价',
    desc: 'XGBoost预测',
    color: ZEN_COLORS.ochre,
    bgColor: 'rgba(196, 92, 62, 0.1)',
  },
  {
    to: '/investment',
    icon: <BarChartOutlined />,
    title: '投资分析',
    desc: 'ROI计算器',
    color: ZEN_COLORS.jade,
    bgColor: 'rgba(90, 138, 110, 0.1)',
  },
  {
    to: '/comparison',
    icon: <CompassOutlined />,
    title: '房源对比',
    desc: '多维度分析',
    color: ZEN_COLORS.gold,
    bgColor: 'rgba(184, 149, 110, 0.1)',
  },
  {
    to: '/opportunities',
    icon: <ThunderboltOutlined />,
    title: '价格洼地',
    desc: '投资机会',
    color: ZEN_COLORS.ochre,
    bgColor: 'rgba(196, 92, 62, 0.1)',
  },
  {
    to: '/favorites',
    icon: <HeartOutlined />,
    title: '我的收藏',
    desc: '管理房源',
    color: ZEN_COLORS.gold,
    bgColor: 'rgba(184, 149, 110, 0.1)',
  },
];

function orderQuickLinksForRole(role: string | null | undefined): QuickLinkItem[] {
  const orderMap: Record<string, string[]> = {
    operator: [
      '/my-listings',
      '/prediction',
      '/comparison',
      '/listings',
      '/recommendation',
      '/investment',
      '/opportunities',
      '/favorites',
    ],
    investor: [
      '/investment',
      '/opportunities',
      '/comparison',
      '/recommendation',
      '/listings',
      '/prediction',
      '/my-listings',
      '/favorites',
    ],
    guest: [
      '/recommendation',
      '/listings',
      '/favorites',
      '/comparison',
      '/investment',
      '/opportunities',
      '/prediction',
      '/my-listings',
    ],
  };
  const order = orderMap[role || 'guest'] || orderMap.guest;
  const byTo = new Map(QUICK_LINKS_BASE.map((x) => [x.to, x]));
  const seen = new Set<string>();
  const out: QuickLinkItem[] = [];
  for (const p of order) {
    const item = byTo.get(p);
    if (item && !seen.has(p)) {
      out.push(item);
      seen.add(p);
    }
  }
  for (const item of QUICK_LINKS_BASE) {
    if (!seen.has(item.to)) out.push(item);
  }
  return out;
}

function sectionHeading(accent: 'ochre' | 'jade' | 'gold' | 'ink', label: string, extra?: React.ReactNode) {
  const bar =
    accent === 'ochre'
      ? 'bg-[var(--ochre)]'
      : accent === 'jade'
        ? 'bg-[var(--jade)]'
        : accent === 'gold'
          ? 'bg-[var(--gold)]'
          : 'bg-[var(--ink-black)]';
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <h2 className="flex items-center gap-3 text-lg font-[var(--font-serif)] font-semibold tracking-tight text-[var(--ink-black)] sm:text-xl">
        <span className={`block min-h-[1.25rem] w-1 self-stretch rounded-full ${bar}`} aria-hidden />
        {label}
      </h2>
      {extra}
    </div>
  );
}

function tagLabel(tag: unknown): string {
  if (typeof tag === 'string') return tag;
  if (tag && typeof tag === 'object') {
    const o = tag as Record<string, unknown>;
    if (typeof o.text === 'string') return o.text;
    if (typeof o.tagText === 'string') return o.tagText;
    return JSON.stringify(tag);
  }
  return String(tag);
}

const Home: React.FC = () => {
  const { user } = useAuth();
  const reducedMotion = usePrefersReducedMotion();
  const sm = sectionMotion(reducedMotion);
  const quickLinks = useMemo(() => orderQuickLinksForRole(user?.user_role), [user?.user_role]);

  const [loading, setLoading] = useState(true);
  const [kpiData, setKpiData] = useState<KpiData | null>(null);
  const [recommendations, setRecommendations] = useState<HomeRecommendation[]>([]);
  const [hotDistricts, setHotDistricts] = useState<TopDistrict[]>([]);
  const [trendData, setTrendData] = useState<TrendData | null>(null);

  useEffect(() => {
    fetchHomeData();
  }, []);

  const fetchHomeData = async () => {
    try {
      setLoading(true);
      const [kpiRes, recommendsRes, topDistrictsRes, trendsRes] = await Promise.allSettled([
        getKpiDashboard(),
        getHomeRecommendations(6),
        getTopDistricts(8),
        // 与 /api/dashboard/trends 的 days 校验一致：ge=7，小于 7 会 422 导致无数据
        getDashboardTrends(14),
      ]);

      if (kpiRes.status === 'fulfilled') {
        setKpiData(kpiRes.value);
      } else {
        console.error('KPI 接口失败:', kpiRes.reason);
      }

      if (recommendsRes.status === 'fulfilled') {
        setRecommendations(Array.isArray(recommendsRes.value) ? recommendsRes.value : []);
      } else {
        console.error('推荐接口失败:', recommendsRes.reason);
        setRecommendations([]);
      }

      if (topDistrictsRes.status === 'fulfilled') {
        setHotDistricts(Array.isArray(topDistrictsRes.value) ? topDistrictsRes.value : []);
      } else {
        console.error('热门商圈接口失败:', topDistrictsRes.reason);
        setHotDistricts([]);
      }

      if (trendsRes.status === 'fulfilled') {
        setTrendData(trendsRes.value);
      } else {
        console.error('趋势接口失败:', trendsRes.reason);
        setTrendData(null);
      }
    } catch (error) {
      console.error('获取首页数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const stats = [
    {
      label: '覆盖区域',
      value: kpiData?.district_count ?? '-',
      suffix: '个',
      icon: <EnvironmentOutlined />,
      color: ZEN_COLORS.jade,
      tooltip: '平台数据覆盖的商圈/行政区数量，反映数据广度',
    },
    {
      label: '房源样本',
      value: kpiData?.total_listings ?? '-',
      suffix: '套',
      icon: <HomeOutlined />,
      color: ZEN_COLORS.ochre,
      tooltip: '平台收录的民宿房源总数，用于价格分析和趋势预测',
    },
    {
      label: '全市均价',
      value: kpiData?.avg_price ?? '-',
      suffix: '元',
      icon: <BarChartOutlined />,
      color: ZEN_COLORS.gold,
      tooltip: '全市民宿的平均日租金价格，基于近期成交数据计算',
    },
    {
      label: '需求热度',
      value: kpiData?.occupancy_rate ?? '-',
      suffix: '%',
      icon: <StarOutlined />,
      color: ZEN_COLORS.gold,
      tooltip: '基于评分与收藏数构建的代理指标，反映市场关注度（非真实入住率）',
    },
    {
      label: '价格趋势',
      value: kpiData?.price_change_percent ?? '-',
      suffix: '%',
      icon: <ArrowUpOutlined />,
      color: ZEN_COLORS.ochre,
      tooltip: '本月截至今日与上月同期的价格变化百分比，基于价格日历日均值对比计算',
    },
    {
      label: '市场吸引力',
      value: kpiData?.avg_roi ?? '-',
      suffix: '%',
      icon: <ThunderboltOutlined />,
      color: ZEN_COLORS.jade,
      tooltip: '综合评分、收藏、供给等因素构建的启发式吸引力指数（非财务ROI）',
    },
  ];

  const districtBarSlice = useMemo(() => hotDistricts.slice(0, 8), [hotDistricts]);

  const districtBarOption = useMemo(() => {
    const top = districtBarSlice;
    if (top.length === 0) return null;
    const maxLc = Math.max(1, ...top.map((d) => d.listing_count));
    return {
      grid: { left: 6, right: 52, top: 6, bottom: 6, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: ZEN_COLORS.paperWhite,
        borderColor: ZEN_COLORS.paperWarm,
        textStyle: { color: ZEN_COLORS.inkBlack },
        extraCssText: 'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); border-radius: 4px;',
        formatter: (params: unknown) => {
          const arr = params as { data: { name: string; listing_count: number; heat: number; avg_price: number } }[];
          const d = arr[0]?.data;
          if (!d) return '';
          return `${d.name}<br/>房源 ${d.listing_count} 套<br/>热度分位 ${d.heat}（全市商圈内排名）<br/>均价 ${d.avg_price} 元/晚`;
        },
      },
      xAxis: {
        type: 'value',
        max: 100,
        show: false,
      },
      yAxis: {
        type: 'category',
        data: top.map((d) => d.name),
        inverse: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: ZEN_COLORS.inkMedium,
          fontSize: 11,
          width: 108,
          overflow: 'truncate',
          ellipsis: '…',
        },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 22,
          data: top.map((d) => ({
            value: Math.round((d.listing_count / maxLc) * 100),
            name: d.name,
            listing_count: d.listing_count,
            heat: d.heat,
            avg_price: d.avg_price,
          })),
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: (params: { dataIndex: number }) => {
              const i = params.dataIndex;
              if (i === 0) return ZEN_COLORS.ochre;
              if (i < 3) return ZEN_COLORS.gold;
              return ZEN_COLORS.jade;
            },
          },
          label: {
            show: true,
            position: 'right',
            color: ZEN_COLORS.inkMedium,
            fontSize: 11,
            formatter: (p: { data: { listing_count: number } }) => `${p.data.listing_count} 套`,
          },
        },
      ],
    };
  }, [districtBarSlice]);

  const districtBarHeight = Math.max(200, Math.min(340, districtBarSlice.length * 36 + 24));

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  const trendOption = createLineOption(
    trendData?.prices || [],
    trendData?.dates || [],
    ZEN_COLORS.ochre,
    '全市均价'
  );

  return (
    <div className="home-shell space-y-10 pb-14 sm:space-y-12">
      {/* 非对称 Hero */}
      <motion.section {...sm} className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -right-20 -top-24 h-80 w-80 rounded-full bg-[rgba(196,92,62,0.04)] blur-2xl" />
          <div className="absolute -bottom-32 -left-16 h-72 w-72 rounded-full bg-[rgba(90,138,110,0.05)] blur-2xl" />
        </div>

        <div className="relative grid items-center gap-10 border-b border-[var(--paper-warm)] pb-12 lg:grid-cols-12 lg:gap-8">
          <div className="lg:col-span-7">
            <Title
              level={2}
              className="home-hero-main-title !mb-4 !mt-0 !text-3xl !font-semibold !tracking-tight text-[var(--ink-black)] sm:!text-4xl"
              style={{ fontFamily: 'var(--font-song)' }}
            >
              武汉民宿智策系统
            </Title>
            <p className="mb-8 max-w-xl text-sm leading-relaxed text-[var(--ink-light)] sm:text-base">
              基于 Hive 数仓与 XGBoost 算法的民宿投资决策智能分析平台，提供价格预测、选址分析、竞品监控等数据支持。
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Link to="/prediction">
                <Button
                  type="primary"
                  size="large"
                  icon={<ThunderboltOutlined />}
                  className="!h-11 !border-none !bg-[var(--ink-black)] !px-6 hover:!bg-[var(--ink-dark)]"
                >
                  智能定价
                </Button>
              </Link>
              <Link to="/listings">
                <Button
                  size="large"
                  icon={<HomeOutlined />}
                  className="!h-11 !border-[var(--ink-black)] !px-6 !text-[var(--ink-black)] hover:!border-[var(--ink-black)] hover:!bg-[var(--ink-black)] hover:!text-white"
                >
                  浏览房源
                </Button>
              </Link>
            </div>
          </div>

          <div className="flex justify-start lg:col-span-5 lg:justify-end">
            <div className="home-hero-seal relative w-full max-w-sm px-6 py-10 sm:px-8 sm:py-12 lg:max-w-none">
              <div className="home-hero-seal__ambient" aria-hidden />
              <div className="home-hero-seal__grain" aria-hidden />
              <div className="home-hero-seal__accent-line" aria-hidden />

              <div className="home-hero-seal__plate mx-auto">
                <div className="home-hero-seal__ring home-hero-seal__ring_outer" aria-hidden />
                <div className="home-hero-seal__ring home-hero-seal__ring_inner" aria-hidden />
                <div className="home-hero-seal__glow-pulse" aria-hidden />
                <div className="home-hero-seal__plate-inner">
                  <div className="home-hero-seal__wordmark">
                    <span className="home-hero-seal__wordmark-main">民宿智策</span>
                    <span className="home-hero-seal__wordmark-sub">武汉 · 数据与决策</span>
                  </div>
                </div>
              </div>

              <p className="home-hero-seal__tagline mt-6 text-center text-xs leading-relaxed tracking-[0.12em] text-[var(--ink-muted)]">
                数据驱动 · 决策有据
              </p>
            </div>
          </div>
        </div>
      </motion.section>

      {/* 横向快捷入口 */}
      <motion.section {...sm}>
        {sectionHeading(
          'gold',
          '常用功能',
          <Text className="text-xs text-[var(--ink-muted)] lg:hidden">向左滑动查看更多</Text>
        )}
        <div className="home-quick-scroll -mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto px-1 pb-2 pt-1">
          {quickLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="zen-card group block w-[min(100%,200px)] shrink-0 snap-start rounded-lg border border-[var(--paper-warm)] no-underline transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-[var(--shadow-medium)]"
            >
              <div className="px-5 py-6 text-center">
                <div
                  className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full text-xl transition-transform duration-300 group-hover:scale-110"
                  style={{ backgroundColor: link.bgColor, color: link.color }}
                >
                  {link.icon}
                </div>
                <div className="text-sm font-medium text-[var(--ink-black)]">{link.title}</div>
                <div className="mt-1 text-xs text-[var(--ink-muted)]">{link.desc}</div>
              </div>
            </Link>
          ))}
        </div>
      </motion.section>

      {/* 数据概览：宣纸底整块 */}
      <motion.section {...sm}>
        <div className="paper-texture rounded-xl border border-[var(--paper-warm)] px-5 py-8 shadow-[var(--shadow-soft)] sm:px-8 sm:py-10">
          {sectionHeading('jade', '数据概览')}
          <Row gutter={[16, 16]}>
            {stats.map((stat, index) => (
              <Col xs={12} sm={8} lg={4} key={index}>
                <div className="group flex h-full items-center gap-3 rounded-lg border border-[var(--paper-warm)] bg-white/80 p-4 shadow-sm transition-[box-shadow,transform] hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)]">
                  <div
                    className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-lg transition-transform group-hover:scale-105"
                    style={{ backgroundColor: `${stat.color}18`, color: stat.color }}
                  >
                    {stat.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-0.5 flex items-center gap-1">
                      <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)] sm:text-xs">
                        {stat.label}
                      </span>
                      <Tooltip title={stat.tooltip} placement="top">
                        <QuestionCircleOutlined className="cursor-help text-[10px] text-[var(--paper-gray)] hover:text-[var(--ink-muted)]" />
                      </Tooltip>
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="font-[var(--font-serif)] text-xl font-semibold text-[var(--ink-black)] sm:text-2xl">
                        {stat.value}
                      </span>
                      <span className="text-xs text-[var(--ink-muted)] sm:text-sm">{stat.suffix}</span>
                    </div>
                  </div>
                </div>
              </Col>
            ))}
          </Row>
        </div>
      </motion.section>

      {/* 洞察区：左窄数据图 + 右宽推荐网格 */}
      <motion.section {...sm}>
        <Row gutter={[24, 24]} align="stretch">
          <Col xs={24} lg={9}>
            <div className="flex h-full flex-col gap-6">
              <Card
                bordered={false}
                className="!flex-1 !rounded-lg !border !border-[var(--paper-warm)] !shadow-[var(--shadow-soft)]"
                styles={{ body: { padding: 'var(--space-md) var(--space-lg)' } }}
                title={
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <div className="h-4 w-1 shrink-0 rounded-full bg-[var(--ochre)]" />
                      <Text className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--ink-muted)]">热门商圈</Text>
                    </div>
                    <Link to="/analysis">
                      <Button type="text" size="small" className="!text-[var(--ochre)] hover:!bg-[var(--ochre-pale)] shrink-0">
                        分析 <ArrowRightOutlined />
                      </Button>
                    </Link>
                  </div>
                }
              >
                {districtBarOption ? (
                  <>
                    <ReactECharts option={districtBarOption} style={{ height: districtBarHeight }} />
                    <Alert
                      type="info"
                      showIcon
                      className="mt-3 !rounded-md text-xs"
                      message="条形长度为房源数相对本榜第一的比例；悬停可看均价与热度分位。"
                    />
                  </>
                ) : (
                  <div className="flex h-[220px] flex-col items-center justify-center px-4 text-center text-sm text-[var(--ink-muted)]">
                    暂无热门商圈数据（当前缺少可聚合样本）
                  </div>
                )}
              </Card>

              <Card
                bordered={false}
                className="!rounded-lg !border !border-[var(--paper-warm)] !shadow-[var(--shadow-soft)]"
                styles={{ body: { padding: 'var(--space-md) var(--space-lg)' } }}
                title={
                  <div className="flex items-center gap-2">
                    <div className="h-4 w-1 rounded-full bg-[var(--jade)]" />
                    <Text className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--ink-muted)]">全市均价走势</Text>
                  </div>
                }
              >
                <ReactECharts option={trendOption} style={{ height: 200 }} />
                {trendData?.series_note ? (
                  <Alert type="info" showIcon className="mt-2 !rounded-md text-xs" message={trendData.series_note} />
                ) : null}
              </Card>
            </div>
          </Col>

          <Col xs={24} lg={15}>
            <div className="rounded-xl border border-[var(--paper-warm)] bg-white p-5 shadow-[var(--shadow-soft)] sm:p-6 lg:min-h-full">
              {sectionHeading(
                'ochre',
                '智能推荐',
                <Link to="/recommendation">
                  <Button type="text" size="small" className="!text-[var(--ochre)] hover:!bg-[var(--ochre-pale)]">
                    查看更多 <ArrowRightOutlined />
                  </Button>
                </Link>
              )}

              {recommendations.length === 0 ? (
                <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-[var(--paper-warm)] bg-[var(--paper-cream)]/50 py-12 text-sm text-[var(--ink-muted)]">
                  暂无推荐房源，请稍后再试或前往房源列表浏览
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  {recommendations.map((item) => {
                    const rid = item.unit_id;
                    const hasCover = Boolean(item.image_url?.trim());
                    const tags = (item.tags || []).slice(0, 3);
                    const matchPct = Math.min(100, Math.max(0, Math.round(Number(item.match_score) || 0)));
                    return (
                      <Link
                        key={rid}
                        to={`/listing/${rid}`}
                        className="zen-card group flex flex-col overflow-hidden rounded-lg border border-[var(--paper-warm)] no-underline transition-[transform,box-shadow] hover:-translate-y-1 hover:shadow-[var(--shadow-medium)]"
                      >
                        <div className="relative aspect-[4/3] overflow-hidden bg-[var(--paper-cream)]">
                          {hasCover ? (
                            <img
                              src={item.image_url!.trim()}
                              alt=""
                              className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-xs text-[var(--ink-muted)]">
                              暂无封面
                            </div>
                          )}
                          <Tag className="!absolute !right-2 !top-2 !m-0 !border-[rgba(184,149,110,0.35)] !bg-white/90 !text-[var(--gold)]">
                            匹配 {matchPct}%
                          </Tag>
                        </div>
                        <div className="flex flex-1 flex-col p-4">
                          <div className="mb-2 line-clamp-2 text-sm font-medium leading-snug text-[var(--ink-black)] group-hover:text-[var(--ochre)]">
                            {item.title}
                          </div>
                          <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[var(--ink-muted)]">
                            <StarOutlined className="text-[var(--gold)]" />
                            <span className="font-medium text-[var(--ink-black)]">{item.rating}</span>
                            {item.district ? (
                              <>
                                <span aria-hidden>·</span>
                                <span>{item.district}</span>
                              </>
                            ) : null}
                          </div>
                          {tags.length > 0 ? (
                            <div className="mb-3 flex flex-wrap gap-1.5">
                              {tags.map((tag, idx) => (
                                <Tag key={idx} className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[10px] !text-[var(--ink-light)]">
                                  {tagLabel(tag)}
                                </Tag>
                              ))}
                              {(item.tags || []).length > 3 ? (
                                <Tag className="!m-0 !border-none !bg-transparent !text-[10px] !text-[var(--ink-muted)]">
                                  +{(item.tags || []).length - 3}
                                </Tag>
                              ) : null}
                            </div>
                          ) : null}
                          <div className="mt-auto flex items-baseline justify-between gap-2 border-t border-[var(--paper-warm)] pt-3">
                            <div>
                              <span className="font-[var(--font-serif)] text-xl font-semibold text-[var(--ochre)]">¥{item.price}</span>
                              <span className="text-xs text-[var(--ink-muted)]"> /晚</span>
                            </div>
                            <span className="text-xs text-[var(--ochre)] opacity-0 transition-opacity group-hover:opacity-100">
                              查看详情 →
                            </span>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </Col>
        </Row>
      </motion.section>
    </div>
  );
};

export default Home;
