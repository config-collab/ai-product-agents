"""
Company Knowledge Ingestion
============================
Processes a folder of company files and extracts structured engineering
knowledge (intent, constraints, decisions, part relationships) using Claude.

Supported file types:
  .eml .msg           — email messages
  .xlsx .csv          — spreadsheets / data tables
  .pdf                — PDF documents
  .docx               — Word documents
  .stp .step          — STEP CAD files (metadata + part names)
  .json               — JSON data
  .xml                — XML data

All records are tagged 'company_sourced' for highest-priority weighting
in the agent pipeline.

Usage:
    python ingest_company_knowledge.py
    python ingest_company_knowledge.py --product "espresso machine" --folder ./data
"""

from __future__ import annotations

import argparse
import csv
import email
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import anthropic as _anthropic
    _client = _anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    _MODEL  = "claude-sonnet-4-6"
except Exception as e:
    print(f"  ✗ Cannot import anthropic: {e}")
    sys.exit(1)

# Optional parsers — graceful degradation if not installed
try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

try:
    import pypdf
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

try:
    import docx as _docx
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False

try:
    import extract_msg as _extract_msg
    _HAS_MSG = True
except ImportError:
    _HAS_MSG = False


SUPPORTED_EXTENSIONS = {
    ".eml", ".msg",
    ".xlsx", ".csv",
    ".pdf",
    ".docx",
    ".stp", ".step",
    ".json",
    ".xml",
}

_MAX_TEXT_CHARS = 6000   # max chars sent to Claude per file


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:50]


def _call(prompt: str, max_tokens: int = 2048) -> str:
    rsp = _client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return rsp.content[0].text.strip()


def _extract_json(text: str):
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text)
    if m:
        raw = m.group(1)
    else:
        brace   = text.find("{")
        bracket = text.find("[")
        start = min(
            brace   if brace   != -1 else len(text),
            bracket if bracket != -1 else len(text),
        )
        end = max(text.rfind("}"), text.rfind("]")) + 1
        raw = text[start:end]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# FILE EXTRACTORS — return (text, source_type, approx_date)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_eml(path: Path) -> tuple[str, str, str]:
    with open(path, "rb") as fh:
        msg = email.message_from_bytes(fh.read())
    subject = msg.get("Subject", "")
    sender  = msg.get("From", "")
    date    = msg.get("Date", "")
    body    = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                body += part.get_payload(decode=True).decode(charset, errors="replace")
                break
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    text = f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}"
    # Parse date to ISO year-month
    try:
        from email.utils import parsedate
        d = parsedate(date)
        iso_date = f"{d[0]}-{d[1]:02d}" if d else datetime.now().strftime("%Y-%m")
    except Exception:
        iso_date = datetime.now().strftime("%Y-%m")
    return text[:_MAX_TEXT_CHARS], "email", iso_date


def _extract_msg(path: Path) -> tuple[str, str, str]:
    if not _HAS_MSG:
        return f"[.msg parser not available — install extract-msg: {path.name}]", "email", datetime.now().strftime("%Y-%m")
    msg  = _extract_msg.Message(str(path))
    text = f"From: {msg.sender}\nDate: {msg.date}\nSubject: {msg.subject}\n\n{msg.body or ''}"
    try:
        iso_date = msg.date.strftime("%Y-%m") if hasattr(msg.date, "strftime") else datetime.now().strftime("%Y-%m")
    except Exception:
        iso_date = datetime.now().strftime("%Y-%m")
    return text[:_MAX_TEXT_CHARS], "email", iso_date


def _extract_xlsx(path: Path) -> tuple[str, str, str]:
    if not _HAS_OPENPYXL:
        return f"[.xlsx parser not available — install openpyxl: {path.name}]", "spreadsheet", datetime.now().strftime("%Y-%m")
    wb   = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets[:3]:   # first 3 sheets
        rows.append(f"=== Sheet: {ws.title} ===")
        for row in ws.iter_rows(max_row=200, values_only=True):
            if any(c is not None for c in row):
                rows.append("\t".join(str(c) if c is not None else "" for c in row))
        if len("\n".join(rows)) > _MAX_TEXT_CHARS:
            break
    return "\n".join(rows)[:_MAX_TEXT_CHARS], "spreadsheet", datetime.now().strftime("%Y-%m")


