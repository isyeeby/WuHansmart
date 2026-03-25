import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, Table, Tag, Spin, Modal, List, Button, Progress } from 'antd';
import { PageHeader } from '../components/common';
import { ZenPanel, ZenSection } from '../components/zen/ZenPageBlocks';
import { ZEN_COLORS } from '../utils/echartsTheme';
import { getDistricts, getFacilityPremium, type DistrictStats, type FacilityPremium } from '../services/analysisApi';
import { getListings, type ListingItem } from '../services/listingsApi';

const Analysis: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [districtStats, setDistrictStats] = useState<DistrictStats[]>([]);
  const [facilityLoading, setFacilityLoading] = useState(true);
  const [facilityData, setFacilityData] = useState<FacilityPremium[]>([]);
  const [listingsModalVisible, setListingsModalVisible] = useState(false);
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [listings, setListings] = useState<ListingItem[]>([]);
  const [listingsLoading, setListingsLoading] = useState(false);

  useEffect(() => {
    fetchData();
    fetchFacilityPremium();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const districts = await getDistricts();
      setDistrictStats(Array.isArray(districts) ? districts : []);
    } catch (error) {
      console.error('获取分析数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchFacilityPremium = async () => {
    try {
      setFacilityLoading(true);
      const response = await getFacilityPremium();
      setFacilityData(response?.facilities || []);
    } catch (error) {
      console.error('获取设施溢价数据失败:', error);
      setFacilityData([]);
    } finally {
      setFacilityLoading(false);
    }
  };

  const handleDistrictClick = async (district: string) => {
    setSelectedDistrict(district);
    setListingsModalVisible(true);
    setListingsLoading(true);
    try {
      const response = await getListings({ district, size: 20 });
      setListings(response?.items || []);
    } catch (error) {
      console.error('获取房源列表失败:', error);
      setListings([]);
    } finally {
      setListingsLoading(false);
    }
  };

  const columns = [
    {
      title: '行政区',
      dataIndex: 'district',
      key: 'district',
      render: (text: string) => <span className="font-medium text-[var(--ink-black)]">{text}</span>,
    },
    {
      title: '商圈名称',
      dataIndex: 'trade_area',
      key: 'trade_area',
      render: (text: string, record: DistrictStats) => (
        <Button type="link" className="h-auto p-0 font-medium text-[var(--ink-black)] hover:!text-[var(--ochre)]" onClick={() => handleDistrictClick(record.district)}>
          {text}
        </Button>
      ),
    },
    {
      title: '平均价格',
      dataIndex: 'avg_price',
      key: 'avg_price',
      render: (text: number) => (
        <span className="font-medium text-[var(--ink-black)]" style={{ fontFamily: 'var(--font-serif)' }}>
          ¥{Math.round(text || 0)}
        </span>
      ),
    },
    {
      title: '房源数量',
      dataIndex: 'listing_count',
      key: 'listing_count',
      render: (text: number, record: DistrictStats) => (
        <Button type="link" className="h-auto p-0" onClick={() => handleDistrictClick(record.district)}>
          <Tag className="!cursor-pointer !border-[var(--paper-warm)] !bg-[var(--paper-cream)] !text-[var(--gold)]">
            {text} 套
          </Tag>
        </Button>
      ),
    },
    {
      title: '平均评分',
      dataIndex: 'avg_rating',
      key: 'avg_rating',
      render: (text: number) => (
        <Tag className="!border-[rgba(90,138,110,0.35)] !bg-[var(--jade-pale)] !text-[var(--jade)]">{text?.toFixed(2) || '-'} 分</Tag>
      ),
    },
    {
      title: '价格区间',
      key: 'price_range',
      render: (record: DistrictStats) => (
        <span className="text-sm text-[var(--ink-light)]">
          ¥{record.min_price?.toFixed(0) || 0} — ¥{record.max_price?.toFixed(0) || 0}
        </span>
      ),
    },
  ];

  const tableData = Array.isArray(districtStats)
    ? districtStats.map((item, index) => ({
        key: index.toString(),
        ...item,
      }))
    : [];

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spin size="large" tip="加载数据中..." />
      </div>
    );
  }

  return (
    <div className="analysis-shell space-y-12 pb-10 sm:space-y-14">
      <PageHeader title="商圈深度分析" subtitle="按行政区与商圈聚合价格、供给与评分，支持下钻查看房源清单" category="Analysis" />

      <ZenSection title="商圈名录" accent="ink">
        <ZenPanel accent="ink" title="商圈深度数据">
          <div className="-mx-1 overflow-x-auto">
            <Table columns={columns} dataSource={tableData} pagination={false} className="zen-table min-w-[720px]" />
          </div>
        </ZenPanel>
      </ZenSection>

      <ZenSection title="设施溢价" accent="jade">
        <ZenPanel accent="jade" title="设施溢价分析" loading={facilityLoading}>
          {facilityData.length > 0 ? (
            <Table
              dataSource={facilityData.map((item, index) => ({ ...item, key: index }))}
              pagination={{ pageSize: 8, showSizeChanger: false, className: '!mb-0' }}
              columns={[
                {
                  title: '设施名称',
                  dataIndex: 'facility_name',
                  key: 'facility_name',
                  render: (text: string) => (
                    <Tag className="!border-[var(--paper-warm)] !bg-[var(--paper-cream)] !font-medium !text-[var(--ink-black)]">{text}</Tag>
                  ),
                },
                {
                  title: '有此设施均价',
                  dataIndex: 'avg_price_with',
                  key: 'avg_price_with',
                  render: (val: number) => <span className="text-[var(--ink-black)]">¥{val?.toFixed(0)}</span>,
                },
                {
                  title: '无此设施均价',
                  dataIndex: 'avg_price_without',
                  key: 'avg_price_without',
                  render: (val: number) => <span className="text-[var(--ink-light)]">¥{val?.toFixed(0)}</span>,
                },
                {
                  title: '溢价金额',
                  dataIndex: 'premium_amount',
                  key: 'premium_amount',
                  render: (val: number) => (
                    <span className={val >= 0 ? 'text-[var(--jade)]' : 'text-[var(--ochre)]'}>
                      {val >= 0 ? '+' : ''}¥{val?.toFixed(0)}
                    </span>
                  ),
                },
                {
                  title: '溢价比例',
                  dataIndex: 'premium_percent',
                  key: 'premium_percent',
                  render: (val: number) => (
                    <div className="flex max-w-[200px] items-center gap-3">
                      <Progress
                        percent={Math.min(Math.abs(val), 100)}
                        size="small"
                        strokeColor={val >= 0 ? ZEN_COLORS.jade : ZEN_COLORS.ochre}
                        showInfo={false}
                        className="min-w-0 flex-1"
                      />
                      <span className={`shrink-0 text-sm font-medium ${val >= 0 ? 'text-[var(--jade)]' : 'text-[var(--ochre)]'}`}>
                        {val >= 0 ? '+' : ''}
                        {val?.toFixed(1)}%
                      </span>
                    </div>
                  ),
                },
                {
                  title: '样本数量',
                  dataIndex: 'listing_count',
                  key: 'listing_count',
                  render: (val: number) => <span className="text-[var(--ink-muted)]">{val} 套</span>,
                },
              ]}
              className="zen-table"
            />
          ) : (
            !facilityLoading && (
              <div className="rounded-lg border border-dashed border-[var(--paper-warm)] bg-[var(--paper-cream)]/40 py-14 text-center text-sm text-[var(--ink-muted)]">
                暂无设施溢价数据
              </div>
            )
          )}
        </ZenPanel>
      </ZenSection>

      <Card
        bordered={false}
        className="!rounded-xl !border !border-[var(--paper-warm)] !bg-[var(--paper-cream)]/90 !shadow-[var(--shadow-soft)]"
        styles={{ body: { padding: 'var(--space-lg)' } }}
      >
        <p className="m-0 text-sm leading-relaxed text-[var(--ink-light)]">
          点击商圈名称或房源数量可查看该行政区下样本房源；溢价基于同批数据内有无该设施的均价对比，仅供参考。
        </p>
      </Card>

      <Modal
        title={
          <span style={{ fontFamily: 'var(--font-serif)' }} className="text-[var(--ink-black)]">
            {selectedDistrict} · 房源列表
          </span>
        }
        open={listingsModalVisible}
        onCancel={() => setListingsModalVisible(false)}
        footer={null}
        width={820}
        rootClassName="analysis-listings-modal"
      >
        <List
          loading={listingsLoading}
          itemLayout="horizontal"
          dataSource={listings}
          renderItem={(item) => (
            <List.Item
              className="!border-[var(--paper-warm)]"
              actions={[
                <Link key="detail" to={`/listing/${item.unit_id}`} className="text-[var(--ochre)] hover:underline">
                  查看详情
                </Link>,
              ]}
            >
              <List.Item.Meta
                title={<span className="font-medium text-[var(--ink-black)]">{item.title}</span>}
                description={
                  <div className="text-sm text-[var(--ink-light)]">
                    <span>卧室 {item.bedroom_count} 间</span>
                    <span className="ml-4">床位 {item.bed_count} 张</span>
                  </div>
                }
              />
              <div className="text-right">
                <div className="text-lg font-semibold text-[var(--ochre)]" style={{ fontFamily: 'var(--font-serif)' }}>
                  ¥{item.final_price}
                </div>
                <div className="text-xs text-[var(--ink-muted)]">评分 {item.rating?.toFixed(1) || '—'}</div>
              </div>
            </List.Item>
          )}
          locale={{ emptyText: '暂无房源数据' }}
        />
      </Modal>
    </div>
  );
};

export default Analysis;
