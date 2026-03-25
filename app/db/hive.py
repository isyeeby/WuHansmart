import pandas as pd
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Use impyla for Hive/Impala connection (no compilation required)
try:
    from impala.dbapi import connect
    IMPYLA_AVAILABLE = True
    logger.info("✅ impyla available, will use real Hive data")
except ImportError:
    IMPYLA_AVAILABLE = False
    logger.warning("⚠️ impyla not installed, using Mock data")

def get_hive_connection():
    """Establish a connection to Hive/Impala using impyla."""
    if not IMPYLA_AVAILABLE:
        raise ImportError("impyla is not installed. Install with: pip install impyla")

    try:
        # 尝试使用 LDAP 或 NOSASL 认证
        import os
        auth_mechanism = os.getenv('HIVE_AUTH', 'NOSASL')
        
        conn = connect(
            host=settings.HIVE_HOST,
            port=settings.HIVE_PORT,
            database=settings.HIVE_DATABASE,
            timeout=10,
            auth_mechanism=auth_mechanism,
            use_http_transport=False
        )
        logger.info(f"✅ Hive connected: {settings.HIVE_HOST}:{settings.HIVE_PORT}/{settings.HIVE_DATABASE}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Hive: {e}")
        logger.warning("⚠️ Trying alternative connection method...")
        
        # 尝试不使用认证
        try:
            conn = connect(
                host=settings.HIVE_HOST,
                port=settings.HIVE_PORT,
                database=settings.HIVE_DATABASE,
                timeout=10
            )
            logger.info(f"✅ Hive connected (no auth): {settings.HIVE_HOST}:{settings.HIVE_PORT}")
            return conn
        except Exception as e2:
            logger.error(f"Alternative connection also failed: {e2}")
            raise e2

def _execute_pyhive_to_df(query: str) -> pd.DataFrame:
    """HiveServer2 + pyhive（requirements 已含 pyhive），认证 NONE 时常用 NOSASL。"""
    try:
        from pyhive import hive
        import os

        auth = os.getenv("HIVE_AUTH") or "NOSASL"
        conn = hive.Connection(
            host=settings.HIVE_HOST,
            port=settings.HIVE_PORT,
            username=settings.HIVE_USER or "hive",
            database=settings.HIVE_DATABASE or "default",
            auth=auth,
        )
        try:
            df = pd.read_sql(query, conn)
            logger.info("Hive pyhive query ok: %s...", query[:50])
            return df if df is not None else pd.DataFrame()
        finally:
            conn.close()
    except Exception as e:
        logger.error("pyhive query failed: %s", e)
        return pd.DataFrame()


def execute_query_to_df(query: str) -> pd.DataFrame:
    """Execute SQL query on Hive and return as Pandas DataFrame."""
    conn = None
    if IMPYLA_AVAILABLE:
        try:
            conn = get_hive_connection()
            df = pd.read_sql(query, conn)
            logger.info("Query executed successfully: %s...", query[:50])
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.warning("impyla failed, trying pyhive: %s", e)
        finally:
            if conn:
                conn.close()
    return _execute_pyhive_to_df(query)
