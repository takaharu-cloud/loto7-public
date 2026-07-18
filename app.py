import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import random
import json
import os
import hashlib
import base64
import io
import time
from collections import Counter
from datetime import datetime, timedelta, date, timezone
import anthropic
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image

# ==========================================
# 定数定義（マジックナンバーの排除）
# ==========================================
LOTO_MAX_NUM = 37               # ロトの数字の最大値
LOTO_PICK_COUNT = 7             # 選択する数字の数
SIMULATION_LOOP_COUNT = 50000   # シミュレーションのループ回数

# ==========================================
# 0. ページ基本設定 & 最強CSS（スマホ無敵化・手打ち完全排除）
# ==========================================
st.set_page_config(page_title="ロト7 くがに堂（金運）", page_icon="icon.png", layout="wide")

# ===== 琉球・金運テーマ（土生金＝土が金を生む配色）=====
# 漆喰ホワイト×砂ベージュ（土）＋ゴールド（金）＋赤瓦テラコッタ（沖縄の土）。
# 風水根拠：金運色=黄・金、最強の組合せ=黄×ベージュ×金、五行の相生「土生金」。黄は強すぎるためポイント使い。
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Shippori+Mincho:wght@500;600;700&family=Zen+Kaku+Gothic+New:wght@400;500&display=swap');
    :root{
        --gold:#B8860B; --gold-deep:#8F6A08; --gold-bright:#D4AF37;
        --ink:#3A2E1E; --ink2:#8A7A5F;
        --line:rgba(184,134,11,0.30); --panel:rgba(255,255,255,0.66);
        --terra:#C0563B; --terra-deep:#A94A32;
        --shikkui:#FBF7EE; --sand:#F1E8D4;
    }
    .stApp {
        background:
            radial-gradient(1100px 560px at 85% -10%, rgba(212,175,55,.14) 0%, rgba(212,175,55,0) 55%),
            radial-gradient(900px 520px at -8% 108%, rgba(192,86,59,.10) 0%, rgba(192,86,59,0) 55%),
            linear-gradient(165deg,#FBF7EE 0%,#F5EDDB 55%,#F1E8D4 100%);
        color: var(--ink); font-family:'Zen Kaku Gothic New','Helvetica Neue',Arial,sans-serif;
    }
    .stApp:before{ content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
        background-image:
            radial-gradient(1.6px 1.6px at 18% 26%, rgba(184,134,11,.30), transparent),
            radial-gradient(1.3px 1.3px at 68% 16%, rgba(212,175,55,.34), transparent),
            radial-gradient(1.2px 1.2px at 42% 70%, rgba(184,134,11,.20), transparent),
            radial-gradient(1.6px 1.6px at 88% 55%, rgba(212,175,55,.30), transparent),
            radial-gradient(1.1px 1.1px at 58% 90%, rgba(169,74,50,.18), transparent); }
    [data-testid="stHeader"]{ background:transparent; }
    .block-container{ position:relative; z-index:1; }
    h1,h2,h3,h4 { font-family:'Shippori Mincho',serif; color:var(--gold-deep); font-weight:600; letter-spacing:.02em; }
    h1 { font-size:28px; border-bottom:2px solid var(--line); padding-bottom:10px; margin-bottom:18px; }
    p, li, label, .stMarkdown { color:var(--ink); }
    .stButton>button {
        width:100%; background:linear-gradient(160deg,#FFFDF7,#F7EFDD); color:var(--gold-deep);
        border:1px solid var(--line); border-radius:14px; padding:13px 16px; font-weight:600; font-size:15px;
        font-family:'Zen Kaku Gothic New',sans-serif; transition:.25s;
        box-shadow:0 2px 8px rgba(184,134,11,.10);
    }
    .stButton>button:hover { background:linear-gradient(160deg,#FFF9E8,#F5E9C9); border-color:var(--gold-bright);
        color:var(--terra-deep); box-shadow:0 4px 16px rgba(212,175,55,.28); transform:translateY(-1px); }
    .info-box { background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--gold-bright);
        border-radius:12px; padding:18px 20px; margin-bottom:18px; font-size:15px; line-height:1.8; color:var(--ink); }
    .analysis-box { background:rgba(255,255,255,.72); border:1px solid var(--line); border-radius:12px;
        padding:20px; margin-bottom:18px; color:var(--ink); }
    .radio-box { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:15px; margin-bottom:15px; }
    .person-select { background:var(--panel); border:1px solid var(--line); padding:15px; border-radius:12px; text-align:center; margin-bottom:20px; }
    /* ===== くがに堂 ダッシュボード ===== */
    .brand{ text-align:center; padding:8px 0 2px; }
    .brand .crest{ color:var(--terra); font-size:18px; letter-spacing:.6em; }
    .brand .ttl{ font-family:'Shippori Mincho',serif; font-size:32px; color:var(--gold-deep); margin:4px 0 2px;
        text-shadow:0 1px 0 #FFF, 0 0 22px rgba(212,175,55,.35); }
    .brand .sub{ color:var(--ink2); font-size:12px; letter-spacing:.30em; }
    .week{ display:flex; justify-content:space-between; gap:6px; margin:16px 0 4px; }
    .wn{ flex:1; text-align:center; padding:11px 3px; border:1px solid var(--line); border-radius:12px; background:var(--panel); }
    .wn .d{ font-family:'Shippori Mincho',serif; font-size:17px; color:var(--ink2); }
    .wn .a{ font-size:10.5px; color:var(--ink2); margin-top:3px; line-height:1.3; }
    .wn.active{ background:linear-gradient(160deg,#FFF6DC,#F9E9BC); border-color:var(--gold-bright);
        box-shadow:0 3px 14px rgba(212,175,55,.30); }
    .wn.active .d{ color:var(--terra-deep); } .wn.active .a{ color:var(--gold-deep); }
    .reset-note{ text-align:center; color:var(--ink2); font-size:11.5px; margin:2px 0 14px; letter-spacing:.12em; }
    .mission{ background:linear-gradient(135deg,#FFF8E4,#FBF3DE);
        border:1px solid var(--gold-bright); border-left:6px solid var(--terra); border-radius:16px;
        padding:20px 24px; margin:4px 0 12px; box-shadow:0 4px 22px rgba(184,134,11,.14); }
    .mission .lbl{ color:var(--terra); font-size:11px; letter-spacing:.3em; }
    .mission .mt{ font-family:'Shippori Mincho',serif; font-size:23px; color:var(--gold-deep); margin:6px 0 6px; }
    .mission .ds{ color:var(--ink); font-size:13.5px; line-height:1.7; }
    .stats{ display:flex; gap:10px; margin:14px 0 6px; }
    .stat{ flex:1; background:var(--panel); border:1px solid var(--line); border-bottom:3px solid var(--gold-bright);
        border-radius:12px; padding:12px 8px; text-align:center; }
    .stat .v{ font-family:'Cormorant Garamond',serif; font-size:25px; color:var(--terra-deep); }
    .stat .k{ color:var(--ink2); font-size:10.5px; letter-spacing:.18em; }
    .sec-label{ color:var(--terra); font-size:11.5px; letter-spacing:.26em; margin:14px 0 6px; }
    .cowork-note{ background:linear-gradient(160deg,#FFF9E8,#F7EFDD); border:1px dashed var(--gold-bright);
        border-radius:12px; padding:14px 18px; margin:12px 0; font-size:14px; color:var(--ink); line-height:1.7; }
</style>
""", unsafe_allow_html=True)

if "menu" not in st.session_state: st.session_state.menu = "ホーム"
def change_menu(menu_name): st.session_state.menu = menu_name

# ==========================================
# 1. 秘密情報と基本設定
# ==========================================
JST = timezone(timedelta(hours=+9), 'JST')

u1_name = st.secrets.get("USER1_NAME", "ご主人")
u1_birth_str = st.secrets.get("USER1_BIRTH", "1990-01-01")
u2_name = st.secrets.get("USER2_NAME", "奥様")
u2_birth_str = st.secrets.get("USER2_BIRTH", "1990-01-01")
secret_profile = st.secrets.get("SECRET_PROFILE", "愛と調和を信じ、世界平和を祈る者。そして家族を支える妻に最高の恩返しを誓う者。この二人の祈りこそが最強の引力となる。")

def parse_date(date_str):
    try: 
        return date(*map(int, str(date_str).split("-")))
    except Exception as e: 
        st.warning(f"日付データの解析に失敗しました。デフォルトの日付を使用します: {e}")
        return date(1990, 1, 1)

USER_PROFILES = {u1_name: {"birth": parse_date(u1_birth_str)}, u2_name: {"birth": parse_date(u2_birth_str)}}

# ==========================================
# 2. クラウドデータベース連携（堅牢化）
# ==========================================
@st.cache_resource
def get_gspread_client():
    if "GCP_SERVICE_ACCOUNT_JSON" not in st.secrets or "SPREADSHEET_URL" not in st.secrets: 
        return None
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    except Exception as e: 
        st.error(f"データベース連携の認証に失敗しました。Secretsの設定を確認してください: {e}")
        return None

@st.cache_resource(show_spinner=False)
def _get_spreadsheet_doc():
    """スプレッドシート本体を開く（1回だけ＝毎回open_by_urlしない）。"""
    client = get_gspread_client()
    if not client:
        return None
    try:
        return client.open_by_url(st.secrets["SPREADSHEET_URL"])
    except Exception:
        return None

@st.cache_data(ttl=60, show_spinner=False)
def _load_sheet_cached(sheet_name):
    """シート読込を60秒キャッシュ＝短時間の再描画・連打でGoogle Sheets APIを叩きすぎない（読み取り上限429を回避）。
    保存時に自動でクリアされるので、書き込んだ内容はすぐ反映される。"""
    doc = _get_spreadsheet_doc()
    if doc is None:
        raise RuntimeError("スプレッドシート未接続")  # ← 失敗をキャッシュに残さない（次回リトライできる）
    return pd.DataFrame(doc.worksheet(sheet_name).get_all_records())

def load_sheet(sheet_name):
    try:
        return _load_sheet_cached(sheet_name)
    except Exception as e:
        # 接続/取得の失敗はキャッシュに居座らせない＝再起動しなくても次回つなぎ直せる
        for _c in (_get_spreadsheet_doc, get_gspread_client):
            try: _c.clear()
            except Exception: pass
        msg = str(e)
        if "429" in msg or "Quota" in msg or "quota" in msg:
            st.info(f"📄 データ読込が少し混み合いました（{sheet_name}）。数十秒待つと自動で回復します。記録は無事です。")
        elif "未接続" in msg:
            st.warning(f"データベースに一時的につながりませんでした（{sheet_name}）。少し待って再読み込みしてください。記録は無事です。")
        else:
            st.warning(f"シート「{sheet_name}」のデータ取得に失敗しました。通信状況をご確認ください: {e}")
        return pd.DataFrame()

def save_sheet(sheet_name, df):
    doc = _get_spreadsheet_doc()
    if doc is None:
        return False
    try:
        try:
            worksheet = doc.worksheet(sheet_name)
        except Exception:
            worksheet = doc.add_worksheet(title=sheet_name, rows="1000", cols="45")
        # 安全装置：空データで既存の記録を全消ししない（通信失敗・誤操作からの全データ消失を防ぐ）
        if df is None or df.empty:
            st.warning(f"シート「{sheet_name}」へ空のデータを書き込もうとしたため、既存の記録を守るために保存を中止しました。")
            return False
        df = df.fillna("").astype(str).replace("nan", "")
        worksheet.clear()
        worksheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        try:
            _load_sheet_cached.clear()  # 保存したら読込キャッシュを消す＝次回は最新を読む
        except Exception:
            pass
        return True
    except Exception as e:
        st.error(f"シート「{sheet_name}」へのデータ保存に失敗しました: {e}")
        return False

# ==========================================
# 3. 究極のAIプロンプト設定（最強の予知科学者・Claude / Anthropic）
# ==========================================
api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
# 💰 コスト最適化：通常はSonnet（高品質・中コスト）、抽出など軽い処理はHaiku（最安）。
# 最高品質にしたい場合は Secrets で ANTHROPIC_MODEL = "claude-opus-4-8" に変更可能。
MODEL_MAIN = st.secrets.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MODEL_LIGHT = st.secrets.get("ANTHROPIC_MODEL_LIGHT", "claude-haiku-4-5")
ANTHROPIC_MODEL = MODEL_MAIN  # 後方互換

@st.cache_resource
def get_claude_client():
    if not api_key:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        st.error(f"Claude APIの初期化に失敗しました。Secretsの ANTHROPIC_API_KEY を確認してください: {e}")
        return None

# 読みやすさのための共通フォーマット指示（全AI出力に適用し、長文の壁を防ぐ）
READABILITY_RULE = """
【読みやすさの絶対ルール】
- 冒頭に必ず1〜2行の「結論サマリー」を置く。
- 見出し（##）と短い箇条書きを使い、1項目1行で簡潔に。専門用語には一言の補足を添える。
- だらだらと長い段落は禁止。スマホでスッと読めるリズムにすること。
"""

def ask_claude(prompt, system=None, max_tokens=2000, image=None, model=None):
    """Claudeに単発で問い合わせる共通関数。imageはPIL Image（任意）。失敗時はNoneを返す。"""
    client = get_claude_client()
    if client is None:
        return None
    try:
        content = []
        if image is not None:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
        content.append({"type": "text", "text": prompt})
        kwargs = {"model": model or MODEL_MAIN, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}
        if system:
            kwargs["system"] = system
        res = client.messages.create(**kwargs)
        return "".join(b.text for b in res.content if b.type == "text")
    except Exception as e:
        st.warning(f"Claudeへの問い合わせに失敗しました: {e}")
        return None

def claude_chat(messages, system=None, max_tokens=1500, model=None):
    """会話履歴（messagesリスト）を渡して応答テキストを得る。占い師チャット用。"""
    client = get_claude_client()
    if client is None:
        return None
    kwargs = {"model": model or MODEL_MAIN, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    res = client.messages.create(**kwargs)
    return "".join(b.text for b in res.content if b.type == "text")

# ==========================================
# 3b. Gemini（第二のAI・任意）— 設定があれば“第二の意見”を出す
# ==========================================
# 無料枠あり。Google AI Studio でキーを取得し、Secrets に GEMINI_API_KEY を入れると有効化。
# モデル名は時々変わる（古い名前は404になる）ので、Secrets指定が無ければ下の候補を上から順に自動で試す。
GEMINI_MODEL = st.secrets.get("GEMINI_MODEL", os.environ.get("GEMINI_MODEL", "")).strip()
GEMINI_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-pro",
    "gemini-2.0-flash-001",
    "gemini-1.5-flash",
]

def get_gemini_key():
    return st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

def gemini_available():
    """Geminiが使える状態か（キーがあるか）。"""
    return bool(get_gemini_key())

def _gemini_model_candidates():
    """試すモデル名の優先リスト。Secrets指定があれば最優先。"""
    cands = []
    if GEMINI_MODEL:
        cands.append(GEMINI_MODEL)
    for m in GEMINI_FALLBACK_MODELS:
        if m not in cands:
            cands.append(m)
    return cands

def ask_gemini(prompt, system=None, max_tokens=1500, image=None):
    """Geminiに単発で問い合わせる。未設定や失敗でもアプリは壊さず、案内/エラー文字列を返す。
    モデル名が古い等の404系エラーは次の候補へ自動フォールバックする。imageはPIL Image（任意）。"""
    key = get_gemini_key()
    if not key:
        return "（Geminiキーが未設定です。Streamlit Secrets に GEMINI_API_KEY を追加すると、第二のAIが使えます）"
    try:
        import google.generativeai as genai
    except Exception:
        return "（Geminiのライブラリ未導入です。requirements.txt に google-generativeai を入れて再デプロイしてください）"
    try:
        genai.configure(api_key=key)
    except Exception as e:
        return f"（Geminiの初期化でエラー: {e}。キー（GEMINI_API_KEY）が正しいか確認してください）"

    last_err = ""
    for mname in _gemini_model_candidates():
        try:
            model = genai.GenerativeModel(mname, system_instruction=system) if system else genai.GenerativeModel(mname)
            parts = []
            if image is not None:
                parts.append(image)  # PIL Image をそのまま渡せる
            parts.append(prompt)
            resp = model.generate_content(parts, generation_config={"max_output_tokens": max_tokens})
            txt = (getattr(resp, "text", "") or "").strip()
            if txt:
                return txt
            last_err = "空の返答"
        except Exception as e:
            last_err = str(e)
            le = last_err.lower()
            # モデルが無い/廃止/未対応 → 次の候補へ。それ以外（認証・課金等）は即返す
            if ("404" in last_err) or ("not found" in le) or ("no longer available" in le) or ("not supported" in le) or ("is not found" in le):
                continue
            return f"（Geminiの呼び出しでエラーが発生しました: {last_err}）"
    return f"（利用可能なGeminiモデルが見つかりませんでした。最後のエラー: {last_err}。Secretsの GEMINI_MODEL に有効なモデル名を指定すると確実です）"

AWAKENED_SCIENTIST_PROMPT = f"""
【役割】あなたはロト7を多角的に読み解く、最強の分析官 Claude。霊的力・運・重力・潮汐・自然・暦（干支/九星/六曜）・出目理論・人間の欲（人気数字）・量子シード・実行者のその日の気持ちまで、あらゆる観点から冷徹かつ公正に分析する。
【実行者の背景（参考情報。ただし結果・評価はこれに一切忖度しない）】\n{secret_profile}

【絶対ルール｜忖度ゼロの辛口分析】
1. おべっか・励まし・精神論で誤魔化さない。この陣形の「強み」だけでなく「弱点・偏り・過剰適合・外れる筋」を必ず同じ熱量で指摘する。
2. 各観点（レンズ）がどう効いたかを根拠とともに簡潔に解説する。ただし「絶対当たる」式の誇大な断定はしない（当選確率そのものは動かないという事実を踏まえる）。
3. 実行者が誰かに関係なく、データと観点だけで厳正に評価する。耳の痛い指摘こそ価値がある。絵文字は使用禁止。
{READABILITY_RULE}
"""

REVIEW_PDCA_PROMPT = f"""
【役割】あなたはロト7の結果を冷徹に検証する、辛口の監査官 Claude。慰めや忖度は一切しない。
【絶対ルール｜忖度ゼロの監査】
1. なぜ当たらなかった／当たったのかを、正解データと突き合わせて率直に分析する。運任せだった点・思い込み・過信を遠慮なく指摘する。
2. 予測の偏り（特定の数字・テーマへの依存）を名指しで指摘し、次回の具体的な改善策を示す。
3. 環境（重力・暦・出目傾向・人間の欲）と結果の関係を多角的に検証する。良ければ良い、ダメならダメとはっきり言う。気休めは禁止。絵文字は使用禁止。
{READABILITY_RULE}
"""

SUPERVISOR_PROMPT = f"""
【役割】あなたはロト7プロジェクトの『統括監督』Claude。忖度せず、毎週「結果 → 分析 → 次回」を締め、仕組みと実行者を厳しくも公正に鍛える。
【実行者の背景（参考。ただし評価は忖度しない）】\n{secret_profile}
【絶対ルール】良い週は認めるが、悪い週は弱点・偏り・油断・過信を容赦なく指摘する。励ましで真実をぼかさない。当たらない確率が高いという事実から目を逸らさせない。当選確率は操作できないと理解した上で、仕組みと習慣の改善だけに集中させる。絵文字は使用禁止。
{READABILITY_RULE}
"""

FORTUNE_CHAT_PROMPT = f"""
【役割】あなたは東洋・西洋の占術を網羅し「視覚（画像認識）」も持つ最高峰のAI占い師であり、相談者の人生に深く寄り添う『魂の伴走者』。ロトの予測設定は完全に消去すること。
【相談者の魂の背景】
{secret_profile}
この方は、生まれてきた意味・家族の本当の幸せ・人生の目的を本気で知りたいと願っている。魂の使命・才能・歩みの意味を、占術と深い洞察で言葉にすること。
【システム防衛命令】
1. 絵文字だけ・短すぎる返答は禁止。日本語の美しい文章で、心の奥に届く鑑定・対話を記すこと。（適度な絵文字は可）
2. 画像が送られたら、線や形など具体的な特徴を必ず文章に含めて鑑定すること。
3. 「生まれた意味」「家族の幸せ」「人生の目的」を問われたら逃げず、存在を肯定しつつ具体的な指針を与えること。
4. 【最重要・忖度厳禁】相談者に媚びてはならない。良い時だけ褒める甘い占いは固く禁じる。運気が低い時・心が乱れている時・行いが伴っていない時は、はっきりと、時に背筋が伸びるほど厳しく伝え、必要なら戒めること。ただし人格否定や脅しはせず、あくまで本人の成長と幸福のための『愛のある厳しさ』とすること。耳の痛い真実こそ、この占いの価値である。
"""

# ==========================================
# 4. 手抜きなし！究極のセンサー・物理演算関数
# ==========================================

# 🚀 【進化1】外部データの柔軟な読み込み（スプレッドシート＆.txt 完全対応）
def get_external_trend(filepath="other_sites.txt"):
    trend = Counter()
    text_data = ""
    # 1. スプレッドシートからの読み込み（自動巡回 or 手入力に両対応）
    try:
        df_ext = load_sheet("他サイト予想")
        if not df_ext.empty:
            # 「予想数字」列があればそれだけを読む（日付やURLの数字がノイズとして混入するのを防ぐ）
            if "予想数字" in df_ext.columns:
                text_data += " ".join(df_ext["予想数字"].astype(str).tolist()) + " "
            else:
                text_data += " ".join(df_ext.astype(str).values.flatten()) + " "
    except Exception as e:
        st.warning(f"スプレッドシートからの「他サイト予想」取得に失敗しました: {e}")
    
    # 2. ローカルの other_sites.txt からの読み込み
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                text_data += f.read()
    except Exception as e: 
        st.warning(f"外部ファイル（{filepath}）の読み込みに失敗しました: {e}")

    nums = re.findall(r'\d+', text_data)
    valid_nums = [int(n) for n in nums if 1 <= int(n) <= LOTO_MAX_NUM]
    trend.update(valid_nums)
    return trend

# 🚀 【進化3】予想サイトを自動巡回し、Claudeで予想数字を抽出して「他サイト予想」を更新
def collect_other_site_predictions():
    """
    「予想サイトURL」シートに並べたURLを巡回し、各ページ本文からClaudeが
    『予想として提示された数字（1〜37）』だけを抽出。結果で「他サイト予想」を丸ごと上書きする。
    戻り値: (結果DataFrame, エラーメッセージ or None)
    """
    if not api_key:
        return None, "Claudeのキー（ANTHROPIC_API_KEY）が未設定のため、自動抽出ができません。"

    df_urls = load_sheet("予想サイトURL")
    if df_urls.empty:
        return None, "「予想サイトURL」シートが空です。A1に見出し『URL』を入れ、A2から予想サイトのURLを1行ずつ貼り付けてください。"

    # 全セルから http で始まる文字列をURLとして収集（重複除去）
    urls = []
    for val in df_urls.astype(str).values.flatten():
        v = val.strip()
        if v.startswith("http") and v not in urls:
            urls.append(v)
    if not urls:
        return None, "有効なURL（httpで始まるもの）が見つかりませんでした。"

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    results = []
    progress = st.progress(0.0)
    for i, url in enumerate(urls):
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            page_text = re.sub(r'\s+', ' ', soup.get_text(" ")).strip()[:8000]
        except Exception as e:
            results.append({"サイトURL": url, "予想数字": "", "状態": f"取得失敗: {e}", "取得日時": now_str})
            progress.progress((i + 1) / len(urls))
            continue

        if not page_text:
            results.append({"サイトURL": url, "予想数字": "", "状態": "本文を取得できず（JavaScript描画サイトの可能性）", "取得日時": now_str})
            progress.progress((i + 1) / len(urls))
            continue

        prompt = f"""次のWebページ本文から、ロト7（1〜37の数字）の「予想・推奨として提示されている数字」だけを抽出してください。
- 過去の当選結果・抽選日・回号・金額・順位などは予想ではないので必ず除外する。
- 「予想」「おすすめ」「狙い目」「本命」等として挙げられた数字のみを対象にする。
- 出力は「7, 15, 21, 30, 33」のようにカンマ区切りの数字だけ。説明や文章は一切書かない。
- 予想数字が見つからなければ、何も出力しない（空）。

本文:
{page_text}"""
        text = ask_claude(prompt, max_tokens=150, model=MODEL_LIGHT) or ""
        found = sorted({int(n) for n in re.findall(r'\d+', text) if 1 <= int(n) <= LOTO_MAX_NUM})
        results.append({
            "サイトURL": url,
            "予想数字": ", ".join(str(n) for n in found),
            "状態": "OK" if found else "予想数字が見つからず",
            "取得日時": now_str,
        })
        progress.progress((i + 1) / len(urls))

    df_out = pd.DataFrame(results, columns=["サイトURL", "予想数字", "状態", "取得日時"])
    save_sheet("他サイト予想", df_out)  # 丸ごと上書き＝古い内容は自動削除
    return df_out, None

# 🚀 【進化4】URL登録不要：Claudeがウェブを全自動検索して予想サイト・YouTubeを横断収集
def research_predictions_via_web(target_round_label):
    """
    Claudeのウェブ検索ツールを使い、指定回号のロト7予想を載せたサイト・ブログ・YouTubeを
    自動で広く探し、各ソースの予想数字（1〜37）を抽出して「他サイト予想」を丸ごと更新する。
    戻り値: (結果DataFrame, エラーメッセージ or None)
    """
    client = get_claude_client()
    if client is None:
        return None, "Claudeのキー（ANTHROPIC_API_KEY）が未設定です。"

    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
    ]
    prompt = f"""あなたはロト7の予想を横断収集する専門リサーチャーです。
ウェブ検索を使い、日本のロト7「{target_round_label}」の予想を載せている予想サイト・ブログ・YouTube動画を、主要なもの6〜8件ほど効率的に探してください。
各ソースが「予想・推奨・狙い目・本命」として挙げている数字（1〜37）を抽出します。

厳守ルール（コスト節約のため検索は最小限に）:
- 検索は多くても5回程度にとどめ、有望なページだけを開く。
- 過去の当選結果・抽選日・回号・金額・順位は予想ではないので必ず除外する。
- 各ソースの予想数字（1〜37の範囲のみ）を集める。
- YouTubeはタイトル・概要・コメント等のテキストから読み取れる数字のみ対象（動画内の音声は対象外）。
- 同じソースを重複させない。

最後に、必ず次の形式のJSONだけを ```json コードブロックで出力してください:
```json
[
  {{"source": "サイト名やチャンネル名", "url": "https://...", "numbers": [3, 12, 19, 25, 31]}}
]
```"""
    messages = [{"role": "user", "content": prompt}]
    text = ""
    try:
        for _ in range(4):
            res = client.messages.create(model=MODEL_MAIN, max_tokens=3000, tools=tools, messages=messages)
            if res.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": res.content})
                continue
            text = "".join(b.text for b in res.content if b.type == "text")
            break
    except Exception as e:
        return None, f"ウェブ検索に失敗しました。Anthropicの管理画面でWeb search（ウェブ検索ツール）が有効か、課金残高があるかをご確認ください: {e}"

    # JSON抽出（コードブロック優先、なければ最初の配列）
    raw = ""
    m = re.search(r'```json\s*(.+?)\s*```', text, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        m2 = re.search(r'\[.*\]', text, re.DOTALL)
        raw = m2.group(0) if m2 else ""
    try:
        data = json.loads(raw)
    except Exception:
        return None, "検索はできましたが、結果を数字リストに変換できませんでした。もう一度お試しください。"
    if not isinstance(data, list):
        return None, "検索結果の形式が想定と異なりました。もう一度お試しください。"

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        nums = set()
        for n in item.get("numbers", []):
            try:
                v = int(n)
            except Exception:
                continue
            if 1 <= v <= LOTO_MAX_NUM:
                nums.add(v)
        if not nums:
            continue
        rows.append({
            "対象回号": target_round_label,
            "ソース": str(item.get("source", ""))[:60],
            "URL": str(item.get("url", ""))[:300],
            "予想数字": ", ".join(str(n) for n in sorted(nums)),
            "取得日時": now_str,
        })
    if not rows:
        return None, "予想数字を含むソースが見つかりませんでした。少し時間をおいて再度お試しください。"

    df_out = pd.DataFrame(rows, columns=["対象回号", "ソース", "URL", "予想数字", "取得日時"])
    save_sheet("他サイト予想", df_out)  # 丸ごと上書き＝古い内容は自動削除
    return df_out, None

# 🚀 【進化5】他サイト予想の横断分析（人気ランキング／自分の予想との差／正解に近いサイト）
def render_other_site_analysis(df_other, target_round_label):
    if df_other is None or df_other.empty:
        st.info("分析できる他サイト予想データがありません。先に自動検索で収集してください。")
        return
    all_nums = []
    col = "予想数字" if "予想数字" in df_other.columns else None
    cells = df_other[col].astype(str).tolist() if col else df_other.astype(str).values.flatten().tolist()
    for s in cells:
        all_nums += [int(x) for x in re.findall(r'\d+', str(s)) if 1 <= int(x) <= LOTO_MAX_NUM]
    if not all_nums:
        st.info("予想数字が抽出できていません。")
        return
    consensus = Counter(all_nums)
    total_sites = len(df_other)

    st.markdown("#### 📊 全予想サイト横断ランキング（多くのサイトが推している数字）")
    rank_df = pd.DataFrame([
        {"順位": i + 1, "数字": str(n).zfill(2), "推すサイト数": c, "支持率": f"{round(c / total_sites * 100)}%"}
        for i, (n, c) in enumerate(consensus.most_common())
    ])
    st.dataframe(rank_df, height=350)
    hot = sorted([n for n, _ in consensus.most_common(7)])
    st.write(f"🔥 全サイト人気トップ7: **{hot}**")

    # 自分の予想との比較
    df_note = load_sheet("予測ノート")
    if not df_note.empty and "対象回号" in df_note.columns:
        mine = df_note[df_note["対象回号"] == target_round_label]
        my_nums = set()
        for _, row in mine.iterrows():
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = row.get(f"数字{i}")
                if str(v).isdigit():
                    my_nums.add(int(v))
        if my_nums:
            top10 = set(n for n, _ in consensus.most_common(10))
            st.markdown("#### 🆚 あなたの予想 vs サイトの総意")
            st.write(f"あなたが{target_round_label}で予想した数字のうち、サイト人気トップ10と一致: **{sorted(my_nums & top10)}**")
            st.write(f"サイト人気トップ10で、あなたがまだ入れていない数字: **{sorted(top10 - my_nums)}**")

    # 正解との照合（抽選後）→ どのソースが一番近かったか
    df_real = load_sheet("実データ")
    rn = re.findall(r'\d+', str(target_round_label))
    actual = set()
    if rn and not df_real.empty and "回号" in df_real.columns:
        match = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if not match.empty:
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = match.iloc[0].get(f"数字{i}")
                if str(v).isdigit():
                    actual.add(int(v))
    if actual:
        st.markdown("#### 🏆 正解との照合：どのサイトが一番近かったか")
        st.write(f"正解番号（{target_round_label}）: **{sorted(actual)}**")
        board = []
        for _, row in df_other.iterrows():
            snums = set(int(x) for x in re.findall(r'\d+', str(row.get("予想数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM)
            board.append({
                "ソース": row.get("ソース", row.get("サイトURL", "")),
                "的中数": len(snums & actual),
                "予想数字": row.get("予想数字", ""),
            })
        board.sort(key=lambda x: x["的中数"], reverse=True)
        st.dataframe(pd.DataFrame(board))
        if board and board[0]["的中数"] > 0:
            st.success(f"最も正解に近かったのは「{board[0]['ソース']}」で {board[0]['的中数']}個的中でした。")
    else:
        st.info(f"{target_round_label}はまだ抽選前（または実データ未取得）のため、『どのサイトが正解に近いか』は抽選後に表示されます。")

# 🚀 【進化6】総監督レポート用ヘルパー
def actual_numbers_for_round(df_real, round_label):
    """指定回号の正解番号の集合を返す（未取得なら空集合）。"""
    rn = re.findall(r'\d+', str(round_label))
    s = set()
    if rn and not df_real.empty and "回号" in df_real.columns:
        m = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if not m.empty:
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = m.iloc[0].get(f"数字{i}")
                if str(v).isdigit():
                    s.add(int(v))
    return s

def user_best_prediction_for_round(df_note, round_label, actual_set):
    """その回号の自分の予測のうち、最も的中数が多かった口を返す。"""
    if df_note.empty or "対象回号" not in df_note.columns:
        return None
    best = None
    for _, row in df_note[df_note["対象回号"] == round_label].iterrows():
        nums = set(int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit())
        h = len(nums & actual_set)
        if best is None or h > best["hits"]:
            best = {"hits": h, "nums": sorted(nums), "実行者": row.get("実行者", ""), "口数": row.get("口数", "")}
    return best

def site_consensus_hot(df_other, top=7):
    """他サイト予想から人気数字トップを返す。"""
    if df_other is None or df_other.empty:
        return []
    col = "予想数字" if "予想数字" in df_other.columns else None
    cells = df_other[col].astype(str).tolist() if col else df_other.astype(str).values.flatten().tolist()
    nums = []
    for s in cells:
        nums += [int(x) for x in re.findall(r'\d+', str(s)) if 1 <= int(x) <= LOTO_MAX_NUM]
    return sorted([n for n, _ in Counter(nums).most_common(top)])

def site_consensus_from_log(target_round, top=10):
    """予想成績ログから、指定回号で多くのサイトが予想している“共通数字”トップを返す（コンセンサス）。
    戻り値: [(数字, 支持サイト数), ...] を多い順。数字だけ欲しい時は [n for n,_ in ...]。"""
    df_log = load_sheet("予想成績ログ")
    if df_log.empty or "対象回号" not in df_log.columns:
        return []
    sub = df_log[df_log["対象回号"].astype(str) == str(target_round)]
    nums = []
    for _, r in sub.iterrows():
        seen = set(int(x) for x in re.findall(r'\d+', str(r.get("予想数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM)
        nums += list(seen)  # 同じサイト内の重複は1票に
    return Counter(nums).most_common(top)

def generate_holistic_candidates(df_real, target_round_str, n=110):
    """積み上げに縛られず、全体の数字×これまでの実績×運気を“総合判断”した候補口を生成する（最終決定用）。
    積み上げの良い口は、この候補と一緒に競わせることでそのまま最終選定に活きる。各口は帯域バランス済み。"""
    nums_list = list(range(1, LOTO_MAX_NUM + 1))
    # ① 実績（過去頻度）＝土台
    number_counts = Counter()
    if df_real is not None and not df_real.empty:
        for i in range(1, LOTO_PICK_COUNT + 1):
            for v in df_real.get(f"数字{i}", []):
                if pd.notna(v) and str(v).isdigit():
                    number_counts[int(v)] += 1
    # ② 出目理論・実績・運気
    try: carry_nums, slide_nums = lens_carry_slide(df_real)
    except Exception: carry_nums, slide_nums = [], []
    unpop = set(lens_unpopular_numbers())
    try: trusted = get_trusted_site_numbers(df_real, target_round_str) or {}
    except Exception: trusted = {}
    try: fortune = set(get_today_fortune_numbers() or [])
    except Exception: fortune = set()
    try: consensus = set(x for x, _ in site_consensus_from_log(target_round_str, top=10))
    except Exception: consensus = set()
    ausp_good = set()
    try:
        _today = datetime.now(JST).date()
        _draw = _today + timedelta(days=((4 - _today.weekday()) % 7))  # 次の金曜（抽選日）
        _lbl, _ag = lens_auspicious_day(_draw)
        ausp_good = set(_ag or [])
    except Exception:
        ausp_good = set()
    # ③ 総合ウェイト（1〜37すべてに、実績を土台に運気を上乗せ）
    weights = []
    for nn in nums_list:
        w = number_counts.get(nn, 1)                       # 実績（過去頻度）＝土台
        if nn in carry_nums: w += 8                         # 引っ張り
        if nn in slide_nums: w += 5                         # スライド
        if nn in unpop: w += 4                              # 大穴（人間の欲）
        if nn in trusted: w += int(trusted.get(nn, 0) * 4)  # 当たっている他サイト
        if nn in consensus: w += 4                          # みんなの共通数字
        if nn in fortune: w += 5                            # 占い（運気）
        if nn in ausp_good: w += 4                          # 縁起日（運気）
        weights.append(max(1, w))
    # ④ 帯域バランスで n 口生成
    cands = []
    su = Counter()
    scap = max(5, round(30 * LOTO_PICK_COUNT / LOTO_MAX_NUM) + 2)
    def _band(x): return (x - 1) // 10
    for k in range(n):
        if k % 30 == 0: su = Counter()
        p = []
        tries = 0
        while len(p) < LOTO_PICK_COUNT and tries < 400:
            ch = random.choices(nums_list, weights=weights, k=1)[0]
            if ch not in p and su[ch] < scap and sum(1 for y in p if _band(y) == _band(ch)) < 3:
                p.append(ch)
            tries += 1
        while len(p) < LOTO_PICK_COUNT:
            cc = [x for x in nums_list if x not in p and su[x] < scap and sum(1 for y in p if _band(y) == _band(x)) < 3] \
                 or [x for x in nums_list if x not in p and su[x] < scap] \
                 or [x for x in nums_list if x not in p]
            mn = min(su[x] for x in cc)
            p.append(random.choice([x for x in cc if su[x] == mn]))
        p = sorted(p)
        for x in p: su[x] += 1
        d = {"実行者": "総合判断AI", "口数": "-", "予測ロジック": "総合判断(全体×実績×運気)",
             "社会情勢": "", "霊的要素": "", "AI直感": "", "祈り/夢": "",
             "実績点数": int(sum(weights[x - 1] for x in p)), "AIの助言": "未照合"}
        for j, x in enumerate(p, 1):
            d[f"数字{j}"] = str(x).zfill(2)
        cands.append(d)
    return cands

def rate_ticket(nums, lens):
    """1口(7数字)の“個別バランス”を◎○△で評価。
    大穴(人気回避)は高数字寄せが狙いなので○以上。通常口は帯域の散らばりで判定（1帯域に固まりすぎ=△）。"""
    valid = [n for n in nums if 1 <= n <= LOTO_MAX_NUM]
    high = sum(1 for n in valid if n >= 32)
    bands = Counter((n - 1) // 10 for n in valid)
    mb = max(bands.values()) if bands else 7
    nb = len(bands)
    if ("人気回避" in str(lens)) or high >= 3:
        return "◎" if high >= 4 else "○"
    if mb >= 5 or nb <= 2:
        return "△"
    if nb >= 3 and mb <= 3:
        return "◎"
    return "○"

def evaluate_formation(final_picks, df_real, ooana_target, prev_actual):
    """買い目の陣形を7項目で◎○△×評価（実測ベース＝AIの感想ではなく事実）。
    戻り値: [{"項目","評価","実測","一言"}, ...]（7件）。"""
    def _nums(c):
        return [int(c.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(c.get(f"数字{i}")).isdigit()]
    n = len(final_picks) or 1
    all_nums = [x for c in final_picks for x in _nums(c)]
    freq = Counter(all_nums)
    even = n * LOTO_PICK_COUNT / LOTO_MAX_NUM  # 均等時の1数字あたり口数
    items = []

    # ① 数字の偏りの無さ（設計上の上限=均等+2程度なので、それを○の基準にする）
    mx = max(freq.values()) if freq else 0
    g = "◎" if mx <= even + 1.5 else "○" if mx <= even + 2.5 else "△" if mx <= even + 4.5 else "×"
    items.append({"項目": "① 数字の偏りの無さ", "評価": g, "実測": f"最多 {mx}口（均等≈{even:.1f}）", "一言": "特定数字への張り付きが無いか"})

    # ② 数字帯のバランス（1-10/11-20/21-30/31-37）
    bands = {"1-10": 0, "11-20": 0, "21-30": 0, "31-37": 0}
    for x in all_nums:
        if x <= 10: bands["1-10"] += 1
        elif x <= 20: bands["11-20"] += 1
        elif x <= 30: bands["21-30"] += 1
        else: bands["31-37"] += 1
    total = sum(bands.values()) or 1
    exp = {"1-10": 10 / 37, "11-20": 10 / 37, "21-30": 10 / 37, "31-37": 7 / 37}
    worst = min((bands[b] / total) / exp[b] for b in bands)  # 1.0で期待通り、小さいほど不足
    g = "◎" if worst >= 0.7 else "○" if worst >= 0.5 else "△" if worst >= 0.25 else "×"
    items.append({"項目": "② 数字帯のバランス", "評価": g, "実測": "／".join(f"{b}:{bands[b]}" for b in bands), "一言": "1〜37を満遍なくカバーしているか"})

    # ③ 大穴（分け前狙い）の確保
    high = set(range(32, LOTO_MAX_NUM + 1))
    ooana_n = sum(1 for c in final_picks if ("人気回避" in str(c.get('予測ロジック', ''))) or sum(1 for x in _nums(c) if x in high) >= 3)
    if ooana_target <= 0:
        g, note = "◎", "今回は大穴指定なし"
    else:
        g = "◎" if ooana_n >= ooana_target else "○" if ooana_n >= ooana_target - 1 else "△" if ooana_n >= 1 else "×"
        note = f"{ooana_n}/{ooana_target}口"
    items.append({"項目": "③ 大穴（分け前狙い）の確保", "評価": g, "実測": note, "一言": "高数字32〜37の大穴口が狙い通り入っているか"})

    # ④ 観点（レンズ）の多様性
    nl = len(set(str(c.get('予測ロジック', '')) for c in final_picks))
    g = "◎" if nl >= 8 else "○" if nl >= 6 else "△" if nl >= 4 else "×"
    items.append({"項目": "④ 観点（レンズ）の多様性", "評価": g, "実測": f"{nl}観点", "一言": "色々な狙いの口がそろっているか"})

    # ⑤ 過去頻度の土台
    top_freq = []
    if df_real is not None and not df_real.empty:
        cnt = Counter()
        for _, r in df_real.iterrows():
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = r.get(f"数字{i}")
                if str(v).isdigit(): cnt[int(v)] += 1
        top_freq = [x for x, _ in cnt.most_common(10)]
    if not top_freq:
        g, note = "△", "当選履歴なし"
    else:
        covered = len(set(top_freq) & set(freq))
        g = "◎" if covered >= 8 else "○" if covered >= 6 else "△" if covered >= 4 else "×"
        note = f"頻出トップ10のうち {covered}個を含む"
    items.append({"項目": "⑤ 過去頻度の土台", "評価": g, "実測": note, "一言": "よく出る数字を押さえているか"})

    # ⑥ 前回に引っ張られすぎない（各回は独立＝前回の正解数字を追いかけるのは偏り）
    #    1口が前回正解と平均何個一致するか。ランダム期待値は 7*7/37≒1.3個。多すぎ＝前回追いの偏り。
    if prev_actual:
        per = [len(set(prev_actual) & set(_nums(c))) for c in final_picks if _nums(c)]
        avg_ov = sum(per) / len(per) if per else 0
        g = "◎" if avg_ov <= 2.0 else "○" if avg_ov <= 2.7 else "△"
        note = f"1口平均 {avg_ov:.1f}個が前回正解と一致（低い＝独立で健全。ランダム目安1.3）"
    else:
        g, note = "◎", "前回結果なし（独立でOK）"
    items.append({"項目": "⑥ 前回への非依存（独立性）", "評価": g, "実測": note, "一言": "各回は独立。前回数字に引っ張られすぎていないか"})

    # ⑦ 合計値・奇偶のバランス
    sums = [sum(_nums(c)) for c in final_picks if _nums(c)]
    odds = [sum(1 for x in _nums(c) if x % 2) for c in final_picks if _nums(c)]
    avg_sum = sum(sums) / len(sums) if sums else 0
    avg_odd = sum(odds) / len(odds) if odds else 0
    ok_sum = 120 <= avg_sum <= 160
    ok_odd = 2.5 <= avg_odd <= 4.5
    g = "◎" if ok_sum and ok_odd else "○" if ok_sum or ok_odd else "△"
    items.append({"項目": "⑦ 合計値・奇偶のバランス", "評価": g, "実測": f"平均合計 {avg_sum:.0f}／平均奇数 {avg_odd:.1f}個", "一言": "極端な合計・奇偶に偏っていないか"})

    return items

# 🚀 【進化7】占い × ロト7 の橋渡し（偏り対策：別管理＋日付ごと＋控えめ反映）
def save_fortune_lucky(nums, user=""):
    """占いが出した今日のラッキーナンバーをシート『占いラッキー』に保存（同じ日付＋同じ利用者は置き換え）。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    df = load_sheet("占いラッキー")
    rows = []
    if not df.empty and "日付" in df.columns:
        for r in df.to_dict("records"):
            if str(r.get("日付")) == today and str(r.get("利用者", "")) == str(user):
                continue
            rows.append(r)
    rows.insert(0, {"日付": today, "利用者": user, "数字": ", ".join(str(n) for n in nums)})
    save_sheet("占いラッキー", pd.DataFrame(rows, columns=["日付", "利用者", "数字"]))

def extract_lucky_from_text(text):
    """占いの鑑定文から『ラッキーナンバー』を抽出（最大7個・1〜37・重複除去）。
    『ラッキーナンバー』という語があればそれ以降を優先的に見て、日付や年号のノイズを避ける。"""
    if not text:
        return []
    idx = str(text).rfind("ラッキーナンバー")
    target = str(text)[idx:] if idx != -1 else str(text)
    seen = []
    for x in re.findall(r'\d+', target):
        v = int(x)
        if 1 <= v <= LOTO_MAX_NUM and v not in seen:
            seen.append(v)
    return seen[:7]

def get_today_fortune_numbers(user=None):
    """今日の占いラッキーナンバー（1〜37）を返す。userを指定するとその利用者分のみ。無ければ空。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    df = load_sheet("占いラッキー")
    if df.empty or "日付" not in df.columns:
        return []
    sub = df[df["日付"].astype(str) == today]
    if user is not None and "利用者" in sub.columns:
        sub = sub[sub["利用者"].astype(str) == str(user)]
    if sub.empty:
        return []
    return sorted({int(x) for x in re.findall(r'\d+', str(sub.iloc[0].get("数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM})

# 🚀 【進化10】多角分析レンズ（フェーズ3）：出目理論・人間の欲・縁起日
def lens_carry_slide(df_real):
    """出目理論：前回の本数字（引っ張り＝再出しやすい）と、その±1（スライド）を返す。戻り値: (引っ張り, スライド)。"""
    if df_real.empty:
        return [], []
    try:
        top = df_real.iloc[0]
        last = sorted({int(top.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(top.get(f"数字{i}", "")).isdigit()})
    except Exception:
        last = []
    slide = sorted({n + d for n in last for d in (-1, 1) if 1 <= n + d <= LOTO_MAX_NUM and (n + d) not in last})
    return last, slide

def lens_unpopular_numbers():
    """人間の欲：誕生日で買われやすい1〜31を避け、買われにくい32〜37を僅かに優遇（当選時の分け前を増やす狙い）。"""
    return list(range(32, LOTO_MAX_NUM + 1))

def lens_auspicious_day(draw_date):
    """縁起日：天赦日・大安などを簡易判定。戻り値: (ラベルリスト, 縁起が良い日か)。"""
    labels = []
    try:
        eto = get_eto(draw_date)  # 十干十二支
        m = draw_date.month
        season = "春" if m in (2, 3, 4) else "夏" if m in (5, 6, 7) else "秋" if m in (8, 9, 10) else "冬"
        tensha = {"春": "戊寅", "夏": "甲午", "秋": "戊申", "冬": "甲子"}
        if eto == tensha[season]:
            labels.append("天赦日")
        rokuyo, _ = get_real_calendar_info(draw_date)
        if rokuyo == "大安":
            labels.append("大安")
    except Exception:
        pass
    return labels, bool(labels)

# 🚀 【進化12】予想サイトの成績追跡（当たっているサイトを見つけ、精度で重み付けして反映）
def log_site_predictions(df_collected, target_round):
    """各サイトの予想を永続ログ『予想成績ログ』に追記（同じ回号＋同ソースは置き換え）。採点用に消さず残す。"""
    if df_collected is None or df_collected.empty:
        return
    col = "予想数字" if "予想数字" in df_collected.columns else None
    src_col = "ソース" if "ソース" in df_collected.columns else ("サイトURL" if "サイトURL" in df_collected.columns else None)
    if not col or not src_col:
        return
    today = datetime.now(JST).strftime("%Y-%m-%d")
    df_log = load_sheet("予想成績ログ")
    existing = df_log.to_dict("records") if not df_log.empty else []
    incoming = {str(r.get(src_col, "")) for _, r in df_collected.iterrows()}
    kept = [r for r in existing if not (str(r.get("対象回号", "")) == str(target_round) and str(r.get("ソース", "")) in incoming)]
    for _, r in df_collected.iterrows():
        nums = ", ".join(str(int(x)) for x in re.findall(r'\d+', str(r.get(col, ""))) if 1 <= int(x) <= LOTO_MAX_NUM)
        if not nums:
            continue
        kept.append({"対象回号": str(target_round), "ソース": str(r.get(src_col, ""))[:60], "予想数字": nums, "取得日": today})
    save_sheet("予想成績ログ", pd.DataFrame(kept, columns=["対象回号", "ソース", "予想数字", "取得日"]))

def compute_site_leaderboard(df_real):
    """予想成績ログを実データで採点し、サイト別の平均的中でランキング。戻り値: dictのリスト（降順）。"""
    df_log = load_sheet("予想成績ログ")
    if df_log.empty or "ソース" not in df_log.columns:
        return []
    stats = {}
    for _, r in df_log.iterrows():
        actual = actual_numbers_for_round(df_real, str(r.get("対象回号", "")))
        if not actual:
            continue  # 抽選前 or 結果未取得
        pred = set(int(x) for x in re.findall(r'\d+', str(r.get("予想数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM)
        if not pred:
            continue
        stats.setdefault(str(r.get("ソース", "")), []).append(len(pred & actual))
    board = []
    for src, hits in stats.items():
        if hits:
            board.append({"ソース": src, "採点回数": len(hits), "平均的中": round(sum(hits) / len(hits), 2), "最高的中": max(hits), "直近的中": hits[-1]})
    board.sort(key=lambda x: (x["平均的中"], x["採点回数"]), reverse=True)
    return board

def get_trusted_site_numbers(df_real, target_round, top_k=3, min_rounds=2):
    """成績上位サイトが今回(target_round)に予想している数字を、精度で重み付けして返す。戻り値: {num: weight}。"""
    board = compute_site_leaderboard(df_real)
    trusted = [b for b in board if b["採点回数"] >= min_rounds and b["平均的中"] > 0][:top_k]
    if not trusted:
        return {}
    df_log = load_sheet("予想成績ログ")
    if df_log.empty:
        return {}
    weights = {}
    for b in trusted:
        sub = df_log[(df_log["ソース"].astype(str) == b["ソース"]) & (df_log["対象回号"].astype(str) == str(target_round))]
        if sub.empty:
            continue
        for x in re.findall(r'\d+', str(sub.iloc[0].get("予想数字", ""))):
            v = int(x)
            if 1 <= v <= LOTO_MAX_NUM:
                weights[v] = weights.get(v, 0) + b["平均的中"]
    return weights

# 🚀 【進化13】天気×結果の検証（天気が出目に影響しているかを忖度なしで判定）
def analyze_weather_correlation(df_real):
    """天気カテゴリ別に出目傾向（合計・奇数比・高数字比・頻出）を集計。戻り値: (要約テキスト, 表の行リスト)。"""
    if df_real.empty or "天気" not in df_real.columns:
        return "", []
    groups = {}
    for _, r in df_real.iterrows():
        w = str(r.get("天気", "")).strip()
        if not w:
            continue
        nums = [int(r.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(r.get(f"数字{i}", "")).isdigit()]
        if len(nums) == LOTO_PICK_COUNT:
            groups.setdefault(w, []).append(nums)
    rows = []
    for w, draws in groups.items():
        n = len(draws)
        if n == 0:
            continue
        avg_sum = round(sum(sum(d) for d in draws) / n, 1)
        avg_odd = round(sum(sum(1 for x in d if x % 2) for d in draws) / n, 2)
        avg_high = round(sum(sum(1 for x in d if x >= 19) for d in draws) / n, 2)
        cnt = Counter(x for d in draws for x in d)
        top = " ".join(f"{x}({c})" for x, c in cnt.most_common(5))
        rows.append({"天気": w, "回数": n, "平均合計": avg_sum, "平均奇数個": avg_odd, "平均高数字個(19-37)": avg_high, "頻出": top})
    rows.sort(key=lambda x: x["回数"], reverse=True)
    summary = "\n".join(
        f"{r['天気']}: {r['回数']}回 / 平均合計{r['平均合計']} / 平均奇数{r['平均奇数個']}個 / 平均高数字{r['平均高数字個(19-37)']}個 / 頻出 {r['頻出']}"
        for r in rows
    )
    return summary, rows

# 🚀 【進化14】バックテスト：過去データで各レンズが本当に効くか検証（lookahead厳禁・APIゼロ）
def run_backtest(df_real, window=150):
    """各抽選回を『その回より前のデータだけ』で予測・採点し、レンズ別にランダム期待値と比較。
    戻り値: (結果リスト, メタ)。結果が出せない場合は (None, None)。"""
    draws = []
    for _, r in df_real.iterrows():
        rn = re.findall(r'\d+', str(r.get("回号", "")))
        dn = re.findall(r'\d+', str(r.get("抽せん日", "")))
        nums = [int(r.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(r.get(f"数字{i}", "")).isdigit()]
        if not rn or len(dn) < 3 or len(nums) != LOTO_PICK_COUNT:
            continue
        try:
            d = date(int(dn[0]), int(dn[1]), int(dn[2]))
        except Exception:
            continue
        draws.append((int(rn[0]), d, set(nums)))
    draws.sort(key=lambda x: x[0])
    if len(draws) < 70:
        return None, None
    window = min(window, len(draws) - 50)
    start_idx = len(draws) - window
    EXP = 7.0 / LOTO_MAX_NUM  # ある1数字が当選7個に含まれる確率
    env_cache = {}
    def envof(d):
        if d not in env_cache:
            env_cache[d] = get_full_environment(d)
        return env_cache[d]
    keys = ["ランダム(対照)", "過去頻度", "引っ張り", "スライド", "人気回避(32-37)", "量子シード(対照)", "環境共鳴", "全部入り(合成)"]
    edges = {k: [] for k in keys}   # 各回の (実的中 − ランダム期待) を保持し、SE/z値を出す
    hitsum = {k: 0.0 for k in keys}
    expsum = {k: 0.0 for k in keys}
    sizesum = {k: 0.0 for k in keys}
    for i in range(start_idx, len(draws)):
        _, ddate, actual = draws[i]
        prior = draws[:i]  # ← その回より前だけ（未来は一切使わない）
        last = prior[-1][2] if prior else set()
        cnt = Counter(n for _, _, s in prior for n in s)
        tenv = envof(ddate)
        ecnt = Counter()
        for _, pdate, ps in prior:
            penv = envof(pdate)
            if sum(w for ax, w in ENV_AXIS_WEIGHTS.items() if tenv.get(ax) == penv.get(ax)) >= 100:
                for n in ps:
                    ecnt[n] += 1
        fav = {
            "過去頻度": set(n for n, _ in cnt.most_common(7)),
            "引っ張り": set(last),
            "スライド": set(n + dl for n in last for dl in (-1, 1) if 1 <= n + dl <= LOTO_MAX_NUM and (n + dl) not in last),
            "人気回避(32-37)": set(range(32, LOTO_MAX_NUM + 1)),
            "量子シード(対照)": set(generate_dynamic_quantum_seed(str(ddate), "", "", "", "")),
            "環境共鳴": set(n for n, _ in ecnt.most_common(7)),
        }
        combo = Counter()
        for n in fav["過去頻度"]: combo[n] += 1
        for n in fav["引っ張り"]: combo[n] += 2
        for n in fav["スライド"]: combo[n] += 1
        for n in fav["量子シード(対照)"]: combo[n] += 2
        for n in fav["環境共鳴"]: combo[n] += 2
        for n in fav["人気回避(32-37)"]: combo[n] += 1
        fav["全部入り(合成)"] = set(n for n, _ in combo.most_common(7))
        # ランダム(対照)は単発だとブレるので毎回15セットの平均（基準線を安定化）
        rc = sum(len(set(random.sample(range(1, LOTO_MAX_NUM + 1), 7)) & actual) for _ in range(15)) / 15.0
        edges["ランダム(対照)"].append(rc - 7 * EXP); hitsum["ランダム(対照)"] += rc; expsum["ランダム(対照)"] += 7 * EXP; sizesum["ランダム(対照)"] += 7
        for k, fset in fav.items():
            if not fset:
                continue
            h, e = len(fset & actual), len(fset) * EXP
            edges[k].append(h - e); hitsum[k] += h; expsum[k] += e; sizesum[k] += len(fset)
    results = []
    for k in keys:
        es = edges[k]
        n = len(es)
        if n == 0:
            continue
        mh, me, sz = hitsum[k] / n, expsum[k] / n, sizesum[k] / n
        mean_e = sum(es) / n
        var = sum((x - mean_e) ** 2 for x in es) / n
        se = (var ** 0.5) / (n ** 0.5)
        z = (mean_e / se) if se > 0 else 0.0
        kind = "対照" if "対照" in k else ("合成" if "合成" in k else "実レンズ")
        results.append({
            "レンズ": k, "種別": kind, "平均的中": round(mh, 3), "ランダム期待": round(me, 3),
            "リフト(倍)": round(mh / me, 3) if me > 0 else 0, "z値(|2|超で要注目)": round(z, 2),
            "集合サイズ": round(sz, 1), "検証回数": n,
        })
    results.sort(key=lambda x: x["リフト(倍)"], reverse=True)
    return results, {"全データ数": len(draws), "検証窓": window}

# 🚀 【進化2】固定バイアスを破壊する「動的量子シード」生成関数
def generate_dynamic_quantum_seed(date_str, soc_sensor, spirit_sensor, prayer, good_deed):
    """
    プルダウンの文字列と日付を暗号学的に混ぜ合わせ、
    その日・その状況でしか生まれ得ない「特異数字」を導き出す。
    人間の思い込みを完全に排除した真の多角的アプローチ。
    """
    hash_input = f"{date_str}_{soc_sensor}_{spirit_sensor}_{prayer}_{good_deed}".encode('utf-8')
    hex_dig = hashlib.sha256(hash_input).hexdigest()
    
    nums = []
    for i in range(0, len(hex_dig)-1, 2):
        if len(nums) >= 5: break
        val = int(hex_dig[i:i+2], 16) % LOTO_MAX_NUM + 1
        if val not in nums: nums.append(val)
        
    while len(nums) < 5:
        val = random.randint(1, LOTO_MAX_NUM)
        if val not in nums: nums.append(val)
    return nums

@st.cache_data(ttl=900, show_spinner=False)
def _fetch_current_weather():
    """今日の天気・気圧をOpen-Meteoから取得（15分キャッシュ＝連打・画面更新でも再取得しない＝429回避）。
    失敗時は不明を返す（失敗もキャッシュして無駄打ちを防ぐ）。天気は控えめなレンズなので不明でも予測は継続。"""
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=26.2124&longitude=127.6809&current=surface_pressure,weather_code&timezone=Asia%2FTokyo"
        res = requests.get(url, timeout=8, headers={"User-Agent": "loto7-app/1.0"})
        res.raise_for_status()
        data = res.json()
        code = data.get("current", {}).get("weather_code", 0)
        pressure = data.get("current", {}).get("surface_pressure", 1013)
        if code in [0, 1]: weather = "晴れ"
        elif code in [2, 3, 45, 48]: weather = "曇り"
        elif code in [95, 96, 99]: weather = "嵐・荒天"
        else: weather = "雨"
        press_str = "高圧" if pressure > 1015 else "低圧" if pressure < 1009 else "通常"
        return weather, press_str
    except Exception:
        return "不明", "不明"

def get_current_weather_and_pressure():
    return _fetch_current_weather()

def get_moon_age(y, m, d): 
    return ((date(y, m, d) - date(2000, 1, 6)).days) % 29.530588853

def get_moon_and_tide(y, m, d):
    ma = int(round(get_moon_age(y, m, d))) % 30
    if ma in [0,1,2,29]: phase = "新月"
    elif ma in [3,4,5,6]: phase = "三日月"
    elif ma in [7,8,9]: phase = "上弦の月"
    elif ma in [10,11,12,13]: phase = "十三夜"
    elif ma in [14,15,16,17]: phase = "満月"
    elif ma in [18,19,20,21]: phase = "下弦の月"
    elif ma in [22,23,24]: phase = "二十三夜"
    else: phase = "二十六夜"
    
    if ma in [0,1,2,14,15,16,17,29]: tide, gravity = "大潮", "強(極大)"
    elif ma in [7,8,9,22,23,24]: tide, gravity = "小潮", "弱"
    elif ma in [10,25]: tide, gravity = "長潮", "弱"
    elif ma in [11,26]: tide, gravity = "若潮", "中"
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

def get_real_calendar_info(target_date):
    y, m, d = target_date.year, target_date.month, target_date.day
    moon_age = int(round(get_moon_age(y, m, d))) % 30
    kyureki_day = moon_age + 1 if moon_age + 1 <= 30 else 1
    kyureki_month = m - 1 if m > 1 else 12 
    rokuyo = ["大安", "赤口", "先勝", "友引", "先負", "仏滅"][(kyureki_month + kyureki_day) % 6]
    return rokuyo, "特になし"

def get_ryukyu_energy(name, birthday_date, draw_date):
    name_score = sum(ord(char) for char in name) % LOTO_MAX_NUM + 1
    birth_score = (birthday_date.year + birthday_date.month + birthday_date.day) % LOTO_MAX_NUM + 1
    draw_score = (draw_date.year + draw_date.month + draw_date.day) % LOTO_MAX_NUM + 1
    sanctuaries = [{"名前": "魂の浄化", "基調数": 3}, {"名前": "天の息吹", "基調数": 9}, {"名前": "風の躍進", "基調数": 14}, {"名前": "大地の繁栄", "基調数": 21}, {"名前": "深層の覚醒", "基調数": 28}, {"名前": "海神の結び", "基調数": 1}, {"名前": "生命力", "基調数": 36}]
    sanctuary = sanctuaries[(name_score + birth_score + draw_score) % len(sanctuaries)]
    lucky_number = (name_score + birth_score + draw_score + sanctuary["基調数"]) % LOTO_MAX_NUM + 1
    if lucky_number == 0: lucky_number = 1
    return lucky_number, sanctuary["名前"]

def get_next_round_info(df_real):
    default_round = 680
    default_date = date.today()
    while default_date.weekday() != 4: default_date += timedelta(days=1)
    if not df_real.empty and "回号" in df_real.columns:
        try:
            df_real["rn"] = df_real["回号"].apply(lambda x: int(re.findall(r'\d+', str(x))[0]) if re.findall(r'\d+', str(x)) else 0)
            max_round = df_real["rn"].max()
            if max_round > 0: default_round = int(max_round + 1)
            d_nums = re.findall(r'\d+', str(df_real.iloc[0]["抽せん日"]))
            if len(d_nums) >= 3:
                last_date = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                default_date = last_date + timedelta(days=7)
                while default_date.weekday() != 4: default_date += timedelta(days=1)
        except Exception as e: 
            st.warning(f"次回抽選情報の推測計算に失敗しました。デフォルト値を使用します: {e}")
    return default_round, default_date

def get_full_environment(target_date):
    """その日の地球・宇宙の全環境を多角的に取得する（互いに独立した複数の軸）。"""
    phase, tide, gravity = get_moon_and_tide(target_date.year, target_date.month, target_date.day)
    rokuyo, _ = get_real_calendar_info(target_date)
    return {
        "重力": gravity, "潮回り": tide, "月相": phase,
        "干支": get_eto(target_date), "九星": get_fengshui(target_date), "六曜": rokuyo
    }

# 各分析軸の重み（独立性を考慮：月由来の3軸は相互に重複するため控えめ、干支など独立周期は高め）
ENV_AXIS_WEIGHTS = {
    "重力": 60,   # 月のリズム（代表軸）
    "潮回り": 20, # 月由来（重力と重複するため低め）
    "月相": 20,   # 月由来（同上）
    "干支": 80,   # 60日周期の独立軸（最も強い独立シグナル）
    "九星": 50,   # 9日周期の独立軸
    "六曜": 30,   # 6日周期の独立軸
}

def find_doppelganger_days(target_date, df_real):
    if df_real.empty: return [], Counter()
    t_env = get_full_environment(target_date)

    results = []
    error_shown = False
    for _, row in df_real.iterrows():
        try:
            d_nums = re.findall(r'\d+', str(row["抽せん日"]))
            if len(d_nums) >= 3:
                y = int(d_nums[0])
                if y < 100: y += 2000
                past_date = date(y, int(d_nums[1]), int(d_nums[2]))
                if past_date >= target_date: continue
                
                p_env = get_full_environment(past_date)
                score = 0
                match_details = []
                for axis, weight in ENV_AXIS_WEIGHTS.items():
                    if t_env.get(axis) == p_env.get(axis):
                        score += weight
                        match_details.append(f"{axis}({t_env.get(axis)})")

                # 月由来だけの一致では不十分。独立軸を含む3項目以上かつ高スコアのみ採用
                if score >= 150 and len(match_details) >= 3:
                    nums = [int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()]
                    if len(nums) == LOTO_PICK_COUNT:
                        results.append({"回号": row.get("回号", ""), "日付": past_date.strftime("%Y-%m-%d"), "スコア": score, "一致項目": "・".join(match_details), "本数字": nums})
        except Exception as e: 
            if not error_shown:
                st.warning(f"ドッペルゲンガー探索中に過去データの解析エラーが発生しました。一部をスキップして続行します: {e}")
                error_shown = True
            
    results.sort(key=lambda x: x["スコア"], reverse=True)
    top_matches = results[:5]
    sync_counts = Counter([n for tm in top_matches for n in tm["本数字"]])
    return top_matches, sync_counts

def analyze_environment_resonance(target_date, df_real):
    """
    過去の全抽選について「どの環境軸が今回と一致したか」を独立軸ごとに判定し、
    一致した軸ごとに出た数字を集計する。月だけに偏らない真の多角分析。
    戻り値: (軸ごとの数字集計 dict, 数字ごとの共鳴スコア Counter, 今回の環境指紋 dict)
    """
    if df_real.empty:
        return {}, Counter(), {}
    target_env = get_full_environment(target_date)
    axis_counters = {axis: Counter() for axis in ENV_AXIS_WEIGHTS}
    resonance = Counter()
    error_shown = False
    for _, row in df_real.iterrows():
        try:
            d_nums = re.findall(r'\d+', str(row.get("抽せん日", "")))
            if len(d_nums) < 3: continue
            y = int(d_nums[0])
            if y < 100: y += 2000
            past_date = date(y, int(d_nums[1]), int(d_nums[2]))
            if past_date >= target_date: continue
            past_env = get_full_environment(past_date)
            nums = [int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()]
            if len(nums) != LOTO_PICK_COUNT: continue
            for axis, weight in ENV_AXIS_WEIGHTS.items():
                if past_env.get(axis) == target_env.get(axis):
                    axis_counters[axis].update(nums)
                    for n in nums:
                        resonance[n] += weight / LOTO_PICK_COUNT
        except Exception as e:
            if not error_shown:
                st.warning(f"環境共鳴分析中に一部データの解析エラーが発生しました。スキップして続行します: {e}")
                error_shown = True
    return axis_counters, resonance, target_env

def analyze_winning_environment(df_note, df_real):
    """
    ご主人が実際に当てた回（3個一致以上＝6等以上）の環境を抽出・集計し、
    『当選時に共通する地球・宇宙・暦の条件』を多角的に浮かび上がらせる。
    戻り値: (的中回の一覧 list, 軸ごとの当選環境集計 dict)
    """
    if df_note.empty or df_real.empty:
        return [], {axis: Counter() for axis in ENV_AXIS_WEIGHTS}
    hits = []
    win_env = {axis: Counter() for axis in ENV_AXIS_WEIGHTS}
    seen = set()
    for _, row in df_note.iterrows():
        advice = str(row.get("AIの助言", ""))
        m = re.search(r'(\d+)\s*個的中', advice)
        hit_count = int(m.group(1)) if m else 0
        if hit_count < 3:  # ロト7は3個一致（6等）から下位等級。記録対象は3個以上
            continue
        round_str = str(row.get("対象回号", ""))
        rn = re.findall(r'\d+', round_str)
        if not rn: continue
        key = (rn[0], tuple(str(row.get(f"数字{i}", "")) for i in range(1, LOTO_PICK_COUNT + 1)))
        if key in seen: continue
        seen.add(key)
        match = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if match.empty: continue
        d_nums = re.findall(r'\d+', str(match.iloc[0].get("抽せん日", "")))
        if len(d_nums) < 3: continue
        y = int(d_nums[0]); y = y + 2000 if y < 100 else y
        try:
            draw_date = date(y, int(d_nums[1]), int(d_nums[2]))
        except Exception:
            continue
        env = get_full_environment(draw_date)
        for axis in ENV_AXIS_WEIGHTS:
            win_env[axis][env[axis]] += 1
        hits.append({"回号": round_str, "抽選日": draw_date.strftime("%Y-%m-%d"), "的中数": hit_count, "等級": advice, "環境": env})
    return hits, win_env

def get_recent_lessons(limit=3):
    """過去の反省会で得た学びを取得し、予測AIに引き継ぐ（PDCAの『Act＝次への反映』を実装）。"""
    try:
        df_log = load_sheet("反省ログ")
        if df_log.empty or "AIの学び" not in df_log.columns:
            return ""
        return "\n---\n".join(df_log.head(limit)["AIの学び"].astype(str).tolist())
    except Exception:
        return ""

def detect_prediction_bias(df_note, recent_rounds=4, threshold=0.45):
    """直近数回の積み上げ予測で、特定の数字に偏りすぎていないかを検知（忖度しない＝偏りを暴く）。
    戻り値: 警告テキスト（偏りが無ければ空文字）。"""
    try:
        if df_note.empty or "対象回号" not in df_note.columns:
            return ""
        def ext(s):
            m = re.findall(r'\d+', str(s))
            return int(m[0]) if m else 0
        rounds = sorted({r for r in df_note["対象回号"].tolist()}, key=ext, reverse=True)[:recent_rounds]
        sub = df_note[df_note["対象回号"].isin(rounds)]
        total_lines = 0
        cnt = Counter()
        for _, row in sub.iterrows():
            nums = [int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()]
            if len(nums) == LOTO_PICK_COUNT:
                total_lines += 1
                cnt.update(set(nums))
        if total_lines < 10:
            return ""
        over = [(n, c / total_lines) for n, c in cnt.most_common() if c / total_lines >= threshold]
        if not over:
            return ""
        items = "、".join(f"{n}（{round(r*100)}%の口に出現）" for n, r in over[:6])
        return f"直近{len(rounds)}回・{total_lines}口の分析：数字 {items} に偏りがあります。同じ数字に頼りすぎている可能性があり、外れた時に共倒れするリスク大。"
    except Exception:
        return ""

def compute_my_lens_performance(df_note):
    """自分の予測ノートを、割り当てたレンズ（予測ロジック）別に採点集計。どの可能性が近いかを学ぶ用（剪定はしない）。"""
    if df_note.empty or "予測ロジック" not in df_note.columns or "AIの助言" not in df_note.columns:
        return []
    stats = {}
    for _, r in df_note.iterrows():
        m = re.search(r'(\d+)個的中', str(r.get("AIの助言", "")))
        if not m:
            continue
        lens = str(r.get("予測ロジック", "")).strip() or "不明"
        stats.setdefault(lens, []).append(int(m.group(1)))
    board = [{"レンズ(可能性)": k, "採点口数": len(v), "平均的中": round(sum(v) / len(v), 2), "最高的中": max(v)} for k, v in stats.items() if v]
    board.sort(key=lambda x: (x["平均的中"], x["採点口数"]), reverse=True)
    return board

def compute_overall_stats(df_note):
    """予測ノート全体を集計し、通算成績（採点口数・平均的中・等級別回数・ニアピン）を返す。"""
    if df_note.empty or "AIの助言" not in df_note.columns:
        return None
    hits_list, near_total, dist = [], 0, Counter()
    for _, r in df_note.iterrows():
        s = str(r.get("AIの助言", ""))
        m = re.search(r'(\d+)個的中', s)
        if not m:
            continue
        h = int(m.group(1))
        hits_list.append(h)
        dist[h] += 1
        nm = re.search(r'ニアピン\s*(\d+)', s)
        if nm:
            near_total += int(nm.group(1))
    if not hits_list:
        return None
    label = {7: "1等", 6: "2〜3等", 5: "4等", 4: "5等", 3: "6等"}
    rows = [{"一致個数": f"{h}個", "等級": label.get(h, "—"), "回数(口)": dist[h]} for h in sorted(dist, reverse=True)]
    return {
        "総採点口数": len(hits_list),
        "平均的中": round(sum(hits_list) / len(hits_list), 3),
        "最高一致": max(hits_list),
        "ニアピン総数": near_total,
        "分布": rows,
    }

def detect_carryover(df_real):
    """キャリーオーバー自動検出：最新回の1等口数が『該当なし/0』なら次回へ繰越中（公式ルール）。"""
    try:
        if df_real is None or df_real.empty: return False
        v = str(df_real.iloc[0].get("1等口数", "")).strip()
        if not v: return False
        return ("該当なし" in v) or (re.sub(r"[^0-9]", "", v) == "0")
    except Exception:
        return False

def auto_check_hits(df_note, df_real):
    if df_note.empty or df_real.empty: return df_note
    if "AIの助言" not in df_note.columns: df_note["AIの助言"] = "未照合"
    updated = False
    error_shown = False
    # 回号は数字だけで照合（第/回/空白/表記ゆれでも取りこぼさない）＝無警告の採点ゼロを防ぐ
    real_key = df_real["回号"].astype(str).str.replace(r"[^0-9]", "", regex=True) if "回号" in df_real.columns else None
    for idx, row in df_note.iterrows():
        adv = str(row.get("AIの助言", ""))
        # 公式ルール採点済み(＋B表記あり)はスキップ。旧形式はボーナス対応で再採点する。
        if "＋B" in adv: continue
        _tn = re.sub(r"[^0-9]", "", str(row.get("対象回号", "")))
        match = df_real[real_key == _tn] if (real_key is not None and _tn) else df_real[df_real.get("回号", "") == str(row.get("対象回号", ""))]
        if not match.empty:
            try:
                actual = set([int(match.iloc[0].get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(match.iloc[0].get(f"数字{i}", "")).isdigit()])
                bonus = set([int(match.iloc[0].get(c)) for c in ("ボーナス1", "ボーナス2") if str(match.iloc[0].get(c, "")).strip().isdigit()])
                pred = set([int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()])
                hits = len(actual & pred)
                b_hits = len(bonus & pred)
                near_pins = sum(1 for p in pred if p not in actual and ((p-1) in actual or (p+1) in actual))
                if bonus:
                    # ★公式ルール準拠（宝くじ公式サイト）：ボーナスは2等/6等の判定に使用
                    if hits == 7: grade = "👑 1等当せん！"
                    elif hits == 6 and b_hits >= 1: grade = "✨ 2等当せん！"
                    elif hits == 6: grade = "✨ 3等当せん！"
                    elif hits == 5: grade = "🎯 4等当せん！"
                    elif hits == 4: grade = "🎉 5等当せん！"
                    elif hits == 3 and b_hits >= 1: grade = "🎊 6等当せん！"
                    else: grade = "ハズレ"
                    df_note.at[idx, "AIの助言"] = f"{LOTO_PICK_COUNT}個中 {hits}個的中＋B{b_hits}【{grade}】 / ニアピン {near_pins}個"
                else:
                    # ボーナス未取得の回は暫定採点（土曜の全期間取り込みで自動的に公式採点へ更新される）
                    grade = "👑 1等当せん！" if hits == 7 else "✨ 2等/3等相当" if hits == 6 else "🎯 4等当せん！" if hits == 5 else "🎉 5等当せん！" if hits == 4 else "6等の可能性(B未取得)" if hits == 3 else "ハズレ"
                    df_note.at[idx, "AIの助言"] = f"{LOTO_PICK_COUNT}個中 {hits}個的中【{grade}】 / ニアピン {near_pins}個"
                updated = True
            except Exception as e:
                if not error_shown:
                    st.warning(f"自動採点中に一部データでエラーが発生しました。スキップして続行します: {e}")
                    error_shown = True
    if updated: save_sheet("予測ノート", df_note)
    return df_note

def get_ai_intuition_numbers(feeling, weather, gravity, target_date):
    if not api_key: return random.sample(range(1, LOTO_MAX_NUM + 1), 3)
    prompt = f"""あなたは10億円のロト7を狙う最強の予知能力を持った天才科学者です。
次の情報から波動を読み取り、純粋な直感・予知で次回ロト7の数字（1〜{LOTO_MAX_NUM}）を3つ選んでください。
- 実行者の今日の気持ち・心境: {feeling if feeling else "（特になし）"}
- 地球の引力: {gravity} / 天気: {weather}
- 抽選予定日: {target_date}
理由・説明・絵文字は一切出力せず、「7, 15, 32」のようにカンマ区切りの数字だけを出力してください。"""
    text = ask_claude(prompt, max_tokens=80, model=MODEL_LIGHT)
    if not text:
        return random.sample(range(1, LOTO_MAX_NUM + 1), 3)
    seen = []
    for n in [int(x) for x in re.findall(r'\d+', text) if 1 <= int(x) <= LOTO_MAX_NUM]:
        if n not in seen: seen.append(n)
    return seen[:3] if len(seen) >= 3 else random.sample(range(1, LOTO_MAX_NUM + 1), 3)

# 🚀 【進化8】結果取得（UTF-8固定＋リトライ。文字化けで0件＝更新されない不具合を解消）
def fetch_loto7_results_ohtashp(existing_rounds):
    """ohtashp.comからロト7結果を取得。戻り値: (new_data行リスト, 取得成功フラグ)。
    取得成功フラグ=Trueは『サイトから表を解析できた』意味（新規が無くてもTrue）。"""
    cols_tail = ["", "", "", "", "", "", ""]  # 六曜/干支/風水/吉凶日/月齢/潮回り/重力 のうち月齢以降を埋める
    for attempt in range(4):
        try:
            res = requests.get(
                "https://www.ohtashp.com/topics/takarakuji/loto7/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20,
            )
            # ★HTTPヘッダに文字コードが無く ISO-8859-1 と誤認されるため、UTF-8で直接デコード
            soup = BeautifulSoup(res.content.decode("utf-8", errors="replace"), "html.parser")
            parsed = []
            for row in soup.find_all("tr"):
                th = row.find("th")
                if not th or "第" not in th.get_text():
                    continue
                tds = row.find_all("td")
                hon_tds = row.find_all("td", class_=lambda c: c and "hon" in c)
                if len(tds) < 10 or len(hon_tds) != LOTO_PICK_COUNT:
                    continue
                parsed.append((th.get_text(strip=True), tds[0].get_text(strip=True),
                               [td.get_text(strip=True) for td in hon_tds]))
            if parsed:
                new_data = []
                for draw_num, date_str, hon_nums in parsed:
                    if draw_num in existing_rounds:
                        continue
                    d_nums = re.findall(r'\d+', date_str)
                    if len(d_nums) >= 3:
                        dd = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                        m_phase, m_tide, m_gravity = get_moon_and_tide(dd.year, dd.month, dd.day)
                    else:
                        m_phase, m_tide, m_gravity = "", "", ""
                    new_data.append([draw_num, date_str] + hon_nums + ["", "", "", "", m_phase, m_tide, m_gravity])
                return new_data, True
        except Exception:
            pass
        time.sleep(1)
    return [], False

def fetch_latest_loto7_via_web(existing_rounds):
    """ohtashpが不調なときのフォールバック：Claudeのウェブ検索で最新結果を取得。戻り値: (new_data, エラー)。"""
    client = get_claude_client()
    if client is None:
        return [], "Claudeのキー（ANTHROPIC_API_KEY）が未設定です。"
    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
    ]
    prompt = f"""ロト7の最新の当選結果を、みずほ銀行など公式・信頼できる情報源でウェブ検索して確認してください。
直近3回分について、回号・抽せん日・本数字7個（ボーナス数字は除く）を返します。
必ず複数のソースで一致を確認した正確な値だけを採用し、確信が持てない回は含めないこと。本数字は1〜37の7個です。

最後に、必ず次のJSONだけを ```json コードブロックで出力してください:
```json
[{{"round": "第683回", "date": "2026-06-26", "numbers": [1, 5, 12, 19, 24, 30, 37]}}]
```"""
    messages = [{"role": "user", "content": prompt}]
    text = ""
    try:
        for _ in range(4):
            r = client.messages.create(model=MODEL_MAIN, max_tokens=2000, tools=tools, messages=messages)
            if r.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": r.content})
                continue
            text = "".join(b.text for b in r.content if b.type == "text")
            break
    except Exception as e:
        return [], f"ウェブ検索に失敗しました: {e}"

    m = re.search(r'```json\s*(.+?)\s*```', text, re.DOTALL)
    raw = m.group(1) if m else (re.search(r'\[.*\]', text, re.DOTALL).group(0) if re.search(r'\[.*\]', text, re.DOTALL) else "")
    try:
        data = json.loads(raw)
    except Exception:
        return [], "ウェブ検索の結果を解析できませんでした。"
    if not isinstance(data, list):
        return [], "ウェブ検索の結果形式が想定と異なりました。"

    new_data = []
    for it in data:
        if not isinstance(it, dict):
            continue
        rd = str(it.get("round", "")).strip()
        if not rd or rd in existing_rounds:
            continue
        nums = []
        for n in it.get("numbers", []):
            try:
                v = int(n)
            except Exception:
                continue
            if 1 <= v <= LOTO_MAX_NUM:
                nums.append(v)
        if len(nums) != LOTO_PICK_COUNT:
            continue
        date_str = str(it.get("date", "")).strip()
        d_nums = re.findall(r'\d+', date_str)
        if len(d_nums) >= 3:
            try:
                dd = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                m_phase, m_tide, m_gravity = get_moon_and_tide(dd.year, dd.month, dd.day)
            except Exception:
                m_phase, m_tide, m_gravity = "", "", ""
        else:
            m_phase, m_tide, m_gravity = "", "", ""
        new_data.append([rd, date_str] + [str(n) for n in nums] + ["", "", "", "", m_phase, m_tide, m_gravity])
    return new_data, None

# 🚀 【進化11】全期間バックフィル（第1回〜最新の全当選番号＋東京の実天気を取り込む）
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
    """東京の過去の日次天気（Open-MeteoのERA5再解析。2013年〜現在を全期間カバー）を範囲取得。
    戻り値: {YYYY-MM-DD: (天気, 気温, 降水, 気圧)}。"""
    out = {}
    try:
        url = ("https://archive-api.open-meteo.com/v1/archive"
               f"?latitude=35.69&longitude=139.69&start_date={start_date}&end_date={end_date}"
               "&daily=weather_code,temperature_2m_mean,precipitation_sum,pressure_msl_mean"
               "&timezone=Asia%2FTokyo")
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
        st.warning(f"過去天気の取得に一部失敗しました（天気欄は空で続行します）: {e}")
    return out

def fetch_loto7_full_history():
    """lotoseven.com から全回の (回号int, 'YYYY-MM-DD', [本数字7], [ボーナス2], [等級別当せん口数6]) を取得。
    ボーナス数字は公式ルールの2等/6等判定に必須。当せん口数は人気（分け前）分析とキャリーオーバー検出に使う。"""
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
        bonus = [c.zfill(2) for c in cells[9:11] if re.fullmatch(r"\d{1,2}", c)] if len(cells) >= 11 else []
        winners = [c for c in cells[11:17]] if len(cells) >= 17 else []
        rows.append((int(cells[0]), ymd, [c.zfill(2) for c in nums], bonus, winners))
    return rows

def backfill_full_history():
    """全回の当選番号＋暦＋東京の実天気で『実データ』を全期間版に再構築。戻り値: (df, エラー)。"""
    rows = fetch_loto7_full_history()
    if not rows:
        return None, "全履歴の取得に失敗しました（取得元の構造が変わった可能性があります）。"
    rows.sort(key=lambda x: x[0], reverse=True)  # 新しい回を上に
    dates = [r[1] for r in rows]
    wmap = fetch_tokyo_weather_range(min(dates), max(dates))
    data = []
    for kai, ymd, nums, bonus, winners in rows:
        y, mo, da = (int(v) for v in ymd.split("-"))
        dd = date(y, mo, da)
        m_phase, m_tide, m_gravity = get_moon_and_tide(y, mo, da)
        rokuyo, _ = get_real_calendar_info(dd)
        w = wmap.get(ymd, ("", "", "", ""))
        row = {"回号": f"第{kai}回", "抽せん日": ymd}
        for i, n in enumerate(nums):
            row[f"数字{i+1}"] = n
        row["ボーナス1"] = bonus[0] if len(bonus) >= 1 else ""
        row["ボーナス2"] = bonus[1] if len(bonus) >= 2 else ""
        for gi in range(6):
            row[f"{gi+1}等口数"] = winners[gi] if gi < len(winners) else ""
        row.update({"六曜": rokuyo, "干支": get_eto(dd), "風水": get_fengshui(dd), "吉凶日": "特になし",
                    "月齢": m_phase, "潮回り": m_tide, "重力状態": m_gravity,
                    "天気": w[0], "気温": w[1], "降水": w[2], "気圧": w[3]})
        data.append(row)
    cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + \
           ["ボーナス1", "ボーナス2"] + [f"{g}等口数" for g in range(1, 7)] + \
           ["六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態", "天気", "気温", "降水", "気圧"]
    df = pd.DataFrame(data, columns=cols)
    save_sheet("実データ", df)
    return df, None

# 🚀 【進化9】週次サイクル：金19:30抽選＝リセットを基点に「今日やること」を判定
def get_week_phase():
    """戻り値: (今日のweekday, 抽選後フラグ, 7日サイクル表示用リスト, 今日のミッション)。
    金曜の抽選（夜）後〜土曜に「答え合わせ＆振り返り」、土〜木に「積み上げ」。"""
    now = datetime.now(JST)
    wd = now.weekday()  # 月=0 ... 日=6
    after_draw = (wd == 4 and (now.hour, now.minute) >= (19, 30))  # 金曜の抽選後
    # 表示用：土→日→月→火→水→木→金
    days = [("土", "結果確認", 5), ("日", "積み上げ", 6), ("月", "積み上げ", 0),
            ("火", "積み上げ", 1), ("水", "積み上げ", 2), ("木", "ゆっくり", 3), ("金", "分析・購入", 4)]
    missions = {
        5: ("結果を見るだけ（採点は自動済み）", "結果取得と採点は朝に自動で完了しています。当たりを確かめて、気が向いたら来週の積み上げを。", "結果を確認する", "最新データ取得"),
        6: ("予測の積み上げ（任意・楽しむ用）", "今日の気持ちを言葉にして積み上げます。毎日でなくてOK。", "予測を積み上げる", "日々の予想・積上げ"),
        0: ("積み上げを重ねる（任意）", "気が向いたら、今日の気持ちを核に予測を厚くします。", "予測を積み上げる", "日々の予想・積上げ"),
        1: ("積み上げの日（任意）", "今日の気持ちをひと言残して積み上げ。無理のない範囲で。", "予測を積み上げる", "日々の予想・積上げ"),
        2: ("積み上げを継続（任意）", "ぶれずに毎日の波長を重ねます。無理のない範囲で。", "予測を積み上げる", "日々の予想・積上げ"),
        3: ("明日は金曜。今日はゆっくりでOK", "他サイトの予想収集は明日の朝に“自動”で走ります。今日は何もしなくて大丈夫。", "予測を積み上げる", "日々の予想・積上げ"),
        4: ("★金曜：Claudeと分析 → 購入（朝6〜8時）★", "Claude（Cowork）を開いて「ロト7の続きから」と言うだけ。一緒に統計を分析して買い目を決め、朝のうちに購入を。ここだけがあなたの出番です。", "今日の積み上げ（任意）", "日々の予想・積上げ"),
    }
    if after_draw:
        mission = ("抽選おつかれさまです（あとは自動）", "結果取得と採点は明日の朝に自動で済みます。今夜はゆっくり。飲み会でも大丈夫。", "結果を確認する", "最新データ取得")
    else:
        mission = missions[wd]
    return wd, after_draw, days, mission

# ==========================================
# 5. メインUIレンダリング（天才科学者の管制室）
# ==========================================

# 🔒 アクセス認証：合言葉が無いと“以降を一切実行しない”（勝手にアプリ/AIを使われる＝課金被害を防ぐ最重要の守り）
APP_PASSWORD = st.secrets.get("APP_PASSWORD", os.environ.get("APP_PASSWORD", ""))
if APP_PASSWORD and not st.session_state.get("_authed", False):
    st.markdown("<div class='brand'><div class='crest'>🔒</div><div class='ttl'>ロト7 くがに堂</div><div class='sub'>家族専用 ・ 合言葉が必要です</div></div>", unsafe_allow_html=True)
    _pw = st.text_input("合言葉を入力してください", type="password", key="_login_pw")
    if st.button("入る", type="primary"):
        if _pw == APP_PASSWORD:
            st.session_state["_authed"] = True
            st.rerun()
        else:
            st.error("合言葉が違います。")
    st.caption("※このアプリは公開URLですが、合言葉が無いと中身もAIも一切動きません。")
    st.stop()  # ← 認証前はここで完全停止（データ表示もAPI呼び出しも実行されない）

if st.session_state.menu != "ホーム":
    st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
    st.button("総合案内（ホーム）に戻る", on_click=change_menu, args=("ホーム",))
    st.markdown("</div><hr>", unsafe_allow_html=True)

if st.session_state.menu == "ホーム":
    now_jst = datetime.now(JST)
    wd, after_draw, days, mission = get_week_phase()
    week_jp = "月火水木金土日"[wd]
    date_disp = f"{now_jst.month}/{now_jst.day}（{week_jp}）"

    # ブランドヘッダー
    st.markdown(
        "<div class='brand'><div class='crest'>◆ ◆ ◆</div>"
        "<div class='ttl'>ロト7 くがに堂</div>"
        "<div class='sub'>くがに＝沖縄の言葉で“黄金” ・ 土生金の金運の間</div></div>",
        unsafe_allow_html=True,
    )

    # 週次サイクル・ステッパー（今日を強調）
    nodes = "".join(
        f"<div class='wn{(' active' if dnum == wd else '')}'><div class='d'>{label}</div><div class='a'>{action}</div></div>"
        for label, action, dnum in days
    )
    st.markdown(f"<div class='week'>{nodes}</div><div class='reset-note'>― 土〜木＝積み上げ（任意）／金＝Claudeと分析→購入 ―</div>", unsafe_allow_html=True)

    # 今日のミッション
    st.markdown(
        f"<div class='mission'><div class='lbl'>TODAY'S MISSION ・ {date_disp}</div>"
        f"<div class='mt'>{mission[0]}</div><div class='ds'>{mission[1]}</div></div>",
        unsafe_allow_html=True,
    )
    st.button(f"▶ {mission[2]}", on_click=change_menu, args=(mission[3],))
    st.caption("🤖 結果取得・採点・他サイト収集は全部“自動”です。あなたの出番は【積み上げ＝任意】と【金曜：Claudeと分析→購入】だけ。")

    # ステータス
    df_real = load_sheet("実データ")
    next_round, _ = get_next_round_info(df_real)
    df_note = load_sheet("予測ノート")
    stacked = len(df_note[df_note["対象回号"] == f"第{next_round}回"]) if (not df_note.empty and "対象回号" in df_note.columns) else 0
    _co_home = detect_carryover(df_real)
    st.markdown(
        f"<div class='stats'>"
        f"<div class='stat'><div class='v'>第{next_round}回</div><div class='k'>NEXT DRAW</div></div>"
        f"<div class='stat'><div class='v'>{stacked}口</div><div class='k'>STACKED</div></div>"
        f"<div class='stat'><div class='v'>{'💰 CO中' if _co_home else '—'}</div><div class='k'>CARRYOVER</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if _co_home:
        st.markdown("<div class='cowork-note'>💰 <b>キャリーオーバー発生中！</b> 前回は1等該当なし＝賞金が次回へ繰越（最高12億円）。積み上げの💰スイッチは自動でONになります。</div>", unsafe_allow_html=True)

    # メニュー（シンプル2ボタン）
    st.markdown("<div class='sec-label'>― メニュー ―</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("🌍 予測の積み上げ（今日の気持ち）", on_click=change_menu, args=("日々の予想・積上げ",))
    with c2:
        st.button("📡 結果確認（当選番号と採点）", on_click=change_menu, args=("最新データ取得",))
    st.markdown("<div class='cowork-note'>💬 <b>金曜の分析はClaudeで</b> ― Coworkを開いて「ロト7の続きから」と言うだけ。統計を一緒に見て買い目を決めます。</div>", unsafe_allow_html=True)

    if get_gspread_client() is None:
        st.error("データベース接続設定（Secrets）が未完了です。")


elif st.session_state.menu == "最新データ取得":
    st.title("📡 結果確認")
    st.caption("結果の取得・採点は毎週土曜の朝に自動で済んでいます。ここでは最新の当選番号と、あなたの予測の採点を確認できます。")

    # 最新の当選番号と自分の採点（見るだけ）
    _dfr = load_sheet("実データ")
    if not _dfr.empty and "回号" in _dfr.columns:
        _last = _dfr.iloc[0]
        _win = [str(_last.get(f"数字{i}", "")) for i in range(1, LOTO_PICK_COUNT + 1)]
        _bn = [str(_last.get(c, "")).strip() for c in ("ボーナス1", "ボーナス2")]
        _bn_txt = f"　＋　ボーナス {_bn[0]}・{_bn[1]}" if all(_bn) else ""
        _co_txt = "<div class='ds' style='color:#A94A32;font-weight:700;'>💰 前回1等該当なし → キャリーオーバー中（次回は高額！）</div>" if detect_carryover(_dfr) else ""
        st.markdown(
            f"<div class='mission'><div class='lbl'>最新の当選番号 ・ {_last.get('回号','')}（{_last.get('抽せん日','')}）</div>"
            f"<div class='mt'>{'　'.join(_win)}<span style='font-size:15px;color:#8A7A5F;'>{_bn_txt}</span></div>{_co_txt}</div>", unsafe_allow_html=True)
        _dfn = load_sheet("予測ノート")
        if not _dfn.empty and "対象回号" in _dfn.columns:
            _mine = _dfn[_dfn["対象回号"].astype(str) == str(_last.get("回号", ""))]
            if not _mine.empty and "AIの助言" in _mine.columns:
                _hits = _mine["AIの助言"].astype(str).str.extract(r"(\d+)個的中")[0].dropna().astype(int)
                if not _hits.empty:
                    _best = int(_hits.max())
                    _grade = "🎉 5等以上！" if _best >= 4 else ("惜しい！" if _best == 3 else "次へ")
                    st.markdown(f"**あなたの最高：{_best}個的中**（{len(_mine)}口中）{_grade}")
                _show = ["AIの助言", "実行者"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["予測ロジック"]
                st.dataframe(_mine[[c for c in _show if c in _mine.columns]], height=280, use_container_width=True)

    st.markdown("---")
    st.caption("👇 自動より先に確認したい時だけ、手動で取り込めます（普段は不要）。")
    if st.button("データ同期および自動採点を実行する"):
        with st.spinner("通信中...最新の当選結果を解析し、予想と照合しています..."):
            try:
                df_real = load_sheet("実データ")
                existing_rounds = df_real["回号"].astype(str).tolist() if not df_real.empty and "回号" in df_real.columns else []

                # ① まず ohtashp.com（UTF-8固定＋リトライ。文字化けで0件→更新されない不具合を解消）
                new_data, site_ok = fetch_loto7_results_ohtashp(existing_rounds)
                source = "ohtashp.com"

                # ② サイトが不調（表を1件も解析できない）なら、Claudeのウェブ検索で補完
                if not site_ok:
                    web_data, web_err = fetch_latest_loto7_via_web(existing_rounds)
                    if web_data:
                        new_data, source = web_data, "ウェブ検索（Claude）"
                    elif web_err:
                        st.caption(f"（ウェブ検索フォールバック: {web_err}）")

                if new_data:
                    cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態"]
                    df_new = pd.DataFrame(new_data, columns=cols)
                    df_combined = pd.concat([df_new, df_real], ignore_index=True) if not df_real.empty else df_new
                    save_sheet("実データ", df_combined)
                    auto_check_hits(load_sheet("予測ノート"), df_combined)
                    st.success(f"最新結果（取得元: {source}）を {len(new_data)} 件取り込み、全予想を自動採点しました！")
                    st.dataframe(df_new[["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)]])
                    if source.startswith("ウェブ"):
                        st.caption("※ウェブ検索で取得した番号です。念のためみずほ銀行の公式発表と照合してください。")
                elif site_ok:
                    auto_check_hits(load_sheet("予測ノート"), df_real)
                    st.info("データベースは既に最新です。既存の予測ノートを再採点しました。")
                else:
                    auto_check_hits(load_sheet("予測ノート"), df_real)
                    st.warning("結果の取得元が一時的に不安定で、新しい結果を取得できませんでした。数分おいて再実行してください（既存の予測ノートは再採点しました）。")
            except Exception as e:
                st.error(f"データの同期・解析中にエラーが発生しました: {e}")

    st.markdown("---")
    st.markdown("### 📚 過去の全当選番号を一括取り込み（全期間＋日付＋東京の実天気）")
    st.markdown("<div class='info-box'>第1回〜最新まで<b>全回の当選番号</b>を取り込み、各回の月齢・暦に加え<b>東京（抽選地）の実際の天気（気象庁モデル）</b>も付与します。データが豊富なほど各レンズの傾向分析が鋭くなり、「天気の影響」も検証できます。<br>（実データを全期間版に置き換えます。月1回ほど押せば天気も最新化されます）</div>", unsafe_allow_html=True)
    if st.button("📚 全期間の当選番号＋天気を取り込む（30秒〜1分）"):
        with st.spinner("全回の当選番号と、東京の過去天気（気象庁モデル）を取得しています..."):
            df_full, err = backfill_full_history()
        if err:
            st.error(err)
        else:
            auto_check_hits(load_sheet("予測ノート"), df_full)
            st.success(f"全 {len(df_full)} 回の当選番号を取り込み、天気を付与して、全予想を再採点しました！")
            show_cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["天気", "気温", "気圧"]
            st.dataframe(df_full[[c for c in show_cols if c in df_full.columns]].head(20))

elif st.session_state.menu == "日々の予想・積上げ":
    st.title("🌍 地球規模の量子環境分析＆日々の予測積上げ")
    st.markdown("<div class='info-box'>明日、来週、その先へ。人間のバイアスを完全に破壊し、その日の宇宙の波動（動的量子シード）と物理演算（隣接波及効果）を融合させて真理の30口を積み上げます。</div>", unsafe_allow_html=True)
    
    df_real = load_sheet("実データ")
    auto_round, auto_date = get_next_round_info(df_real)
    
    operator = st.radio("本日の実行者", [u1_name, u2_name], horizontal=True)
    
    with st.form("daily_form"):
        c1, c2 = st.columns(2)
        target_rounds = [f"第{auto_round + i}回" for i in range(-5, 10) if auto_round + i > 0]
        target_round_str = c1.selectbox("予測対象の回号（未来も指定可能）", target_rounds, index=target_rounds.index(f"第{auto_round}回") if f"第{auto_round}回" in target_rounds else 0)
        draw_date = c2.date_input("対象となる抽選予定日", value=auto_date)
        
        st.markdown("#### 💗 今日のあなたの気持ち・心境（プログラムがこれを読み取ります）")
        st.caption("プルダウンで飾る必要はありません。いま感じていること・今日の出来事・祈り・直感を、そのまま自由に書いてください。書いた言葉そのものが、その日だけの量子シードとAI分析の核になります。空欄でもOKです。")
        feeling = st.text_area(
            "今日の気持ち（自由入力）",
            placeholder="例：今朝カラスが3羽鳴いていた。なんとなく胸騒ぎがする。家族が健康でいられますように。仕事は落ち着いている。",
            height=150
        )

        use_fortune = st.checkbox("🔮 保存済みのラッキーナンバーを軽く加味する（控えめウェイト・任意）", value=False, help="シート『占いラッキー』に保存された数字を控えめに加点します（金曜のClaude分析で更新できます）。")

        gen_mode = st.radio(
            "🧪 生成モード",
            ["🎲 探索モード（1口ずつ違う可能性・各レンズに分散）", "🎯 集中モード（全レンズを合成した加重）"],
            index=0,
            help="探索モード＝30口を『過去頻度・引っ張り・環境共鳴・占い・他サイト…』など別々の可能性に1口ずつ割り当て、抽選後にどのレンズが近かったかを学びます（剪定はしません）。集中モード＝全部を1つの加重に混ぜて厳選。",
        )

        _co_auto = detect_carryover(df_real)
        carryover = st.checkbox(
            "💰 今週はキャリーオーバー（高額繰越）— 人気回避を強める" + ("　※前回1等該当なし→自動でONにしました" if _co_auto else ""),
            value=_co_auto,
            help="前回の1等が『該当なし』だと自動でONになります（公式ルール：1等不在の賞金は次回へ繰越）。買われにくい高数字(32-37)を厚めにし、当たった時の『分け前』を最大化する狙い（確率は変わりません）。")

        submitted = st.form_submit_button("🔥 超次元演算：あなたの気持ちを核に予測を積上げる")
        
        if submitted:
            if df_real.empty: st.error("基盤データがありません。")
            else:
                with st.spinner("量子シード生成中... 地球環境、ドッペルゲンガー、物理的ボール衝突法則を完全に同期させています..."):
                    today_str = datetime.now(JST).strftime("%Y-%m-%d")

                    # 0. 「気持ち」を全シグナルの核に据える（プログラムが実行者の気持ちを理解する）
                    feeling_text = (feeling or "").strip()
                    soc_sensor = spirit_sensor = good_deed = feeling_text if feeling_text else "特になし"
                    prayer = feeling_text if feeling_text else "（無心）"
                    biorhythm = sign = feeling_text

                    # 占い × ロト7（任意・控えめ）：今日の占いナンバーを取得
                    fortune_nums = get_today_fortune_numbers() if use_fortune else []

                    weather, pressure = get_current_weather_and_pressure()
                    m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                    m_feng = get_fengshui(draw_date)

                    # 1. AI直感の取得（気持ちを最重要シグナルとして渡す）
                    ai_intuition_nums = get_ai_intuition_numbers(feeling_text, f"{weather} / {pressure}", m_gravity, draw_date)
                    
                    # 2. 完全環境一致（ドッペルゲンガー）の抽出
                    sync_matches, sync_counts = find_doppelganger_days(draw_date, df_real)
                    hot_sync_nums = [n for n, c in sync_counts.most_common(5)]

                    # 2.5 多角的「環境共鳴」分析（重力・潮・月相・干支・九星・六曜を独立軸で集計）
                    axis_counters, env_resonance, target_env = analyze_environment_resonance(draw_date, df_real)
                    resonance_top = [n for n, _ in env_resonance.most_common(7)]

                    # 3. 🚀 動的量子シード生成
                    quantum_seed_nums = generate_dynamic_quantum_seed(str(draw_date), soc_sensor, spirit_sensor, prayer, good_deed)
                    
                    # 4. 直近トレンドの取得
                    recent_df = df_real.head(10)
                    recent_nums = [int(r.get(f"数字{i}")) for _, r in recent_df.iterrows() for i in range(1, LOTO_PICK_COUNT + 1) if pd.notna(r.get(f"数字{i}")) and str(r.get(f"数字{i}")).isdigit()]
                    recent_counts = Counter(recent_nums)

                    # フェーズ3：多角分析レンズ
                    carry_nums, slide_nums = lens_carry_slide(df_real)
                    unpop_nums = lens_unpopular_numbers()
                    ausp_labels, ausp_good = lens_auspicious_day(draw_date)
                    # 成績上位サイトの予想を、精度に応じて反映
                    trusted_site_w = get_trusted_site_numbers(df_real, target_round_str)
                    # みんなが予想している“共通数字”（コンセンサス）。多くのサイトが推す数字。
                    site_consensus_nums = [n for n, _ in site_consensus_from_log(target_round_str, top=10)]

                    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                    st.markdown("### 🔭 全方位レポート（観点＝レンズ別）")
                    st.write(f"🌍 **【自然・引力】** 予定日（{draw_date}）：{m_tide} / {m_phase} / 重力:{m_gravity} / {weather}")
                    st.write(f"🌌 **【量子シード】**: {quantum_seed_nums} （今日の波長から生成）")
                    if ai_intuition_nums: st.write(f"🧠 **【AIの直感】**: {ai_intuition_nums}")
                    if fortune_nums: st.write(f"🔮 **【占いラッキー（控えめ反映）】**: {fortune_nums}")
                    elif use_fortune: st.caption("🔮 占いを加味する設定ですが、今日の占いナンバーが未保存です。占い師の館で『🎯ロト7へ渡す』を押してください。")
                    if env_resonance:
                        st.write(f"🪐 **【暦・環境共鳴（干支・九星・六曜・月）】**: {resonance_top}")
                        axis_brief = " / ".join([f"{ax}:{target_env.get(ax)}" for ax in ENV_AXIS_WEIGHTS])
                        st.caption(f"今回の環境指紋 → {axis_brief}")
                    if sync_matches:
                        st.write(f"🎯 **【完全環境一致日（ドッペルゲンガー）】**: {hot_sync_nums}")
                        for m in sync_matches[:2]: st.caption(f" - {m['回号']} ({m['日付']}) | 一致: {m['一致項目']}")
                    if carry_nums or slide_nums:
                        st.write(f"📜 **【出目理論】** 引っ張り(前回再出): {carry_nums} ／ スライド(±1): {slide_nums}")
                    if carryover:
                        st.write(f"💰 **【分け前重視モード：高額キャリーオーバー】** 買われにくい高数字 {unpop_nums} を強めに優遇（当たった時の取り分を最大化）")
                    else:
                        st.write(f"👥 **【人間の欲】** 買われにくい高数字 {unpop_nums} を僅かに優遇（普段も常駐。当たった時の分け前を増やす狙い）")
                    if ausp_labels:
                        st.write(f"🗓 **【縁起日】** {' ・ '.join(ausp_labels)} ＝ 縁起の良い日。直感を後押し")
                    if trusted_site_w:
                        top_site_nums = sorted(trusted_site_w, key=lambda k: trusted_site_w[k], reverse=True)[:10]
                        st.write(f"🏅 **【成績上位サイトの予想（精度で重み付け反映）】**: {sorted(top_site_nums)}")
                    st.markdown("</div>", unsafe_allow_html=True)

                    # 外部トレンド読み込み（スプレッドシート連動対応）
                    trend_counts = get_external_trend()
                    number_counts = Counter([int(val) for i in range(1, LOTO_PICK_COUNT + 1) for val in df_real.get(f"数字{i}", []) if pd.notna(val) and str(val).isdigit()])
                    nums_list = list(range(1, LOTO_MAX_NUM + 1))
                    
                    # 5. 究極の加重計算（全ロジックの融合）
                    base_weights = []
                    for n in nums_list:
                        # 過去実績 + 他サイトのトレンド
                        base_w = number_counts.get(n, 1) + trend_counts.get(n, 0) * 3
                        
                        # 理論1：完全一致日の数字
                        if n in hot_sync_nums: base_w += 30
                                
                        # 理論2（重力＝「最近出ていない数字はそろそろ来る／出過ぎた数字は下がる」）は
                        # 統計的根拠が無いギャンブラーの誤謬のため撤去した。各回は独立で、過去の出現は次回に影響しない。

                        # 理論3：AI直感への同調
                        if n in ai_intuition_nums: base_w += 50
                            
                        # 理論4：量子シードへの同調
                        if n in quantum_seed_nums: base_w += 40

                        # 理論6：多角・環境共鳴（過去の同一環境で実際に出た数字を、月だけに偏らず加点）
                        base_w += int(env_resonance.get(n, 0) * 0.5)

                        # 理論7：占いのラッキーナンバー（任意・控えめ。他シグナルより弱く＝偏りにくい）
                        if n in fortune_nums: base_w += 15

                        # 理論8：出目理論（引っ張り＝前回再出／スライド＝±1）
                        if n in carry_nums: base_w += 12
                        if n in slide_nums: base_w += 8

                        # 理論9：人間の欲（買われにくい高数字を優遇＝当選時の分け前UP狙い。高額週はさらに強める）
                        if n in unpop_nums: base_w += (22 if carryover else 6)

                        # 理論10：縁起日ブースト（縁起の良い日は直感ナンバーを後押し）
                        if ausp_good and n in ai_intuition_nums: base_w += 8

                        # 理論11：成績上位サイトの予想を、その平均的中（精度）に応じて反映
                        if n in trusted_site_w: base_w += int(trusted_site_w[n] * 5)

                        base_weights.append(max(1, base_w))

                    # 🔥 理論5：物理法則「ボール隣接波及効果」の適用
                    smoothed_weights = base_weights[:]
                    for i in range(LOTO_MAX_NUM):
                        if i > 0: smoothed_weights[i] += base_weights[i-1] * 0.15 
                        if i < LOTO_MAX_NUM - 1: smoothed_weights[i] += base_weights[i+1] * 0.15 
                    weights_list = [max(1, w) for w in smoothed_weights]

                    # 6. ベースナンバーの設定
                    if operator == u1_name:
                        matched_nums = []
                        err_shown = False
                        for _, row in df_real.iterrows():
                            w = 0
                            if str(row.get("重力状態")) == m_gravity: w += 2
                            if str(row.get("潮回り")) == m_tide: w += 1
                            if str(row.get("風水")).startswith(m_feng[:2]): w += 2
                            if w > 0:
                                for i in range(1, LOTO_PICK_COUNT + 1):
                                    try: 
                                        val = row.get(f"数字{i}")
                                        if pd.notna(val) and str(val).isdigit():
                                            matched_nums.extend([int(val)] * w)
                                    except Exception as e: 
                                        if not err_shown:
                                            st.warning(f"統計データからのベース数字抽出中に一部エラーが発生しました: {e}")
                                            err_shown = True
                        stat_tops = [n for n, _ in Counter(matched_nums).most_common(2)]
                        base_must = list(set(stat_tops + quantum_seed_nums[:1] + ai_intuition_nums[:1]))
                        logic_name = "量子シード × 物理連番波及 × 過去統計"
                    else:
                        ob = USER_PROFILES[operator]["birth"]
                        num1, _ = get_ryukyu_energy(operator, ob, draw_date)
                        num2 = (draw_date.day + draw_date.month + ob.day) % LOTO_MAX_NUM + 1
                        if num2 == 0 or num2 == num1: num2 = (num2 + 1) % LOTO_MAX_NUM + 1
                        base_must = list(set([num1, num2] + quantum_seed_nums[:1] + ai_intuition_nums[:1]))
                        logic_name = "直感と夢 × 量子シード × ボール波及"

                    base_must = list(set(base_must))
                    while len(base_must) < 4: base_must.append(random.choice(nums_list))

                    top30, added = [], set()

                    if "探索" in gen_mode:
                        # 🎲 探索モード：30口を別々の可能性（レンズ）に1口ずつ割り当て、各口にレンズ名を記録。
                        # 抽選後に『どのレンズが近かったか』を学ぶための“広く張る”戦略（剪定はしない）。
                        top_freq = [n for n, _ in number_counts.most_common(12)]
                        site_top = sorted(trusted_site_w, key=lambda k: trusted_site_w[k], reverse=True)[:8] if trusted_site_w else []
                        lens_favs = {
                            "過去頻度(土台)": top_freq,
                            "引っ張り": carry_nums,
                            "スライド": slide_nums,
                            "環境共鳴(暦)": resonance_top,
                            "量子シード": quantum_seed_nums,
                            "AI直感": ai_intuition_nums,
                            "ドッペルゲンガー": hot_sync_nums,
                            "人気回避(高数字)": unpop_nums,
                            "占いラッキー": fortune_nums,
                            "他サイト成績上位": site_top,
                            "他サイト総意(コンセンサス)": site_consensus_nums,
                        }
                        alloc = {"過去頻度(土台)": 5, "引っ張り": 3, "スライド": 2, "環境共鳴(暦)": 3, "量子シード": 2,
                                 "AI直感": 2, "ドッペルゲンガー": 2, "人気回避(高数字)": 2, "占いラッキー": 2,
                                 "他サイト成績上位": 2, "他サイト総意(コンセンサス)": 2}
                        if carryover:
                            alloc["人気回避(高数字)"] = 6  # 高額週は分け前重視で人気回避を厚く

                        # ★固定バイアス防止：30口の中で同じ数字が出過ぎないよう上限を設ける（34/12/21等の張り付き解消）
                        stack_usage = Counter()
                        stack_cap = max(5, round(30 * LOTO_PICK_COUNT / LOTO_MAX_NUM) + 2)  # ≒8（30口で1数字あたり最大8口程度）

                        def make_ticket(favs, lens=""):
                            # 上限に達した数字は種から除外
                            favs = [n for n in dict.fromkeys(favs) if 1 <= n <= LOTO_MAX_NUM and stack_usage[n] < stack_cap]
                            # ★個々の口もバランス：1帯域(1-10/11-20/21-30/31-37)は最大3個まで＝低域固まり(△)を防ぐ。
                            #   ただし大穴(人気回避)は高数字寄せが狙いなので帯域制約を外す。
                            band_balance = ("人気回避" not in str(lens))
                            def _band(n): return (n - 1) // 10
                            p = []
                            def _band_ok(n):
                                if not band_balance: return True
                                return sum(1 for x in p if _band(x) == _band(n)) < 3
                            # 種：favsから帯域を散らして3〜5個
                            seed_k = min(len(favs), random.choice([3, 4, 5]))
                            fv = favs[:]; random.shuffle(fv)
                            for n in fv:
                                if len(p) >= seed_k: break
                                if _band_ok(n): p.append(n)
                            tries = 0
                            while len(p) < LOTO_PICK_COUNT and tries < 400:
                                ch = random.choices(nums_list, weights=weights_list, k=1)[0]
                                if ch not in p and stack_usage[ch] < stack_cap and _band_ok(ch): p.append(ch)
                                tries += 1
                            # 帯域・上限で埋まらない分は“まだ使われていない数字”を優先
                            while len(p) < LOTO_PICK_COUNT:
                                cand = ([n for n in nums_list if n not in p and stack_usage[n] < stack_cap and _band_ok(n)]
                                        or [n for n in nums_list if n not in p and stack_usage[n] < stack_cap]
                                        or [n for n in nums_list if n not in p])
                                mn = min(stack_usage[n] for n in cand)
                                p.append(random.choice([n for n in cand if stack_usage[n] == mn]))
                            return sorted(p)

                        for lens, cnt in alloc.items():
                            favs = lens_favs.get(lens, [])
                            for _ in range(cnt):
                                if len(top30) >= 30: break
                                t = make_ticket(favs, lens)
                                for _retry in range(8):
                                    if tuple(t) not in added: break
                                    t = make_ticket(favs, lens)
                                top30.append({"nums": t, "pts": 0, "base_pts": int(sum(weights_list[n - 1] for n in t)), "type": lens})
                                added.add(tuple(t))
                                for n in t: stack_usage[n] += 1
                        # 残りは「ランダム探索（未知）」で30口まで（上限を尊重＝まだ少ない数字を優先）
                        while len(top30) < 30:
                            rp = []
                            while len(rp) < LOTO_PICK_COUNT:
                                cand = [n for n in nums_list if n not in rp and stack_usage[n] < stack_cap] or [n for n in nums_list if n not in rp]
                                mn = min(stack_usage[n] for n in cand)
                                rp.append(random.choice([n for n in cand if stack_usage[n] == mn]))
                            rp = sorted(rp)
                            if tuple(rp) in added: continue
                            top30.append({"nums": rp, "pts": 0, "base_pts": 0, "type": "ランダム探索(未知)"})
                            added.add(tuple(rp))
                            for n in rp: stack_usage[n] += 1
                    else:
                        # 🎯 集中モード：全レンズを合成した加重から超並列シミュレーションで厳選
                        elites = []
                        for _ in range(SIMULATION_LOOP_COUNT):
                            p = random.sample(base_must, random.choice([2, 3]))
                            while len(p) < LOTO_PICK_COUNT:
                                ch = random.choices(nums_list, weights=weights_list, k=1)[0]
                                if ch not in p: p.append(ch)
                            p.sort()
                            if not (80 <= sum(p) <= 180): continue
                            if sum(1 for n in p if n % 2 != 0) not in [2, 3, 4, 5]: continue
                            base_pts = sum(weights_list[n - 1] for n in p)
                            fluctuation_max = 0.2
                            if "絶好調" in biorhythm or "無の境地" in biorhythm: fluctuation_max += 0.1
                            if "転換" in soc_sensor or "幽霊" in spirit_sensor: fluctuation_max += 0.1
                            ai_yuragi = random.uniform(0, base_pts * fluctuation_max)
                            elites.append({"nums": p, "pts": base_pts + ai_yuragi, "base_pts": base_pts})
                        elites.sort(key=lambda x: x["pts"], reverse=True)
                        num_usage = Counter()
                        TARGET_ELITE = 28

                        def add_pick(e, max_overlap, usage_cap):
                            key = tuple(e["nums"])
                            if key in added: return False
                            if any(len(set(e["nums"]) & set(t["nums"])) >= max_overlap for t in top30): return False
                            if usage_cap is not None and any(num_usage[n] >= usage_cap for n in e["nums"]): return False
                            item = dict(e); item["type"] = logic_name
                            top30.append(item); added.add(key)
                            for n in e["nums"]: num_usage[n] += 1
                            return True

                        for max_ov, cap in [(4, 7), (4, 10), (4, None), (5, None), (7, None)]:
                            for e in elites:
                                if len(top30) >= TARGET_ELITE: break
                                add_pick(e, max_ov, cap)
                            if len(top30) >= TARGET_ELITE: break
                        while len(top30) < TARGET_ELITE:
                            rp = sorted(random.sample(nums_list, LOTO_PICK_COUNT))
                            if tuple(rp) in added: continue
                            top30.append({"nums": rp, "pts": 0, "base_pts": 0, "type": logic_name + "(補完)"})
                            added.add(tuple(rp))
                        for _ in range(2):
                            rp = sorted(random.sample(nums_list, LOTO_PICK_COUNT))
                            top30.append({"nums": rp, "pts": 0, "base_pts": 0, "type": "完全ランダム(未知への挑戦)"})
                    
                    new_data = []
                    for i, item in enumerate(top30, 1):
                        row_data = {
                            "対象回号": target_round_str, "抽選日": draw_date.strftime("%Y-%m-%d"), "実行日": today_str, 
                            "実行者": operator, "口数": f"{i}口目",
                            "実績点数": int(item["base_pts"]), "社会情勢": soc_sensor[:15], "霊的要素": spirit_sensor[:15], "AI直感": str(ai_intuition_nums),
                            "徳積み": good_deed[:15], "祈り/夢": prayer, "地球環境": f"{m_phase}/引力{m_gravity}",
                            "予測ロジック": item["type"], "キャリーオーバー": ("YES" if carryover else ""), "AIの助言": "未照合"
                        }
                        for j in range(LOTO_PICK_COUNT):
                            row_data[f"数字{j+1}"] = str(item["nums"][j]).zfill(2)
                        new_data.append(row_data)
                    
                    # 同時書き込み対策：保存直前にキャッシュを消して“最新”を読み直す（妻/自動処理の直近の書き込みを取りこぼさない）
                    try: _load_sheet_cached.clear()
                    except Exception: pass
                    df_note = load_sheet("予測ノート")
                    new_df = pd.DataFrame(new_data)
                    # 最新を上に積む（追記・上書きしない）。完全に同一の行だけ重複排除（最新側を残す）。
                    if not df_note.empty:
                        df_note = pd.concat([new_df, df_note], ignore_index=True).drop_duplicates().reset_index(drop=True)
                    else:
                        df_note = new_df
                    if "実行日" in df_note.columns:
                        df_note = df_note.sort_values("実行日", ascending=False, kind="stable").reset_index(drop=True)  # 常に最新が上
                    save_sheet("予測ノート", df_note)
                    st.success(f"固定バイアスを完全排除し、動的量子シードと物理演算を駆使して、{target_round_str}に向けて最強の{len(top30)}口を積み上げました。（担当: {operator}）")

            st.dataframe(df, use_container_width=True, height=300)