from __future__ import annotations
import re
from typing import Dict, Any, List

from .base import SupplierParser
from ..types import ParseResult, LineItem
from ..utils import normalize_ws


def clean_number(s: str) -> str:
    s = re.sub(r"[^0-9,\.]", "", s)
    return s.replace(",", ".")


CODE_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9\-\./]{2,}$")   # dovolí i tečky (161.167) a pomlčky
PREFIX_ONLY = re.compile(r"^[A-Z]{2,8}-$")                # VEN-
SUFFIX_DOTS = re.compile(r"^\d+(?:\.\d+)+$")              # 161.167
NUMS_LINE = re.compile(r"(\d+)\s+PZ\s+([\d.,]+)\s*€\s+([\d.,]+)\s*€")


class OmniaParser(SupplierParser):
    supplier_key = "omnia"
    display_name = "Omnia (enterprise robust)"

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

        for i, line in enumerate(lines):
            m = NUMS_LINE.search(line)
            if not m:
                continue

            qty = clean_number(m.group(1))
            price = clean_number(m.group(2))
            total = clean_number(m.group(3))

            # --- najdi kód + popis v řádcích NAD tím ---
            code = ""
            desc = ""

            # vezmi okno max 4 řádky zpět
            window = lines[max(0, i - 4): i]

            # 1) speciálně: VEN- + 161.167
            for w_idx in range(len(window) - 1):
                a = window[w_idx]
                b = window[w_idx + 1]
                if PREFIX_ONLY.fullmatch(a) and SUFFIX_DOTS.fullmatch(b):
                    code = a + b
                    # popis bude ideálně hned po tom (pokud existuje), jinak poslední řádek okna
                    if w_idx + 2 < len(window):
                        desc = window[w_idx + 2]
                    else:
                        desc = window[-1] if window else ""
                    break

            # 2) běžně: kód je první token na řádku (nebo samostatný řádek)
            if not code:
                # jdeme odzadu: nejblíž k číslům bývá popis
                for back in range(1, min(4, i) + 1):
                    cand = lines[i - back]
                    parts = cand.split()

                    if not parts:
                        continue

                    # samostatný kód
                    if CODE_TOKEN.fullmatch(parts[0]) and len(parts) == 1:
                        code = parts[0]
                        # popis bude řádek pod tím (blíž k číslům), pokud existuje
                        if i - back + 1 < i:
                            desc = lines[i - back + 1]
                        break

                    # kód + popis na jednom řádku
                    if CODE_TOKEN.fullmatch(parts[0]) and len(parts) > 1:
                        code = parts[0]
                        desc = " ".join(parts[1:])
                        break

            # 3) fallback: když nemáme popis, vezmi řádek těsně nad čísly
            if not desc and i - 1 >= 0:
                desc = lines[i - 1]

            # pokud se ani tak nepodaří kód, přeskoč (nechceme plnit nesmysly)
            if not code:
                continue

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

        if not items:
            warnings.append("OmniaParser: Nenalezeny žádné položky (zkontroluj, že řádky obsahují 'PZ' a ceny s €).")

        return ParseResult(
            header={"supplier": "omnia"},
            items=items,
            warnings=warnings
        )


def create() -> OmniaParser:
    return OmniaParser()
