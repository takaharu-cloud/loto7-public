"""
ロト7アプリ 自動更新スクリプト（GitHub Actions などの定期実行用・headless）
アプリ(app.py)とは独立して動き、Googleスプレッドシートを直接更新する。

自動で行うこと（毎日の予測・最終予測 以外すべて）:
  1. 全期間の当選番号＋東京の実天気を取り込み（実データを最新化）
  2. 予測ノートの自動採点
  3. 他サイト予想の収集（節約モード：登録URLを直接取得＋Haiku抽出）＋成績ログ記録

必要な環境変数（GitHubリポジトリのSecretsに登録）:
  GCP_SERVICE_ACCOUNT_JSON, SPREADSHEET_URL, ANTHROPIC_API_KEY(任意・他サイト抽出に使用)
"""
import os
import re
import json
import sys
from datetime import date, datetime, timedelta, timezone

import requests
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

LOTO_MAX_NUM = 37
LOTO_PICK_COUNT = 7
JST = timezone(timedelta(hours=+9), "JST")


def log(msg):
    print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] {msg}", flush=True)


# ========== Google Sheets ==========
def get_client():
    creds_dict = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))


def load_sheet(client, name):
    try:
        return pd.DataFrame(client.open_by_url(os.environ["SPREADSHEET_URL"]).worksheet(name).get_all_records())
    except Exception as e:
        log(f"load '{name}' 失敗(空で続行): {e}")
        return pd.DataFrame()


def save_sheet(client, name, df):
    doc = client.open_by_url(os.environ["SPREADSHEET_URL"])
    try:
        ws = doc.worksheet(name)
    except Exception:
        ws = doc.add_worksheet(title=name, rows="1000", cols="45")
    ws.clear()
    if not df.empty:
        df = df.fillna("").astype(str).replace("nan", "")
        ws.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")


# ========== 暦・天文（app.pyと同一の純計算） ==========
def get_moon_age(y, m, d):
    return ((date(y, m, d) - date(2000, 1, 6)).days) % 29.530588853


def get_moon_and_tide(y, m, d):
    ma = int(round(get_moon_age(y, m, d))) % 30
    if ma in [0, 1, 2, 29]: phase = "新月"
    elif ma in [3, 4, 5, 6]: phase = "三日月"
    elif ma in [7, 8, 9]: phase = "上弦の月"
    elif ma in [10, 11, 12, 13]: phase = "十三夜"
    elif ma in [14, 15, 16, 17]: phase = "満月"
    elif ma in [18, 19, 20, 21]: phase = "下弦の月"
    elif ma in [22, 23, 24]: phase = "二十三夜"
    else: phase = "二十六夜"
    if ma in [0, 1, 2, 14, 15, 16, 17, 29]: tide, gravity = "大潮", "強(極大)"
    elif ma in [7, 8, 9, 22, 23, 24]: tide, gravity = "小潮", "弱"
    elif ma in [10, 25]: tide, gravity = "長潮", "弱"
    elif ma in [11, 26]: tide, gravity = "若潮", "中"
    else: tide, gravity = "中潮", "中"
    return phase, tide, gravity


def get_eto(target_date):
    jikkan = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    junishi = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    diff = (target_date - date(2024, 1, 1)).days
    return f"{jikkan[diff % 10]}{junishi[diff % 12]}"


def get_fengshui(target_date):
    kyusei = ["一白水星", "二黒土星", "三碧木星", "四緑木星", "五黄土星", "六白金星", "七赤金星", "八白土星", "九紫火星"]
    diff = (target_date - date(2024, 1, 1)).days
    return kyusei[diff % 9]


def get_rokuyo(target_date):
    y, m, d = target_date.year, target_date.month, target_date.day
    moon_age = int(round(get_moon_age(y, m, d))) % 30
    kyureki_day = moon_age + 1 if moon_age + 1 <= 30 else 1
    kyureki_month = m - 1 if m > 1 else 12
    return ["大安", "赤口", "先勝", "友引", "先負", "仏滅"][(kyureki_month + kyureki_day) % 6]


