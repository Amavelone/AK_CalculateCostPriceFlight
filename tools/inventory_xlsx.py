#!/usr/bin/env python3
"""Строит структурный инвентарь рабочих книг Excel в формате OOXML.

Скрипт использует только стандартную библиотеку Python, работает в режиме
чтения и никогда не изменяет исходные книги. Компактный JSON фиксирует
структуру книги, шаблоны формул, межлистовые связи и характерные значения.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "x14": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main",
}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
CELL_REF = re.compile(r"(?<![A-Z0-9_])(?P<col>\$?[A-Z]{1,3})(?P<row>\$?\d+)")
SHEET_REF = re.compile(r"(?:'(?P<quoted>[^']+)'|(?P<bare>[A-Za-zА-Яа-яЁё0-9_]+))!")
EXTERNAL_REF = re.compile(r"\[(?P<file>[^\]]+)\]")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_xml(archive: zipfile.ZipFile, path: str) -> ET.Element | None:
    try:
        return ET.fromstring(archive.read(path))
    except KeyError:
        return None


def rels_for(archive: zipfile.ZipFile, part: str) -> dict[str, dict[str, str]]:
    folder, filename = posixpath.split(part)
    relpath = posixpath.join(folder, "_rels", filename + ".rels")
    root = read_xml(archive, relpath)
    if root is None:
        return {}
    results: dict[str, dict[str, str]] = {}
    for rel in root:
        target = rel.attrib.get("Target", "")
        if target and rel.attrib.get("TargetMode") != "External":
            target = posixpath.normpath(posixpath.join(folder, target))
        results[rel.attrib.get("Id", "")] = {
            "type": rel.attrib.get("Type", "").rsplit("/", 1)[-1],
            "target": target,
            "mode": rel.attrib.get("TargetMode", "Internal"),
        }
    return results


def column_num(column: str) -> int:
    value = 0
    for char in column.replace("$", ""):
        value = value * 26 + ord(char) - 64
    return value


def parse_a1(reference: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", reference)
    if not match:
        return None
    return int(match.group(2)), column_num(match.group(1))


def normalise_formula(formula: str, cell_ref: str) -> str:
    """Преобразует простые ссылки A1 в относительные маркеры, близкие к R1C1.

    Ссылки на листы и внешние книги намеренно остаются неизменными, а формулы,
    скопированные по строкам или столбцам, объединяются в одно семейство.
    """
    position = parse_a1(cell_ref)
    if position is None:
        return formula
    row, col = position

    def replacement(match: re.Match[str]) -> str:
        absolute_col = match.group("col").startswith("$")
        absolute_row = match.group("row").startswith("$")
        target_col = column_num(match.group("col"))
        target_row = int(match.group("row").replace("$", ""))
        col_part = f"C{target_col}" if absolute_col else f"C[{target_col - col}]"
        row_part = f"R{target_row}" if absolute_row else f"R[{target_row - row}]"
        return row_part + col_part

    return CELL_REF.sub(replacement, formula)


def translate_formula(formula: str, source_ref: str, target_ref: str) -> str:
    """Переносит основную общую формулу из исходной ячейки в дочернюю."""
    source = parse_a1(source_ref)
    target = parse_a1(target_ref)
    if source is None or target is None:
        return formula
    row_shift = target[0] - source[0]
    col_shift = target[1] - source[1]

    def replacement(match: re.Match[str]) -> str:
        col_text = match.group("col")
        row_text = match.group("row")
        absolute_col = col_text.startswith("$")
        absolute_row = row_text.startswith("$")
        new_column = column_num(col_text) + (0 if absolute_col else col_shift)
        new_row = int(row_text.replace("$", "")) + (0 if absolute_row else row_shift)
        if new_column < 1 or new_row < 1:
            return "#REF!"
        letters = ""
        while new_column:
            new_column, remainder = divmod(new_column - 1, 26)
            letters = chr(65 + remainder) + letters
        return ("$" if absolute_col else "") + letters + ("$" if absolute_row else "") + str(new_row)

    return CELL_REF.sub(replacement, formula)


def looks_like_external_file(value: str) -> bool:
    """Отличает внешние файлы от структурированных ссылок вида [#All] или [Column]."""
    candidate = value.lower()
    return ".xls" in candidate or "\\" in value or "/" in value or candidate.startswith("http")


def text_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(cell.itertext())
    value = cell.find("main:v", NS)
    if value is None:
        return None
    raw = value.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    if cell_type == "b":
        return raw == "1"
    if cell_type == "e":
        return raw
    return raw


def snippet(value: Any, limit: int = 100) -> Any:
    if isinstance(value, str):
        return value.replace("\n", " ")[:limit]
    return value


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = read_xml(archive, "xl/sharedStrings.xml")
    if root is None:
        return []
    return ["".join(item.itertext()) for item in root.findall("main:si", NS)]


def style_inventory(archive: zipfile.ZipFile) -> dict[str, int]:
    root = read_xml(archive, "xl/styles.xml")
    if root is None:
        return {}
    return {
        "fonts": len(root.findall("main:fonts/main:font", NS)),
        "fills": len(root.findall("main:fills/main:fill", NS)),
        "borders": len(root.findall("main:borders/main:border", NS)),
        "cellXfs": len(root.findall("main:cellXfs/main:xf", NS)),
    }


def content_types(archive: zipfile.ZipFile) -> dict[str, int]:
    counts = Counter()
    for name in archive.namelist():
        if not name.startswith("xl/"):
            continue
        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
            counts["worksheets"] += 1
        elif name.startswith("xl/pivotTables/"):
            counts["pivotTables"] += 1
        elif name.startswith("xl/pivotCache/"):
            counts["pivotCaches"] += 1
        elif re.fullmatch(r"xl/tables/table\d+\.xml", name):
            counts["tables"] += 1
        elif re.fullmatch(r"xl/externalLinks/externalLink\d+\.xml", name):
            counts["externalLinks"] += 1
        elif name == "xl/connections.xml":
            counts["connectionsParts"] += 1
        elif name.startswith("xl/queryTables/"):
            counts["queryTables"] += 1
        elif name.startswith("xl/slicers/"):
            counts["slicers"] += 1
        elif name.startswith("xl/drawings/"):
            counts["drawings"] += 1
        elif name.startswith("xl/vbaProject"):
            counts["vbaProjects"] += 1
        elif name.startswith("xl/ctrlProps/"):
            counts["controlProperties"] += 1
        elif name.startswith("xl/embeddings/"):
            counts["embeddings"] += 1
    return dict(counts)


def extract_connections(archive: zipfile.ZipFile) -> list[dict[str, str]]:
    root = read_xml(archive, "xl/connections.xml")
    if root is None:
        return []
    results = []
    for connection in root.findall("main:connection", NS):
        results.append({
            "id": connection.attrib.get("id", ""),
            "name": connection.attrib.get("name", ""),
            "type": connection.attrib.get("type", ""),
            "description": connection.attrib.get("description", ""),
            "connection": connection.attrib.get("connection", "")[:500],
            "refreshedVersion": connection.attrib.get("refreshedVersion", ""),
        })
    return results


def extract_external_links(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for part in archive.namelist():
        if not re.fullmatch(r"xl/externalLinks/externalLink\d+\.xml", part):
            continue
        root = read_xml(archive, part)
        rels = rels_for(archive, part)
        book_ref = root.find(".//main:externalBook", NS) if root is not None else None
        relation_id = book_ref.attrib.get(RID, "") if book_ref is not None else ""
        sheet_names = []
        if root is not None:
            for name in root.findall(".//main:sheetName", NS):
                sheet_names.append(name.attrib.get("val", ""))
        results.append({
            "part": part,
            "target": rels.get(relation_id, {}).get("target", ""),
            "sheets": sheet_names,
        })
    return results


def inspect_sheet(
    archive: zipfile.ZipFile,
    sheet_name: str,
    sheet_path: str,
    shared: list[str],
) -> dict[str, Any]:
    root = read_xml(archive, sheet_path)
    if root is None:
        return {"name": sheet_name, "part": sheet_path, "error": "worksheet XML missing"}
    rels = rels_for(archive, sheet_path)
    dimension = root.find("main:dimension", NS)
    cells = root.findall(".//main:sheetData/main:row/main:c", NS)
    formula_cells: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    style_counts: Counter[str] = Counter()
    external_files: Counter[str] = Counter()
    references: Counter[str] = Counter()
    cross_sheet_refs: Counter[str] = Counter()
    formulas_by_pattern: dict[str, list[str]] = defaultdict(list)
    shared_formula_masters: dict[str, tuple[str, str]] = {}
    cached_formula_errors: Counter[str] = Counter()
    cached_formula_error_samples: list[dict[str, Any]] = []
    rows = Counter()
    columns = Counter()

    for cell in cells:
        reference = cell.attrib.get("r", "")
        point = parse_a1(reference)
        if point:
            rows[point[0]] += 1
            columns[point[1]] += 1
        if "s" in cell.attrib:
            style_counts[cell.attrib["s"]] += 1
        formula = cell.find("main:f", NS)
        value = text_value(cell, shared)
        if formula is not None:
            formula_body = formula.text or ""
            shared_index = formula.attrib.get("si")
            if formula.attrib.get("t") == "shared":
                if formula_body:
                    shared_formula_masters[shared_index or ""] = (reference, formula_body)
                elif shared_index in shared_formula_masters:
                    master_ref, master_formula = shared_formula_masters[shared_index]
                    formula_body = translate_formula(master_formula, master_ref, reference)
            formula_text = "=" + formula_body
            pattern = normalise_formula(formula_text, reference)
            formulas_by_pattern[pattern].append(reference)
            for match in EXTERNAL_REF.finditer(formula_text):
                candidate = match.group("file")
                if looks_like_external_file(candidate):
                    external_files[candidate] += 1
            for match in SHEET_REF.finditer(formula_text):
                linked_sheet = match.group("quoted") or match.group("bare")
                cross_sheet_refs[linked_sheet] += 1
            for match in CELL_REF.finditer(formula_text):
                references[match.group(0)] += 1
            if len(formula_cells) < 20:
                formula_cells.append({"cell": reference, "formula": formula_text[:500], "cachedValue": snippet(value)})
            if isinstance(value, str) and value.startswith("#"):
                cached_formula_errors[value] += 1
                if len(cached_formula_error_samples) < 20:
                    cached_formula_error_samples.append({"cell": reference, "formula": formula_text[:500], "cachedValue": value})
        elif value not in (None, "") and len(values) < 60:
            values.append({"cell": reference, "value": snippet(value)})

    table_parts = []
    for table_part in root.findall("main:tableParts/main:tablePart", NS):
        rid = table_part.attrib.get(RID, "")
        target = rels.get(rid, {}).get("target", "")
        table_root = read_xml(archive, target)
        if table_root is not None:
            table_parts.append({
                "name": table_root.attrib.get("name", ""),
                "displayName": table_root.attrib.get("displayName", ""),
                "ref": table_root.attrib.get("ref", ""),
                "totalsRowShown": table_root.attrib.get("totalsRowShown", "0"),
                "columns": [column.attrib.get("name", "") for column in table_root.findall("main:tableColumns/main:tableColumn", NS)],
            })

    validations = []
    for validation in root.findall("main:dataValidations/main:dataValidation", NS):
        formula_1 = validation.find("main:formula1", NS)
        formula_2 = validation.find("main:formula2", NS)
        validations.append({
            "sqref": validation.attrib.get("sqref", ""),
            "type": validation.attrib.get("type", ""),
            "operator": validation.attrib.get("operator", ""),
            "formula1": formula_1.text if formula_1 is not None else "",
            "formula2": formula_2.text if formula_2 is not None else "",
            "allowBlank": validation.attrib.get("allowBlank", ""),
        })

    conditional_formats = []
    for conditional in root.findall("main:conditionalFormatting", NS):
        conditional_formats.append({
            "sqref": conditional.attrib.get("sqref", ""),
            "rules": [rule.attrib.get("type", "") for rule in conditional.findall("main:cfRule", NS)],
        })

    merged = [merge.attrib.get("ref", "") for merge in root.findall("main:mergeCells/main:mergeCell", NS)]
    hyperlinks = [link.attrib.get("ref", "") for link in root.findall("main:hyperlinks/main:hyperlink", NS)]
    drawings = [rel.attrib.get(RID, "") for rel in root.findall("main:drawing", NS)]
    legacy_drawing = root.find("main:legacyDrawing", NS)

    return {
        "name": sheet_name,
        "part": sheet_path,
        "dimension": dimension.attrib.get("ref", "") if dimension is not None else "",
        "cellCount": len(cells),
        "populatedRowCount": len(rows),
        "maxPopulatedRow": max(rows, default=0),
        "maxPopulatedColumn": max(columns, default=0),
        "formulaCount": sum(len(items) for items in formulas_by_pattern.values()),
        "formulaPatterns": [
            {"count": len(cells_), "sampleCells": cells_[:6], "pattern": pattern[:600]}
            for pattern, cells_ in sorted(formulas_by_pattern.items(), key=lambda item: (-len(item[1]), item[0]))[:40]
        ],
        "formulaSamples": formula_cells,
        "cachedFormulaErrors": dict(cached_formula_errors),
        "cachedFormulaErrorSamples": cached_formula_error_samples,
        "nonFormulaValueSamples": values,
        "externalFormulaReferences": dict(external_files),
        "crossSheetReferences": dict(cross_sheet_refs),
        "tables": table_parts,
        "dataValidations": validations,
        "conditionalFormats": conditional_formats,
        "mergedRanges": merged[:100],
        "hyperlinks": hyperlinks,
        "hasDrawing": bool(drawings),
        "hasLegacyDrawing": legacy_drawing is not None,
        "styleCount": len(style_counts),
        "topStyles": style_counts.most_common(10),
    }


def inventory(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        workbook = read_xml(archive, "xl/workbook.xml")
        if workbook is None:
            raise ValueError("xl/workbook.xml is absent")
        rels = rels_for(archive, "xl/workbook.xml")
        shared = shared_strings(archive)
        sheets = []
        for sheet in workbook.findall("main:sheets/main:sheet", NS):
            relation_id = sheet.attrib.get(RID, "")
            part = rels.get(relation_id, {}).get("target", "")
            sheet_info = inspect_sheet(archive, sheet.attrib.get("name", ""), part, shared)
            sheet_info["state"] = sheet.attrib.get("state", "visible")
            sheet_info["sheetId"] = sheet.attrib.get("sheetId", "")
            sheets.append(sheet_info)

        defined_names = []
        for name in workbook.findall("main:definedNames/main:definedName", NS):
            defined_names.append({
                "name": name.attrib.get("name", ""),
                "localSheetId": name.attrib.get("localSheetId", ""),
                "hidden": name.attrib.get("hidden", "0"),
                "formula": (name.text or "")[:1000],
            })

        all_external_formula_refs: Counter[str] = Counter()
        for sheet in sheets:
            all_external_formula_refs.update(sheet.get("externalFormulaReferences", {}))

        return {
            "file": str(path),
            "fileName": path.name,
            "fileSizeBytes": path.stat().st_size,
            "inventoriedAtUtc": datetime.now(timezone.utc).isoformat(),
            "workbookProperties": {
                "date1904": workbook.find("main:workbookPr", NS).attrib.get("date1904", "0") if workbook.find("main:workbookPr", NS) is not None else "0",
                "calcMode": workbook.find("main:calcPr", NS).attrib.get("calcMode", "") if workbook.find("main:calcPr", NS) is not None else "",
                "fullCalcOnLoad": workbook.find("main:calcPr", NS).attrib.get("fullCalcOnLoad", "") if workbook.find("main:calcPr", NS) is not None else "",
                "forceFullCalc": workbook.find("main:calcPr", NS).attrib.get("forceFullCalc", "") if workbook.find("main:calcPr", NS) is not None else "",
            },
            "packageContents": content_types(archive),
            "styleInventory": style_inventory(archive),
            "definedNames": defined_names,
            "connections": extract_connections(archive),
            "externalLinkParts": extract_external_links(archive),
            "externalFormulaReferences": dict(all_external_formula_refs),
            "sheets": sheets,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"workbooks": [inventory(path) for path in args.inputs]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
