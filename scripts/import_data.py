"""
途家民宿数据导入脚本
将JSON数据导入MySQL和生成Hive导入文件
"""
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy import create_engine, text
from app.core.config import settings
from scripts.feature_engineering import TitleParser, FacilityExtractor


class DataImporter:
    """数据导入器"""

    def __init__(self):
        # MySQL连接
        self.mysql_engine = create_engine(settings.DATABASE_URL)
        self.parser = TitleParser()
        self.extractor = FacilityExtractor()

    @staticmethod
    def parse_favorite_count(value) -> int:
        """解析收藏数（处理'1k+'格式）"""
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value = value.strip().lower()
            if 'k' in value:
                # 处理 "1k+", "2k" 格式
                num = value.replace('k', '').replace('+', '')
                try:
                    return int(float(num) * 1000)
                except:
                    return 0
            try:
                return int(value)
            except:
                return 0
        return 0

    def load_json_data(self, filepath: str) -> Dict[str, Any]:
        """加载JSON文件"""
        print(f"加载数据: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def process_calendar_data(self, data: Dict) -> pd.DataFrame:
        """处理tujia_calendar_data.json"""
        houses = data.get("houses", [])
        print(f"处理房源数据: {len(houses)} 条")

        records = []
        for house in houses:
            record = {
                "unit_id": str(house.get("unit_id")),
                "title": house.get("title"),
                "city": house.get("city"),
                "district": house.get("district"),
                "address": house.get("address"),
                "price": house.get("final_price"),
                "original_price": house.get("original_price"),
                "rating": house.get("rating"),
                "comment_count": house.get("comment_count"),
                "favorite_count": self.parse_favorite_count(house.get("favorite_count")),
                "longitude": house.get("longitude"),
                "latitude": house.get("latitude"),
                "cover_image": house.get("cover_image"),
                "tags": json.dumps(house.get("tags", []), ensure_ascii=False),
                "detail_url": house.get("detail_url"),
                "crawled_at": house.get("crawled_at"),
            }

            # 特征工程：解析户型
            title_info = self.parser.parse_all(record["title"])
            record.update({
                "bedroom_count": title_info["bedroom_count"],
                "bathroom_count": title_info["bathroom_count"],
                "bed_count": title_info["bed_count"],
                "area_sqm": title_info.get("area_sqm"),
                "max_guests": title_info.get("max_guests"),
            })

            # 特征工程：提取设施
            facilities = self.extractor.extract(record["tags"])
            record.update({
                "facility_count": self.extractor.get_facility_count(facilities),
                "facility_premium": self.extractor.calculate_premium(facilities),
                "has_projector": facilities.get("has_projector", False),
                "has_kitchen": facilities.get("has_kitchen", False),
                "has_washer": facilities.get("has_washer", False),
                "has_aircon": facilities.get("has_aircon", False),
                "has_wifi": facilities.get("has_wifi", False),
                "has_tv": facilities.get("has_tv", False),
                "has_bathtub": facilities.get("has_bathtub", False),
                "has_balcony": facilities.get("has_balcony", False),
                "has_parking": facilities.get("has_parking", False),
                "has_elevator": facilities.get("has_elevator", False),
                "has_smart_lock": facilities.get("has_smart_lock", False),
                "has_floor_window": facilities.get("has_floor_window", False),
                "has_mahjong": facilities.get("has_mahjong", False),
            })

            records.append(record)

        df = pd.DataFrame(records)
        print(f"数据列: {list(df.columns)}")
        print(f"数据示例:\n{df.head(2)}")
        return df

    def process_price_calendar(self, data: Dict) -> pd.DataFrame:
        """处理价格日历数据"""
        houses = data.get("houses", [])
        print(f"处理价格日历: {len(houses)} 个房源")

        calendar_records = []
        for house in houses:
            unit_id = str(house.get("unit_id"))
            calendars = house.get("price_calendar", {}).get("data", {}).get("houseCalendars", [])

            for cal in calendars:
                calendar_records.append({
                    "unit_id": unit_id,
                    "calendar_date": cal.get("date"),
                    "price": cal.get("price"),
                    "can_booking": cal.get("canBooking") == 1,
                    "price_flag": cal.get("priceFlag"),
                })

        df = pd.DataFrame(calendar_records)
        print(f"日历记录数: {len(df)}")
        return df

    def import_to_mysql(self, df: pd.DataFrame, table_name: str):
        """导入到MySQL"""
        print(f"\n导入到MySQL表: {table_name}")

        try:
            # 先删除旧数据
            with self.mysql_engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                conn.commit()

            # 导入数据
            df.to_sql(table_name, self.mysql_engine, index=False, if_exists='replace',
                     chunksize=1000, method='multi')

            print(f"成功导入 {len(df)} 条记录到 {table_name}")

            # 添加索引（TEXT类型需要指定前缀长度）
            with self.mysql_engine.connect() as conn:
                if 'unit_id' in df.columns:
                    conn.execute(text(f"CREATE INDEX idx_{table_name}_unit_id ON {table_name}(unit_id(50))"))
                if 'district' in df.columns:
                    conn.execute(text(f"CREATE INDEX idx_{table_name}_district ON {table_name}(district(50))"))
                conn.commit()
                print(f"索引创建完成")

        except Exception as e:
            print(f"导入失败: {e}")
            raise

    def generate_hive_import_files(self, df_listings: pd.DataFrame, df_calendar: pd.DataFrame, output_dir: str = "data/hive_import"):
        """生成Hive导入文件"""
        print(f"\n生成Hive导入文件到: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)

        # 生成CSV文件（Hive可直接导入）
        listings_file = os.path.join(output_dir, "listings.csv")
        df_listings.to_csv(listings_file, index=False, encoding='utf-8', sep='\t')
        print(f"生成: {listings_file} ({len(df_listings)} 条)")

        calendar_file = os.path.join(output_dir, "price_calendar.csv")
        df_calendar.to_csv(calendar_file, index=False, encoding='utf-8', sep='\t')
        print(f"生成: {calendar_file} ({len(df_calendar)} 条)")

        # 生成Hive加载脚本
        hive_script = os.path.join(output_dir, "load_to_hive.sql")
        today = datetime.now().strftime("%Y-%m-%d")

        with open(hive_script, 'w', encoding='utf-8') as f:
            f.write(f"""-- Hive数据加载脚本
-- 生成时间: {today}

USE tujia_dw;

-- 加载房源数据到ODS层
LOAD DATA LOCAL INPATH '{listings_file.replace(os.sep, '/')}'
OVERWRITE INTO TABLE ods_listings
PARTITION (dt='{today}');

-- 加载价格日历到ODS层
LOAD DATA LOCAL INPATH '{calendar_file.replace(os.sep, '/')}'
OVERWRITE INTO TABLE ods_price_calendar
PARTITION (dt='{today}');

-- 验证数据
SELECT '房源数量' as metric, COUNT(*) as value FROM ods_listings WHERE dt='{today}'
UNION ALL
SELECT '日历记录数', COUNT(*) FROM ods_price_calendar WHERE dt='{today}';
""")

        print(f"生成Hive加载脚本: {hive_script}")

    def generate_statistics(self, df_listings: pd.DataFrame):
        """生成数据统计报告"""
        print("\n" + "="*50)
        print("数据统计报告")
        print("="*50)

        print(f"\n【基础统计】")
        print(f"  总房源数: {len(df_listings)}")
        print(f"  商圈数: {df_listings['district'].nunique()}")
        print(f"  平均价格: {df_listings['price'].mean():.2f} 元")
        print(f"  价格中位数: {df_listings['price'].median():.2f} 元")
        print(f"  平均评分: {df_listings['rating'].mean():.2f}")
        print(f"  平均评论数: {df_listings['comment_count'].mean():.1f}")

        print(f"\n【商圈分布 Top10】")
        district_stats = df_listings.groupby('district').agg({
            'unit_id': 'count',
            'price': 'mean',
            'rating': 'mean'
        }).round(2)
        district_stats.columns = ['房源数', '均价', '均分']
        print(district_stats.sort_values('房源数', ascending=False).head(10).to_string())

        print(f"\n【户型分布】")
        bedroom_stats = df_listings['bedroom_count'].value_counts().sort_index()
        for bedroom, count in bedroom_stats.head(5).items():
            print(f"  {bedroom}室: {count} 套 ({count/len(df_listings)*100:.1f}%)")

        print(f"\n【设施统计】")
        facility_cols = [c for c in df_listings.columns if c.startswith('has_')]
        for col in facility_cols:
            count = df_listings[col].sum()
            if count > 0:
                print(f"  {col.replace('has_', '')}: {count} 套 ({count/len(df_listings)*100:.1f}%)")

        print(f"\n【价格区间分布】")
        bins = [0, 150, 250, 350, 500, 1000, 10000]
        labels = ['<150', '150-250', '250-350', '350-500', '500-1000', '>1000']
        df_listings['price_range'] = pd.cut(df_listings['price'], bins=bins, labels=labels)
        price_dist = df_listings['price_range'].value_counts().sort_index()
        for range_label, count in price_dist.items():
            print(f"  {range_label}: {count} 套 ({count/len(df_listings)*100:.1f}%)")

        print("\n" + "="*50)


def main():
    """主程序"""
    importer = DataImporter()

    # 1. 加载calendar数据
    print("\n" + "="*60)
    print("步骤1: 加载 tujia_calendar_data.json")
    print("="*60)
    calendar_data = importer.load_json_data("tujia_calendar_data.json")

    # 2. 处理房源数据
    print("\n" + "="*60)
    print("步骤2: 处理房源数据")
    print("="*60)
    df_listings = importer.process_calendar_data(calendar_data)

    # 3. 处理价格日历
    print("\n" + "="*60)
    print("步骤3: 处理价格日历")
    print("="*60)
    df_calendar = importer.process_price_calendar(calendar_data)

    # 4. 导入MySQL
    print("\n" + "="*60)
    print("步骤4: 导入MySQL")
    print("="*60)
    importer.import_to_mysql(df_listings, "raw_listings")
    importer.import_to_mysql(df_calendar, "raw_price_calendar")

    # 5. 生成Hive导入文件
    print("\n" + "="*60)
    print("步骤5: 生成Hive导入文件")
    print("="*60)
    importer.generate_hive_import_files(df_listings, df_calendar)

    # 6. 生成统计报告
    importer.generate_statistics(df_listings)

    print("\n" + "="*60)
    print("✅ 数据导入完成！")
    print("="*60)
    print("\n数据已导入到:")
    print("  - MySQL: raw_listings, raw_price_calendar")
    print("  - 文件: data/hive_import/listings.csv")
    print("  - 文件: data/hive_import/price_calendar.csv")
    print("  - 脚本: data/hive_import/load_to_hive.sql")
    print("\n后续可运行: hive -f data/hive_import/load_to_hive.sql")


if __name__ == "__main__":
    main()
