import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Typography, Tag, Spin, Empty, message, Select, Alert, Tooltip } from 'antd';
import { Link } from 'react-router-dom';
import { EnvironmentOutlined, AimOutlined } from '@ant-design/icons';
import { PageHeader } from '../components/common';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import { getCompetitorAnalysis, getMyListings } from '../services/myListingsApi';
import type { CompetitorAnalysis, MyListing } from '../services/myListingsApi';

const { Text } = Typography;
const { Option } = Select;

const parseCompetitorTags = (value: unknown): string[] => {
  if (!value) return [];

  const extractText = (tag: any): string | null => {
    if (typeof tag === 'string') return tag.trim();
    if (!tag || typeof tag !== 'object') return null;
    if (typeof tag.text === 'string' && tag.text.trim()) return tag.text.trim();
    if (typeof tag.tagText === 'string' && tag.tagText.trim()) return tag.tagText.trim();
    if (tag.tagText && typeof tag.tagText === 'object' && typeof tag.tagText.text === 'string') {
      return tag.tagText.text.trim();
    }
    return null;
  };

  if (Array.isArray(value)) {
    return value.map(extractText).filter((tag): tag is string => Boolean(tag)).slice(0, 3);
  }

  if (typeof value === 'string') {
    const raw = value.trim();
    if (!raw) return [];

    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.map(extractText).filter((tag): tag is string => Boolean(tag)).slice(0, 3);
      }
      const single = extractText(parsed);
      return single ? [single] : [];
    } catch {
      return raw.split(',').map(tag => tag.trim()).filter(Boolean).slice(0, 3);
    }
  }

  const single = extractText(value);
  return single ? [single] : [];
};

