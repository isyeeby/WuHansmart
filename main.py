"""
Wuhan Homestay Price Prediction API
FastAPI backend for homestay data analysis and price prediction.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.endpoints import predict, analysis, auth, user, recommend, dashboard, investment, my_listings, competitor, comparison, home, listings, tags, favorites, geocode
from app.db.database import init_db, engine
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs startup and shutdown events.
    """
    # Startup
    logger.info("Starting up...")
    if not settings.DEBUG:
        weak = (
            "your-secret-key-change-this-in-production",
            "change-me-to-a-long-random-string",
        )
        if settings.SECRET_KEY in weak or len(settings.SECRET_KEY) < 16:
            raise RuntimeError(
                "生产环境请设置强随机 SECRET_KEY（≥16 字符），勿使用默认值；见 .env.example"
            )
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")

    yield

    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="基于大数据的民宿价格数据分析系统 - 后端API服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

def _cors_origins_and_credentials() -> tuple:
    raw = settings.CORS_ORIGINS
    if raw and raw.strip():
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        return origins, True
    if settings.DEBUG:
        return ["*"], False
    logger.warning("CORS_ORIGINS 未配置，生产环境已关闭 credentials 并使用 *；请设置白名单")
    return ["*"], False


_cors_origins, _cors_credentials = _cors_origins_and_credentials()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(user.router, prefix="/api/user", tags=["用户"])
app.include_router(listings.router, prefix="/api/listings", tags=["房源列表"])
app.include_router(tags.router, prefix="/api/tags", tags=["标签库"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["收藏"])
app.include_router(predict.router, prefix="/api/predict", tags=["价格预测"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["数据分析"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["推荐系统"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["驾驶舱"])
app.include_router(investment.router, prefix="/api/investment", tags=["投资计算器"])
app.include_router(my_listings.router, prefix="/api/my-listings", tags=["我的房源"])
app.include_router(competitor.router, prefix="/api/competitor", tags=["竞品情报"])
app.include_router(comparison.router, prefix="/api/compare", tags=["房源对比"])
app.include_router(home.router, prefix="/api/home", tags=["首页"])
app.include_router(geocode.router, prefix="/api/geocode", tags=["地理编码"])


@app.get("/")
def read_root():
    """Root endpoint - API info."""
    return {
        "message": "欢迎使用民宿价格数据分析系统API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/api/health")
def health_check():
    """
    健康检查：MySQL 为必需；Hive 是否必需由 HIVE_HEALTH_REQUIRED 决定。
    """
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning("health db check failed: %s", e)

    hive_reachable = False
    if settings.HIVE_HEALTH_REQUIRED or settings.HIVE_ANALYTICS_PRIMARY:
        try:
            from app.db.hive import execute_query_to_df

            execute_query_to_df("SELECT 1 AS ok")
            hive_reachable = True
        except Exception as e:
            logger.warning("health hive check failed: %s", e)

    hive_required = settings.HIVE_HEALTH_REQUIRED
    degraded = not db_ok or (hive_required and not hive_reachable)
    status = "degraded" if degraded else "healthy"
    return {
        "status": status,
        "version": "1.0.0",
        "services": {
            "api": "running",
            "database": "connected" if db_ok else "disconnected",
            "hive": {
                "required": hive_required,
                "reachable": hive_reachable,
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
