import { useState, useEffect, useMemo } from 'react';
import { motion } from 'motion/react';
import { Link, useSearchParams } from 'react-router-dom';
import * as echarts from 'echarts';
import {
  SwapOutlined,
  TrophyOutlined,
  BarChartOutlined,
  EyeOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
  HeartOutlined,
} from '@ant-design/icons';
import {
  Button,
  Row,
  Col,
  Select,
  Table,
  Tag,
  Alert,
  Empty,
  Spin,
  message,
  Collapse,
} from 'antd';
import ReactECharts from 'echarts-for-react';
import PageHeader from '../components/common/PageHeader';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import {
  compareListings,
  ComparisonResult,
  CompareListingResponse,
} from '../services/comparisonApi';
import { getListingDetail, ListingDetail } from '../services/listingsApi';
import { getFavorites } from '../services/favoritesApi';

const { Option } = Select;
const { Panel } = Collapse;

/** 雷达系列色：赭石 / 竹青 / 金 / 墨 / 浅赭 */
const RADAR_SERIES_STYLES = [
  { line: '#c45c3e', area: new echarts.graphic.RadialGradient(0.5, 0.5, 0.8, [
      { offset: 0, color: 'rgba(196, 92, 62, 0.35)' },
      { offset: 1, color: 'rgba(196, 92, 62, 0.06)' },
    ]) },
  { line: '#5a8a6e', area: new echarts.graphic.RadialGradient(0.5, 0.5, 0.8, [
      { offset: 0, color: 'rgba(90, 138, 110, 0.32)' },
      { offset: 1, color: 'rgba(90, 138, 110, 0.06)' },
    ]) },
  { line: '#b8956e', area: new echarts.graphic.RadialGradient(0.5, 0.5, 0.8, [
      { offset: 0, color: 'rgba(184, 149, 110, 0.3)' },
      { offset: 1, color: 'rgba(184, 149, 110, 0.06)' },
    ]) },
  { line: '#4a4a4a', area: new echarts.graphic.RadialGradient(0.5, 0.5, 0.8, [
      { offset: 0, color: 'rgba(74, 74, 74, 0.2)' },
      { offset: 1, color: 'rgba(74, 74, 74, 0.04)' },
    ]) },
  { line: '#d97b5d', area: new echarts.graphic.RadialGradient(0.5, 0.5, 0.8, [
      { offset: 0, color: 'rgba(217, 123, 93, 0.28)' },
      { offset: 1, color: 'rgba(217, 123, 93, 0.05)' },
    ]) },
];

const fadeIn = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] as const },
};

