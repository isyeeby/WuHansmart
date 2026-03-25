import React, { useState, useEffect, useCallback } from 'react';
import {
  List,
  Rate,
  Button,
  Grid,
  Form,
  Select,
  Slider,
  Spin,
  Tag,
  message,
  Row,
  Col,
  Divider,
  Empty,
} from 'antd';
import { Link } from 'react-router-dom';
import {
  EnvironmentOutlined,
  HomeOutlined,
  BulbOutlined,
  CompassOutlined,
} from '@ant-design/icons';
import { PageHeader } from '../components/common';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import { getRecommendations, type RecommendedListing, type RecommendParams } from '../services/recommendApi';
import { getDistricts, type DistrictStats } from '../services/analysisApi';

const { Option } = Select;
const { useBreakpoint } = Grid;

const FACILITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'subway', label: '近地铁' },
  { value: 'projector', label: '巨幕投影' },
  { value: 'bathtub', label: '浴缸' },
  { value: 'cooking', label: '可做饭' },
  { value: 'wifi', label: 'WiFi' },
  { value: 'washer', label: '洗衣机' },
  { value: 'parking', label: '停车位' },
  { value: 'mahjong', label: '麻将/棋牌' },
  { value: 'balcony', label: '阳台/露台' },
  { value: 'smart_lock', label: '智能门锁' },
  { value: 'pet', label: '宠物友好' },
];