# ========== 天気（Open-Meteo / ERA5・全期間カバー） ==========
def weather_label_from_code(code):
    try:
        c = int(code)
    except Exception:
        return ""
    if c in (0, 1): return "晴れ"
    if c in (2, 3, 45, 48): return "曇り"
    if c in (71, 73, 75, 77, 85, 86): return "雪"
    if c in (95, 96, 99): return "嵐"
    return "雨"


def fetch_tokyo_weather_range(start_date, end_date):
    out = {}
    try:
        url = ("https://archive-api.open-meteo.com/v1/archive"
               f"?latitude=35.69&longitude=139.69&start_date={start_date}&end_date={end_date}"
               "&daily=weather_code,temperature_2m_mean,precipitation_sum,pressure_msl_mean&timezone=Asia%2FTokyo")
        d = requests.get(url, timeout=60).json().get("daily", {})
        times = d.get("time", [])
        wc, tm, pr, ps = d.get("weather_code", []), d.get("temperature_2m_mean", []), d.get("precipitation_sum", []), d.get("pressure_msl_mean", [])
        for i, t in enumerate(times):
            out[t] = (
                weather_label_from_code(wc[i]) if i < len(wc) else "",
                round(tm[i], 1) if i < len(tm) and tm[i] is not None else "",
                pr[i] if i < len(pr) and pr[i] is not None else "",
                round(ps[i]) if i < len(ps) and ps[i] is not None else "",
            )
    except Exception as e:
        log(f"天気取得失敗(空で続行): {e}")
    return out


