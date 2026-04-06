import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import * as echarts from 'echarts';
import { 
  CalendarOutlined, 
  PieChartOutlined,
  TrophyOutlined,
  ThunderboltOutlined,
  HomeOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { 
  Form, 
  InputNumber, 
  Select, 
  Button, 
  Row, 
  Col, 
  Statistic, 
  Tag,
  Alert,
  Tabs,
  Progress,
  Empty,
  Spin,
  message,
  Checkbox,
  Divider,
} from 'antd';
import ReactECharts from 'echarts-for-react';
import PageHeader from '../components/common/PageHeader';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import {
  getForecast,
  getFactorDecomposition,
  getCompetitivenessAssessment,
  type PredictionAnalysisParams,
} from '../services/predictionApi';
import { getDistricts } from '../services/analysisApi';
import { getMyListings, MyListing } from '../services/myListingsApi';

const { Option } = Select;

/** ECharts 用色（与 zen-theme CSS 变量一致） */
const Z = {
  paper: '#faf8f5',
  cream: '#f5f2ed',
  warm: '#ebe7e0',
  ink: '#6b6b6b',
  inkBlack: '#1a1a1a',
  ochre: '#c45c3e',
  ochreMuted: 'rgba(196, 92, 62, 0.35)',
  jade: '#5a8a6e',
  jadeMuted: 'rgba(90, 138, 110, 0.25)',
  gold: '#b8956e',
} as const;

const chartTooltipBase = {
  backgroundColor: 'rgba(250, 248, 245, 0.96)',
  borderColor: Z.warm,
  borderWidth: 1,
  textStyle: { color: Z.inkBlack, fontSize: 12 },
};

// 动画配置
const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 },
};

