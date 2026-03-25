import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  BulbOutlined, 
  TrophyOutlined,
  RiseOutlined,
  DollarOutlined,
  PercentageOutlined,
  StarOutlined,
  ArrowRightOutlined
} from '@ant-design/icons';
import { 
  Card, 
  Button, 
  Row, 
  Col, 
  Table,
  Tag,
  Alert,
  Empty,
  Spin,
  Slider,
  InputNumber,
  Statistic,
  Progress,
  Badge,
  Tooltip
} from 'antd';
import ReactECharts from 'echarts-for-react';
import PageHeader from '../components/common/PageHeader';
import {
  getPriceOpportunities,
  getROIRanking,
  PriceOpportunity,
  ROIRanking
} from '../services/priceOpportunitiesApi';

// 动画配置
const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
};

export default function Opportunities() {
  // 状态
  const [opportunities, setOpportunities] = useState<PriceOpportunity[]>([]);
  const [rankings, setRankings] = useState<ROIRanking[]>([]);
  const [loading, setLoading] = useState(false);
  const [minGapRate, setMinGapRate] = useState(20);

  // 初始化数据
  useEffect(() => {
    fetchData();
  }, [minGapRate]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [oppData, rankingData] = await Promise.all([
        getPriceOpportunities(minGapRate, 20),
        getROIRanking(10)
      ]);
      setOpportunities(oppData);
      setRankings(rankingData);
    } catch (error) {
      console.error('获取数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 生成ROI排名图表配置
  const getROIOption = () => {
    return {
      title: { text: '商圈投资收益率排名' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'value',
        name: 'ROI评分'
      },
      yAxis: {
        type: 'category',
        data: rankings.slice(0, 10).map(r => r.district).reverse()
      },
      series: [{
        type: 'bar',
        data: rankings.slice(0, 10).map(r => ({
          value: r.roi_score,
          itemStyle: {
            color: r.roi_score >= 80 ? '#52c41a' : 
                   r.roi_score >= 60 ? '#faad14' : '#f5222d'
          }
        })).reverse(),
        label: {
          show: true,
          position: 'right',
          formatter: '{c}分'
        }
      }],
      grid: { left: '15%', right: '10%', bottom: '10%', top: '15%' }
    };
  };

  // 生成价格分布图表配置
  const getPriceDistributionOption = () => {
    const districtGroups: Record<string, number> = {};
    opportunities.forEach(opp => {
      districtGroups[opp.district] = (districtGroups[opp.district] || 0) + 1;
    });

    return {
      title: { text: '价格洼地房源分布' },
      tooltip: { trigger: 'item', formatter: '{b}: {c}个 ({d}%)' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: Object.entries(districtGroups).map(([name, value]) => ({
          name,
          value
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    };
  };

  // 机会表格列
  const opportunityColumns = [
    {
      title: '排名',
      key: 'index',
      width: 80,
      render: (_: any, __: any, index: number) => (
        <Badge 
          count={index + 1} 
          style={{ 
            backgroundColor: index < 3 ? '#ffd700' : '#d9d9d9',
            color: index < 3 ? '#000' : '#666'
          }} 
        />
      )
    },
    {
      title: '房源',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string, record: PriceOpportunity) => (
        <div>
          <div className="font-medium">{title}</div>
          <div className="text-gray-500 text-sm">{record.district}</div>
        </div>
      )
    },
    {
      title: '当前价格',
      dataIndex: 'current_price',
      key: 'current_price',
      render: (price: number) => (
        <span className="text-green-600 font-semibold">¥{price}</span>
      )
    },
    {
      title: (
        <Tooltip title="XGBoost 回归估算，或模型失败时改用同行政区挂牌价中位数。非官方指导价。">
          <span className="cursor-help border-b border-dotted border-gray-400">参考估算价</span>
        </Tooltip>
      ),
      dataIndex: 'predicted_price',
      key: 'predicted_price',
      render: (price: number) => (
        <span className="text-blue-600 font-semibold">¥{price}</span>
      )
    },
    {
      title: (
        <Tooltip title="(参考估算价 − 当前挂牌价) ÷ 当前挂牌价。数值大只说明与模型/中位数偏离大，不等于一定能套利。">
          <span className="cursor-help border-b border-dotted border-gray-400">相对挂牌偏差</span>
        </Tooltip>
      ),
      dataIndex: 'gap_rate',
      key: 'gap_rate',
      render: (rate: number) => (
        <Tag color="green" icon={<RiseOutlined />}>
          +{rate.toFixed(1)}%
        </Tag>
      )
    },
    {
      title: (
        <Tooltip title="模型：XGBoost；区中位数：模型不可用时的兜底参考。">
          <span className="cursor-help border-b border-dotted border-gray-400">估算依据</span>
        </Tooltip>
      ),
      dataIndex: 'prediction_source',
      key: 'prediction_source',
      width: 100,
      render: (src: string | undefined) => {
        if (src === 'xgboost') return <Tag color="processing">模型</Tag>;
        if (src === 'district_median') return <Tag>区中位数</Tag>;
        return <Tag color="default">—</Tag>;
      }
    },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      render: (rating: number) => (
        <div className="flex items-center">
          <StarOutlined className="text-yellow-500 mr-1" />
          <span>{rating}</span>
        </div>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: PriceOpportunity) => (
        <Button 
          type="link" 
          icon={<ArrowRightOutlined />}
          href={`/listing/${record.unit_id}`}
        >
          查看详情
        </Button>
      )
    }
  ];

  // 排名表格列
  const rankingColumns = [
    {
      title: '排名',
      key: 'index',
      width: 80,
      render: (_: any, __: any, index: number) => (
        <div className="flex items-center justify-center">
          {index < 3 ? (
            <TrophyOutlined 
              className={`text-2xl ${
                index === 0 ? 'text-yellow-500' : 
                index === 1 ? 'text-gray-400' : 'text-orange-400'
              }`} 
            />
          ) : (
            <span className="text-gray-500 font-medium">{index + 1}</span>
          )}
        </div>
      )
    },
    {
      title: '商圈',
      dataIndex: 'district',
      key: 'district',
      render: (district: string) => (
        <span className="font-medium">{district}</span>
      )
    },
    {
      title: '投资评分',
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
      title: '预估入住率',
      dataIndex: 'occupancy_rate',
      key: 'occupancy_rate',
      render: (rate: number) => `${rate}%`
    },
    {
      title: '投资建议',
      dataIndex: 'recommendation',
      key: 'recommendation',
      render: (rec: string) => (
        <Tag color={rec.includes('推荐') ? 'green' : rec.includes('谨慎') ? 'orange' : 'default'}>
          {rec}
        </Tag>
      )
    }
  ];

  return (
    <div className="space-y-8">
      {/* 页面头部 */}
      <PageHeader
        title="价格洼地分析"
        subtitle="用模型参考价与当前挂牌价对比，筛出「可能存在价差」的候选，仅供研究参考"
        category="Opportunities"
      />

      <Spin spinning={loading}>
        <motion.div {...fadeInUp}>
          <Alert
            type="warning"
            showIcon
            className="mb-6"
            message="关于本页数字的说明"
            description={
              <div className="text-sm space-y-1">
                <p>
                  「参考估算价」来自 XGBoost 或行政区中位数兜底，不是平台定价、也不是成交价或收益承诺。
                </p>
                <p>
                  「相对挂牌偏差」= (参考估算价 − 当前挂牌价) ÷ 当前挂牌价，仅表示<strong>统计模型与展示价之间的差异</strong>，
                  可能来自模型误差、房源信息不全、促销或特殊房型等，请结合详情页自行判断。
                </p>
              </div>
            }
          />
        </motion.div>
        {/* 筛选控制 */}
        <motion.div {...fadeInUp}>
          <Card className="shadow-sm mb-6">
            <div className="flex items-center">
              <span className="mr-4">最小相对挂牌偏差：</span>
              <Slider
                min={5}
                max={50}
                value={minGapRate}
                onChange={setMinGapRate}
                className="flex-1 mr-4"
              />
              <InputNumber
                min={5}
                max={50}
                value={minGapRate}
                onChange={(value) => setMinGapRate(value || 20)}
                formatter={value => `${value}%`}
                parser={value => parseFloat(value!.replace('%', ''))}
                style={{ width: 80 }}
              />
            </div>
          </Card>
        </motion.div>

        <Row gutter={24}>
          {/* 左侧：价格洼地列表 */}
          <Col xs={24} lg={14}>
            <motion.div {...fadeInUp}>
              <Card 
                title={
                  <div className="flex items-center">
                    <BulbOutlined className="mr-2 text-yellow-500" />
                    <span>价格洼地候选</span>
                    <Tag color="green" className="ml-2">{opportunities.length} 条</Tag>
                  </div>
                }
                className="shadow-sm"
              >
                {opportunities.length > 0 ? (
                  <Table
                    dataSource={opportunities}
                    columns={opportunityColumns}
                    rowKey="unit_id"
                    pagination={{ pageSize: 10 }}
                    scroll={{ x: true }}
                  />
                ) : (
                  <Empty description="暂无满足阈值的候选（已排除床位/青旅等及过低/过高挂牌价）" />
                )}
              </Card>
            </motion.div>
          </Col>

          {/* 右侧：统计图表 */}
          <Col xs={24} lg={10}>
            <motion.div {...fadeInUp}>
              <Card 
                title={
                  <div className="flex items-center">
                    <TrophyOutlined className="mr-2 text-yellow-500" />
                    <span>商圈投资排名</span>
                  </div>
                }
                className="shadow-sm mb-6"
              >
                <ReactECharts option={getROIOption()} style={{ height: 300 }} />
              </Card>

              <Card 
                title="分布统计"
                className="shadow-sm"
              >
                <ReactECharts option={getPriceDistributionOption()} style={{ height: 250 }} />
              </Card>
            </motion.div>
          </Col>
        </Row>

        {/* 底部：详细排名 */}
        <motion.div {...fadeInUp} className="mt-6">
          <Card 
            title={
              <div className="flex items-center">
                <RiseOutlined className="mr-2 text-green-500" />
                <span>投资收益率详细排名</span>
              </div>
            }
            className="shadow-sm"
          >
            <Row gutter={24} className="mb-6">
              <Col span={6}>
                <Statistic
                  title="最佳投资商圈"
                  value={rankings[0]?.district || '-'}
                  prefix={<TrophyOutlined className="text-yellow-500" />}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="最高ROI评分"
                  value={rankings[0]?.roi_score || 0}
                  suffix="分"
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="平均房价"
                  value={rankings[0]?.avg_price || 0}
                  prefix="¥"
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="预估入住率"
                  value={rankings[0]?.occupancy_rate || 0}
                  suffix="%"
                />
              </Col>
            </Row>

            <Table
              dataSource={rankings}
              columns={rankingColumns}
              rowKey="district"
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </motion.div>

        {/* 投资建议 */}
        <motion.div {...fadeInUp} className="mt-6">
          <Alert
            message="投资策略建议"
            description={
              <div className="space-y-2">
                <p>1. <strong>候选筛选</strong>：相对挂牌偏差 ≥ 阈值仅作排序线索，需核对房型、设施、日历价是否与模型假设一致</p>
                <p>2. <strong>商圈选择</strong>：ROI 评分为启发式指数，可与下方商圈排名对照，勿当作财务结论</p>
                <p>3. <strong>风险控制</strong>：结合评分、评价与实拍，警惕信息不全或异常低价</p>
              </div>
            }
            type="info"
            showIcon
          />
        </motion.div>
      </Spin>
    </div>
  );
}
