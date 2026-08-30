#!/usr/bin/env python3
"""Печатает заголовки и характерные строки исходных рабочих книг."""

from __future__ import annotations

import json
from pathlib import Path


data = json.loads(Path("analysis/xlsx-inventory.json").read_text(encoding="utf-8"))
for book in data["workbooks"]:
    if book["fileName"].startswith("Расчет"):
        continue
    sheet = book["sheets"][0]
    print("\n###", book["fileName"], sheet["dimension"])
    for item in sheet["nonFormulaValueSamples"]:
        print(item)
