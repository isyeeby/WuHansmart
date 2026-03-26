import React, { useState, useEffect } from 'react';
import { List, Tag, Button, Select, Form, Row, Col, Spin, Pagination, Empty, message } from 'antd';
import { HeartOutlined, HeartFilled, EnvironmentOutlined, HomeOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/common';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';

import { getListings, type ListingItem, type ListingsQueryParams } from '../services/listingsApi';
import { getDistricts, type DistrictStats } from '../services/analysisApi';
import { addFavorite, removeFavorite } from '../services/favoritesApi';

const { Option } = Select;

/** Select 的 value 须为可稳定比较的值；数组引用每次渲染不同会导致无法选中 */
const PRICE_RANGE_KEYS = ['0-100', '100-200', '200-300', '300-500', '500-1000'] as const;
type PriceRangeKey = (typeof PRICE_RANGE_KEYS)[number];

const PRICE_RANGE_MAP: Record<PriceRangeKey, [number, number]> = {
  '0-100': [0, 100],
  '100-200': [100, 200],
  '200-300': [200, 300],
  '300-500': [300, 500],
  '500-1000': [500, 1000],
};

function priceRangeFromFormValue(v: string | undefined): [number, number] | undefined {
  if (!v || !(v in PRICE_RANGE_MAP)) return undefined;
  return PRICE_RANGE_MAP[v as PriceRangeKey];
}

const Listings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [listings, setListings] = useState<ListingItem[]>([]);
  const [districts, setDistricts] = useState<DistrictStats[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [form] = Form.useForm();
  const [favorites, setFavorites] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchDistricts();
    fetchListings();
  }, []);

  const fetchDistricts = async () => {
    try {
      const data = await getDistricts();
      setDistricts(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('获取商圈数据失败:', error);
    }
  };

  const fetchListings = async (params?: ListingsQueryParams) => {
    try {
      setLoading(true);
      const queryParams: ListingsQueryParams = {
        page: currentPage,
        size: pageSize,
        ...params,
      };
      const response = await getListings(queryParams);
      setListings(response.items || []);
      setTotal(response.total || 0);
    } catch (error) {
      console.error('获取房源列表失败:', error);
      message.error('获取房源列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (values: any) => {
    const pr = priceRangeFromFormValue(values.priceRange);
    setCurrentPage(1);
    fetchListings({
      page: 1,
      size: pageSize,
      district: values.district,
      min_price: pr?.[0],
      max_price: pr?.[1],
      bedroom_count: values.bedroomCount,
      sort_by: values.sortBy,
    });
  };

  const handlePageChange = (page: number, size?: number) => {
    setCurrentPage(page);
    if (size) setPageSize(size);
    const values = form.getFieldsValue();
    const pr = priceRangeFromFormValue(values.priceRange);
    fetchListings({
      page,
      size: size || pageSize,
      district: values.district,
      min_price: pr?.[0],
      max_price: pr?.[1],
      bedroom_count: values.bedroomCount,
      sort_by: values.sortBy,
    });
  };

  const toggleFavorite = async (unitId: string, isFavorite: boolean) => {
    try {
      if (isFavorite) {
        await removeFavorite(unitId);
        setFavorites(prev => {
          const next = new Set(prev);
          next.delete(unitId);
          return next;
        });
        message.success('取消收藏成功');
      } else {
        await addFavorite(unitId);
        setFavorites(prev => {
          const next = new Set(prev);
          next.add(unitId);
          return next;
        });
        message.success('收藏成功');
      }
    } catch (error) {
      message.error('操作失败');
    }
  };

  const parseTags = (tags: any): string[] => {
    if (!tags) return [];

    const extractText = (t: any): string | null => {
      if (typeof t === 'string') return t;
      if (!t || typeof t !== 'object') return null;
      if (t.tagText && typeof t.tagText === 'object') {
        return t.tagText.text || null;
      }
      if (t.text && typeof t.text === 'string') {
        return t.text;
      }
      if (t.tagText && typeof t.tagText === 'string') {
        return t.tagText;
      }
      return null;
    };

    if (Array.isArray(tags)) {
      return tags.map(extractText).filter((t): t is string => Boolean(t)).slice(0, 3);
    }
    if (typeof tags === 'string') {
      try {
        const parsed = JSON.parse(tags);
        if (Array.isArray(parsed)) {
          return parsed.map(extractText).filter((t): t is string => Boolean(t)).slice(0, 3);
        }
        const text = extractText(parsed);
        return text ? [text] : [];
      } catch {
        return tags.split(',').filter(t => t.trim()).slice(0, 3);
      }
    }
    if (typeof tags === 'object') {
      const text = extractText(tags);
      return text ? [text] : [];
    }
    return [];
  };

  const uniqueDistricts = Array.from(new Set(districts.map(d => d.district)));

  return (
    <div className="listings-shell space-y-10 pb-10 sm:space-y-12">
      <PageHeader title="房源列表" subtitle="浏览武汉市民宿房源，支持多条件筛选与排序" category="Listings" />

      <ZenSection title="筛选条件" accent="jade">
        <ZenPanel accent="jade" title="筛选与排序">
          <Form form={form} layout="vertical" className="listings-filter-form" onFinish={handleSearch}>
            <Row gutter={[16, 8]}>
              <Col xs={24} sm={12} md={8} lg={5}>
                <Form.Item name="district" label={<span className="text-[var(--ink-light)]">行政区</span>} className="!mb-3">
                  <Select placeholder="全部" allowClear size="large" className="w-full">
                    {uniqueDistricts.map(district => (
                      <Option key={district} value={district}>
                        {district}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={8} lg={5}>
                <Form.Item name="bedroomCount" label={<span className="text-[var(--ink-light)]">卧室数</span>} className="!mb-3">
                  <Select placeholder="全部" allowClear size="large" className="w-full">
                    <Option value={1}>1 室</Option>
                    <Option value={2}>2 室</Option>
                    <Option value={3}>3 室</Option>
                    <Option value={4}>4 室及以上</Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={8} lg={6}>
                <Form.Item name="priceRange" label={<span className="text-[var(--ink-light)]">价格区间</span>} className="!mb-3">
                  <Select placeholder="全部" allowClear size="large" className="w-full">
                    <Option value="0-100">100 元以下</Option>
                    <Option value="100-200">100 — 200 元</Option>
                    <Option value="200-300">200 — 300 元</Option>
                    <Option value="300-500">300 — 500 元</Option>
                    <Option value="500-1000">500 元以上</Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={8} lg={5}>
                <Form.Item name="sortBy" label={<span className="text-[var(--ink-light)]">排序</span>} className="!mb-3">
                  <Select placeholder="默认" allowClear size="large" className="w-full">
                    <Option value="favorite_count">收藏数</Option>
                    <Option value="price_asc">价格从低到高</Option>
                    <Option value="price_desc">价格从高到低</Option>
                    <Option value="rating">评分</Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={8} lg={3} className="flex items-end">
                <Form.Item label=" " className="!mb-3 w-full" colon={false}>
                  <Button type="primary" htmlType="submit" size="large" block className="!h-10 !border-none !bg-[var(--ink-black)] hover:!bg-[var(--ink-dark)]">
                    搜索
                  </Button>
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </ZenPanel>
      </ZenSection>

      <ZenSection title="房源结果" accent="ink">
        <ZenPanel
          accent="ink"
          title="全部房源"
          extra={
            !loading && total > 0 ? (
              <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-muted)]">共 {total} 套</Tag>
            ) : null
          }
        >
          <Spin spinning={loading} tip="加载中...">
            {listings.length > 0 ? (
              <>
                <List
                  className="listings-result-list"
                  grid={{ gutter: [16, 22], xs: 1, sm: 2, md: 3, lg: 4, xl: 4, xxl: 4 }}
                  dataSource={listings}
                  renderItem={item => {
                    const isFavorite = favorites.has(item.unit_id);
                    const tags = parseTags(item.house_tags);
                    return (
                      <List.Item className="!mb-0 !h-full !border-none !p-0">
                        <div className="group relative flex h-full min-h-0 w-full flex-col">
                          <Link
                            to={`/listing/${item.unit_id}`}
                            className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] no-underline shadow-[var(--shadow-soft)] transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-medium)]"
                          >
                            <div className="relative aspect-[4/3] overflow-hidden bg-[var(--paper-cream)]">
                              <img
                                alt=""
                                src={item.cover_image || `https://picsum.photos/seed/${item.unit_id}/400/300`}
                                className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                              />
                              <Button
                                type="text"
                                size="large"
                                aria-label={isFavorite ? '取消收藏' : '收藏'}
                                icon={isFavorite ? <HeartFilled className="text-[var(--ochre)]" /> : <HeartOutlined />}
                                className="absolute right-2 top-2 !flex !h-10 !w-10 !items-center justify-center !rounded-full !border !border-[var(--paper-warm)] !bg-white/90 !shadow-sm backdrop-blur-sm hover:!bg-white"
                                onClick={e => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  toggleFavorite(item.unit_id, isFavorite);
                                }}
                              />
                              {item.discount_rate > 0 && (
                                <Tag className="absolute left-2 top-2 !m-0 !border-none !bg-[var(--ochre)] !text-white">
                                  省 {Math.round(item.discount_rate * 100)}%
                                </Tag>
                              )}
                            </div>
                            <div className="flex min-h-0 flex-1 flex-col p-4">
                              <div className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-[var(--ink-black)] group-hover:text-[var(--ochre)]">
                                {item.title}
                              </div>
                              <div className="mt-2 flex shrink-0 items-center gap-1 text-xs text-[var(--ink-muted)]">
                                <EnvironmentOutlined className="shrink-0 text-[var(--gold)]" />
                                <span className="truncate">
                                  {item.district} · {item.trade_area}
                                </span>
                              </div>
                              {/* 固定两行标签区高度，避免同排卡片因换行参差不齐 */}
                              <div
                                className="listing-card-tags mt-2 flex h-[3.625rem] flex-wrap content-start gap-1.5 overflow-hidden"
                                aria-label={tags.length ? '房源标签' : undefined}
                              >
                                {tags.length > 0 ? (
                                  tags.map((tag, idx) => (
                                    <Tag
                                      key={idx}
                                      className="!m-0 !max-w-full !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-xs !text-[var(--ink-light)]"
                                    >
                                      <span className="inline-block max-w-[10.5rem] truncate align-bottom sm:max-w-[12rem]" title={tag}>
                                        {tag}
                                      </span>
                                    </Tag>
                                  ))
                                ) : null}
                              </div>
                              <div className="mt-3 flex flex-1 flex-col justify-end border-t border-[var(--paper-warm)] pt-3">
                                <div className="flex items-end justify-between gap-2">
                                  <div className="flex flex-wrap items-baseline gap-1">
                                    <span className="text-xl font-semibold text-[var(--ochre)]" style={{ fontFamily: 'var(--font-serif)' }}>
                                      ¥{item.final_price}
                                    </span>
                                    {item.original_price > item.final_price && (
                                      <span className="text-xs text-[var(--ink-muted)] line-through">¥{item.original_price}</span>
                                    )}
                                  </div>
                                  <div className="flex shrink-0 items-center gap-2 text-xs text-[var(--ink-muted)]">
                                    <span className="flex items-center gap-0.5 text-[var(--ink-light)]">
                                      <HomeOutlined className="text-[var(--gold)]" />
                                      {item.bedroom_count} 室
                                    </span>
                                    <span className="text-[var(--gold)]">★ {item.rating}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </Link>
                        </div>
                      </List.Item>
                    );
                  }}
                />
                <div className="mt-8 flex justify-center rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/40 px-4 py-4">
                  <Pagination
                    current={currentPage}
                    pageSize={pageSize}
                    total={total}
                    onChange={handlePageChange}
                    showSizeChanger
                    showTotal={t => <span className="text-sm text-[var(--ink-muted)]">共 {t} 条</span>}
                  />
                </div>
              </>
            ) : (
              !loading && (
                <Empty description="暂无房源数据" className="py-16" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )
            )}
          </Spin>
        </ZenPanel>
      </ZenSection>
    </div>
  );
};

export default Listings;
