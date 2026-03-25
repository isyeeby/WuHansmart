#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新数据库中的经纬度数据
从JSON文件中提取经纬度并更新到listings表
使用流式处理避免内存问题
"""
import os
import ijson
from sqlalchemy import create_engine, text

# 数据库连接配置 - 直接配置，避免依赖问题
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/tujia_db?charset=utf8mb4"


def update_coordinates():
    """从JSON文件更新经纬度数据到数据库"""
    # JSON文件路径
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data/hive_import/listings_with_tags_and_calendar.json"
    )

    if not os.path.exists(json_path):
        print(f"错误: 找不到数据文件 {json_path}")
        return

    print(f"加载数据: {json_path}")

    # 统计
    total = 0
    updated = 0
    no_coords = 0
    not_found = 0
    batch_count = 0

    # 连接数据库
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # 使用ijson流式处理
        houses = ijson.items(open(json_path, 'rb'), 'houses.item')

        for house in houses:
            unit_id = str(house.get("unit_id"))
            longitude = house.get("longitude")
            latitude = house.get("latitude")

            if not longitude or not latitude:
                no_coords += 1
                continue

            total += 1

            try:
                # 直接尝试更新
                result = conn.execute(
                    text("""
                        UPDATE listings
                        SET longitude = :longitude, latitude = :latitude
                        WHERE unit_id = :unit_id
                    """),
                    {"unit_id": unit_id, "longitude": longitude, "latitude": latitude}
                )

                if result.rowcount > 0:
                    updated += 1
                else:
                    not_found += 1

                # 每100条提交一次
                if total % 100 == 0:
                    conn.commit()
                    batch_count += 1
                    print(f"  已处理 {total} 条...")

            except Exception as e:
                print(f"  错误 {unit_id}: {e}")

        conn.commit()

    print(f"\n更新完成:")
    print(f"  有经纬度数据的房源: {total}")
    print(f"  成功更新: {updated}")
    print(f"  数据库中不存在: {not_found}")
    print(f"  无经纬度数据: {no_coords}")

    # 验证更新结果
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN longitude IS NOT NULL AND latitude IS NOT NULL THEN 1 ELSE 0 END) as with_coords
            FROM listings
        """)).fetchone()

        print(f"\n数据库状态:")
        print(f"  总房源数: {result[0]}")
        print(f"  有经纬度的: {result[1]}")


if __name__ == "__main__":
    update_coordinates()