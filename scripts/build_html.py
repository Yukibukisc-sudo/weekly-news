#!/usr/bin/env python3
"""
build_html.py
讀取 data/news.json，把新聞資料與週次資訊注入 template.html，
產生最終要部署的 index.html。

用法：
  python3 scripts/build_html.py

輸入：
  data/news.json      由 fetch_news.py 產生
  template.html        網頁模板（含 __NEWS_DATA_JSON__ 等佔位符）

輸出：
  dist/index.html      最終可部署的網頁
"""

import json
import os
from datetime import datetime, date


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(BASE_DIR, "template.html")
NEWS_JSON_PATH = os.path.join(BASE_DIR, "data", "news.json")
DIST_DIR = os.path.join(BASE_DIR, "dist")
OUTPUT_PATH = os.path.join(DIST_DIR, "index.html")

# 分類 key 與輸出順序需與 template.html 中的 list-xx 容器一致
CATEGORY_ORDER = ["tw", "jp", "wd", "fin", "ai"]


def format_date_range(week_start: str, week_end: str) -> tuple[str, str]:
    """將 YYYY-MM-DD 轉成頁面顯示用的 YYYY/MM/DD 格式（起、訖各一個字串）。"""
    start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    end_dt = datetime.strptime(week_end, "%Y-%m-%d")
    start_str = start_dt.strftime("%Y/%m/%d")
    end_str = end_dt.strftime("%m/%d")
    return start_str, end_str


def format_generated_date(generated_at_iso: str) -> str:
    """將 ISO 時間字串轉成中文日期顯示，例如 2026年06月21日。"""
    dt = datetime.fromisoformat(generated_at_iso.replace("Z", "+00:00"))
    return dt.strftime("%Y年%m月%d日")


def compute_edition_num(week_start: str) -> int:
    """用週次起始日期推算這是第幾期（以 2026-01-05 視為第1期週一，可依需求調整）。
    若你想要更精準的期數管理，可改成從 data/edition_counter.json 讀取累加值。
    """
    base = date(2026, 1, 5)  # 專案起算的第一個週一，可自行調整
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    delta_weeks = (start - base).days // 7
    return max(1, delta_weeks + 1)


def build():
    if not os.path.exists(NEWS_JSON_PATH):
        raise FileNotFoundError(
            f"找不到 {NEWS_JSON_PATH}，請先執行 scripts/fetch_news.py 產生新聞資料。"
        )

    with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
        news_data = json.load(f)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    week_start = news_data["week_start"]
    week_end = news_data["week_end"]
    generated_at = news_data["generated_at"]

    # 組出前端要用的 DATA 物件：{ tw: [...], jp: [...], ... }
    data_for_js = {}
    for key in CATEGORY_ORDER:
        category = news_data["categories"].get(key)
        if not category:
            print(f"[警告] news.json 缺少分類 {key}，將輸出空陣列")
            data_for_js[key] = []
        else:
            data_for_js[key] = category["items"]

    data_json_str = json.dumps(data_for_js, ensure_ascii=False)

    week_start_display, week_end_display = format_date_range(week_start, week_end)
    generated_date_display = format_generated_date(generated_at)
    edition_num = compute_edition_num(week_start)

    replacements = {
        "__NEWS_DATA_JSON__": data_json_str,
        "__WEEK_START__": week_start_display,
        "__WEEK_END__": week_end_display,
        "__GENERATED_DATE__": generated_date_display,
        "__EDITION_NUM__": str(edition_num),
    }

    for placeholder, value in replacements.items():
        if placeholder not in html:
            print(f"[警告] 在模板中找不到佔位符 {placeholder}，可能模板已被修改")
        html = html.replace(placeholder, value)

    os.makedirs(DIST_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 已產生 {OUTPUT_PATH}")
    print(f"   週次：{week_start} ~ {week_end}（第 {edition_num} 期）")
    for key in CATEGORY_ORDER:
        print(f"   - {key}: {len(data_for_js[key])} 則")


if __name__ == "__main__":
    build()
