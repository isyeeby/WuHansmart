import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, Row, Col, Tag, Button, Spin, Empty, message, Image, Rate, Divider, Collapse, Tabs, Typography } from 'antd';
import { HeartOutlined, HeartFilled, EnvironmentOutlined, HomeOutlined, StarOutlined, ArrowLeftOutlined, CalendarOutlined, DownOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { motion } from 'motion/react';
import { PageHeader } from '../components/common';

import { getListingDetail, getListingGallery, getSimilarListings, getListingPriceCalendar, type ListingDetail, type ListingGallery, type SimilarListing, type ImageCategories, type PriceCalendarResponse } from '../services/listingsApi';
import { addFavorite, removeFavorite } from '../services/favoritesApi';
import { PriceCalendar } from '../components/PriceCalendar';
import { FacilityModulePanel, CommentModulePanel, LandlordModulePanel } from '../components/ListingDynamicModules';

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

const ListingDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const reducedMotion = usePrefersReducedMotion();
  const sm = sectionMotion(reducedMotion);

  const [loading, setLoading] = useState(true);
  const [listing, setListing] = useState<ListingDetail | null>(null);
  const [gallery, setGallery] = useState<ListingGallery | null>(null);
  const [similarListings, setSimilarListings] = useState<SimilarListing[]>([]);
  const [isFavorite, setIsFavorite] = useState(false);
  const [priceCalendarVisible, setPriceCalendarVisible] = useState(false);
  const [priceCalendarData, setPriceCalendarData] = useState<PriceCalendarResponse | null>(null);
  const [priceCalendarLoading, setPriceCalendarLoading] = useState(false);
  const [activeImageIndex, setActiveImageIndex] = useState(0);

  useEffect(() => {
    if (id) {
      fetchListingDetail(id);
    }
  }, [id]);

  const fetchListingDetail = async (unitId: string) => {
    try {
      setLoading(true);
      const [listingData, galleryData, similarData] = await Promise.all([
        getListingDetail(unitId),
        getListingGallery(unitId),
        getSimilarListings(unitId, 6),
      ]);
      setListing(listingData);
      setGallery(galleryData);
      setSimilarListings(similarData);
    } catch (error) {
      console.error('获取房源详情失败:', error);
      message.error('获取房源详情失败');
    } finally {
      setLoading(false);
    }
  };

  const toggleFavorite = async () => {
    if (!id) return;
    try {
      if (isFavorite) {
        await removeFavorite(id);
        setIsFavorite(false);
        message.success('取消收藏成功');
      } else {
        await addFavorite(id);
        setIsFavorite(true);
        message.success('收藏成功');
      }
    } catch (error) {
      message.error('操作失败');
    }
  };

  const showPriceCalendar = async () => {
    if (!id) return;
    setPriceCalendarVisible(true);
    setPriceCalendarLoading(true);
    try {
      const data = await getListingPriceCalendar(id, undefined, undefined, true);
      setPriceCalendarData(data);
    } catch (error) {
      message.error('获取价格日历失败');
    } finally {
      setPriceCalendarLoading(false);
    }
  };

  interface TagItem {
    tagText?: {
      text?: string;
      color?: string;
      border?: { color?: string; width?: number };
      background?: { color?: string; image?: string | null; gradientColor?: string | null };
    };
    tagDesc?: string;
    tagCode?: number;
  }

  const parseTags = (tags: any): TagItem[] => {
    if (!tags) return [];
    if (Array.isArray(tags)) {
      return tags.filter(t => t && typeof t === 'object' && t.tagText);
    }
    if (typeof tags === 'string') {
      try {
        const parsed = JSON.parse(tags);
        if (Array.isArray(parsed)) {
          return parsed.filter(t => t && typeof t === 'object' && t.tagText);
        }
        return parsed && parsed.tagText ? [parsed] : [];
      } catch {
        return [];
      }
    }
    if (typeof tags === 'object' && tags.tagText) {
      return [tags];
    }
    return [];
  };

  const mainImages = useMemo(() => {
    if (!gallery) return [];
    const { categories } = gallery;
    const collected: string[] = [];
    const priorityOrder = ['客厅', '卧室', '阳台', '外景', '卫生间', '厨房', '休闲', '其他'];
    for (const category of priorityOrder) {
      const images = categories[category as keyof ImageCategories];
      if (images && images.length > 0) {
        collected.push(...images);
      }
    }
    return collected.slice(0, 5);
  }, [gallery]);

  useEffect(() => {
    if (activeImageIndex >= mainImages.length) {
      setActiveImageIndex(0);
    }
  }, [mainImages.length, activeImageIndex]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!listing) {
    return (
      <Empty description="房源不存在或已下架">
        <Link to="/listings">
          <Button type="primary" className="!bg-[#1a1a1a] !border-none">
            返回房源列表
          </Button>
        </Link>
      </Empty>
    );
  }

  const tags = parseTags(listing.house_tags);
  const currentMainSrc = mainImages[activeImageIndex] ?? mainImages[0];

  const priceBlock = (
    <div className="flex flex-wrap items-baseline gap-2">
      <span className="text-3xl sm:text-4xl font-[var(--font-serif)] font-semibold text-[var(--ochre)]">
        ¥{listing.final_price}
      </span>
      {listing.original_price != null &&
        listing.discount_rate != null &&
        listing.original_price > listing.final_price && (
        <>
          <span className="text-base sm:text-lg text-[var(--ink-muted)] line-through">¥{listing.original_price}</span>
          <Tag className="!bg-[var(--ochre)] !text-white !border-none">
            省{Math.round(Number(listing.discount_rate) * 100)}%
          </Tag>
        </>
      )}
      <span className="text-[var(--ink-muted)]">/晚</span>
    </div>
  );

  const metaGrid = (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 text-sm">
      <div className="flex items-center gap-2 min-w-0">
        <HomeOutlined className="text-[var(--ink-muted)] shrink-0" />
        <span className="text-[var(--ink-light)] truncate">
          {listing.bedroom_count}室{listing.bed_count}床
        </span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        <EnvironmentOutlined className="text-[var(--ink-muted)] shrink-0" />
        <span className="text-[var(--ink-light)] truncate">{listing.district}</span>
      </div>
      <div className="flex items-center gap-2">
        <StarOutlined className="text-[var(--gold)] shrink-0" />
        <span className="text-[var(--ink-light)]">{listing.rating}分</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[var(--ink-muted)]">收藏</span>
        <span className="text-[var(--ink-light)]">{listing.favorite_count}</span>
      </div>
    </div>
  );

  const actionRow = (
    <div className="flex flex-wrap items-center gap-2 pt-1">
      <Button
        type="text"
        icon={<CalendarOutlined />}
        onClick={showPriceCalendar}
        className="!text-[var(--gold)] hover:!bg-[rgba(184,149,110,0.12)] !h-10"
      >
        查看价格日历
      </Button>
      <Link to="/prediction">
        <Button type="text" icon={<ThunderboltOutlined />} className="!text-[var(--ink-black)] hover:!bg-[rgba(26,26,26,0.06)] !h-10">
          智能定价
        </Button>
      </Link>
      <Button
        size="large"
        icon={isFavorite ? <HeartFilled className="text-[var(--ochre)]" /> : <HeartOutlined />}
        onClick={toggleFavorite}
        className="!h-10 !w-10 !min-w-10"
        aria-label={isFavorite ? '取消收藏' : '收藏'}
      />
    </div>
  );

  const bookingCardInner = (
    <div className="space-y-4">
      {priceBlock}
      <Divider className="!my-2 !border-[var(--paper-warm)]" />
      {metaGrid}
      {actionRow}
    </div>
  );

  const editorialTitle = (accent: 'jade' | 'gold' | 'ink', label: string) => {
    const bar =
      accent === 'jade'
        ? 'bg-[var(--jade)]'
        : accent === 'gold'
          ? 'bg-[var(--gold)]'
          : 'bg-[var(--ink-black)]';
    return (
      <h2 className="flex items-center gap-3 text-lg sm:text-xl font-[var(--font-serif)] font-semibold text-[var(--ink-black)] tracking-tight">
        <span className={`block w-1 self-stretch min-h-[1.25rem] rounded-full ${bar}`} aria-hidden />
        {label}
      </h2>
    );
  };

  return (
    <div className="listing-detail-shell space-y-8 sm:space-y-10 pb-10">
      <motion.div {...sm}>
        <div className="flex items-center gap-2">
          <Link to="/listings">
            <Button type="text" icon={<ArrowLeftOutlined />} className="text-[var(--ink-light)] hover:!text-[var(--ink-black)]">
              返回列表
            </Button>
          </Link>
        </div>

        <PageHeader title={listing.title} subtitle={`${listing.district} · ${listing.trade_area}`} category="Listing Detail" />
      </motion.div>

      {/* 首屏图区：影廊式主图（墨底 + 氛围模糊层 + 清晰主图）+ 底部胶片缩略条，无侧栏滚动条 */}
      <motion.section {...sm} className="listing-detail-hero">
        {mainImages.length > 0 && currentMainSrc ? (
          <div className="listing-detail-hero-stage overflow-hidden rounded-2xl border border-[var(--paper-warm)] bg-[var(--ink-black)] shadow-[var(--shadow-medium)]">
            <div
              className="relative w-full overflow-hidden"
              style={{ aspectRatio: '16 / 10', maxHeight: 'min(72vh, 720px)' }}
            >
              <img
                src={currentMainSrc}
                alt=""
                aria-hidden
                className="pointer-events-none absolute inset-0 z-0 h-full w-full scale-[1.08] object-cover opacity-40 blur-3xl"
              />
              <div className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-b from-[var(--ink-black)]/25 via-transparent to-[var(--ink-black)]/55" />
              <div className="relative z-[2] h-full min-h-[min(42vh,280px)] w-full">
                <Image
                  src={currentMainSrc}
                  alt={`房源图片 ${activeImageIndex + 1}`}
                  preview={{ src: currentMainSrc }}
                  classNames={{ root: 'listing-detail-hero-mainimg h-full w-full' }}
                />
              </div>
              <div
                className="absolute bottom-3 left-3 z-[3] rounded-md border border-white/20 bg-black/50 px-2.5 py-1 text-[11px] font-medium tabular-nums text-white/95 backdrop-blur-sm"
                aria-live="polite"
              >
                {activeImageIndex + 1} / {mainImages.length}
              </div>
            </div>
            <div
              className="listing-detail-hero-thumbs flex flex-nowrap gap-2 overflow-x-auto border-t border-[var(--paper-warm)] bg-[var(--paper-white)]/95 px-3 py-2.5 backdrop-blur-md sm:gap-2.5 sm:px-4 sm:py-3 snap-x snap-mandatory"
              role="tablist"
              aria-label="主图缩略图"
            >
              {mainImages.map((img, idx) => (
                <button
                  key={idx}
                  type="button"
                  role="tab"
                  aria-selected={idx === activeImageIndex}
                  onClick={() => setActiveImageIndex(idx)}
                  className={`listing-detail-thumb-btn shrink-0 snap-start overflow-hidden rounded-lg border-2 transition-[border-color,box-shadow,opacity] ${
                    idx === activeImageIndex
                      ? 'border-[var(--ochre)] shadow-[var(--shadow-soft)] opacity-100'
                      : 'border-transparent opacity-80 hover:opacity-100'
                  }`}
                >
                  <img src={img} alt="" className="h-14 w-[4.75rem] object-cover sm:h-[4.25rem] sm:w-[6.25rem]" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex min-h-[14rem] items-center justify-center rounded-2xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]">
            <span className="text-[var(--ink-muted)]">暂无图片</span>
          </div>
        )}
      </motion.section>

      {/* 小屏：首屏下紧凑预订条 */}
      <motion.section {...sm} className="lg:hidden">
        <div className="zen-card rounded-lg border border-[var(--paper-warm)] p-4 shadow-[var(--shadow-soft)]">{bookingCardInner}</div>
      </motion.section>

      <Row gutter={[24, 24]} align="top">
        <Col xs={24} lg={15}>
          <motion.section {...sm}>
            {gallery ? (
              <Card
                bordered={false}
                className="!rounded-lg !border !border-[var(--paper-warm)] !shadow-[var(--shadow-soft)]"
                styles={{ body: { padding: 'var(--space-md) var(--space-lg)' } }}
                title={
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <div className="h-4 w-1 shrink-0 rounded-full bg-[var(--gold)]" />
                      <span className="truncate text-sm font-medium text-[var(--ink-black)]">房源相册</span>
                    </div>
                    <span className="shrink-0 text-xs text-[var(--ink-muted)]">共 {gallery.total_pics} 张</span>
                  </div>
                }
              >
                <Collapse
                  ghost
                  defaultActiveKey={['客厅']}
                  expandIcon={({ isActive }) => <DownOutlined rotate={isActive ? 180 : 0} className="text-[var(--ink-muted)]" />}
                  className="!bg-transparent"
                >
                  {Object.entries(gallery.categories)
                    .filter(([_, images]) => images.length > 0)
                    .map(([category, images]) => (
                      <Collapse.Panel
                        key={category}
                        header={
                          <div className="flex w-full items-center justify-between pr-4">
                            <span className="text-sm text-[var(--ink-black)]">{category}</span>
                            <span className="text-xs text-[var(--ink-muted)]">{images.length} 张</span>
                          </div>
                        }
                      >
                        <Image.PreviewGroup>
                          <Row gutter={[8, 8]}>
                            {images.map((img, idx) => (
                              <Col span={6} xs={12} sm={8} md={6} key={idx}>
                                <Image
                                  src={img}
                                  alt={`${category} ${idx + 1}`}
                                  style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 4 }}
                                  preview={{ mask: '查看' }}
                                />
                              </Col>
                            ))}
                          </Row>
                        </Image.PreviewGroup>
                      </Collapse.Panel>
                    ))}
                </Collapse>
              </Card>
            ) : null}
          </motion.section>
        </Col>

        <Col xs={24} lg={9}>
          <div className="hidden lg:block lg:sticky lg:top-24 lg:self-start">
            <motion.section {...sm}>
              <Card
                bordered={false}
                className="!rounded-lg !border !border-[var(--paper-warm)] !shadow-[var(--shadow-medium)]"
                styles={{ body: { padding: 'var(--space-lg)' } }}
              >
                {bookingCardInner}
              </Card>
            </motion.section>
          </div>
        </Col>
      </Row>

      {/* 全宽编辑区块：特色 */}
      {tags.length > 0 ? (
        <motion.section {...sm} className="paper-texture rounded-xl border border-[var(--paper-warm)] px-5 py-8 sm:px-8 sm:py-10 shadow-[var(--shadow-soft)]">
          {editorialTitle('jade', '房源特色')}
          <div className="mt-6 flex flex-wrap gap-2">
            {tags.map((tag, idx) => (
              <Tag
                key={idx}
                className="!border-none !px-3 !py-1 !text-sm"
                style={{
                  backgroundColor: tag.tagText?.background?.color || 'var(--paper-cream)',
                  color: tag.tagText?.color || 'var(--ink-light)',
                }}
                title={tag.tagDesc}
              >
                {tag.tagText?.text}
              </Tag>
            ))}
          </div>
        </motion.section>
      ) : null}

      {/* 全宽：评价摘要 */}
      {listing.comment_brief ? (
        <motion.section {...sm} className="rounded-xl border border-[var(--paper-warm)] bg-white px-5 py-8 sm:px-8 sm:py-10 shadow-[var(--shadow-soft)]">
          {editorialTitle('gold', '房客评价')}
          <blockquote className="mt-6 border-l-4 border-[var(--gold)] pl-5 text-base leading-relaxed text-[var(--ink-light)] sm:text-lg">
            <span className="text-[var(--ink-muted)]">「</span>
            {listing.comment_brief}
            <span className="text-[var(--ink-muted)]">」</span>
          </blockquote>
        </motion.section>
      ) : null}

      {/* 相似房源横向带 */}
      {similarListings.length > 0 ? (
        <motion.section {...sm}>
          <div className="mb-4">{editorialTitle('ink', '相似房源推荐')}</div>
          <div className="listing-detail-similar-scroll flex gap-4 overflow-x-auto pb-2 pt-1">
            {similarListings.map((item) => (
              <Link
                key={item.unit_id}
                to={`/listing/${item.unit_id}`}
                className="listing-detail-similar-card zen-card block w-[min(100%,280px)] shrink-0 overflow-hidden rounded-lg border border-[var(--paper-warm)] no-underline transition-[box-shadow,transform] hover:-translate-y-0.5 hover:shadow-[var(--shadow-medium)]"
              >
                {item.cover_image?.trim() ? (
                  <img
                    src={item.cover_image.trim()}
                    alt=""
                    className="h-36 w-full object-cover bg-[var(--paper-warm)]"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="flex h-36 w-full items-center justify-center bg-[var(--paper-warm)] text-xs text-[var(--ink-muted)]">
                    暂无封面
                  </div>
                )}
                <div className="p-4">
                  <div className="line-clamp-2 text-sm font-medium text-[var(--ink-black)]">{item.title}</div>
                  <div className="mt-1 text-xs text-[var(--ink-muted)]">{item.district}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="font-[var(--font-serif)] font-semibold text-[var(--ochre)]">¥{item.final_price}</span>
                    <Rate disabled defaultValue={item.rating} className="text-xs [&_.ant-rate-star]:mr-0.5" />
                    <Tag className="!ml-auto !border-none !bg-[var(--jade-pale)] !text-[var(--jade)]">
                      相似度 {Math.round(item.similarity_score)}%
                    </Tag>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </motion.section>
      ) : null}

      <motion.section {...sm} className="listing-detail-modules">
        <div className="overflow-hidden rounded-2xl border border-[var(--paper-warm)] bg-[var(--paper-white)] shadow-[var(--shadow-soft)]">
          <div className="border-b border-[var(--paper-warm)] bg-gradient-to-br from-[var(--paper-cream)]/90 via-[var(--paper-white)] to-[var(--paper-cream)]/50 px-5 py-5 sm:px-7 sm:py-6">
            <h2
              className="m-0 flex items-center gap-3 text-lg font-semibold tracking-tight text-[var(--ink-black)] sm:text-xl"
              style={{ fontFamily: 'var(--font-serif)' }}
            >
              <span className="block h-4 w-1 shrink-0 rounded-full bg-[var(--ochre)]" aria-hidden />
              详情与服务
            </h2>
            <p className="mb-0 mt-2 max-w-3xl text-xs leading-relaxed text-[var(--ink-muted)] sm:text-sm">
              {listing.detail_modules_note ||
                '设施清单、评价维度与房东信息来自途家详情模块；以下为结构化展示，随页面自然展开，无需在框内反复滚动。'}
            </p>
          </div>
          <div className="px-4 pb-6 pt-1 sm:px-7 sm:pb-8 sm:pt-2">
            <Tabs
              className="listing-detail-tabs"
              classNames={{ indicator: 'listing-detail-tabs-indicator' }}
              size="large"
              items={[
                {
                  key: 'facility',
                  label: '设施详情',
                  children: (
                    <div className="pt-4 sm:pt-5">
                      <FacilityModulePanel data={listing.facility_module ?? null} />
                    </div>
                  ),
                },
                {
                  key: 'comment',
                  label: '评价维度',
                  children: (
                    <div className="pt-4 sm:pt-5">
                      <CommentModulePanel data={listing.comment_module ?? null} />
                    </div>
                  ),
                },
                {
                  key: 'landlord',
                  label: '房东 / 品牌',
                  children: (
                    <div className="pt-4 sm:pt-5">
                      <LandlordModulePanel data={listing.landlord_module ?? null} />
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>
      </motion.section>

      <PriceCalendar
        visible={priceCalendarVisible}
        onClose={() => setPriceCalendarVisible(false)}
        data={priceCalendarData}
        loading={priceCalendarLoading}
      />
    </div>
  );
};

export default ListingDetail;