def _extract_csv(path: Path) -> tuple[str, str, str]:
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)
        rows   = ["\t".join(row) for _, row in zip(range(300), reader)]
    return "\n".join(rows)[:_MAX_TEXT_CHARS], "spreadsheet", datetime.now().strftime("%Y-%m")


def _extract_pdf(path: Path) -> tuple[str, str, str]:
    if not _HAS_PYPDF:
        return f"[.pdf parser not available — install pypdf: {path.name}]", "pdf", datetime.now().strftime("%Y-%m")
    text = []
    with open(path, "rb") as fh:
        reader = pypdf.PdfReader(fh)
        for page in reader.pages[:30]:
            text.append(page.extract_text() or "")
    return "\n".join(text)[:_MAX_TEXT_CHARS], "pdf", datetime.now().strftime("%Y-%m")


def _extract_docx(path: Path) -> tuple[str, str, str]:
    if not _HAS_DOCX:
        return f"[.docx parser not available — install python-docx: {path.name}]", "document", datetime.now().strftime("%Y-%m")
    doc  = _docx.Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return text[:_MAX_TEXT_CHARS], "document", datetime.now().strftime("%Y-%m")


def _extract_step(path: Path) -> tuple[str, str, str]:
    """Extract part names and basic metadata from STEP/STP files."""
    text_lines = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 2000:
                    break
                line = line.strip()
                # STEP entity types relevant for parts/assemblies
                if any(kw in line.upper() for kw in (
                    "PRODUCT(", "PRODUCT_DEFINITION", "PART_NAME",
                    "NEXT_ASSEMBLY", "FILE_NAME", "FILE_DESCRIPTION",
                )):
                    text_lines.append(line)
    except Exception as e:
        return f"[STEP read error: {e}]", "cad", datetime.now().strftime("%Y-%m")
    text = f"STEP/CAD file: {path.name}\n" + "\n".join(text_lines)
    return text[:_MAX_TEXT_CHARS], "cad", datetime.now().strftime("%Y-%m")


def _extract_json_file(path: Path) -> tuple[str, str, str]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    # Pretty-print first 200 keys worth
    try:
        data = json.loads(raw)
        text = json.dumps(data, indent=2)[:_MAX_TEXT_CHARS]
    except Exception:
        text = raw[:_MAX_TEXT_CHARS]
    return text, "json", datetime.now().strftime("%Y-%m")


def _extract_xml_file(path: Path) -> tuple[str, str, str]:
    try:
        tree = ET.parse(str(path))
        root = tree.getroot()

        def _walk(node, depth=0) -> list[str]:
            lines = [f"{'  '*depth}<{node.tag}> {(node.text or '').strip()[:120]}"]
            for child in list(node)[:50]:
                lines.extend(_walk(child, depth + 1))
            return lines

        text = "\n".join(_walk(root))
    except Exception as e:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()[:_MAX_TEXT_CHARS]
    return text[:_MAX_TEXT_CHARS], "xml", datetime.now().strftime("%Y-%m")


_EXTRACTORS = {
    ".eml":  _extract_eml,
    ".msg":  _extract_msg,
    ".xlsx": _extract_xlsx,
    ".csv":  _extract_csv,
    ".pdf":  _extract_pdf,
    ".docx": _extract_docx,
    ".stp":  _extract_step,
    ".step": _extract_step,
    ".json": _extract_json_file,
    ".xml":  _extract_xml_file,
}


