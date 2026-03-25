import React, { useState, useEffect, useMemo } from 'react';
import {
  Row,
  Col,
  Button,
  List,
  Tag,
  Checkbox,
  Dropdown,
  Modal,
  Empty,
  Spin,
  message,
} from 'antd';
import {
  DeleteOutlined,
  CompressOutlined,
  MoreOutlined,
  EyeOutlined,
  FolderOutlined,
  HeartOutlined,
  EnvironmentOutlined,
  HomeOutlined,
} from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/common';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import {
  getFavorites,
  removeFavorite,
  getFavoriteFolders,
  type FavoriteItem,
  type FavoriteFolder,
} from '../services/favoritesApi';
import { getListingDetail, type ListingItem } from '../services/listingsApi';

interface FavoriteWithDetail extends FavoriteItem {
  listing?: ListingItem;
  loading?: boolean;
}

const SORT_OPTIONS: { key: 'time' | 'price' | 'rating'; label: string }[] = [
  { key: 'time', label: '最近收藏' },
  { key: 'price', label: '价格' },
  { key: 'rating', label: '评分' },
];

const Favorites: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [favorites, setFavorites] = useState<FavoriteWithDetail[]>([]);
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [folders, setFolders] = useState<FavoriteFolder[]>([]);
  const [activeTab, setActiveTab] = useState('all');
  const [sortBy, setSortBy] = useState<'time' | 'price' | 'rating'>('time');

  useEffect(() => {
    fetchFavoritesData();
    fetchFolders();
  }, []);

  const fetchFolders = async () => {
    try {
      const data = await getFavoriteFolders();
      setFolders(data);
    } catch (error) {
      console.error('获取收藏夹失败:', error);
    }
  };

  const fetchFavoritesData = async () => {
    try {
      setLoading(true);
      const favoritesData = await getFavorites();

      if (!Array.isArray(favoritesData)) {
        setFavorites([]);
        return;
      }

      const initialFavorites: FavoriteWithDetail[] = favoritesData.map(fav => ({
        ...fav,
        listing: undefined,
        loading: true,
      }));
      setFavorites(initialFavorites);

      const detailPromises = favoritesData.map(async fav => {
        try {
          const detail = await getListingDetail(fav.unit_id);
          return { unit_id: fav.unit_id, detail, error: null };
        } catch (error) {
          console.error(`获取房源 ${fav.unit_id} 详情失败:`, error);
          return { unit_id: fav.unit_id, detail: null, error };
        }
      });

      const details = await Promise.all(detailPromises);

      setFavorites(prev =>
        prev.map(fav => {
          const detailResult = details.find(d => d.unit_id === fav.unit_id);
          return {
            ...fav,
            listing: detailResult?.detail || undefined,
            loading: false,
          };
        })
      );
    } catch (error) {
      console.error('获取收藏数据失败:', error);
      message.error('获取收藏数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFavorite = async (unitId: string) => {
    try {
      await removeFavorite(unitId);
      message.success('取消收藏成功');
      setSelectedItems(prev => prev.filter(id => id !== unitId));
      fetchFavoritesData();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleSelectItem = (id: string, checked: boolean) => {
    if (checked) {
      setSelectedItems([...selectedItems, id]);
    } else {
      setSelectedItems(selectedItems.filter(item => item !== id));
    }
  };

  const handleSelectAll = () => {
    if (selectedItems.length === displayedFavorites.length) {
      setSelectedItems([]);
    } else {
      setSelectedItems(displayedFavorites.map(f => f.unit_id));
    }
  };

  const handleDeleteSelected = async () => {
    try {
      for (const unitId of selectedItems) {
        await removeFavorite(unitId);
      }
      message.success('批量删除成功');
      setSelectedItems([]);
      fetchFavoritesData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleCompare = () => {
    if (selectedItems.length >= 2) {
      navigate('/comparison?ids=' + selectedItems.join(','));
    } else {
      setCompareModalOpen(true);
    }
  };

  const sortedFavorites = [...favorites].sort((a, b) => {
    if (sortBy === 'price') {
      return (a.listing?.final_price || 0) - (b.listing?.final_price || 0);
    }
    if (sortBy === 'rating') {
      return (b.listing?.rating || 0) - (a.listing?.rating || 0);
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const displayedFavorites = useMemo(() => {
    if (activeTab === 'all') return sortedFavorites;
    return sortedFavorites.filter(f => (f.folder_name || '默认收藏夹') === activeTab);
  }, [sortedFavorites, activeTab]);

  const parseTags = (tags: unknown): string[] => {
    if (!tags) return [];
    const extractText = (t: unknown): string | null => {
      if (typeof t === 'string') return t;
      if (!t || typeof t !== 'object') return null;
      const o = t as Record<string, unknown>;
      if (o.tagText && typeof o.tagText === 'object' && o.tagText !== null) {
        const tt = o.tagText as Record<string, unknown>;
        return typeof tt.text === 'string' ? tt.text : null;
      }
      if (typeof o.text === 'string') return o.text;
      if (typeof o.tagText === 'string') return o.tagText;
      return null;
    };
    if (Array.isArray(tags)) {
      return tags.map(extractText).filter((t): t is string => Boolean(t)).slice(0, 3);
    }
    if (typeof tags === 'string') {
      try {
        const parsed = JSON.parse(tags) as unknown;
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

  return (
    <div className="favorites-shell space-y-10 pb-10 sm:space-y-12">
      <PageHeader
        title="我的收藏"
        subtitle="按收藏夹整理房源，支持多选对比与批量管理"
        category="Favorites"
      />

      <ZenSection title="收藏库" accent="ochre">
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={7}>
            <ZenPanel accent="jade" title="收藏夹" titleCaps={false}>
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('all')}
                  className={`favorites-folder-row flex w-full items-center justify-between rounded-lg border px-3 py-3 text-left transition-colors ${
                    activeTab === 'all'
                      ? 'border-[var(--paper-warm)] bg-[var(--paper-cream)] shadow-[var(--shadow-soft)]'
                      : 'border-transparent hover:bg-[var(--paper-cream)]/60'
                  }`}
                >
                  <span className="flex items-center gap-2 text-sm font-medium text-[var(--ink-black)]">
                    <FolderOutlined className="text-[var(--jade)]" aria-hidden />
                    全部收藏
                  </span>
                  <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-white)] !text-xs !text-[var(--ink-muted)]">
                    {sortedFavorites.length}
                  </Tag>
                </button>
                {folders.map(folder => (
                  <button
                    key={folder.name}
                    type="button"
                    onClick={() => setActiveTab(folder.name)}
                    className={`favorites-folder-row flex w-full items-center justify-between rounded-lg border px-3 py-3 text-left transition-colors ${
                      activeTab === folder.name
                        ? 'border-[var(--paper-warm)] bg-[var(--paper-cream)] shadow-[var(--shadow-soft)]'
                        : 'border-transparent hover:bg-[var(--paper-cream)]/60'
                    }`}
                  >
                    <span className="truncate text-sm text-[var(--ink-black)]">{folder.name}</span>
                    <Tag className="!m-0 shrink-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-xs !text-[var(--ink-light)]">
                      {folder.count}
                    </Tag>
                  </button>
                ))}
              </div>
            </ZenPanel>
          </Col>

          <Col xs={24} lg={17}>
            <ZenPanel
              accent="ink"
              title="已藏房源"
              titleCaps={false}
              extra={
                !loading && displayedFavorites.length > 0 ? (
                  <Tag className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--ink-muted)]">
                    本页 {displayedFavorites.length} 套
                  </Tag>
                ) : null
              }
            >
              <div className="mb-6 flex flex-col gap-4 border-b border-[var(--paper-warm)] pb-6 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap items-center gap-3">
                  <Checkbox
                    checked={
                      selectedItems.length === displayedFavorites.length && displayedFavorites.length > 0
                    }
                    onChange={handleSelectAll}
                    className="text-[var(--ink-light)]"
                  >
                    <span className="text-sm text-[var(--ink-muted)]">
                      全选（{selectedItems.length}/{displayedFavorites.length}）
                    </span>
                  </Checkbox>
                  {selectedItems.length > 0 && (
                    <>
                      <Button
                        size="small"
                        icon={<CompressOutlined />}
                        onClick={handleCompare}
                        className="!border-[var(--paper-warm)] !bg-[var(--ink-black)] !text-white hover:!bg-[var(--ink-dark)]"
                      >
                        对比（{selectedItems.length}）
                      </Button>
                      <Button
                        size="small"
                        danger
                        type="default"
                        icon={<DeleteOutlined />}
                        onClick={handleDeleteSelected}
                        className="!border-[var(--paper-warm)]"
                      >
                        批量移除
                      </Button>
                    </>
                  )}
                </div>
                <div
                  className="flex flex-wrap items-center gap-1 rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/35 p-1"
                  role="group"
                  aria-label="排序"
                >
                  {SORT_OPTIONS.map(opt => (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => setSortBy(opt.key)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        sortBy === opt.key
                          ? 'bg-[var(--paper-white)] text-[var(--ink-black)] shadow-[var(--shadow-soft)]'
                          : 'text-[var(--ink-muted)] hover:text-[var(--ink-black)]'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <Spin spinning={loading} tip="加载中...">
                {displayedFavorites.length > 0 ? (
                  <List
                    grid={{ gutter: [20, 24], xs: 1, sm: 2, md: 2, lg: 2, xl: 3 }}
                    dataSource={displayedFavorites}
                    renderItem={item => {
                      const listing = item.listing;
                      const isLoading = item.loading;

                      if (isLoading) {
                        return (
                          <List.Item className="!mb-0 !border-none !p-0">
                            <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-cream)]/30">
                              <Spin />
                            </div>
                          </List.Item>
                        );
                      }

                      if (!listing) {
                        return (
                          <List.Item className="!mb-0 !border-none !p-0">
                            <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[var(--paper-warm)] bg-[var(--paper-cream)]/20 p-4 text-center">
                              <p className="m-0 text-sm text-[var(--ink-muted)]">房源 {item.unit_id} 暂不可用</p>
                              <Button type="link" danger size="small" onClick={() => handleRemoveFavorite(item.unit_id)}>
                                取消收藏
                              </Button>
                            </div>
                          </List.Item>
                        );
                      }

                      const tags = parseTags(listing.house_tags);
                      const savedLabel = new Date(item.created_at).toLocaleDateString('zh-CN', {
                        month: 'short',
                        day: 'numeric',
                      });

                      return (
                        <List.Item className="!mb-0 !border-none !p-0">
                          <div className="group relative h-full">
                            <div className="flex h-full flex-col overflow-hidden rounded-xl border border-[var(--paper-warm)] bg-[var(--paper-white)] shadow-[var(--shadow-soft)] transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-medium)]">
                              <div className="favorite-card-cover relative aspect-[4/3] overflow-hidden bg-[var(--paper-cream)]">
                                <div
                                  className="absolute left-0 top-0 z-20 flex h-9 w-9 items-center justify-center rounded-br-lg border-b border-r border-[var(--paper-warm)] bg-white/82 backdrop-blur-[6px]"
                                  onClick={e => e.stopPropagation()}
                                >
                                  <Checkbox
                                    checked={selectedItems.includes(item.unit_id)}
                                    onChange={e => {
                                      e.stopPropagation();
                                      handleSelectItem(item.unit_id, e.target.checked);
                                    }}
                                    onClick={e => e.stopPropagation()}
                                    className="!m-0"
                                    aria-label={selectedItems.includes(item.unit_id) ? '取消选择' : '选择房源'}
                                  />
                                </div>
                                <div
                                  className="absolute right-0 top-0 z-30 flex h-9 w-9 items-center justify-center rounded-bl-lg border-b border-l border-[var(--paper-warm)] bg-white/82 backdrop-blur-[6px]"
                                  onClick={e => e.stopPropagation()}
                                >
                                  <Dropdown
                                    menu={{
                                      items: [
                                        {
                                          key: 'detail',
                                          label: '查看详情',
                                          icon: <EyeOutlined />,
                                        },
                                        { type: 'divider' },
                                        {
                                          key: 'remove',
                                          label: '取消收藏',
                                          danger: true,
                                          icon: <DeleteOutlined />,
                                        },
                                      ],
                                      onClick: ({ key, domEvent }) => {
                                        domEvent.stopPropagation();
                                        if (key === 'detail') {
                                          navigate(`/listing/${item.unit_id}/detail`);
                                        }
                                        if (key === 'remove') handleRemoveFavorite(item.unit_id);
                                      },
                                    }}
                                    trigger={['click']}
                                    placement="bottomRight"
                                  >
                                    <Button
                                      type="text"
                                      icon={<MoreOutlined />}
                                      className="!flex !h-full !w-full !items-center !justify-center !rounded-none !border-0 !bg-transparent !text-[var(--ink-muted)] hover:!bg-[var(--paper-cream)] hover:!text-[var(--ink-black)]"
                                      aria-label="更多操作"
                                      onClick={e => e.preventDefault()}
                                    />
                                  </Dropdown>
                                </div>
                                <Link
                                  to={`/listing/${item.unit_id}/detail`}
                                  className="relative z-0 block h-full w-full overflow-hidden"
                                >
                                  <img
                                    alt=""
                                    src={listing.cover_image || `https://picsum.photos/seed/${item.unit_id}/400/300`}
                                    className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                                  />
                                  <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/45 to-transparent px-3 pb-2 pt-8">
                                    <span className="text-[10px] font-medium uppercase tracking-wider text-white/90">
                                      收藏于 {savedLabel}
                                    </span>
                                  </div>
                                </Link>
                              </div>
                              <Link
                                to={`/listing/${item.unit_id}/detail`}
                                className="flex flex-1 flex-col p-4 no-underline"
                              >
                                <div
                                  className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-[var(--ink-black)] group-hover:text-[var(--ochre)]"
                                  style={{ fontFamily: 'var(--font-serif)' }}
                                >
                                  {listing.title}
                                </div>
                                <div className="mt-2 flex items-center gap-1 text-xs text-[var(--ink-muted)]">
                                  <EnvironmentOutlined className="shrink-0 text-[var(--gold)]" />
                                  <span className="truncate">
                                    {listing.district}
                                    {listing.trade_area ? ` · ${listing.trade_area}` : ''}
                                  </span>
                                </div>
                                <div className="mt-2 flex min-h-[1.75rem] flex-wrap items-center gap-1.5">
                                  {tags.length > 0 ? (
                                    tags.map((tag, idx) => (
                                      <Tag
                                        key={idx}
                                        className="!m-0 !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-xs !text-[var(--ink-light)]"
                                      >
                                        {tag}
                                      </Tag>
                                    ))
                                  ) : (
                                    <span className="text-[10px] text-transparent select-none" aria-hidden>
                                      ·
                                    </span>
                                  )}
                                </div>
                                <div className="mt-3 flex flex-1 flex-col justify-end border-t border-[var(--paper-warm)] pt-3">
                                  <div className="flex items-end justify-between gap-2">
                                    <div className="flex flex-wrap items-baseline gap-1">
                                      <span
                                        className="text-xl font-semibold text-[var(--ochre)]"
                                        style={{ fontFamily: 'var(--font-serif)' }}
                                      >
                                        ¥{listing.final_price}
                                      </span>
                                      <span className="text-xs text-[var(--ink-muted)]">/ 晚</span>
                                      {listing.original_price != null &&
                                        listing.final_price !== listing.original_price && (
                                          <span className="text-xs text-[var(--ink-muted)] line-through">
                                            ¥{listing.original_price}
                                          </span>
                                        )}
                                    </div>
                                    <div className="flex shrink-0 items-center gap-2 text-xs text-[var(--ink-muted)]">
                                      <span className="flex items-center gap-0.5 text-[var(--ink-light)]">
                                        <HomeOutlined className="text-[var(--gold)]" />
                                        {listing.bedroom_count ?? 1} 室
                                      </span>
                                      <span className="text-[var(--gold)]">★ {listing.rating ?? '—'}</span>
                                    </div>
                                  </div>
                                </div>
                              </Link>
                            </div>
                          </div>
                        </List.Item>
                      );
                    }}
                  />
                ) : (
                  !loading && (
                    <Empty
                      description="暂无收藏的房源"
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      className="py-16"
                    >
                      <Link to="/recommendation">
                        <Button
                          type="primary"
                          size="large"
                          icon={<HeartOutlined />}
                          className="!border-none !bg-[var(--ink-black)] hover:!bg-[var(--ink-dark)]"
                        >
                          去发现房源
                        </Button>
                      </Link>
                    </Empty>
                  )
                )}
              </Spin>
            </ZenPanel>
          </Col>
        </Row>
      </ZenSection>

      <Modal
        title="提示"
        open={compareModalOpen}
        onOk={() => setCompareModalOpen(false)}
        onCancel={() => setCompareModalOpen(false)}
        footer={[
          <Button
            key="ok"
            onClick={() => setCompareModalOpen(false)}
            className="!border-none !bg-[var(--ink-black)] !text-white hover:!bg-[var(--ink-dark)]"
          >
            知道了
          </Button>,
        ]}
      >
        <p className="text-[var(--ink-muted)]">请至少选择 2 个房源进行对比</p>
      </Modal>
    </div>
  );
};

export default Favorites;
