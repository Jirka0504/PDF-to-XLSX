from __future__ import annotations

import re
from typing import Dict, Any, List

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws


def clean_number(s: str) -> str:
    """
    Normalize numeric strings to "1234.56" (dot decimal) and strip non-numeric chars.
    """
    s = (s or "").strip()
    s = re.sub(r"[^0-9,\.]", "", s)
    # If comma is decimal separator, normalize to dot
    # (most Omnia PDFs use dot, but be defensive)
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    # If both separators exist, assume comma is thousands separator -> remove commas
    if s.count(".") >= 1 and s.count(",") >= 1:
        s = s.replace(",", "")
    return s


class OmniaParser(SupplierParser):
    """
    Omnia invoice layout.

    We MUST NOT naive-concatenate arbitrary lines, because PDF text often contains a header like:
      "PRODUCT CODE DESCRIPTION QUANTITY PREZZO ..."

    Real items can appear as:
      A) Full single line:
         125709  LAMP COVER 40W - GORENJE 125709  100 PZ  1.15 €  115.00 €
      B) Split across 2 lines:
         125709  LAMP COVER 40W - GORENJE 125709
         100 PZ  1.15 €  115.00 €
      C) Special split code:
         VEN-
         9161.167  D.35.8 SHOWER
         1 PZ  1.95 €  1.95 €
    """

    supplier_key = "omnia"
    display_name = "Omnia (enterprise invoice)"

    # Full row pattern: CODE + DESC + QTY PZ + PRICE € + TOTAL €
    _row_full_re = re.compile(
        r"^(?P<code>[A-Z0-9][A-Z0-9\-\./]{2,})\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>[\d.,]+)\s*€\s+"
        r"(?P<total>[\d.,]+)\s*€?\s*$"
    )

    # Second line pattern (for 2-line items): "100 PZ 1.15 € 115.00 €"
    _qty_line_re = re.compile(
        r"^(?P<qty>\d+)\s+PZ\s+"
        r"(?P<price>[\d.,]+)\s*€\s+"
        r"(?P<total>[\d.,]+)\s*€?\s*$"
    )

    # Prefix-only line (e.g., "VEN-")
    _prefix_only_re = re.compile(r"^[A-Z]{2,8}-$")

    # First token must look like a product code
    _code_token_re = re.compile(r"^[A-Z0-9][A-Z0-9\-\./]{2,}$")

    def can_parse(self, pdf_text_pages: List[str], tables: list) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        return ("omniacomponents" in text) or ("26vin" in text) or ("invoice" in text)

    @staticmethod
    def _is_header_line(s: str) -> bool:
        """
        Detects header lines like:
          PRODUCT CODE DESCRIPTION QUANTITY PREZZO ...
        We skip them completely to prevent mixing into item descriptions.
        """
        lo = (s or "").lower()
        header_words = ("product", "code", "description", "quantity", "prezzo", "sconto", "importo", "totale")
        hits = sum(1 for w in header_words if w in lo)
        return hits >= 3

    def parse(self, pdf_text_pages: List[str], tables: list, options: Dict[str, Any]) -> ParseResult:
        # Flatten and normalize text lines from PDF
        lines: List[str] = []
        for page in pdf_text_pages:
            for l in (page or "").splitlines():
                l = normalize_ws(l)
                if l:
                    lines.append(l)

        items: List[LineItem] = []
        warnings: List[str] = []

        pending_prefix: str | None = None  # e.g. "VEN-"
        pending_code: str | None = None
        pending_desc: str | None = None

        for line in lines:
            # 0) Skip table headers
            if self._is_header_line(line):
                continue

            # 1) Prefix-only line like "VEN-"
            if self._prefix_only_re.fullmatch(line):
                pending_prefix = line
                # reset pending code/desc; the next code will be prefixed
                pending_code = None
                pending_desc = None
                continue

            # 2) Try full one-line item parse (no buffering!)
            m = self._row_full_re.match(line)
            if m:
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
                        delivered_qty=qty,
                        net_unit_price=price,
                        total_price=total,
                        customs_code="",
                        weight_g="",
                    )
                )
                pending_code = None
                pending_desc = None
                continue

            # 3) If this line is "qty PZ price € total €", attach to previously seen code/desc
            q = self._qty_line_re.match(line)
            if q and pending_code and pending_desc:
                code = pending_code
                desc = pending_desc
                qty = clean_number(q.group("qty"))
                price = clean_number(q.group("price"))
                total = clean_number(q.group("total"))

                items.append(
                    LineItem(
                        product_number=code,
                        product_name=desc,
                        delivered_qty=qty,
                        net_unit_price=price,
                        total_price=total,
                        customs_code="",
                        weight_g="",
                    )
                )
                pending_code = None
                pending_desc = None
                continue

            # 4) Otherwise: could be "CODE + DESCRIPTION..." (first line of a 2-line item)
            parts = line.split(" ", 1)
            if len(parts) == 2 and self._code_token_re.fullmatch(parts[0]):
                pending_code = parts[0].strip()
                pending_desc = parts[1].strip()

                if pending_prefix:
                    pending_code = pending_prefix + pending_code
                    pending_prefix = None

                continue

            # 5) Or continuation of description (still waiting for qty/price line)
            if pending_code and pending_desc:
                # Avoid appending if it's clearly not part of description
                if not self._is_header_line(line):
                    pending_desc = (pending_desc + " " + line).strip()
                continue

            # else ignore unrelated lines

        if not items:
            warnings.append(
                "OmniaParser: Nenalezeny položky. Ověř, že PDF obsahuje řádky s 'PZ' a cenami s €."
            )

        return ParseResult(header={"supplier": "omnia"}, items=items, warnings=warnings)


def create() -> OmniaParser:
    return OmniaParser()
