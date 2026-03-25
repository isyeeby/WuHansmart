from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

# ============================================================
# 房源相关模型
# ============================================================

class ListingBase(BaseModel):
    """房源基础信息"""
    unit_id: str
    title: str
    district: str
    trade_area: Optional[str] = None
    final_price: float
    original_price: Optional[float] = None
    discount_rate: Optional[float] = None
    rating: Optional[float] = None
    favorite_count: Optional[int] = None
    pic_count: Optional[int] = None
    cover_image: Optional[str] = None
    house_tags: Optional[str] = None
    comment_brief: Optional[str] = None
    bedroom_count: Optional[int] = None
    bed_count: Optional[int] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    # 离线流水线按医院 POI 写入；无坐标或未跑流水线时为 null
    nearest_hospital_km: Optional[float] = None
    nearest_hospital_name: Optional[str] = None


class ListingResponse(ListingBase):
    """房源详情响应"""
    class Config:
        from_attributes = True


class ListingListItem(ListingBase):
    """房源列表项（不含详情页大三块 JSON，减轻列表 payload）"""

    class Config:
        from_attributes = True


class ListingDetailResponse(ListingBase):
    """房源详情（含 dynamicModule 三模块解析结果）"""
    facility_module: Optional[Dict[str, Any]] = None
    comment_module: Optional[Dict[str, Any]] = None
    landlord_module: Optional[Dict[str, Any]] = None
    detail_modules_note: Optional[str] = Field(
        default="以下为途家详情页 dynamicModule 快照（爬取时点）；评价与标签为平台展示口径，非订单验证数据。"
    )

    class Config:
        from_attributes = True


class ListingListRequest(BaseModel):
    """房源列表请求"""
    district: Optional[str] = None
    business_circle: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    tags: Optional[List[str]] = None
    bedroom_count: Optional[int] = None
    sort_by: Optional[str] = "favorite_count"  # price_asc, price_desc, rating, favorite_count
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class ListingListResponse(BaseModel):
    """房源列表响应"""
    total: int
    page: int
    size: int
    items: List[ListingListItem]


class ListingGalleryResponse(BaseModel):
    """房源图片画廊"""
    unit_id: str
    title: str
    total_pics: int
    categories: Dict[str, List[str]]  # 客厅、卧室、厨房、卫生间、阳台、外景


class PriceCalendarItem(BaseModel):
    """价格日历单项"""
    date: str  # YYYY-MM-DD
    price: float
    can_booking: bool


class PriceCalendarResponse(BaseModel):
    """房源价格日历响应"""
    unit_id: str
    title: str
    date_range: Dict[str, str]  # start, end
    calendar: List[PriceCalendarItem]
    price_stats: Dict[str, float]  # min, max, avg


class ListingSimilarResponse(BaseModel):
    """相似房源"""
    unit_id: str
    title: str
    district: str
    final_price: float
    rating: float
    similarity_score: float
    cover_image: Optional[str] = None


# ============================================================
# Dashboard相关模型
# ============================================================

class DashboardSummaryResponse(BaseModel):
    """Dashboard核心指标"""
    total_listings: int
    avg_price: float
    avg_rating: float
    district_count: int
    price_trend: Optional[float] = None  # 环比变化


class PriceTrendPoint(BaseModel):
    """价格趋势点"""
    date: str
    avg_price: float
    listing_count: int


class DashboardPriceTrendResponse(BaseModel):
    """价格趋势响应"""
    district: Optional[str]
    days: int
    data: List[PriceTrendPoint]


class DistrictComparisonItem(BaseModel):
    """商圈对比项"""
    district: str
    trade_area: str
    avg_price: float
    listing_count: int
    avg_rating: float


class DashboardDistrictComparisonResponse(BaseModel):
    """商圈对比响应"""
    items: List[DistrictComparisonItem]


# ============================================================
# 首页 Dashboard KPI 相关模型
# ============================================================

class DashboardKPIResponse(BaseModel):
    """KPI 核心指标响应"""
    total_listings: int = Field(..., description="平台总房源数")
    avg_price: float = Field(..., description="全市平均房价（元/晚）")
    price_change_percent: float = Field(..., description="价格环比变化百分比")
    district_count: int = Field(..., description="覆盖商圈/行政区数量")
    occupancy_rate: float = Field(..., description="需求热度指数（启发式，非订单入住率）")
    avg_roi: float = Field(..., description="市场吸引力指数（启发式，非财务 ROI）")
    kpi_definitions: Optional[Dict[str, str]] = Field(
        default=None,
        description="各字段口径说明，供前端展示",
    )


class HeatmapPoint(BaseModel):
    """热力图数据点"""
    name: str = Field(..., description="商圈名称")
    x: float = Field(..., ge=0, le=100, description="横坐标位置（0-100，保留小数避免网格重叠）")
    y: float = Field(..., ge=0, le=100, description="纵坐标位置（0-100，保留小数避免网格重叠）")
    value: int = Field(..., ge=0, le=100, description="热度值（0-100）")


