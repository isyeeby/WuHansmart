"""SQLAlchemy database models and connection for user management.
Supports SQLite (default) and MySQL.
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Boolean, Float,
    ForeignKey, Text, Numeric, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.types import TypeDecorator, Text as SQLText
from typing import Generator, Optional, List, Any
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# JSON类型处理（兼容SQLite和MySQL）
# =============================================================================
class JSONType(TypeDecorator):
    """通用JSON类型，底层存储为TEXT。"""
    impl = SQLText

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[Any]:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value


# =============================================================================
# 数据库连接配置
# =============================================================================
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # MySQL configuration（池参数来自 Settings，勿在此硬编码与 .env 不一致）
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.MYSQL_POOL_SIZE,
        max_overflow=settings.MYSQL_MAX_OVERFLOW,
        pool_recycle=settings.MYSQL_POOL_RECYCLE,
        pool_timeout=settings.MYSQL_POOL_TIMEOUT,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# =============================================================================
# 0. 房源数据表 (从Hive同步)
# =============================================================================
class Listing(Base):
    """房源数据表 - 从Hive ADS层同步"""
    __tablename__ = "listings"

    unit_id = Column(String(50), primary_key=True, index=True, comment="房源ID")
    title = Column(String(500), comment="房源标题")
    district = Column(String(50), index=True, comment="行政区")
    trade_area = Column(String(100), comment="商圈")
    final_price = Column(Numeric(10, 2), comment="最终价格")
    original_price = Column(Numeric(10, 2), comment="原价")
    discount_rate = Column(Numeric(5, 4), comment="折扣率")
    rating = Column(Numeric(2, 1), comment="评分")
    favorite_count = Column(Integer, comment="收藏数")
    pic_count = Column(Integer, comment="图片数量")
    cover_image = Column(String(500), comment="封面图")
    house_pics = Column(Text, comment="完整图片列表JSON")
    house_tags = Column(Text, comment="标签JSON")
    comment_brief = Column(String(500), comment="评论摘要")
    bedroom_count = Column(Integer, comment="卧室数")
    bed_count = Column(Integer, comment="床位数")
    area = Column(Numeric(8, 2), comment="面积")
    capacity = Column(Integer, comment="可住人数")
    house_type = Column(String(50), comment="房屋类型(整套/单间/复式等)")
    longitude = Column(Numeric(12, 8), comment="经度")
    latitude = Column(Numeric(12, 8), comment="纬度")
    # tags JSON 详情页三模块（途家 dynamicModule，截断后入库）
    facility_module_json = Column(Text, nullable=True, comment="facilityModule JSON")
    comment_module_json = Column(Text, nullable=True, comment="commentModule JSON")
    landlord_module_json = Column(Text, nullable=True, comment="landlordModule JSON")
    # TF-IDF+LR 房源场景多标签概率，与 travel_purpose 键一致
    scene_scores = Column(JSONType, nullable=True, comment="场景标签概率 JSON")
    # 至 data/hospital_poi_wuhan.json 中最近医院 POI 的 Haversine 距离（km），流水线回写
    nearest_hospital_km = Column(Numeric(9, 3), nullable=True, comment="至最近POI医院直线距离km")
    nearest_hospital_name = Column(String(200), nullable=True, comment="最近POI医院名称")


# =============================================================================
# 1. 价格日历表
# =============================================================================
class PriceCalendar(Base):
    """房源价格日历 - 每日价格和可预订状态"""
    __tablename__ = "price_calendars"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(String(50), index=True, nullable=False, comment="房源ID")
    date = Column(String(10), nullable=False, comment="日期 YYYY-MM-DD")
    price = Column(Numeric(10, 2), nullable=False, comment="当日价格")
    can_booking = Column(Integer, default=1, comment="是否可预订: 0-不可, 1-可")
    
    # 联合唯一索引
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )


# =============================================================================
# 1. 用户表 (扩展字段)
# =============================================================================
class User(Base):
    """User model for authentication and profile management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=True, comment="邮箱（可选）")
    phone = Column(String(20), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # User preferences for recommendations
    preferred_district = Column(String(50), nullable=True)      # 偏好商圈
    preferred_price_min = Column(Numeric(10, 2), nullable=True)  # 最低价格偏好
    preferred_price_max = Column(Numeric(10, 2), nullable=True)  # 最高价格偏好
    travel_purpose = Column(String(20), nullable=True)          # 浏览/推荐偏好场景（中或英 key），非预订意图；见 recommend_travel、scene_scores
    required_facilities = Column(JSONType, nullable=True)       # 必带设施列表 ["投影", "厨房"]

    # 首登调研与用户画像
    user_role = Column(String(20), nullable=True)               # operator | investor | guest
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    onboarding_skipped_at = Column(DateTime, nullable=True)
    persona_answers = Column(JSONType, nullable=True)             # 分身份问卷 JSON
    persona_summary = Column(Text, nullable=True)                 # 规则生成的可读摘要

    # Relationships
    my_listings = relationship("MyListing", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    view_history = relationship("UserViewHistory", back_populates="user", cascade="all, delete-orphan")


# =============================================================================
# 2. 我的房源表
# =============================================================================
class MyListing(Base):
    """用户自己的房源信息，用于竞品分析和定价预测。"""
    __tablename__ = "my_listings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 基础信息
    title = Column(String(255), nullable=False, comment="房源名称")
    city = Column(String(50), nullable=True, comment="城市")
    district = Column(String(50), nullable=False, comment="行政区")
    business_circle = Column(String(100), nullable=True, comment="商圈")
    address = Column(Text, nullable=True, comment="详细地址")
    
    # 地理位置
    longitude = Column(Numeric(12, 8), nullable=True, comment="经度")
    latitude = Column(Numeric(12, 8), nullable=True, comment="纬度")
    
    # 户型信息
    bedroom_count = Column(Integer, default=1, comment="卧室数")
    bed_count = Column(Integer, default=1, comment="床位数")
    bathroom_count = Column(Integer, default=1, comment="卫生间数")
    max_guests = Column(Integer, default=2, comment="容纳人数")
    area = Column(Numeric(5, 2), nullable=True, comment="面积(㎡)")
    
    # 价格
    current_price = Column(Numeric(10, 2), nullable=False, comment="当前定价")
    
    # 标签
    style_tags = Column(JSONType, nullable=True, comment="风格标签")
    facility_tags = Column(JSONType, nullable=True, comment="设施标签")
    location_tags = Column(JSONType, nullable=True, comment="位置标签")
    crowd_tags = Column(JSONType, nullable=True, comment="人群标签")
    
    # 图片
    cover_image = Column(String(500), nullable=True, comment="封面图")
    images = Column(JSONType, nullable=True, comment="图片列表")
    
    # 状态
    status = Column(String(20), default="active", comment="状态: active/inactive/deleted")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="my_listings")

    def to_dict(self) -> dict:
        """转换为字典（方便序列化）。"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "city": self.city,
            "district": self.district,
            "business_circle": self.business_circle,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude else None,
            "latitude": float(self.latitude) if self.latitude else None,
            "bedroom_count": self.bedroom_count,
            "bed_count": self.bed_count,
            "bathroom_count": self.bathroom_count,
            "max_guests": self.max_guests,
            "area": float(self.area) if self.area else None,
            "current_price": float(self.current_price) if self.current_price else None,
            "style_tags": self.style_tags or [],
            "facility_tags": self.facility_tags or [],
            "location_tags": self.location_tags or [],
            "crowd_tags": self.crowd_tags or [],
            "cover_image": self.cover_image,
            "images": self.images or [],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# =============================================================================
# 3. 收藏夹表
# =============================================================================
class Favorite(Base):
    """用户收藏的房源。"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    unit_id = Column(String(50), nullable=False, index=True, comment="房源ID")
    folder_name = Column(String(100), nullable=False, default="默认收藏夹", comment="收藏夹名称")
    listing_data = Column(JSONType, nullable=True, comment="房源快照JSON")
    price_alert_enabled = Column(Boolean, default=False, comment="是否启用价格提醒")
    alert_threshold = Column(Numeric(5, 4), nullable=True, comment="价格变动阈值如0.1=10%")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="favorites")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "unit_id": self.unit_id,
            "folder_name": self.folder_name,
            "listing_data": self.listing_data,
            "price_alert_enabled": self.price_alert_enabled,
            "alert_threshold": float(self.alert_threshold) if self.alert_threshold is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# 4. 用户浏览历史表