# ========== 全当選番号（lotoseven） ==========
def fetch_loto7_full_history():
    r = requests.get("https://lotoseven.com/ap/tools/show_numbers",
                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=40)
    soup = BeautifulSoup(r.content.decode(r.apparent_encoding, errors="replace"), "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 9 or not re.fullmatch(r"\d{1,4}", cells[0]):
            continue
        m = re.fullmatch(r"(20\d{2})/(\d{1,2})/(\d{1,2})", cells[1])
        if not m:
            continue
        nums = [c for c in cells[2:9] if re.fullmatch(r"\d{1,2}", c)]
        if len(nums) != 7:
            continue
        ymd = f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        rows.append((int(cells[0]), ymd, [c.zfill(2) for c in nums]))
    return rows


def task_backfill(client):
    rows = fetch_loto7_full_history()
    if not rows:
        log("全履歴の取得に失敗。スキップ")
        return
    rows.sort(key=lambda x: x[0], reverse=True)
    dates = [r[1] for r in rows]
    wmap = fetch_tokyo_weather_range(min(dates), max(dates))
    data = []
    for kai, ymd, nums in rows:
        y, mo, da = (int(v) for v in ymd.split("-"))
        dd = date(y, mo, da)
        mp, mt, mg = get_moon_and_tide(y, mo, da)
        w = wmap.get(ymd, ("", "", "", ""))
        row = {"回号": f"第{kai}回", "抽せん日": ymd}
        for i, n in enumerate(nums):
            row[f"数字{i+1}"] = n
        row.update({"六曜": get_rokuyo(dd), "干支": get_eto(dd), "風水": get_fengshui(dd), "吉凶日": "特になし",
                    "月齢": mp, "潮回り": mt, "重力状態": mg, "天気": w[0], "気温": w[1], "降水": w[2], "気圧": w[3]})
        data.append(row)
    cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + \
           ["六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態", "天気", "気温", "降水", "気圧"]
    save_sheet(client, "実データ", pd.DataFrame(data, columns=cols))
    log(f"実データを全{len(data)}回に更新（天気付与）")


# ========== 予測ノートの自動採点 ==========
def task_score(client):
    df_note = load_sheet(client, "予測ノート")
    df_real = load_sheet(client, "実データ")
    if df_note.empty or df_real.empty:
        log("採点スキップ（データ不足）")
        return
    if "AIの助言" not in df_note.columns:
        df_note["AIの助言"] = "未照合"
    updated = False
    for idx, row in df_note.iterrows():
        adv = str(row.get("AIの助言", ""))
        if "的中" in adv and "等" in adv:
            continue
        match = df_real[df_real["回号"] == str(row.get("対象回号", ""))]
        if match.empty:
            continue
        try:
            actual = set(int(match.iloc[0].get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(match.iloc[0].get(f"数字{i}", "")).isdigit())
            pred = set(int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit())
            hits = len(actual & pred)
            near = sum(1 for p in pred if p not in actual and ((p - 1) in actual or (p + 1) in actual))
            grade = "👑 1等当せん！" if hits == 7 else "✨ 2等/3等相当" if hits == 6 else "🎯 4等当せん！" if hits == 5 else "🎉 5等当せん！" if hits == 4 else "惜しい！ 6等リーチ" if hits == 3 else "ハズレ"
            df_note.at[idx, "AIの助言"] = f"{LOTO_PICK_COUNT}個中 {hits}個的中【{grade}】 / ニアピン {near}個"
            updated = True
        except Exception:
            continue
    if updated:
        save_sheet(client, "予測ノート", df_note)
        log("予測ノートを自動採点")
    else:
        log("採点対象なし（既に最新）")


# ========== 他サイト予想の収集（節約モード）＋成績ログ ==========
def extract_numbers_via_haiku(page_text, anthropic_key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        prompt = ("次のWebページ本文から、ロト7（1〜37）の『予想・推奨として提示された数字』だけを抽出。"
                  "過去の当選結果・日付・金額・順位は除外。カンマ区切りの数字のみ出力（説明禁止）。無ければ空。\n\n本文:\n" + page_text)
        res = client.messages.create(model=os.environ.get("ANTHROPIC_MODEL_LIGHT", "claude-haiku-4-5"),
                                     max_tokens=150, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in res.content if b.type == "text")
    except Exception as e:
        log(f"Haiku抽出失敗: {e}")
        return ""


def task_collect_sites(client, target_round):
    df_urls = load_sheet(client, "予想サイトURL")
    if df_urls.empty:
        log("予想サイトURL シートが空。収集スキップ")
        return
    urls = []
    for v in df_urls.astype(str).values.flatten():
        v = v.strip()
        if v.startswith("http") and v not in urls:
            urls.append(v)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    results = []
    for url in urls:
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20)
            soup = BeautifulSoup(res.content.decode(res.apparent_encoding, errors="replace"), "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:8000]
        except Exception as e:
            results.append({"サイトURL": url, "予想数字": "", "状態": f"取得失敗: {e}", "取得日時": now_str})
            continue
        nums = []
        if anthropic_key and text:
            extracted = extract_numbers_via_haiku(text, anthropic_key)
            nums = sorted({int(n) for n in re.findall(r"\d+", extracted) if 1 <= int(n) <= LOTO_MAX_NUM})
        results.append({"サイトURL": url, "予想数字": ", ".join(str(n) for n in nums),
                        "状態": "OK" if nums else "予想数字が見つからず", "取得日時": now_str})
    save_sheet(client, "他サイト予想", pd.DataFrame(results, columns=["サイトURL", "予想数字", "状態", "取得日時"]))
    # 成績ログに追記（同じ回号＋同URLは置換）
    df_log = load_sheet(client, "予想成績ログ")
    existing = df_log.to_dict("records") if not df_log.empty else []
    incoming = {r["サイトURL"] for r in results}
    kept = [r for r in existing if not (str(r.get("対象回号", "")) == str(target_round) and str(r.get("ソース", "")) in incoming)]
    for r in results:
        if r["予想数字"]:
            kept.append({"対象回号": str(target_round), "ソース": r["サイトURL"], "予想数字": r["予想数字"], "取得日": now_str})
    save_sheet(client, "予想成績ログ", pd.DataFrame(kept, columns=["対象回号", "ソース", "予想数字", "取得日"]))
    ok = sum(1 for r in results if r["状態"] == "OK")
    log(f"他サイト収集 {len(results)}件中 {ok}件抽出・成績ログ記録")


def next_round_label(client):
    df_real = load_sheet(client, "実データ")
    mx = 0
    if not df_real.empty and "回号" in df_real.columns:
        for v in df_real["回号"].astype(str):
            m = re.findall(r"\d+", v)
            if m:
                mx = max(mx, int(m[0]))
    return f"第{mx + 1}回" if mx else "第683回"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    client = get_client()
    log(f"自動更新 開始 (mode={mode})")
    if mode in ("all", "results"):
        task_backfill(client)
        task_score(client)
    if mode in ("all", "collect"):
        task_collect_sites(client, next_round_label(client))
    log("自動更新 完了")


if __name__ == "__main__":
    main()
