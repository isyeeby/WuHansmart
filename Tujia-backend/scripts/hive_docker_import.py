"""
启动 Docker 中的 Hive（docker-compose-hive.yml），创建 warehouse 目录并执行 sql/hive_load_data.hql。

前置:
  1. Docker Desktop 已运行
  2. 已执行: python scripts/export_mysql_for_hive.py

用法（在 Tujia-backend 目录）:
  python scripts/hive_docker_import.py
  python scripts/hive_docker_import.py --skip-up    # 容器已启动时跳过 compose up
  python scripts/hive_docker_import.py --date 2026-03-24
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import date

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE_FILE = os.path.join(BACKEND_ROOT, "docker-compose-hive.yml")
CONTAINER = "hive-server"
HQL_IN_CONTAINER = "/opt/hive/data/sql/hive_load_data.hql"


def run(args: list[str], cwd: str | None = None) -> int:
    print("+", " ".join(args))
    # 非交互：docker exec 用 -i（勿用 -T，-T 仅适用于 docker compose exec）
    if (
        len(args) >= 3
        and args[0] == "docker"
        and args[1] == "exec"
        and "-i" not in args[:6]
    ):
        args = [args[0], args[1], "-i", *args[2:]]
    p = subprocess.run(args, cwd=cwd or BACKEND_ROOT)
    return p.returncode


def wait_hs2(timeout_sec: int = 180) -> bool:
    """轮询本机 10000 端口（HiveServer2）是否可连。"""
    try:
        import socket
    except ImportError:
        time.sleep(45)
        return True
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", 10000))
            s.close()
            return True
        except OSError:
            time.sleep(3)
    return False


def cleanup_managed_layers(container: str) -> None:
    """
    清理四层中「托管表」在 file:/// warehouse 下的目录。
    重复执行 HQL 时若分区目录里已有 ORC 文件，INSERT OVERWRITE 的 MoveTask 可能 rename 失败。
    ODS 为 EXTERNAL 且数据在 LOAD 路径，此处不删 ods_* 表目录（由 DROP/LOAD 覆盖）。
    """
    cmd = (
        "rm -rf "
        "/user/hive/warehouse/tujia_dw.db/dwd_listing_details "
        "/user/hive/warehouse/tujia_dw.db/dws_district_stats "
        "/user/hive/warehouse/tujia_dw.db/dws_facility_analysis "
        "/user/hive/warehouse/tujia_dw.db/dws_price_distribution "
        "/user/hive/warehouse/tujia_dw.db/ads_price_opportunities "
        "/user/hive/warehouse/tujia_dw.db/ads_roi_ranking"
    )
    run(["docker", "exec", container, "bash", "-lc", cmd])


def init_metastore_schema() -> None:
    """PostgreSQL 空库时需先初始化 Hive 元表，否则 metastore 进程会直接退出。"""
    rc = run(
        [
            "docker",
            "exec",
            CONTAINER,
            "/opt/hive/bin/schematool",
            "-dbType",
            "postgres",
            "-initSchema",
        ]
    )
    if rc != 0:
        # 已初始化过时会失败，可忽略
        print("提示: schematool 非零退出（若元数据已存在可忽略）", file=sys.stderr)
    run(["docker", "compose", "-f", COMPOSE_FILE, "restart", "hive-metastore"])
    time.sleep(15)
    run(["docker", "compose", "-f", COMPOSE_FILE, "restart", "hive-server"])
    time.sleep(20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-up", action="store_true", help="不执行 docker compose up")
    parser.add_argument(
        "--skip-schema-init",
        action="store_true",
        help="跳过 schematool（元数据已初始化时使用）",
    )
    parser.add_argument("--date", default=None, help="hiveconf process_date，默认今天")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="不清理 DWD/DWS/ADS 本地目录（默认清理，避免重复跑 HQL 时 rename 失败）",
    )
    args = parser.parse_args()
    process_date = args.date or date.today().isoformat()

    listings_tsv = os.path.join(BACKEND_ROOT, "data", "hive_import", "listings_for_hive.tsv")
    cal_tsv = os.path.join(BACKEND_ROOT, "data", "hive_import", "price_calendar_for_hive.tsv")
    if not os.path.isfile(listings_tsv) or not os.path.isfile(cal_tsv):
        print("缺少 TSV，请先运行: python scripts/export_mysql_for_hive.py", file=sys.stderr)
        sys.exit(1)

    if not args.skip_up:
        rc = run(
            [
                "docker",
                "compose",
                "-f",
                COMPOSE_FILE,
                "up",
                "-d",
            ]
        )
        if rc != 0:
            sys.exit(rc)
        time.sleep(10)
        if not args.skip_schema_init:
            print("初始化 Hive Metastore 元数据（仅首次或空库需要）...")
            init_metastore_schema()
        print("等待 HiveServer2 (10000)...")
        if not wait_hs2(240):
            print("警告: 端口 10000 仍未就绪，可稍后在容器日志中排查后手动执行 hive -f", file=sys.stderr)

    rc = run(
        [
            "docker",
            "exec",
            CONTAINER,
            "mkdir",
            "-p",
            "/user/hive/warehouse",
        ]
    )
    if rc != 0:
        sys.exit(rc)

    if not args.no_clean:
        print("清理 DWD/DWS/ADS 本地 warehouse 目录（幂等重跑）...")
        cleanup_managed_layers(CONTAINER)

    rc = run(
        [
            "docker",
            "exec",
            CONTAINER,
            "hive",
            "-hiveconf",
            f"process_date={process_date}",
            "-f",
            HQL_IN_CONTAINER,
        ]
    )
    if rc != 0:
        sys.exit(rc)

    print("Hive 建表与导入完成。验证示例:")
    print(
        f'  docker exec {CONTAINER} hive -e "USE tujia_dw; SELECT COUNT(*) FROM ods_listings;"'
    )


if __name__ == "__main__":
    main()
