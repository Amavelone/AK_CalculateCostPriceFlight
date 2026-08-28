#!/usr/bin/env python3
"""Print detailed, review-friendly information for the primary workbook."""

from __future__ import annotations

import json
import sys
from pathlib import Path


data = json.loads(Path("analysis/xlsx-inventory.json").read_text(encoding="utf-8"))
book = next(book for book in data["workbooks"] if book["fileName"].startswith("Расчет"))
requested_sheet = sys.argv[1] if len(sys.argv) > 1 else ""

print("DEFINED NAMES")
for item in book["definedNames"]:
    print(item)

print("\nSHEETS")
for sheet in book["sheets"]:
    if requested_sheet and sheet["name"] != requested_sheet:
        continue
    print("\n###", sheet["name"], sheet["dimension"], "formulas", sheet["formulaCount"])
    print("tables:")
    for table in sheet["tables"]:
        print(" ", table)
    print("validations:")
    for validation in sheet["dataValidations"]:
        print(" ", validation)
    print("conditional formats:", sheet["conditionalFormats"])
    print("cached formula errors:", sheet["cachedFormulaErrors"])
    for error in sheet["cachedFormulaErrorSamples"]:
        print(" ", error)
    print("value samples:")
    for value in sheet["nonFormulaValueSamples"]:
        print(" ", value)
    print("formula patterns:")
    for formula in sheet["formulaPatterns"][:20]:
        print(" ", formula)
    print("formula samples:")
    for formula in sheet["formulaSamples"][:12]:
        print(" ", formula)
