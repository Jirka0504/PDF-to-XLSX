from __future__ import annotations
from typing import Dict, Any
from .base import SupplierParser
from ..types import ParseResult

class GenericParser(SupplierParser):
    supplier_key = "generic"
    display_name = "Generic (no-op / diagnostics)"

    def can_parse(self, pdf_text_pages: list[str], tables: list[list[list[str]]]) -> bool:
        return True

    def parse(self, pdf_text_pages: list[str], tables: list[list[list[str]]], options: Dict[str, Any]) -> ParseResult:
        # Produces empty output but helps you inspect what was extracted (see logs).
        return ParseResult(header={"source": "generic"}, items=[], warnings=["Generic parser selected. No extraction performed."])

def create() -> GenericParser:
    return GenericParser()
