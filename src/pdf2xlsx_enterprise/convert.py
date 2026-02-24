from __future__ import annotations
from typing import Dict, Any
import logging
from .pdf_reader import extract_text_by_page, extract_tables
from .parsers.registry import get as get_parser
from .xlsx_writer import write_items_to_template
from .types import ConvertRequest, ParseResult

log = logging.getLogger(__name__)

def convert(req: ConvertRequest) -> ParseResult:
    text_pages = extract_text_by_page(req.pdf_path)
    tables = extract_tables(req.pdf_path)

    parser = get_parser(req.supplier_key)
    log.info("Using parser: %s (%s)", parser.display_name, parser.supplier_key)

    if not parser.can_parse(text_pages, tables):
        log.warning("Parser '%s' heuristics say it may not match this PDF. Continuing anyway.", req.supplier_key)

    result = parser.parse(text_pages, tables, req.options or {})
    write_items_to_template(req.template_xlsx_path, req.output_xlsx_path, result.items, req.options or {})
    return result
