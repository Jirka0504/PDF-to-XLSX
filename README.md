# PDF → XLSX Enterprise (multi-supplier)

Cíl: jeden repozitář, více dodavatelů (parser pluginy), jednotná šablona XLSX.

## Instalace
```bash
pip install -e .
```

## GUI
```bash
pdf2xlsx-gui
```

## CLI
```bash
pdf2xlsx --pdf ./in.pdf --template ./template.xlsx --out ./out.xlsx --supplier omnia
```

## Jak přidat nového dodavatele
1. Vytvoř parser `src/pdf2xlsx_enterprise/parsers/<dodavatel>.py` (dědí `SupplierParser`).
2. Zaregistruj ho v `src/pdf2xlsx_enterprise/parsers/__init__.py` v `bootstrap()`.
3. Přidej profil do `config/supplier_profiles.json` (volitelně mapování/sloupce, sheet name, apod).
4. Přidej testy do `tests/`.

## Profily (config/supplier_profiles.json)
- `sheet_name`: list ve šabloně, default první.
- `clear_existing`: vyčistí stará data pod hlavičkou.
- `mapping`: mapování "název sloupce ve šabloně" → "atribut LineItem".

### Default atributy LineItem
- product_number, product_name, customs_code, weight_g, delivered_qty, net_unit_price, total_price

## GitHub Actions
- CI testy na Ubuntu
- Build `.exe` na Windows a upload jako artifact (Actions → Artifacts)