def extract_file(path: Path) -> tuple[str, str, str]:
    """Return (text, source_type, iso_date) for any supported file."""
    ext = path.suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        return f"[unsupported: {path.name}]", "unknown", datetime.now().strftime("%Y-%m")
    try:
        return extractor(path)
    except Exception as e:
        return f"[extraction error: {e}]", "error", datetime.now().strftime("%Y-%m")


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE EXTRACTION VIA CLAUDE
# ─────────────────────────────────────────────────────────────────────────────

def extract_knowledge(product: str, filename: str, source_type: str,
                      text: str, record_id: str) -> dict:
    """Use Claude to extract structured engineering knowledge from raw text."""
    if not text.strip() or text.startswith("["):
        # Placeholder / error text — return minimal record
        return {
            "record_id":             record_id,
            "source_file":           filename,
            "source_type":           source_type,
            "tag":                   "company_sourced",
            "intent":                "",
            "constraints":           [],
            "trade_offs":            "",
            "alternatives_rejected": [],
            "decisions":             [],
            "part_relationships":    [],
            "confidence":            "assumed",
            "text":                  text[:500],
            "notes":                 "extraction skipped — content unavailable",
        }

    prompt = f"""You are a senior systems engineer. Extract structured engineering knowledge
from the following company document excerpt for a: {product}

Document: {filename} (type: {source_type})

--- CONTENT START ---
{text}
--- CONTENT END ---

Extract any engineering knowledge present and return a JSON object:
{{
  "intent":                "what design goal or objective is described (empty string if none)",
  "constraints":           ["hard constraint 1", ...],  // measurable limits, empty list if none
  "trade_offs":            "what was gained vs. lost in any described decision (empty if none)",
  "alternatives_rejected": ["alternative + reason rejected", ...],  // empty list if none
  "decisions":             ["specific engineering decision described", ...],  // empty list if none
  "part_relationships":    [
    {{"part_a": "part name", "relation": "connects_to|requires|replaces|compatible_with|incompatible_with", "part_b": "part name"}}
  ],
  "confidence":            "verified"  // always verified for company documents
}}

Rules:
- Extract ONLY what is actually present in the text — do not invent content
- Keep constraints specific and measurable where possible
- If the document contains no engineering knowledge, return empty lists/strings
- Output JSON only.
""".strip()

    try:
        raw  = _call(prompt)
        data = _extract_json(raw)
    except Exception as e:
        print(f"    ⚠ Claude extraction error for {filename}: {e}")
        data = {
            "intent": "", "constraints": [], "trade_offs": "",
            "alternatives_rejected": [], "decisions": [],
            "part_relationships": [], "confidence": "assumed",
        }

    # Assemble final record
    flat_text = _flatten_record(product, filename, data)
    return {
        "record_id":             record_id,
        "source_file":           filename,
        "source_type":           source_type,
        "tag":                   "company_sourced",
        "intent":                data.get("intent", ""),
        "constraints":           data.get("constraints", []),
        "trade_offs":            data.get("trade_offs", ""),
        "alternatives_rejected": data.get("alternatives_rejected", []),
        "decisions":             data.get("decisions", []),
        "part_relationships":    data.get("part_relationships", []),
        "confidence":            data.get("confidence", "verified"),
        "text":                  flat_text,
    }


def _flatten_record(product: str, filename: str, d: dict) -> str:
    """Flatten extracted knowledge to a text blob for RAG ingestion."""
    parts = [f"Product: {product}", f"Source: {filename}"]
    if d.get("intent"):
        parts.append(f"Intent: {d['intent']}")
    if d.get("constraints"):
        parts.append("Constraints: " + "; ".join(d["constraints"]))
    if d.get("trade_offs"):
        parts.append(f"Trade-offs: {d['trade_offs']}")
    if d.get("alternatives_rejected"):
        parts.append("Alternatives rejected: " + "; ".join(d["alternatives_rejected"]))
    if d.get("decisions"):
        parts.append("Decisions: " + "; ".join(d["decisions"]))
    if d.get("part_relationships"):
        rels = "; ".join(
            f"{r.get('part_a')} {r.get('relation')} {r.get('part_b')}"
            for r in d["part_relationships"]
        )
        parts.append(f"Part relationships: {rels}")
    parts.append("Tag: company_sourced")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# FOLDER SCAN