class DashboardHeatmapResponse(BaseModel):
    """商圈热力图响应"""
    data: List[HeatmapPoint]
    series_note: Optional[str] = Field(
        default=None,
        description="数据生成说明：如使用真实经纬度均值或行政区占位网格",
    )


class TopDistrictItem(BaseModel):
    """热门商圈排行项"""
    name: str = Field(..., description="商圈名称")
    heat: int = Field(..., ge=0, le=100, description="热度值（0-100）")
    avg_price: float = Field(..., description="该商圈平均房价")
    price_trend: float = Field(..., description="价格趋势（百分比，可为负数）")
    listing_count: int = Field(..., description="该商圈房源数量")


class DashboardTopDistrictsResponse(BaseModel):
    """热门商圈排行响应"""
    items: List[TopDistrictItem]


# ============================================================
# 商圈分析相关模型
# ============================================================

class DistrictStatsResponse(BaseModel):
    """商圈统计"""
    district: str
    trade_area: str
    listing_count: int
    avg_price: float
    avg_rating: float
    avg_favorite_count: float
    avg_comment_count: float
    avg_bedroom_count: float
    min_price: float
    max_price: float


class FacilityPremiumItem(BaseModel):
    """设施溢价项"""
    facility_name: str
    avg_price_with: float
    avg_price_without: float
    premium_amount: float
    premium_percent: float
    listing_count: int


class FacilityPremiumResponse(BaseModel):
    """设施溢价分析响应"""
    facilities: List[FacilityPremiumItem]


class PriceDistributionPoint(BaseModel):
    """价格分布点"""
    price_range: str
    count: int
    percent: float


class PriceDistributionResponse(BaseModel):
    """价格分布响应"""
    district: Optional[str]
    distribution: List[PriceDistributionPoint]


# ============================================================
# 我的房源相关模型
# ============================================================

class MyListingCreate(BaseModel):
    """创建我的房源"""
    title: str = Field(..., min_length=1, max_length=255)
    district: str
    business_circle: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    bedroom_count: int = Field(1, ge=1)
    bed_count: int = Field(1, ge=1)
    bathroom_count: int = Field(1, ge=1)
    max_guests: int = Field(2, ge=1)
    area: Optional[float] = None
    current_price: float = Field(..., gt=0)
    style_tags: Optional[List[str]] = None
    facility_tags: Optional[List[str]] = None
    location_tags: Optional[List[str]] = None
    crowd_tags: Optional[List[str]] = None


