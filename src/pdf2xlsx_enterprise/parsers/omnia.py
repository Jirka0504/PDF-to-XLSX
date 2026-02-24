from __future__ import annotations
import re
from typing import Dict, Any
from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws, money_to_str

class OmniaParser(SupplierParser):
    supplier_key = "omnia"
    display_name = "Omnia (sample invoice layout)"

    def can_parse(self, pdf_text_pages: list[str], tables: list[list[list[str]]]) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        # Heuristic signatures - adjust to your real supplier patterns:
        return ("omnia" in text) or ("vin" in text and "invoice" in text)

    def parse(self, pdf_text_pages: list[str], tables: list[list[list[str]]], options: Dict[str, Any]) -> ParseResult:
        full = "\n".join(pdf_text_pages)
        warnings: list[str] = []
        items: list[LineItem] = []

        # Prefer tables if any; otherwise regex fallback
        if tables:
            # very defensive: look for rows that resemble line items
            for t in tables:
                for row in t:
                    if not row:
                        continue
                    cells = [normalize_ws(c or "") for c in row]
                    joined = " | ".join(cells)
                    # Heuristic: product number tends to be alnum like HTR012SA or DC47-00033A
                    cand = next((c for c in cells if re.fullmatch(r"[A-Z0-9\-]{5,}", c)), "")
                    if not cand:
                        continue

                    # Try map: [code, description, qty, unit, price, total] (varies)
                    # We'll pick best-effort fields:
                    product_number = cand
                    # product name: longest cell that's not numeric-ish
                    name = max((c for c in cells if len(c) > 6 and not re.fullmatch(r"[0-9.,]+", c)), key=len, default="")
                    qty = next((c for c in cells if re.fullmatch(r"[0-9]+", c)), "")
                    # prices: find two money-like
                    money = [c for c in cells if re.fullmatch(r"[0-9]+[.,][0-9]{2}", c)]
                    net = money_to_str(money[0]) if len(money) >= 1 else ""
                    total = money_to_str(money[1]) if len(money) >= 2 else ""

                    items.append(LineItem(
                        product_number=product_number,
                        product_name=name,
                        customs_code="",
                        weight_g="",
                        delivered_qty=qty,
                        net_unit_price=net,
                        total_price=total,
                    ))

        if not items:
            # Regex fallback: looks for patterns like CODE, DESCRIPTION, QTY, PRICE, TOTAL on same/next lines
            # This is only a starter; for each supplier you will tune.
            lines = [normalize_ws(l) for l in full.splitlines() if normalize_ws(l)]
            pat = re.compile(r"^(?P<code>[A-Z0-9\-]{5,})\s+(?P<desc>.+?)\s+(?P<qty>[0-9]+)\s+(?P<unit>[0-9]+[.,][0-9]{2})\s+(?P<tot>[0-9]+[.,][0-9]{2})$")
            for l in lines:
                m = pat.match(l)
                if m:
                    items.append(LineItem(
                        product_number=m.group("code"),
                        product_name=m.group("desc"),
                        delivered_qty=m.group("qty"),
                        net_unit_price=money_to_str(m.group("unit")),
                        total_price=money_to_str(m.group("tot")),
                    ))

        if not items:
            warnings.append("No line items detected by OmniaParser. Tune the parser for this supplier layout.")

        header = {
            "source": "omnia",
        }
        return ParseResult(header=header, items=items, warnings=warnings)

def create() -> OmniaParser:
    return OmniaParser()
