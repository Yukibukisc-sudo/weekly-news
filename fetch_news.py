#!/usr/bin/env python3
"""
fetch_news.py
每週由 GitHub Actions 排程執行。
呼叫 Anthropic Claude API（搭配 web_search 工具），
針對「台灣／日本／世界／財經／生成式AI」五個分類，
各自搜尋「上週」十大重大新聞，並要求模型回傳結構化 JSON。

輸出：data/news.json

需要的環境變數：
  ANTHROPIC_API_KEY   你的 Anthropic API 金鑰

可選環境變數：
  NEWS_MODEL           預設 claude-sonnet-4-6
  WEEK_END_OVERRIDE    手動指定週末日期 (YYYY-MM-DD)，主要用於本地測試
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = os.environ.get("NEWS_MODEL", "claude-sonnet-4-6")

# 五大分類設定：key 對應前端 DATA 物件的鍵名
CATEGORIES = [
    {
        "key": "tw",
        "label": "台灣",
        "label_en": "TAIWAN",
        "prompt_topic": "台灣（政治、社會、兩岸、治安、國防、產業等公共事務新聞，不含財經與AI類，那兩類另有專屬分類）",
    },
    {
        "key": "jp",
        "label": "日本",
        "label_en": "JAPAN",
        "prompt_topic": "日本（政治、社會、災害、政策、產業等公共事務新聞，不含財經與AI類，那兩類另有專屬分類）",
    },
    {
        "key": "wd",
        "label": "世界",
        "label_en": "WORLD",
        "prompt_topic": "世界其他地區（不含台灣、日本本身；國際外交、地緣政治、戰爭與衝突、選舉、重大社會事件等，不含財經與AI類）",
    },
    {
        "key": "fin",
        "label": "財經",
        "label_en": "FINANCE",
        "prompt_topic": "全球財經與市場（股市、央行利率、重大企業財報或上市、原油與商品價格、重要經濟數據與預測等，可包含台灣、日本、全球市場）",
    },
    {
        "key": "ai",
        "label": "生成式AI",
        "label_en": "GENERATIVE AI",
        "prompt_topic": "生成式AI與大型語言模型產業（新模型發布、AI公司動態如OpenAI/Anthropic/Google/Meta等、AI監管與政策、AI基礎設施與晶片、重大AI安全事件等）",
    },
    {
        "key": "ent",
        "label": "影視圈",
        "label_en": "ENTERTAINMENT",
        "prompt_topic": "影視圈與娛樂產業（電影電視劇上映、頒獎典禮如金曲獎/金鐘獎/金馬獎、知名藝人動態、演藝圈爭議或重大事件、串流平台新片等，可包含台灣、日本、韓國、好萊塢等地）",
    },
    {
        "key": "sp",
        "label": "運動",
        "label_en": "SPORTS",
        "prompt_topic": "體育與運動賽事（世界盃足球、MLB美國職棒含台灣球員動態、NBA、中華職棒CPBL等重大賽事戰績、轉隊交易、選秀、重要紀錄與賽事結果等，可包含台灣、國際各項賽事）",
    },
]

SYSTEM_PROMPT = """你是一個專業新聞編輯助手，任務是根據網路搜尋結果，為新聞週報網站整理「上週十大新聞」，並同時提供繁體中文、日文、英文三語版本。

