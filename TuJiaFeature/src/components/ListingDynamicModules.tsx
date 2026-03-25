import React from 'react';
import { Empty, Row, Col, Tag, Typography, Collapse, List, Divider, Image } from 'antd';

const { Text, Title } = Typography;

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="w-1 h-3.5 bg-[#b8956e] rounded-full shrink-0" />
      <span className="text-sm font-medium text-[#1a1a1a]">{children}</span>
    </div>
  );
}

/** 途家 cHotelFacility：null / 空 / 字符串 "None" 等均视为无数据 */
function hasMeaningfulCHotelFacility(v: unknown): boolean {
  if (v == null) return false;
  if (typeof v === 'string') {
    const t = v.trim().toLowerCase();
    return t !== '' && t !== 'none' && t !== 'null' && t !== 'undefined';
  }
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'object') return Object.keys(v as object).length > 0;
  return false;
}

/** 途家酒店类设施：多为 { info: { facilityCategories, condensedFacilities, topTip } } */
function extractCHotelStructuredInfo(cHotel: object): {
  facilityCategories: unknown[];
  condensedFacilities: unknown[] | null;
  topTip: Record<string, unknown> | null;
} | null {
  const root = cHotel as Record<string, unknown>;
  const infoRaw = root.info && typeof root.info === 'object' ? (root.info as Record<string, unknown>) : root;
  const facilityCategories = infoRaw.facilityCategories;
  if (!Array.isArray(facilityCategories)) return null;
  const condensed = infoRaw.condensedFacilities;
  const topTip = infoRaw.topTip && typeof infoRaw.topTip === 'object' ? (infoRaw.topTip as Record<string, unknown>) : null;
  return {
    facilityCategories,
    condensedFacilities: Array.isArray(condensed) ? condensed : null,
    topTip,
  };
}

