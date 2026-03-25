"""
Hive数据服务 - 通过Docker CLI调用
不需要安装pyhive/impyla，直接调用docker exec hive hive
"""
import subprocess
import json
import os
from typing import List, Dict, Any, Optional


class HiveDockerService:
    """通过Docker CLI连接Hive"""

    def __init__(self):
        self.container_name = "hive-server"
        self.database = "tujia_dw"

    def _execute_hive_command(self, sql: str) -> List[Dict]:
        """
        执行Hive命令并解析结果
        """
        # 构建完整的Hive命令
        full_sql = f"USE {self.database}; {sql}"

        try:
            # 调用docker exec执行hive命令
            result = subprocess.run(
                ["docker", "exec", self.container_name, "hive", "-e", full_sql],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode != 0:
                print(f"Hive执行错误: {result.stderr}")
                return []

            # 解析输出
            return self._parse_hive_output(result.stdout)

        except Exception as e:
            print(f"执行Hive命令失败: {e}")
            return []

    def _parse_hive_output(self, output: str) -> List[Dict]:
        """
        解析Hive的输出结果
        Hive输出格式：
        OK
col1    col2    col3
val1    val2    val3
val4    val5    val6
        """
        lines = output.strip().split('\n')

        # 找到OK之后的行
        data_start = -1
        for i, line in enumerate(lines):
            if line.strip() == 'OK':
                data_start = i + 1
                break

        if data_start == -1 or data_start >= len(lines):
            return []

        # 解析表头
        header_line = lines[data_start].strip()
        headers = [h.strip() for h in header_line.split('\t')]

        # 解析数据行
        results = []
        for line in lines[data_start + 1:]:
            line = line.strip()
            if not line or line.startswith('Time taken:'):
                break

            values = [v.strip() for v in line.split('\t')]
            row = {}
            for i, header in enumerate(headers):
                if i < len(values):
                    # 尝试转换为数字
                    value = values[i]
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except (ValueError, TypeError):
                        pass
                    row[header] = value
                else:
                    row[header] = None

            results.append(row)

        return results

    # ============ 业务查询方法 ============

    def get_district_stats(self) -> List[Dict]:
        """获取商圈统计（取最新分区 dt）"""
        sql = """
            SELECT district, avg_price, total_listings, avg_rating
            FROM dws_district_stats
            WHERE dt = (SELECT MAX(dt) FROM dws_district_stats)
            ORDER BY avg_price DESC
        """
        return self._execute_hive_command(sql)

    def get_facility_analysis(self) -> List[Dict]:
        """获取设施溢价分析"""
        sql = """
            SELECT facility_name, has_count, price_premium, premium_rate
            FROM dws_facility_analysis
            WHERE dt = (SELECT MAX(dt) FROM dws_facility_analysis)
            ORDER BY price_premium DESC
        """
        return self._execute_hive_command(sql)

    def get_price_opportunities(self, limit: int = 20) -> List[Dict]:
        """获取价格洼地"""
        sql = f"""
            SELECT unit_id, district, current_price, gap_rate, reason
            FROM ads_price_opportunities
            WHERE dt = (SELECT MAX(dt) FROM ads_price_opportunities)
            ORDER BY gap_rate DESC
            LIMIT {limit}
        """
        return self._execute_hive_command(sql)

    def get_roi_ranking(self) -> List[Dict]:
        """获取ROI排名"""
        sql = """
            SELECT district, estimated_roi, investment_score, risk_level
            FROM ads_roi_ranking
            WHERE dt = (SELECT MAX(dt) FROM ads_roi_ranking)
            ORDER BY estimated_roi DESC
        """
        return self._execute_hive_command(sql)

    def get_table_counts(self) -> Dict[str, int]:
        """获取各表的数据量"""
        tables = [
            'ods_listings',
            'ods_price_calendar',
            'dwd_listing_details',
            'dws_district_stats',
            'dws_facility_analysis',
            'ads_price_opportunities'
        ]

        counts = {}
        for table in tables:
            try:
                if table in (
                    "dwd_listing_details",
                    "dws_district_stats",
                    "dws_facility_analysis",
                    "dws_price_distribution",
                    "ads_price_opportunities",
                    "ads_roi_ranking",
                ):
                    sql = f"SELECT COUNT(*) as cnt FROM {table} WHERE dt = (SELECT MAX(dt) FROM {table})"
                else:
                    sql = f"SELECT COUNT(*) as cnt FROM {table}"
                result = self._execute_hive_command(sql)
                counts[table] = result[0]["cnt"] if result else 0
            except Exception:
                counts[table] = 0

        return counts

    def check_connection(self) -> bool:
        """检查 Hive 容器内 CLI 是否可用（导入前可无 tujia_dw；导入后可有）。"""
        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "hive", "-e", "SHOW DATABASES;"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            ok = result.returncode == 0 and "OK" in result.stdout
            return ok
        except Exception:
            return False

    def run_query_dataframe(self, sql: str):
        """
        执行 SELECT 并返回 pandas.DataFrame（用于离线训练从 Hive ODS 取数）。
        依赖与业务方法相同的 docker exec 解析逻辑。
        """
        try:
            import pandas as pd
        except ImportError:
            return None
        rows = self._execute_hive_command(sql.strip())
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)


# 单例实例
hive_docker_service = HiveDockerService()


if __name__ == "__main__":
    # 测试连接
    print("=" * 60)
    print("Hive Docker连接测试")
    print("=" * 60)

    if hive_docker_service.check_connection():
        print("\n✓ Hive连接成功")

        # 获取各表数据量
        print("\n📊 数据仓库统计:")
        counts = hive_docker_service.get_table_counts()
        for table, count in counts.items():
            status = "✓" if count > 0 else "✗"
            print(f"  {status} {table}: {count} 条")

        # 测试查询
        print("\n📋 商圈统计示例:")
        stats = hive_docker_service.get_district_stats()
        for i, row in enumerate(stats[:3], 1):
            print(f"  {i}. {row.get('district', 'N/A')}: "
                  f"均价 {row.get('avg_price', 'N/A')} 元, "
                  f"{row.get('total_listings', 'N/A')} 套房源")

    else:
        print("\n✗ Hive连接失败")
        print("  请检查:")
        print("    1. Docker容器是否运行: docker ps | findstr hive")
        print("    2. 容器名称是否正确 (默认: hive)")
        print("    3. Hive服务是否正常启动")
