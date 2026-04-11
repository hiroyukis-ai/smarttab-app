import streamlit as st
import fitz  # PyMuPDF
import io

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
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="title-block">
    <h1>📑 施工計画書 スマートタブ生成</h1>
    <p>結合済みPDFをアップロードするだけで、章ごとのナビゲーションタブを自動で追加します</p>
</div>
""", unsafe_allow_html=True)


# =============================================
# テキスト正規化
# =============================================
def normalize(text: str) -> str:
    text = text.replace("　", "").replace(" ", "")
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    text = text.translate(str.maketrans(
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))
    text = text.replace("．", ".").replace("、", ",").replace("。", ".")
    return text.strip()


def extract_top_text(page: fitz.Page, ratio: float = 0.30) -> str:
    rect = page.rect
    top_rect = fitz.Rect(0, 0, rect.width, rect.height * ratio)
    blocks = page.get_text("blocks", clip=top_rect)
    blocks_sorted = sorted(blocks, key=lambda b: b[1])
    return "\n".join(b[4].strip() for b in blocks_sorted)


def detect_chapter_pages(doc: fitz.Document, titles: list) -> list:
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


def build_page_mapping(doc: fitz.Document, chapter_pages: list) -> tuple:
    total_pages = doc.page_count
    chapters_info = []
    for i, chap in enumerate(chapter_pages):
        start = chap["start_page"]
        end = chapter_pages[i + 1]["start_page"] if i + 1 < len(chapter_pages) else total_pages
        chapters_info.append({
            "title": chap["title"],
            "pages": end - start,
            "start_page": start
        })
    page_mapping = []
    for page_num in range(total_pages):
        chapter_idx = 0
        page_in_chapter = page_num + 1
        for i, chap in enumerate(chapters_info):
            if page_num >= chap["start_page"]:
                chapter_idx = i
                page_in_chapter = page_num - chap["start_page"] + 1
        page_mapping.append({"chapter_idx": chapter_idx, "page_in_chapter": page_in_chapter})
    return chapters_info, page_mapping


# =============================================
# タブカラーパレット（くすみポップ・グリーン〜オレンジ系）
# =============================================
TAB_COLORS = [
    (0.40, 0.72, 0.56),  # くすみグリーン
    (0.95, 0.64, 0.38),  # くすみオレンジ
    (0.38, 0.68, 0.78),  # くすみブルー
    (0.82, 0.55, 0.40),  # テラコッタ
    (0.55, 0.78, 0.50),  # ライトグリーン
    (0.95, 0.78, 0.38),  # くすみイエロー
    (0.45, 0.65, 0.70),  # スレートブルー
    (0.88, 0.60, 0.55),  # くすみピンク
]

ACTIVE_PAGE_COLOR = (0.95, 0.45, 0.20)   # オレンジ（現在ページ）
INACTIVE_TEXT    = (0.55, 0.55, 0.55)    # グレー（非アクティブ文字）
BG_COLOR         = (0.97, 0.97, 0.96)    # 背景帯（オフホワイト）


def apply_smart_tabs(doc: fitz.Document, chapters: list, page_mapping: list) -> fitz.Document:
    # アクティブタブ：番号＋タイトル表示のため少し広め
    MARGIN = 62
    chapter_start_pages = [c["start_page"] for c in chapters]
    num_chapters = len(chapters)

    for i in range(doc.page_count):
        page = doc[i]
        rect = page.rect
        current_chapter_idx = page_mapping[i]["chapter_idx"]
        current_page_in_chap = page_mapping[i]["page_in_chapter"]

        # 背景帯
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(0, 0, MARGIN, rect.height))
        shape.finish(color=BG_COLOR, fill=BG_COLOR)
        shape.commit()

        # タブの高さを画面全体に均等配置
        available_height = rect.height - 20
        tab_h = min(36, available_height / max(num_chapters, 1))
        y_offset = 10

        for c_idx, chapter in enumerate(chapters):
            is_active = (c_idx == current_chapter_idx)
            color = TAB_COLORS[c_idx % len(TAB_COLORS)]

            tab_rect = fitz.Rect(4, y_offset, MARGIN - 2, y_offset + tab_h - 2)

            # タブ背景
            tab_shape = page.new_shape()
            tab_shape.draw_rect(tab_rect)
            if is_active:
                # アクティブ：塗りつぶし＋左アクセントライン
                tab_shape.finish(color=color, fill=color)
                tab_shape.commit()
                # 左アクセントライン（濃い色）
                accent = page.new_shape()
                accent_rect = fitz.Rect(4, y_offset, 7, y_offset + tab_h - 2)
                accent.draw_rect(accent_rect)
                dark = tuple(max(0, c - 0.15) for c in color)
                accent.finish(color=dark, fill=dark)
                accent.commit()
            else:
                # 非アクティブ：薄い塗りつぶし
                light = tuple(min(1.0, c + 0.28) for c in color)
                tab_shape.finish(color=light, fill=light)
                tab_shape.commit()

            # 章番号テキスト
            num_str = f"{c_idx + 1:02d}"
            if is_active:
                # アクティブ：番号を上部に小さく、タイトルを下部に
                num_rect = fitz.Rect(8, y_offset + 2, MARGIN - 2, y_offset + tab_h * 0.42)
                page.insert_textbox(num_rect, num_str, fontsize=7,
                                    fontname="helv", color=(1, 1, 1), align=fitz.TEXT_ALIGN_LEFT)
                # タイトル（短縮表示）
                raw_title = chapter["title"]
                # 番号部分を除いたタイトルのみ抽出（例: "1.工事概要" → "工事概要"）
                import re
                short = re.sub(r"^\d+[\.\．]\s*", "", raw_title).replace(" ", "")
                # 長すぎる場合は省略
                if len(short) > 6:
                    short = short[:5] + "…"
                title_rect = fitz.Rect(8, y_offset + tab_h * 0.40, MARGIN - 2, y_offset + tab_h - 2)
                page.insert_textbox(title_rect, short, fontsize=6.5,
                                    fontname="helv", color=(1, 1, 1), align=fitz.TEXT_ALIGN_LEFT)
            else:
                # 非アクティブ：番号のみ中央表示
                page.insert_textbox(tab_rect, num_str, fontsize=8,
                                    fontname="helv", color=INACTIVE_TEXT, align=fitz.TEXT_ALIGN_CENTER)

            page.insert_link({
                "kind": fitz.LINK_GOTO,
                "page": chapter_start_pages[c_idx],
                "from": tab_rect
            })

            y_offset += tab_h

            # アクティブ章のページ一覧（タブの下に続けて表示）
            if is_active:
                for p in range(1, chapter["pages"] + 1):
                    sub_h = 14
                    if y_offset + sub_h > rect.height - 5:
                        break
                    sub_rect = fitz.Rect(10, y_offset, MARGIN - 2, y_offset + sub_h)
                    is_cur = (p == current_page_in_chap)

                    if is_cur:
                        # 現在ページ：オレンジ背景
                        bg_shape = page.new_shape()
                        bg_shape.draw_rect(sub_rect)
                        bg_shape.finish(color=ACTIVE_PAGE_COLOR, fill=ACTIVE_PAGE_COLOR)
                        bg_shape.commit()
                        page.insert_textbox(sub_rect, f" >p.{p}", fontsize=7,
                                            fontname="helv", color=(1, 1, 1),
                                            align=fitz.TEXT_ALIGN_LEFT)
                    else:
                        page.insert_textbox(sub_rect, f"  p.{p}", fontsize=6.5,
                                            fontname="helv", color=(0.45, 0.45, 0.45),
                                            align=fitz.TEXT_ALIGN_LEFT)

                    page.insert_link({
                        "kind": fitz.LINK_GOTO,
                        "page": chapter_start_pages[c_idx] + p - 1,
                        "from": sub_rect
                    })
                    y_offset += sub_h

            y_offset += 3  # タブ間の余白

    return doc


def generate_pdf(pdf_bytes: bytes, chapter_pages: list) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chapters_info, page_mapping = build_page_mapping(doc, chapter_pages)
    final_doc = apply_smart_tabs(doc, chapters_info, page_mapping)
    buf = io.BytesIO()
    final_doc.save(buf)
    final_doc.close()
    buf.seek(0)
    return buf.read()


# =============================================
# セッション状態の初期化
# =============================================
for key, default in [
    ("detection_done", False),
    ("chapter_pages", []),
    ("missing_titles", []),
    ("pdf_bytes", None),
    ("total_pages", 1),
    ("output_pdf", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# =============================================
# UI
# =============================================

st.markdown('<div class="step-label">STEP 1</div>', unsafe_allow_html=True)
st.markdown("#### 結合済みPDFをアップロード")
uploaded_file = st.file_uploader("施工計画書（全章を結合済みのPDF）", type="pdf")

st.divider()

st.markdown('<div class="step-label">STEP 2</div>', unsafe_allow_html=True)
st.markdown("#### 章タイトルの一覧を入力")
st.markdown("""
<div class="info-box">
💡 各章の1ページ目にある<b>タイトル文字</b>を、1行に1つずつ入力してください。<br>
スペース・全角/半角・句読点の違いは自動で吸収します。
</div>
""", unsafe_allow_html=True)

default_titles = """1.工 事 概 要
2.計 画 工 程 表
3.現場組織表
4.指 定 機 械
5.主 要 機 械
6.主 要 資 材
7.施 工 方 法
8.施 工 管 理 計 画
9.安 全 管 理
10.緊急時の体制及び対応
11.交 通 管 理
12.環 境 対 策
13.現場作業環境の整備
14.再生資源の利用の促進と建設副産物の適正処理方法
15.そ の 他"""

titles_input = st.text_area("章タイトル一覧（1行に1章）", value=default_titles, height=280)

st.divider()

st.markdown('<div class="step-label">STEP 3</div>', unsafe_allow_html=True)
st.markdown("#### タブを生成する")

if st.button("📑 スマートタブを生成する", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("PDFファイルをアップロードしてください。")
    else:
        titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        with st.spinner("章タイトルを検出しています..."):
            chapter_pages = detect_chapter_pages(doc, titles)
        doc.close()

        if not chapter_pages:
            st.error("章タイトルが1つも見つかりませんでした。タイトルの文字を確認してください。")
        else:
            detected_idxs = [c["chapter_idx"] for c in chapter_pages]
            missing_titles = [(i, t) for i, t in enumerate(titles) if i not in detected_idxs]
            st.session_state.detection_done = True
            st.session_state.chapter_pages = chapter_pages
            st.session_state.missing_titles = missing_titles
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.total_pages = fitz.open(stream=pdf_bytes, filetype="pdf").page_count
            st.session_state.output_pdf = None

if st.session_state.detection_done:
    chapter_pages = st.session_state.chapter_pages
    missing_titles = st.session_state.missing_titles

    col1, col2 = st.columns(2)
    with col1:
        st.success(f"✅ 検出された章：{len(chapter_pages)} 件")
        for c in chapter_pages:
            st.write(f"　{c['title']} → {c['start_page'] + 1}ページ目〜")
    with col2:
        if missing_titles:
            st.warning(f"⚠️ 自動検出できなかった章：{len(missing_titles)} 件")
            for idx, title in missing_titles:
                st.write(f"　{title}")

    if missing_titles:
        st.markdown("""