# ─────────────────────────────────────────────────────────────────────────────

def scan_folder(folder: Path) -> list[Path]:
    """Recursively find all supported files in folder."""
    found = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            found.append(path)
    return found


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest company knowledge files")
    parser.add_argument("--product", type=str, default="",
                        help="Product name")
    parser.add_argument("--folder",  type=str, default="",
                        help="Path to data folder")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  COMPANY KNOWLEDGE INGESTION")
    print("═" * 60)
    print("  Supported: .eml .msg .xlsx .csv .pdf .docx .stp .step .json .xml\n")

    # Optional parsers status
    missing = []
    if not _HAS_OPENPYXL: missing.append("openpyxl (for .xlsx)")
    if not _HAS_PYPDF:    missing.append("pypdf (for .pdf)")
    if not _HAS_DOCX:     missing.append("python-docx (for .docx)")
    if not _HAS_MSG:      missing.append("extract-msg (for .msg)")
    if missing:
        print(f"  ⚠ Optional parsers not installed (pip install {' '.join(missing)}):")
        for m in missing:
            print(f"    • {m}")
        print()

    product = args.product.strip() or input("  What product? > ").strip()
    if not product:
        print("  ✗ No product specified.")
        sys.exit(1)

    folder_str = args.folder.strip() or input("  Where is your data folder? > ").strip()
    folder     = Path(folder_str).expanduser().resolve()
    if not folder.exists():
        print(f"  ✗ Folder not found: {folder}")
        sys.exit(1)

    slug     = _slug(product)
    out_path = Path(__file__).parent / f"company_knowledge_{slug}.json"

    print(f"\n  Product : {product}")
    print(f"  Folder  : {folder}")
    print(f"  Output  : {out_path}\n")

    # Scan
    files = scan_folder(folder)
    if not files:
        print(f"  ✗ No supported files found in {folder}")
        sys.exit(1)
    print(f"  Found {len(files)} file(s):\n")
    for f in files:
        print(f"    • {f.name}")
    print()

    # Process
    records     = []
    file_index  = {}   # filename → source_date (for report)
    for i, path in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {path.name} ...", end=" ", flush=True)
        record_id = f"CK-{i:03d}"
        text, source_type, iso_date = extract_file(path)
        print(f"({source_type}, {len(text)} chars) → extracting ...", end=" ", flush=True)
        record = extract_knowledge(product, path.name, source_type, text, record_id)
        record["source_date"] = iso_date
        records.append(record)
        file_index[path.name] = iso_date

        n_constraints = len(record.get("constraints", []))
        n_decisions   = len(record.get("decisions", []))
        n_parts       = len(record.get("part_relationships", []))
        print(f"✓  ({n_constraints} constraints, {n_decisions} decisions, {n_parts} part-rels)")

    # Save
    output = {
        "product":      product,
        "generated_at": datetime.now().isoformat(),
        "source_folder": str(folder),
        "model":        _MODEL,
        "tag":          "company_sourced",
        "total":        len(records),
        "file_index":   file_index,
        "records":      records,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    # Summary
    total_constraints = sum(len(r.get("constraints", [])) for r in records)
    total_decisions   = sum(len(r.get("decisions", [])) for r in records)
    total_part_rels   = sum(len(r.get("part_relationships", [])) for r in records)
    print(f"""
  ✓ Ingestion complete
    Records    : {len(records)}
    Constraints: {total_constraints}
    Decisions  : {total_decisions}
    Part rels  : {total_part_rels}
    Saved →    : {out_path}

  The file will be auto-detected by the agent pipeline on next run
  when the product name matches: '{product}'
""")


if __name__ == "__main__":
    main()
