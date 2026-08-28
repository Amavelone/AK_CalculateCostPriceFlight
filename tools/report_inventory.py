#!/usr/bin/env python3
"""Print concise reports from tools/inventory_xlsx.py JSON."""

from __future__ import annotations

import json
from pathlib import Path


report = json.loads(Path("analysis/xlsx-inventory.json").read_text(encoding="utf-8"))

for workbook in report["workbooks"]:
    print(
        "WORKBOOK",
        workbook["fileName"],
        "size", workbook["fileSizeBytes"],
        "pkg", workbook["packageContents"],
        "names", len(workbook["definedNames"]),
        "externalFormulaRefs", workbook["externalFormulaReferences"],
        "externalLinkParts", workbook["externalLinkParts"],
        "connections", workbook["connections"],
    )
    for sheet in workbook["sheets"]:
        print(
            "  ", sheet["name"], "|", sheet["state"], "|", sheet["dimension"],
            "| cells", sheet["cellCount"], "formula", sheet["formulaCount"],
            "tables", len(sheet["tables"]), "DV", len(sheet["dataValidations"]),
            "cross", sheet["crossSheetReferences"], "external", sheet["externalFormulaReferences"],
            "drawing", sheet["hasDrawing"], "legacy", sheet["hasLegacyDrawing"],
        )
