from __future__ import annotations

import re
from typing import Dict, Any, List, Optional

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws


# Matches a COMPLETE invoice line that ends with: "<qty> PZ <price> € <total> €"
# Example:
# 125709 LAMP COVER 40W - GORENJE 125709 100 PZ 1.15 € 115.00 €
ROW_RE = re.compile(
    r"^(?P<code>[A-Z0-9][A-Z0-9\-.]*)\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<qty>\d+(?:[.,]\d+)?)\s+PZ\s+"
    r"(?P<price>\d+(?:[.,]\d+)?)\s*€\s+"
    r"(?P<total>\d+(?:[.,]\d+)?)\s*€\s*$"
)

# Matches split code lines like:
# "SS 2230002839"   (desc on next line)
# "VEN 149198350"   (desc on next line)
SPLIT_CODE_RE = re.compile(r"^(SS|VEN)\s+([0-9][0-9\-.]*)\s*$", re.IGNORECASE)

# Matches a "code-only-ish" line that likely needs continuation
CODE_ONLY_HINT_RE = re.compile(r"^(SS|VEN)\b", re.IGNORECASE)


def _to_number_str(s: str) -> str:
    """
    Keep only a normalized numeric string:
    - removes spaces and €
    - converts comma to dot
    """
    s = (s or "").strip()
    s = s.replace("€", "").replace(" ", "")
    s = s.replace(",", ".")
    # Keep digits and single dot
    s = re.sub(r"[^0-9.]", "", s)
    # If multiple dots, keep first as decimal separator, remove others
    if s.count(".") > 1:
        first, *rest = s.split(".")
        s = first + "." + "".join(rest)
    return s


def _clean_line(line: str) -> str:
    line = line or ""
    # Normalize whitespace
    line = normalize_ws(line)
    # Replace common PDF odd spaces
    line = line.replace("\u00A0", " ").replace("\uf0be", " ").replace("\uf0a7", " ")
    line = normalize_ws(line)
    return line.strip()


def _is_header_or_total(line: str) -> bool:
    l = (line or "").strip().lower()
    if not l:
        return True
    # Skip headers / footers / totals
    if l.startswith("product code description quantity"):
        return True
    if l.startswith("totale"):
        return True
    if l.startswith("totale da pagare"):
        return True
    if l.startswith("spese"):
        return True
    if l.startswith("fattura"):
        return True
    if "omniacomponents" in l:
        return True
    return False


class OmniaParser(SupplierParser):
    supplier_key = "omnia"
    display_name = "Omnia (enterprise invoice layout)"

    def can_parse(self, pdf_text_pages: List[str], tables: Any) -> bool:
        text = "\n".join(pdf_text_pages).lower()
        # Omnia PDFs contain these markers (invoice number 26VIN..., company name)
        return ("omnia components" in text) or ("26vin" in text)

    def parse(
        self,
        pdf_text_pages: List[str],
        tables: Any,
        options: Dict[str, Any],
    ) -> ParseResult:
        warnings: List[str] = []
        items: List[LineItem] = []

        # Flatten PDF text into cleaned lines
        raw_lines: List[str] = []
        for page in pdf_text_pages:
            for ln in (page or "").splitlines():
                ln = _clean_line(ln)
                if not ln:
                    continue
                if _is_header_or_total(ln):
                    continue
                raw_lines.append(ln)

        # Build "logical rows" by buffering until ROW_RE matches
        buf: str = ""
        pending_code_prefix: Optional[str] = None  # For cases like "SS 2230002839" alone

        def try_emit(candidate: str) -> bool:
            m = ROW_RE.match(candidate)
            if not m:
                return False

            code = m.group("code").strip()
            desc = m.group("desc").strip()
            qty = _to_number_str(m.group("qty"))
            price = _to_number_str(m.group("price"))
            total = _to_number_str(m.group("total"))

            # basic numeric sanity
            if not qty or not price or not total:
                warnings.append(f"Skipping row (bad numbers): {candidate}")
                return True  # consumed

            # Unit is always PZ in this invoice
            unit = "PZ"

            # Produce a minimal, stable LineItem dict (writer/mapping can map keys to XLSX columns)
            items.append(
                {
                    "supplier_product_code": code,  # "Kód zboží dodavatele"
                    "product_code": code,           # "Kód zboží" (often same for you)
                    "name": desc,                   # "Název zboží"
                    "mj": unit,                     # "MJ"
                    "quantity": qty,                # "Množství"
                    "unit_price": price,            # "Cena za jednotku"
                    "total_price": total,           # "Cena celkem"
                }
            )
            return True

        for ln in raw_lines:
            # If we have a split-code line like "SS 2230002839"
            m_split = SPLIT_CODE_RE.match(ln)
            if m_split:
                prefix = m_split.group(1).upper()
                num = m_split.group(2)
                pending_code_prefix = f"{prefix}-{num}"
                buf = pending_code_prefix  # start buffer with the fixed code
                continue

            # If line starts with "SS-" / "VEN-" like "SS￾223..." or "VEN￾149..."
            # normalize weird separators into dash if it looks like "SS 223..." merged
            ln_norm = ln
            ln_norm = re.sub(r"^(SS|VEN)\s+([0-9])", r"\1-\2", ln_norm, flags=re.IGNORECASE)

            # If buffer empty, start it
            if not buf:
                buf = ln_norm
            else:
                # Append continuation with a space
                buf = f"{buf} {ln_norm}"

            buf = _clean_line(buf)

            # Try emit; if not match, keep buffering
            if try_emit(buf):
                buf = ""
                pending_code_prefix = None
                continue

            # Some PDFs create short lines like "SS-POIGNEE" (bad OCR join).
            # If buffer grows too long without matching, reset defensively.
            if len(buf) > 500:
                warnings.append(f"Buffer too long, reset: {buf[:120]}...")
                buf = ""
                pending_code_prefix = None

        # Try last buffer
        if buf and not try_emit(buf):
            # If last buffer looks like code-only, ignore quietly; else warn
            if not CODE_ONLY_HINT_RE.match(buf):
                warnings.append(f"Unparsed tail: {buf}")

        return {"items": items, "warnings": warnings}