# =============================================================================
class UserViewHistory(Base):
    """用户浏览记录，用于协同过滤推荐。"""
    __tablename__ = "user_view_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    unit_id = Column(String(50), nullable=False, index=True, comment="浏览的房源ID")
    view_duration = Column(Integer, default=0, comment="浏览时长（秒）")
    view_count = Column(Integer, default=1, comment="浏览次数")
    listing_data = Column(JSONType, nullable=True, comment="房源快照")
    last_viewed_at = Column(DateTime, default=datetime.utcnow, comment="最近浏览时间")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="view_history")


# =============================================================================
# 5. 价格预测记录表
# =============================================================================
class PricePredictionLog(Base):
    """价格预测记录，用于模型优化和预测历史查询。"""
    __tablename__ = "price_prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # 输入特征
    input_features = Column(JSONType, nullable=False, comment="完整的输入特征")
    district = Column(String(50), nullable=False, comment="商圈")
    bedrooms = Column(Integer, comment="卧室数")
    area = Column(Numeric(8, 2), comment="面积")
    facilities = Column(JSONType, comment="设施")

    # 预测结果
    predicted_price = Column(Numeric(10, 2), nullable=False, comment="预测价格")
    confidence_lower = Column(Numeric(10, 2), comment="置信区间下限")
    confidence_upper = Column(Numeric(10, 2), comment="置信区间上限")

    # 模型信息
    model_version = Column(String(20), default="v1.0", comment="模型版本")
    is_mock = Column(Boolean, default=True, comment="是否Mock预测")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "input_features": self.input_features,
            "district": self.district,
            "bedrooms": self.bedrooms,
            "area": float(self.area) if self.area else None,
            "facilities": self.facilities,
            "predicted_price": float(self.predicted_price),
            "confidence_lower": float(self.confidence_lower) if self.confidence_lower else None,
            "confidence_upper": float(self.confidence_upper) if self.confidence_upper else None,
            "model_version": self.model_version,
            "is_mock": self.is_mock,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# 7. 推荐结果缓存表
