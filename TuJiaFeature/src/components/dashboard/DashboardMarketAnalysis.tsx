import React, { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { Alert, Card, Table, Tag, Modal, List, Button, Progress } from 'antd';
import { ZenRichTooltip } from '../zen/ZenRichTooltip';
import { ZenPanel, ZenSection } from '../zen/ZenPageBlocks';
import { ZEN_COLORS } from '../../utils/echartsTheme';
import type { DistrictStats, FacilityPremium } from '../../services/analysisApi';
import { getListings, type ListingItem } from '../../services/listingsApi';

/** 接口可能返回空字符串；聚合行表示「该行政区下未维护商圈」的样本 */
function tradeAreaCellLabel(tradeArea: string | null | undefined): { label: string; isMissing: boolean } {
  const t = typeof tradeArea === 'string' ? tradeArea.trim() : '';
  if (t) return { label: t, isMissing: false };
  return { label: '未标注商圈', isMissing: true };
}

function listingLocationLine(item: ListingItem): string {
  const parts = [item.district, item.trade_area?.trim()].filter((p): p is string => Boolean(p && String(p).trim()));
  return parts.length ? parts.join(' · ') : '—';
}

/** 与后端 /api/analysis/facility-premium 一致，悬停标题旁问号可见精简版 */
const FACILITY_PREMIUM_TOOLTIP = (
  <div className="max-w-[320px] text-xs leading-relaxed">
    <p className="mb-2 text-[var(--ink-black)]">
      对固定一批设施名，把样本分成「<strong>标签里出现过该词</strong>」与「<strong>未出现</strong>」两组，分别算<strong>展示价均价</strong>，再求差得到金额与比例。
    </p>
    <p className="mb-1 font-medium text-[var(--ink-black)]">注意</p>
    <ul className="mb-0 list-disc space-y-1 pl-4 text-[var(--ink-muted)]">
      <li>这是<strong>描述性对比</strong>，混杂户型、地段、装修等，不等于因果溢价。</li>
      <li>每组至少 3 套才展示；标签写法与词表不一致时可能未计入。</li>
    </ul>
  </div>
);

type DistrictsPanelProps = {
  districtStats: DistrictStats[];
};

/** 商圈名录：行政区/商圈聚合表 + 下钻房源 */
export const DashboardDistrictsPanel: React.FC<DistrictsPanelProps> = ({ districtStats }) => {
  const [listingsModalVisible, setListingsModalVisible] = useState(false);
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [listings, setListings] = useState<ListingItem[]>([]);
  const [listingsLoading, setListingsLoading] = useState(false);

  const handleDistrictClick = useCallback(async (district: string) => {
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
  }, []);

  const columns = useMemo(
    () => [
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
        render: (text: string, record: DistrictStats) => {
          const { label, isMissing } = tradeAreaCellLabel(text);
          return (
            <Button
              type="link"
              title={isMissing ? '该分组房源未维护商圈字段，统计仍按行政区汇总' : undefined}
              className={`h-auto p-0 font-medium hover:!text-[var(--ochre)] ${isMissing ? '!text-[var(--ink-muted)]' : 'text-[var(--ink-black)]'}`}
              onClick={() => handleDistrictClick(record.district)}
            >
              {label}
            </Button>
          );
        },
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
          <Tag className="!border-[rgba(90,138,110,0.35)] !bg-[var(--jade-pale)] !text-[var(--jade)]">
            {text?.toFixed(2) || '-'} 分
          </Tag>
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
    ],
    [handleDistrictClick]
  );

  const tableData = useMemo(
    () =>
      Array.isArray(districtStats)
        ? districtStats.map((item, index) => ({
            key: index.toString(),
            ...item,
          }))
        : [],
    [districtStats]
  );

  return (
    <div className="space-y-10 pb-4 sm:space-y-12">
      <ZenSection title="商圈名录" accent="ink">
        <ZenPanel accent="ink" title="行政区与商圈聚合">
          <div className="-mx-1 overflow-x-auto">
            <Table columns={columns} dataSource={tableData} pagination={false} className="zen-table min-w-[720px]" />
          </div>
        </ZenPanel>
      </ZenSection>

      <Card
        bordered={false}
        className="!rounded-xl !border !border-[var(--paper-warm)] !bg-[var(--paper-cream)]/90 !shadow-[var(--shadow-soft)]"
        styles={{ body: { padding: 'var(--space-lg)' } }}
      >
        <p className="m-0 text-sm leading-relaxed text-[var(--ink-light)]">
          点击商圈名称或房源数量可查看该行政区下样本房源；数据与「市场总览」同源统计口径。
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
                    <div className="mb-1 text-[var(--ink-muted)]">{listingLocationLine(item)}</div>
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

type FacilitiesPanelProps = {
  facilityData: FacilityPremium[];
  facilityLoading: boolean;
};

/** 设施溢价分析表 */
export const DashboardFacilitiesPanel: React.FC<FacilitiesPanelProps> = ({ facilityData, facilityLoading }) => {
  return (
    <div className="space-y-10 pb-4 sm:space-y-12">
      <ZenSection title="设施溢价" accent="jade">
        <ZenPanel
          accent="jade"
          title="设施溢价分析"
          loading={facilityLoading}
          extra={
            <ZenRichTooltip title={FACILITY_PREMIUM_TOOLTIP} placement="left">
              <QuestionCircleOutlined className="cursor-help text-[var(--ink-muted)]" aria-label="设施溢价计算方法" />
            </ZenRichTooltip>
          }
        >
          <Alert
            type="info"
            showIcon
            className="mb-4 !rounded-lg !border-[var(--paper-warm)] !bg-[var(--paper-white)]/90 text-xs leading-relaxed [&_.ant-alert-message]:text-[var(--ink-light)]"
            message={
              <div className="space-y-2">
                <p>
                  下表比较的是当前库内<strong className="text-[var(--ink-black)]">挂牌展示价</strong>：详情标签<strong className="text-[var(--ink-black)]">含有</strong>某设施关键词的房源，与<strong className="text-[var(--ink-black)]">不含</strong>该词的房源，各自<strong className="text-[var(--ink-black)]">算术均价</strong>之差（及相对无该词组的百分比）。
                </p>
                <ul className="mb-0 list-disc space-y-1 pl-4 text-[var(--ink-muted)]">
                  <li>
                    仅统计有效展示价；后端要求「有标签」「无标签」两组均<strong className="text-[var(--ink-black)]">不少于 3 套</strong>才输出该行，以降低偶然波动。
                  </li>
                  <li>
                    标签来自房源 <span className="font-mono text-[11px] text-[var(--ink-black)]">house_tags</span> 解析，与预设词表（如投影、厨房、近地铁等）做匹配；表述不一致时可能未命中。
                  </li>
                  <li>
                    差价反映的是<strong className="text-[var(--ink-black)]">同时期的关联关系</strong>，未控制户型、面积、行政区、商圈、装修档次等，<strong className="text-[var(--ink-black)]">不能</strong>理解为「加装该设施必然带来同等涨幅」。
                  </li>
                </ul>
              </div>
            }
          />
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
                    <Tag className="!border-[var(--paper-warm)] !bg-[var(--paper-cream)] !font-medium !text-[var(--ink-black)]">
                      {text}
                    </Tag>
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
                      <span
                        className={`shrink-0 text-sm font-medium ${val >= 0 ? 'text-[var(--jade)]' : 'text-[var(--ochre)]'}`}
                      >
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
        <div className="flex items-start gap-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--jade-pale)]">
            <span className="text-xs font-semibold text-[var(--jade)]">示</span>
          </div>
          <div className="min-w-0 space-y-2 text-sm leading-relaxed text-[var(--ink-light)]">
            <p className="m-0">
              本页定位为<strong className="text-[var(--ink-black)]">市场粗览与选题参考</strong>，适合看「哪些标签常与更高展示价同框出现」。若要做投资决策或改造回报估算，需结合分层统计、回归或对照样本控制混杂因素。
            </p>
            <p className="m-0 text-xs text-[var(--ink-muted)]">
              与「市场总览」同为演示/样本口径；数据随库内同步更新而变化。
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};
