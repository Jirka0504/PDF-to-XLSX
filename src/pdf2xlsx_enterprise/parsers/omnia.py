from __future__ import annotations

import re
from typing import Dict, Any, List

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws


def clean_number(s: str) -> str:
    s = re.sub(r"[^0-9,\.]", "", s)
    return s.replace(",", ".")


class OmniaParser(SupplierParser):
    """
    Omnia invoice layout: item rows look like:

      125709   LAMP COVER 40W - GORENJE 125709   100 PZ   1.15 €   115.00 €

    Special case (split code):
      VEN-
      9161.167   D.35.8 SHOWER   1 PZ   1.95 €   1.95 €

    We parse full rows (code+desc+qty+price+total) to avoid mixing headers into description.
    """
    supplier_key = "omnia"
    display_name = "Omnia (enterprise invoice)"

    _row_re = re.compile(
        r"^(?P<code>[A-Z0-9][A-Z0-9\-\./]{2,})\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>[\d.,]+)\s*€\s+"
        r"(?P<total>[\d.,]+)\s*€?\s*$"
    )
    _prefix_only = re.compile(r"^[A-Z]{2,8}-$")  # VEN-

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        return ("omniacomponents" in text) or ("26vin" in text) or ("invoice" in text)

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
        lines: List[str] = []
        for page in pdf_text_pages:
            for l in (page or "").splitlines():
                l = normalize_ws(l)
                if l:
                    lines.append(l)

        items: List[LineItem] = []
        warnings: List[str] = []

        pending_prefix: str | None = None
        buffer = ""

        for line in lines:
            # handle prefix-only line like "VEN-"
            if self._prefix_only.fullmatch(line):
                pending_prefix = line
                buffer = ""
                continue

            # build a buffer to support descriptions wrapped across lines
            buffer = (buffer + " " + line).strip() if buffer else line

            m = self._row_re.match(buffer)
            if not m:
                # prevent runaway buffer in weird PDFs
                if len(buffer) > 500:
                    buffer = ""
                continue

            code = m.group("code").strip()
            desc = m.group("desc").strip()
            qty = clean_number(m.group("qty"))
            price = clean_number(m.group("price"))
            total = clean_number(m.group("total"))

            if pending_prefix:
                code = pending_prefix + code
                pending_prefix = None

            items.append(
                LineItem(
                    product_number=code,
                    product_name=desc,
                    delivered_qty=qty,       # "Množství" -> číslo
                    net_unit_price=price,    # "Cena za jednotku" -> číslo
                    total_price=total,       # "Cena celkem" -> číslo
                    customs_code="",
                    weight_g="",
                )
            )

            buffer = ""

        if not items:
            warnings.append(
                "OmniaParser: Nenalezeny položky. Ověř, že řádky obsahují 'PZ' a ceny s € ve formátu '... PZ 1.15 € 115.00 €'."
            )

        return ParseResult(header={"supplier": "omnia"}, items=items, warnings=warnings)


def create() -> OmniaParser:
    return OmniaParser()
