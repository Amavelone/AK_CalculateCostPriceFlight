#!/usr/bin/env python3
"""Анализирует дубликаты ключей таблицы тарифов для ВПР без изменения книги."""

from __future__ import annotations

import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from inventory_xlsx import NS, read_xml, shared_strings, text_value


INPUT = Path(r"C:\Users\soale\Downloads\Расчет себестоимости рейсов (1).xlsx")


def cells_by_row(archive: zipfile.ZipFile, part: str):
    root = read_xml(archive, part)
    shared = shared_strings(archive)
    rows = defaultdict(dict)
    for cell in root.findall(".//main:sheetData/main:row/main:c", NS):
        reference = cell.attrib.get("r", "")
        column = "".join(ch for ch in reference if ch.isalpha())
        row = int("".join(ch for ch in reference if ch.isdigit()))
        rows[row][column] = text_value(cell, shared)
    return rows


with zipfile.ZipFile(INPUT) as archive:
    rows = cells_by_row(archive, "xl/worksheets/sheet5.xml")

tariffs = [
    {
        "key": values.get("A"),
        "airport": values.get("B"),
        "service": values.get("C"),
        "rate": values.get("D"),
        "unit": values.get("E"),
        "aircraft": values.get("H"),
        "from": values.get("I"),
        "to": values.get("J"),
    }
    for row, values in sorted(rows.items())
    if row > 1 and values.get("A")
]

by_key = defaultdict(list)
for tariff in tariffs:
    by_key[tariff["key"]].append(tariff)

duplicates = {key: values for key, values in by_key.items() if len(values) > 1}
frequency = Counter(len(values) for values in by_key.values())

print("tariff rows", len(tariffs))
print("distinct airport-service keys", len(by_key))
print("keys with duplicates", len(duplicates))
print("duplicate distribution (rows per key -> key count)", dict(sorted(frequency.items())))
print("examples of duplicate keys in current VLOOKUP range")
for key, values in sorted(duplicates.items(), key=lambda item: (-len(item[1]), item[0]))[:12]:
    print(json.dumps({"key": key, "count": len(values), "firstRows": values[:4]}, ensure_ascii=False))