const Recommendation: React.FC = () => {
  const screens = useBreakpoint();
  const isMobile = !screens.lg;
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<RecommendedListing[]>([]);
  const [form] = Form.useForm();
  const [districtNames, setDistrictNames] = useState<string[]>([]);
  const [tradeAreas, setTradeAreas] = useState<string[]>([]);
  const [districtRows, setDistrictRows] = useState<DistrictStats[]>([]);

  const loadDistricts = useCallback(async () => {
    try {
      const rows = await getDistricts();
      setDistrictRows(rows);
      const unique = [...new Set(rows.map(d => d.district).filter(Boolean))] as string[];
      setDistrictNames(unique.sort((a, b) => a.localeCompare(b, 'zh-CN')));
    } catch (error) {
      console.error('获取行政区/商圈失败:', error);
      message.warning('行政区列表加载失败，仍可仅用价格与出行目的推荐');
    }
  }, []);

  useEffect(() => {
    loadDistricts();
  }, [loadDistricts]);

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const handleDistrictChange = (district: string | undefined) => {
    if (!district) {
      setTradeAreas([]);
      form.setFieldsValue({ trade_area: undefined });
      return;
    }
    const areas = [
      ...new Set(
        districtRows.filter(d => d.district === district && d.trade_area).map(d => d.trade_area as string)
      ),
    ].sort((a, b) => a.localeCompare(b, 'zh-CN'));
    setTradeAreas(areas);
    form.setFieldsValue({ trade_area: undefined });
  };

  const fetchRecommendations = async (params?: Record<string, unknown>) => {
    try {
      setLoading(true);
      const p = params ?? form.getFieldsValue();
      const priceRange = p?.priceRange as [number, number] | undefined;
      const mustHave = p?.mustHave as string[] | undefined;
      const bedroom = p?.bedroom_count as number | undefined;
      const cap = p?.capacity as number | undefined;
      const topK = (p?.top_k as number) ?? 10;
      const districtVal = p?.district as string | undefined;
      const tradeAreaVal = districtVal ? (p?.trade_area as string | undefined) : undefined;

      const requestParams: RecommendParams = {
        district: districtVal,
        trade_area: tradeAreaVal,
        price_min: priceRange?.[0],
        price_max: priceRange?.[1],
        travel_purpose: p?.target as string | undefined,
        facilities: mustHave?.length ? mustHave.join(',') : undefined,
        bedroom_count: bedroom,
        capacity: cap,
        top_k: topK,
      };

      const response = await getRecommendations(requestParams);
      setData(response?.recommendations || []);
    } catch (error) {
      console.error('获取推荐失败:', error);
      message.error('获取推荐失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const onFinish = (values: Record<string, unknown>) => {
    fetchRecommendations(values);
  };

  const sectionLabel = (text: string) => (
    <span className="mb-3 block text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-muted)]">{text}</span>
  );

  return (
    <div className="recommendation-shell space-y-10 pb-10 sm:space-y-12">
      <PageHeader
        title="个性化推荐"
        subtitle="按出行目的、预算与设施偏好，为您匹配高相关度房源；结果含匹配度与简要理由，便于快速决策。"
        category="Recommendation"
      />

      <ZenSection title="偏好与条件" accent="jade">
        <ZenPanel accent="jade" title="推荐参数" titleCaps={false} extra={<CompassOutlined className="text-[var(--jade)] opacity-70" />}>
          <Form
            className="recommendation-form"
            form={form}
            layout="vertical"
            onFinish={onFinish}
            initialValues={{
              priceRange: [150, 400],
              target: 'couple',
              mustHave: [],
              top_k: 10,
            }}
          >
            {sectionLabel('地理位置')}
            <Row gutter={[16, 0]}>
              <Col xs={24} sm={12} lg={8}>
                <Form.Item name="district" label={<span className="text-[var(--ink-light)]">行政区</span>}>
                  <Select
                    allowClear
                    showSearch
                    optionFilterProp="children"
                    placeholder="不限"
                    size="large"
                    className="w-full"
                    onChange={handleDistrictChange}
                  >
                    {districtNames.map(d => (
                      <Option key={d} value={d}>
                        {d}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} lg={8}>
                <Form.Item
                  name="trade_area"
                  label={<span className="text-[var(--ink-light)]">商圈</span>}
                  tooltip="在行政区下进一步缩小范围；可不选"
                >
                  <Select
                    allowClear
                    showSearch
                    optionFilterProp="children"
                    placeholder={tradeAreas.length ? '不限' : '请先选择行政区'}
                    size="large"
                    className="w-full"
                    disabled={!tradeAreas.length}
                  >
                    {tradeAreas.map(ta => (
                      <Option key={ta} value={ta}>
                        {ta}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            <Divider className="!my-5 !border-[var(--paper-warm)]" />

            {sectionLabel('行程与房源')}
            <Row gutter={[16, 0]}>
              <Col xs={24} sm={12} lg={8}>
                <Form.Item
                  name="target"
                  label={<span className="text-[var(--ink-light)]">出行目的</span>}
                  rules={[{ required: true, message: '请选择出行目的' }]}
                >
                  <Select className="w-full" size="large">
                    <Option value="couple">情侣出游</Option>
                    <Option value="family">家庭亲子</Option>
                    <Option value="business">商务差旅</Option>
                    <Option value="exam">学生考研</Option>
                    <Option value="team_party">团建聚会</Option>
                    <Option value="medical">医疗陪护</Option>
                    <Option value="pet_friendly">宠物友好</Option>
                    <Option value="long_stay">长租</Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} lg={8}>
                <Form.Item name="bedroom_count" label={<span className="text-[var(--ink-light)]">卧室数量（至少）</span>}>
                  <Select allowClear placeholder="不限" size="large" className="w-full">
                    <Option value={1}>至少 1 室</Option>
                    <Option value={2}>至少 2 室</Option>
                    <Option value={3}>至少 3 室</Option>
                    <Option value={4}>至少 4 室</Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} lg={8}>
                <Form.Item name="capacity" label={<span className="text-[var(--ink-light)]">可住人数（至少）</span>}>
                  <Select allowClear placeholder="不限" size="large" className="w-full">
                    {[2, 3, 4, 5, 6, 8].map(n => (
                      <Option key={n} value={n}>
                        至少 {n} 人
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={[16, 16]} align="middle">
              <Col xs={24} lg={16}>
                <Form.Item
                  name="priceRange"
                  label={<span className="text-[var(--ink-light)]">每晚预算（元）</span>}
                  className="recommendation-price-slider !mb-2"
                >
                  <Slider range min={50} max={1000} step={50} tooltip={{ formatter: v => `¥${v}` }} />
                </Form.Item>
              </Col>
              <Col xs={24} lg={8}>
                <Form.Item name="top_k" label={<span className="text-[var(--ink-light)]">返回条数</span>}>
                  <Select size="large" className="w-full">
                    <Option value={10}>10 条</Option>
                    <Option value={20}>20 条</Option>
                    <Option value={30}>30 条</Option>
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            <Form.Item name="mustHave" label={<span className="text-[var(--ink-light)]">核心设施（必选偏好）</span>} className="!mb-6">
              <Select
                mode="multiple"
                placeholder="可选，多选"
                className="w-full"
                maxTagCount={isMobile ? 2 : 'responsive'}
                size="large"
                optionFilterProp="children"
              >
                {FACILITY_OPTIONS.map(f => (
                  <Option key={f.value} value={f.value}>
                    {f.label}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item className="!mb-0">
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                size="large"
                icon={<BulbOutlined />}
                className="!h-12 !border-none !bg-[var(--ink-black)] !px-8 hover:!bg-[var(--ink-dark)]"
                style={{ fontFamily: 'var(--font-serif)', letterSpacing: '0.15em' }}
              >
                生成推荐
              </Button>
            </Form.Item>
          </Form>
        </ZenPanel>
      </ZenSection>

      <ZenSection title="为您甄选" accent="gold">
        <ZenPanel
          accent="ink"
          title="推荐结果"
          titleCaps={false}
          extra={
            !loading && data.length > 0 ? (
              <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-muted)]">
                共 {data.length} 套
              </Tag>
            ) : null
          }
        >
          <Spin spinning={loading} tip="智能匹配中…">
            {data.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                className="py-14"
                description={
                  <div className="text-[var(--ink-muted)]">
                    <p className="m-0 text-[var(--ink-medium)]">暂无推荐结果</p>
                    <p className="mt-2 text-sm">可放宽行政区、商圈或价格区间后再试</p>
                  </div>
                }
              />
            ) : (
              <List
                grid={{ gutter: [18, 22], xs: 1, sm: 2, md: 2, lg: 3, xl: 4 }}
                dataSource={data}
                renderItem={item => {
                  const pct = Math.round(item.match_score * 100);
                  return (
                    <List.Item className="!mb-0 !border-none !p-0">
                      <div className="group relative h-full">
                        <div className="flex h-full flex-col overflow-hidden rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] shadow-[var(--shadow-soft)] transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-medium)]">
                          <Link to={`/listing/${item.id}`} className="relative block aspect-[4/3] overflow-hidden bg-[var(--paper-cream)] no-underline">
                            <img
                              alt=""
                              src={
                                item.cover_image?.trim()
                                  ? item.cover_image
                                  : `https://picsum.photos/seed/${item.id}/480/360`
                              }
                              className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                            />
                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-black/10" />
                            <div className="absolute left-3 top-3 flex items-center gap-2">
                              <span
                                className="rounded-full border border-white/40 bg-black/35 px-2.5 py-1 text-[11px] font-semibold tabular-nums text-white backdrop-blur-sm"
                                style={{ fontFamily: 'var(--font-serif)' }}
                              >
                                匹配 {pct}%
                              </span>
                            </div>
                          </Link>
                          <div className="flex flex-1 flex-col p-4">
                            <Link
                              to={`/listing/${item.id}`}
                              className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-[var(--ink-black)] no-underline transition-colors group-hover:text-[var(--ochre)]"
                              style={{ fontFamily: 'var(--font-serif)' }}
                            >
                              {item.title}
                            </Link>
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--ink-muted)]">
                              <EnvironmentOutlined className="text-[var(--gold)]" />
                              <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-light)]">
                                {item.district}
                              </Tag>
                            </div>
                            {(item.reason || item.rating != null) && (
                              <p className="recommendation-reason mt-3 border-l-2 border-[var(--gold)]/70 pl-3 text-xs leading-relaxed text-[var(--ink-medium)]">
                                {item.reason?.trim() || `综合评分 ${item.rating} 分`}
                              </p>
                            )}
                            <div className="mt-auto flex flex-1 flex-col justify-end border-t border-[var(--paper-warm)] pt-3">
                              <div className="flex items-end justify-between gap-2">
                                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                                  <Rate disabled value={item.rating} allowHalf className="!text-[13px] text-[var(--gold)]" />
                                  <span className="text-[11px] text-[var(--ink-muted)]">{item.rating} 分</span>
                                </div>
                                <div className="shrink-0 text-right">
                                  <div
                                    className="text-xl font-semibold text-[var(--ochre)]"
                                    style={{ fontFamily: 'var(--font-serif)' }}
                                  >
                                    ¥{item.price}
                                  </div>
                                  <div className="flex items-center justify-end gap-1 text-[11px] text-[var(--ink-muted)]">
                                    <HomeOutlined className="text-[var(--gold)]" />
                                    <span>/ 晚</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </List.Item>
                  );
                }}
              />
            )}
          </Spin>
        </ZenPanel>
      </ZenSection>
    </div>
  );
};

export default Recommendation;
