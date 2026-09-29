import io
import os
import re
import csv
import base64
from typing import List, Dict, Any

# Optional robust parsers with graceful fallbacks
try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pymupdf  # fallback for pdf
except ImportError:
    pymupdf = None

try:
    import docx
except ImportError:
    docx = None


def parse_excel(file_bytes: bytes, filename: str, max_rows: int = 50, max_chars: int = 2500) -> str:
    """Parses Excel (.xlsx, .xls) workbooks into readable markdown tables."""
    if not openpyxl:
        return f"[Excel file: {filename} (openpyxl library not installed)]"

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        sheets_output = []

        for sheet_name in wb.sheetnames[:3]:  # inspect up to first 3 sheets
            sheet = wb[sheet_name]
            rows_data = []
            row_count = 0

            for row in sheet.iter_rows(values_only=True):
                # Filter out completely empty rows
                if any(cell is not None and str(cell).strip() != "" for cell in row):
                    cleaned_cells = [str(c).strip() if c is not None else "" for c in row]
                    # Don't keep infinite trailing empty columns
                    while cleaned_cells and cleaned_cells[-1] == "":
                        cleaned_cells.pop()
                    if cleaned_cells:
                        rows_data.append(cleaned_cells)
                        row_count += 1
                        if row_count >= max_rows:
                            break

            if not rows_data:
                sheets_output.append(f"Sheet '{sheet_name}': (Empty)")
                continue

            # Format as clean markdown table
            headers = rows_data[0]
            header_line = "| " + " | ".join(headers) + " |"
            sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            data_lines = []
            for r in rows_data[1:]:
                # Pad row to match header length
                padded = r + [""] * (len(headers) - len(r))
                data_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")

            sheet_text = f"Sheet '{sheet_name}':\n{header_line}\n{sep_line}\n" + "\n".join(data_lines)
            if row_count >= max_rows:
                sheet_text += f"\n[... truncated after {max_rows} rows]"
            sheets_output.append(sheet_text)

        wb.close()
        full_text = "\n\n".join(sheets_output)
        return full_text[:max_chars] if len(full_text) > max_chars else full_text
    except Exception as e:
        return f"[Error reading Excel file {filename}: {str(e)}]"


def parse_csv(file_bytes: bytes, filename: str, max_rows: int = 50, max_chars: int = 2500) -> str:
    """Parses CSV text into a markdown table."""
    try:
        text = None
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                text = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return f"[Error reading CSV {filename}: unknown encoding]"

        reader = csv.reader(io.StringIO(text))
        rows = []
        for i, row in enumerate(reader):
            if any(cell.strip() for cell in row):
                rows.append([cell.strip() for cell in row])
            if i >= max_rows:
                break

        if not rows:
            return "(Empty CSV file)"

        headers = rows[0]
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_lines = []
        for r in rows[1:]:
            padded = r + [""] * (len(headers) - len(r))
            data_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")

        out = f"{header_line}\n{sep_line}\n" + "\n".join(data_lines)
        return out[:max_chars] if len(out) > max_chars else out
    except Exception as e:
        return f"[Error reading CSV file {filename}: {str(e)}]"


def parse_pdf(file_bytes: bytes, filename: str, max_pages: int = 5, max_chars: int = 2500) -> str:
    """Extracts text from PDF documents using pypdf or pymupdf."""
    # 1. Try pypdf first
    if pypdf:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for i in range(min(len(reader.pages), max_pages)):
                page = reader.pages[i]
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(f"--- Page {i+1} ---\n{txt.strip()}")
            out = "\n\n".join(pages_text) if pages_text else "(No extractable text found in PDF)"
            return out[:max_chars] if len(out) > max_chars else out
        except Exception as e:
            pass  # Fall through to pymupdf

    # 2. Try pymupdf if available
    if pymupdf:
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            pages_text = []
            for i in range(min(len(doc), max_pages)):
                page = doc[i]
                txt = page.get_text() or ""
                if txt.strip():
                    pages_text.append(f"--- Page {i+1} ---\n{txt.strip()}")
            doc.close()
            out = "\n\n".join(pages_text) if pages_text else "(No extractable text found in PDF)"
            return out[:max_chars] if len(out) > max_chars else out
        except Exception as e:
            return f"[Error reading PDF {filename}: {str(e)}]"

    return f"[PDF document: {filename} (pypdf/pymupdf parser unavailable)]"


def parse_docx(file_bytes: bytes, filename: str, max_chars: int = 2500) -> str:
    """Extracts paragraphs and tables from Word (.docx) documents."""
    if not docx:
        return f"[Word document: {filename} (python-docx parser unavailable)]"
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        
        tables_text = []
        for table in doc.tables[:3]:  # inspect up to 3 tables
            t_rows = []
            for row in table.rows[:20]:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    t_rows.append(" | ".join(cells))
            if t_rows:
                tables_text.append("Table:\n" + "\n".join(t_rows))

        combined = "\n\n".join(paragraphs + tables_text)
        out = combined if combined else "(Empty Word document)"
        return out[:max_chars] if len(out) > max_chars else out
    except Exception as e:
        return f"[Error reading Word document {filename}: {str(e)}]"


