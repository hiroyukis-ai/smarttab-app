import streamlit as st
import fitz  # PyMuPDF
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
    .warn-box {
        background: #fffbea;
        border-left: 4px solid #f59e0b;
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
# テキスト正規化（スペース・全半角・句読点を統一）
# =============================================
def normalize(text: str) -> str:
    text = text.replace("　", "").replace(" ", "")
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    text = text.translate(str.maketrans(
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))
    # 全角句読点→半角（．→. を追加）
    text = text.replace("．", ".").replace("、", ",").replace("。", ".")
    return text.strip()


# =============================================
# ページ上部のテキストを抽出（上部30%の範囲）
# =============================================
def extract_top_text(page: fitz.Page, ratio: float = 0.30) -> str:
    rect = page.rect
    top_rect = fitz.Rect(0, 0, rect.width, rect.height * ratio)
    blocks = page.get_text("blocks", clip=top_rect)
    blocks_sorted = sorted(blocks, key=lambda b: b[1])
    lines = []
    for b in blocks_sorted:
        lines.append(b[4].strip())
    return "\n".join(lines)


# =============================================
# 章の開始ページを検出
# =============================================
def detect_chapter_pages(doc: fitz.Document, titles: list) -> list:
    normalized_titles = [normalize(t) for t in titles]
    chapter_pages = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        top_text = extract_top_text(page)
        normalized_top = normalize(top_text)

        for idx, norm_title in enumerate(normalized_titles):
            if norm_title and norm_title in normalized_top:
                already = any(c["chapter_idx"] == idx for c in chapter_pages)
                if not already:
                    chapter_pages.append({
                        "chapter_idx": idx,
                        "title": titles[idx],
                        "start_page": page_num
                    })
                break

    chapter_pages.sort(key=lambda x: x["chapter_idx"])
    return chapter_pages


# =============================================
# ページマッピングを生成
# =============================================
def build_page_mapping(doc: fitz.Document, chapter_pages: list) -> tuple:
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
# タブ描画・ダウンロード（共通処理）
# =============================================
def generate_and_download(doc: fitz.Document, chapter_pages: list):
    chapters_info, page_mapping = build_page_mapping(doc, chapter_pages)
    st.info("🖊️ タブを描画しています...")
    final_doc = apply_smart_tabs(doc, chapters_info, page_mapping)

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


# =============================================
# スマートタブの描画
# タブ幅を55に縮小・現在ページ記号を>に変更
# =============================================
def apply_smart_tabs(doc: fitz.Document, chapters: list, page_mapping: list) -> fitz.Document:
    margin_left = 55  # タブ幅を狭く

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

        y_offset = 20
        tab_height = 30

        for c_idx, chapter in enumerate(chapters):
            chapter_num = f"{c_idx + 1:02d}"
            is_current_chapter = (c_idx == current_chapter_idx)

            tab_rect = fitz.Rect(3, y_offset, margin_left - 3, y_offset + tab_height)
            tab_shape = page.new_shape()
            tab_shape.draw_rect(tab_rect)

            if is_current_chapter:
                tab_shape.finish(color=(0.1, 0.4, 0.8), fill=(0.1, 0.4, 0.8))
                text_color = (1, 1, 1)
                font_size = 13
            else:
                tab_shape.finish(color=(0.85, 0.88, 0.95), fill=(0.85, 0.88, 0.95))
                text_color = (0.4, 0.4, 0.5)
                font_size = 11

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

            if is_current_chapter:
                for p in range(1, chapter["pages"] + 1):
                    sub_tab_rect = fitz.Rect(3, y_offset, margin_left - 3, y_offset + 18)
                    is_current_page = (p == current_page_in_chap)

                    if is_current_page:
                        sub_color = (0.85, 0.3, 0.05)
                        sub_font_size = 9
                        label = f">p.{p}"  # > 記号で現在ページを表示
                    else:
                        sub_color = (0.4, 0.4, 0.4)
                        sub_font_size = 8
                        label = f" p.{p}"

                    page.insert_textbox(
                        sub_tab_rect, label,
                        fontsize=sub_font_size, fontname="helv",
                        color=sub_color, align=fitz.TEXT_ALIGN_LEFT
                    )
                    page.insert_link({
                        "kind": fitz.LINK_GOTO,
                        "page": chapter_start_pages[c_idx] + p - 1,
                        "from": sub_tab_rect
                    })
                    y_offset += 18

            y_offset += 6

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

titles_input = st.text_area(
    "章タイトル一覧（1行に1章）",
    value=default_titles,
    height=280,
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
            try:
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                total_pages = doc.page_count

                st.info("📖 章タイトルを検出しています...")
                chapter_pages = detect_chapter_pages(doc, titles)

                if not chapter_pages:
                    st.error("章タイトルが1つも見つかりませんでした。タイトルの文字を確認してください。")
                    st.stop()

                detected_idxs = [c["chapter_idx"] for c in chapter_pages]
                missing_titles = [(i, t) for i, t in enumerate(titles) if i not in detected_idxs]

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
                    # 手動ページ指定フォームを表示
                    st.markdown("""
<div class="warn-box">
⚠️ 自動検出できなかった章があります。<br>
PDFを開いて確認し、<b>何ページ目から始まるか</b>を入力してください。
</div>
""", unsafe_allow_html=True)

                    manual_inputs = {}
                    for idx, title in missing_titles:
                        manual_inputs[idx] = st.number_input(
                            f"「{title}」の開始ページ番号（1〜{total_pages}）",
                            min_value=1,
                            max_value=total_pages,
                            value=1,
                            step=1,
                            key=f"manual_{idx}"
                        )

                    if st.button("✅ 手動入力を確定してタブを生成", type="primary", use_container_width=True):
                        for idx, title in missing_titles:
                            chapter_pages.append({
                                "chapter_idx": idx,
                                "title": title,
                                "start_page": manual_inputs[idx] - 1
                            })
                        chapter_pages.sort(key=lambda x: x["chapter_idx"])
                        generate_and_download(doc, chapter_pages)
                else:
                    generate_and_download(doc, chapter_pages)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.exception(e)
