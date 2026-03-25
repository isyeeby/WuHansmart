from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "民宿价格数据分析系统"
    DEBUG: bool = True
    API_V1_STR: str = "/api"

    # Security Settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production"  # 生产环境请更换
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # Database - MySQL Only (用户明确要求使用MySQL)
    # 从环境变量读取，默认使用本地MySQL
    DATABASE_URL: str = "mysql+pymysql://root:123456@localhost:3306/tujia_db?charset=utf8mb4"

    # MySQL连接池配置（与 app/db/database.py 中 create_engine 一致；并发页面会占满池导致 TimeoutError）
    MYSQL_POOL_SIZE: int = 15
    MYSQL_MAX_OVERFLOW: int = 35
    MYSQL_POOL_RECYCLE: int = 3600  # 连接回收时间（秒）
    MYSQL_POOL_TIMEOUT: int = 60  # 取连接等待秒数，池满时过短会频繁报错

    # Hive Connection Settings (for business data)
    HIVE_HOST: str = "localhost"
    HIVE_PORT: int = 10000
    HIVE_USER: str = "hive"
    HIVE_DATABASE: str = "tujia_dw"
    HIVE_PASSWORD: Optional[str] = None
    HIVE_AUTH: Optional[str] = None  # e.g., "LDAP", "KERBEROS", or None
    # 分析接口优先 Hive；False 则始终 MySQL（生产推荐 false，见 .env.example）
    HIVE_ANALYTICS_PRIMARY: bool = False
    # /api/health 是否要求 Hive 可达；False 时仅 MySQL 正常即可 healthy
    HIVE_HEALTH_REQUIRED: bool = False

    # Model Settings
    MODEL_PATH: str = "models/xgboost_price_model_latest.pkl"
    RECOMMENDER_PATH: str = "models/listing_similarity_latest.npz"

    # Data Import Settings
    DATA_IMPORT_BATCH_SIZE: int = 1000  # 数据导入批次大小
    DATA_QUALITY_THRESHOLD: float = 0.8  # 数据质量阈值

    # Feature Engineering Settings
    PRICE_OUTLIER_THRESHOLD: float = 3.0  # 价格异常值阈值（标准差倍数）
    MIN_COMMENT_COUNT: int = 5  # 最小评论数（过滤低质量数据）
    MIN_LISTING_DAYS: int = 30  # 最小上架天数

    # Cache Settings (for future Redis integration)
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 3600  # 缓存时间
    REDIS_URL: str = "redis://localhost:6379/0"
    # 进程内短缓存（秒），用于 dashboard 等只读热点；0 关闭
    API_IN_PROCESS_CACHE_TTL_SECONDS: int = 30

    # CORS：逗号分隔，如 "https://a.com,http://localhost:5173"；空则开发可用宽限
    CORS_ORIGINS: Optional[str] = None

    # API Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100  # 每分钟请求限制

    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # Crawler Settings
    CRAWLER_INTERVAL_HOURS: int = 24  # 爬虫定时执行间隔（小时）

    class Config:
        env_file = ".env"

settings = Settings()
