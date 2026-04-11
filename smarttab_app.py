import streamlit as st
import fitz  # PyMuPDF
import io
import re
import pandas as pd  # ★追加：表を扱うためのライブラリ

st.set_page_config(
    page_title="施工計画書 スマートタブ生成",
    page_icon="📑",
    layout="centered"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }
    .title-block {
        background: linear-gradient(135deg, #2d6a4f 0%, #52b788 100%);
        color: white; padding: 2rem 2.5rem; border-radius: 12px; margin-bottom: 2rem;
    }
    .title-block h1 { color: white; margin: 0; font-size: 1.8rem; }
    .title-block p  { color: #d8f3dc; margin: 0.5rem 0 0; font-size: 0.95rem; }
    .step-label {
        background: #52b788; color: white; padding: 0.2rem 0.8rem;
        border-radius: 20px; font-size: 0.8rem; font-weight: bold;
        display: inline-block; margin-bottom: 0.5rem;
    }
    .info-box {
        background: #f0faf4; border-left: 4px solid #52b788;
        padding: 1rem 1.2rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.9rem;
    }
    .warn-box {
        background: #fff8f0; border-left: 4px solid #f4a261;
        padding: 1rem 1.2rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.9rem;
    }
    .confirm-box {
        background: #f5f0ff; border-left: 4px solid #7c5cbf;
        padding: 1rem 1.2rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="title-block">
    <h1>📑 施工計画書 スマートタブ生成</h1>
    <p>結合済みPDFをアップロードするだけで、章ごとのナビゲーションタブを自動で追加します</p>
</div>
""", unsafe_allow_html=True)


# =============================================
# ユーティリティ関数
# =============================================

def normalize(text: str) -> str:
    """全角/半角・スペース・句読点を統一して比較用に変換"""
    text = text.replace("　", "").replace(" ", "")
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    text = text.translate(str.maketrans(
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))
    text = text.replace("．", ".").replace("、", ",").replace("。", ".")
    return text.strip()

def extract_title_text(title: str) -> str:
    """「1.工 事 概 要」→「工事概要」 数字・記号・スペースを除去"""
    t = re.sub(r"^[\d]+[\.．]\s*", "", title)
    t = t.replace("　", "").replace(" ", "").strip()
    return t

def extract_top_text(page: fitz.Page, ratio: float = 0.30) -> str:
    rect = page.rect
    top_rect = fitz.Rect(0, 0, rect.width, rect.height * ratio)
    blocks = page.get_text("blocks", clip=top_rect)
    blocks_sorted = sorted(blocks, key=lambda b: b[1])
    return "\n".join(b[4].strip() for b in blocks_sorted)

def detect_chapter_pages(doc: fitz.Document, titles: list) -> list:
    """本文章タイトルの開始ページを自動検出"""
    normalized_titles = [normalize(t) for t in titles]
    chapter_pages = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        normalized_top = normalize(extract_top_text(page))
        for idx, norm_title in enumerate(normalized_titles):
            if norm_title and norm_title in normalized_top:
                if not any(c["chapter_idx"] == idx for c in chapter_pages):
                    chapter_pages.append({
                        "chapter_idx": idx,
                        "title": titles[idx],
                        "start_page": page_num
                    })
                break
    chapter_pages.sort(key=lambda x: x["chapter_idx"])
    return chapter_pages

def extract_chapter_number(title: str) -> str:
    """タイトルから章番号を抽出（例:「7.施工方法」→「7」）"""
    m = re.match(r"^([\d]+)[\.．]", title.strip())
    if m:
        return m.group(1)
    return None

# =============================================
# カラーパレット・描画処理 (変更なし)
# =============================================
PALETTE = [
    {"base": (0.85, 0.85, 0.80), "light": (0.95, 0.95, 0.92), "dark": (0.60, 0.60, 0.55)},
    {"base": (0.75, 0.78, 0.85), "light": (0.90, 0.92, 0.96), "dark": (0.52, 0.55, 0.65)},
    {"base": (0.38, 0.72, 0.55), "light": (0.58, 0.88, 0.72), "dark": (0.22, 0.52, 0.38)},
    {"base": (0.94, 0.63, 0.35), "light": (1.00, 0.80, 0.58), "dark": (0.72, 0.44, 0.20)},
    {"base": (0.36, 0.68, 0.78), "light": (0.55, 0.84, 0.92), "dark": (0.20, 0.50, 0.62)},
    {"base": (0.80, 0.52, 0.40), "light": (0.96, 0.70, 0.58), "dark": (0.60, 0.34, 0.24)},
    {"base": (0.54, 0.78, 0.48), "light": (0.72, 0.94, 0.65), "dark": (0.36, 0.60, 0.32)},
    {"base": (0.94, 0.78, 0.35), "light": (1.00, 0.92, 0.58), "dark": (0.72, 0.58, 0.18)},
    {"base": (0.44, 0.64, 0.70), "light": (0.62, 0.80, 0.88), "dark": (0.28, 0.46, 0.54)},
    {"base": (0.86, 0.58, 0.56), "light": (1.00, 0.76, 0.74), "dark": (0.66, 0.38, 0.36)},
]
ACTIVE_PAGE_COLOR = (0.94, 0.42, 0.18)
BG_COLOR = (0.96, 0.96, 0.95)

def get_palette(tab_index: int) -> dict:
    return PALETTE[tab_index % len(PALETTE)]

def draw_3d_tab(page: fitz.Page, rect: fitz.Rect, palette: dict, is_active: bool):
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    base  = palette["base"]
    light = palette["light"]
    dark  = palette["dark"]
    h = y1 - y0

    if is_active:
        top_rect = fitz.Rect(x0, y0, x1, y0 + h * 0.35)
        s = page.new_shape(); s.draw_rect(top_rect); s.finish(color=light, fill=light); s.commit()
        bot_rect = fitz.Rect(x0, y0 + h * 0.35, x1, y1)
        s = page.new_shape(); s.draw_rect(bot_rect); s.finish(color=base, fill=base); s.commit()
        accent = fitz.Rect(x0, y0, x0 + 4, y1)
        s = page.new_shape(); s.draw_rect(accent); s.finish(color=dark, fill=dark); s.commit()
        shadow = fitz.Rect(x0, y1 - 2, x1, y1)
        s = page.new_shape(); s.draw_rect(shadow); s.finish(color=dark, fill=dark); s.commit()
    else:
        faded_base  = tuple(min(1.0, c + 0.30) for c in base)
        faded_light = tuple(min(1.0, c + 0.15) for c in light)
        faded_dark  = tuple(min(1.0, c + 0.20) for c in dark)
        top_rect = fitz.Rect(x0, y0, x1, y0 + h * 0.30)
        s = page.new_shape(); s.draw_rect(top_rect); s.finish(color=faded_light, fill=faded_light); s.commit()
        bot_rect = fitz.Rect(x0, y0 + h * 0.30, x1, y1)
        s = page.new_shape(); s.draw_rect(bot_rect); s.finish(color=faded_base, fill=faded_base); s.commit()
        shadow = fitz.Rect(x0, y1 - 1, x1, y1)
        s = page.new_shape(); s.draw_rect(shadow); s.finish(color=faded_dark, fill=faded_dark); s.commit()

def apply_smart_tabs(doc: fitz.Document, all_tabs: list, page_mapping: list) -> fitz.Document:
    MARGIN = 64
    num_tabs = len(all_tabs)
    tab_start_pages = [t["start_page"] for t in all_tabs]

    for i in range(doc.page_count):
        page = doc[i]
        rect = page.rect
        current_tab_idx = page_mapping[i]["tab_idx"]
        current_page_in_tab = page_mapping[i]["page_in_tab"]

        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(0, 0, MARGIN, rect.height))
        shape.finish(color=BG_COLOR, fill=BG_COLOR)
        shape.commit()

        available_height = rect.height - 20
        tab_h = min(38, available_height / max(num_tabs, 1))
        y_offset = 10

        for t_idx, tab in enumerate(all_tabs):
            is_active = (t_idx == current_tab_idx)
            palette = get_palette(t_idx)

            tab_rect = fitz.Rect(3, y_offset, MARGIN - 1, y_offset + tab_h - 2)
            draw_3d_tab(page, tab_rect, palette, is_active)

            label = tab["label"]
            lines = label.split("\n")

            if is_active:
                if len(lines) == 2:
                    num_rect = fitz.Rect(8, y_offset + 2, MARGIN - 2, y_offset + tab_h * 0.44)
                    page.insert_textbox(num_rect, lines[0], fontsize=7, fontname="japan", color=(1,1,1), align=fitz.TEXT_ALIGN_LEFT)
                    t_text = lines[1]
                    if len(t_text) > 6: t_text = t_text[:5] + "…"
                    title_rect = fitz.Rect(8, y_offset + tab_h * 0.42, MARGIN - 2, y_offset + tab_h - 3)
                    page.insert_textbox(title_rect, t_text, fontsize=6.5, fontname="japan", color=(1,1,1), align=fitz.TEXT_ALIGN_LEFT)
                else:
                    page.insert_textbox(tab_rect, label, fontsize=8, fontname="japan", color=(1,1,1), align=fitz.TEXT_ALIGN_CENTER)
            else:
                page.insert_textbox(tab_rect, lines[0], fontsize=8, fontname="japan", color=(0.30, 0.30, 0.30), align=fitz.TEXT_ALIGN_CENTER)

            page.insert_link({"kind": fitz.LINK_GOTO, "page": tab_start_pages[t_idx], "from": tab_rect})
            y_offset += tab_h

            if is_active:
                tab_pages = tab.get("pages", 1)
                for p in range(1, tab_pages + 1):
                    sub_h = 14
                    if y_offset + sub_h > rect.height - 5: break
                    sub_rect = fitz.Rect(8, y_offset, MARGIN - 2, y_offset + sub_h)
                    is_cur = (p == current_page_in_tab)
                    if is_cur:
                        bg = page.new_shape()
                        bg.draw_rect(fitz.Rect(5, y_offset, MARGIN - 1, y_offset + sub_h))
                        bg.finish(color=ACTIVE_PAGE_COLOR, fill=ACTIVE_PAGE_COLOR)
                        bg.commit()
                        page.insert_textbox(sub_rect, f" >p.{p}", fontsize=7, fontname="japan", color=(1,1,1), align=fitz.TEXT_ALIGN_LEFT)
                    else:
                        page.insert_textbox(sub_rect, f"  p.{p}", fontsize=6.5, fontname="japan", color=(0.45,0.45,0.45), align=fitz.TEXT_ALIGN_LEFT)
                    page.insert_link({"kind": fitz.LINK_GOTO, "page": tab_start_pages[t_idx] + p - 1, "from": sub_rect})
                    y_offset += sub_h
            y_offset += 3

    return doc

def build_all_tabs_and_mapping(doc: fitz.Document, confirmed_tabs: list) -> tuple:
    total_pages = doc.page_count
    all_tabs = []
    for i, tab in enumerate(confirmed_tabs):
        start = tab["start_page"]
        end = confirmed_tabs[i+1]["start_page"] if i+1 < len(confirmed_tabs) else total_pages
        all_tabs.append({
            "label": tab["label"],
            "start_page": start,
            "pages": end - start
        })

    page_mapping = []
    for page_num in range(total_pages):
        tab_idx = 0
        page_in_tab = page_num + 1
        for i, tab in enumerate(all_tabs):
            if page_num >= tab["start_page"]:
                tab_idx = i
                page_in_tab = page_num - tab["start_page"] + 1
        page_mapping.append({"tab_idx": tab_idx, "page_in_tab": page_in_tab})

    return all_tabs, page_mapping

def generate_pdf(pdf_bytes: bytes, confirmed_tabs: list) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_tabs, page_mapping = build_all_tabs_and_mapping(doc, confirmed_tabs)
    final_doc = apply_smart_tabs(doc, all_tabs, page_mapping)
    buf = io.BytesIO()
    final_doc.save(buf)
    final_doc.close()
    buf.seek(0)
    return buf.read()

# =============================================
# セッション状態の初期化
# =============================================
for key, default in [
    ("phase", "input"),
    ("pdf_bytes", None),
    ("total_pages", 1),
    ("tabs_df", None),
    ("missing_count", 0),
    ("confirmed_tabs", []),
    ("output_pdf", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================
# UI フェーズ管理
# =============================================

st.markdown('<div class="step-label">STEP 1</div>', unsafe_allow_html=True)
st.markdown("#### 結合済みPDFをアップロード")
uploaded_file = st.file_uploader("施工計画書（全章を結合済みのPDF）", type="pdf")
st.divider()

st.markdown('<div class="step-label">STEP 2</div>', unsafe_allow_html=True)
st.markdown("#### 章タイトルの一覧を入力")
st.markdown("""
<div class="info-box">
💡 各章の1ページ目にある<b>タイトル文字</b>を、1行に1つずつ入力してください。
</div>
""", unsafe_allow_html=True)

# ★ここが変更された初期設定です
default_titles = """1.工事概要
2.計画工程表
3.現場組織表
4.指定機械
5.主要機械
6.主要資材
7.施工方法
8.施工管理計画
9.安全管理
10.緊急時の体制及び対応
11.交通管理
12.環境対策
13.現場作業環境の整備
14.再生資源の利用の促進と建設副産物の適正処理方法
15.その他"""

# ★行数が増えたため、height（高さ）を180から350に増やしました
titles_input = st.text_area("章タイトル一覧（1行に1章）", value=default_titles, height=350)
st.divider()

st.markdown('<div class="step-label">STEP 3</div>', unsafe_allow_html=True)
st.markdown("#### タブ構成の確認と生成")

# -----------------------------------------------
# フェーズ1：自動検出ボタン
# -----------------------------------------------
if st.session_state.phase == "input":
    if st.button("🔍 タブ構成を自動検出する", type="primary", use_container_width=True):
        if not uploaded_file:
            st.error("PDFファイルをアップロードしてください。")
        else:
            titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]
            pdf_bytes = uploaded_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = doc.page_count

            with st.spinner("章タイトルを検出しています..."):
                chapter_pages = detect_chapter_pages(doc, titles)
            doc.close()

            # DataFrame用のデータ作成（1ページ目：表紙、2ページ目：目次 を固定で追加）
            df_tabs = []
            df_tabs.append({"タブ名": "表紙", "開始ページ": 1})
            df_tabs.append({"タブ名": "目次", "開始ページ": 2})

            for c in chapter_pages:
                raw_title = c["title"]
                num = extract_chapter_number(raw_title)
                title_text = extract_title_text(raw_title)
                label = f"{num}\n{title_text}" if num else title_text
                df_tabs.append({
                    "タブ名": label,
                    "開始ページ": c["start_page"] + 1
                })

            # 見つからなかった章（仮で最終ページに割り当て）
            detected_idxs = [c["chapter_idx"] for c in chapter_pages]
            missing = [t for i, t in enumerate(titles) if i not in detected_idxs]
            for m_title in missing:
                num = extract_chapter_number(m_title)
                title_text = extract_title_text(m_title)
                label = f"{num}\n{title_text}" if num else title_text
                df_tabs.append({
                    "タブ名": label,
                    "開始ページ": total_pages
                })

            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.total_pages = total_pages
            st.session_state.tabs_df = pd.DataFrame(df_tabs)
            st.session_state.missing_count = len(missing)
            st.session_state.phase = "confirm"
            st.rerun()

# -----------------------------------------------
# フェーズ2：データエディタでの確認・修正・生成
# -----------------------------------------------
if st.session_state.phase == "confirm":
    st.markdown("""
    <div class="confirm-box">
    📋 <b>以下の構成でタブを作成します。</b><br>
    表のセルをクリックして修正、行の左端を選んで削除（Deleteキー）、下部の＋から追加が可能です。
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.missing_count > 0:
        st.markdown(f"""
        <div class="warn-box">
        ⚠️ {st.session_state.missing_count}件の章が自動検出できませんでした。<br>
        表の末尾に仮のページ番号で追加していますので、正しいページ番号に修正してください。
        </div>
        """, unsafe_allow_html=True)

    # ★データエディタ（ここで自由に追加・削除・編集できる）
    edited_df = st.data_editor(
        st.session_state.tabs_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "タブ名": st.column_config.TextColumn("タブ名 (改行OK)", required=True),
            "開始ページ": st.column_config.NumberColumn(
                "開始ページ", 
                min_value=1, 
                max_value=st.session_state.total_pages, 
                required=True,
                help="PDFの何ページ目から始まるかを入力してください。"
            )
        }
    )

    if st.button("📑 この構成でタブを生成する", type="primary", use_container_width=True):
        # バリデーション：重複チェック
        pages = edited_df["開始ページ"].tolist()
        if len(pages) != len(set(pages)):
            st.error("❌ エラー: 「開始ページ」に重複があります。同じページから複数のタブを開始することはできません。（表紙と目次なども被らないようにしてください）")
            st.stop()
            
        # 確定処理
        confirmed_tabs = []
        edited_df_sorted = edited_df.sort_values(by="開始ページ")
        for _, row in edited_df_sorted.iterrows():
            confirmed_tabs.append({
                "label": str(row["タブ名"]),
                "start_page": int(row["開始ページ"]) - 1  # 内部処理は0始まり
            })
            
        st.session_state.confirmed_tabs = confirmed_tabs
        
        with st.spinner("タブを描画しています..."):
            st.session_state.output_pdf = generate_pdf(
                st.session_state.pdf_bytes,
                st.session_state.confirmed_tabs
            )
        st.session_state.phase = "done"
        st.rerun()

# -----------------------------------------------
# フェーズ3：ダウンロード
# -----------------------------------------------
if st.session_state.phase == "done" and st.session_state.output_pdf:
    st.success("✅ 生成完了！下のボタンからダウンロードしてください。")
    st.download_button(
        label="⬇️ タブ付きPDFをダウンロード",
        data=st.session_state.output_pdf,
        file_name="施工計画書_スマートタブ付き.pdf",
        mime="application/pdf",
        use_container_width=True
    )
    if st.button("🔄 最初からやり直す", use_container_width=True):
        for key in ["phase", "pdf_bytes", "total_pages", "tabs_df", "confirmed_tabs", "output_pdf"]:
            st.session_state[key] = None if "pdf" in key or "bytes" in key or key == "tabs_df" else (
                [] if "tabs" in key else ("input" if key == "phase" else 1)
            )
        st.session_state.missing_count = 0
        st.rerun()
