from __future__ import annotations
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .logging_config import setup_logging
from .types import ConvertRequest
from .convert import convert
from .parsers import bootstrap
from .parsers.registry import all_parsers

APP_TITLE = "PDF → XLSX Enterprise Converter"

def load_profiles(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main() -> None:
    setup_logging("INFO")
    bootstrap()
    suppliers = all_parsers()

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("720x360")

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)

    pdf_var = tk.StringVar()
    template_var = tk.StringVar()
    out_var = tk.StringVar()
    supplier_var = tk.StringVar(value=suppliers[0].supplier_key if suppliers else "generic")
    profiles_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "config", "supplier_profiles.json"))

    def browse_pdf():
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p: pdf_var.set(p)

    def browse_template():
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if p: template_var.set(p)

    def browse_out():
        p = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if p: out_var.set(p)

    def run_convert():
        pdf = pdf_var.get().strip()
        tpl = template_var.get().strip()
        out = out_var.get().strip()
        supplier = supplier_var.get().strip()

        if not (pdf and os.path.exists(pdf)):
            messagebox.showerror("Chyba", "Vyber platný PDF soubor.")
            return
        if not (tpl and os.path.exists(tpl)):
            messagebox.showerror("Chyba", "Vyber platnou XLSX šablonu.")
            return
        if not out:
            messagebox.showerror("Chyba", "Vyber cestu pro výstupní XLSX.")
            return

        profiles = load_profiles(profiles_path_var.get().strip())
        options = profiles.get(supplier, {}).get("options", {})

        try:
            req = ConvertRequest(pdf_path=pdf, template_xlsx_path=tpl, output_xlsx_path=out, supplier_key=supplier, options=options)
            res = convert(req)
        except Exception as e:
            messagebox.showerror("Chyba převodu", str(e))
            return

        msg = "Hotovo. Uloženo:\n" + out
        if res.warnings:
            msg += "\n\nVarování:\n" + "\n".join(res.warnings)
        messagebox.showinfo("OK", msg)

    # Layout
    row = 0
    ttk.Label(frm, text="PDF soubor:").grid(column=0, row=row, sticky="w")
    ttk.Entry(frm, textvariable=pdf_var, width=70).grid(column=1, row=row, sticky="we")
    ttk.Button(frm, text="Vybrat…", command=browse_pdf).grid(column=2, row=row, padx=6)

    row += 1
    ttk.Label(frm, text="XLSX šablona:").grid(column=0, row=row, sticky="w", pady=(8,0))
    ttk.Entry(frm, textvariable=template_var, width=70).grid(column=1, row=row, sticky="we", pady=(8,0))
    ttk.Button(frm, text="Vybrat…", command=browse_template).grid(column=2, row=row, padx=6, pady=(8,0))

    row += 1
    ttk.Label(frm, text="Výstup XLSX:").grid(column=0, row=row, sticky="w", pady=(8,0))
    ttk.Entry(frm, textvariable=out_var, width=70).grid(column=1, row=row, sticky="we", pady=(8,0))
    ttk.Button(frm, text="Uložit jako…", command=browse_out).grid(column=2, row=row, padx=6, pady=(8,0))

    row += 1
    ttk.Label(frm, text="Dodavatel / parser:").grid(column=0, row=row, sticky="w", pady=(12,0))
    combo = ttk.Combobox(frm, textvariable=supplier_var, values=[f"{p.supplier_key} — {p.display_name}" for p in suppliers], state="readonly")
    combo.grid(column=1, row=row, sticky="we", pady=(12,0))

    def on_combo(_):
        v = combo.get()
        key = v.split("—")[0].strip()
        supplier_var.set(key)

    combo.bind("<<ComboboxSelected>>", on_combo)
    # show nice label but keep var as key
    if suppliers:
        combo.set(f"{suppliers[0].supplier_key} — {suppliers[0].display_name}")

    row += 1
    ttk.Label(frm, text="Profiles config (JSON):").grid(column=0, row=row, sticky="w", pady=(8,0))
    ttk.Entry(frm, textvariable=profiles_path_var, width=70).grid(column=1, row=row, sticky="we", pady=(8,0))
    def browse_profiles():
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p: profiles_path_var.set(p)
    ttk.Button(frm, text="Vybrat…", command=browse_profiles).grid(column=2, row=row, padx=6, pady=(8,0))

    row += 1
    ttk.Separator(frm).grid(column=0, row=row, columnspan=3, sticky="we", pady=14)

    row += 1
    ttk.Button(frm, text="Převést", command=run_convert).grid(column=1, row=row, sticky="e")
    ttk.Button(frm, text="Konec", command=root.destroy).grid(column=2, row=row, sticky="e")

    frm.columnconfigure(1, weight=1)
    root.mainloop()

if __name__ == "__main__":
    main()