export default function Prediction() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [districts, setDistricts] = useState<string[]>([]);
  const [tradeAreas, setTradeAreas] = useState<string[]>([]);  // 商圈列表
  const [allDistrictData, setAllDistrictData] = useState<any[]>([]);  // 所有商圈数据
  const [myListings, setMyListings] = useState<MyListing[]>([]);

  // 预测结果状态
  const [forecastData, setForecastData] = useState<any>(null);
  const [factorData, setFactorData] = useState<any>(null);
  const [competitivenessData, setCompetitivenessData] = useState<any>(null);

  // 初始化数据
  useEffect(() => {
    fetchDistricts();
    fetchMyListings();
  }, []);

  const fetchDistricts = async () => {
    try {
      const data = await getDistricts();
      setAllDistrictData(data);
      // 提取唯一的行政区列表
      const uniqueDistricts = [...new Set(data.map((d: any) => d.district).filter(Boolean))];
      setDistricts(uniqueDistricts);
    } catch (error) {
      console.error('获取商圈失败:', error);
    }
  };

  const fetchMyListings = async () => {
    try {
      const data = await getMyListings();
      setMyListings(data);
    } catch (error) {
      console.error('获取我的房源失败:', error);
    }
  };

  // 处理行政区变化，更新商圈列表
  const handleDistrictChange = (district: string) => {
    // 过滤出该行政区的商圈
    const filteredTradeAreas = allDistrictData
      .filter((d: any) => d.district === district && d.trade_area)
      .map((d: any) => d.trade_area);
    setTradeAreas(filteredTradeAreas);
    
    // 清空商圈选择
    form.setFieldsValue({ trade_area: undefined });
  };

  /** 合并「我的房源」各分类标签，与定价工作台勾选逻辑一致（含设施/位置/人群） */
  const collectListingTags = (listing: MyListing): string[] => [
    ...(listing.facility_tags || []),
    ...(listing.location_tags || []),
    ...(listing.crowd_tags || []),
  ];

  // 选择我的房源后自动填充表单
  const handleSelectMyListing = (listingId: number) => {
    const listing = myListings.find(l => l.id === listingId);
    if (!listing) return;

    const allTags = collectListingTags(listing);
    const has = (...keywords: string[]) => keywords.some(kw => allTags.some(t => t === kw));
    const includes = (sub: string) => allTags.some(t => t.includes(sub));

    // 更新商圈列表
    if (listing.district) {
      const filteredTradeAreas = allDistrictData
        .filter((d: any) => d.district === listing.district && d.trade_area)
        .map((d: any) => d.trade_area);
      setTradeAreas(filteredTradeAreas);
    }

    // 填充表单
    form.setFieldsValue({
      district: listing.district,
      trade_area: listing.trade_area || listing.business_circle || listing.district,
      current_price: listing.current_price,
      capacity: listing.max_guests,
      bedrooms: listing.bedroom_count,
      bed_count: listing.bed_count || listing.bedroom_count,
      area: listing.area || 50,
      // 设施 / 位置 / 人群（与「我的房源」标签库、后端 tags 分类对齐）
      has_wifi: has('WiFi', '无线网络'),
      has_air_conditioning: has('空调', '冷暖空调'),
      has_kitchen: has('厨房', '可做饭'),
      has_projector: has('投影', '巨幕投影'),
      has_bathtub: has('浴缸'),
      has_washer: has('洗衣机'),
      has_smart_lock: has('智能锁', '智能门锁'),
      has_tv: has('电视'),
      has_heater: has('暖气', '地暖'),
      has_fridge: has('冰箱'),
      near_metro: has('近地铁'),
      near_station: has('近火车站') || includes('火车站'),
      near_university: has('近高校'),
      near_ski: has('近滑雪场') || includes('滑雪场'),
      has_elevator: has('电梯', '有电梯'),
      has_terrace: has('观景露台', '露台'),
      has_mahjong: has('麻将', '麻将机'),
      has_big_living_room: has('大客厅'),
      has_parking: has('停车位', '免费停车', '付费停车位'),
      pet_friendly: has('可带宠物', '允许宠物'),
      has_river_view: includes('江景'),
      has_lake_view: includes('湖景'),
      has_mountain_view: includes('山景'),
      has_garden: has('私家花园', '格调小院') || includes('花园'),
    });

    message.success(`已加载房源：${listing.title}`);
  };

  // 执行预测分析
  const handleAnalyze = async (values: any) => {
    setLoading(true);
    try {
      const areaN = values.area || 50;
      const refPrice =
        values.current_price != null && Number(values.current_price) > 0
          ? Number(values.current_price)
          : Math.max(80, Math.round(areaN * 4));

      const params: PredictionAnalysisParams = {
        district: values.district,
        trade_area: values.trade_area || values.district,  // 商圈（如果没有则使用行政区）
        room_type: values.bedrooms >= 2 ? '整套房屋' : '独立房间', // 根据卧室数推断房型
        capacity: values.capacity,
        bedrooms: values.bedrooms,
        bed_count: values.bed_count || values.bedrooms,
        area: areaN,
        current_price: Number.isFinite(refPrice) ? refPrice : Math.max(80, Math.round(areaN * 4)),
        // 设施参数
        has_wifi: values.has_wifi ?? true,
        has_air_conditioning: values.has_air_conditioning ?? true,
        has_kitchen: values.has_kitchen ?? false,
        has_projector: values.has_projector ?? false,
        has_bathtub: values.has_bathtub ?? false,
        has_washer: values.has_washer ?? false,
        has_smart_lock: values.has_smart_lock ?? false,
        has_tv: values.has_tv ?? false,
        has_heater: values.has_heater ?? false,
        near_metro: values.near_metro ?? false,
        near_station: values.near_station ?? false,
        near_university: values.near_university ?? false,
        near_ski: values.near_ski ?? false,
        has_elevator: values.has_elevator ?? false,
        has_fridge: values.has_fridge ?? false,
        has_terrace: values.has_terrace ?? false,
        has_mahjong: values.has_mahjong ?? false,
        has_big_living_room: values.has_big_living_room ?? false,
        has_parking: values.has_parking ?? false,
        pet_friendly: values.pet_friendly ?? false,
        // 景观特色
        has_view: values.has_river_view || values.has_lake_view || values.has_mountain_view || false,
        view_type: [
          values.has_river_view ? '江景' : null,
          values.has_lake_view ? '湖景' : null,
          values.has_mountain_view ? '山景' : null,
        ].filter(Boolean).join(','),
        river_view: values.has_river_view ?? false,
        lake_view: values.has_lake_view ?? false,
        mountain_view: values.has_mountain_view ?? false,
        garden: !!(values.has_garden ?? false),
      };

      const [forecast, factors, competitiveness] = await Promise.all([
        getForecast(params),
        getFactorDecomposition(params),
        getCompetitivenessAssessment(params)
      ]);

      setForecastData(forecast);
      setFactorData(factors);
      setCompetitivenessData(competitiveness);
      message.success('价格预测分析完成！');
    } catch (error: any) {
      console.error('分析失败:', error);
      message.error(error?.response?.data?.detail || error?.message || '分析失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // ─── 日历网格辅助 ───
  const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日'];

  const getDayType = (f: any): 'holiday' | 'weekend' | 'weekday' => {
    if (f.is_holiday) return 'holiday';
    if (f.is_weekend) return 'weekend';
    return 'weekday';
  };

  const dayTypeStyle: Record<string, { bg: string; border: string; badge: string; text: string }> = {
    holiday: {
      bg: 'bg-[var(--ochre-pale)]',
      border: 'border-[var(--ochre)]/35',
      badge: 'bg-[var(--ochre)]',
      text: 'text-[var(--ochre)]',
    },
    weekend: {
      bg: 'bg-[var(--paper-cream)]',
      border: 'border-[var(--gold)]/45',
      badge: 'bg-[var(--gold)]',
      text: 'text-[var(--ink-dark)]',
    },
    weekday: {
      bg: 'bg-[var(--paper-white)]',
      border: 'border-[var(--paper-warm)]',
      badge: 'bg-[var(--jade)]',
      text: 'text-[var(--ink-medium)]',
    },
  };

  const getPriceChangeReason = (f: any): string => {
    const parts: string[] = [];
    if (f.is_holiday) parts.push(f.holiday_name ? `${f.holiday_name}（已入模型）` : '节假日（已入模型）');
    if (f.is_weekend && !f.is_holiday) parts.push('周末（已入模型）');
    if (
      f.price_low != null &&
      f.price_high != null &&
      Number.isFinite(f.price_low) &&
      Number.isFinite(f.price_high)
    ) {
      parts.push(`区间 ¥${Math.round(f.price_low)}–¥${Math.round(f.price_high)}`);
    }
    if (!parts.length) parts.push('日级模型逐日预测');
    return parts.join('；');
  };

  // ─── Tornado 图（因子敏感度） ───
  const getTornadoOption = () => {
    if (!factorData) return {};
    const factors: any[] = (factorData.factors || []).slice(0, 12);
    if (!factors.length) return {};
    const labels = factors.map((f: any) => f.factor).reverse();
    const deltas = factors.map((f: any) => f.delta).reverse();

    return {
      textStyle: { color: Z.ink, fontSize: 11 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow', shadowStyle: { color: Z.jadeMuted } },
        ...chartTooltipBase,
        formatter: (params: any) => {
          const p = params[0];
          const f = factors[factors.length - 1 - p.dataIndex];
          return `${f.factor}\n您的配置: ${f.your_value}\n基线: ${f.baseline}\n边际: ${f.delta > 0 ? '+' : ''}${f.delta} 元（${f.pct > 0 ? '+' : ''}${f.pct}%）`;
        },
      },
      grid: { left: 8, right: 44, top: 16, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        name: '元',
        nameTextStyle: { color: Z.ink, fontSize: 11 },
        axisLabel: { color: Z.ink, fontSize: 11 },
        splitLine: { lineStyle: { color: Z.warm, type: 'dashed' } },
        axisLine: { lineStyle: { color: Z.warm } },
      },
      yAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: Z.inkBlack, fontSize: 11 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: Z.warm } },
      },
      series: [
        {
        type: 'bar',
        data: deltas.map((d: number) => ({
          value: d,
            itemStyle: {
              color:
                d >= 0
                  ? new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                      { offset: 0, color: 'rgba(90, 138, 110, 0.45)' },
                      { offset: 1, color: Z.jade },
                    ])
                  : new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                      { offset: 0, color: Z.ochre },
                      { offset: 1, color: 'rgba(196, 92, 62, 0.35)' },
                    ]),
              borderRadius: d >= 0 ? [0, 6, 6, 0] : [6, 0, 0, 6],
            },
          })),
          barMaxWidth: 20,
        label: {
          show: true,
          position: 'right',
          formatter: (p: any) => `${p.value > 0 ? '+' : ''}${p.value}`,
          fontSize: 11,
            color: Z.inkBlack,
          },
        },
      ],
    };
  };

  // ─── 14 天价格走势 ───
  const getForecastLineOption = () => {
    if (!forecastData?.forecasts?.length) return {};
    const list = forecastData.forecasts as any[];
    const dates = list.map((f: any) => f.date.slice(5));
    const prices = list.map((f: any) => Math.round(f.predicted_price));
    const base = forecastData.base_price as number | undefined;
    return {
      textStyle: { color: Z.ink, fontSize: 11 },
      tooltip: {
        trigger: 'axis',
        ...chartTooltipBase,
        axisPointer: { type: 'line', lineStyle: { color: Z.gold, width: 1, type: 'dashed' } },
      },
      grid: { left: 52, right: 20, top: 32, bottom: 28 },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLine: { lineStyle: { color: Z.warm } },
        axisLabel: { color: Z.ink },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: Z.warm, type: 'dashed' } },
        axisLabel: { color: Z.ink, formatter: (v: number) => `¥${v}` },
      },
      series: [
        {
          name: '建议价',
          type: 'line',
          smooth: 0.35,
          symbol: 'circle',
          symbolSize: 8,
          data: prices,
          lineStyle: { width: 2.5, color: Z.ochre },
          itemStyle: { color: Z.gold, borderColor: Z.paper, borderWidth: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(196, 92, 62, 0.2)' },
              { offset: 1, color: 'rgba(196, 92, 62, 0)' },
            ]),
          },
          ...(base != null && Number.isFinite(base)
            ? {
                markLine: {
                  silent: true,
                  symbol: 'none',
                  lineStyle: { color: Z.jade, type: 'dashed', width: 1 },
                  label: { show: true, formatter: '基准', color: Z.jade, fontSize: 10 },
                  data: [{ yAxis: base }],
                },
              }
            : {}),
        },
      ],
    };
  };

  // ─── 竞争力 · 价格横向对比 ───
  const getCompetitivenessBarOption = () => {
    if (!competitivenessData) return {};
    const pa = competitivenessData.pricing_analysis || {};
    const mp = competitivenessData.market_position || {};
    const fairLabel = '模型基准价（锚定日）';
    const names = ['您的定价', fairLabel, '商圈均价'];
    const values = [
      Math.round(pa.user_price || 0),
      Math.round(pa.fair_price || 0),
      Math.round(mp.district_avg_price || 0),
    ];
    const colors = [Z.ochre, Z.jade, Z.gold] as const;
    return {
      textStyle: { color: Z.ink, fontSize: 11 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow', shadowStyle: { color: Z.jadeMuted } },
        ...chartTooltipBase,
        formatter: (params: any) => {
          const p = params[0];
          return `${names[p.dataIndex]}\n¥${values[p.dataIndex]}`;
        },
      },
      grid: { left: 100, right: 36, top: 8, bottom: 8 },
      xAxis: {
        type: 'value',
        axisLabel: { formatter: (v: number) => `¥${v}`, color: Z.ink },
        splitLine: { lineStyle: { color: Z.warm, type: 'dashed' } },
      },
      yAxis: {
        type: 'category',
        data: names,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: Z.warm } },
        axisLabel: { color: Z.inkBlack, fontSize: 12 },
      },
      series: [
        {
          type: 'bar',
          data: values.map((v, i) => ({
            value: v,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: colors[i] },
                {
                  offset: 1,
                  color:
                    i === 0 ? 'rgba(196, 92, 62, 0.35)' : i === 1 ? 'rgba(90, 138, 110, 0.35)' : 'rgba(184, 149, 110, 0.4)',
                },
              ]),
              borderRadius: [0, 8, 8, 0],
            },
          })),
          barMaxWidth: 22,
          label: {
            show: true,
            position: 'right',
            formatter: (p: any) => `¥${p.value}`,
            color: Z.inkBlack,
            fontSize: 11,
          },
        },
      ],
    };
  };

  // ─── 竞争力仪表盘 ───
  const getGaugeOption = (score: number) => ({
    series: [
      {
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
        radius: '92%',
        center: ['50%', '58%'],
        pointer: {
          show: true,
          length: '58%',
          width: 5,
          itemStyle: { color: Z.inkBlack, shadowBlur: 4, shadowColor: 'rgba(0,0,0,0.12)' },
        },
      axisLine: {
        lineStyle: {
            width: 20,
            color: [
              [0.35, Z.ochre],
              [0.55, Z.gold],
              [0.72, 'rgba(90, 138, 110, 0.7)'],
              [1, Z.jade],
            ],
        },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
        detail: {
          formatter: '{value}',
          fontSize: 28,
          fontWeight: 600,
          offsetCenter: [0, '74%'],
          color: Z.inkBlack,
          fontFamily: 'Noto Serif SC, SimSun, serif',
        },
      data: [{ value: Math.round(score) }],
      },
    ],
  });

  const predictionTabItems = useMemo(() => {
    if (!forecastData) return [];

    const forecastTab = {
      key: 'forecast',
      label: (
        <span className="inline-flex items-center gap-1.5 text-[var(--ink-medium)]">
          <CalendarOutlined className="text-[var(--ochre)]" />
          14 天日历
        </span>
      ),
      children: (
        <div className="space-y-6">
          <Row gutter={[12, 12]}>
            <Col xs={12} sm={6}>
              <div className="prediction-stat-card p-4">
                <Statistic
                  title={<span className="text-xs text-[var(--ink-muted)]">模型基准价</span>}
                  value={forecastData.base_price}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ color: 'var(--ink-black)', fontFamily: 'var(--font-serif)' }}
                />
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <div className="prediction-stat-card p-4">
                <Statistic
                  title={<span className="text-xs text-[var(--ink-muted)]">14 天均价</span>}
                  value={forecastData.avg_forecast_price}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ color: 'var(--jade)', fontFamily: 'var(--font-serif)' }}
                />
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <div className="prediction-stat-card p-4">
                <Statistic
                  title={<span className="text-xs text-[var(--ink-muted)]">最高</span>}
                  value={forecastData.max_price}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ color: 'var(--ochre)', fontFamily: 'var(--font-serif)' }}
                />
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <div className="prediction-stat-card p-4">
                <Statistic
                  title={<span className="text-xs text-[var(--ink-muted)]">最低</span>}
                  value={forecastData.min_price}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ color: 'var(--jade)', fontFamily: 'var(--font-serif)' }}
                />
              </div>
            </Col>
          </Row>

          <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/40 px-4 py-3">
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-[var(--ink-muted)]">
              <LineChartOutlined className="text-[var(--gold)]" />
              14 天建议价走势
            </div>
            <ReactECharts option={getForecastLineOption()} style={{ height: 240 }} opts={{ renderer: 'svg' }} />
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--ink-muted)]">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded border border-[var(--paper-warm)] bg-[var(--paper-white)]" />{' '}
              周中
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded border border-[var(--gold)]/50 bg-[var(--paper-cream)]" />{' '}
              周末
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded border border-[var(--ochre)]/40 bg-[var(--ochre-pale)]" />{' '}
              节假日
            </span>
          </div>

          <div className="grid grid-cols-7 gap-2 border-b border-[var(--paper-warm)] pb-2">
            {WEEKDAY_LABELS.map(d => (
              <div
                key={d}
                className="py-1 text-center text-xs font-semibold tracking-wider text-[var(--ink-muted)]"
                style={{ fontFamily: 'var(--font-serif)' }}
              >
                {d}
              </div>
            ))}
          </div>

          {(() => {
            const list: any[] = forecastData.forecasts;
            if (!list.length) return null;
            const firstWeekday = new Date(list[0].date).getDay();
            const offset = firstWeekday === 0 ? 6 : firstWeekday - 1;
            const cells: (any | null)[] = Array(offset).fill(null).concat(list);
            const rows: (any | null)[][] = [];
            for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
            return rows.map((row, ri) => (
              <div key={ri} className="mb-2 grid grid-cols-7 gap-2">
                {row.map((f, ci) => {
                  if (!f) return <div key={ci} />;
                  const dt = getDayType(f);
                  const st = dayTypeStyle[dt];
                  const priceDelta = Math.round(f.predicted_price - forecastData.base_price);
  return (
                    <div
                      key={ci}
                      className={`group relative cursor-default rounded-xl border ${st.border} ${st.bg} p-2.5 shadow-[var(--shadow-soft)] transition-shadow duration-300 hover:shadow-[var(--shadow-medium)]`}
                      title={getPriceChangeReason(f)}
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <span className={`text-xs font-semibold ${st.text}`}>{f.date.slice(5)}</span>
                        <span className="text-[10px] text-[var(--ink-muted)]">{f.weekday}</span>
                      </div>
                      <div
                        className="text-base font-semibold text-[var(--ink-black)]"
                        style={{ fontFamily: 'var(--font-serif)' }}
                      >
                        ¥{Math.round(f.predicted_price)}
                      </div>
                      <div
                        className={`mt-0.5 text-[11px] ${priceDelta > 0 ? 'text-[var(--ochre)]' : priceDelta < 0 ? 'text-[var(--jade)]' : 'text-[var(--ink-muted)]'}`}
                      >
                        {priceDelta > 0 ? `+${priceDelta}` : priceDelta < 0 ? `${priceDelta}` : '—'}
                      </div>
                      {f.holiday_name && (
                        <div className="absolute -right-1 -top-2">
                          <Tag className="!m-0 !border-none !bg-[var(--ochre)] !px-1.5 !py-0 !text-[10px] !leading-4 !text-white">
                            {f.holiday_name}
                          </Tag>
                        </div>
                      )}
                      <div className="absolute left-1/2 top-full z-10 mt-1 hidden w-52 -translate-x-1/2 rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] p-3 text-xs text-[var(--ink-muted)] shadow-[var(--shadow-medium)] group-hover:block">
                        <div
                          className="mb-1 font-medium text-[var(--ink-black)]"
                          style={{ fontFamily: 'var(--font-serif)' }}
                        >
                          {f.date} {f.weekday}
                        </div>
                        <div className="mb-0.5">
                          建议定价:{' '}
                          <strong className="text-[var(--ochre)]">¥{Math.round(f.predicted_price)}</strong>
                        </div>
                        <div>{getPriceChangeReason(f)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ));
          })()}

          {forecastData.pricing_strategy && (
            <Alert
              type="info"
              showIcon
              className="!border-[var(--paper-warm)] !bg-[var(--paper-cream)]/60"
              message={<span className="text-[var(--ink-black)]">定价策略参考</span>}
              description={
                <div className="flex flex-wrap gap-3 text-sm text-[var(--ink-muted)]">
                  <span>{forecastData.pricing_strategy.weekend_premium}</span>
                  <span>{forecastData.pricing_strategy.holiday_premium}</span>
                  <span>{forecastData.pricing_strategy.advance_discount}</span>
                </div>
              }
            />
          )}
        </div>
      ),
    };

    const factorsTab = {
      key: 'factors',
      label: (
        <span className="inline-flex items-center gap-1.5 text-[var(--ink-medium)]">
          <PieChartOutlined className="text-[var(--jade)]" />
          因子分析
        </span>
      ),
      children: factorData ? (
        <div className="space-y-6">
          <Row gutter={[12, 12]}>
            <Col xs={24} sm={8}>
              <div className="prediction-stat-card p-4">
                <Statistic
                  title={<span className="text-xs text-[var(--ink-muted)]">锚定日模型基准价</span>}
                  value={factorData.predicted_price}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ color: 'var(--ochre)', fontWeight: 700, fontFamily: 'var(--font-serif)' }}
                />
              </div>
            </Col>
            <Col xs={24} sm={8}>
              <div className="prediction-stat-card p-4">
                <Statistic
                  title={<span className="text-xs text-[var(--ink-muted)]">商圈均价</span>}
                  value={factorData.district_avg_price}
                  prefix="¥"
                  precision={0}
                  valueStyle={{ fontFamily: 'var(--font-serif)' }}
                />
              </div>
            </Col>
            <Col xs={24} sm={8}>
              {factorData.model_info?.r2 != null && (
                <div className="prediction-stat-card p-4">
                  <div className="mb-1 text-xs text-[var(--ink-muted)]">模型拟合度</div>
                  <Progress
                    percent={Math.round(factorData.model_info.r2 * 100)}
                    size="small"
                    strokeColor={{
                      '0%': 'var(--ochre)',
                      '100%': 'var(--jade)',
                    }}
                    format={p => `R²=${(p! / 100).toFixed(2)}`}
                  />
                  {factorData.model_info.mape != null && (
                    <div className="mt-1 text-[11px] text-[var(--ink-muted)]">
                      MAPE {factorData.model_info.mape.toFixed(1)}% · 样本{' '}
                      {factorData.model_info.sample_count?.toLocaleString() ?? '—'}
                    </div>
                  )}
                </div>
              )}
              {factorData.model_info?.r2 == null && factorData.model_info?.mae != null && (
                <div className="prediction-stat-card p-4">
                  <div className="mb-1 text-xs text-[var(--ink-muted)]">日级模型验证 MAE</div>
                  <div
                    className="text-2xl font-semibold tabular-nums text-[var(--ink-black)]"
                    style={{ fontFamily: 'var(--font-serif)' }}
                  >
                    ¥{Number(factorData.model_info.mae).toFixed(0)}
                  </div>
                  <div className="mt-1 text-[11px] text-[var(--ink-muted)]">价格单位误差（元），供参考</div>
                </div>
              )}
            </Col>
          </Row>

          <div
            className="text-sm font-semibold text-[var(--ink-black)]"
            style={{ fontFamily: 'var(--font-serif)' }}
          >
            逐项敏感度
          </div>
          <Alert
            type="info"
            showIcon
            className="!border-[var(--paper-warm)] !bg-[var(--paper-cream)]/60"
            message={factorData.methodology?.name || '对比基线原理'}
            description={
              factorData.methodology?.description ||
              '保持其他特征不变，将单项特征恢复为预设的常见基线（如面积→50㎡、设施关闭），用同一模型重算预测价；价差即为该因子边际贡献。基线为规则基线，非全市统计均值。'
            }
          />

          {(factorData.factors || []).length > 0 ? (
            <>
              <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] p-2">
                <ReactECharts
                  option={getTornadoOption()}
                  style={{ height: Math.max(220, (factorData.factors || []).length * 28 + 48) }}
                  opts={{ renderer: 'svg' }}
                />
              </div>

              <div className="overflow-hidden rounded-xl border border-[var(--paper-warm)]">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-[var(--paper-cream)] text-xs text-[var(--ink-muted)]">
                      <th className="px-3 py-2.5 text-left font-medium">特征</th>
                      <th className="px-3 py-2.5 text-center font-medium">您的配置</th>
                      <th className="px-3 py-2.5 text-center font-medium">对比基线</th>
                      <th className="px-3 py-2.5 text-right font-medium">边际贡献</th>
                      <th className="px-3 py-2.5 text-right font-medium">占预测价</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(factorData.factors || []).map((f: any, i: number) => (
                      <tr
                        key={i}
                        className="border-t border-[var(--paper-warm)] transition-colors hover:bg-[var(--paper-cream)]/50"
                      >
                        <td className="px-3 py-2 font-medium text-[var(--ink-black)]">{f.factor}</td>
                        <td className="px-3 py-2 text-center text-[var(--ink-medium)]">{f.your_value}</td>
                        <td className="px-3 py-2 text-center text-[var(--ink-muted)]">{f.baseline}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">
                          <span className={f.delta >= 0 ? 'text-[var(--jade)]' : 'text-[var(--ochre)]'}>
                            {f.delta >= 0 ? '+' : ''}
                            {f.delta} 元
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right text-[var(--ink-muted)]">
                          {f.pct > 0 ? '+' : ''}
                          {f.pct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <Alert message="当前配置均为市场基线水平，无显著差异项。" type="info" showIcon className="!border-[var(--paper-warm)]" />
          )}

          {(factorData.global_importance || []).length > 0 && (
            <div className="border-t border-[var(--paper-warm)] pt-6">
              <div
                className="mb-1 text-sm font-semibold text-[var(--ink-black)]"
                style={{ fontFamily: 'var(--font-serif)' }}
              >
                模型全局特征重要性 Top 10
              </div>
              <div className="mb-4 text-xs text-[var(--ink-muted)]">
                基于 XGBoost 训练得到的 Gain 重要性，反映模型在整体样本上对各特征的依赖程度。
              </div>
              <div className="space-y-2">
                {factorData.global_importance.map((g: any, i: number) => {
                  const maxImp = factorData.global_importance[0]?.importance || 1;
                  const pct = Math.min(100, (g.importance / maxImp) * 100);
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <span className="w-36 shrink-0 truncate text-right text-xs text-[var(--ink-medium)]" title={g.feature}>
                        {g.display_name || g.feature}
                      </span>
                      <div className="h-5 flex-1 overflow-hidden rounded-full bg-[var(--paper-cream)] ring-1 ring-[var(--paper-warm)]">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${pct}%`,
                            background:
                              i < 3
                                ? `linear-gradient(90deg, var(--ochre), var(--gold))`
                                : `linear-gradient(90deg, rgba(90,138,110,0.5), var(--jade))`,
                          }}
                        />
                      </div>
                      <span className="w-12 shrink-0 text-right text-xs tabular-nums text-[var(--ink-muted)]">
                        {g.importance}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ) : (
        <Empty description="暂无因子数据" className="py-12" />
      ),
    };

    const compTab = {
      key: 'competitiveness',
      label: (
        <span className="inline-flex items-center gap-1.5 text-[var(--ink-medium)]">
          <TrophyOutlined className="text-[var(--gold)]" />
          竞争力
        </span>
      ),
      children: competitivenessData ? (
        <div className="space-y-6">
          <Row gutter={[24, 24]}>
            <Col xs={24} md={10} className="flex flex-col items-center">
              <div className="w-full max-w-[280px] rounded-2xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/25 p-2 shadow-[var(--shadow-soft)]">
                <ReactECharts
                  option={getGaugeOption(competitivenessData.competitiveness_score)}
                  style={{ height: 240, width: '100%' }}
                  opts={{ renderer: 'svg' }}
                />
              </div>
              <Tag
                className={`!mt-3 !border-[var(--paper-warm)] !px-4 !py-1 !text-sm ${
                  competitivenessData.competitiveness_score >= 70
                    ? '!bg-[var(--jade-pale)] !text-[var(--jade)]'
                    : competitivenessData.competitiveness_score >= 45
                      ? '!bg-[var(--paper-cream)] !text-[var(--ink-black)]'
                      : '!bg-[var(--ochre-pale)] !text-[var(--ochre)]'
                }`}
              >
                {competitivenessData.competitiveness_level}
              </Tag>
            </Col>
            <Col xs={24} md={14}>
              <div className="mb-2 text-sm font-medium text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
                价格对比
              </div>
              <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] p-2">
                <ReactECharts option={getCompetitivenessBarOption()} style={{ height: 168 }} opts={{ renderer: 'svg' }} />
              </div>
              {competitivenessData.pricing_analysis?.evaluation && (
                <div className="mt-3 text-xs italic leading-relaxed text-[var(--ink-muted)]">
                  {competitivenessData.pricing_analysis.evaluation}
                </div>
              )}

              {competitivenessData.market_position && (
                <div className="mt-5 rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/40 p-4">
                  <div className="mb-2 text-sm font-medium text-[var(--ink-black)]">市场定位</div>
                  <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-white)] !text-[var(--ink-black)]">
                    {competitivenessData.market_position.position}
                  </Tag>
                  <span className="ml-2 text-xs text-[var(--ink-muted)]">
                    {competitivenessData.market_position.detail}
                  </span>
                </div>
              )}

              {competitivenessData.facility_analysis && (
                <div className="mt-5">
                  <div className="mb-2 text-sm font-medium text-[var(--ink-muted)]">
                    设施配置（{competitivenessData.facility_analysis.count} 项）
                  </div>
                  <Progress
                    percent={Math.min(100, competitivenessData.facility_analysis.score * 2.5)}
                    strokeColor={{
                      '0%': 'var(--ochre)',
                      '50%': 'var(--gold)',
                      '100%': 'var(--jade)',
                    }}
                    size="small"
                  />
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(competitivenessData.facility_analysis.facilities || []).map((f: string) => (
                      <Tag key={f} className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-xs !text-[var(--ink-light)]">
                        {f}
                      </Tag>
                    ))}
                  </div>
                </div>
              )}
            </Col>
          </Row>

          {competitivenessData.suggestions?.length > 0 && (
            <div className="border-t border-[var(--paper-warm)] pt-5">
              <div className="mb-3 text-sm font-semibold text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
                优化建议
              </div>
              {competitivenessData.suggestions.map((s: string, i: number) => (
                <div key={i} className="mb-2 flex items-start gap-3 text-sm text-[var(--ink-medium)]">
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--gold)] ring-2 ring-[var(--ochre-pale)]"
                    aria-hidden
                  />
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <Empty description="暂无竞争力数据" className="py-12" />
      ),
    };

    return [forecastTab, factorsTab, compTab];
  }, [forecastData, factorData, competitivenessData]);

  return (
    <div className="prediction-shell space-y-10 pb-10 sm:space-y-12">
      <PageHeader
        title="智能定价预测"
        subtitle="面向经营者与投资者：填写房源条件与当前/心理价位，系统将给出模型参考价、因子解读与竞争力建议，并匹配相似竞品供对比。"
        category="Prediction"
      />

      <ZenSection title="定价工作台" accent="ochre">
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={8}>
          <motion.div {...fadeInUp}>
              <ZenPanel accent="jade" title="房源与条件" titleCaps={false}>
              <Alert
                type="info"
                showIcon
                  className="mb-4 !border-[var(--paper-warm)] !bg-[var(--paper-cream)]/70"
                  message={<span className="text-[var(--ink-black)]">使用说明</span>}
                description={
                    <span className="text-[var(--ink-muted)]">
                      请填写<strong className="text-[var(--ink-black)]">区位、户型、设施与您的定价</strong>
                      ；也可从「我的房源」快速载入已保存信息。
                  </span>
                }
              />
              <Form
                className="prediction-form"
                form={form}
                layout="vertical"
                onFinish={handleAnalyze}
                onFinishFailed={({ errorFields }) => {
                  console.log('表单验证失败:', errorFields);
                  message.error('请填写所有必填字段');
                }}
                initialValues={{
                  capacity: 2,
                  bedrooms: 1,
                  has_wifi: true,
                  has_air_conditioning: true
                }}
              >
                {/* 快速选择我的房源 */}
                {myListings.length > 0 && (
                  <>
                    <Form.Item label={<><HomeOutlined /> 快速选择我的房源</>}>
                      <Select
                        placeholder="选择已保存的房源，自动填充表单"
                        allowClear
                        onChange={handleSelectMyListing}
                        size="middle"
                      >
                        {myListings.map(listing => (
                          <Option key={listing.id} value={listing.id}>
                            {listing.title} - {listing.trade_area || listing.district} ({listing.bedroom_count}室 ¥{listing.current_price})
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Divider className="!border-[var(--paper-warm)]" style={{ margin: '8px 0' }} />
                  </>
                )}
        
                <Form.Item
                  label="行政区"
                  name="district"
                  rules={[{ required: true, message: '请选择行政区' }]}
                >
                  <Select 
                    placeholder="选择行政区" 
                    onChange={handleDistrictChange}
                    size="middle"
                  >
                    {districts.map(d => (
                      <Option key={d} value={d}>{d}</Option>
                    ))}
                  </Select>
                </Form.Item>
        
                <Form.Item
                  label="商圈"
                  name="trade_area"
                  tooltip="商圈对价格影响更大，建议选择具体商圈"
                >
                  <Select placeholder="选择商圈（可选）" allowClear size="middle">
                    {tradeAreas.map(ta => (
                      <Option key={ta} value={ta}>{ta}</Option>
                    ))}
                  </Select>
                </Form.Item>

                <Form.Item
                  label="您的挂牌价 / 心理价位（元）"
                  name="current_price"
                  tooltip="用于与模型参考价、市场竞品对比；不填时系统按面积估算一个参考价参与竞争力分析"
                >
                  <InputNumber min={1} max={99999} placeholder="建议填写以便对比" style={{ width: '100%' }} size="middle" />
                </Form.Item>
        
                <Row gutter={[8, 8]}>
                  <Col span={8}>
                    <Form.Item
                      label="卧室数"
                      name="bedrooms"
                      rules={[{ required: true }]}
                    >
                      <InputNumber min={0} max={10} style={{ width: '100%' }} size="middle" />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item
                      label="床位数"
                      name="bed_count"
                      tooltip="床位数是影响价格的第 1 重要因素"
                    >
                      <InputNumber min={1} max={20} style={{ width: '100%' }} size="middle" />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item
                      label="可住人数"
                      name="capacity"
                      rules={[{ required: true }]}
                    >
                      <InputNumber min={1} max={20} style={{ width: '100%' }} size="middle" />
                    </Form.Item>
                  </Col>
                </Row>
        
                <Form.Item
                  label="面积 (㎡)"
                  name="area"
                  tooltip="面积是影响价格的重要因素"
                >
                  <InputNumber min={10} max={500} placeholder="50" style={{ width: '100%' }} size="middle" />
                </Form.Item>
        
                <Form.Item label="设施配置">
                  <Row gutter={[6, 6]}>
                    <Col span={8}>
                      <Form.Item name="has_wifi" valuePropName="checked" noStyle>
                        <Checkbox>WiFi</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_air_conditioning" valuePropName="checked" noStyle>
                        <Checkbox>空调</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_kitchen" valuePropName="checked" noStyle>
                        <Checkbox>厨房</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_projector" valuePropName="checked" noStyle>
                        <Checkbox>投影</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_bathtub" valuePropName="checked" noStyle>
                        <Checkbox>浴缸</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_washer" valuePropName="checked" noStyle>
                        <Checkbox>洗衣机</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_smart_lock" valuePropName="checked" noStyle>
                        <Checkbox>智能锁</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_tv" valuePropName="checked" noStyle>
                        <Checkbox>电视</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_heater" valuePropName="checked" noStyle>
                        <Checkbox>暖气</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="near_metro" valuePropName="checked" noStyle>
                        <Checkbox>近地铁</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="near_station" valuePropName="checked" noStyle>
                        <Checkbox>近火车站</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="near_university" valuePropName="checked" noStyle>
                        <Checkbox>近高校</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="near_ski" valuePropName="checked" noStyle>
                        <Checkbox>近滑雪场</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_elevator" valuePropName="checked" noStyle>
                        <Checkbox>电梯</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_fridge" valuePropName="checked" noStyle>
                        <Checkbox>冰箱</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_terrace" valuePropName="checked" noStyle>
                        <Checkbox>观景露台</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_mahjong" valuePropName="checked" noStyle>
                        <Checkbox>麻将机</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_big_living_room" valuePropName="checked" noStyle>
                        <Checkbox>大客厅</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="has_parking" valuePropName="checked" noStyle>
                        <Checkbox>停车位</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="pet_friendly" valuePropName="checked" noStyle>
                        <Checkbox>可带宠物</Checkbox>
                      </Form.Item>
                    </Col>
                  </Row>
                </Form.Item>

                <Form.Item label="景观特色">
                  <Row gutter={[6, 6]}>
                    <Col span={6}>
                      <Form.Item name="has_river_view" valuePropName="checked" noStyle>
                        <Checkbox>江景</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item name="has_lake_view" valuePropName="checked" noStyle>
                        <Checkbox>湖景</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item name="has_mountain_view" valuePropName="checked" noStyle>
                        <Checkbox>山景</Checkbox>
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item name="has_garden" valuePropName="checked" noStyle>
                        <Checkbox>私家花园</Checkbox>
                      </Form.Item>
                    </Col>
                  </Row>
                </Form.Item>
        
                <Button
                  type="primary"
                  block
                  size="large"
                  icon={<ThunderboltOutlined />}
                  onClick={() => form.submit()}
                  loading={loading}
                  className="!mt-2 !h-12 !border-none !bg-[var(--ink-black)] hover:!bg-[var(--ink-dark)]"
                >
                  开始分析
                </Button>
              </Form>
              </ZenPanel>
          </motion.div>
        </Col>
        
        <Col xs={24} lg={16}>
            <ZenPanel
              accent="ink"
              title="模型输出"
              titleCaps={false}
              loading={loading && !forecastData}
              extra={
                forecastData ? (
                  <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-muted)]">
                    已生成分析
                  </Tag>
                ) : null
              }
            >
              <Spin spinning={loading && !!forecastData} tip="刷新结果…">
            {forecastData ? (
              <motion.div {...fadeInUp}>
                    <Tabs
                      type="card"
                      className="prediction-tabs"
                      defaultActiveKey="forecast"
                      items={predictionTabItems}
                    />
              </motion.div>
            ) : (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={
                      <span className="text-[var(--ink-muted)]">填写左侧房源参数后点击「开始分析」</span>
                    }
                    className="py-20"
                />
            )}
          </Spin>
            </ZenPanel>
        </Col>
      </Row>
      </ZenSection>
    </div>
  );
}
