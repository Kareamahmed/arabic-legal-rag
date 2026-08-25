"""Egyptian Civil Code PDF → JSON corpus (bilingual, hierarchy-aware)."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pdfplumber

PDF_PATH = Path.cwd() / "file" / "egyptian_civil_code.pdf"
OUTPUT_PATH = Path.cwd() / "data" / "corpus.json"
if not PDF_PATH.exists():
    PDF_PATH = Path("/home/workdir/artifacts/file/egyptian_civil_code.pdf")

AR_RE = re.compile(r"[\u0600-\u06FF]")
EN_RE = re.compile(r"[A-Za-z]")
NUM_RE = re.compile(r"^[0-9٠-٩]+$")
NUM_PUNCT_RE = re.compile(r"^[0-9٠-٩\-–—./()]+$")
ZW_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e]")

ARTICLE_RE = re.compile(r"^Article\s+(\d+)$", re.I)
# SECTION/CHAPTER/BOOK with optional same-line title
STRUCT_RE = re.compile(
    r"^(SECTION|CHAPTER|BOOK)\s+([IVXLC0-9]+)\b\s*(.*)$"
    r"|^((?:FIRST|SECOND|THIRD|FOURTH)\s+PART)\b\s*(.*)$",
    re.I,
)
TOPIC_RE = re.compile(r"^(\d+)\s*[.\-–—]\s*(.+)$")
KIND_MAP = {"SECTION": "section", "CHAPTER": "chapter", "BOOK": "book"}


def has_ar(s: str) -> bool:
    return bool(AR_RE.search(s))


def has_en(s: str) -> bool:
    return bool(EN_RE.search(s))


def reconstruct_word(word: dict) -> str:
    text, chars = word["text"], word.get("chars") or []
    if not chars or NUM_RE.fullmatch(text):
        return text
    reverse = has_ar(text)
    chars = sorted(chars, key=lambda c: c["x0"], reverse=reverse)
    return "".join(c["text"] for c in chars)


def norm_ar(text: str) -> str:
    text = ZW_RE.sub("", unicodedata.normalize("NFKC", text)).replace("\u0640", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\)\s*([0-9٠-٩]+)\s*\(", r"(\1)", text)
    text = re.sub(r"\s+([،؛,.!?])", r"\1", text)
    text = re.sub(r"([،؛,.!?])(?=\S)", r"\1 ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_en(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def group_lines(words: list[dict], y_tol: float = 3.0) -> list[list[dict]]:
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines, cur, cur_top = [], [], None
    for w in words:
        if cur and abs(w["top"] - cur_top) > y_tol:
            lines.append(cur)
            cur = []
        cur.append(w)
        cur_top = w["top"] if len(cur) == 1 else cur_top
    if cur:
        lines.append(cur)
    return lines


def split_line(words: list[dict], page_width: float) -> tuple[str, str]:
    ar, en, nums = [], [], []
    for w in words:
        t = w["text"]
        if has_ar(t):
            ar.append(w)
        elif has_en(t):
            en.append(w)
        elif NUM_PUNCT_RE.fullmatch(t):
            nums.append(w)
    mid = page_width / 2
    for w in nums:
        (ar if (w["x0"] + w["x1"]) / 2 > mid else en).append(w)
    ar.sort(key=lambda w: w["x0"], reverse=True)
    en.sort(key=lambda w: w["x0"])
    return (
        norm_ar(" ".join(reconstruct_word(w) for w in ar)),
        norm_en(" ".join(reconstruct_word(w) for w in en)),
    )


def extract_lines(pdf_path: Path) -> list[dict]:
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
                return_chars=True,
            )
            for row in group_lines(words):
                text_ar, text_en = split_line(row, page.width)
                if text_ar or text_en:
                    out.append(
                        {
                            "page": page_no,
                            "top": min(w["top"] for w in row),
                            "text_ar": text_ar,
                            "text_en": text_en,
                        }
                    )
    return out


def parse_struct(en: str) -> tuple[str, str] | None:
    m = STRUCT_RE.match(en.strip())
    if not m:
        return None
    if m.group(1):  # SECTION|CHAPTER|BOOK
        kind = KIND_MAP[m.group(1).upper()]
        return kind, (m.group(3) or "").strip()
    return "book", (m.group(5) or "").strip()  # FIRST PART …


def article_num(en: str) -> int | None:
    m = ARTICLE_RE.match(en.strip())
    return int(m.group(1)) if m else None


def is_title_cont(en: str) -> bool:
    t = en.strip()
    if not t or article_num(t) or parse_struct(t) or TOPIC_RE.match(t):
        return False
    if len(t) > 120:
        return False
    if t[0].isalpha() and (t[0].isupper() or t.isupper()):
        return True
    return len(t) <= 40 and not t.endswith(".")


def build_corpus(lines: list[dict]) -> list[dict]:
    corpus: list[dict] = []
    book = chapter = section = topic = ""
    article: dict | None = None
    pending: dict | None = None  # {type, parts}

    def flush_pending() -> None:
        nonlocal pending, book, chapter, section, topic
        if not pending:
            return
        title = re.sub(r"\s+", " ", " ".join(pending["parts"])).strip()
        kind = pending["type"]
        if kind == "book":
            book, chapter, section, topic = title, "", "", ""
        elif kind == "chapter":
            chapter, section, topic = title, "", ""
        elif kind == "section":
            section, topic = title, ""
        else:
            topic = title
        pending = None

    def close_article() -> None:
        nonlocal article
        if not article:
            return
        article["text_ar"] = norm_ar(" ".join(article.pop("_ar")))
        article["text_en"] = norm_en(" ".join(article.pop("_en")))
        corpus.append(article)
        article = None

    for line in lines:
        en, ar = line["text_en"].strip(), line["text_ar"]
        num = article_num(en)

        if num is not None:
            flush_pending()
            close_article()
            article = {
                "article_number": num,
                "book": book,
                "chapter": chapter,
                "section": section,
                "topic": topic,
                "_ar": [],
                "_en": [],
                "source_page": line["page"],
                "citation": f"Egyptian Civil Code, Article {num}",
            }
            continue

        struct = parse_struct(en)
        if struct:
            kind, same = struct
            flush_pending()
            pending = {"type": kind, "parts": [same] if same else []}
            continue

        tm = TOPIC_RE.match(en)
        if tm:
            flush_pending()
            pending = {"type": "topic", "parts": [tm.group(2).strip()]}
            continue

        if pending and is_title_cont(en):
            limit = 3 if pending["type"] in ("section", "chapter", "book") else 2
            if len(pending["parts"]) < limit:
                pending["parts"].append(en)
                continue
            flush_pending()

        if pending:
            flush_pending()

        if article:
            if ar:
                article["_ar"].append(ar)
            if line["text_en"]:
                article["_en"].append(line["text_en"])

    flush_pending()
    close_article()
    return corpus


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    print("Extracting PDF...")
    lines = extract_lines(PDF_PATH)
    print(f"Extracted {len(lines)} lines.")

    corpus = build_corpus(lines)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Extracted {len(corpus)} articles → {OUTPUT_PATH}")

    for n in (1, 147, 646):
        art = next((a for a in corpus if a["article_number"] == n), None)
        print(f"\n===== ARTICLE {n} =====")
        print(json.dumps(art, ensure_ascii=False, indent=2) if art else "(not found)")


if __name__ == "__main__":
    main()
