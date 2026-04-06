import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import ReactECharts from 'echarts-for-react';
import { Card, Col, Row, Typography, Spin, Alert, Tabs } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  HomeOutlined,
  DollarOutlined,
  FireOutlined,
  WarningOutlined,
  StarOutlined,
  ShopOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { PageHeader } from '../components/common';
import { ZenRichTooltip } from '../components/zen/ZenRichTooltip';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import { ZEN_COLORS, createBarOption, createLineOption } from '../utils/echartsTheme';
import {
  getDistricts,
  getPriceDistribution,
  getFacilityPremium,
  type DistrictStats,
  type PriceDistribution,
  type FacilityPremium,
} from '../services/analysisApi';
import { getKpiDashboard, getHeatmapData, getTopDistricts, getDashboardTrends, getDashboardAlerts, type KpiData, type HeatmapPoint, type TopDistrict, type TrendData, type AlertItem } from '../services/dashboardApi';
import { DashboardDistrictsPanel, DashboardFacilitiesPanel } from '../components/dashboard/DashboardMarketAnalysis';

const { Text } = Typography;

const DASHBOARD_TAB_KEYS = new Set(['overview', 'districts', 'facilities']);

type DashboardTabKey = 'overview' | 'districts' | 'facilities';

function normalizeDashboardTab(raw: string | null): DashboardTabKey {
  if (raw && DASHBOARD_TAB_KEYS.has(raw)) return raw as DashboardTabKey;
  return 'overview';
}

/** 热力图/热门商圈「热度」分：面向用户的说明（与后台排名映射一致） */
const DASHBOARD_HEAT_TOOLTIP_USER = (
  <div className="max-w-[300px] text-xs leading-relaxed">
    <p className="mb-2 text-[var(--ink-black)]">
      每个<strong>行政区 + 商圈</strong>会有一个 <strong>20～100</strong> 的「热度展示分」，方便一眼比较哪里更「热闹」。
    </p>
    <p className="mb-1 font-medium text-[var(--ink-black)]">大致会看什么：</p>
    <ul className="mb-2 list-disc space-y-1 pl-4 text-[var(--ink-muted)]">
      <li>这一片<strong>房源多不多</strong>、<strong>评分高不高</strong>、大家<strong>收藏多不多</strong>（都做了平滑，避免特大商圈垄断）。</li>
      <li>所有商圈按综合强弱<strong>排个名次</strong>：排第一的给 100 分，往后每名略减，最低不低于 20，所以不会出现「几乎全是 100」看不懂的情况。</li>
    </ul>
    <p className="m-0 text-[11px] text-[var(--ink-muted)]">
      条形图与右侧列表用同一套分；图上条数与列表条数上限可能不同，以各自标题为准。
    </p>
  </div>
);

