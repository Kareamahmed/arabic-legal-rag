"""
Egyptian Civil Code — Bilingual PDF -> Structured JSON Extractor
==================================================================

Extracts a bilingual (Arabic/English) two-column tabular PDF of the
Egyptian Civil Code into a flat, one-record-per-article JSON corpus
matching the target schema:

    {
      "article_number": 147,
      "book": "Obligations or Personal Rights",
      "chapter": "Sources of Obligations",
      "section": "Contracts",
      "topic": "The Effects of a Contract",
      "text_ar": "...",
      "text_en": "...",
      "is_repealed": false,
      "source_page": 34,
      "citation": "Egyptian Civil Code, Article 147"
    }
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import pdfplumber

# --------------------------------------------------------------------------
# REQUIRED PATHS
# --------------------------------------------------------------------------
PDF_PATH = Path(__file__).parent / "file" / "egyptian_civil_code.pdf"
OUTPUT_PATH = Path(__file__).parent / "data" / "corpus.json"

VALIDATION_REPORT_PATH = OUTPUT_PATH.parent / "validation_report.json"
ROW_DUMP_PATH = OUTPUT_PATH.parent / "row_dump.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("civil_code_extractor")


# ==========================================================================
# 1. TEXT & DIGIT PATTERNS / NORMALIZATION
# ==========================================================================

AR_RE = re.compile(r"[\u0600-\u06FF]")
EN_RE = re.compile(r"[A-Za-z]")
NUM_RE = re.compile(r"^[0-9٠-٩]+$")
NUM_PUNCT_RE = re.compile(r"^[0-9٠-٩\-–—./()]+$")
ZW_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e]")

STRIP_AR_HEADER_RE = re.compile(
    r"^\s*(?:"
    r"(?:مادة|المادة|الماده)\s*[\(\[]?\s*[0-9٠-٩]+\s*[\)\]\(\]]*"
    r"|"
    r"[\(\[]?\s*[0-9٠-٩]+\s*[\)\]\(\]]*\s*(?:مادة|المادة|الماده)"
    r")\s*[:\.\-–—]*\s*",
    re.IGNORECASE,
)


def has_ar(s: str) -> bool:
    return bool(AR_RE.search(s))


def has_en(s: str) -> bool:
    return bool(EN_RE.search(s))


def reconstruct_word(word: dict) -> str:
    text = word.get("text", "")
    chars = word.get("chars") or []
    if not chars or NUM_RE.fullmatch(text):
        return text
    reverse = has_ar(text)
    chars_sorted = sorted(chars, key=lambda c: c["x0"], reverse=reverse)
    return "".join(c["text"] for c in chars_sorted)


def norm_ar(text: str) -> str:
    if not text:
        return ""
    text = ZW_RE.sub("", unicodedata.normalize("NFKC", text)).replace("\u0640", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\)\s*([0-9٠-٩]+)\s*\(", r"(\1)", text)
    text = re.sub(r"\s+([،؛,.!?])", r"\1", text)
    text = re.sub(r"([،؛,.!?])(?=\S)", r"\1 ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_ar_article_header(text: str) -> str:
    if not text:
        return ""
    cleaned = STRIP_AR_HEADER_RE.sub("", text)
    return cleaned.strip(" :.-")


def norm_en(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


clean_display_arabic = norm_ar
normalize_arabic = norm_ar
clean_english = norm_en


def smart_join_english(prev: str, nxt: str) -> str:
    if not prev:
        return nxt
    if not nxt:
        return prev
    if prev.endswith("-") and nxt[:1].islower():
        return prev[:-1] + nxt
    return prev.rstrip() + " " + nxt.lstrip()


def smart_join_arabic(prev: str, nxt: str) -> str:
    if not prev:
        return nxt
    if not nxt:
        return prev
    return prev.rstrip() + " " + nxt.lstrip()


# ==========================================================================
# 2. PATTERNS
# ==========================================================================

ARTICLE_EN_RE = re.compile(r"^\s*A?rticle\s+(\d+)\b", re.IGNORECASE)
ARTICLE_AR_RE = re.compile(r"(?:مادة|الماده|الرقم)\D{0,6}([0-9٠-٩]+)")
ARTICLE_AR_NUM_FIRST_RE = re.compile(r"([0-9٠-٩]+)\D{0,6}(?:مادة|الماده)")

# نطاق الإلغاء: "Articles 54 to 80 were repealed..."
REPEAL_RANGE_RE = re.compile(
    r"^\s*Articles?\s+(\d+)\s*(?:to|-|–|through)\s*(\d+)\b.{0,100}?(?:repealed|abrogated)",
    re.IGNORECASE | re.DOTALL,
)

# إلغاء مادة مفردة بدقة: يشترط أن يكون لفظ repealed تابعاً للعنوان وليس فعلاً داخل المتن
REPEAL_SINGLE_RE = re.compile(
    r"^\s*Article\s+(\d+)\s*(?:[-–—:]\s*)?(?:\([^\)]*repealed|\b(?:is|was|were|has\s+been)\s+repealed\b|\brepealed\b)",
    re.IGNORECASE,
)

REPEAL_AR_SINGLE_RE = re.compile(
    r"^\s*(?:مادة|المادة|الماده)\s*[\(\[]?\s*([0-9٠-٩]+)\s*[\)\]]?\s*[\(\-–—:]?\s*(?:ملغاة|ملغية|ألغيت)",
    re.IGNORECASE,
)

HEADING_KEYWORDS = [
    (re.compile(r"^\s*(BOOK|PART)\b", re.IGNORECASE), "book"),
    (re.compile(r"^\s*CHAPTER\b", re.IGNORECASE), "chapter"),
    (re.compile(r"^\s*SECTION\b", re.IGNORECASE), "section"),
]

# Matches the label prefix: "BOOK IV", "Chapter I:", "Section 2 -", "Part First", ...
# The Roman numeral part is case-sensitive (uppercase only) so a real title
# word such as "Section Civil ..." is not mistaken for a numeral.
HEADING_PREFIX_RE = re.compile(
    r"^\s*(?:BOOK|PART|CHAPTER|SECTION)\s+"
    r"(?:(?-i:[IVXLCDM]+)|\d+|"
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth))\b"
    r"\s*[:.\-–—]*\s*",
    re.IGNORECASE,
)

MAX_SANE_RECORD_CHARS = 6000


def clean_heading_label(text: str) -> str:
    """'BOOK IV\\nACCESSORY RIGHTS' -> 'ACCESSORY RIGHTS'"""
    text = HEADING_PREFIX_RE.sub("", text or "", count=1)
    return " ".join(text.split()).strip(" :.-–—")


# ==========================================================================
# 3. DATA MODEL
# ==========================================================================


@dataclass
class ArticleRecord:
    article_number: int
    book: str = ""
    chapter: str = ""
    section: str = ""
    topic: str = ""
    text_ar: str = ""
    text_en: str = ""
    is_repealed: bool = False
    source_page: Optional[int] = None
    citation: str = ""

    def finalize(self):
        self.text_en = norm_en(self.text_en)
        self.text_ar = strip_ar_article_header(norm_ar(self.text_ar))
        self.citation = f"Egyptian Civil Code, Article {self.article_number}"


@dataclass
class HierarchyState:
    book: str = ""
    chapter: str = ""
    section: str = ""
    topic: str = ""

    def apply_heading(self, level: str, text_en: str):
        text_en = clean_heading_label(text_en)
        if not text_en:
            return
        setattr(self, level, text_en)
        order = ["book", "chapter", "section", "topic"]
        idx = order.index(level)
        for deeper in order[idx + 1 :]:
            setattr(self, deeper, "")

    def apply_topic(self, text_en: str):
        text_en = " ".join((text_en or "").split()).strip(" :")
        if text_en:
            self.topic = text_en

    def snapshot(self) -> dict:
        return {
            "book": self.book,
            "chapter": self.chapter,
            "section": self.section,
            "topic": self.topic,
        }


# ==========================================================================
# 4. LOW-LEVEL CELL TEXT RECONSTRUCTION
# ==========================================================================


def _group_words_into_lines(
    words: list[dict], y_tolerance: float = 3.0
) -> list[list[dict]]:
    if not words:
        return []
    words = sorted(words, key=lambda w: w["top"])
    lines: list[list[dict]] = []
    current: list[dict] = [words[0]]
    current_top = words[0]["top"]
    for w in words[1:]:
        if abs(w["top"] - current_top) <= y_tolerance:
            current.append(w)
        else:
            lines.append(current)
            current = [w]
            current_top = w["top"]
    lines.append(current)
    return lines


def extract_cell_text(page: "pdfplumber.page.Page", bbox, *, rtl: bool) -> str:
    if not bbox:
        return ""
    x0, top, x1, bottom = bbox

    x0 = max(0.0, min(float(x0), float(page.width)))
    top = max(0.0, min(float(top), float(page.height)))
    x1 = max(0.0, min(float(x1), float(page.width)))
    bottom = max(0.0, min(float(bottom), float(page.height)))

    if x1 <= x0 or bottom <= top:
        return ""
    try:
        cropped = page.crop((x0, top, x1, bottom))
        words = cropped.extract_words(
            keep_blank_chars=False,
            use_text_flow=False,
            return_chars=True,
        )
    except Exception as exc:
        log.debug("Cell crop/extract failed at %s: %s", bbox, exc)
        return ""
    if not words:
        return ""

    lines = _group_words_into_lines(words)
    out_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: (-w["x0"] if rtl else w["x0"]))
        line_text = " ".join(reconstruct_word(w) for w in line_sorted)
        out_lines.append(line_text)
    return "\n".join(out_lines)


# ==========================================================================
# 5. ROW CLASSIFICATION
# ==========================================================================

ROW_ARTICLE_START = "article_start"
ROW_HEADING = "heading"
ROW_REPEAL_NOTICE = "repeal_notice"
ROW_CONTINUATION = "continuation"
ROW_BLANK = "blank"


def _looks_like_heading(en_text: str, ar_text: str) -> bool:
    combined = (en_text or "").strip()
    if not combined:
        return bool(ar_text) and len(ar_text.strip()) < 60
    if len(combined) > 90:
        return False
    if combined.endswith((".", ";", ",")):
        return False
    if re.match(r"^\d+\.\s+\S", combined):
        return True
    if combined.isupper():
        return True
    if any(pat.match(combined) for pat, _ in HEADING_KEYWORDS):
        return True
    words = combined.split()
    if 1 <= len(words) <= 8 and combined[:1].isupper():
        return True
    return False


def classify_row(en_text: str, ar_text: str) -> str:
    en_text = (en_text or "").strip()
    ar_text = (ar_text or "").strip()

    if not en_text and not ar_text:
        return ROW_BLANK

    if (
        REPEAL_RANGE_RE.search(en_text)
        or REPEAL_SINGLE_RE.search(en_text)
        or REPEAL_AR_SINGLE_RE.search(ar_text)
    ):
        return ROW_REPEAL_NOTICE

    if (
        ARTICLE_EN_RE.match(en_text)
        or ARTICLE_AR_RE.search(ar_text)
        or ARTICLE_AR_NUM_FIRST_RE.search(ar_text)
    ):
        return ROW_ARTICLE_START

    if _looks_like_heading(en_text, ar_text):
        return ROW_HEADING

    return ROW_CONTINUATION


def classify_heading_level(en_text: str) -> str:
    # Uses the RAW text (with "BOOK"/"Chapter"/"Section" prefix) to pick the
    # level; the prefix is removed later in HierarchyState.apply_heading.
    for pattern, level in HEADING_KEYWORDS:
        if pattern.match(en_text.strip()):
            return level
    return "topic"


# ==========================================================================
# 6. MAIN EXTRACTION PIPELINE
# ==========================================================================


class ExtractionStats:
    def __init__(self):
        self.pages_processed = 0
        self.rows_seen = 0
        self.rows_by_type: dict[str, int] = {}
        self.fallback_pages = 0
        self.warnings: list[str] = []

    def note_row(self, row_type: str):
        self.rows_by_type[row_type] = self.rows_by_type.get(row_type, 0) + 1

    def warn(self, msg: str):
        log.warning(msg)
        self.warnings.append(msg)


def find_table_on_page(page: "pdfplumber.page.Page"):
    tables = page.find_tables(
        table_settings={
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 5,
            "join_tolerance": 5,
        }
    )
    if not tables:
        return None
    return max(tables, key=lambda t: len(t.rows))


def iter_table_rows(page: "pdfplumber.page.Page", table, stats: ExtractionStats):
    mid_x = page.width / 2.0

    for row in table.rows:
        row_top = row.bbox[1]
        row_bottom = row.bbox[3]

        valid_cells = [c for c in row.cells if c is not None]

        left_bbox = None
        right_bbox = None

        for c in valid_cells:
            cx = (c[0] + c[2]) / 2.0
            if cx < mid_x:
                if left_bbox is None or c[0] < left_bbox[0]:
                    left_bbox = c
            else:
                if right_bbox is None or c[2] > right_bbox[2]:
                    right_bbox = c

        if left_bbox is None and right_bbox is not None:
            left_bbox = (0.0, row_top, right_bbox[0], row_bottom)
        elif right_bbox is None and left_bbox is not None:
            right_bbox = (left_bbox[2], row_top, page.width, row_bottom)
        elif left_bbox is None and right_bbox is None:
            left_bbox = (0.0, row_top, mid_x, row_bottom)
            right_bbox = (mid_x, row_top, page.width, row_bottom)

        en_text = extract_cell_text(page, left_bbox, rtl=False)
        ar_text = extract_cell_text(page, right_bbox, rtl=True)

        if not ar_text.strip():
            split_x = left_bbox[2] if (left_bbox and left_bbox[2] > 50) else mid_x
            alt_right_bbox = (split_x - 3.0, row_top, page.width, row_bottom)
            ar_text = extract_cell_text(page, alt_right_bbox, rtl=True)

        yield en_text, ar_text


def fallback_positional_rows(page: "pdfplumber.page.Page", stats: ExtractionStats):
    stats.fallback_pages += 1
    words = page.extract_words(
        keep_blank_chars=False,
        use_text_flow=False,
        return_chars=True,
    )
    if not words:
        return
    mid_x = page.width / 2.0
    left_words = [w for w in words if (w["x0"] + w["x1"]) / 2.0 < mid_x]
    right_words = [w for w in words if (w["x0"] + w["x1"]) / 2.0 >= mid_x]

    left_lines = _group_words_into_lines(left_words)
    right_lines = _group_words_into_lines(right_words)

    def line_text(line, rtl):
        s = sorted(line, key=lambda w: (-w["x0"] if rtl else w["x0"]))
        return " ".join(reconstruct_word(w) for w in s)

    left_by_top = {min(w["top"] for w in ln): line_text(ln, False) for ln in left_lines}
    right_by_top = {
        min(w["top"] for w in ln): line_text(ln, True) for ln in right_lines
    }

    all_tops = sorted(set(list(left_by_top.keys()) + list(right_by_top.keys())))
    merged_tops: list[float] = []
    for t in all_tops:
        if merged_tops and abs(t - merged_tops[-1]) <= 6:
            continue
        merged_tops.append(t)

    for t in merged_tops:
        en = next((v for k, v in left_by_top.items() if abs(k - t) <= 6), "")
        ar = next((v for k, v in right_by_top.items() if abs(k - t) <= 6), "")
        yield en, ar


def extract_pdf(
    pdf_path: Path,
    *,
    max_pages: Optional[int] = None,
    dump_rows: bool = False,
) -> tuple[list[ArticleRecord], ExtractionStats]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {pdf_path}.")

    stats = ExtractionStats()
    hierarchy = HierarchyState()
    records: list[ArticleRecord] = []
    row_dump: list[dict] = []

    current: Optional[ArticleRecord] = None

    def flush_current():
        nonlocal current
        if current is not None:
            current.finalize()
            records.append(current)
            current = None

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        if max_pages:
            n_pages = min(n_pages, max_pages)

        for page_idx in range(n_pages):
            page = pdf.pages[page_idx]
            page_number = page_idx + 1
            stats.pages_processed += 1

            table = find_table_on_page(page)
            if table is not None:
                row_iter = iter_table_rows(page, table, stats)
            else:
                row_iter = fallback_positional_rows(page, stats)

            for en_text, ar_text in row_iter:
                stats.rows_seen += 1
                row_type = classify_row(en_text, ar_text)
                stats.note_row(row_type)

                if dump_rows:
                    row_dump.append(
                        {
                            "page": page_number,
                            "type": row_type,
                            "en": en_text,
                            "ar": ar_text,
                        }
                    )

                if row_type == ROW_BLANK:
                    continue

                if row_type == ROW_REPEAL_NOTICE:
                    flush_current()
                    lo_hi = None
                    m = REPEAL_RANGE_RE.search(en_text)
                    if m:
                        lo_hi = (int(m.group(1)), int(m.group(2)))
                    else:
                        m2 = REPEAL_SINGLE_RE.search(en_text)
                        if m2:
                            n = int(m2.group(1))
                            lo_hi = (n, n)
                        else:
                            m_ar = REPEAL_AR_SINGLE_RE.search(ar_text)
                            if m_ar:
                                n = int(m_ar.group(1))
                                lo_hi = (n, n)

                    if lo_hi is None:
                        stats.warn(
                            f"Page {page_number}: repeal notice detected but "
                            f"could not parse article range from: {en_text!r}"
                        )
                        continue

                    lo, hi = lo_hi
                    for n in range(lo, hi + 1):
                        rec = ArticleRecord(
                            article_number=n,
                            **hierarchy.snapshot(),
                            text_en=en_text,
                            text_ar=ar_text,
                            is_repealed=True,
                            source_page=page_number,
                        )
                        rec.finalize()
                        records.append(rec)
                    continue

                if row_type == ROW_HEADING:
                    flush_current()
                    level = classify_heading_level(en_text or ar_text)
                    label = en_text.strip() if en_text.strip() else ar_text.strip()
                    if level == "topic":
                        hierarchy.apply_topic(label)
                    else:
                        hierarchy.apply_heading(level, label)
                    continue

                if row_type == ROW_ARTICLE_START:
                    flush_current()
                    m_en = ARTICLE_EN_RE.match(en_text)
                    article_num = None
                    if m_en:
                        article_num = int(m_en.group(1))
                        body_en = en_text[m_en.end() :].strip(" .:-")
                    else:
                        body_en = en_text

                    if article_num is None:
                        m_ar = ARTICLE_AR_RE.search(
                            ar_text
                        ) or ARTICLE_AR_NUM_FIRST_RE.search(ar_text)
                        if m_ar:
                            article_num = int(m_ar.group(1))

                    if article_num is None:
                        stats.warn(
                            f"Page {page_number}: classified as article start "
                            f"but no article number could be parsed: "
                            f"en={en_text!r} ar={ar_text!r}"
                        )
                        continue

                    body_ar = strip_ar_article_header(ar_text)

                    current = ArticleRecord(
                        article_number=article_num,
                        **hierarchy.snapshot(),
                        text_en=body_en,
                        text_ar=body_ar,
                        is_repealed=False,
                        source_page=page_number,
                    )
                    continue

                # ROW_CONTINUATION
                if current is None:
                    if en_text or ar_text:
                        stats.note_row("orphan_continuation")
                    continue

                current.text_en = smart_join_english(current.text_en, en_text)
                current.text_ar = smart_join_arabic(current.text_ar, ar_text)

        flush_current()

    if dump_rows:
        ROW_DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        ROW_DUMP_PATH.write_text(
            json.dumps(row_dump, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("Row-level dump written to %s (%d rows)", ROW_DUMP_PATH, len(row_dump))

    return records, stats


# ==========================================================================
# 7. VALIDATION
# ==========================================================================


def validate_corpus(records: list[ArticleRecord]) -> dict:
    report: dict = {"ok": True, "errors": [], "warnings": [], "stats": {}}

    if not records:
        report["ok"] = False
        report["errors"].append("No records extracted at all.")
        return report

    by_number: dict[int, list[ArticleRecord]] = {}
    for r in records:
        by_number.setdefault(r.article_number, []).append(r)

    dupes = {n: rs for n, rs in by_number.items() if len(rs) > 1}
    if dupes:
        report["warnings"].append(
            f"{len(dupes)} article numbers have more than one record "
            f"(e.g. {list(dupes.keys())[:10]}) — check for failed splits."
        )

    numbers = sorted(by_number.keys())
    lo, hi = numbers[0], numbers[-1]
    missing = [n for n in range(lo, hi + 1) if n not in by_number]
    if missing:
        report["ok"] = False
        report["errors"].append(
            f"{len(missing)} article numbers are missing between {lo} and "
            f"{hi} with no repeal/record explaining the gap: "
            f"{missing[:25]}{'...' if len(missing) > 25 else ''}"
        )

    empty_ar = [
        r.article_number for r in records if not r.is_repealed and not r.text_ar.strip()
    ]
    if empty_ar:
        report["ok"] = False
        report["errors"].append(
            f"{len(empty_ar)} non-repealed records have empty text_ar: "
            f"{empty_ar[:25]}{'...' if len(empty_ar) > 25 else ''}"
        )

    too_long = [
        r.article_number
        for r in records
        if len(r.text_en) > MAX_SANE_RECORD_CHARS
        or len(r.text_ar) > MAX_SANE_RECORD_CHARS
    ]
    if too_long:
        report["warnings"].append(
            f"{len(too_long)} records exceed {MAX_SANE_RECORD_CHARS} chars: "
            f"{too_long[:25]}"
        )

    repealed = [r.article_number for r in records if r.is_repealed]
    report["stats"] = {
        "total_records": len(records),
        "article_number_range": [lo, hi],
        "repealed_count": len(repealed),
        "repealed_articles": repealed,
        "duplicate_count": len(dupes),
    }

    return report


# ==========================================================================
# 8. CLI / MAIN
# ==========================================================================


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--pdf", type=Path, default=PDF_PATH, help="Override PDF input path"
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_PATH, help="Override JSON output path"
    )
    parser.add_argument(
        "--max-pages", type=int, default=None, help="Only process first N pages"
    )
    parser.add_argument(
        "--dump-rows",
        action="store_true",
        help="Write row classifications to data/row_dump.json",
    )
    parser.add_argument(
        "--sample", type=int, default=0, help="Print N random extracted articles"
    )
    args = parser.parse_args()

    log.info("Reading PDF from %s", args.pdf)
    records, stats = extract_pdf(
        args.pdf, max_pages=args.max_pages, dump_rows=args.dump_rows
    )
    log.info(
        "Extracted %d article records from %d pages (%d rows; fallback used on %d pages)",
        len(records),
        stats.pages_processed,
        stats.rows_seen,
        stats.fallback_pages,
    )
    log.info("Row type breakdown: %s", stats.rows_by_type)

    records.sort(key=lambda r: r.article_number)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Corpus written to %s", args.output)

    report = validate_corpus(records)
    VALIDATION_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log.info("=" * 70)
    log.info("VALIDATION: %s", "PASSED" if report["ok"] else "FAILED")
    for e in report["errors"]:
        log.error("  ERROR: %s", e)
    for w in report["warnings"]:
        log.warning("  WARN:  %s", w)
    log.info("Stats: %s", report["stats"])
    log.info("Full report: %s", VALIDATION_REPORT_PATH)

    if stats.warnings:
        log.info(
            "%d extraction-time warnings were logged above/inline.", len(stats.warnings)
        )

    if args.sample:
        sample_n = min(args.sample, len(records))
        log.info("=" * 70)
        log.info("RANDOM SAMPLE OF %d ARTICLES:", sample_n)
        for r in random.sample(records, sample_n):
            print(
                f"\n--- Article {r.article_number} "
                f"[{r.book} / {r.chapter} / {r.section} / {r.topic}] "
                f"(repealed={r.is_repealed}, page={r.source_page}) ---"
            )
            print("EN:", r.text_en[:300])
            print("AR:", r.text_ar[:300])

    if not report["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()