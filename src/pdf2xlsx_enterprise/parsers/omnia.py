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
    supplier_key = "omnia"
    display_name = "Omnia (enterprise layout)"

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        return "omniacomponents" in text or "26vin" in text

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
        lines = []

        for page in pdf_text_pages:
            for l in (page or "").splitlines():
                l = normalize_ws(l)
                if l:
                    lines.append(l)

        items: List[LineItem] = []
        warnings: List[str] = []

        pending_prefix = None
        pending_code = None
        pending_desc = None

        for line in lines:

            # VEN-
            if re.fullmatch(r"[A-Z]{2,6}-", line):
                pending_prefix = line
                continue

            # 161.167
            if pending_prefix and re.fullmatch(r"\d+(?:\.\d+)+", line):
                pending_code = pending_prefix + line
                pending_prefix = None
                continue

            # popis (D.35.8 SHOWER)
            if pending_code and not re.search(r"\bPZ\b", line):
                pending_desc = line
                continue

            # čísla (5 PZ 2.45 € 12.25 €)
            m = re.search(r"(\d+)\s+PZ\s+([\d.,]+)\s*€\s+([\d.,]+)", line)
            if m and pending_code and pending_desc:
                qty = clean_number(m.group(1))
                price = clean_number(m.group(2))
                total = clean_number(m.group(3))

                item = LineItem(
                    product_number=pending_code,
                    product_name=pending_desc,
                    delivered_qty=qty,
                    net_unit_price=price,
                    total_price=total,
                    customs_code="",
                    weight_g=""
                )

                items.append(item)

                pending_code = None
                pending_desc = None

        if not items:
            warnings.append("Nenalezeny žádné položky.")

        return ParseResult(
            header={"supplier": "omnia"},
            items=items,
            warnings=warnings
        )


def create() -> OmniaParser:
    return OmniaParser()
