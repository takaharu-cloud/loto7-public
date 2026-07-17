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
    # 安全装置：空データで既存の記録を全消ししない（夜間の無人実行でも記録消失を防ぐ最重要ガード）
    if df is None or df.empty:
        log(f"⚠ シート「{name}」へ空データを書き込もうとしたため、既存の記録を守り保存を中止しました")
        return
    doc = client.open_by_url(os.environ["SPREADSHEET_URL"])
    try:
        ws = doc.worksheet(name)
    except Exception:
        ws = doc.add_worksheet(title=name, rows="1000", cols="45")
    df = df.fillna("").astype(str).replace("nan", "")
    ws.clear()
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
    # 天気取得が失敗/欠けても、既存シートの天気を残す（全消し防止・週次で自然回復）
    old = load_sheet(client, "実データ")
    old_w = {}
    if not old.empty and "抽せん日" in old.columns:
        for _, r in old.iterrows():
            old_w[str(r.get("抽せん日", ""))] = (str(r.get("天気", "")), str(r.get("気温", "")), str(r.get("降水", "")), str(r.get("気圧", "")))
    data = []
    for kai, ymd, nums in rows:
        y, mo, da = (int(v) for v in ymd.split("-"))
        dd = date(y, mo, da)
        mp, mt, mg = get_moon_and_tide(y, mo, da)
        w = wmap.get(ymd)
        if not w or not str(w[0]):  # 新規取得が空なら既存の天気を使う
            w = old_w.get(ymd, ("", "", "", ""))
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
    # 回号は数字だけで照合（表記ゆれでも取りこぼさない）
    real_key = df_real["回号"].astype(str).str.replace(r"[^0-9]", "", regex=True) if "回号" in df_real.columns else None
    for idx, row in df_note.iterrows():
        adv = str(row.get("AIの助言", ""))
        if "的中" in adv and "等" in adv:
            continue
        _tn = re.sub(r"[^0-9]", "", str(row.get("対象回号", "")))
        match = df_real[real_key == _tn] if (real_key is not None and _tn) else df_real.iloc[0:0]
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


def task_collect_via_web(client, target_round, anthropic_key):
    """ウェブ検索（Claudeのweb_search）で他サイトの予想を自動収集（週1回・金曜のみ）。
    スクレイピングが不安定でも、検索経由で確実に数件を集めて成績ログ＆コンセンサスに反映する。"""
    if not anthropic_key:
        return
    try:
        import anthropic
        ac = anthropic.Anthropic(api_key=anthropic_key)
    except Exception as e:
        log(f"webサーチ収集スキップ(anthropic未導入): {e}")
        return
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    prompt = (
        f"日本の宝くじ『ロト7』（数字は1〜37から7個）について、{target_round}の予想数字を掲載している予想サイトを"
        "ウェブ検索で3〜6件見つけてください。各サイトについて、必ず次の1行形式『だけ』を出力（前置き・説明・箇条書き記号は不要）：\n"
        "サイト名 | n1,n2,n3,n4,n5,n6,n7\n"
        "・数字は1〜37の“予想数字”を7個。過去の当選結果・日付・金額・順位は使わない。\n"
        "・予想数字が確認できないサイトは出力しない。"
    )
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
    messages = [{"role": "user", "content": prompt}]
    text = ""
    try:
        for _ in range(4):
            res = ac.messages.create(model=model, max_tokens=1500, tools=tools, messages=messages)
            text += "".join(b.text for b in res.content if getattr(b, "type", "") == "text")
            if getattr(res, "stop_reason", "") == "pause_turn":
                messages.append({"role": "assistant", "content": res.content})
                continue
            break
    except Exception as e:
        log(f"webサーチ収集失敗（無視して継続）: {e}")
        return
    found = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        name, _, nums_part = line.partition("|")
        nums = sorted({int(n) for n in re.findall(r"\d+", nums_part) if 1 <= int(n) <= LOTO_MAX_NUM})
        name = name.strip().strip("・-*#　●○▼>・ ").strip()
        if name and len(nums) >= LOTO_PICK_COUNT:
            found.append((name[:60], nums[:LOTO_PICK_COUNT]))
    if not found:
        log("webサーチ収集：予想数字を抽出できず")
        return
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    df_log = load_sheet(client, "予想成績ログ")
    existing = df_log.to_dict("records") if not df_log.empty else []
    incoming = {n for n, _ in found}
    kept = [r for r in existing if not (str(r.get("対象回号", "")) == str(target_round) and str(r.get("ソース", "")) in incoming)]
    for name, nums in found:
        kept.append({"対象回号": str(target_round), "ソース": name, "予想数字": ", ".join(str(x) for x in nums), "取得日": now_str})
    save_sheet(client, "予想成績ログ", pd.DataFrame(kept, columns=["対象回号", "ソース", "予想数字", "取得日"]))
    # 他サイト予想（コンセンサス表示用）を当回の全ソースで再構築
    full = load_sheet(client, "予想成績ログ")
    if not full.empty and "対象回号" in full.columns:
        curdf = full[full["対象回号"].astype(str) == str(target_round)]
        if not curdf.empty and "ソース" in curdf.columns and "予想数字" in curdf.columns:
            save_sheet(client, "他サイト予想", curdf[["ソース", "予想数字"]].reset_index(drop=True))
    log(f"webサーチ収集 {len(found)}サイトを成績ログに記録（{target_round}）")