<div class="warn-box">
⚠️ 自動検出できなかった章があります。<br>
PDFを開いて確認し、<b>何ページ目から始まるか</b>を入力して「確定」を押してください。
</div>
""", unsafe_allow_html=True)

        with st.form("manual_form"):
            manual_inputs = {}
            for idx, title in missing_titles:
                manual_inputs[idx] = st.number_input(
                    f"「{title}」の開始ページ番号（1〜{st.session_state.total_pages}）",
                    min_value=1, max_value=st.session_state.total_pages,
                    value=1, step=1, key=f"manual_{idx}"
                )
            submitted = st.form_submit_button("✅ 手動入力を確定してタブを生成", use_container_width=True)

        if submitted:
            for idx, title in missing_titles:
                chapter_pages.append({
                    "chapter_idx": idx,
                    "title": title,
                    "start_page": manual_inputs[idx] - 1
                })
            chapter_pages.sort(key=lambda x: x["chapter_idx"])
            with st.spinner("タブを描画しています..."):
                st.session_state.output_pdf = generate_pdf(st.session_state.pdf_bytes, chapter_pages)
    else:
        if st.session_state.output_pdf is None:
            with st.spinner("タブを描画しています..."):
                st.session_state.output_pdf = generate_pdf(st.session_state.pdf_bytes, chapter_pages)

    if st.session_state.output_pdf:
        st.success("✅ 生成完了！下のボタンからダウンロードしてください。")
        st.download_button(
            label="⬇️ タブ付きPDFをダウンロード",
            data=st.session_state.output_pdf,
            file_name="施工計画書_スマートタブ付き.pdf",
            mime="application/pdf",
            use_container_width=True
        )
