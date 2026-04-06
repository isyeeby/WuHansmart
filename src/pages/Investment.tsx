import { useState, useEffect, useMemo, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  CalculatorOutlined,
  TrophyOutlined,
  BulbOutlined,
  HomeOutlined,
  PercentageOutlined,
  ClockCircleOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  StarOutlined,
  BookOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import {
  Card,
  Form,
  InputNumber,
  Select,
  Button,
  Row,
  Col,
  Statistic,
  Table,
  Tag,
  Tabs,
  Tooltip,
  Progress,
  Empty,
  Spin,
  Divider,
  message,
  Collapse,
  Slider,
  List,
} from 'antd';
import ReactECharts from 'echarts-for-react';
import PageHeader from '../components/common/PageHeader';
import {
  calculateInvestment,
  getInvestmentRanking,
  getInvestmentOpportunities,
  InvestmentInput,
  InvestmentResult,
  InvestmentRanking,
  InvestmentOpportunity,
} from '../services/investmentApi';
import { getDistricts } from '../services/analysisApi';

const { Option } = Select;
const { TabPane } = Tabs;
const { Panel } = Collapse;

type ZenCalloutTone = 'ochre' | 'jade' | 'ink';

function ZenCallout({
  tone,
  title,
  icon,
  children,
}: {
  tone: ZenCalloutTone;
  title: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  const barClass =
    tone === 'ochre'
      ? 'bg-gradient-to-b from-[var(--ochre-light)] to-[var(--ochre)]'
      : tone === 'jade'
        ? 'bg-gradient-to-b from-[rgba(90,138,110,0.88)] to-[var(--jade)]'
        : 'bg-gradient-to-b from-[var(--ink-medium)] to-[var(--ink-dark)]';

  return (
    <div className="relative overflow-hidden rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)]/95 shadow-[var(--shadow-soft)]">
      <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${barClass}`} aria-hidden />
      <div className="py-3.5 pl-4 pr-4 sm:py-4 sm:pl-5 sm:pr-5">
        <div
          className="mb-2 flex items-center gap-2 text-[var(--ink-black)]"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          {icon ? <span className="text-[var(--ochre)] opacity-90">{icon}</span> : null}
          <span className="text-[15px] font-semibold tracking-wide">{title}</span>
        </div>
        <div className="text-sm leading-[1.7] text-[var(--ink-medium)]">{children}</div>
      </div>
    </div>
  );
}

const ZEN_PIE_COLORS = ['#5a8a6e', '#b8956e', '#c45c3e', '#d97b5d', '#4a6b58', '#8b7355', '#6b5344', '#7a9a82'];

// 动画配置
const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
};

export default function Investment() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = useMemo(() => {
    const t = searchParams.get('tab');
    if (t === 'opportunities' || t === 'ranking' || t === 'calculator') return t;
    return 'calculator';
  }, [searchParams]);

  // 状态
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [calculationResult, setCalculationResult] = useState<InvestmentResult | null>(null);
  const [rankings, setRankings] = useState<InvestmentRanking[]>([]);
  const [opportunities, setOpportunities] = useState<InvestmentOpportunity[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [dataLoading, setDataLoading] = useState(false);
  const [oppLoading, setOppLoading] = useState(false);
  const [minGapRate, setMinGapRate] = useState(20);
  const [oppListPage, setOppListPage] = useState(1);
  const oppPageSize = 8;

  useEffect(() => {
    (async () => {
      setDataLoading(true);
      try {
        const [rankingData, districtData] = await Promise.all([
          getInvestmentRanking(10),
          getDistricts(),
        ]);
        const rankingList = Array.isArray(rankingData) ? rankingData : ((rankingData as any).data || []);
        setRankings(rankingList);
        const districtNames = districtData.map((d) => d.district).filter(Boolean);
        setDistricts(districtNames);
      } catch (error) {
        console.error('获取数据失败:', error);
        message.warning('部分数据加载失败，请刷新页面重试');
      } finally {
        setDataLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setOppLoading(true);
      try {
        const opportunityData = await getInvestmentOpportunities({
          minGapRate,
          limit: 50,
          minRoi: 10,
        });
        const opportunityList = Array.isArray(opportunityData)
          ? opportunityData
          : ((opportunityData as any).data || []);
        setOpportunities(opportunityList);
      } catch (error) {
        console.error('获取价格洼地候选失败:', error);
        message.warning('价格洼地数据加载失败');
      } finally {
        setOppLoading(false);
      }
    })();
  }, [minGapRate]);

  useEffect(() => {
    setOppListPage(1);
  }, [minGapRate]);

  useEffect(() => {
    const maxP = Math.max(1, Math.ceil(opportunities.length / oppPageSize) || 1);
    if (oppListPage > maxP) setOppListPage(maxP);
  }, [opportunities.length, oppListPage, oppPageSize]);

  // 计算投资
  const handleCalculate = async (values: any) => {
    console.log('表单提交值:', values);
    setLoading(true);
    try {
      const input: InvestmentInput = {
        district: values.district,
        property_price: values.property_price,
        area_sqm: values.area_sqm,
        bedroom_count: values.bedroom_count,
        expected_daily_price: values.expected_daily_price,
        occupancy_rate: values.occupancy_rate || 0.65,
        operating_costs_monthly: values.operating_costs_monthly || 2000,
        renovation_cost: values.renovation_cost || 10,
        loan_ratio: values.loan_ratio || 0.5,
        loan_rate: values.loan_rate || 0.045,
        loan_years: values.loan_years || 20
      };
      console.log('发送请求:', input);
      const result = await calculateInvestment(input);
      console.log('计算结果:', result);
      setCalculationResult(result);
      message.success('投资收益计算完成！');
    } catch (error: any) {
      console.error('计算失败:', error);
      message.error(error?.response?.data?.detail || error?.message || '计算失败，请检查输入参数');
    } finally {
      setLoading(false);
    }
  };

  // 获取收益等级颜色
  const getRiskColor = (risk: string) => {
    switch (risk) {
      case '收益突出':
      case '高收益':
      case '推荐投资':
        return 'green';
      case '中等收益':
      case '中风险':
      case '谨慎投资':
        return 'orange';
      case '保守区间':
      case '低风险':
        return 'blue';
      default:
        return 'default';
    }
  };

  // 获取推荐颜色
  const getRecommendationColor = (rec: string) => {
    if (rec.includes('高收益')) return 'gold';
    if (rec.includes('良好')) return 'green';
    if (rec.includes('稳健')) return 'blue';
    return 'default';
  };

  // 排名表格列
  const rankingColumns = [
    {
      title: '排名',
      dataIndex: 'index',
      key: 'index',
      width: 80,
      render: (_: any, __: any, index: number) => (
        <span
          className={`inline-flex h-8 min-w-[2rem] items-center justify-center rounded-full px-2 text-xs font-semibold tabular-nums ${
            index < 3
              ? 'bg-[var(--ochre)] text-white shadow-sm'
              : 'border border-[var(--paper-warm)] bg-[var(--paper-cream)] text-[var(--ink-muted)]'
          }`}
        >
          {index + 1}
        </span>
      )
    },
    {
      title: '商圈',
      dataIndex: 'district',
      key: 'district'
    },
    {
      title: (
        <Tooltip title="把商圈的订房热度、用户口碑、房价水平、房源多少等综合起来打的 0–100 分，只在各商圈之间比高低；不是年化投资收益率。">
          <span>综合评分</span>
        </Tooltip>
      ),
      dataIndex: 'roi_score',
      key: 'roi_score',
      render: (score: number) => (
        <Progress
          percent={score}
          size="small"
          strokeColor={
            score >= 80 ? 'var(--jade)' : score >= 60 ? 'var(--gold)' : 'var(--ochre-light)'
          }
          trailColor="rgba(212, 208, 200, 0.35)"
          format={(percent) => `${percent}分`}
        />
      )
    },
    {
      title: '平均房价',
      dataIndex: 'avg_price',
      key: 'avg_price',
      render: (price: number) => `¥${price}`
    },
    {
      title: (
        <Tooltip title="表示「有多难订到房」的示意指标，不是酒店系统里的真实入住率。有日历时：难订的日子越多，数字往往越高；没有足够日历时：用该商圈房源的用户评分、收藏量等估算一个相近含义的分数。">
          <span>订房热度示意</span>
        </Tooltip>
      ),
      dataIndex: 'occupancy_rate',
      key: 'occupancy_rate',
      render: (rate: number, record: InvestmentRanking) => (
        <Tooltip
          title={
            record.occupancy_basis === 'calendar_unavailable_share'
              ? '根据价格日历：不可预订的天数占比越高，通常表示档期更紧。'
              : record.occupancy_basis === 'hive_ads_estimated_occupancy'
                ? '来自离线分析数据中的入住相关估算字段。'
                : '日历样本偏少时：用该商圈评分、收藏量等综合估算。'
          }
        >
          <span>{rate}%</span>
        </Tooltip>
      )
    },
    {
      title: '建议',
      dataIndex: 'recommendation',
      key: 'recommendation',
      render: (rec: string) => (
        <Tag
          className={
            rec.includes('推荐')
              ? '!m-0 !border-[rgba(90,138,110,0.45)] !bg-[var(--jade-pale)] !text-[var(--jade)]'
              : '!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-white)] !text-[var(--ink-muted)]'
          }
        >
          {rec}
        </Tag>
      )
    }
  ];

  const renderOppSourcePill = (src: string | undefined) => {
    if (src === 'xgboost_daily')
      return (
        <span className="rounded-full border border-[rgba(90,138,110,0.35)] bg-[var(--jade-pale)] px-2 py-0.5 text-[11px] text-[var(--jade)]">
          系统估价
        </span>
      );
    if (src === 'district_median')
      return (
        <span className="rounded-full border border-[var(--paper-warm)] bg-[var(--paper-cream)] px-2 py-0.5 text-[11px] text-[var(--ink-medium)]">
          同区参考价
        </span>
      );
    return (
      <span className="rounded-full border border-[var(--paper-warm)] px-2 py-0.5 text-[11px] text-[var(--ink-muted)]">
        —
      </span>
    );
  };

  const onTabChange = (key: string) => {
    if (key === 'calculator') setSearchParams({}, { replace: true });
    else setSearchParams({ tab: key }, { replace: true });
  };

  const oppPieChartOption = useMemo(() => {
    const districtGroups: Record<string, number> = {};
    opportunities.forEach((opp) => {
      districtGroups[opp.district] = (districtGroups[opp.district] || 0) + 1;
    });
    const entries = Object.entries(districtGroups);
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {c}个 ({d}%)' },
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          itemStyle: { borderColor: '#faf8f5', borderWidth: 2 },
          data: entries.map(([name, value], i) => ({
            name,
            value,
            itemStyle: { color: ZEN_PIE_COLORS[i % ZEN_PIE_COLORS.length] },
          })),
          emphasis: {
            itemStyle: { shadowBlur: 12, shadowOffsetX: 0, shadowColor: 'rgba(45, 45, 45, 0.12)' },
          },
        },
      ],
    };
  }, [opportunities]);

  return (
    <div className="investment-analysis-scope space-y-8">
      {/* 页面头部 */}
      <PageHeader
        title="投资分析"
        subtitle="投资计算器、商圈测算排行与价格洼地（相对低估候选）"
        category="Investment"
      />

      <Collapse
        defaultActiveKey={[]}
        className="inv-zen-collapse mb-2"
        expandIconPosition="end"
        ghost
      >
        <Panel
          header={
            <span className="flex items-center gap-2">
              <BookOutlined className="text-[var(--ochre)]" />
              卷首导读 · 三块数字各是什么？
            </span>
          }
          key="inv-meta"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)]/90 p-4 shadow-[var(--shadow-soft)]">
              <div
                className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--ochre)]"
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                壹 · 计算器
              </div>
              <p className="m-0 text-sm leading-relaxed text-[var(--ink-medium)]">
                按房价、装修、<strong className="text-[var(--ink-dark)]">等额本息</strong>、日租与入住率、月成本，粗算月净利与相对
                <strong className="text-[var(--ink-dark)]">首付</strong>
                的年化回报、回本年数；未计税费、大修与租金年涨。
              </p>
            </div>
            <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)]/90 p-4 shadow-[var(--shadow-soft)]">
              <div
                className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--jade)]"
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                贰 · 商圈排行
              </div>
              <p className="m-0 text-sm leading-relaxed text-[var(--ink-medium)]">
                <strong className="text-[var(--ink-dark)]">综合分 0–100</strong>
                综合订房热度、口碑、均价带与供给规模，仅作站内横向比较；
                <strong className="text-[var(--ink-dark)]">不是</strong>
                财务年化收益率。「订房热度示意」亦非 PMS 真实入住率。
              </p>
            </div>
            <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)]/90 p-4 shadow-[var(--shadow-soft)]">
              <div
                className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--gold)]"
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                叁 · 价格洼地
              </div>
              <p className="m-0 text-sm leading-relaxed text-[var(--ink-medium)]">
                <strong className="text-[var(--ink-dark)]">参考日价</strong>
                与挂牌对比筛「相对低估」；表内百分比为价差示意，
                <strong className="text-[var(--ink-dark)]">非</strong>
                真实购房投资收益，亦未扣运营成本。
              </p>
            </div>
          </div>
          <p
            className="mt-4 border-t border-dashed border-[var(--paper-warm)] pt-4 text-center text-xs leading-relaxed text-[var(--ink-muted)]"
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            计算器为按揭与现金流常用公式；排行与洼地为数据加权与估值辅助，仅供参考。
            <span className="text-[var(--ink-dark)]">不能替代尽调与专业财务测算。</span>
            表头悬停可查看列含义。
          </p>
        </Panel>
      </Collapse>

      <Spin spinning={dataLoading}>
        <Tabs activeKey={activeTab} onChange={onTabChange} type="card" className="investment-tabs-zen">
          {/* 投资计算器 */}
          <TabPane 
            tab={<span><CalculatorOutlined />投资计算器</span>} 
            key="calculator"
          >
            <Row gutter={24}>
              <Col xs={24} lg={12}>
                <motion.div {...fadeInUp}>
                  <Card
                    title="投资参数设置"
                    className="inv-zen-card shadow-[var(--shadow-soft)]"
                    extra={
                      <Tooltip title="输入您的投资计划参数">
                        <BulbOutlined className="text-[var(--ochre)]" />
                      </Tooltip>
                    }
                  >
                    <Form
                      form={form}
                      layout="vertical"
                      onFinish={handleCalculate}
                      onFinishFailed={({ errorFields }) => {
                        console.log('表单验证失败:', errorFields);
                        message.error('请填写所有必填字段');
                      }}
                      initialValues={{
                        occupancy_rate: 0.65,
                        operating_costs_monthly: 2000,
                        renovation_cost: 10,
                        loan_ratio: 0.5,
                        loan_rate: 0.045,
                        loan_years: 20
                      }}
                    >
                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item
                            label="选择商圈"
                            name="district"
                            rules={[{ required: true, message: '请选择商圈' }]}
                          >
                            <Select placeholder="选择商圈">
                              {districts.map(d => (
                                <Option key={d} value={d}>{d}</Option>
                              ))}
                            </Select>
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item
                            label="房产总价（万元）"
                            name="property_price"
                            rules={[{ required: true, message: '请输入房产总价' }]}
                          >
                            <InputNumber 
                              min={10} 
                              max={1000} 
                              style={{ width: '100%' }}
                              placeholder="例如：150"
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item
                            label="面积（平米）"
                            name="area_sqm"
                            rules={[{ required: true, message: '请输入面积' }]}
                          >
                            <InputNumber 
                              min={10} 
                              max={500} 
                              style={{ width: '100%' }}
                              placeholder="例如：60"
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item
                            label="卧室数量"
                            name="bedroom_count"
                            rules={[{ required: true, message: '请输入卧室数量' }]}
                          >
                            <InputNumber 
                              min={0} 
                              max={10} 
                              style={{ width: '100%' }}
                              placeholder="例如：2"
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item
                            label="期望日租金（元）"
                            name="expected_daily_price"
                            rules={[{ required: true, message: '请输入期望日租金' }]}
                          >
                            <InputNumber 
                              min={50} 
                              max={2000} 
                              style={{ width: '100%' }}
                              placeholder="例如：300"
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item
                            label="预期入住率"
                            name="occupancy_rate"
                          >
                            <InputNumber 
                              min={0.1} 
                              max={1} 
                              step={0.05}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item
                            label="月运营成本（元）"
                            name="operating_costs_monthly"
                          >
                            <InputNumber 
                              min={500} 
                              max={10000} 
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item
                            label="装修成本（万元）"
                            name="renovation_cost"
                          >
                            <InputNumber 
                              min={0} 
                              max={100} 
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      <Row gutter={16}>
                        <Col span={8}>
                          <Form.Item
                            label="贷款比例"
                            name="loan_ratio"
                          >
                            <InputNumber 
                              min={0} 
                              max={0.9} 
                              step={0.1}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item
                            label="贷款利率"
                            name="loan_rate"
                          >
                            <InputNumber 
                              min={0.025} 
                              max={0.06} 
                              step={0.005}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item
                            label="贷款年限"
                            name="loan_years"
                          >
                            <InputNumber 
                              min={5} 
                              max={30} 
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Col>
                      </Row>

                      <Form.Item className="!mb-0">
                        <Button 
                          type="primary" 
                          htmlType="submit" 
                          loading={loading}
                          block
                          size="large"
                          icon={<CalculatorOutlined />}
                        >
                          计算投资收益
                        </Button>
                      </Form.Item>
                    </Form>
                  </Card>
                </motion.div>
              </Col>

              <Col xs={24} lg={12}>
                {calculationResult ? (
                  <motion.div {...fadeInUp}>
                    <Card
                      title="投资分析结果"
                      className="inv-zen-card shadow-[var(--shadow-soft)]"
                      extra={
                        <Tag
                          className={
                            getRiskColor(calculationResult.risk_level) === 'green'
                              ? '!m-0 !border-[rgba(90,138,110,0.45)] !bg-[var(--jade-pale)] !text-[var(--jade)]'
                              : getRiskColor(calculationResult.risk_level) === 'orange'
                                ? '!m-0 !border-[rgba(196,92,62,0.35)] !bg-[var(--ochre-pale)] !text-[var(--ochre)]'
                                : '!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-medium)]'
                          }
                        >
                          {calculationResult.risk_level}
                        </Tag>
                      }
                    >
                      {/* 核心指标 */}
                      <Row gutter={[16, 16]} className="mb-6">
                        <Col span={12}>
                          <Statistic
                            title="年化收益率"
                            value={calculationResult.annual_roi}
                            suffix="%"
                            valueStyle={{
                              color:
                                calculationResult.annual_roi > 15
                                  ? 'var(--jade)'
                                  : calculationResult.annual_roi > 10
                                    ? 'var(--gold)'
                                    : 'var(--ochre)',
                            }}
                            prefix={<PercentageOutlined />}
                          />
                        </Col>
                        <Col span={12}>
                          <Statistic
                            title="回本周期"
                            value={calculationResult.payback_period}
                            suffix="年"
                            prefix={<ClockCircleOutlined />}
                          />
                        </Col>
                      </Row>

                      <Row gutter={[16, 16]} className="mb-6">
                        <Col span={12}>
                          <Statistic
                            title="月净收入"
                            value={calculationResult.monthly_net_income}
                            prefix="¥"
                            valueStyle={{
                              color:
                                calculationResult.monthly_net_income > 0 ? 'var(--jade)' : 'var(--ochre)',
                            }}
                          />
                        </Col>
                        <Col span={12}>
                          <Statistic
                            title="投资评分"
                            value={calculationResult.investment_score}
                            suffix="/100"
                            prefix={<TrophyOutlined />}
                          />
                        </Col>
                      </Row>

                      <div className="mb-4">
                        <ZenCallout
                          tone={
                            calculationResult.annual_roi > 15
                              ? 'ochre'
                              : calculationResult.annual_roi > 10
                                ? 'jade'
                                : 'ink'
                          }
                          title="测算结论"
                          icon={<BulbOutlined />}
                        >
                          <p className="m-0">{calculationResult.recommendation}</p>
                        </ZenCallout>
                      </div>

                      <Collapse
                        ghost
                        className="mb-4 rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/40"
                      >
                        <Panel
                          header={
                            <span className="flex items-center gap-2 text-xs font-medium text-[var(--ink-medium)]">
                              <InfoCircleOutlined className="text-[var(--ochre)]" />
                              公式与口径（可展开）
                            </span>
                          }
                          key="1"
                        >
                          <ul className="m-0 list-none space-y-2 pl-0 text-xs leading-relaxed text-[var(--ink-medium)]">
                            <li className="border-l-2 border-[var(--paper-warm)] pl-3">
                              <strong className="text-[var(--ink-dark)]">年化收益率：</strong>
                              (月净收入 × 12) ÷ 首付 × 100%
                            </li>
                            <li className="border-l-2 border-[var(--paper-warm)] pl-3">
                              <strong className="text-[var(--ink-dark)]">月净收入：</strong>
                              日租金 × 30 × 入住率 − 月运营成本 − 月供
                            </li>
                            <li className="border-l-2 border-[var(--paper-warm)] pl-3">
                              <strong className="text-[var(--ink-dark)]">月供：</strong>
                              等额本息（贷款额、利率、年限）
                            </li>
                            <li className="border-l-2 border-[var(--paper-warm)] pl-3">
                              <strong className="text-[var(--ink-dark)]">投资评分 / 回本周期：</strong>
                              由年化 ROI 与现金流推导的示意指标
                            </li>
                          </ul>
                        </Panel>
                      </Collapse>

                      <Divider className="border-[var(--paper-warm)]" />

                      {/* 详细数据 */}
                      <Row gutter={[16, 16]}>
                        <Col span={12}>
                          <div className="mb-1 text-xs text-[var(--ink-muted)]">总投资成本</div>
                          <div
                            className="text-lg font-semibold text-[var(--ink-black)] tabular-nums"
                            style={{ fontFamily: 'var(--font-serif)' }}
                          >
                            ¥{calculationResult.total_investment}万
                          </div>
                        </Col>
                        <Col span={12}>
                          <div className="mb-1 text-xs text-[var(--ink-muted)]">首付金额</div>
                          <div
                            className="text-lg font-semibold text-[var(--ink-black)] tabular-nums"
                            style={{ fontFamily: 'var(--font-serif)' }}
                          >
                            ¥{calculationResult.down_payment}万
                          </div>
                        </Col>
                        <Col span={12}>
                          <div className="mb-1 text-xs text-[var(--ink-muted)]">贷款金额</div>
                          <div
                            className="text-lg font-semibold text-[var(--ink-black)] tabular-nums"
                            style={{ fontFamily: 'var(--font-serif)' }}
                          >
                            ¥{calculationResult.loan_amount}万
                          </div>
                        </Col>
                        <Col span={12}>
                          <div className="mb-1 text-xs text-[var(--ink-muted)]">月供</div>
                          <div
                            className="text-lg font-semibold text-[var(--ink-black)] tabular-nums"
                            style={{ fontFamily: 'var(--font-serif)' }}
                          >
                            ¥{calculationResult.monthly_payment}
                          </div>
                        </Col>
                        <Col span={12}>
                          <div className="mb-1 text-xs text-[var(--ink-muted)]">月营收</div>
                          <div
                            className="text-lg font-semibold text-[var(--ink-black)] tabular-nums"
                            style={{ fontFamily: 'var(--font-serif)' }}
                          >
                            ¥{calculationResult.monthly_revenue}
                          </div>
                        </Col>
                      </Row>
                    </Card>
                  </motion.div>
                ) : (
                  <Card className="inv-zen-card flex h-full min-h-[320px] items-center justify-center border-dashed border-[var(--paper-warm)] bg-[var(--paper-cream)]/30 shadow-none">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        <span className="text-[var(--ink-muted)]">请输入左侧参数并点击「计算投资收益」</span>
                      }
                    />
                  </Card>
                )}
              </Col>
            </Row>
          </TabPane>

          {/* 收益率排行 */}
          <TabPane
            tab={<span><TrophyOutlined />收益率排行</span>}
            key="ranking"
          >
            <motion.div {...fadeInUp}>
              <Card
                title="各商圈投资测算排行"
                className="inv-zen-card shadow-[var(--shadow-soft)]"
                extra={
                  <Tooltip title="基于平台挂牌房源统计：综合房价、口碑、订房热度示意、房源规模等打分排序">
                    <InfoCircleOutlined className="text-[var(--ink-muted)]" />
                  </Tooltip>
                }
              >
                <div className="mb-5">
                  <ZenCallout tone="jade" title="测算说明" icon={<InfoCircleOutlined />}>
                    <div className="space-y-2">
                      <p className="m-0">
                        排行使用各商圈<strong className="text-[var(--ink-dark)]">真实挂牌房源</strong>
                        汇总，将
                        <strong className="text-[var(--ink-dark)]">平均房价</strong>、
                        <strong className="text-[var(--ink-dark)]">用户评分</strong>、
                        <strong className="text-[var(--ink-dark)]">订房热度示意</strong>、
                        <strong className="text-[var(--ink-dark)]">房源数量</strong>
                        合成<strong className="text-[var(--ink-dark)]">综合分</strong>
                        便于横向比较。
                      </p>
                      <p className="m-0 text-[var(--ink-muted)]">
                        此为统计意义上的<strong className="text-[var(--ink-dark)]">参考排序</strong>
                        ，不是订单量、不是真实入住率，亦<strong className="text-[var(--ink-dark)]">不能</strong>
                        直接当作投资收益率。
                      </p>
                    </div>
                  </ZenCallout>
                </div>
                <Table
                  className="zen-investment-table"
                  size="middle"
                  dataSource={rankings}
                  columns={rankingColumns}
                  rowKey="district"
                  pagination={false}
                />
              </Card>
            </motion.div>
          </TabPane>

          {/* 价格洼地（原独立「价格洼地」页已合并至此） */}
          <TabPane
            tab={<span><ThunderboltOutlined />价格洼地</span>}
            key="opportunities"
          >
            <motion.div {...fadeInUp} className="space-y-5">
              <ZenCallout tone="ochre" title="读数须知" icon={<ThunderboltOutlined />}>
                <div className="space-y-2">
                  <p className="m-0">
                    「参考价」由系统结合历史挂牌与同类规律估算；单套信息不足时用
                    <strong className="text-[var(--ink-dark)]">同商圈主流价位</strong>
                    代替——<strong className="text-[var(--ink-dark)]">不是</strong>
                    平台官方定价或成交价。
                  </p>
                  <p className="m-0">
                    「相对挂牌偏差」仅表示<strong className="text-[var(--ink-dark)]">参考价与当前展示价</strong>
                    的差距，可能含模型误差、促销或房型因素。
                  </p>
                  <p className="m-0 text-[var(--ink-muted)]">
                    商圈<strong className="text-[var(--ink-dark)]">综合分</strong>见「收益率排行」表；右侧饼图仅反映
                    <strong className="text-[var(--ink-dark)]">当前候选</strong>的商圈分布。
                  </p>
                </div>
              </ZenCallout>
              <div className="inv-filter-strip p-4">
                <div className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--ink-muted)]">
                  筛选阈值
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="shrink-0 text-sm text-[var(--ink-dark)]">最小相对挂牌偏差</span>
                  <Slider
                    min={5}
                    max={50}
                    value={minGapRate}
                    onChange={setMinGapRate}
                    className="min-w-[min(100%,12rem)] flex-1"
                  />
                  <InputNumber
                    min={5}
                    max={50}
                    value={minGapRate}
                    onChange={(v) => setMinGapRate(v ?? 20)}
                    formatter={(v) => `${v}%`}
                    parser={(v) => parseFloat((v || '').replace('%', ''))}
                    className="w-[5.5rem]"
                  />
                </div>
              </div>
              <Row gutter={[20, 20]}>
                <Col xs={24} lg={14}>
                  <Spin spinning={oppLoading}>
                    <Card
                      title={
                        <span className="inline-flex items-center gap-2">
                          <BulbOutlined className="text-[var(--ochre)]" />
                          相对低估候选
                          <Tag className="!m-0 !border-[rgba(90,138,110,0.4)] !bg-[var(--jade-pale)] !text-[var(--jade)]">
                            {opportunities.length} 条
                          </Tag>
                        </span>
                      }
                      className="inv-zen-card shadow-[var(--shadow-soft)]"
                      extra={
                        <Tooltip title="与旧版「价格洼地」页、分析接口同源筛选">
                          <InfoCircleOutlined className="text-[var(--ink-muted)]" aria-label="说明" />
                        </Tooltip>
                      }
                    >
                      {opportunities.length > 0 ? (
                        <List
                          className="inv-opp-list"
                          split={false}
                          dataSource={opportunities}
                          pagination={{
                            current: oppListPage,
                            pageSize: oppPageSize,
                            total: opportunities.length,
                            onChange: (p) => setOppListPage(p),
                            showSizeChanger: false,
                            hideOnSinglePage: opportunities.length <= oppPageSize,
                            showTotal: (t) => (
                              <span className="text-xs text-[var(--ink-muted)]">共 {t} 条</span>
                            ),
                            className: '!mt-5',
                          }}
                          renderItem={(record, idx) => {
                            const rank = (oppListPage - 1) * oppPageSize + idx + 1;
                            const gap = record.price_gap;
                            const listPrice = Number(record.current_price);
                            const refPrice = Number(record.predicted_price);
                            const roi = record.estimated_annual_roi;
                            return (
                              <List.Item className="!border-none !px-0 !py-2">
                                <div className="inv-opp-row group flex w-full gap-3 rounded-xl border border-[var(--paper-warm)] bg-gradient-to-br from-[var(--paper-white)] via-[var(--paper-white)] to-[var(--paper-cream)]/40 p-3.5 shadow-[var(--shadow-soft)] transition-[border-color,box-shadow] sm:gap-4 sm:p-4">
                                  <div className="shrink-0 pt-0.5">
                                    <span
                                      className={`inline-flex h-9 w-9 items-center justify-center rounded-full text-xs font-semibold tabular-nums ${
                                        rank <= 3
                                          ? 'bg-[var(--ochre)] text-white shadow-sm'
                                          : 'border border-[var(--paper-warm)] bg-[var(--paper-cream)] text-[var(--ink-muted)]'
                                      }`}
                                    >
                                      {rank}
                                    </span>
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <Link
                                      to={`/listing/${record.unit_id}`}
                                      className="line-clamp-2 text-[15px] font-semibold leading-snug text-[var(--ink-black)] no-underline transition-colors hover:text-[var(--ochre)]"
                                      style={{ fontFamily: 'var(--font-serif)' }}
                                    >
                                      {record.title || record.unit_id}
                                    </Link>
                                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-[var(--ink-muted)]">
                                      <span className="text-[var(--ink-light)]">{record.district}</span>
                                      <span className="inline-flex items-center gap-0.5 tabular-nums">
                                        <StarOutlined className="text-[var(--gold)] text-[13px]" />
                                        {record.rating}
                                      </span>
                                      {renderOppSourcePill(record.prediction_source)}
                                    </div>
                                    <div className="mt-3 flex flex-wrap items-baseline gap-x-1 gap-y-1 text-sm">
                                      <Tooltip title="当前挂牌日价">
                                        <span className="tabular-nums">
                                          <span className="mr-1 text-[11px] text-[var(--ink-muted)]">挂牌</span>
                                          <span className="font-medium text-[var(--ink-black)]">
                                            ¥{listPrice.toFixed(0)}
                                          </span>
                                        </span>
                                      </Tooltip>
                                      <span className="mx-1 text-[var(--ink-muted)]">→</span>
                                      <Tooltip title="系统参考日价（详见读数须知）">
                                        <span className="tabular-nums">
                                          <span className="mr-1 text-[11px] text-[var(--ink-muted)]">参考</span>
                                          <span
                                            className="font-semibold text-[var(--ochre)]"
                                            style={{ fontFamily: 'var(--font-serif)' }}
                                          >
                                            ¥{refPrice.toFixed(0)}
                                          </span>
                                        </span>
                                      </Tooltip>
                                      {gap != null && gap > 0 && (
                                        <span className="ml-2 text-xs font-medium text-[var(--jade)] tabular-nums">
                                          +¥{Number(gap).toFixed(0)}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <div className="flex w-full shrink-0 flex-col justify-center gap-2 border-t border-dashed border-[var(--paper-warm)] pt-3 sm:ml-0 sm:w-[7.5rem] sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
                                    <div className="flex flex-wrap items-center justify-between gap-2 sm:flex-col sm:items-stretch">
                                      <Tooltip title="相对挂牌偏差（参考价高于挂牌的幅度）">
                                        <Tag className="!m-0 !inline-flex !w-full !justify-center !border-[rgba(90,138,110,0.45)] !bg-[var(--jade-pale)] !py-1 !text-[var(--jade)]">
                                          +{record.gap_rate}%
                                        </Tag>
                                      </Tooltip>
                                      <Tooltip title="由价差换算的示意比例，非真实年化投资收益">
                                        <div className="text-center text-[11px] leading-tight text-[var(--ink-muted)]">
                                          示意{' '}
                                          <span
                                            className={`font-semibold tabular-nums ${
                                              roi > 15
                                                ? 'text-[var(--ink-dark)]'
                                                : roi > 10
                                                  ? 'text-[var(--jade)]'
                                                  : 'text-[var(--ink-medium)]'
                                            }`}
                                          >
                                            {roi}%
                                          </span>
                                        </div>
                                      </Tooltip>
                                    </div>
                                    <Link
                                      to={`/listing/${record.unit_id}`}
                                      className="flex items-center justify-center gap-1 rounded-lg border border-[var(--paper-warm)] bg-[var(--paper-white)] py-1.5 text-xs font-medium text-[var(--ochre)] no-underline transition-colors hover:border-[rgba(196,92,62,0.35)] hover:bg-[var(--ochre-pale)]"
                                    >
                                      房源详情
                                      <ArrowRightOutlined className="text-[10px] opacity-80" />
                                    </Link>
                                  </div>
                                </div>
                              </List.Item>
                            );
                          }}
                        />
                      ) : (
                        <Empty description="暂无满足阈值的候选（已排除床位/青旅等及异常挂牌价）" />
                      )}
                    </Card>
                  </Spin>
                </Col>
                <Col xs={24} lg={10}>
                  <Card
                    title="候选房源商圈分布"
                    className="inv-zen-card shadow-[var(--shadow-soft)]"
                    extra={
                      <Tooltip title="仅统计本页候选列表，随「最小相对挂牌偏差」变化">
                        <InfoCircleOutlined className="text-[var(--ink-muted)] text-sm" />
                      </Tooltip>
                    }
                  >
                    <ReactECharts option={oppPieChartOption} style={{ height: 340 }} />
                  </Card>
                </Col>
              </Row>
              <ZenCallout tone="jade" title="使用提示" icon={<InfoCircleOutlined />}>
                <div className="space-y-1">
                  <p className="m-0">调高「最小相对挂牌偏差」可缩小列表、聚焦价差更显著的房源。</p>
                  <p className="m-0 text-[var(--ink-muted)]">
                    为控制响应时间，后端会先对一定数量房源做精细参考价测算再排序（与旧价格洼地页一致）。
                  </p>
                </div>
              </ZenCallout>
            </motion.div>
          </TabPane>
        </Tabs>
      </Spin>
    </div>
  );
}