SUPERVISOR_SYS = (
    "あなたはロト7プロジェクトの統括監督Claude。忖度せず、結果→分析→次回を締め、仕組みと習慣を厳しくも公正に鍛える。"
    "良い週は認め、悪い週は弱点・偏り・油断を容赦なく指摘。励ましで真実をぼかさない。当たらない確率が高い事実から目を逸らさせない。絵文字禁止。"
    "出力は『## 今週の総括』『## 良かった点 / 外した要因』『## 次回への調整指示』『## 今週のやることチェックリスト』の見出しで簡潔に。"
)


def _round_actual(df_real, label):
    rn = re.findall(r"\d+", str(label))
    s = set()
    if rn and not df_real.empty and "回号" in df_real.columns:
        m = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if not m.empty:
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = m.iloc[0].get(f"数字{i}")
                if str(v).isdigit():
                    s.add(int(v))
    return s


def task_supervisor_report(client, anthropic_key):
    """抽選後、総監督レポート（総括＋次回指示）を自動生成し『反省ログ』に保存（次回予測AIにも反映）。"""
    if not anthropic_key:
        log("⚠ ANTHROPIC_API_KEY 無し：総監督レポートはスキップ")
        return
    df_real = load_sheet(client, "実データ")
    df_note = load_sheet(client, "予測ノート")
    if df_real.empty or "回号" not in df_real.columns:
        return
    mx = max((int(re.findall(r"\d+", str(v))[0]) for v in df_real["回号"].astype(str) if re.findall(r"\d+", str(v))), default=0)
    if not mx:
        return
    last_label = f"第{mx}回"
    actual = _round_actual(df_real, last_label)
    best, lens = 0, {}
    if not df_note.empty and "AIの助言" in df_note.columns:
        for _, r in df_note.iterrows():
            mm = re.search(r"(\d+)個的中", str(r.get("AIの助言", "")))
            if not mm:
                continue
            h = int(mm.group(1))
            if str(r.get("対象回号", "")) == last_label:
                best = max(best, h)
            lens.setdefault(str(r.get("予測ロジック", "")), []).append(h)
    lens_rank = sorted(((k, round(sum(v) / len(v), 2), len(v)) for k, v in lens.items() if v), key=lambda x: x[1], reverse=True)[:5]
    lessons = ""
    df_log = load_sheet(client, "反省ログ")
    if not df_log.empty and "AIの学び" in df_log.columns:
        lessons = "\n---\n".join(df_log.head(2)["AIの学び"].astype(str).tolist())
    summary = (f"直近 {last_label} の正解: {sorted(actual) if actual else '未取得'}\n"
               f"あなたの最高的中: {best}個\n"
               f"レンズ別 平均的中(上位): " + ", ".join(f"{k}={a}({n}口)" for k, a, n in lens_rank) + "\n"
               f"過去の学び:\n{lessons or 'なし'}")
    try:
        import anthropic
        ac = anthropic.Anthropic(api_key=anthropic_key)
        res = ac.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=1800, system=SUPERVISOR_SYS,
            messages=[{"role": "user", "content": "次のロト7運用状況を統括監督として講評し、次回への具体的な調整指示まで出してください。\n\n" + summary}],
        )
        report = "".join(b.text for b in res.content if b.type == "text")
    except Exception as e:
        log(f"総監督レポート生成失敗: {e}")
        return
    if report:
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        new = pd.DataFrame({"日時": [now], "対象回号": [f"自動総監督({last_label})"], "分析テーマ": ["週次自動レポート"], "AIの学び": [report]})
        merged = pd.concat([new, df_log], ignore_index=True) if not df_log.empty else new
        save_sheet(client, "反省ログ", merged)
        log("総監督レポートを自動生成→『反省ログ』に保存")


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
    # --- Secrets チェック（未設定なら原因をはっきり表示） ---
    missing = [k for k in ("GCP_SERVICE_ACCOUNT_JSON", "SPREADSHEET_URL") if not os.environ.get(k)]
    if missing:
        log("❌ 必要なGitHub Secretsが未設定です: " + ", ".join(missing))
        log("→ リポジトリ Settings → Secrets and variables → Actions →『New repository secret』で登録してください。")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("⚠ ANTHROPIC_API_KEY 未設定：他サイト収集はスキップします（結果取得・採点は実行）。")
    try:
        client = get_client()
    except Exception as e:
        log(f"❌ スプレッドシート認証に失敗: {e}")
        log("→ GCP_SERVICE_ACCOUNT_JSON の中身（JSON全文）と、スプレッドシートがサービスアカウントに共有されているかを確認。")
        sys.exit(1)

    log(f"自動更新 開始 (mode={mode})")
    errors = 0
    if mode in ("all", "results"):
        try:
            task_backfill(client)
        except Exception as e:
            errors += 1; log(f"❌ 結果取り込みでエラー: {e}")
        try:
            task_score(client)
        except Exception as e:
            errors += 1; log(f"❌ 採点でエラー: {e}")
        # 総監督AIレポートは廃止（2026-07-18）：分析はCowork（Claudeとの対話）に一本化。API節約。
    if mode in ("all", "collect"):
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                task_collect_sites(client, next_round_label(client))
            except Exception as e:
                errors += 1; log(f"❌ 他サイト収集でエラー: {e}")
            # ウェブ検索での自動収集は金曜(collect)のみ＝週1回（コスト抑制）。失敗してもAction全体は失敗させない。
            if mode == "collect":
                try:
                    task_collect_via_web(client, next_round_label(client), os.environ.get("ANTHROPIC_API_KEY", ""))
                except Exception as e:
                    log(f"⚠ webサーチ収集は失敗（無視して継続）: {e}")
    log(f"自動更新 完了（エラー {errors} 件）")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
