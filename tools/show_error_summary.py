#!/usr/bin/env python3
"""Печатает перечень сохранённых ошибок формул в книге монитора."""

from __future__ import annotations

import json
from pathlib import Path


data = json.loads(Path("analysis/xlsx-inventory.json").read_text(encoding="utf-8"))
book = next(book for book in data["workbooks"] if book["fileName"].startswith("Расчет"))
for sheet in book["sheets"]:
    if sheet["cachedFormulaErrors"]:
        print(sheet["name"], sheet["cachedFormulaErrors"])
        for item in sheet["cachedFormulaErrorSamples"]:
            print(" ", item)
