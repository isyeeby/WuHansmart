import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  CalculatorOutlined,
  LineChartOutlined,
  TrophyOutlined,
  BulbOutlined,
  DollarOutlined,
  HomeOutlined,
  PercentageOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined
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
  Alert,
  Tabs,
  Tooltip,
  Progress,
  Empty,
  Spin,
  Divider,
  message,
  Collapse
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
  InvestmentOpportunity
} from '../services/investmentApi';
import { getDistricts } from '../services/analysisApi';

const { Option } = Select;
const { TabPane } = Tabs;
const { Panel } = Collapse;

// 动画配置
const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
};

export default function Investment() {
  // 状态
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [calculationResult, setCalculationResult] = useState<InvestmentResult | null>(null);
  const [rankings, setRankings] = useState<InvestmentRanking[]>([]);
  const [opportunities, setOpportunities] = useState<InvestmentOpportunity[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [dataLoading, setDataLoading] = useState(false);

  // 初始化数据
  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    setDataLoading(true);
    try {
      const [rankingData, opportunityData, districtData] = await Promise.all([
        getInvestmentRanking(10),
        getInvestmentOpportunities(10),
        getDistricts()
      ]);
      // 正确处理返回的数据结构（兼容新旧格式）
      const rankingList = Array.isArray(rankingData) ? rankingData : ((rankingData as any).data || []);
      const opportunityList = Array.isArray(opportunityData) ? opportunityData : ((opportunityData as any).data || []);
      setRankings(rankingList);
      setOpportunities(opportunityList);
      const districtNames = districtData.map(d => d.district).filter(Boolean);
      console.log('加载商圈数据:', districtNames.length, '个商圈');
      setDistricts(districtNames);
    } catch (error) {
      console.error('获取数据失败:', error);
      message.warning('部分数据加载失败，请刷新页面重试');
    } finally {
      setDataLoading(false);
    }
  };

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
        <Tag color={index < 3 ? 'gold' : 'default'}>{index + 1}</Tag>
      )
    },
    {
      title: '商圈',
      dataIndex: 'district',
      key: 'district'
    },
    {
      title: (
        <Tooltip title="0–100 综合吸引力分（多因子加权），非财务年化收益率">
          <span>综合评分</span>
        </Tooltip>
      ),
      dataIndex: 'roi_score',
      key: 'roi_score',
      render: (score: number) => (
        <Progress 
          percent={score} 
          size="small" 
          strokeColor={score >= 80 ? '#52c41a' : score >= 60 ? '#faad14' : '#f5222d'}
          format={percent => `${percent}分`}
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
        <Tooltip title="日历路径：不可订天次占比；否则：评分+收藏启发式。非真实入住率。">
          <span>需求代理</span>
        </Tooltip>
      ),
      dataIndex: 'occupancy_rate',
      key: 'occupancy_rate',
      render: (rate: number, record: InvestmentRanking) => (
        <Tooltip
          title={
            record.occupancy_basis === 'calendar_unavailable_share'
              ? '日历不可订天次占比'
              : record.occupancy_basis === 'hive_ads_estimated_occupancy'
                ? '数仓 estimated_occupancy 字段（口径以离线 ETL 为准）'
                : '评分+收藏启发式'
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
        <Tag color={rec.includes('推荐') ? 'green' : 'default'}>{rec}</Tag>
      )
    }
  ];

  // 机会表格列
  const opportunityColumns = [
    {
      title: '房源',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true
    },
    {
      title: '商圈',
      dataIndex: 'district',
      key: 'district'
    },
    {
      title: '当前价格',
      dataIndex: 'current_price',
      key: 'current_price',
      render: (price: number) => `¥${price}`
    },
    {
      title: '预测价格',
      dataIndex: 'predicted_price',
      key: 'predicted_price',
      render: (price: number) => `¥${price}`
    },
    {
      title: '价差率',
      dataIndex: 'gap_rate',
      key: 'gap_rate',
      render: (rate: number) => (
        <Tag color="green">+{rate}%</Tag>
      )
    },
    {
      title: (
        <Tooltip title="简化示意：日租×20×12 相对日租×100 尺度，非购房 ROI，未扣运营成本">
          <span>简化收益指标</span>
        </Tooltip>
      ),
      dataIndex: 'estimated_annual_roi',
      key: 'estimated_annual_roi',
      render: (roi: number) => (
        <Tag color={roi > 15 ? 'gold' : roi > 10 ? 'green' : 'blue'}>
          {roi}%
        </Tag>
      )
    }
  ];

  return (
    <div className="space-y-8">
      {/* 页面头部 */}
      <PageHeader
        title="投资分析"
        subtitle="民宿投资计算器、收益率分析与投资机会推荐"
        category="Investment"
      />

      <Collapse defaultActiveKey={[]} className="mb-4 bg-[#faf9f6] border border-[#ebe7e0] rounded">
        <Panel header="数据来源与假设说明（投资分析三模块）" key="inv-meta">
          <ul className="text-sm text-[#666] space-y-2 list-disc pl-5 m-0">
            <li><strong>投资计算器</strong>：按表单公式计算，入住率、月供、运营成本等以您填写或默认假设为准。</li>
            <li><strong>商圈排行</strong>：roi_score 为综合吸引力分；occupancy_rate 为需求代理（日历不可订占比或启发式），非真实入住率；estimated_roi 为收入强度比，与投资计算器 annual_roi（首付回报）不同。</li>
            <li><strong>投资机会</strong>：基于真实房源价与商圈中位价等规则估算潜力，非外部实时行情或承诺收益。</li>
          </ul>
        </Panel>
      </Collapse>

      <Spin spinning={dataLoading}>
        <Tabs defaultActiveKey="calculator" type="card">
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
                    className="shadow-sm"
                    extra={<Tooltip title="输入您的投资计划参数"><BulbOutlined /></Tooltip>}
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
                      className="shadow-sm"
                      extra={
                        <Tag color={getRiskColor(calculationResult.risk_level)}>
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
                              color: calculationResult.annual_roi > 15 ? '#52c41a' : 
                                     calculationResult.annual_roi > 10 ? '#faad14' : '#f5222d'
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
                            valueStyle={{ color: calculationResult.monthly_net_income > 0 ? '#52c41a' : '#f5222d' }}
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

                      <Alert
                        message="投资建议"
                        description={calculationResult.recommendation}
                        type={calculationResult.annual_roi > 15 ? 'success' : calculationResult.annual_roi > 10 ? 'info' : 'warning'}
                        showIcon
                        className="mb-4"
                      />

                      {/* 计算依据说明 */}
                      <Collapse ghost className="mb-4">
                        <Panel header={<span className="text-xs text-gray-500 flex items-center gap-1"><InfoCircleOutlined /> 计算依据说明</span>} key="1">
                          <div className="text-xs text-gray-500 space-y-1">
                            <p><strong>年化收益率计算：</strong>(月净收入 × 12) / 首付金额 × 100%</p>
                            <p><strong>月净收入计算：</strong>期望日租金 × 30天 × 入住率 - 月运营成本 - 月供</p>
                            <p><strong>月供计算：</strong>等额本息公式，基于贷款金额、利率和年限</p>
                            <p><strong>投资评分：</strong>基于年化收益率综合评估 (0-100分)</p>
                            <p><strong>回本周期：</strong>首付金额 / (月净收入 × 12)</p>
                          </div>
                        </Panel>
                      </Collapse>

                      <Divider />

                      {/* 详细数据 */}
                      <Row gutter={[16, 16]}>
                        <Col span={12}>
                          <div className="text-gray-500 mb-1">总投资成本</div>
                          <div className="text-lg font-semibold">¥{calculationResult.total_investment}万</div>
                        </Col>
                        <Col span={12}>
                          <div className="text-gray-500 mb-1">首付金额</div>
                          <div className="text-lg font-semibold">¥{calculationResult.down_payment}万</div>
                        </Col>
                        <Col span={12}>
                          <div className="text-gray-500 mb-1">贷款金额</div>
                          <div className="text-lg font-semibold">¥{calculationResult.loan_amount}万</div>
                        </Col>
                        <Col span={12}>
                          <div className="text-gray-500 mb-1">月供</div>
                          <div className="text-lg font-semibold">¥{calculationResult.monthly_payment}</div>
                        </Col>
                        <Col span={12}>
                          <div className="text-gray-500 mb-1">月营收</div>
                          <div className="text-lg font-semibold">¥{calculationResult.monthly_revenue}</div>
                        </Col>
                      </Row>
                    </Card>
                  </motion.div>
                ) : (
                  <Card className="shadow-sm h-full flex items-center justify-center">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="请输入投资参数并点击计算"
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
                className="shadow-sm"
                extra={
                  <Tooltip title="数据来源于平台真实房源统计，综合商圈均价、评分、收藏数等指标计算">
                    <InfoCircleOutlined className="text-gray-400" />
                  </Tooltip>
                }
              >
                <Alert
                  type="info"
                  showIcon
                  className="mb-4"
                  message="测算说明"
                  description="投资测算排行基于各商圈真实房源数据进行综合评估，考虑因素包括：平均房价、入住率代理（基于评分和收藏数）、市场活跃度等；结果用于测算参考，不是实际订单口径。"
                />
                <Table
                  dataSource={rankings}
                  columns={rankingColumns}
                  rowKey="district"
                  pagination={false}
                />
              </Card>
            </motion.div>
          </TabPane>

          {/* 投资机会 */}
          <TabPane
            tab={<span><BulbOutlined />投资机会</span>}
            key="opportunities"
          >
            <motion.div {...fadeInUp}>
              <Card
                title="价格洼地测算机会"
                className="shadow-sm"
                extra={
                  <div className="flex items-center gap-2">
                    <Tag color="green">高性价比</Tag>
                    <Tooltip title="基于XGBoost模型预测价与实际挂牌价的价差分析">
                      <InfoCircleOutlined className="text-gray-400" />
                    </Tooltip>
                  </div>
                }
              >
                <Alert
                  type="info"
                  showIcon
                  className="mb-4"
                  message="数据来源说明"
                  description="价格洼地识别基于XGBoost价格预测模型，对比模型预测价与实际挂牌价的差异。价差率越大，表示该房源相对模型估价越有价格优势。预估年化收益基于日租金×20天入住计算。"
                />
                <Table
                  dataSource={opportunities}
                  columns={opportunityColumns}
                  rowKey="unit_id"
                  pagination={{ pageSize: 10 }}
                />
              </Card>
            </motion.div>
          </TabPane>
        </Tabs>
      </Spin>
    </div>
  );
}