function CHotelFacilityStructuredView({
  facilityCategories,
  condensedFacilities,
  topTip,
}: {
  facilityCategories: unknown[];
  condensedFacilities: unknown[] | null;
  topTip: Record<string, unknown> | null;
}) {
  return (
    <div className="space-y-5">
      {topTip ? (
        <div className="flex gap-3 rounded-lg border border-[#eee] bg-[#fafafa] px-3 py-2.5">
          {typeof topTip.icon === 'string' && topTip.icon ? (
            <img src={topTip.icon} alt="" className="h-9 w-9 shrink-0 object-contain" loading="lazy" />
          ) : null}
          {typeof topTip.content === 'string' && topTip.content.trim() ? (
            <Text className="text-xs text-[#555] leading-relaxed m-0">{topTip.content.trim()}</Text>
          ) : null}
        </div>
      ) : null}

      {condensedFacilities && condensedFacilities.length > 0 ? (
        <div>
          <Text type="secondary" className="text-xs block mb-2">
            门店设施摘要
          </Text>
          <div className="flex flex-wrap gap-2">
            {condensedFacilities.map((raw, i) => {
              const o = raw as Record<string, unknown>;
              const n = String(o.name ?? '').trim();
              if (!n) return null;
              return (
                <Tag key={`${o.id ?? n}-${i}`} className="!mr-0">
                  {n}
                </Tag>
              );
            })}
          </div>
        </div>
      ) : null}

      {facilityCategories.map((catRaw, ci) => {
        const cat = catRaw as Record<string, unknown>;
        const catName = String(cat.name ?? `分类${ci + 1}`);
        const groups = Array.isArray(cat.groups) ? cat.groups : [];
        if (groups.length === 0) return null;

        return (
          <div key={`${catName}-${ci}`}>
            <Text strong className="text-sm text-[#1a1a1a] block mb-3">
              {catName}
            </Text>
            <div className="space-y-4 pl-0">
              {groups.map((gRaw, gi) => {
                const g = gRaw as Record<string, unknown>;
                const groupName = String(g.name ?? '');
                const facilities = Array.isArray(g.facilities) ? g.facilities : [];
                const details = Array.isArray(g.details) ? g.details : [];
                const desc = typeof g.desc === 'string' ? g.desc.trim() : '';
                const st = g.style && typeof g.style === 'object' ? (g.style as Record<string, unknown>) : null;
                const descColor =
                  st && typeof st.textColor === 'string' && st.textColor.trim() ? String(st.textColor) : '#666';

                if (facilities.length === 0) {
                  return (
                    <div
                      key={`${groupName}-${gi}`}
                      className="rounded-lg border border-[#eee] bg-white px-3 py-2.5"
                    >
                      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                        <span className="text-sm font-medium text-[#1a1a1a]">{groupName || '设施'}</span>
                        {desc ? (
                          <span className="text-xs" style={{ color: descColor }}>
                            {desc}
                          </span>
                        ) : null}
                      </div>
                      {details.length > 0 ? (
                        <dl className="mt-2 mb-0 space-y-1 text-xs text-[#555]">
                          {details.map((dRaw, di) => {
                            const d = dRaw as Record<string, unknown>;
                            const k = String(d.key ?? '').trim();
                            const v = String(d.value ?? '').trim();
                            if (!k && !v) return null;
                            return (
                              <div key={di} className="flex gap-2">
                                <dt className="shrink-0 text-[#999]">{k || '—'}</dt>
                                <dd className="m-0 min-w-0">{v || '—'}</dd>
                              </div>
                            );
                          })}
                        </dl>
                      ) : null}
                    </div>
                  );
                }

                return (
                  <div key={`${groupName}-${gi}`} className="rounded-lg border border-[#eee] bg-[#fafafa] px-3 py-3">
                    <div className="text-sm font-medium text-[#1a1a1a] mb-2">{groupName || '分组'}</div>
                    <div className="space-y-3">
                      {facilities.map((fRaw, fi) => {
                        const f = fRaw as Record<string, unknown>;
                        const fn = String(f.name ?? '').trim();
                        if (!fn) return null;
                        const fst = f.style && typeof f.style === 'object' ? (f.style as Record<string, unknown>) : null;
                        const fc =
                          fst && typeof fst.textColor === 'string' && fst.textColor.trim()
                            ? String(fst.textColor)
                            : undefined;
                        const pics = Array.isArray(f.pictures) ? f.pictures : [];
                        const fd = typeof f.desc === 'string' ? f.desc.trim() : '';

                        return (
                          <div key={`${f.id ?? fn}-${fi}`} className="text-sm">
                            <div className="flex flex-wrap items-center gap-2">
                              <Tag color={fc ? undefined : 'default'} className="!mr-0" style={fc ? { color: fc, borderColor: fc } : undefined}>
                                {fn}
                              </Tag>
                              {fd ? (
                                <Text type="secondary" className="text-xs">
                                  {fd}
                                </Text>
                              ) : null}
                            </div>
                            {pics.length > 0 ? (
                              <div className="flex flex-wrap gap-2 mt-2">
                                {pics.map((pRaw, pi) => {
                                  const p = pRaw as Record<string, unknown>;
                                  const url = typeof p.url === 'string' ? p.url : '';
                                  if (!url) return null;
                                  const alt = typeof p.name === 'string' ? p.name : fn;
                                  return (
                                    <Image
                                      key={pi}
                                      src={url}
                                      alt={alt}
                                      width={88}
                                      height={66}
                                      className="!object-cover rounded border border-[#eee]"
                                      preview={{ mask: '查看' }}
                                    />
                                  );
                                })}
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** 途家 facilityModule：分层展示 */
export function FacilityModulePanel({ data }: { data: Record<string, unknown> | null | undefined }) {
  if (!data || typeof data !== 'object') {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无设施详情数据" />;
  }

  const houseSummary = Array.isArray(data.houseSummary) ? data.houseSummary : null;
  const houseContent = typeof data.houseContent === 'string' ? data.houseContent.trim() : '';
  const houseFacility =
    data.houseFacility && typeof data.houseFacility === 'object'
      ? (data.houseFacility as Record<string, unknown>)
      : null;
  const bedRoomSummary = Array.isArray(data.bedRoomSummary) ? data.bedRoomSummary : null;
  const cHotel = data.cHotelFacility;

  const bedSizeDetailInfo =
    houseFacility && typeof houseFacility.bedSizeDetailInfo === 'object'
      ? (houseFacility.bedSizeDetailInfo as Record<string, unknown>)
      : null;

  const facilityGroups = houseFacility && Array.isArray(houseFacility.houseFacilitys)
    ? (houseFacility.houseFacilitys as unknown[])
    : [];

  const showCHotelJson =
    hasMeaningfulCHotelFacility(cHotel) && typeof cHotel === 'object' && cHotel !== null;
  const showCHotelText =
    hasMeaningfulCHotelFacility(cHotel) && typeof cHotel === 'string';
  const hasAny =
    (houseSummary && houseSummary.length > 0) ||
    houseContent ||
    facilityGroups.length > 0 ||
    (bedRoomSummary && bedRoomSummary.length > 0) ||
    bedSizeDetailInfo ||
    showCHotelJson ||
    showCHotelText;

  if (!hasAny) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无设施详情数据" />;
  }

  return (
    <div className="space-y-6 pb-1">
      {houseSummary && houseSummary.length > 0 ? (
        <section>
          <SectionTitle>户型摘要</SectionTitle>
          <Row gutter={[12, 12]}>
            {houseSummary.map((raw, idx) => {
              const item = raw as Record<string, unknown>;
              const icon = typeof item.icon === 'string' ? item.icon : '';
              const tit = String(item.title ?? '');
              const txt = String(item.text ?? '').trim();
              return (
                <Col xs={24} sm={12} lg={8} key={idx}>
                  <div className="flex gap-3 rounded-lg border border-[#eee] bg-[#fafafa] p-3 h-full">
                    {icon ? (
                      <img src={icon} alt="" className="w-10 h-10 object-contain shrink-0" loading="lazy" />
                    ) : (
                      <div className="w-10 h-10 shrink-0 rounded bg-[#e8e4df]" />
                    )}
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-[#1a1a1a] leading-snug">{tit}</div>
                      {txt ? (
                        <Text type="secondary" className="text-xs block mt-0.5">
                          {txt}
                        </Text>
                      ) : null}
                    </div>
                  </div>
                </Col>
              );
            })}
          </Row>
        </section>
      ) : null}

      {houseContent ? (
        <section>
          <SectionTitle>房屋概况</SectionTitle>
          <div className="text-sm text-[#333] leading-relaxed bg-[#f5f2ed] rounded-lg px-4 py-3">{houseContent}</div>
        </section>
      ) : null}

      {bedSizeDetailInfo ? (
        <section>
          <SectionTitle>床型与入住说明</SectionTitle>
          {Array.isArray(bedSizeDetailInfo.houseTips) && bedSizeDetailInfo.houseTips.length > 0 ? (
            <ul className="text-sm text-[#333] list-disc pl-5 mb-2 space-y-1">
              {(bedSizeDetailInfo.houseTips as unknown[]).map((t, i) => (
                <li key={i}>{String(t)}</li>
              ))}
            </ul>
          ) : null}
          {typeof bedSizeDetailInfo.houseIntroduction === 'string' && bedSizeDetailInfo.houseIntroduction ? (
            <Text type="secondary" className="text-xs block">
              {bedSizeDetailInfo.houseIntroduction}
            </Text>
          ) : null}
        </section>
      ) : null}

      {facilityGroups.length > 0 ? (
        <section>
          <SectionTitle>设施清单</SectionTitle>
          <Text type="secondary" className="text-xs block mb-3">
            绿色为房源已标注提供；灰色删除线为未提供项（以途家详情为准）。
          </Text>
          <Collapse
            bordered={false}
            className="!bg-transparent [&_.ant-collapse-item]:!border-[#eee]"
            defaultActiveKey={facilityGroups.map((_, i) => String(i))}
            items={facilityGroups.map((raw, gi) => {
              const g = raw as Record<string, unknown>;
              const groupName = String(g.groupName ?? `分组${gi + 1}`);
              const facilitys = Array.isArray(g.facilitys) ? g.facilitys : [];
              const gIcon = typeof g.icon === 'string' ? g.icon : '';
              return {
                key: String(gi),
                label: (
                  <div className="flex items-center gap-2">
                    {gIcon ? <img src={gIcon} alt="" className="w-5 h-5 object-contain" loading="lazy" /> : null}
                    <span className="text-[#1a1a1a]">{groupName}</span>
                    <Tag className="!m-0 !text-xs">{facilitys.length} 项</Tag>
                  </div>
                ),
                children: (
                  <div className="flex flex-wrap gap-2">
                    {facilitys.map((fraw, fi) => {
                      const f = fraw as Record<string, unknown>;
                      const name = String(f.name ?? '');
                      const notProvided = f.deleted === true;
                      return (
                        <Tag
                          key={fi}
                          color={notProvided ? 'default' : 'success'}
                          className={
                            notProvided
                              ? '!mr-0 !text-[#999] line-through decoration-[#999] !bg-[#f5f5f5] !border-[#e0e0e0]'
                              : '!mr-0'
                          }
                        >
                          {name}
                          {notProvided ? ' · 无' : ''}
                        </Tag>
                      );
                    })}
                  </div>
                ),
              };
            })}
          />
        </section>
      ) : null}

      {bedRoomSummary && bedRoomSummary.length > 0 ? (
        <section>
          <SectionTitle>卧室与床型</SectionTitle>
          <List
            size="small"
            dataSource={bedRoomSummary}
            renderItem={(raw) => {
              const br = raw as Record<string, unknown>;
              const bedInfos = Array.isArray(br.bedInfos) ? br.bedInfos : [];
              const roomLabel = String(br.title ?? '卧室');
              const num = br.bedRoomNumber != null ? ` #${br.bedRoomNumber}` : '';
              return (
                <List.Item className="!px-0 !border-[#f0f0f0]">
                  <div className="w-full">
                    <Text strong className="text-sm">
                      {roomLabel}
                      {num}
                    </Text>
                    <div className="mt-2 space-y-1">
                      {bedInfos.map((b, bi) => {
                        const info = b as Record<string, unknown>;
                        const bedTitle = String(info.bedTitle ?? '');
                        const bedCount = String(info.bedCount ?? '');
                        const bedType = String(info.bedType ?? '');
                        return (
                          <div key={bi} className="text-sm text-[#555] pl-2 border-l-2 border-[#b8956e]">
                            <span className="font-medium text-[#1a1a1a]">{bedTitle}</span>
                            {bedCount ? <span className="mx-1">{bedCount}</span> : null}
                            {bedType ? <Text type="secondary">{bedType}</Text> : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </List.Item>
              );
            }}
          />
        </section>
      ) : null}

      {showCHotelJson ? (
        <section>
          <SectionTitle>酒店类设施</SectionTitle>
          {(() => {
            const structured =
              cHotel && typeof cHotel === 'object' ? extractCHotelStructuredInfo(cHotel as object) : null;
            const hasStructuredContent =
              structured &&
              ((structured.condensedFacilities && structured.condensedFacilities.length > 0) ||
                (structured.topTip &&
                  typeof structured.topTip.content === 'string' &&
                  structured.topTip.content.trim() !== '') ||
                structured.facilityCategories.some((catRaw) => {
                  const c = catRaw as Record<string, unknown>;
                  const groups = Array.isArray(c.groups) ? c.groups : [];
                  return groups.length > 0;
                }));
            if (structured && hasStructuredContent) {
              return (
                <CHotelFacilityStructuredView
                  facilityCategories={structured.facilityCategories}
                  condensedFacilities={structured.condensedFacilities}
                  topTip={structured.topTip}
                />
              );
            }
            return (
              <pre className="text-xs bg-[#fafafa] p-3 rounded overflow-x-auto m-0">
                {JSON.stringify(cHotel, null, 2)}
              </pre>
            );
          })()}
        </section>
      ) : showCHotelText ? (
        <section>
          <SectionTitle>酒店类设施</SectionTitle>
          <div className="text-sm text-[#333] leading-relaxed">{String(cHotel).trim()}</div>
        </section>
      ) : null}
    </div>
  );
}

/** 途家 commentTagVo：标签数组 { text, texts[], backgroundColor, color, borderColor } */
function CommentTagVoCloud({ vo }: { vo: unknown }) {
  let list: unknown[] | null = null;
  if (Array.isArray(vo)) {
    list = vo;
  } else if (vo && typeof vo === 'object' && Array.isArray((vo as Record<string, unknown>).tags)) {
    list = (vo as Record<string, unknown>).tags as unknown[];
  } else if (vo && typeof vo === 'object' && Array.isArray((vo as Record<string, unknown>).commentTags)) {
    list = (vo as Record<string, unknown>).commentTags as unknown[];
  }

  if (!list || list.length === 0) {
    return (
      <pre className="text-xs bg-[#fafafa] p-3 rounded overflow-x-auto m-0 max-h-48">
        {typeof vo === 'object' ? JSON.stringify(vo, null, 2) : String(vo)}
      </pre>
    );
  }

  const first = list[0];
  if (typeof first !== 'object' || first === null) {
    return (
      <pre className="text-xs bg-[#fafafa] p-3 rounded overflow-x-auto m-0 max-h-48">
        {JSON.stringify(vo, null, 2)}
      </pre>
    );
  }

  const looksLikeTujiaTag = 'text' in first || 'texts' in first;
  if (!looksLikeTujiaTag) {
    return (
      <pre className="text-xs bg-[#fafafa] p-3 rounded overflow-x-auto m-0 max-h-48">
        {JSON.stringify(vo, null, 2)}
      </pre>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {list.map((raw, i) => {
        const t = raw as Record<string, unknown>;
        let label = '';
        if (typeof t.text === 'string' && t.text.trim()) {
          label = t.text.trim();
        } else if (Array.isArray(t.texts)) {
          label = (t.texts as unknown[]).map((x) => String(x ?? '')).join('');
        }
        if (!label) label = `标签${i + 1}`;

        const bg = typeof t.backgroundColor === 'string' ? t.backgroundColor : '#F7F8FC';
        const fg = typeof t.color === 'string' ? t.color : '#666';
        const border =
          typeof t.borderColor === 'string' && t.borderColor !== 'rgba(0,0,0,0)' ? t.borderColor : '#e8e8e8';

        return (
          <span
            key={`${label}-${i}`}
            className="inline-block px-3 py-1.5 rounded-md text-sm border border-solid leading-snug"
            style={{ backgroundColor: bg, color: fg, borderColor: border }}
          >
            {label}
          </span>
        );
      })}
    </div>
  );
}

/**
 * 途家 subScores 多为字符串数组：「维度名 分数」，如 "干净卫生 4.9"；
 * 少数接口可能返回 { name, score } 对象。
 */
function parseSubScoreEntry(raw: unknown, index: number): { name: string; score: string } {
  if (typeof raw === 'string') {
    const t = raw.trim();
    const m = t.match(/^(.+?)\s+(\d+(?:\.\d+)?)\s*$/);
    if (m) {
      return { name: m[1].trim(), score: m[2] };
    }
    return { name: t || `分项${index + 1}`, score: '—' };
  }
  if (raw && typeof raw === 'object') {
    const s = raw as Record<string, unknown>;
    const name = String(
      s.name ?? s.title ?? s.dimensionName ?? s.label ?? s.dimension ?? `分项${index + 1}`
    );
    const score = s.score ?? s.value ?? s.rating ?? s.scoreText;
    return {
      name,
      score: score != null && String(score) !== '' ? String(score) : '—',
    };
  }
  return { name: `分项${index + 1}`, score: '—' };
}

/** 途家 commentModule */
export function CommentModulePanel({ data }: { data: Record<string, unknown> | null | undefined }) {
  if (!data || typeof data !== 'object') {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无评价维度数据" />;
  }

  const overall = data.overall && typeof data.overall === 'object' ? (data.overall as Record<string, unknown>) : null;
  const subScores = Array.isArray(data.subScores) ? data.subScores : null;
  const totalCount = data.totalCount ?? data.totalCountStr;
  const commentTagVo = data.commentTagVo;
  const commentList = Array.isArray(data.commentList) ? data.commentList : null;
  const note = typeof data.commentList_note === 'string' ? data.commentList_note : '';

  const hasAny =
    overall ||
    (subScores && subScores.length) ||
    totalCount != null ||
    commentTagVo != null ||
    (commentList && commentList.length);

  if (!hasAny) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无评价维度数据" />;
  }

  return (
    <div className="space-y-5">
      {overall ? (
        <section>
          <SectionTitle>总体评分</SectionTitle>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {Object.entries(overall).map(([k, v]) => (
              <div key={k}>
                <Text type="secondary" className="text-xs">
                  {k}
                </Text>
                <div className="font-medium text-[#1a1a1a]">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {totalCount != null && String(totalCount) !== '' ? (
        <div className="text-sm">
          <Text type="secondary">评价条数：</Text>
          <Text strong>{String(totalCount)}</Text>
        </div>
      ) : null}

      {subScores && subScores.length > 0 ? (
        <section>
          <SectionTitle>分项得分</SectionTitle>
          <Text type="secondary" className="text-xs block mb-3">
            对应途家评价维度（描述相符、服务、位置、卫生等），分数为平台展示分。
          </Text>
          <Row gutter={[16, 12]}>
            {subScores.map((raw, i) => {
              const { name, score } = parseSubScoreEntry(raw, i);
              return (
                <Col xs={12} sm={8} key={i}>
                  <div className="rounded-lg border border-[#eee] p-3 text-center">
                    <div className="text-lg font-semibold text-[#b8956e]">{score}</div>
                    <div className="text-xs text-[#666] mt-1 leading-snug">{name}</div>
                  </div>
                </Col>
              );
            })}
          </Row>
        </section>
      ) : null}

      {commentTagVo != null ? (
        <section>
          <SectionTitle>评价标签</SectionTitle>
          <Text type="secondary" className="text-xs block mb-3">
            来自途家评价标签云；括号内为提及次数（若有）。
          </Text>
          <CommentTagVoCloud vo={commentTagVo} />
        </section>
      ) : null}

      {commentList && commentList.length > 0 ? (
        <section>
          <SectionTitle>精选短评</SectionTitle>
          {note ? (
            <Text type="secondary" className="text-xs block mb-2">
              {note}
            </Text>
          ) : null}
          <List
            size="small"
            dataSource={commentList}
            renderItem={(raw, i) => {
              const c = raw as Record<string, unknown>;
              const pickStr = (...keys: string[]) => {
                for (const k of keys) {
                  const v = c[k];
                  if (typeof v === 'string' && v.trim()) return v.trim();
                }
                return '';
              };
              const body = pickStr('commentDetail', 'content', 'commentText');
              const translation = pickStr('commentDetailTranslation');
              const userName = pickStr('userName') || `用户${i + 1}`;
              const score =
                c.overall != null && String(c.overall) !== ''
                  ? String(c.overall)
                  : c.averageScore != null && String(c.averageScore) !== ''
                    ? String(c.averageScore)
                    : c.score != null && String(c.score) !== ''
                      ? String(c.score)
                      : '';
              const meta = [pickStr('checkInDate'), pickStr('userTags'), pickStr('orderTotalStayNight')]
                .filter(Boolean)
                .join(' · ');
              return (
                <List.Item className="!items-start !px-0">
                  <div className="w-full">
                    <div className="flex justify-between gap-2 text-xs text-[#999] mb-1">
                      <span>{userName}</span>
                      {score ? <span>{score} 分</span> : null}
                    </div>
                    {meta ? (
                      <div className="text-xs text-[#bbb] mb-1">{meta}</div>
                    ) : null}
                    <p className="text-sm text-[#333] m-0 leading-relaxed whitespace-pre-wrap">
                      {body || '（无正文）'}
                    </p>
                    {translation && translation !== body ? (
                      <p className="text-xs text-[#888] mt-2 mb-0 leading-relaxed border-l-2 border-[#e8e4df] pl-2">
                        译：{translation}
                      </p>
                    ) : null}
                  </div>
                </List.Item>
              );
            }}
          />
        </section>
      ) : null}
    </div>
  );
}

/** 途家标签数组：tagText.text / color / background.color（与房源 house_tags 结构一致） */
function TujiaTagBadgeList({ items }: { items: unknown }) {
  if (items == null) return null;

  if (typeof items === 'string') {
    const t = items.trim();
    return t ? <p className="text-sm text-[#333] m-0">{t}</p> : null;
  }

  let list: unknown[] | null = Array.isArray(items) ? items : null;
  if (!list && items && typeof items === 'object' && 'tagText' in (items as object)) {
    list = [items];
  }
  if (!list || list.length === 0) {
    return (
      <pre className="text-xs bg-[#fafafa] p-2 rounded m-0 overflow-x-auto">
        {JSON.stringify(items, null, 2)}
      </pre>
    );
  }

  const nodes = list.map((raw, i) => {
    const o = raw as Record<string, unknown>;
    const tt =
      o.tagText && typeof o.tagText === 'object' ? (o.tagText as Record<string, unknown>) : null;
    const text = tt && typeof tt.text === 'string' ? tt.text.trim() : '';
    if (!text) return null;

    const color = typeof tt.color === 'string' ? tt.color : '#333333';
    let bg = '#F2F5F7';
    if (tt.background && typeof tt.background === 'object') {
      const c = (tt.background as Record<string, unknown>).color;
      if (typeof c === 'string' && c) bg = c;
    }

    let borderColor = 'transparent';
    if (tt.border && typeof tt.border === 'object') {
      const bc = (tt.border as Record<string, unknown>).color;
      if (typeof bc === 'string' && bc) borderColor = bc;
    }

    const tip =
      typeof o.tagDesc === 'string' && o.tagDesc
        ? o.tagDesc
        : typeof tt.tips === 'string'
          ? tt.tips
          : undefined;

    return (
      <span
        key={`${text}-${i}`}
        className="inline-block px-3 py-1 rounded-md text-sm border border-solid leading-snug"
        style={{ color, backgroundColor: bg, borderColor }}
        title={tip}
      >
        {text}
      </span>
    );
  });

  const filtered = nodes.filter(Boolean);
  if (filtered.length === 0) {
    return (
      <pre className="text-xs bg-[#fafafa] p-2 rounded m-0 overflow-x-auto">
        {JSON.stringify(items, null, 2)}
      </pre>
    );
  }

  return <div className="flex flex-wrap gap-2">{filtered}</div>;
}

/** 途家 landlordModule */
export function LandlordModulePanel({ data }: { data: Record<string, unknown> | null | undefined }) {
  if (!data || typeof data !== 'object') {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无房东/品牌数据" />;
  }

  const hotelName = data.hotelName != null ? String(data.hotelName) : '';
  const landlordLevel = data.landlordLevel != null ? String(data.landlordLevel) : '';
  const hotelTags = data.hotelTags;
  const landlordTag = data.landlordTag;
  const hotelSummary = typeof data.hotelSummary === 'string' ? data.hotelSummary : '';
  const replyFast = data.isReplyTimeMoreThan5Min === false;
  const businessType = data.businessType != null ? String(data.businessType) : '';

  const knownKeys = new Set([
    'hotelId',
    'hotelName',
    'landlordLevel',
    'landlordLevelUrl',
    'hotelTags',
    'landlordTag',
    'hotelSummary',
    'isReplyTimeMoreThan5Min',
    'businessType',
    'topScroll',
    'hotelLogo',
    'landlordBanner',
    'logoAtmosphere',
    'landlordSummaryList',
  ]);
  const restEntries = Object.entries(data).filter(([k, v]) => !knownKeys.has(k) && v != null && v !== '');

  const hasMain = hotelName || landlordLevel || hotelSummary || businessType || hotelTags || landlordTag;

  if (!hasMain && restEntries.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无房东/品牌数据" />;
  }

  return (
    <div className="space-y-5">
      {hasMain ? (
        <section>
          <SectionTitle>房东 / 品牌</SectionTitle>
          <div className="space-y-3 text-sm">
            {hotelName ? (
              <div>
                <Text type="secondary">名称</Text>
                <div className="font-medium text-[#1a1a1a]">{hotelName}</div>
              </div>
            ) : null}
            {landlordLevel ? (
              <div>
                <Text type="secondary">等级</Text>
                <div>
                  <Tag color="gold">{landlordLevel}</Tag>
                </div>
              </div>
            ) : null}
            {businessType ? (
              <div>
                <Text type="secondary">经营类型</Text>
                <div>{businessType}</div>
              </div>
            ) : null}
            <div>
              <Text type="secondary">回复时效</Text>
              <div>{replyFast ? <Tag color="green">通常较快回复</Tag> : <Tag>以平台展示为准</Tag>}</div>
            </div>
            {hotelSummary ? (
              <div>
                <Text type="secondary">简介</Text>
                <p className="text-[#333] mt-1 mb-0 leading-relaxed">{hotelSummary}</p>
              </div>
            ) : null}
            {hotelTags != null ? (
              <div>
                <Text type="secondary" className="block mb-2">
                  品牌标签
                </Text>
                <TujiaTagBadgeList items={hotelTags} />
              </div>
            ) : null}
            {landlordTag != null ? (
              <div>
                <Text type="secondary" className="block mb-2">
                  房东标签
                </Text>
                <TujiaTagBadgeList items={landlordTag} />
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {restEntries.length > 0 ? (
        <section>
          <Divider className="!my-2" />
          <Title level={5} className="!text-xs !mb-2 !font-normal text-[#999]">
            其他字段
          </Title>
          {restEntries.map(([k, v]) => (
            <div key={k} className="mb-2">
              <Text type="secondary" className="text-xs">
                {k}
              </Text>
              <pre className="text-xs bg-[#fafafa] p-2 rounded m-0 mt-0.5 overflow-x-auto max-h-32">
                {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
              </pre>
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}