# =============================================================================
class RecommendationResult(Base):
    """推荐结果缓存（协同过滤结果）。"""
    __tablename__ = "recommendation_results"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    unit_id = Column(String(50), nullable=False, comment="推荐房源ID")
    match_score = Column(Numeric(4, 3), comment="匹配度分数（0-1）")
    reason = Column(String(200), comment="推荐理由")
    algorithm = Column(String(20), default="cf", comment="推荐算法：cf/content/popular")
    is_clicked = Column(Boolean, default=False, comment="是否被点击")
    is_mock = Column(Boolean, default=True, comment="是否Mock推荐")

    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# 8. API调用日志表
# =============================================================================
class APILog(Base):
    """API调用日志。"""
    __tablename__ = "api_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    endpoint = Column(String(200), nullable=False, comment="接口路径")
    method = Column(String(10), nullable=False, comment="HTTP方法")
    request_params = Column(JSONType, comment="请求参数")
    response_status = Column(Integer, comment="响应状态码")
    response_time_ms = Column(Integer, comment="响应时间（毫秒）")
    client_ip = Column(String(50), comment="客户端IP")

    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# 数据库工具函数
# =============================================================================
def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_extra_columns() -> None:
    """为已存在的 MySQL/SQLite 表补充 ORM 新增列（create_all 不会 ALTER 旧表）。"""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
        dialect = engine.dialect.name
    except Exception as e:
        logger.warning("Schema inspect skipped: %s", e)
        return

    def run(sql: str) -> None:
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception as ex:
            if "duplicate" in str(ex).lower() or "already exists" in str(ex).lower():
                return
            logger.debug("ALTER optional: %s -> %s", sql[:80], ex)

    if "users" in insp.get_table_names():
        ucols = {c["name"] for c in insp.get_columns("users")}
        if "email" not in ucols:
            if dialect == "sqlite":
                run("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
            else:
                run("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL COMMENT '邮箱（可选）'")
        user_extra = [
            ("user_role", "VARCHAR(20) NULL COMMENT 'operator|investor|guest'", "VARCHAR(20)"),
            (
                "onboarding_completed",
                "TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否完成首登调研'",
                "INTEGER NOT NULL DEFAULT 0",
            ),
            (
                "onboarding_skipped_at",
                "DATETIME NULL COMMENT '跳过调研时间'",
                "DATETIME",
            ),
            ("persona_answers", "TEXT NULL COMMENT '问卷JSON'", "TEXT"),
            ("persona_summary", "TEXT NULL COMMENT '用户画像摘要'", "TEXT"),
        ]
        for col_name, mysql_ddl, sqlite_ddl in user_extra:
            if col_name not in ucols:
                if dialect == "sqlite":
                    run(f"ALTER TABLE users ADD COLUMN {col_name} {sqlite_ddl}")
                else:
                    run(f"ALTER TABLE users ADD COLUMN {col_name} {mysql_ddl}")

    if "favorites" in insp.get_table_names():
        fcols = {c["name"] for c in insp.get_columns("favorites")}
        if "folder_name" not in fcols:
            if dialect == "sqlite":
                run("ALTER TABLE favorites ADD COLUMN folder_name VARCHAR(100) DEFAULT '默认收藏夹'")
            else:
                run(
                    "ALTER TABLE favorites ADD COLUMN folder_name VARCHAR(100) NOT NULL DEFAULT '默认收藏夹' "
                    "COMMENT '收藏夹名称'"
                )
        if "listing_data" not in fcols:
            if dialect == "sqlite":
                run("ALTER TABLE favorites ADD COLUMN listing_data TEXT")
            else:
                run("ALTER TABLE favorites ADD COLUMN listing_data TEXT NULL COMMENT '房源快照JSON'")
        if "price_alert_enabled" not in fcols:
            if dialect == "sqlite":
                run("ALTER TABLE favorites ADD COLUMN price_alert_enabled INTEGER DEFAULT 0")
            else:
                run(
                    "ALTER TABLE favorites ADD COLUMN price_alert_enabled TINYINT(1) NOT NULL DEFAULT 0 "
                    "COMMENT '是否启用价格提醒'"
                )
        if "alert_threshold" not in fcols:
            if dialect == "sqlite":
                run("ALTER TABLE favorites ADD COLUMN alert_threshold NUMERIC(5,4)")
            else:
                run(
                    "ALTER TABLE favorites ADD COLUMN alert_threshold DECIMAL(5,4) NULL "
                    "COMMENT '价格变动阈值'"
                )

    if "user_view_history" in insp.get_table_names():
        hcols = {c["name"] for c in insp.get_columns("user_view_history")}
        if "view_count" not in hcols:
            if dialect == "sqlite":
                run("ALTER TABLE user_view_history ADD COLUMN view_count INTEGER DEFAULT 1")
            else:
                run(
                    "ALTER TABLE user_view_history ADD COLUMN view_count INT NOT NULL DEFAULT 1 "
                    "COMMENT '浏览次数'"
                )
        if "listing_data" not in hcols:
            if dialect == "sqlite":
                run("ALTER TABLE user_view_history ADD COLUMN listing_data TEXT")
            else:
                run(
                    "ALTER TABLE user_view_history ADD COLUMN listing_data TEXT NULL COMMENT '房源快照'"
                )
        if "last_viewed_at" not in hcols:
            if dialect == "sqlite":
                run("ALTER TABLE user_view_history ADD COLUMN last_viewed_at DATETIME")
            else:
                run(
                    "ALTER TABLE user_view_history ADD COLUMN last_viewed_at DATETIME NULL "
                    "COMMENT '最近浏览时间'"
                )

    if "listings" in insp.get_table_names():
        lcols = {c["name"] for c in insp.get_columns("listings")}
        for col_name, mysql_ddl, sqlite_ddl in (
            ("facility_module_json", "LONGTEXT NULL COMMENT 'facilityModule JSON'", "TEXT"),
            ("comment_module_json", "LONGTEXT NULL COMMENT 'commentModule JSON'", "TEXT"),
            ("landlord_module_json", "LONGTEXT NULL COMMENT 'landlordModule JSON'", "TEXT"),
            (
                "scene_scores",
                "TEXT NULL COMMENT '场景标签概率 JSON'",
                "TEXT",
            ),
            (
                "nearest_hospital_km",
                "DECIMAL(9,3) NULL COMMENT '至最近POI医院直线距离km'",
                "REAL",
            ),
            (
                "nearest_hospital_name",
                "VARCHAR(200) NULL COMMENT '最近POI医院名称'",
                "VARCHAR(200)",
            ),
        ):
            if col_name not in lcols:
                if dialect == "sqlite":
                    run(f"ALTER TABLE listings ADD COLUMN {col_name} {sqlite_ddl}")
                else:
                    run(f"ALTER TABLE listings ADD COLUMN {col_name} {mysql_ddl}")

    _ensure_performance_indexes(insp, dialect, run)


def _ensure_performance_indexes(insp, dialect: str, run) -> None:
    """为 listings 热点查询补充索引（MySQL；SQLite 跳过）。"""
    if dialect == "sqlite":
        return
    if "listings" not in insp.get_table_names():
        return
    # 复合索引：行政区 + 价格、行政区 + 商圈
    for idx_name, ddl in (
        ("idx_listings_district_price", "CREATE INDEX idx_listings_district_price ON listings (district, final_price)"),
        (
            "idx_listings_district_trade",
            "CREATE INDEX idx_listings_district_trade ON listings (district, trade_area(50))",
        ),
    ):
        try:
            run(ddl)
        except Exception:
            pass


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_extra_columns()
    logger.info("Database tables created successfully")


# =============================================================================
# User CRUD 操作
# =============================================================================
def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    """Get user by phone number."""
    return db.query(User).filter(User.phone == phone).first()


def create_user(db: Session, username: str, hashed_password: str,
                phone: Optional[str] = None, full_name: Optional[str] = None) -> User:
    """Create a new user."""
    db_user = User(
        username=username,
        hashed_password=hashed_password,
        phone=phone,
        full_name=full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def refresh_user_persona_summary(user: User) -> None:
    """根据当前用户字段重写 persona_summary（不提交）。"""
    from app.core.persona import build_persona_summary

    pa = user.persona_answers
    if pa is not None and not isinstance(pa, dict):
        pa = {}
    rf = user.required_facilities
    if rf is not None and not isinstance(rf, list):
        rf = None
    user.persona_summary = build_persona_summary(
        user.user_role,
        pa or {},
        user.travel_purpose,
        user.preferred_district,
        float(user.preferred_price_min) if user.preferred_price_min is not None else None,
        float(user.preferred_price_max) if user.preferred_price_max is not None else None,
        rf,
    )


def update_user_preferences(
    db: Session,
    user_id: int,
    preferred_district: Optional[str] = None,
    preferred_price_min: Optional[float] = None,
    preferred_price_max: Optional[float] = None,
    travel_purpose: Optional[str] = None,
    required_facilities: Optional[List[str]] = None,
    user_role: Optional[str] = None,
    persona_answers: Optional[dict] = None,
) -> Optional[User]:
    """Update user preferences for recommendations and refresh persona summary."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if preferred_district is not None:
            user.preferred_district = preferred_district
        if preferred_price_min is not None:
            user.preferred_price_min = preferred_price_min
        if preferred_price_max is not None:
            user.preferred_price_max = preferred_price_max
        if travel_purpose is not None:
            user.travel_purpose = travel_purpose
        if required_facilities is not None:
            user.required_facilities = required_facilities
        if user_role is not None:
            user.user_role = user_role
        if persona_answers is not None:
            user.persona_answers = persona_answers
        refresh_user_persona_summary(user)
        db.commit()
        db.refresh(user)
    return user


# =============================================================================
# MyListing CRUD 操作
# =============================================================================
def create_my_listing(db: Session, user_id: int, **kwargs) -> MyListing:
    """创建用户的房源。"""
    db_listing = MyListing(user_id=user_id, **kwargs)
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)
    return db_listing


def get_my_listings(db: Session, user_id: int) -> List[MyListing]:
    """获取用户的所有房源。"""
    return db.query(MyListing).filter(MyListing.user_id == user_id).all()


def get_my_listing_by_id(db: Session, listing_id: int, user_id: int) -> Optional[MyListing]:
    """获取单个房源详情。"""
    return db.query(MyListing).filter(
        MyListing.id == listing_id,
        MyListing.user_id == user_id
    ).first()


def update_my_listing(db: Session, listing_id: int, user_id: int, **kwargs) -> Optional[MyListing]:
    """更新房源信息。"""
    listing = db.query(MyListing).filter(
        MyListing.id == listing_id,
        MyListing.user_id == user_id
    ).first()
    if listing:
        for key, value in kwargs.items():
            if hasattr(listing, key):
                setattr(listing, key, value)
        listing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(listing)
    return listing


def delete_my_listing(db: Session, listing_id: int, user_id: int) -> bool:
    """删除房源。"""
    listing = db.query(MyListing).filter(
        MyListing.id == listing_id,
        MyListing.user_id == user_id
    ).first()
    if listing:
        db.delete(listing)
        db.commit()
        return True
    return False


# =============================================================================
# Favorite CRUD 操作
# =============================================================================
def add_favorite(
    db: Session,
    user_id: int,
    unit_id: str,
    folder_name: str = "默认收藏夹",
    listing_data: dict = None
) -> Favorite:
    """添加收藏。"""
    # 检查是否已存在
    existing = db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.unit_id == unit_id,
        Favorite.folder_name == folder_name
    ).first()

    if existing:
        return existing

    db_favorite = Favorite(
        user_id=user_id,
        unit_id=unit_id,
        folder_name=folder_name,
        listing_data=listing_data
    )
    db.add(db_favorite)
    db.commit()
    db.refresh(db_favorite)
    return db_favorite


def remove_favorite(db: Session, user_id: int, favorite_id: int) -> bool:
    """取消收藏。"""
    favorite = db.query(Favorite).filter(
        Favorite.id == favorite_id,
        Favorite.user_id == user_id
    ).first()
    if favorite:
        db.delete(favorite)
        db.commit()
        return True
    return False


def get_user_favorites(
    db: Session,
    user_id: int,
    folder_name: str = None
) -> List[Favorite]:
    """获取用户收藏列表。"""
    query = db.query(Favorite).filter(Favorite.user_id == user_id)
    if folder_name:
        query = query.filter(Favorite.folder_name == folder_name)
    return query.order_by(Favorite.created_at.desc()).all()


def get_favorite_folders(db: Session, user_id: int) -> List[str]:
    """获取用户的收藏夹列表。"""
    folders = db.query(Favorite.folder_name).filter(
        Favorite.user_id == user_id
    ).distinct().all()
    return [f[0] for f in folders]


# =============================================================================
# View History 操作
# =============================================================================
def add_view_history(
    db: Session,
    user_id: int,
    unit_id: str,
    duration: int = 0
) -> UserViewHistory:
    """添加浏览记录。"""
    now = datetime.utcnow()
    db_history = UserViewHistory(
        user_id=user_id,
        unit_id=unit_id,
        view_duration=duration,
        view_count=1,
        last_viewed_at=now,
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history


def get_user_view_history(
    db: Session,
    user_id: int,
    limit: int = 50
) -> List[UserViewHistory]:
    """获取用户浏览历史。"""
    return db.query(UserViewHistory).filter(
        UserViewHistory.user_id == user_id
    ).order_by(UserViewHistory.last_viewed_at.desc()).limit(limit).all()


# =============================================================================
# Price Prediction Log 操作
# =============================================================================
def log_prediction(
    db: Session,
    user_id: int = None,
    **kwargs
) -> PricePredictionLog:
    """记录价格预测日志。"""
    db_log = PricePredictionLog(user_id=user_id, **kwargs)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


def get_user_predictions(
    db: Session,
    user_id: int,
    limit: int = 20
) -> List[PricePredictionLog]:
    """获取用户的预测历史。"""
    return db.query(PricePredictionLog).filter(
        PricePredictionLog.user_id == user_id
    ).order_by(PricePredictionLog.created_at.desc()).limit(limit).all()