規則：
1. 你必須使用 web_search 工具實際搜尋，不能憑記憶捏造新聞或日期。
2. 只挑選在指定的「上週日期範圍」內發生或被報導的事件。
3. 每個分類恰好輸出 10 則新聞，依重要性與時間新舊排序（最重要或最新的排前面）。
4. 中文用繁體中文（台灣用語），語氣中性、客觀，避免立場偏頗的形容詞；日文與英文需為通順、自然的當地語感翻譯，不要逐字直譯，但內容與中文版本的事實必須完全一致（同樣的人事時地物與數字）。
5. 摘要長度約 60-100 字（中文）；日文與英文摘要可依語言特性調整長度，但需完整傳達同等資訊量，不要省略關鍵事實。不要使用「據報導」之類的空話開頭。
6. 你的回覆必須只包含一個 JSON 陣列，不要有任何其他文字、不要用 Markdown 程式碼框（不要加 ```json）。
7. JSON 陣列中每個元素的格式必須完全符合（title/desc/tag 都是包含 zh/ja/en 三個鍵的物件）：
   {
     "date": "MM.DD",
     "title": {"zh": "中文標題", "ja": "日文標題", "en": "English title"},
     "desc": {"zh": "中文摘要", "ja": "日文摘要", "en": "English summary"},
     "tag": {"zh": "中文標籤(2-6字)", "ja": "日文標籤", "en": "English tag (1-3 words)"}
   }
8. date 欄位是新聞發生或發布的月.日，使用兩位數字，例如 "06.18"，三語共用同一個 date 值不需要翻譯。
9. 絕對不要在 JSON 前後加任何說明文字、不要加註解、不要把 JSON 包在其他物件裡，最外層必須直接是陣列 [...]。
"""



def build_user_prompt(category: dict, week_start: str, week_end: str) -> str:
    return (
        f"請搜尋並整理「{week_start} 到 {week_end}」這週關於「{category['prompt_topic']}」"
        f"的十大重大新聞。請實際使用搜尋工具查證，確保新聞確實發生在這個日期範圍內或該週被報導。"
        f"輸出符合規則的 JSON 陣列，剛好 10 則。"
    )


def call_claude_with_search(system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
    """呼叫 Anthropic API，啟用 web_search 工具，回傳模型輸出的完整文字內容。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("錯誤：找不到環境變數 ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)

    body = {
        "model": MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    }

    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(ANTHROPIC_API_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
            # 串接所有 text 區塊（過程中可能夾雜 tool_use / tool_result 區塊）
            text_parts = [
                block.get("text", "")
                for block in resp_json.get("content", [])
                if block.get("type") == "text"
            ]
            full_text = "\n".join(text_parts).strip()
            if not full_text:
                raise ValueError(f"API 回應沒有文字內容：{resp_json}")
            return full_text
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, TimeoutError) as e:
            last_err = e
            wait = 5 * attempt
            print(f"[警告] 第 {attempt} 次呼叫失敗：{e}，{wait} 秒後重試...", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"呼叫 Claude API 連續失敗 {max_retries} 次：{last_err}")


def extract_json_array(raw_text: str) -> list:
    """從模型輸出中盡量穩健地擷取 JSON 陣列（去除可能誤加的程式碼框或前後文字）。"""
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    # 找到第一個 [ 與對應的最後一個 ]，避免模型不小心加了說明文字
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"找不到 JSON 陣列邊界，原始內容：{cleaned[:500]}")

    json_str = cleaned[start:end + 1]
    parsed = json.loads(json_str)

    if not isinstance(parsed, list):
        raise ValueError("解析結果不是 JSON 陣列")

    required_keys = {"date", "title", "desc", "tag"}
    required_langs = {"zh", "ja", "en"}
    for i, item in enumerate(parsed):
        if not isinstance(item, dict) or not required_keys.issubset(item.keys()):
            raise ValueError(f"第 {i} 筆資料欄位不完整：{item}")
        for field in ("title", "desc", "tag"):
            value = item[field]
            if not isinstance(value, dict) or not required_langs.issubset(value.keys()):
                raise ValueError(f"第 {i} 筆資料的 {field} 欄位不是包含 zh/ja/en 的三語物件：{value}")

    return parsed


def fetch_category(category: dict, week_start: str, week_end: str) -> list | None:
    """搜尋單一分類新聞。若最終仍失敗，回傳 None（由呼叫端決定是否沿用舊資料）。"""
    print(f"→ 搜尋分類「{category['label']}」...")
    user_prompt = build_user_prompt(category, week_start, week_end)
    try:
        raw_text = call_claude_with_search(SYSTEM_PROMPT, user_prompt)
        items = extract_json_array(raw_text)
    except Exception as e:
        print(f"[錯誤] 分類「{category['label']}」最終仍失敗，將沿用舊資料（如果有）：{e}", file=sys.stderr)
        return None

    if len(items) != 10:
        print(f"[警告] 分類「{category['label']}」回傳 {len(items)} 則，預期 10 則，仍會繼續使用。", file=sys.stderr)

    print(f"  ✓ 取得 {len(items)} 則新聞")
    return items


def load_all_weeks(path: str) -> list:
    """讀取現有的 data/news.json（多週歷史結構），回傳 weeks 陣列。
    若檔案不存在或格式異常，回傳空陣列。
    相容舊格式：若檔案是單週物件（沒有 "weeks" 鍵），自動包裝成單元素陣列。
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"[警告] 讀取舊版 news.json 失敗，將視為沒有歷史資料：{e}", file=sys.stderr)
        return []

    if isinstance(raw, dict) and "weeks" in raw:
        return raw["weeks"]
    elif isinstance(raw, dict) and "week_start" in raw:
        # 舊版單週格式，包裝成陣列以相容
        return [raw]
    else:
        print("[警告] news.json 格式無法辨識，將視為沒有歷史資料", file=sys.stderr)
        return []


def get_latest_week_categories(all_weeks: list) -> dict:
    """從現有歷史資料中取出最新一週的 categories，用於分類搜尋失敗時的 fallback。"""
    if not all_weeks:
        return {}
    latest = max(all_weeks, key=lambda w: w.get("week_start", ""))
    return latest.get("categories", {})


def get_week_range() -> tuple[str, str]:
    """計算「上週」的起訖日期（週一到週日），格式 YYYY-MM-DD。"""
    override = os.environ.get("WEEK_END_OVERRIDE")
    if override:
        week_end_date = datetime.strptime(override, "%Y-%m-%d")
    else:
        today = datetime.now(timezone.utc)
        # 找到上一個週日作為 week_end，往前推 6 天作為 week_start
        days_since_sunday = (today.weekday() + 1) % 7  # Monday=0 ... Sunday=6 -> 轉成「距離上個週日幾天」
        last_sunday = today - timedelta(days=days_since_sunday if days_since_sunday != 0 else 7)
        week_end_date = last_sunday

    week_start_date = week_end_date - timedelta(days=6)
    return week_start_date.strftime("%Y-%m-%d"), week_end_date.strftime("%Y-%m-%d")


def main():
    week_start, week_end = get_week_range()
    print(f"本次更新範圍：{week_start} ~ {week_end}")
    print(f"使用模型：{MODEL}")

    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
    output_path = os.path.abspath(output_path)

    all_weeks = load_all_weeks(output_path)
    previous_categories = get_latest_week_categories(all_weeks)

    result = {
        "week_start": week_start,
        "week_end": week_end,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": {},
    }

    failed_labels = []
    for category in CATEGORIES:
        items = fetch_category(category, week_start, week_end)
        if items is None:
            # 本次搜尋失敗，沿用上一次成功的資料，避免該分類在網頁上整個消失
            fallback = previous_categories.get(category["key"], {}).get("items")
            items = fallback if fallback else []
            failed_labels.append(category["label"])

        result["categories"][category["key"]] = {
            "label": category["label"],
            "label_en": category["label_en"],
            "items": items,
        }

    # 累加邏輯：若本次週次已存在於歷史資料中（例如重新執行同一週），就覆蓋舊的那一筆，
    # 否則新增一筆，永久保留所有歷史週次，供前端下拉選單切換瀏覽。
    all_weeks = [w for w in all_weeks if w.get("week_start") != week_start]
    all_weeks.append(result)
    all_weeks.sort(key=lambda w: w.get("week_start", ""), reverse=True)

    output_data = {"weeks": all_weeks}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已寫入 {output_path}（現有 {len(all_weeks)} 週歷史資料）")

    if failed_labels:
        print(f"[警告] 以下分類本次搜尋失敗，已沿用上一次資料：{', '.join(failed_labels)}", file=sys.stderr)
        # 只有「全部分類都失敗」才視為這次執行失敗（給 CI 一個明確的失敗訊號）；
        # 部分分類失敗仍視為成功，因為已有 fallback 內容可顯示，不會讓網站開天窗。
        if len(failed_labels) == len(CATEGORIES):
            print("[錯誤] 全部分類均搜尋失敗，視為本次執行失敗。", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
