from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from typing import Any
import fitz
from bs4 import BeautifulSoup
from docx import Document
from .cleaning import clean_text, remove_repeated_page_lines
from .util import write_jsonl, stable_id


def extract_pdf_native(path: Path) -> tuple[str, list[str]]:
    doc = fitz.open(path)
    pages = [page.get_text("text") or "" for page in doc]
    return "\n\n".join(pages), pages


def extract_pdf_docling(path: Path, ocr_languages: list[str], use_gpu: bool) -> str:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    except Exception as e:
        raise RuntimeError("Docling/OCR extras are not installed. Run RUN_0_SETUP_FULL.bat") from e
    opts = PdfPipelineOptions()
    opts.do_ocr = True
    opts.do_table_structure = False
    opts.ocr_options = EasyOcrOptions(lang=ocr_languages, use_gpu=use_gpu)
    # Docling's native parser cannot open its resources under accented Windows paths.
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_options=opts, backend=PyPdfiumDocumentBackend)})
    result = converter.convert(path)
    return result.document.export_to_markdown()


def extract_docx(path: Path) -> str:
    doc = Document(path)
    blocks: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip(): blocks.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            blocks.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(blocks)


def convert_legacy_doc(path: Path, cache_dir: Path) -> Path | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / (path.stem + ".docx")
    if out.exists() and out.stat().st_size > 100:
        return out
    # Microsoft Word COM is the most reliable on the user's Windows environment.
    if sys.platform == "win32":
        try:
            import win32com.client  # type: ignore
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(str(path.resolve()))
            doc.SaveAs2(str(out.resolve()), FileFormat=16)  # wdFormatDocumentDefault (.docx)
            doc.Close(False)
            word.Quit()
            if out.exists(): return out
        except Exception:
            try:
                word.Quit()  # type: ignore[name-defined]
            except Exception:
                pass
    # LibreOffice fallback.
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", str(cache_dir), str(path)],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if out.exists(): return out
        except Exception:
            pass
    # antiword fallback gives plain text; caller handles separately.
    return None


def extract_doc(path: Path, cache_dir: Path) -> tuple[str, str]:
    converted = convert_legacy_doc(path, cache_dir)
    if converted:
        return extract_docx(converted), "word_or_libreoffice_conversion"
    antiword = shutil.which("antiword")
    if antiword:
        proc = subprocess.run([antiword, str(path)], capture_output=True, timeout=120)
        for enc in ("utf-8", "cp1258", "latin-1"):
            try:
                return proc.stdout.decode(enc), "antiword"
            except Exception:
                continue
    raise RuntimeError("Cannot read legacy .doc. Install Microsoft Word, LibreOffice, or antiword.")


def extract_html(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    return soup.get_text("\n")


def extract_one(row: dict, cfg: dict, output_dir: Path) -> dict:
    path = Path(row["path"])
    ext = path.suffix.lower()
    method = ""
    pages: list[str] = []
    needs_ocr = False
    error = None
    raw = ""
    try:
        if ext == ".pdf":
            raw, pages = extract_pdf_native(path)
            method = "pymupdf"
            native_chars = len("".join(raw.split()))
            threshold = int(cfg["extraction"].get("min_text_chars_before_ocr", 1200))
            use_docling = str(cfg["extraction"].get("use_docling", "auto")).lower()
            if native_chars < threshold and use_docling != "never":
                try:
                    raw = extract_pdf_docling(
                        path,
                        cfg["extraction"].get("ocr_languages", ["vi", "en"]),
                        bool(cfg["extraction"].get("ocr_use_gpu", False)),
                    )
                    pages = [raw]
                    method = "docling_ocr"
                except Exception as e:
                    needs_ocr = True
                    if use_docling == "always": raise
                    error = f"OCR fallback unavailable: {e}"
        elif ext == ".docx":
            raw = extract_docx(path); pages = [raw]; method = "python-docx"
        elif ext == ".doc":
            raw, method = extract_doc(path, output_dir / "01_extracted" / "converted_docx"); pages = [raw]
        elif ext in {".html", ".htm"}:
            raw = extract_html(path); pages = [raw]; method = "beautifulsoup"
        elif ext == ".txt":
            raw = path.read_text(encoding="utf-8", errors="ignore"); pages = [raw]; method = "text"
        elif ext == ".json":
            raw = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False, indent=2); pages=[raw]; method="json"
        else:
            raise RuntimeError(f"Unsupported file type {ext}")
        if pages:
            pages = remove_repeated_page_lines(
                pages,
                float(cfg["cleaning"].get("repeated_line_page_ratio", .55)),
                int(cfg["cleaning"].get("repeated_line_max_chars", 120)),
            )
        cleaned = clean_text("\n\n".join(pages) if pages else raw)
    except Exception as e:
        cleaned = ""; error = str(e)
    out = {
        **row,
        "extraction_method": method,
        "text": cleaned,
        "text_chars": len(cleaned),
        "needs_ocr": needs_ocr,
        "extraction_error": error,
    }
    return out


def extract_all(manifest: list[dict], cfg: dict, output_dir: Path) -> list[dict]:
    from tqdm import tqdm
    rows = [extract_one(row, cfg, output_dir) for row in tqdm(manifest, desc="Extract/Clean")]
    write_jsonl(output_dir / "01_extracted" / "documents.jsonl", rows)
    failures = [r for r in rows if r.get("extraction_error") or r.get("text_chars", 0) < 100]
    write_jsonl(output_dir / "reports" / "extraction_issues.jsonl", failures)
    return rows