class MyListingResponse(MyListingCreate):
    """我的房源响应"""
    id: int
    user_id: int
    cover_image: Optional[str] = None
    images: Optional[List[str]] = None
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MyListingUpdate(BaseModel):
    """更新我的房源 - 所有字段都是可选的"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    district: Optional[str] = None
    business_circle: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    bedroom_count: Optional[int] = Field(None, ge=1)
    bed_count: Optional[int] = Field(None, ge=1)
    bathroom_count: Optional[int] = Field(None, ge=1)
    max_guests: Optional[int] = Field(None, ge=1)
    area: Optional[float] = None
    current_price: Optional[float] = Field(None, gt=0)
    style_tags: Optional[List[str]] = None
    facility_tags: Optional[List[str]] = None
    location_tags: Optional[List[str]] = None
    crowd_tags: Optional[List[str]] = None
    cover_image: Optional[str] = None
    images: Optional[List[str]] = None
    status: Optional[str] = None


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


class CompetitorItem(BaseModel):
    """竞品项"""
    unit_id: str
    title: str
    district: str
    final_price: float
    rating: float
    favorite_count: int
    house_tags: Optional[str] = None
    tag_list: Optional[List[str]] = None
    similarity_score: float
    distance_km: Optional[float] = Field(
        default=None,
        description="与我的房源直线距离（公里），仅当双方均有有效经纬度时给出",
    )


class ComparisonReport(BaseModel):
    """竞品对比报告"""
    my_listing: MyListingResponse
    market_position: Dict[str, Any]
    competitors: List[CompetitorItem]
    analysis: Dict[str, List[str]]


class PriceSuggestionResponse(BaseModel):
    """定价建议响应"""
    current_price: float
    suggested_price: float
    price_difference: float
    difference_percent: float
    suggestion: str
    reasoning: List[str]
    confidence: float


# ============================================================
# 标签库相关模型
# ============================================================

class TagCategoryResponse(BaseModel):
    """标签分类"""
    category: str  # style, facility, location, crowd
    tags: List[str]


class PopularTagItem(BaseModel):
    """热门标签项"""
    tag_name: str
    usage_count: int
    avg_price: float
    percent: float


class PopularTagsResponse(BaseModel):
    """热门标签响应"""
    district: Optional[str]
    tags: List[PopularTagItem]


# ============================================================
# 原有的模型（保留）
# ============================================================

class PredictionRequest(BaseModel):
    district: str
    trade_area: Optional[str] = None  # 商圈（更精细的位置）
    unit_id: Optional[str] = Field(
        default=None,
        description="若提供，则从 price_calendars 聚合日历特征参与定价（与训练一致）",
    )
    room_type: str
    capacity: int = Field(..., ge=1, le=20, description="可住人数")
    bedrooms: int = Field(..., ge=0, description="卧室数")
    bed_count: int = Field(1, ge=1, le=20, description="床位数")
    bathrooms: Optional[int] = Field(1, ge=0)
    area: Optional[int] = Field(50, ge=10, le=500, description="面积(平方米)")
    has_wifi: bool = True
    has_kitchen: bool = False
    has_air_conditioning: bool = True
    has_projector: bool = False
    has_bathtub: bool = False
    has_washer: bool = False
    has_smart_lock: bool = False
    has_tv: bool = False
    has_heater: bool = False
    near_metro: bool = False
    has_elevator: bool = False
    has_fridge: bool = False
    has_view: bool = False  # 江景/湖景（景观房）
    view_type: Optional[str] = None  # 景观类型: 江景/湖景/山景
    has_terrace: bool = False  # 观景露台
    has_mahjong: bool = False  # 麻将机
    has_big_living_room: bool = False  # 大客厅
    has_parking: bool = False  # 停车位
    is_weekend: bool = False
    is_holiday: bool = False
    # 来自 listings 表时可传入，与 ModelManager 推理特征对齐
    rating: Optional[float] = Field(None, ge=0, le=5, description="房源评分")
    favorite_count: Optional[int] = Field(None, ge=0, description="收藏数")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")

class PredictionResponse(BaseModel):
    predicted_price: float
    confidence_interval: List[float]
    features_used: dict
    district_avg: Optional[float]
    suggestion: Optional[str]

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    phone: Optional[str] = None
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

UserRoleType = Literal["operator", "investor", "guest"]


class UserUpdate(BaseModel):
    phone: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    preferred_district: Optional[str] = None
    preferred_price_min: Optional[float] = None
    preferred_price_max: Optional[float] = None
    travel_purpose: Optional[str] = None
    required_facilities: Optional[List[str]] = None
    user_role: Optional[str] = None
    persona_answers: Optional[Dict[str, Any]] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    email: Optional[str] = None
    preferred_district: Optional[str] = None
    preferred_price_min: Optional[float] = None
    preferred_price_max: Optional[float] = None
    travel_purpose: Optional[str] = None
    required_facilities: Optional[List[str]] = None
    user_role: Optional[str] = None
    onboarding_completed: bool = False
    onboarding_skipped_at: Optional[datetime] = None
    persona_answers: Optional[Dict[str, Any]] = None
    persona_summary: Optional[str] = None

    class Config:
        from_attributes = True

class UserPreferences(BaseModel):
    preferred_district: Optional[str] = None
    preferred_price_min: Optional[float] = None
    preferred_price_max: Optional[float] = None
    travel_purpose: Optional[str] = None
    required_facilities: Optional[List[str]] = None


class OnboardingComplete(BaseModel):
    """首登调研提交（完成）"""
    user_role: UserRoleType
    persona_answers: Dict[str, Any] = Field(default_factory=dict)
    preferred_district: Optional[str] = None
    travel_purpose: Optional[str] = None
    required_facilities: Optional[List[str]] = None
    preferred_price_min: Optional[float] = None
    preferred_price_max: Optional[float] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

class FavoriteCreate(BaseModel):
    unit_id: str
    folder_name: Optional[str] = "默认收藏夹"
    price_alert_enabled: Optional[bool] = False

class FavoriteResponse(BaseModel):
    id: int
    user_id: int
    unit_id: str
    folder_name: Optional[str] = "默认收藏夹"
    price_alert_enabled: Optional[bool] = False
    alert_threshold: Optional[float] = None
    created_at: datetime
    class Config:
        from_attributes = True

class FavoriteFolder(BaseModel):
    name: str
    count: int

class ViewHistoryCreate(BaseModel):
    unit_id: str
    listing_data: Optional[dict] = None

class ViewHistoryResponse(BaseModel):
    id: int
    unit_id: str
    view_count: int
    last_viewed_at: datetime
    class Config:
        from_attributes = True

class RecommendationRequest(BaseModel):
    user_id: Optional[str] = None
    district: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    capacity: Optional[int] = None
    top_k: int = Field(10, ge=1, le=50)

class HomestayRecommendation(BaseModel):
    id: str
    title: str
    district: str
    price: float
    rating: float
    match_score: float
    reason: Optional[str] = None
    cover_image: Optional[str] = None
    facilities: Optional[List[str]] = None
    unit_id: Optional[str] = None
    nearest_hospital_km: Optional[float] = Field(
        default=None,
        description="至最近医院 POI 直线距离 km（库字段，仅展示；医疗目的排序加分见推荐服务实现）",
    )
    nearest_hospital_name: Optional[str] = Field(
        default=None,
        description="最近医院 POI 名称（与 nearest_hospital_km 对应，来自离线 POI 表）",
    )

class RecommendationResponse(BaseModel):
    recommendations: List[HomestayRecommendation]