const Competitor: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [listingsLoading, setListingsLoading] = useState(false);
  const [myListings, setMyListings] = useState<MyListing[]>([]);
  const [selectedListing, setSelectedListing] = useState<MyListing | null>(null);
  const [competitorAnalysis, setCompetitorAnalysis] = useState<CompetitorAnalysis | null>(null);

  useEffect(() => {
    fetchMyListings();
  }, []);

  const fetchMyListings = async () => {
    try {
      setListingsLoading(true);
      const listings = await getMyListings();
      setMyListings(listings);
      if (listings.length > 0 && !selectedListing) {
        handleSelectListing(listings[0].id);
      }
    } catch (error) {
      console.error('获取房源列表失败:', error);
      message.error('获取房源列表失败');
    } finally {
      setListingsLoading(false);
    }
  };

  const handleSelectListing = async (listingId: number) => {
    const listing = myListings.find(l => l.id === listingId);
    if (!listing) return;

    setSelectedListing(listing);
    setLoading(true);

    try {
      const analysis = await getCompetitorAnalysis(listingId);
      setCompetitorAnalysis(analysis);
    } catch (error) {
      console.error('获取竞品分析失败:', error);
      message.error('获取竞品分析失败');
      setCompetitorAnalysis(null);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '房源名称',
      dataIndex: 'title',
      key: 'title',
      render: (text: string, record: { unit_id: string }) => (
        <Link to={`/listing/${record.unit_id}`} className="font-medium text-[var(--ink-black)] transition-colors hover:text-[var(--ochre)]">
          {text}
        </Link>
      ),
    },
    {
      title: '距离',
      dataIndex: 'distance_km',
      key: 'distance_km',
      render: (d: number | null | undefined) =>
        d != null && d > 0 ? (
          <span className="text-[var(--jade)]">{d} km</span>
        ) : (
          <span className="text-xs text-[var(--ink-muted)]">—</span>
        ),
    },
    {
      title: '日均价',
      dataIndex: 'final_price',
      key: 'final_price',
      render: (p: number) => (
        <span className="font-medium text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
          ¥{p}
        </span>
      ),
    },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      render: (s: number) => <span className="text-[var(--gold)]">★ {s}</span>,
    },
    {
      title: '收藏数',
      dataIndex: 'favorite_count',
      key: 'favorite_count',
      render: (o: number) => <span className="text-[var(--ink-light)]">{o}</span>,
    },
    {
      title: '相似度',
      dataIndex: 'similarity_score',
      key: 'similarity_score',
      render: (s: number) => (
        <Tag className="!m-0 !border-[rgba(196,92,62,0.35)] !bg-[var(--ochre-pale)] !text-[var(--ochre)]">{Math.round(s)}%</Tag>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tag_list',
      key: 'tag_list',
      render: (tagList: string[] | undefined, record: any) => {
        const raw =
          Array.isArray(record.tag_list) && record.tag_list.length > 0
            ? record.tag_list
            : tagList && tagList.length > 0
              ? tagList
              : record.house_tags;
        const tags = parseCompetitorTags(raw);

        if (tags.length === 0) {
          return <span className="text-xs text-[var(--ink-muted)]">—</span>;
        }

        return (
          <div className="flex flex-wrap gap-1">
            {tags.slice(0, 3).map((t: string, index: number) => (
              <Tag key={`${t}-${index}`} className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-xs !text-[var(--ink-light)]">
                {t}
              </Tag>
            ))}
            {tags.length > 3 && (
              <Tooltip title={tags.slice(3).join(', ')}>
                <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-gray)]/40 !text-xs">+{tags.length - 3}</Tag>
              </Tooltip>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="competitor-shell space-y-10 pb-10 sm:space-y-12">
      <PageHeader
        title="竞品情报分析"
        subtitle="同行政区平台房源为竞品池；若「我的房源」与库内房源均有经纬度，则按直线距离取最近若干条，并展示公里数"
        category="Competitor"
      />

      <ZenSection title="规则与范围" accent="gold">
        <div className="paper-texture rounded-xl border border-[var(--paper-warm)] px-4 py-3 shadow-[var(--shadow-soft)] sm:px-5 sm:py-4">
          <Alert
            type="info"
            showIcon
            icon={<AimOutlined className="text-[var(--gold)]" />}
            message={<span className="font-medium text-[var(--ink-black)]">竞品选取说明</span>}
            description={
              competitorAnalysis?.market_position?.selection_note ??
              '加载分析结果后将显示具体说明。平台房源坐标可通过后端脚本从 tujia_calendar_data.json 回填至 listings 表。'
            }
            className="!border-transparent !bg-transparent !p-0"
          />
        </div>
      </ZenSection>

      <ZenSection title="分析对象" accent="jade">
        <ZenPanel accent="jade" title="选择我的房源" extra={myListings.length > 0 ? <Tag className="!m-0 !border-[var(--paper-warm)] !text-[var(--ink-muted)]">{myListings.length} 套</Tag> : null}>
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} md={16} lg={12}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
                <Text className="shrink-0 text-sm text-[var(--ink-light)]">选择要分析的房源</Text>
                <Select
                  className="w-full min-w-0 sm:!max-w-md"
                  placeholder="请选择房源"
                  loading={listingsLoading}
                  value={selectedListing?.id}
                  onChange={handleSelectListing}
                  disabled={myListings.length === 0}
                  size="large"
                >
                  {myListings.map(listing => (
                    <Option key={listing.id} value={listing.id}>
                      <div className="flex items-center justify-between gap-4">
                        <span className="truncate">{listing.title}</span>
                        <span className="shrink-0 text-xs text-[var(--ink-muted)]">¥{listing.current_price}</span>
                      </div>
                    </Option>
                  ))}
                </Select>
              </div>
            </Col>
            <Col xs={24} md={8} lg={12}>
              {myListings.length === 0 && (
                <Text type="secondary" className="text-sm text-[var(--ink-muted)]">
                  暂无房源，请先在「我的房源」中添加
                </Text>
              )}
            </Col>
          </Row>
        </ZenPanel>
      </ZenSection>

      {selectedListing && (
        <ZenSection title="标的概览" accent="ochre">
          <div className="overflow-hidden rounded-xl border border-[var(--paper-warm)] bg-gradient-to-br from-[var(--ink-black)] to-[var(--ink-dark)] shadow-[var(--shadow-medium)]">
            <div className="border-l-[3px] border-[var(--ochre)] px-5 py-6 sm:px-8 sm:py-7">
              <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 flex-1 text-white">
                  <div className="mb-1 text-xs tracking-wider text-white/50">正在分析</div>
                  <div className="text-xl font-semibold leading-snug sm:text-2xl" style={{ fontFamily: 'var(--font-serif)' }}>
                    {selectedListing.title}
                  </div>
                  <div className="mt-2 text-sm text-[var(--gold)]">
                    {selectedListing.district} · {selectedListing.bedroom_count} 室 {selectedListing.bed_count} 床 · 当前定价 ¥{selectedListing.current_price}
                    /晚
                  </div>
                </div>
                {competitorAnalysis?.market_position && (
                  <div className="flex flex-wrap gap-6 sm:gap-10 lg:shrink-0 lg:text-right">
                    <div>
                      <div className="text-2xl font-semibold text-[var(--ochre)]" style={{ fontFamily: 'var(--font-serif)' }}>
                        {competitorAnalysis.market_position.my_price_rank}
                      </div>
                      <div className="text-xs text-white/50">价格排名</div>
                    </div>
                    <div>
                      <div className="text-2xl font-semibold text-[var(--gold)]" style={{ fontFamily: 'var(--font-serif)' }}>
                        {competitorAnalysis.market_position.price_percentile?.toFixed(1) ?? '—'}%
                      </div>
                      <div className="text-xs text-white/50">价格分位</div>
                    </div>
                    <div>
                      <div className="text-2xl font-semibold text-[var(--jade)]" style={{ fontFamily: 'var(--font-serif)' }}>
                        ¥{competitorAnalysis.market_position.avg_price?.toFixed(0) ?? '—'}
                      </div>
                      <div className="text-xs text-white/50">商圈均价</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </ZenSection>
      )}

      <ZenSection title="竞品监控" accent="ink">
        <ZenPanel
          accent="ink"
          title="周边竞品"
          extra={
            <div className="flex flex-wrap items-center gap-2">
              <Tooltip
                overlayStyle={{ maxWidth: 360 }}
                title={
                  competitorAnalysis?.market_position?.selection_note?.trim()
                    ? competitorAnalysis.market_position.selection_note
                    : '加载分析后显示说明：同行政区为池；若「我的房源」与同区平台房源均有有效经纬度，则按球面直线距离取最近若干条并展示公里数。'
                }
              >
                <EnvironmentOutlined className="text-[var(--jade)]" />
              </Tooltip>
              {competitorAnalysis?.competitors && competitorAnalysis.competitors.length > 0 && (
                <Tag className="!m-0 !border-[rgba(196,92,62,0.35)] !bg-[var(--ochre-pale)] !text-[var(--ochre)]">
                  共 {competitorAnalysis.competitors.length} 个竞品
                </Tag>
              )}
            </div>
          }
        >
          {loading ? (
            <div className="flex h-52 items-center justify-center">
              <Spin size="large" tip="加载竞品数据..." />
            </div>
          ) : competitorAnalysis?.competitors && competitorAnalysis.competitors.length > 0 ? (
            <div className="-mx-1 overflow-x-auto">
              <Table
                columns={columns}
                dataSource={competitorAnalysis.competitors}
                pagination={false}
                className="zen-table min-w-[900px]"
                rowKey="unit_id"
              />
            </div>
          ) : selectedListing ? (
            <Empty description="暂无竞品数据" className="py-8" />
          ) : (
            <Empty description="请先选择一个房源" className="py-8" />
          )}
        </ZenPanel>
      </ZenSection>
    </div>
  );
};

export default Competitor;