export default function Comparison() {
  const [favoriteListings, setFavoriteListings] = useState<ListingDetail[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);

  const [searchParams] = useSearchParams();

  useEffect(() => {
    void fetchFavoriteListings();
  }, []);

  /** 收藏加载完成后：按 URL ?ids= 预选，并剔除非收藏 id */
  useEffect(() => {
    if (dataLoading) return;
    const allowed = new Set(favoriteListings.map((l) => l.unit_id));
    const idsParam = searchParams.get('ids');
    const fromUrl = idsParam
      ? idsParam.split(',').map((s) => s.trim()).filter(Boolean)
      : null;

    if (fromUrl && fromUrl.length > 0) {
      if (favoriteListings.length === 0) {
        setSelectedIds([]);
        if (fromUrl.length > 0) {
          message.info('暂无收藏房源，请先在列表或详情页加入收藏后再对比');
        }
        return;
      }
      const valid = fromUrl.filter((id) => allowed.has(id));
      const invalid = fromUrl.filter((id) => !allowed.has(id));
      if (invalid.length > 0) {
        message.warning('部分链接中的房源不在您的收藏中，已忽略');
      }
      setSelectedIds(valid);
      return;
    }

    setSelectedIds((prev) => prev.filter((id) => allowed.has(id)));
  }, [searchParams, dataLoading, favoriteListings]);

  const fetchFavoriteListings = async () => {
    setDataLoading(true);
    try {
      const favs = await getFavorites();
      if (!Array.isArray(favs) || favs.length === 0) {
        setFavoriteListings([]);
        return;
      }
      const details = await Promise.all(
        favs.map(async (f) => {
          try {
            return await getListingDetail(f.unit_id);
          } catch {
            return null;
          }
        })
      );
      setFavoriteListings(details.filter((d): d is ListingDetail => d != null));
    } catch (e) {
      console.error(e);
      message.error('加载收藏房源失败');
      setFavoriteListings([]);
    } finally {
      setDataLoading(false);
    }
  };

  const handleCompare = async () => {
    if (selectedIds.length < 2) {
      message.warning('请至少选择 2 套收藏房源进行对比');
      return;
    }
    if (selectedIds.length > 5) {
      message.warning('最多对比 5 套房源');
      return;
    }

    setLoading(true);
    try {
      const result = await compareListings({
        unit_ids: selectedIds,
        comparison_type: 'full',
      });

      if (result.error) {
        message.error(result.error);
        return;
      }

      setComparisonResult(result);
    } catch (error: unknown) {
      console.error('对比失败:', error);
      const err = error as { response?: { data?: { detail?: string } }; message?: string };
      const errorMsg = err?.response?.data?.detail || err?.message || '对比失败，请重试';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleAddSelection = (unitId: string) => {
    const allowed = favoriteListings.some((l) => l.unit_id === unitId);
    if (!allowed) {
      message.warning('只能从已收藏的房源中选择');
      return;
    }
    if (selectedIds.includes(unitId)) {
      message.info('该房源已在对比列表中');
      return;
    }
    if (selectedIds.length >= 5) {
      message.warning('最多只能选择 5 套');
      return;
    }
    setSelectedIds([...selectedIds, unitId]);
  };

  const handleRemoveSelection = (unitId: string) => {
    setSelectedIds(selectedIds.filter((id) => id !== unitId));
  };

  const radarOption = useMemo(() => {
    if (!comparisonResult) return {};
    const { radar_chart } = comparisonResult;
    const textStyle = {
      color: 'var(--ink-medium)',
      fontFamily: 'var(--font-sans)',
      fontSize: 11,
    };
    return {
      backgroundColor: 'transparent',
      title: {
        text: '多维度相对得分',
        left: 'center',
        top: 8,
        textStyle: {
          color: 'var(--ink-black)',
          fontSize: 14,
          fontWeight: 600,
          fontFamily: 'var(--font-serif)',
        },
      },
      tooltip: { trigger: 'item' as const },
      legend: {
        data: radar_chart.datasets.map((d) => d.name),
        bottom: 4,
        textStyle: { ...textStyle, fontSize: 11 },
        itemGap: 16,
      },
      radar: {
        center: ['50%', '52%'],
        radius: '58%',
        axisName: { color: 'var(--ink-muted)', fontSize: 11 },
        splitLine: { lineStyle: { color: 'var(--paper-warm)' } },
        splitArea: {
          show: true,
          areaStyle: {
            color: ['rgba(245, 242, 237, 0.5)', 'rgba(250, 248, 245, 0.35)'],
          },
        },
        axisLine: { lineStyle: { color: 'var(--paper-gray)' } },
        indicator: radar_chart.dimensions.map((dim) => ({
          name: dim,
          max: 100,
        })),
      },
      series: [
        {
          type: 'radar' as const,
          data: radar_chart.datasets.map((dataset, i) => {
            const style = RADAR_SERIES_STYLES[i % RADAR_SERIES_STYLES.length];
            return {
              value: dataset.values,
              name: dataset.name,
              symbol: 'circle',
              symbolSize: 5,
              lineStyle: { width: 2, color: style.line },
              itemStyle: { color: style.line },
              areaStyle: { color: style.area },
            };
          }),
        },
      ],
    };
  }, [comparisonResult]);

  const comparisonColumns = useMemo(
    () => [
      {
        title: '房源',
        key: 'title',
        render: (_: unknown, record: CompareListingResponse) => (
          <div>
            <div className="font-medium text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
              {record.title}
            </div>
            <div className="text-xs text-[var(--ink-muted)]">{record.district}</div>
          </div>
        ),
      },
      {
        title: '价格',
        dataIndex: 'price',
        key: 'price',
        render: (price: number, record: CompareListingResponse) => (
          <div>
            <div className="text-lg font-semibold text-[var(--ochre)]" style={{ fontFamily: 'var(--font-serif)' }}>
              ¥{price}
            </div>
            <Tag className="!mt-1 !border-[var(--paper-warm)] !bg-[var(--jade-pale)] !text-[var(--jade)]">
              综合价值 {record.value_score}
            </Tag>
          </div>
        ),
      },
      {
        title: '评分',
        dataIndex: 'rating',
        key: 'rating',
        render: (rating: number) => (
          <div className="flex items-center gap-1 text-[var(--ink-dark)]">
            <span className="text-[var(--gold)]">★</span>
            <span className="font-medium">{rating}</span>
          </div>
        ),
      },
      {
        title: '面积',
        dataIndex: 'area',
        key: 'area',
        render: (area: number | null) => (
          <span className="text-[var(--ink-medium)]">{area ? `${area}㎡` : '—'}</span>
        ),
      },
      {
        title: '卧室 / 卫',
        key: 'rooms',
        render: (_: unknown, record: CompareListingResponse) => (
          <span className="text-[var(--ink-medium)]">
            {record.bedrooms} 室 / {record.bathrooms} 卫
          </span>
        ),
      },
      {
        title: '设施',
        dataIndex: 'facilities',
        key: 'facilities',
        render: (facilities: string[]) => (
          <div className="flex flex-wrap gap-1">
            {facilities.slice(0, 3).map((f, i) => (
              <Tag key={i} className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-medium)]">
                {f}
              </Tag>
            ))}
            {facilities.length > 3 && (
              <Tag className="!m-0 !border-[var(--paper-warm)] !text-[var(--ink-muted)]">
                +{facilities.length - 3}
              </Tag>
            )}
          </div>
        ),
      },
      {
        title: '相对得分（本次集合）',
        key: 'scores',
        render: (_: unknown, record: CompareListingResponse) => (
          <div className="space-y-0.5 text-[11px] leading-relaxed text-[var(--ink-muted)]">
            <div>价格 {record.scores.price}</div>
            <div>位置 {record.scores.location}</div>
            <div>设施 {record.scores.facility}</div>
            <div>评分 {record.scores.rating}</div>
            <div>面积 {record.scores.size}</div>
          </div>
        ),
      },
    ],
    []
  );

  const tagExtra = (
    <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-muted)]">
      已选 {selectedIds.length} / 5
    </Tag>
  );

  return (
    <div className="comparison-page paper-texture min-h-[60vh] space-y-8 pb-10">
      <PageHeader
        title="房源对比"
        subtitle="仅从「我的收藏」中选 2～5 套进行相对对比；各维度在选中集合内归一化，综合价值指数为启发式参考"
        category="Comparison"
      />

      <Spin spinning={dataLoading}>
        <ZenSection title="从收藏中对比" accent="ochre">
          <Row gutter={[24, 24]} align="stretch">
            <Col xs={24} lg={9}>
              <motion.div {...fadeIn}>
                <ZenPanel accent="jade" title="选择对比房源" titleCaps={false} extra={tagExtra}>
                  {favoriteListings.length === 0 && !dataLoading ? (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        <span className="text-[var(--ink-muted)]">
                          还没有收藏房源，无法加入对比
                        </span>
                      }
                    >
                      <Link to="/listings">
                        <Button type="default" className="!border-[var(--paper-warm)]">
                          去浏览房源
                        </Button>
                      </Link>
                      <Link to="/favorites" className="ml-2">
                        <Button type="link" className="!text-[var(--jade)]">
                          打开我的收藏
                        </Button>
                      </Link>
                    </Empty>
                  ) : (
                    <>
                      {selectedIds.length > 0 && (
                        <div className="mb-4">
                          <div className="mb-2 text-xs uppercase tracking-[0.12em] text-[var(--ink-muted)]">
                            已选
                          </div>
                          <ul className="m-0 list-none space-y-2 p-0">
                            {selectedIds.map((id) => {
                              const listing = favoriteListings.find((l) => l.unit_id === id);
                              if (!listing) return null;
                              return (
                                <li
                                  key={id}
                                  className="flex items-center gap-2 rounded-lg border border-[var(--paper-warm)] bg-[var(--paper-cream)]/60 px-3 py-2"
                                >
                                  <div className="min-w-0 flex-1">
                                    <div
                                      className="truncate text-sm font-medium text-[var(--ink-black)]"
                                      style={{ fontFamily: 'var(--font-serif)' }}
                                    >
                                      {listing.title}
                                    </div>
                                    <div className="text-xs text-[var(--ochre)]">¥{listing.final_price}</div>
                                  </div>
                                  <Button
                                    type="text"
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                    aria-label={`移除 ${listing.title}`}
                                    onClick={() => handleRemoveSelection(id)}
                                  />
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}

                      <Select
                        placeholder="在收藏中搜索并添加…"
                        className="comparison-fav-select w-full"
                        size="large"
                        showSearch
                        allowClear
                        disabled={favoriteListings.length === 0}
                        filterOption={(input, option) => {
                          const lid = String(option?.value ?? '');
                          const listing = favoriteListings.find((l) => l.unit_id === lid);
                          if (!listing) return false;
                          const q = input.toLowerCase();
                          return (
                            listing.title.toLowerCase().includes(q) ||
                            listing.district.toLowerCase().includes(q)
                          );
                        }}
                        onSelect={(v) => handleAddSelection(String(v))}
                        value={undefined}
                        popupClassName="comparison-fav-dropdown"
                      >
                        {favoriteListings.map((listing) => (
                          <Option key={listing.unit_id} value={listing.unit_id} disabled={selectedIds.includes(listing.unit_id)}>
                            <div className="flex items-center justify-between gap-3 py-0.5">
                              <span className="min-w-0 flex-1 truncate text-[var(--ink-dark)]">
                                {listing.title}
                              </span>
                              <span className="shrink-0 text-xs text-[var(--ochre)]">¥{listing.final_price}</span>
                            </div>
                          </Option>
                        ))}
                      </Select>

                      <Button
                        type="primary"
                        block
                        size="large"
                        icon={<SwapOutlined />}
                        onClick={() => void handleCompare()}
                        loading={loading}
                        disabled={selectedIds.length < 2 || favoriteListings.length === 0}
                        className="mt-4 !h-11 !rounded-lg !font-medium"
                      >
                        开始对比
                      </Button>

                      {selectedIds.length < 2 && favoriteListings.length > 0 && (
                        <Alert
                          message="请至少选择 2 套收藏房源"
                          type="info"
                          showIcon
                          className="mt-4 !rounded-lg !border-[var(--paper-warm)] !bg-[var(--paper-cream)]"
                        />
                      )}

                      <p className="mt-4 mb-0 text-xs leading-relaxed text-[var(--ink-muted)]">
                        <HeartOutlined className="mr-1 text-[var(--ochre)]" aria-hidden />
                        对比池与收藏同步；若从收藏页勾选后跳转，链接中的 id 会自动载入（非收藏项会被忽略）。
                      </p>
                    </>
                  )}
                </ZenPanel>
              </motion.div>
            </Col>

            <Col xs={24} lg={15}>
              <motion.div {...fadeIn} transition={{ ...fadeIn.transition, delay: 0.06 }}>
                {comparisonResult ? (
                  <div className="space-y-6">
                    {comparisonResult.winner && (
                      <ZenPanel
                        accent="gold"
                        title="本次综合推荐"
                        titleCaps={false}
                        extra={
                          <Link to={`/listing/${comparisonResult.winner.unit_id}/detail`}>
                            <Button type="primary" size="middle" icon={<EyeOutlined />} className="!rounded-lg">
                              查看详情
                            </Button>
                          </Link>
                        }
                      >
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                          <div
                            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[var(--paper-warm)] bg-[var(--ochre-pale)]"
                            aria-hidden
                          >
                            <TrophyOutlined className="text-2xl text-[var(--gold)]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <h3
                              className="m-0 text-lg font-semibold text-[var(--ink-black)]"
                              style={{ fontFamily: 'var(--font-serif)' }}
                            >
                              {comparisonResult.winner.title}
                            </h3>
                            <div className="mt-1 text-sm text-[var(--ink-medium)]">
                              <span>{comparisonResult.winner.district}</span>
                              <span className="mx-2 text-[var(--paper-gray)]">·</span>
                              <span className="font-semibold text-[var(--jade)]">
                                综合价值 {comparisonResult.winner.value_score}
                              </span>
                            </div>
                            <p className="mt-2 mb-0 text-sm leading-relaxed text-[var(--ink-muted)]">
                              {comparisonResult.winner.reason}
                              {comparisonResult.winner.highlights &&
                                comparisonResult.winner.highlights.length > 0 && (
                                  <span className="mt-1 block text-[var(--ink-medium)]">
                                    {comparisonResult.winner.highlights.join('，')}
                                  </span>
                                )}
                            </p>
                          </div>
                        </div>
                      </ZenPanel>
                    )}

                    <ZenPanel accent="ink" title="多维度雷达图" titleCaps={false} extra={<BarChartOutlined className="text-[var(--ink-muted)]" />}>
                      <ReactECharts option={radarOption} style={{ height: 400 }} notMerge lazyUpdate />
                    </ZenPanel>

                    <ZenPanel accent="ink" title="详细对比" titleCaps={false}>
                      <Table<CompareListingResponse>
                        dataSource={comparisonResult.listings}
                        columns={comparisonColumns}
                        rowKey="unit_id"
                        pagination={false}
                        scroll={{ x: 'max-content' }}
                        size="middle"
                        className="comparison-table-wrap"
                      />
                    </ZenPanel>

                    {comparisonResult.scoring_methodology && (
                      <ZenPanel accent="jade" title="评分与基线说明" titleCaps={false}>
                        <Alert
                          message="对比基线"
                          description={`${comparisonResult.scoring_methodology.description}分数仅在本次选中集合内可比，不代表全市绝对排名。`}
                          type="info"
                          showIcon
                          className="mb-4 !rounded-lg !border-[var(--paper-warm)] !bg-[var(--paper-cream)]"
                        />
                        <Collapse
                          ghost
                          className="comparison-methodology-collapse !border-0 !bg-transparent"
                          items={[
                            {
                              key: '1',
                              label: (
                                <span className="flex items-center gap-2 text-sm text-[var(--ink-medium)]">
                                  <InfoCircleOutlined className="text-[var(--jade)]" />
                                  展开查看计算逻辑
                                </span>
                              ),
                              children: (
                                <div className="space-y-3 text-xs text-[var(--ink-muted)]">
                                  <Row gutter={[16, 12]}>
                                    <Col span={24} md={12}>
                                      <div className="font-medium text-[var(--ink-dark)]">价格优势分</div>
                                      <div>基线：本次集合内最低/最高价</div>
                                      <div>计算：100 − ((价 − 低价) / (高价 − 低价)) × 100</div>
                                    </Col>
                                    <Col span={24} md={12}>
                                      <div className="font-medium text-[var(--ink-dark)]">评分口碑分</div>
                                      <div>基线：集合内最低/最高评分</div>
                                      <div>计算：按区间线性映射到 0–100</div>
                                    </Col>
                                    <Col span={24} md={12}>
                                      <div className="font-medium text-[var(--ink-dark)]">空间与设施</div>
                                      <div>面积、设施数量在集合内归一化</div>
                                    </Col>
                                    <Col span={24} md={12}>
                                      <div className="font-medium text-[var(--ink-dark)]">综合价值指数</div>
                                      <div>启发式公式，侧重质价比与设施</div>
                                    </Col>
                                  </Row>
                                </div>
                              ),
                            },
                          ]}
                        />
                      </ZenPanel>
                    )}

                    <Row gutter={[16, 16]}>
                      <Col xs={24} sm={8}>
                        <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/50 px-4 py-3 shadow-[var(--shadow-soft)]">
                          <div className="text-xs uppercase tracking-[0.1em] text-[var(--ink-muted)]">价格区间</div>
                          <div className="mt-1 text-base font-semibold text-[var(--ochre)]" style={{ fontFamily: 'var(--font-serif)' }}>
                            ¥{comparisonResult.summary.price_range.min} — ¥{comparisonResult.summary.price_range.max}
                          </div>
                          <div className="text-xs text-[var(--ink-muted)]">均价 ¥{comparisonResult.summary.price_range.avg}</div>
                        </div>
                      </Col>
                      <Col xs={24} sm={8}>
                        <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/50 px-4 py-3 shadow-[var(--shadow-soft)]">
                          <div className="text-xs uppercase tracking-[0.1em] text-[var(--ink-muted)]">评分区间</div>
                          <div className="mt-1 text-base font-semibold text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
                            {comparisonResult.summary.rating_range.min} — {comparisonResult.summary.rating_range.max}
                          </div>
                          <div className="text-xs text-[var(--ink-muted)]">平均 {comparisonResult.summary.rating_range.avg}</div>
                        </div>
                      </Col>
                      <Col xs={24} sm={8}>
                        <div className="rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/50 px-4 py-3 shadow-[var(--shadow-soft)]">
                          <div className="text-xs uppercase tracking-[0.1em] text-[var(--ink-muted)]">面积区间</div>
                          <div className="mt-1 text-base font-semibold text-[var(--ink-dark)]" style={{ fontFamily: 'var(--font-serif)' }}>
                            {comparisonResult.summary.area_range.min} — {comparisonResult.summary.area_range.max} ㎡
                          </div>
                          <div className="text-xs text-[var(--ink-muted)]">平均 {comparisonResult.summary.area_range.avg} ㎡</div>
                        </div>
                      </Col>
                    </Row>
                  </div>
                ) : (
                  <ZenPanel
                    accent="ink"
                    title="对比结果"
                    titleCaps={false}
                    extra={
                      favoriteListings.length > 0 ? (
                        <span className="text-xs text-[var(--ink-muted)]">选择房源后点击「开始对比」</span>
                      ) : null
                    }
                  >
                    <div className="flex min-h-[320px] flex-col items-center justify-center py-8">
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description={
                          <span className="text-[var(--ink-muted)]">
                            {favoriteListings.length === 0
                              ? '收藏房源后将显示在此'
                              : '从左侧选择 2～5 套收藏房源后开始对比'}
                          </span>
                        }
                      />
                    </div>
                  </ZenPanel>
                )}
              </motion.div>
            </Col>
          </Row>
        </ZenSection>
      </Spin>
    </div>
  );
}
