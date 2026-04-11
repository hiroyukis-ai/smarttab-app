import streamlit as st
import fitz  # PyMuPDF
import re
import io

# =============================================
# ページ設定
# =============================================
st.set_page_config(
    page_title="施工計画書 スマートタブ生成",
    page_icon="📑",
    layout="centered"
)

# =============================================
# スタイル
# =============================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }
    .title-block {
        background: linear-gradient(135deg, #1a3a5c 0%, #2563a8 100%);
        color: white;
        padding: 2rem 2.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
    }
    .title-block h1 { color: white; margin: 0; font-size: 1.8rem; }
    .title-block p  { color: #cce0ff; margin: 0.5rem 0 0; font-size: 0.95rem; }
    .step-label {
        background: #2563a8;
        color: white;
        padding: 0.2rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    .info-box {
        background: #f0f6ff;
        border-left: 4px solid #2563a8;
        padding: 1rem 1.2rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
        font-size: 0.9rem;
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
# テキスト正規化（スペース除去・全半角統一）
# =============================================
def normalize(text: str) -> str:
    """スペース・全角数字・全角英数を除去して比較用に正規化する"""
    text = text.replace("　", "").replace(" ", "")
    # 全角数字→半角
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 全角英字→半角
    text = text.translate(str.maketrans(
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))
    return text.strip()


# =============================================
# ページ上部のテキストを抽出（上部30%の範囲）
# =============================================
def extract_top_text(page: fitz.Page, ratio: float = 0.30) -> str:
    rect = page.rect
    top_rect = fitz.Rect(0, 0, rect.width, rect.height * ratio)
    blocks = page.get_text("blocks", clip=top_rect)
    # y座標でソートして上から順に結合
    blocks_sorted = sorted(blocks, key=lambda b: b[1])
    lines = []
    for b in blocks_sorted:
        lines.append(b[4].strip())
    return "\n".join(lines)


# =============================================
# 章の開始ページを検出
# =============================================
def detect_chapter_pages(doc: fitz.Document, titles: list[str]) -> list[dict]:
    """
    各章タイトルがどのページから始まるかを検出する。
    スペース・全角差異を吸収して照合する。
    """
    normalized_titles = [normalize(t) for t in titles]
    chapter_pages = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        top_text = extract_top_text(page)
        normalized_top = normalize(top_text)

        for idx, norm_title in enumerate(normalized_titles):
            if norm_title and norm_title in normalized_top:
                # まだ登録されていない章のみ（最初に見つかったページを採用）
                already = any(c["chapter_idx"] == idx for c in chapter_pages)
                if not already:
                    chapter_pages.append({
                        "chapter_idx": idx,
                        "title": titles[idx],
                        "start_page": page_num
                    })
                break

    # 章順にソート
    chapter_pages.sort(key=lambda x: x["chapter_idx"])
    return chapter_pages


# =============================================
# ページマッピングを生成
# =============================================
def build_page_mapping(doc: fitz.Document, chapter_pages: list[dict]) -> tuple[list, list]:
    """
    各ページがどの章の何ページ目かを計算する。
    返り値: (chapters_info, page_mapping)
    """
    total_pages = doc.page_count
    chapters_info = []
    page_mapping = []

    for i, chap in enumerate(chapter_pages):
        start = chap["start_page"]
        end = chapter_pages[i + 1]["start_page"] if i + 1 < len(chapter_pages) else total_pages
        page_count = end - start
        chapters_info.append({
            "title": chap["title"],
            "pages": page_count,
            "start_page": start
        })

    for page_num in range(total_pages):
        # どの章に属するか判定
        chapter_idx = 0
        page_in_chapter = page_num + 1
        for i, chap in enumerate(chapters_info):
            if page_num >= chap["start_page"]:
                chapter_idx = i
                page_in_chapter = page_num - chap["start_page"] + 1

        page_mapping.append({
            "chapter_idx": chapter_idx,
            "page_in_chapter": page_in_chapter
        })

    return chapters_info, page_mapping


# =============================================
# スマートタブの描画（既存ロジックを維持）
# =============================================
def apply_smart_tabs(doc: fitz.Document, chapters: list, page_mapping: list) -> fitz.Document:
    margin_left = 80

    chapter_start_pages = [c["start_page"] for c in chapters]

    for i in range(doc.page_count):
        page = doc[i]
        rect = page.rect
        current_chapter_idx = page_mapping[i]["chapter_idx"]
        current_page_in_chap = page_mapping[i]["page_in_chapter"]

        # 左側の背景帯
        shape = page.new_shape()
        bg_rect = fitz.Rect(0, 0, margin_left, rect.height)
        shape.draw_rect(bg_rect)
        shape.finish(color=(0.96, 0.96, 0.98), fill=(0.96, 0.96, 0.98))
        shape.commit()

        y_offset = 30
        tab_height = 40

        for c_idx, chapter in enumerate(chapters):
            # 章番号（表示用）
            chapter_num = f"{c_idx + 1:02d}"
            is_current_chapter = (c_idx == current_chapter_idx)

            tab_rect = fitz.Rect(5, y_offset, margin_left - 5, y_offset + tab_height)
            tab_shape = page.new_shape()
            tab_shape.draw_rect(tab_rect)

            if is_current_chapter:
                tab_shape.finish(color=(0.1, 0.4, 0.8), fill=(0.1, 0.4, 0.8))
                text_color = (1, 1, 1)
                font_size = 18
            else:
                tab_shape.finish(color=(0.85, 0.88, 0.95), fill=(0.85, 0.88, 0.95))
                text_color = (0.4, 0.4, 0.5)
                font_size = 14

            tab_shape.commit()
            page.insert_textbox(
                tab_rect, chapter_num,
                fontsize=font_size, fontname="helv",
                color=text_color, align=fitz.TEXT_ALIGN_CENTER
            )
            page.insert_link({
                "kind": fitz.LINK_GOTO,
                "page": chapter_start_pages[c_idx],
                "from": tab_rect
            })

            y_offset += tab_height

            # 現在の章はページ一覧も表示
            if is_current_chapter:
                for p in range(1, chapter["pages"] + 1):
                    sub_tab_rect = fitz.Rect(20, y_offset, margin_left - 5, y_offset + 25)
                    is_current_page = (p == current_page_in_chap)

                    if is_current_page:
                        sub_color = (0.9, 0.4, 0.1)
                        sub_font_size = 12
                        prefix = "▶"
                    else:
                        sub_color = (0.4, 0.4, 0.4)
                        sub_font_size = 10
                        prefix = " "

                    page.insert_textbox(
                        sub_tab_rect, f"{prefix}p.{p}",
                        fontsize=sub_font_size, fontname="helv",
                        color=sub_color, align=fitz.TEXT_ALIGN_LEFT
                    )
                    page.insert_link({
                        "kind": fitz.LINK_GOTO,
                        "page": chapter_start_pages[c_idx] + p - 1,
                        "from": sub_tab_rect
                    })
                    y_offset += 25

            y_offset += 10

    return doc


# =============================================
# UI
# =============================================

# STEP 1: PDFアップロード
st.markdown('<div class="step-label">STEP 1</div>', unsafe_allow_html=True)
st.markdown("#### 結合済みPDFをアップロード")
uploaded_file = st.file_uploader("施工計画書（全章を結合済みのPDF）", type="pdf")

st.divider()

# STEP 2: 章タイトルの入力
st.markdown('<div class="step-label">STEP 2</div>', unsafe_allow_html=True)
st.markdown("#### 章タイトルの一覧を入力")
st.markdown("""
<div class="info-box">
💡 各章の1ページ目にある<b>タイトル文字</b>を、1行に1つずつ入力してください。<br>
スペースは自動で無視されるので <code>１．工 事 概 要</code> でも <code>１．工事概要</code> でも同じに扱われます。
</div>
""", unsafe_allow_html=True)

default_titles = """１．工 事 概 要
２．工 程 計 画
３．施 工 体 制
４．安 全 管 理
５．品 質 管 理"""

titles_input = st.text_area(
    "章タイトル一覧（1行に1章）",
    value=default_titles,
    height=180,
    placeholder="１．工 事 概 要\n２．工 程 計 画\n..."
)

st.divider()

# STEP 3: 生成ボタン
st.markdown('<div class="step-label">STEP 3</div>', unsafe_allow_html=True)
st.markdown("#### タブを生成する")

if st.button("📑 スマートタブを生成する", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("PDFファイルをアップロードしてください。")
    else:
        titles = [t.strip() for t in titles_input.strip().splitlines() if t.strip()]
        if not titles:
            st.error("章タイトルを1つ以上入力してください。")
        else:
            with st.spinner("処理中です..."):
                try:
                    pdf_bytes = uploaded_file.read()
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

                    # 章の開始ページを検出
                    st.info("📖 章タイトルを検出しています...")
                    chapter_pages = detect_chapter_pages(doc, titles)

                    if not chapter_pages:
                        st.error("章タイトルが1つも見つかりませんでした。タイトルの文字が正確に入力されているか確認してください。")
                        st.stop()

                    # 検出結果を表示
                    detected_titles = [c["title"] for c in chapter_pages]
                    missing = [t for t in titles if t not in detected_titles]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.success(f"✅ 検出された章：{len(chapter_pages)} 件")
                        for c in chapter_pages:
                            st.write(f"　{c['title']} → {c['start_page'] + 1}ページ目〜")
                    with col2:
                        if missing:
                            st.warning(f"⚠️ 見つからなかった章：{len(missing)} 件")
                            for m in missing:
                                st.write(f"　{m}")

                    # ページマッピング生成
                    chapters_info, page_mapping = build_page_mapping(doc, chapter_pages)

                    # タブ描画
                    st.info("🖊️ タブを描画しています...")
                    final_doc = apply_smart_tabs(doc, chapters_info, page_mapping)

                    # バイト列として出力
                    output_buffer = io.BytesIO()
                    final_doc.save(output_buffer)
                    final_doc.close()
                    output_buffer.seek(0)

                    st.success("✅ 生成完了！下のボタンからダウンロードしてください。")
                    st.download_button(
                        label="⬇️ タブ付きPDFをダウンロード",
                        data=output_buffer,
                        file_name="施工計画書_スマートタブ付き.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    st.exception(e)