// 禅意统计卡片
const StatCard: React.FC<{
  title: string;
  value: string | number;
  suffix?: string;
  trend?: number;
  icon: React.ReactNode;
  description?: string;
  /** 标题旁问号，长说明给最终用户看 */
  titleTooltip?: React.ReactNode;
  color?: string;
}> = ({ title, value, suffix, trend, icon, description, titleTooltip, color = ZEN_COLORS.jade }) => (
  <Card
    bordered={false}
    className="group h-full !rounded-xl !border !border-[var(--paper-warm)] !bg-white/90 !shadow-[var(--shadow-soft)] transition-[transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:!shadow-[var(--shadow-medium)]"
    styles={{ body: { padding: 'var(--space-lg)' } }}
  >
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1">
          <Text className="text-[10px] font-medium uppercase tracking-wider text-[var(--ink-muted)] sm:text-xs">{title}</Text>
          {titleTooltip && (
            <ZenRichTooltip title={titleTooltip} placement="top">
              <QuestionCircleOutlined className="cursor-help text-[10px] text-[var(--paper-gray)] hover:text-[var(--ink-muted)]" />
            </ZenRichTooltip>
          )}
        </div>
        <div className="mt-2">
          <span
            className="text-2xl font-semibold tracking-tight text-[var(--ink-black)] sm:text-3xl"
            style={{ fontFamily: 'var(--font-serif)' }}
          >
            {value}
          </span>
          {suffix && <span className="ml-1 text-lg text-[var(--ink-muted)]">{suffix}</span>}
        </div>
        {trend !== undefined && (
          <div
            className={`mt-2 flex items-center gap-1 text-sm ${trend >= 0 ? 'text-[var(--jade)]' : 'text-[var(--ochre)]'}`}
          >
            {trend >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            <span>{Math.abs(trend)}%</span>
            <span className="text-[var(--ink-muted)]">环比（日历价）</span>
          </div>
        )}
        {description && <p className="mt-2 text-xs leading-relaxed text-[var(--ink-muted)]">{description}</p>}
      </div>
      <div
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-xl transition-transform group-hover:scale-105 sm:h-14 sm:w-14"
        style={{ backgroundColor: `${color}18`, color }}
      >
        {icon}
      </div>
    </div>
  </Card>
);

const Dashboard: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = useMemo(() => normalizeDashboardTab(searchParams.get('tab')), [searchParams]);

  const [loading, setLoading] = useState(true);
  const [districtStats, setDistrictStats] = useState<DistrictStats[]>([]);
  const [priceDistribution, setPriceDistribution] = useState<PriceDistribution[]>([]);

  const [facilityData, setFacilityData] = useState<FacilityPremium[]>([]);
  const [facilityLoading, setFacilityLoading] = useState(false);
  const facilityFetchedRef = useRef(false);

  // Dashboard API 数据 - 使用新接口 (KPI、热力图、热门商圈)
  const [kpiData, setKpiData] = useState<KpiData | null>(null);
  const [topDistricts, setTopDistricts] = useState<TopDistrict[]>([]);
  const [heatmapData, setHeatmapData] = useState<HeatmapPoint[]>([]);
  const [trendsData, setTrendsData] = useState<TrendData | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  const loadFacilityPremium = useCallback(async () => {
    try {
      setFacilityLoading(true);
      const response = await getFacilityPremium();
      setFacilityData(response?.facilities || []);
    } catch (error) {
      console.error('获取设施溢价数据失败:', error);
      setFacilityData([]);
    } finally {
      setFacilityLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  useEffect(() => {
    const raw = searchParams.get('tab');
    if (raw && !DASHBOARD_TAB_KEYS.has(raw)) {
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (loading) return;
    if (activeTab !== 'facilities') return;
    if (facilityFetchedRef.current) return;
    facilityFetchedRef.current = true;
    void loadFacilityPremium();
  }, [loading, activeTab, loadFacilityPremium]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      // 使用新的后端接口 - KPI、热力图、热门商圈排行、趋势、预警
      const [districtData, priceData, kpi, topDistrictsData, heatmap, trends, alertData] = await Promise.all([
        getDistricts(),
        getPriceDistribution(),
        getKpiDashboard(),
        getTopDistricts(10),
        getHeatmapData(),
        getDashboardTrends(30),
        getDashboardAlerts()
      ]);
      
      setDistrictStats(Array.isArray(districtData) ? districtData : []);
      setPriceDistribution(Array.isArray(priceData) ? priceData : []);
      setKpiData(kpi);
      setTopDistricts(Array.isArray(topDistrictsData) ? topDistrictsData : []);
      const hm = heatmap as { data?: HeatmapPoint[] };
      setHeatmapData(Array.isArray(hm?.data) ? hm.data : []);
      setTrendsData(trends);
      setAlerts(Array.isArray(alertData) ? alertData : []);
    } catch (error) {
      console.error('获取驾驶舱数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMainTabChange = (key: string) => {
    const k = normalizeDashboardTab(key);
    if (k === 'overview') {
      setSearchParams({}, { replace: true });
    } else {
      setSearchParams({ tab: k }, { replace: true });
    }
    if (k === 'facilities' && !facilityFetchedRef.current) {
      facilityFetchedRef.current = true;
      void loadFacilityPremium();
    }
  };

  // 根据数据生成图表配置
  const districtPriceData = districtStats.map((item, index) => ({
    name: item.district,
    value: Math.round(item.avg_price || 0),
    itemStyle: { 
      color: index === 0 ? ZEN_COLORS.ochre : 
             index === 1 ? ZEN_COLORS.jade : 
             index === 2 ? ZEN_COLORS.gold : 
             index % 2 === 0 ? ZEN_COLORS.ochre : ZEN_COLORS.jade 
    }
  }));

  const districtPriceOption = createBarOption(districtPriceData, ZEN_COLORS.ochre);

  // 图表配置 - 价格区间分布
  const priceDistributionOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: ZEN_COLORS.paperWhite,
      borderColor: ZEN_COLORS.paperWarm,
      textStyle: { color: ZEN_COLORS.inkBlack },
      formatter: (params: any) => `${params.name}<br/>房源数: ${params.value}<br/>占比: ${params.percent}%`,
    },
    legend: {
      bottom: 0,
      textStyle: { color: ZEN_COLORS.inkLight },
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 4,
        borderColor: ZEN_COLORS.paperWhite,
        borderWidth: 2,
      },
      label: {
        show: false,
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold',
          color: ZEN_COLORS.inkBlack,
        },
      },
      labelLine: {
        show: false,
      },
      data: priceDistribution.map((item, index) => ({
        name: item.price_range,
        value: item.count,
        itemStyle: {
          color: [ZEN_COLORS.jade, ZEN_COLORS.gold, ZEN_COLORS.ochre, ZEN_COLORS.inkBlack, '#999'][index % 5],
        },
      })),
    }],
  };

  // 商圈热度：与「热门商圈榜单」同一综合分，横向条形取前 16 条
  const heatRanked = useMemo(() => {
    return [...heatmapData].sort((a, b) => b.value - a.value).slice(0, 16);
  }, [heatmapData]);

  const heatmapOption = useMemo(() => {
    if (heatRanked.length === 0) {
      return {
        title: {
          text: '暂无商圈热度数据',
          left: 'center',
          top: 'center',
          textStyle: { color: ZEN_COLORS.inkMuted, fontSize: 14, fontWeight: 400 },
        },
      };
    }
    const values = heatRanked.map((d) => d.value);
    const maxV = Math.max(...values, 1);
    const minV = Math.min(...values);
    // 后端按名次给分多在 85～100；不设 min 时轴从 0 起，条几乎全长同色，易被误认为「全是 100」
    const axisMin = Math.max(0, minV - 8);
    const span = Math.max(1, maxV - axisMin);
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: ZEN_COLORS.paperWhite,
        borderColor: ZEN_COLORS.paperWarm,
        textStyle: { color: ZEN_COLORS.inkBlack },
        extraCssText: 'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); border-radius: 4px;',
        formatter: (params: unknown) => {
          const p = Array.isArray(params) ? params[0] : params;
          const ax = p as { name?: string; value?: number };
          return `${ax.name ?? ''}<br/>热度：${ax.value ?? '—'}`;
        },
      },
      grid: { left: 4, right: 40, top: 12, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        min: axisMin,
        max: 100,
        name: '热度',
        nameTextStyle: { color: ZEN_COLORS.inkMuted, fontSize: 11 },
        splitLine: { lineStyle: { color: ZEN_COLORS.paperWarm, type: 'dashed' } },
        axisLabel: { color: ZEN_COLORS.inkMuted, fontSize: 11 },
      },
      yAxis: {
        type: 'category',
        data: heatRanked.map((d) => d.name),
        inverse: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: ZEN_COLORS.inkLight,
          fontSize: 11,
          width: 88,
          overflow: 'truncate',
        },
      },
      series: [
        {
          type: 'bar',
          data: heatRanked.map((d) => d.value),
          barMaxWidth: 22,
          itemStyle: {
            borderRadius: [0, 4, 4, 0],
            color: (params: { value: number }) => {
              const ratio = (Number(params.value) - axisMin) / span;
              if (ratio >= 0.66) return ZEN_COLORS.ochre;
              if (ratio >= 0.33) return ZEN_COLORS.gold;
              return ZEN_COLORS.jade;
            },
          },
          label: {
            show: true,
            position: 'right',
            formatter: '{c}',
            color: ZEN_COLORS.inkMuted,
            fontSize: 11,
          },
        },
      ],
    };
  }, [heatRanked]);

  const heatChartHeight = useMemo(
    () => Math.max(300, Math.min(440, heatRanked.length * 30 + 56)),
    [heatRanked]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spin size="large" tip="加载数据中..." />
      </div>
    );
  }

  const overviewTabContent = (
    <>
      {/* KPI：宣纸底条带，四格均分 */}
      <div className="paper-texture rounded-xl border border-[var(--paper-warm)] px-4 py-6 shadow-[var(--shadow-soft)] sm:px-6 sm:py-8">
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} xl={6}>
            <StatCard
              title="在售房源总数"
              value={kpiData?.total_listings?.toLocaleString() || '-'}
              icon={<HomeOutlined />}
              description="库内在架样本总量"
              titleTooltip={
                <div className="max-w-[300px] text-xs leading-relaxed">
                  <p className="mb-2 text-[var(--ink-black)]">
                    当前数据库里收录的<strong>民宿条数</strong>，是本页均价、热度、趋势等指标的统计基础。
                  </p>
                  <p className="m-0 text-[11px] text-[var(--ink-muted)]">随导入/爬虫更新变化；不是订单笔数。</p>
                </div>
              }
              color={ZEN_COLORS.jade}
            />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <StatCard
              title="全市均价"
              value={kpiData?.avg_price?.toFixed(2) || '-'}
              suffix="元"
              trend={kpiData?.price_change_percent || 0}
              icon={<DollarOutlined />}
              description="当前挂牌价截面平均；旁为日历价环比"
              titleTooltip={
                <div className="max-w-[300px] text-xs leading-relaxed">
                  <p className="mb-2 text-[var(--ink-black)]">
                    <strong>大数字</strong>：全库房源<strong>展示日价</strong>的简单平均，粗看整体价格带；<strong>不是</strong>成交价、也<strong>不是</strong>「今日」专属均价。
                  </p>
                  <p className="mb-1 text-[var(--ink-muted)]">
                    <strong>下方涨跌</strong>：来自价格日历——优先「本月至今 vs 上月同期」的日均价对比；若上月头几天没有日历，会用「最近14天 vs 再前14天」等回退；无日历则为 0。
                  </p>
                  <p className="m-0 text-[11px] text-[var(--ink-muted)]">与曲线图同为日历口径时，方向应大致一致。</p>
                </div>
              }
              color={ZEN_COLORS.ochre}
            />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <StatCard
              title="需求热度"
              value={kpiData?.occupancy_rate?.toFixed(1) || '-'}
              suffix="%"
              icon={<StarOutlined />}
              description="关注度代理 · 非真实入住率"
              titleTooltip={
                <div className="max-w-[300px] text-xs leading-relaxed">
                  <p className="mb-2 text-[var(--ink-black)]">
                    <strong>关注度代理指数</strong>（约 50～92），「%」仅为样式，<strong>不是</strong> PMS 入住率。
                  </p>
                  <p className="mb-1 text-[var(--ink-muted)]">
                    用全平台<strong>平均评分</strong>、<strong>平均收藏</strong>合成：评分高、收藏多则偏高，并限制在合理区间便于对比。
                  </p>
                  <p className="m-0 text-[11px] text-[var(--ink-muted)]">首页「市场吸引力」会复用同一思路下的热度信息。</p>
                </div>
              }
              color={ZEN_COLORS.gold}
            />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <StatCard
              title="商圈数量"
              value={kpiData?.district_count || '-'}
              suffix="个"
              icon={<ShopOutlined />}
              description="有房源的行政区数"
              titleTooltip={
                <div className="max-w-[300px] text-xs leading-relaxed">
                  <p className="mb-2 text-[var(--ink-black)]">
                    当前样本里出现过房源的<strong>行政区（district）种类数</strong>，表示地理覆盖广度。
                  </p>
                  <p className="m-0 text-[11px] text-[var(--ink-muted)]">不表示每区房源同样多；细分商圈请看下方图表与列表。</p>
                </div>
              }
              color={ZEN_COLORS.jade}
            />
          </Col>
        </Row>
      </div>

      {/* 价格动向：主趋势全宽 */}
      <ZenSection title="价格动向" accent="gold">
        <ZenPanel accent="ochre" title="平台价格趋势（近30天）">
          <ReactECharts
            option={createLineOption(
              trendsData?.prices || [],
              trendsData?.dates || [],
              ZEN_COLORS.ochre,
              '全市均价'
            )}
            style={{ height: 360 }}
          />
        </ZenPanel>
      </ZenSection>

      {/* 商圈对比：双大图并列 */}
      <ZenSection title="商圈对比" accent="jade">
        <Row gutter={[20, 20]}>
          <Col xs={24} lg={12}>
            <ZenPanel accent="jade" title="核心商圈均价对比">
              <ReactECharts option={districtPriceOption} style={{ height: 380 }} />
            </ZenPanel>
          </Col>
          <Col xs={24} lg={12}>
            <ZenPanel
              accent="ochre"
              titleCaps={false}
              title="核心商圈热度（条形图）"
              extra={
                <ZenRichTooltip title={DASHBOARD_HEAT_TOOLTIP_USER} placement="left">
                  <QuestionCircleOutlined className="cursor-help text-[var(--ink-muted)]" aria-label="热度定义" />
                </ZenRichTooltip>
              }
            >
              <ReactECharts option={heatmapOption} style={{ height: heatChartHeight }} />
            </ZenPanel>
          </Col>
        </Row>
      </ZenSection>

      {/* 结构与排行：饼图 + 排行长列表 */}
      <ZenSection title="结构 · 排行" accent="ochre">
        <Row gutter={[20, 20]} align="stretch">
          <Col xs={24} lg={9}>
            <ZenPanel accent="jade" title="价格区间分布" className="h-full">
              <ReactECharts option={priceDistributionOption} style={{ height: 320 }} />
            </ZenPanel>
          </Col>
          <Col xs={24} lg={15}>
            <ZenPanel
              accent="gold"
              titleCaps={false}
              title="热门商圈榜单"
              extra={
                <ZenRichTooltip
                  title={
                    <div className="max-w-[300px] text-xs leading-relaxed">
                      {DASHBOARD_HEAT_TOOLTIP_USER}
                      <p className="mt-2 border-t border-[var(--paper-warm)] pt-2 text-[11px] text-[var(--ink-muted)]">
                        下列表额外展示：挂牌均价、套数、相对全市均价的偏离（便于看溢价/洼地）。
                      </p>
                    </div>
                  }
                  placement="left"
                >
                  <QuestionCircleOutlined className="cursor-help text-[var(--ink-muted)]" aria-label="热度与榜单说明" />
                </ZenRichTooltip>
              }
            >
              <div className="flex max-h-[min(420px,58vh)] flex-col gap-2 overflow-y-auto pr-1">
                {topDistricts.map((district, index) => (
                  <div
                    key={`${district.name}-${index}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-[var(--paper-warm)] bg-[var(--paper-white)]/80 px-3 py-2.5 transition-[box-shadow] hover:shadow-[var(--shadow-soft)] sm:px-4 sm:py-3"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <span
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold sm:h-8 sm:w-8 ${
                          index < 3 ? 'bg-[var(--ochre)] text-white' : 'bg-[var(--paper-cream)] text-[var(--ink-muted)]'
                        }`}
                      >
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <span className="block truncate font-medium text-[var(--ink-black)]">{district.name}</span>
                        <span className="text-xs text-[var(--ink-muted)]">热度展示分 {district.heat}</span>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-sm font-semibold text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
                        ¥{district.avg_price.toFixed(0)}
                      </div>
                      <div className="text-xs text-[var(--ink-muted)]">{district.listing_count} 套</div>
                    </div>
                  </div>
                ))}
              </div>
            </ZenPanel>
          </Col>
        </Row>
      </ZenSection>

      {alerts.length > 0 && (
        <ZenPanel
          accent="ochre"
          titleCaps={false}
          title={
            <span className="inline-flex items-center gap-2 text-[var(--ink-black)]">
              <WarningOutlined className="text-[var(--ochre)]" />
              预警信息
            </span>
          }
        >
          <div className="space-y-3">
            {alerts.slice(0, 5).map((alert, index) => (
              <Alert
                key={index}
                message={alert.title}
                description={alert.message}
                type={alert.severity === 'high' ? 'error' : alert.severity === 'medium' ? 'warning' : 'info'}
                showIcon
                className="!border-[var(--paper-warm)] !bg-transparent"
              />
            ))}
          </div>
        </ZenPanel>
      )}

      <Card
        bordered={false}
        className="!rounded-xl !border !border-[var(--paper-warm)] !bg-[var(--paper-cream)]/90 !shadow-[var(--shadow-soft)]"
        styles={{ body: { padding: 'var(--space-lg)' } }}
      >
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--jade-pale)]">
            <span className="text-xs font-semibold text-[var(--jade)]">注</span>
          </div>
          <div>
            <h4 className="mb-2 font-medium text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
              系统运行说明
            </h4>
            <p className="text-sm leading-relaxed text-[var(--ink-light)]">
              本系统基于 Hive 数仓与 XGBoost 算法构建。当前展示为演示数据，实际部署时将连接 Python 后端 API 获取实时 Hive 分析结果。数据每 24 小时自动更新一次，预测模型每周重新训练。
            </p>
          </div>
        </div>
      </Card>
    </>
  );

  return (
    <div className="dashboard-shell space-y-8 pb-10 sm:space-y-10">
      <PageHeader
        title="经营驾驶舱"
        subtitle="市场总览、商圈名录与设施溢价同一入口；总览看 KPI 与趋势，后两页做下钻与结构分析"
        category="Dashboard"
        extra={<Text className="text-sm text-[var(--ink-muted)]">数据更新时间: {new Date().toLocaleDateString('zh-CN')}</Text>}
      />

      <Tabs
        activeKey={activeTab}
        onChange={handleMainTabChange}
        destroyInactiveTabPane={false}
        className="dashboard-main-tabs [&_.ant-tabs-nav]:mb-6 [&_.ant-tabs-nav::before]:border-[var(--paper-warm)] [&_.ant-tabs-tab]:text-[var(--ink-muted)] [&_.ant-tabs-tab-active]:!text-[var(--ink-black)]"
        items={[
          {
            key: 'overview',
            label: '市场总览',
            children: <div className="space-y-12 sm:space-y-14">{overviewTabContent}</div>,
          },
          {
            key: 'districts',
            label: '商圈名录',
            children: <DashboardDistrictsPanel districtStats={districtStats} />,
          },
          {
            key: 'facilities',
            label: '设施溢价',
            children: <DashboardFacilitiesPanel facilityData={facilityData} facilityLoading={facilityLoading} />,
          },
        ]}
      />
    </div>
  );
};

export default Dashboard;
