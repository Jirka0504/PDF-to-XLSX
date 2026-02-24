from __future__ import annotations
import pdfplumber
from typing import List, Dict, Any, Optional
import logging

log = logging.getLogger(__name__)

def extract_text_by_page(pdf_path: str) -> List[str]:
    pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text() or ""
            pages.append(txt)
            log.debug("Extracted text from page %s (%s chars)", i + 1, len(txt))
    return pages

def extract_tables(pdf_path: str) -> List[List[List[str]]]:
    # Returns list of tables per page (flattened)
    tables: List[List[List[str]]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables() or []:
                tables.append(t)
    return tables
