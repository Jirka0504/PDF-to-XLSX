import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import pdfplumber
from openpyxl import Workbook


APP_TITLE = "OMNIA PDF → XLSX převodník"


HEADERS = [
    "Interní kód zboží",
    "Název",
    "Množství",
    "Cena celkem",
    "Zkrácená poznámka",
    "Kód kombinované nomenklatury",
    "Země původu",
    "Hmotnost",
]


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("￾", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_number(value: str) -> float:
    value = value.replace("€", "").replace("EUR", "").strip()
    value = value.replace(",", ".")
    return float(value)


def looks_like_code_only(line: str) -> bool:
    """
    Samostatný kód na řádku, např.:
    VEN149198350
    nebo
    SS-193757
    """
    line = normalize_text(line)
    if " PZ " in line:
        return False
    return bool(re.fullmatch(r"[A-Z0-9\-.]{4,}", line))


def parse_pdf(pdf_path: str):
    lines = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = normalize_text(line)
                if line:
                    lines.append(line)

    items = []
    warnings = []

    pending_code = None

    full_row_re = re.compile(
        r"""
        ^
        (?P<code>[A-Z0-9\-.]+)\s+
        (?P<name>.+?)\s+
        (?P<qty>\d+)\s+PZ\s+
        (?P<price>\d+(?:[.,]\d{2}))\s+€\s+
        (?P<total>\d+(?:[.,]\d{2}))\s+€
        $
        """,
        re.VERBOSE,
    )

    cont_row_re = re.compile(
        r"""
        ^
        (?P<name>.+?)\s+
        (?P<qty>\d+)\s+PZ\s+
        (?P<price>\d+(?:[.,]\d{2}))\s+€\s+
        (?P<total>\d+(?:[.,]\d{2}))\s+€
        $
        """,
        re.VERBOSE,
    )

    skip_prefixes = (
        "Consegnare a:",
        "Spettabile:",
        "Vat code:",
        "TOTALE MERCE",
        "SCONTO %",
        "SPESE INCASSO",
        "TOTALE IMPONIBILE",
        "TOTALE IMPOSTA",
        "IMPONIBILE",
        "ALIQUOTA IVA",
        "TOTALE DOCUMENTO",
        "OMAGGI",
        "TOTALE DA PAGARE",
        "FATTURA",
        "OMNIA COMPONENTS",
        "Via Travnik",
        "Tel.",
        "C.F. E P.IVA",
        "Capitale Sociale",
        "N.Documento",
        "Data spedizione richiesta:",
        "http://www.omniacomponents.com",
        "PRODUCT CODE DESCRIPTION QUANTITY PREZZO SCONTO % IMPORTO TOTALE",
        "Spese di Trasporto UE Vendita - Shipping Fees",
    )

    for raw_line in lines:
        line = normalize_text(raw_line)

        if any(line.startswith(prefix) for prefix in skip_prefixes):
            continue

        if line.startswith("KTS - AME") or line.startswith("Karla Čapka") or line.startswith("500 02"):
            continue

        # 1) Normální kompletní řádek
        m = full_row_re.match(line)
        if m:
            code = m.group("code").strip()
            name = m.group("name").strip()
            qty = int(m.group("qty"))
            total = clean_number(m.group("total"))

            items.append({
                "code": code,
                "name": name,
                "qty": qty,
                "total": total,
            })
            pending_code = None
            continue

        # 2) Samostatný kód na řádku – další řádek je pokračování
        if looks_like_code_only(line):
            pending_code = line
            continue

        # 3) Pokračovací řádek bez kódu
        m2 = cont_row_re.match(line)
        if m2 and pending_code:
            code = pending_code.strip()
            name = m2.group("name").strip()
            qty = int(m2.group("qty"))
            total = clean_number(m2.group("total"))

            items.append({
                "code": code,
                "name": name,
                "qty": qty,
                "total": total,
            })
            pending_code = None
            continue

        # 4) Ostatní ignoruj, ale jen pokud to nevypadá jako důležitý rozbitý řádek
        if " PZ " in line or pending_code:
            warnings.append(f"Nepodařilo se naparsovat řádek: {line}")

    return items, warnings


def save_xlsx(output_path: str, items: list[dict]):
    wb = Workbook()
    ws = wb.active
    ws.title = "List1"

    # hlavička
    for col_idx, header in enumerate(HEADERS, start=1):
        ws.cell(row=1, column=col_idx, value=header)

    # data
    row = 2
    for item in items:
        ws.cell(row=row, column=1, value=item["code"])
        ws.cell(row=row, column=2, value=item["name"])
        ws.cell(row=row, column=3, value=item["qty"])
        ws.cell(row=row, column=4, value=item["total"])
        ws.cell(row=row, column=5, value=None)
        ws.cell(row=row, column=6, value=None)
        ws.cell(row=row, column=7, value=None)
        ws.cell(row=row, column=8, value=None)
        row += 1

    wb.save(output_path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x560")

        self.pdf_path = tk.StringVar()
        self.output_path = tk.StringVar()

        self.preview_text = None

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Vstupní PDF:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.pdf_path, width=90).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(frm, text="Vybrat…", command=self.pick_pdf).grid(row=0, column=2, padx=6)

        ttk.Label(frm, text="Výstupní XLSX:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.output_path, width=90).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(frm, text="Uložit jako…", command=self.pick_output).grid(row=1, column=2, padx=6)

        ttk.Separator(frm, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)

        note = (
            "Poznámka: Pokud je kód zboží rozdělený do dvou řádků, aplikace vezme samostatný kód\n"
            "z jednoho řádku a spojí ho s následujícím řádkem s názvem, množstvím a cenou."
        )
        ttk.Label(frm, text=note, foreground="#555").grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.preview_text = tk.Text(frm, height=18, wrap="none")
        self.preview_text.grid(row=4, column=0, columnspan=3, sticky="nsew")

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="e", pady=12)
        ttk.Button(btns, text="Náhled", command=self.preview).pack(side="left", padx=4)
        ttk.Button(btns, text="Převést", command=self.convert).pack(side="left", padx=4)
        ttk.Button(btns, text="Konec", command=self.destroy).pack(side="left", padx=4)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(4, weight=1)

    def pick_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.pdf_path.set(path)
            if not self.output_path.get().strip():
                self.output_path.set(str(Path(path).with_suffix(".xlsx")))

    def pick_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if path:
            self.output_path.set(path)

    def preview(self):
        pdf = self.pdf_path.get().strip()
        if not pdf:
            messagebox.showerror("Chyba", "Vyber vstupní PDF.")
            return

        try:
            items, warnings = parse_pdf(pdf)
        except Exception as e:
            messagebox.showerror("Chyba", str(e))
            return

        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", f"Nalezeno položek: {len(items)}\n\n")

        for item in items[:30]:
            self.preview_text.insert(
                "end",
                f"{item['code']} | {item['name']} | qty={item['qty']} | total={item['total']}\n"
            )

        if warnings:
            self.preview_text.insert("end", "\n--- VAROVÁNÍ ---\n")
            for w in warnings[:20]:
                self.preview_text.insert("end", w + "\n")

    def convert(self):
        pdf = self.pdf_path.get().strip()
        out = self.output_path.get().strip()

        if not pdf:
            messagebox.showerror("Chyba", "Vyber vstupní PDF.")
            return
        if not out:
            messagebox.showerror("Chyba", "Vyber výstupní XLSX.")
            return

        try:
            items, warnings = parse_pdf(pdf)
            save_xlsx(out, items)
        except Exception as e:
            messagebox.showerror("Chyba", str(e))
            return

        msg = f"Hotovo.\nUloženo do:\n{out}\n\nPočet položek: {len(items)}"
        if warnings:
            msg += f"\n\nVarování: {len(warnings)}"
        messagebox.showinfo("Hotovo", msg)


if __name__ == "__main__":
    App().mainloop()