def parse_text(file_bytes: bytes, filename: str, max_chars: int = 2500) -> str:
    """Decodes plain text, Markdown, JSON, and source code files."""
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            content = file_bytes.decode(enc)
            return content[:max_chars] if len(content) > max_chars else content
        except UnicodeDecodeError:
            continue
    return f"[Attached text file: {filename} (Could not decode text)]"


def parse_attachment(filename: str, file_bytes: bytes, max_chars: int = 2500) -> str:
    """Universal attachment parser routing to the correct parser based on file extension."""
    if not file_bytes:
        return f"[Empty file: {filename}]"

    fn_lower = filename.lower()

    if fn_lower.endswith(('.xlsx', '.xls', '.xlsm')):
        return parse_excel(file_bytes, filename, max_chars=max_chars)
    elif fn_lower.endswith('.csv'):
        return parse_csv(file_bytes, filename, max_chars=max_chars)
    elif fn_lower.endswith('.pdf'):
        return parse_pdf(file_bytes, filename, max_chars=max_chars)
    elif fn_lower.endswith('.docx'):
        return parse_docx(file_bytes, filename, max_chars=max_chars)
    elif fn_lower.endswith(('.txt', '.md', '.json', '.log', '.py', '.js', '.ts', '.html', '.css', '.yaml', '.yml', '.xml')):
        return parse_text(file_bytes, filename, max_chars=max_chars)
    elif fn_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
        kb_size = round(len(file_bytes) / 1024, 1)
        return f"[Image attachment: {filename} ({kb_size} KB)]"
    else:
        kb_size = round(len(file_bytes) / 1024, 1)
        return f"[Attached file: {filename} ({kb_size} KB) - binary/unsupported text format]"


def extract_attachments_from_message(gmail_service, msg_id: str, payload: dict) -> List[Dict[str, Any]]:
    """
    Recursively scans the Gmail message payload MIME tree for attachments,
    fetches their binary data via Gmail API, and parses their contents.
    """
    attachments = []

    def _traverse_parts(parts):
        for part in parts:
            filename = part.get('filename')
            body = part.get('body', {})
            att_id = body.get('attachmentId')
            mime_type = part.get('mimeType', 'application/octet-stream')

            # An attachment is typically identified by having a filename and either an attachmentId or data
            if filename and filename.strip():
                file_bytes = None
                try:
                    if att_id and gmail_service:
                        att_res = gmail_service.users().messages().attachments().get(
                            userId='me',
                            messageId=msg_id,
                            id=att_id
                        ).execute()
                        raw_data = att_res.get('data', '')
                        if raw_data:
                            file_bytes = base64.urlsafe_b64decode(raw_data)
                    elif 'data' in body and body['data']:
                        file_bytes = base64.urlsafe_b64decode(body['data'])
                except Exception as ex:
                    print(f"Failed to fetch attachment '{filename}' for message {msg_id}: {ex}")

                parsed_content = ""
                if file_bytes:
                    parsed_content = parse_attachment(filename, file_bytes)
                else:
                    parsed_content = f"[Attachment metadata found for {filename}, but binary data could not be retrieved]"

                attachments.append({
                    "filename": filename,
                    "mime_type": mime_type,
                    "size": len(file_bytes) if file_bytes else body.get('size', 0),
                    "content": parsed_content
                })

            # Recurse into nested multipart branches
            if 'parts' in part:
                _traverse_parts(part['parts'])

    if 'parts' in payload:
        _traverse_parts(payload['parts'])

    return attachments


def format_attachments_for_llm(attachments: List[Dict[str, Any]]) -> str:
    """Formats a list of parsed attachments into structured text for LLM prompts."""
    if not attachments:
        return ""

    blocks = []
    blocks.append(f"\n--- ATTACHMENTS DETECTED & PARSED ({len(attachments)} file(s)) ---")
    for idx, att in enumerate(attachments, 1):
        fn = att.get('filename', 'Unknown')
        mime = att.get('mime_type', 'unknown')
        size_kb = round(att.get('size', 0) / 1024, 1)
        content = att.get('content', '').strip()
        blocks.append(f"[Attachment #{idx}: {fn} ({size_kb} KB, {mime})]")
        blocks.append("Content Preview / Data:")
        blocks.append(content)
        blocks.append("-" * 40)
    blocks.append("--- END OF ATTACHMENTS ---\n")


    return "\n".join(blocks)
