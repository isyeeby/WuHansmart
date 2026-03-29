#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
途家浏览器爬虫 - 流式处理版本
流程：
1. 滚动页面，找到当前可见的房源
2. 立即点击进入获取价格日历
3. 返回后继续滚动，跳过已处理的
4. 断点续传：下次运行时不再处理已有日历的房源
"""

import json
import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright


class TujiaCalendarSpider:
    def __init__(self, output_file="tujia_calendar_data.json"):
        self.houses = []  # 基础房源信息 {unit_id: house_data}
        self.houses_dict = {}  # 用dict存储，便于查找
        self.house_calendars = {}  # 价格日历数据 {unit_id: calendar_data}
        self.house_tags = {}  # 房源详细标签数据 {unit_id: tags_data}
        self.seen_ids = set()  # 已见过的房源ID
        self.processed_ids = set()  # 已获取日历的房源ID
        self.pending_houses = {}  # API捕获但未处理的房源 {unit_id: house_data}
        self.is_crawling = False
        self.page = None
        self.output_file = output_file
        self.backup_file = output_file.replace(".json", "_backup.json")
        self.tags_file = output_file.replace(".json", "_tags.json")  # 标签单独存
        self.load_existing_data()
        self.load_tags_data()  # 加载已有标签

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            print(f"[{timestamp}] {msg}", flush=True)
        except:
            safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
            print(f"[{timestamp}] {safe_msg}", flush=True)

    def load_existing_data(self):
        """加载已有数据（断点续传）"""
        import os
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "houses" in data:
                        for house in data["houses"]:
                            unit_id = house.get("unit_id")
                            if unit_id and unit_id not in self.seen_ids:
                                self.houses.append(house)
                                self.houses_dict[unit_id] = house
                                self.seen_ids.add(unit_id)
                                if house.get("price_calendar"):
                                    self.house_calendars[unit_id] = house["price_calendar"]
                                    self.processed_ids.add(unit_id)
                                # 加载标签数据
                                if house.get("house_detail_tags"):
                                    self.house_tags[unit_id] = house["house_detail_tags"]
                self.log(f"[断点续传] 已加载 {len(self.houses)} 条房源, {len(self.processed_ids)} 条已有日历, {len(self.house_tags)} 条已有标签")
            except Exception as e:
                self.log(f"[断点续传] 加载失败: {e}")

    def load_tags_data(self):
        """加载标签数据（从单独文件）"""
        import os
        if os.path.exists(self.tags_file):
            try:
                with open(self.tags_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "tags" in data:
                        for unit_id_str, tags in data["tags"].items():
                            unit_id = int(unit_id_str)
                            self.house_tags[unit_id] = tags
                self.log(f"[标签加载] 从 {self.tags_file} 加载 {len(self.house_tags)} 条标签")
            except Exception as e:
                self.log(f"[标签加载] 失败: {e}")

    def save_tags(self, new_unit_id=None, force=False):
        """保存标签数据（安全版本：先写临时文件再重命名，定期备份）"""
        import os
        import shutil

        # 如果不是强制保存，且距上次保存不到10条，则跳过
        if not force and hasattr(self, '_last_tags_count'):
            if len(self.house_tags) - self._last_tags_count < 10:
                return

        self._last_tags_count = len(self.house_tags)

        data = {
            "meta": {
                "count": len(self.house_tags),
                "saved_at": datetime.now().isoformat()
            },
            "tags": {str(k): v for k, v in self.house_tags.items()}
        }

        # 安全写入：先写临时文件，成功后再重命名
        temp_file = self.tags_file + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 原子重命名
            shutil.move(temp_file, self.tags_file)

            # 定期备份（每100条）
            if len(self.house_tags) % 100 == 0:
                backup_name = self.tags_file.replace(".json", f"_backup_{len(self.house_tags)}.json")
                shutil.copy(self.tags_file, backup_name)
                self.log(f"    [标签备份] 已备份 {len(self.house_tags)} 条到 {backup_name}")

            if new_unit_id:
                self.log(f"    [标签保存] #{new_unit_id} ({len(self.house_tags)}条总计)")

        except Exception as e:
            self.log(f"    [标签保存错误] {e}")

    def get_houses_missing_tags(self):
        """获取需要补标签的房源（有日历但没标签）"""
        return [
            unit_id for unit_id in self.processed_ids
            if unit_id not in self.house_tags
        ]

    def extract_from_list(self, data):
        """从列表API提取房源，返回新增数量"""
        if not isinstance(data, dict):
            return 0

        items = None
        if "data" in data and isinstance(data["data"], dict):
            items = data["data"].get("items", [])

        if not items or not isinstance(items, list):
            return 0

        # 限制pending队列大小，优先处理现有房源
        max_pending = 5  # 最多保留5个待处理房源
        current_pending = len(self.pending_houses)

        count = 0
        for item in items:
            if not isinstance(item, dict):
                continue

            # 如果pending队列已满，暂停添加新房源
            if len(self.pending_houses) >= max_pending:
                self.log(f"[队列] pending队列已满({max_pending})，暂停添加新房源")
                break

            unit_id = item.get("unitId")
            if not unit_id or unit_id in self.seen_ids:
                continue

            self.seen_ids.add(unit_id)
            count += 1

            comment_brief = item.get("commentBrief", {}) or {}

            tags = []
            house_tags = item.get("houseTags", [])
            for tag in house_tags[:5]:
                if isinstance(tag, dict):
                    tags.append(tag.get("text", ""))

            house = {
                "unit_id": unit_id,
                "title": item.get("unitName", ""),
                "city": item.get("cityName", ""),
                "city_id": item.get("cityId", 55),
                "district": item.get("districtName", ""),
                "address": item.get("address", ""),
                "final_price": item.get("finalPrice", 0),
                "original_price": item.get("productPrice", 0),
                "rating": comment_brief.get("overall", 0),
                "comment_count": comment_brief.get("totalCount", 0),
                "favorite_count": item.get("favoriteCount", 0),
                "longitude": item.get("longitude", 0),
                "latitude": item.get("latitude", 0),
                "cover_image": item.get("defaultPicture", ""),
                "tags": tags,
                "detail_url": f"https://m.tujia.com/detail/{unit_id}.html",
                "crawled_at": datetime.now().isoformat()
            }
            self.houses.append(house)
            self.houses_dict[unit_id] = house

            # 如果还没有日历，加入待处理队列
            if unit_id not in self.processed_ids and unit_id not in self.pending_houses:
                self.pending_houses[unit_id] = house

        return count

    def handle_list_response(self, response):
        """处理列表API响应"""
        url = response.url
        if "bnbapp-node-h5/h5/search/v2/searchhouse" in url and response.status == 200:
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    data = response.json()
                    count = self.extract_from_list(data)
                    if count > 0:
                        self.log(f"[列表] +{count}条 (总计:{len(self.houses)})")
            except:
                pass

    def find_houses_on_page_mixed(self):
        """
        在页面上查找所有需要处理的房源（混合模式）
        返回: [(unit_id, element, house_data, need_calendar), ...]
        need_calendar: True表示新房源需要日历，False表示老房源只需要标签
        """
        found_houses = []
        found_ids = set()

        try:
            # 等待页面稳定
            time.sleep(0.5)

            # 尝试多种选择器查找房源卡片
            links = []

            # 方法1: 直接查找包含/detail/的链接
            try:
                links = self.page.locator("a[href*='/detail/']").all()
                if links:
                    self.log(f"[调试] 找到 {len(links)} 个链接")
            except Exception as e:
                self.log(f"[调试] 选择器失败: {e}")

            # 方法2: 如果没找到，尝试所有a标签
            if not links:
                try:
                    all_links = self.page.locator("a").all()
                    for link in all_links:
                        try:
                            href = link.get_attribute("href")
                            if href and "/detail/" in href:
                                links.append(link)
                        except:
                            pass
                    self.log(f"[调试] 筛选后剩余 {len(links)} 个相关链接")
                except Exception as e:
                    self.log(f"[调试] 选择器失败: {e}")

            for link in links:
                try:
                    # 获取href提取unit_id
                    href = link.get_attribute("href")
                    if not href:
                        continue

                    # 提取unit_id
                    import re
                    match = re.search(r'/detail/(\d+)', href)
                    if not match:
                        continue

                    unit_id = int(match.group(1))

                    # 避免重复
                    if unit_id in found_ids:
                        continue
                    found_ids.add(unit_id)

                    # 判断房源类型
                    if unit_id in self.pending_houses:
                        # 新房源：需要日历+标签
                        house = self.pending_houses[unit_id]
                        found_houses.append((unit_id, link, house, True))
                        self.log(f"[调试] 找到新房源: {unit_id}")
                    elif unit_id in self.houses_dict and unit_id not in self.house_tags:
                        # 老房源：已有日历，只缺标签
                        house = self.houses_dict[unit_id]
                        found_houses.append((unit_id, link, house, False))
                        self.log(f"[调试] 找到缺标签老房源: {unit_id}")

                except Exception:
                    continue

        except Exception as e:
            self.log(f"[警告] 查找房源时出错: {e}")

        # 分类统计
        new_count = sum(1 for _, _, _, need_cal in found_houses if need_cal)
        old_count = len(found_houses) - new_count
        if found_houses:
            self.log(f"[发现] 找到 {len(found_houses)} 个房源 (新{new_count}/老缺标签{old_count})")

        return found_houses

    def click_house_and_get_calendar(self, house, link_element):
        """
        点击进入详情页并获取价格日历和标签数据
        传入已找到的元素，避免重复查找
        """
        unit_id = house["unit_id"]
        calendar_data = None
        tags_data = None

        def handle_detail_response(response):
            nonlocal calendar_data, tags_data
            url = response.url

            # 监听价格日历接口
            if "getunitcalendar" in url.lower() and response.status == 200:
                try:
                    if "json" in response.headers.get("content-type", ""):
                        data = response.json()
                        if isinstance(data, dict) and data.get("data"):
                            calendar_data = data
                            self.log(f"    ✓ 捕获日历API: {unit_id}")
                except:
                    pass

            # 监听房源详情标签接口 (gethouse/v3/bnb)
            if "gethouse/v3/bnb" in url.lower() and response.status == 200:
                try:
                    if "json" in response.headers.get("content-type", ""):
                        data = response.json()
                        if isinstance(data, dict) and data.get("data"):
                            tags_data = data
                            self.log(f"    ✓ 捕获标签API: {unit_id}")
                except:
                    pass

        # 添加监听器
        self.page.on("response", handle_detail_response)

        try:
            # 先滚动到元素位置
            try:
                link_element.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.5)
            except:
                pass

            # 点击传入的元素
            link_element.click(timeout=5000)
            self.log(f"    点击进入详情页")

            # 等待详情页加载
            time.sleep(random.uniform(3, 5))

            # 点击"共一晚"
            calendar_clicked = False
            try:
                self.page.locator(".price-calendar-item").first.click(timeout=3000)
                calendar_clicked = True
                self.log(f"    点击'共一晚'")
            except:
                try:
                    self.page.get_by_text("共1晚").first.click(timeout=2000)
                    calendar_clicked = True
                    self.log(f"    点击'共1晚'")
                except:
                    self.log(f"    ⚠ 未找到'共一晚'，跳过")
                    try:
                        self.page.go_back()
                        time.sleep(1)
                    except:
                        pass
                    return False

            if not calendar_clicked:
                return False

            # 等待API返回
            time.sleep(random.uniform(6, 8))


            # 关闭弹窗
            try:
                self.page.locator(".close-icon").first.click(timeout=2000)
                self.log(f"    关闭弹窗")
            except:
                self.page.keyboard.press("Escape")


            # 返回列表页
            try:
                self.page.go_back()
                self.log(f"    返回列表")
            except:
                pass


            time.sleep(random.uniform(2, 3))


        except Exception as e:
            self.log(f"    ✗ 错误: {str(e)[:50]}")
            try:
                self.page.go_back()
                time.sleep(1)
            except:
                pass
        finally:
            self.page.remove_listener("response", handle_detail_response)

        # 保存数据
        if calendar_data:
            self.house_calendars[unit_id] = calendar_data
            self.processed_ids.add(unit_id)

        if tags_data:
            self.house_tags[unit_id] = tags_data
            # 标签单独保存（增量写入，不存主文件）
            self.save_tags(unit_id)

        if calendar_data:
            return True
        else:
            self.log(f"    ✗ 未获取到日历数据")
            return False

    def stream_crawl_phase(self, houses_per_batch=20, rest_minutes=(3, 5)):
        """
        流式爬取：API捕获 → 页面查找 → 点击处理 → 滚动加载更多
        返回处理的新数据数量

        Args:
            houses_per_batch: 每处理多少个房源休息一次（默认20）
            rest_minutes: 休息分钟数范围 (min, max)
        """
        self.log("\n" + "="*60)
        self.log("流式爬取（混合模式）：新房源(日历+标签) + 老房源(补标签)")
        self.log(f"配置: 每{houses_per_batch}条休息{rest_minutes[0]}-{rest_minutes[1]}分钟")
        self.log("="*60)

        total_processed = 0  # 总共处理的
        batch_processed = 0  # 当前批次处理的
        scroll_count = 0
        no_found_count = 0  # 连续没找到房源的次数
        scroll_direction = 1  # 1=向下, -1=向上
        scroll_to_top_attempted = False  # 是否已经尝试回到顶部

        while self.is_crawling:
            # 1. 在页面上查找待处理的房源（混合模式：新房源+缺标签老房源）
            found_houses = self.find_houses_on_page_mixed()

            if found_houses:
                no_found_count = 0

                # 2. 处理这些找到的房源
                for unit_id, link_element, house, need_calendar in found_houses:
                    if not self.is_crawling:
                        break

                    # 新房源需要日历且已处理过，跳过
                    if need_calendar and unit_id in self.processed_ids:
                        if unit_id in self.pending_houses:
                            del self.pending_houses[unit_id]
                        continue

                    # 老房源已补完标签，跳过
                    if not need_calendar and unit_id in self.house_tags:
                        continue

                    total_processed += 1
                    batch_processed += 1

                    if need_calendar:
                        self.log(f"\n[新房源 总{total_processed}/批次{batch_processed}] {house['title'][:30]}...")
                        # 新房源：获取日历+标签
                        success = self.click_house_and_get_calendar(house, link_element)
                        if unit_id in self.pending_houses:
                            del self.pending_houses[unit_id]
                    else:
                        self.log(f"\n[补标签 总{total_processed}/批次{batch_processed}] {house['title'][:30]}...")
                        # 老房源：只获取标签
                        success = self.click_house_and_get_tags_only(house, link_element)

                    if success:
                        self.log(f"    ✓ 成功 (日历{len(self.house_calendars)}条/标签{len(self.house_tags)}条)")

                        # 每50条备份一次
                        if total_processed % 50 == 0:
                            self.save_data(stage="backup")
                            self.log(f"[备份] 已处理 {total_processed} 条，已备份")

                        # 每N条休息一次
                        if batch_processed >= houses_per_batch:
                            self.save_data(stage="progress")
                            self.log(f"\n[批次完成] 本次处理 {batch_processed} 条，共 {total_processed} 条")

                            # 休息
                            rest_time = random.randint(rest_minutes[0] * 60, rest_minutes[1] * 60)
                            rest_mins = rest_time // 60
                            self.log(f"[休息] {rest_mins} 分钟后继续... (按Ctrl+C可中断)")

                            try:
                                for remaining in range(rest_time, 0, -10):
                                    mins = remaining // 60
                                    secs = remaining % 60
                                    print(f"\r    剩余 {mins}分{secs}秒...", end="", flush=True)
                                    time.sleep(10)
                                    # 每30秒轻微滚动保持页面活跃
                                    if remaining % 30 == 0:
                                        try:
                                            self.page.evaluate("window.scrollBy(0, 1)")
                                        except:
                                            pass
                                print("\r    继续爬取!            ")
                                self.log("")
                            except KeyboardInterrupt:
                                self.log("\n[用户中断休息]")
                                raise

                            # 重置批次计数
                            batch_processed = 0

                    # 随机间隔（2-4秒）
                    delay = random.uniform(2, 4)
                    self.log(f"    等待 {delay:.1f}秒...")
                    time.sleep(delay)

                # 当前批次处理完毕
                self.log(f"[完成] 本批次 {len(found_houses)} 个房源处理完毕")

            else:
                # 页面上没有待处理的房源，需要滚动加载
                no_found_count += 1
                scroll_count += 1

                # 检查pending队列
                pending_count = len(self.pending_houses)

                if pending_count > 0:
                    self.log(f"[提示] 还有 {pending_count} 个房源在队列中，但未在页面上找到")

                # 策略调整：如果有pending房源但找不到，尝试回到页面顶部
                if pending_count > 0 and no_found_count >= 3 and not scroll_to_top_attempted:
                    self.log(f"[策略] 尝试回到页面顶部查找之前的房源...")
                    try:
                        self.page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(1)
                        scroll_to_top_attempted = True
                        no_found_count = 0
                        self.log(f"[策略] 已回到顶部，重新查找...")
                        continue
                    except Exception as e:
                        self.log(f"[警告] 回到顶部失败: {e}")

                if no_found_count >= 5 and pending_count > 0:
                    # 已经尝试过回到顶部但还是没找到，继续向下滚动加载更多
                    extra_scroll = random.randint(2000, 3000)
                    self.log(f"[滚动] 第{scroll_count}次向下滚动 {extra_scroll}px，加载新房源...")
                    scroll_to_top_attempted = False  # 重置，下次可以再尝试回顶部
                elif no_found_count >= 5000:
                    # 连续10次都没找到，可能到底了
                    self.log(f"[提示] 连续{no_found_count}次未找到房源，可能已到底部")
                    if pending_count == 0:
                        self.log(f"[完成] 所有房源已处理完毕")
                        break
                    # 还有pending，尝试回到顶部最后一次
                    if not scroll_to_top_attempted:
                        self.log(f"[策略] 尝试回到顶部最后一次...")
                        try:
                            self.page.evaluate("window.scrollTo(0, 0)")
                            time.sleep(3)
                            scroll_to_top_attempted = True
                            no_found_count = 0
                            continue
                        except:
                            pass
                    extra_scroll = random.randint(1500, 2500)
                else:
                    # 正常向下滚动
                    extra_scroll = random.randint(800, 1500)
                    self.log(f"[滚动] 第{scroll_count}次向下滚动 {extra_scroll}px...")

                try:
                    # 分段滚动
                    segments = 2
                    segment_distance = extra_scroll // segments
                    for _ in range(segments):
                        self.page.evaluate(f"window.scrollBy(0, {segment_distance})")
                        time.sleep(random.uniform(0.5, 1))
                except Exception as e:
                    self.log(f"[警告] 滚动失败: {e}")
                    time.sleep(1)
                    continue

                # 等待API返回新数据和页面渲染
                wait_time = random.uniform(2, 4)
                self.log(f"[等待] 等待 {wait_time:.1f}秒...")
                time.sleep(wait_time)

        self.log(f"\n流式爬取结束！本次共处理 {total_processed} 个新房源")
        return total_processed

    def save_data(self, stage="final", show_log=True):
        """保存数据（主文件只存基础信息+日历，标签单独存）"""
        if not self.houses:
            return

        # 合并数据（不包含标签，标签单独存）
        merged_data = []
        for unit_id, house in self.houses_dict.items():
            house_copy = house.copy()
            house_copy["price_calendar"] = self.house_calendars.get(unit_id)
            merged_data.append(house_copy)

        data_to_save = {
            "meta": {
                "total_houses": len(self.houses_dict),
                "calendar_count": len(self.house_calendars),
                "tags_count": len(self.house_tags),
                "processed_count": len(self.processed_ids),
                "stage": stage,
                "saved_at": datetime.now().isoformat()
            },
            "houses": merged_data
        }

        # 保存主文件（不含标签，体积小）
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)

        # 备份文件
        if stage == "backup":
            with open(self.backup_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

        if show_log:
            tag_rate = len(self.house_tags)/len(self.houses_dict)*100 if self.houses_dict else 0
            self.log(f"[保存] {len(self.houses_dict)}条房源(其中{len(self.house_tags)}条带标签/{tag_rate:.1f}%), {len(self.house_calendars)}条日历 -> {self.output_file}")

    def run(self, output_file=None):
        """
        主流程 - 自动循环版
        每20条休息5-7分钟，50条备份一次
        """
        if output_file:
            self.output_file = output_file
            self.backup_file = output_file.replace(".json", "_backup.json")

        self.log("="*60)
        self.log(f"途家价格日历爬虫 - 流式处理版")
        self.log(f"输出文件: {self.output_file}")
        self.log(f"断点续传: {len(self.processed_ids)}条已有日历, {len(self.house_tags)}条已有标签")
        self.log("="*60)

        with sync_playwright() as p:
            self.log("[启动] 使用本机IP（无代理模式）")
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                timeout=60000
            )

            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],
                color_scheme="light",
                reduced_motion="no-preference",
                is_mobile=True,
                has_touch=True,
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [{name: "PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format"}]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
                Object.defineProperty(navigator, 'platform', {get: () => 'iPhone'});
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 4});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
                delete navigator.__proto__.webdriver;
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
                window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
            """)

            self.page = context.new_page()
            self.page.on("response", self.handle_list_response)

            # 1. 打开页面并登录
            self.log("\n步骤1: 打开途家移动版...")

            try:
                self.page.goto("https://m.tujia.com", wait_until="domcontentloaded", timeout=30000)
                time.sleep(1)
            except Exception as e:
                self.log(f"[警告] 首页加载超时: {e}")

            try:
                self.page.evaluate("window.scrollBy(0, 300)")
                time.sleep(1)
            except:
                pass

            self.log("正在进入房源列表...")
            time.sleep(random.uniform(1, 2))
            try:
                self.page.goto("https://m.tujia.com/wuhan", wait_until="networkidle", timeout=60000)
                self.log("页面已加载")
            except Exception as e:
                self.log(f"[警告] 列表页加载超时: {e}")

            self.log("")
            self.log("="*60)
            self.log("【重要】如果看到登录弹窗或验证页面：")
            self.log("  1. 请手动完成登录/验证（可能需要滑块验证）")
            self.log("  2. 登录完成后，确保进入房源列表页")
            self.log("  3. 然后在下方按回车键继续")
            self.log("="*60)

            try:
                input("\n[等待] 完成登录后按回车继续...")
            except EOFError:
                self.log("后台模式，等待60秒...")
                for i in range(60, 0, -1):
                    print(f"\r{i}秒后自动开始...", end="", flush=True)
                    time.sleep(1)
                print("\r开始爬取!              ")

            # 2. 流式爬取（混合模式）：边滚动边处理新房源+补标签
            self.is_crawling = True
            try:
                # 混合模式：同时处理新房源（日历+标签）和老房源（补标签）
                processed_count = self.stream_crawl_phase(
                    houses_per_batch=20,
                    rest_minutes=(3, 4)
                )

                # 检查是否还有未补完标签的房源（页面上找不到的）
                missing_tags = self.get_houses_missing_tags()
                if missing_tags:
                    self.log(f"\n[注意] 还有 {len(missing_tags)} 个房源在页面上未找到，无法补标签")
                    self.log("[提示] 可以重新运行程序，滚动到不同位置再尝试")

            except KeyboardInterrupt:
                self.log("\n用户中断，保存当前进度...")
                self.save_data(stage="interrupt")
                self.log("[已保存] 可以安全退出")
                return
            except Exception as e:
                self.log(f"\n[错误] 爬取过程中断: {e}")
                self.log("[保存] 保存当前进度...")
                self.save_data(stage="error")
            finally:
                self.is_crawling = False

            # 最终保存
            self.save_data(stage="final")
            self.log(f"\n[最终保存] 数据已保存到: {self.output_file}")

            # 最终统计
            self.log("\n" + "="*60)
            self.log(f"爬取结束！")
            self.log(f"  总房源数: {len(self.houses_dict)}")
            self.log(f"  价格日历: {len(self.house_calendars)}")
            self.log(f"  标签数据: {len(self.house_tags)}")
            self.log(f"  完成率: {len(self.house_calendars)/len(self.houses_dict)*100:.1f}%" if self.houses_dict else "  完成率: N/A")
            if self.houses:
                self.log("\n前3条房源:")
                for i, (uid, h) in enumerate(list(self.houses_dict.items())[:3], 1):
                    has_calendar = "✓" if uid in self.house_calendars else "✗"
                    has_tags = "✓" if uid in self.house_tags else "✗"
                    self.log(f"  {i}. [日历{has_calendar} 标签{has_tags}] {h['title'][:25]}... ¥{h['final_price']}")
            self.log("="*60)

            browser.close()

    def get_houses_missing_tags(self):
        """获取缺少标签数据的房源列表"""
        missing_tags_houses = []
        for unit_id, house in self.houses_dict.items():
            if unit_id not in self.house_tags:
                missing_tags_houses.append((unit_id, house))
        return missing_tags_houses

    def click_house_and_get_tags_only(self, house, link_element):
        """
        点击进入详情页并获取标签数据（仅用于补爬标签）
        """
        unit_id = house["unit_id"]
        tags_data = None

        def handle_tags_response(response):
            nonlocal tags_data
            url = response.url
            # 监听房源详情标签接口 (gethouse/v3/bnb)
            if "gethouse/v3/bnb" in url.lower() and response.status == 200:
                try:
                    if "json" in response.headers.get("content-type", ""):
                        data = response.json()
                        if isinstance(data, dict) and data.get("data"):
                            tags_data = data
                            self.log(f"    ✓ 捕获标签API: {unit_id}")
                except:
                    pass

        # 添加监听器
        self.page.on("response", handle_tags_response)

        try:
            # 先滚动到元素位置
            try:
                link_element.scroll_into_view_if_needed(timeout=3000)
                time.sleep(0.5)
            except:
                pass

            # 点击传入的元素
            link_element.click(timeout=5000)
            self.log(f"    点击进入详情页")

            # 等待详情页加载和API返回
            time.sleep(random.uniform(2, 3))

            # 返回列表页
            try:
                self.page.go_back()
                self.log(f"    返回列表")
            except:
                pass

            time.sleep(random.uniform(1, 2))

        except Exception as e:
            self.log(f"    ✗ 错误: {str(e)[:50]}")
            try:
                self.page.go_back()
                time.sleep(1)
            except:
                pass
        finally:
            self.page.remove_listener("response", handle_tags_response)

        if tags_data:
            self.house_tags[unit_id] = tags_data
            # 标签单独保存（增量写入，不存主文件）
            self.save_tags(unit_id)
            return True
        else:
            self.log(f"    ✗ 未获取到标签数据")
            return False

    def find_house_on_page(self, target_unit_id):
        """在页面上查找指定房源"""
        try:
            # 等待页面稳定
            time.sleep(0.5)

            # 尝试多种选择器查找房源卡片
            links = []

            # 方法1: 直接查找包含/detail/的链接
            try:
                links = self.page.locator("a[href*='/detail/']").all()
            except:
                pass

            # 方法2: 如果没找到，尝试所有a标签
            if not links:
                try:
                    all_links = self.page.locator("a").all()
                    for link in all_links:
                        try:
                            href = link.get_attribute("href")
                            if href and "/detail/" in href:
                                links.append(link)
                        except:
                            pass
                except:
                    pass

            # 查找目标房源
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if not href:
                        continue

                    import re
                    match = re.search(r'/detail/(\d+)', href)
                    if not match:
                        continue

                    unit_id = int(match.group(1))
                    if unit_id == target_unit_id:
                        return link

                except Exception:
                    continue

        except Exception as e:
            self.log(f"[警告] 查找房源时出错: {e}")

        return None

    def stream_tags_completion_phase(self, houses_per_batch=20, rest_minutes=(5, 7), max_houses=None):
        """
        标签补爬流程：查找缺少标签的房源 → 点击进入获取标签
        """
        self.log("\n" + "="*60)
        self.log("标签补爬模式：查找缺少标签的房源 → 点击进入获取标签")
        self.log(f"配置: 每{houses_per_batch}条休息{rest_minutes[0]}-{rest_minutes[1]}分钟")
        if max_houses:
            self.log(f"上限: 本次最多处理 {max_houses} 条")
        self.log("="*60)

        # 获取缺少标签的房源
        missing_tags_houses = self.get_houses_missing_tags()
        total_missing = len(missing_tags_houses)

        if total_missing == 0:
            self.log("[完成] 所有房源都已有标签数据")
            return 0

        self.log(f"[补爬] 共有 {total_missing} 个房源缺少标签数据")

        total_processed = 0
        batch_processed = 0
        scroll_count = 0
        pending_tags_houses = dict(missing_tags_houses)  # 转为dict便于查找

        while self.is_crawling and pending_tags_houses:
            # 在页面上查找待处理的房源
            found_houses = []

            for unit_id in list(pending_tags_houses.keys()):
                link = self.find_house_on_page(unit_id)
                if link:
                    found_houses.append((unit_id, link, pending_tags_houses[unit_id]))

            if found_houses:
                self.log(f"[处理] 找到 {len(found_houses)} 个待处理房源在页面上")

                # 处理这些找到的房源
                for unit_id, link_element, house in found_houses:
                    if not self.is_crawling:
                        break

                    # 检查是否达到上限
                    if max_houses and total_processed >= max_houses:
                        self.log(f"\n[完成] 已达到上限 {max_houses} 条，停止处理")
                        return total_processed

                    total_processed += 1
                    batch_processed += 1

                    self.log(f"\n[总{total_processed}/批次{batch_processed}] {house['title'][:30]}...")

                    # 处理这个房源
                    success = self.click_house_and_get_tags_only(house, link_element)

                    # 从pending中移除
                    if unit_id in pending_tags_houses:
                        del pending_tags_houses[unit_id]

                    if success:
                        self.log(f"    ✓ 成功 ({len(self.house_tags)}条标签/共{len(self.houses_dict)}条房源)")

                        # 每50条备份一次
                        if total_processed % 50 == 0:
                            self.save_data(stage="backup")
                            self.log(f"[备份] 已处理 {total_processed} 条，已备份")

                        # 每N条休息一次
                        if batch_processed >= houses_per_batch:
                            self.save_data(stage="progress")
                            self.log(f"\n[批次完成] 本次处理 {batch_processed} 条，共 {total_processed} 条")

                            # 休息
                            rest_time = random.randint(rest_minutes[0] * 60, rest_minutes[1] * 60)
                            rest_mins = rest_time // 60
                            self.log(f"[休息] {rest_mins} 分钟后继续... (按Ctrl+C可中断)")

                            try:
                                for remaining in range(rest_time, 0, -10):
                                    mins = remaining // 60
                                    secs = remaining % 60
                                    print(f"\r    剩余 {mins}分{secs}秒...", end="", flush=True)
                                    time.sleep(10)
                                    # 每30秒轻微滚动保持页面活跃
                                    if remaining % 30 == 0:
                                        try:
                                            self.page.evaluate("window.scrollBy(0, 1)")
                                        except:
                                            pass
                                print("\r    继续爬取!            ")
                                self.log("")
                            except KeyboardInterrupt:
                                self.log("\n[用户中断休息]")
                                raise

                            # 重置批次计数
                            batch_processed = 0

                    # 随机间隔（2-4秒）
                    delay = random.uniform(2, 4)
                    self.log(f"    等待 {delay:.1f}秒...")
                    time.sleep(delay)

            else:
                # 页面上没有待处理的房源，需要滚动加载
                scroll_count += 1
                extra_scroll = random.randint(800, 1500)
                self.log(f"[滚动] 第{scroll_count}次向下滚动 {extra_scroll}px...")

                try:
                    self.page.evaluate(f"window.scrollBy(0, {extra_scroll})")
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    self.log(f"[警告] 滚动失败: {e}")
                    time.sleep(1)

                # 检查是否还有未处理的房源
                if scroll_count >= 20:
                    self.log(f"[提示] 已滚动多次，尝试回到顶部...")
                    try:
                        self.page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(1)
                        scroll_count = 0
                    except:
                        pass

                # 如果pending队列还有数据但一直找不到，可能是页面问题了
                pending_count = len(pending_tags_houses)
                if pending_count > 0 and scroll_count >= 50:
                    self.log(f"[警告] 还有 {pending_count} 个房源未找到，可能已下架或页面问题")
                    self.log(f"[跳过] 跳过这些房源，继续处理其他")
                    break

        self.log(f"\n标签补爬结束！本次共处理 {total_processed} 个房源")
        return total_processed

    def run_fill_tags_mode(self, output_file=None, max_houses=None):
        """
        运行标签补爬模式
        """
        if output_file:
            self.output_file = output_file
            self.backup_file = output_file.replace(".json", "_backup.json")

        # 重新加载数据
        self.houses = []
        self.houses_dict = {}
        self.house_calendars = {}
        self.house_tags = {}
        self.seen_ids = set()
        self.processed_ids = set()
        self.load_existing_data()
        self.load_tags_data()  # 加载已有标签

        self.log("="*60)
        self.log(f"途家标签补爬模式")
        self.log(f"输出文件: {self.output_file}")
        self.log(f"现有房源: {len(self.houses_dict)} 条")
        self.log(f"已有标签: {len(self.house_tags)} 条")
        self.log(f"缺失标签: {len(self.houses_dict) - len(self.house_tags)} 条")
        if max_houses:
            self.log(f"本次上限: {max_houses} 条")
        self.log("="*60)

        # 检查是否有需要补爬的
        missing = self.get_houses_missing_tags()
        if not missing:
            self.log("[完成] 所有房源都已有标签数据，无需补爬")
            return

        with sync_playwright() as p:
            self.log("[启动] 使用本机IP（无代理模式）")
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                timeout=60000
            )

            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],
                color_scheme="light",
                reduced_motion="no-preference",
                is_mobile=True,
                has_touch=True,
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [{name: "PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format"}]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
                Object.defineProperty(navigator, 'platform', {get: () => 'iPhone'});
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 4});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
                delete navigator.__proto__.webdriver;
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
                window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
            """)

            self.page = context.new_page()

            # 1. 打开页面并登录
            self.log("\n步骤1: 打开途家移动版...")

            try:
                self.page.goto("https://m.tujia.com", wait_until="domcontentloaded", timeout=30000)
                time.sleep(1)
            except Exception as e:
                self.log(f"[警告] 首页加载超时: {e}")

            try:
                self.page.evaluate("window.scrollBy(0, 300)")
                time.sleep(1)
            except:
                pass

            self.log("正在进入房源列表...")
            time.sleep(random.uniform(1, 2))
            try:
                self.page.goto("https://m.tujia.com/wuhan", wait_until="networkidle", timeout=60000)
                self.log("页面已加载")
            except Exception as e:
                self.log(f"[警告] 列表页加载超时: {e}")

            self.log("")
            self.log("="*60)
            self.log("【重要】如果看到登录弹窗或验证页面：")
            self.log("  1. 请手动完成登录/验证（可能需要滑块验证）")
            self.log("  2. 登录完成后，确保进入房源列表页")
            self.log("  3. 然后在下方按回车键继续")
            self.log("="*60)

            try:
                input("\n[等待] 完成登录后按回车继续...")
            except EOFError:
                self.log("后台模式，等待60秒...")
                for i in range(60, 0, -1):
                    print(f"\r{i}秒后自动开始...", end="", flush=True)
                    time.sleep(1)
                print("\r开始爬取!              ")

            # 2. 标签补爬流程
            self.is_crawling = True
            try:
                processed = self.stream_tags_completion_phase(
                    houses_per_batch=20,
                    rest_minutes=(3, 4),
                    max_houses=max_houses
                )
            except KeyboardInterrupt:
                self.log("\n用户中断，保存当前进度...")
                self.save_data(stage="interrupt")
                self.log("[已保存] 可以安全退出")
                return
            except Exception as e:
                self.log(f"\n[错误] 爬取过程中断: {e}")
                self.log("[保存] 保存当前进度...")
                self.save_data(stage="error")
            finally:
                self.is_crawling = False

            # 最终保存
            self.save_data(stage="final")
            self.log(f"\n[最终保存] 数据已保存到: {self.output_file}")

            # 最终统计
            self.log("\n" + "="*60)
            self.log(f"标签补爬结束！")
            self.log(f"  总房源数: {len(self.houses_dict)}")
            self.log(f"  价格日历: {len(self.house_calendars)}")
            self.log(f"  标签数据: {len(self.house_tags)}")
            self.log(f"  标签覆盖率: {len(self.house_tags)/len(self.houses_dict)*100:.1f}%" if self.houses_dict else "  标签覆盖率: N/A")
            self.log("="*60)

            browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='途家价格日历爬虫')
    parser.add_argument('--fill-tags', action='store_true', help='只补爬缺失的标签（不获取新房源）')
    parser.add_argument('--max', type=int, default=None, help='最多处理多少条')
    args = parser.parse_args()

    spider = TujiaCalendarSpider(output_file="tujia_calendar_data.json")

    if args.fill_tags:
        spider.log("="*60)
        spider.log("补爬标签模式")
        spider.log(f"已有标签: {len(spider.house_tags)} 条")
        spider.log(f"缺失标签: {len(spider.get_houses_missing_tags())} 条")
        spider.log("="*60)
        spider.run_fill_tags_mode(max_houses=args.max)
    else:
        # 默认模式：自动循环爬取新房源+补标签
        spider.run()
