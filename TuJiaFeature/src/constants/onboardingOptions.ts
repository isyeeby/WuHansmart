/** 首登调研 / 个人信息页共用选项（与后端 persona_answers 键名一致） */

export type UserRole = 'operator' | 'investor' | 'guest';

export const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'operator', label: '我是民宿/短租房东或代运营（经营者）' },
  { value: 'investor', label: '我主要关注民宿投资与回报（投资者）' },
  {
    value: 'guest',
    label: '我主要浏览房源、看行情或做功课（本系统不提供预订）',
  },
];

export const OPERATOR_LISTING_SCALE = [
  { value: '筹备中暂无上线房源', label: '筹备中暂无上线房源' },
  { value: '1 套', label: '1 套' },
  { value: '2～5 套', label: '2～5 套' },
  { value: '6 套及以上', label: '6 套及以上' },
];

export const OPERATOR_FOCUS = [
  { value: '定价与日历', label: '定价与日历' },
  { value: '竞品与商圈分析', label: '竞品与商圈分析' },
  { value: '房源上架与信息管理', label: '房源上架与信息管理' },
  { value: '数据看板与报表', label: '数据看板与报表' },
];

export const EXPERIENCE_LEVEL = [
  { value: '新手（1 年内）', label: '新手（1 年内）' },
  { value: '熟练（1～3 年）', label: '熟练（1～3 年）' },
  { value: '资深（3 年以上）', label: '资深（3 年以上）' },
];

export const PRIMARY_CITIES = [
  '江汉路',
  '光谷',
  '楚河汉街',
  '街道口',
  '武昌区',
  '洪山区',
  '汉口',
  '其他',
];

export const INVESTMENT_STAGE = [
  { value: '了解观望', label: '了解观望' },
  { value: '已看房或谈判中', label: '已看房或谈判中' },
  { value: '已持有房源', label: '已持有房源' },
  { value: '已委托运营', label: '已委托运营' },
];

export const BUDGET_TIER = [
  { value: '不限', label: '不限' },
  { value: '80 万以下', label: '80 万以下' },
  { value: '80～150 万', label: '80～150 万' },
  { value: '150～300 万', label: '150～300 万' },
  { value: '300 万以上', label: '300 万以上' },
];

export const INVESTOR_PRIORITIES = [
  { value: '年化收益与现金流', label: '年化收益与现金流' },
  { value: '入住率与淡旺季', label: '入住率与淡旺季' },
  { value: '地段与升值', label: '地段与升值' },
  { value: '合规与风险', label: '合规与风险' },
  { value: '托管省心程度', label: '托管省心程度' },
];

export const HOLD_HORIZON = [
  { value: '2 年内', label: '2 年内' },
  { value: '2～5 年', label: '2～5 年' },
  { value: '5 年以上', label: '5 年以上' },
  { value: '尚未考虑', label: '尚未考虑' },
];

/**
 * 存 users.travel_purpose，供推荐匹配 scene_scores；非「预订意图」，仅表示浏览/参考时偏好的房源场景。
 * value 与后端 recommend_travel、LISTING_SCENE 键一致，勿改。
 */
export const GUEST_TRAVEL_PURPOSE = [
  { value: '情侣', label: '更关注情侣/双人向房源' },
  { value: '家庭', label: '更关注家庭亲子向房源' },
  { value: '商务', label: '更关注商务向房源' },
  { value: '考研', label: '更关注学习/考试陪护向房源' },
  { value: '团建聚会', label: '更关注团建聚会向房源' },
  { value: '医疗陪护', label: '更关注医疗陪护向房源' },
  { value: '宠物友好', label: '更关注宠物友好向房源' },
  { value: '长租', label: '更关注长租向房源' },
  { value: '休闲', label: '更关注休闲度假向房源' },
];

export const GUEST_PRICE_TIER = [
  { value: 'any', label: '不限', min: undefined, max: undefined },
  { value: 'lt200', label: '200 以下', min: undefined, max: 200 },
  { value: '200_400', label: '200～400', min: 200, max: 400 },
  { value: '400_700', label: '400～700', min: 400, max: 700 },
  { value: 'gt700', label: '700 以上', min: 700, max: 50000 },
];

export const DISTRICT_OPTIONS = ['江汉路', '光谷', '楚河汉街', '街道口', '武昌区', '洪山区', '不限'];

export const FACILITY_OPTIONS = ['投影', '厨房', '洗衣机', '停车位', 'WiFi', '空调', '宠物'];

export const ACQUISITION_CHANNEL = [
  { value: '朋友推荐', label: '朋友推荐' },
  { value: '搜索', label: '搜索' },
  { value: '社交媒体', label: '社交媒体' },
  { value: '线下活动', label: '线下活动' },
  { value: '其他', label: '其他' },
];

export const CONTENT_INTERESTS = [
  { value: '新品与功能更新', label: '新品与功能更新' },
  { value: '行业数据与报告', label: '行业数据与报告' },
  { value: '运营技巧', label: '运营技巧' },
  { value: '投资案例', label: '投资案例' },
];
