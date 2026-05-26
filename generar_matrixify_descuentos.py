from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet


MATRIXIFY_REQUIRED_HEADERS = [
    "ID",
    "Handle",
    "Command",
    "Variant Inventory Item ID",
    "Variant ID",
    "Variant Command",
    "Variant SKU",
    "Variant Price",
    "Variant Compare At Price",
]


@dataclass
class DiscountColumn:
    index: int
    label: str
    header: str
    kind: str
    starts_at: Any = None
    ends_at: Any = None


@dataclass
class DiscountLoad:
    label: str
    kind: str
    discounts: dict[str, float]
    starts_at: Any = None
    ends_at: Any = None
    scope_keys: set[str] = field(default_factory=set)


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def normalize_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", normalize(value))


def as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return number / 100 if "%" in str(value) or number > 1 else number


def money(value: Any) -> float | None:
    number = as_number(value)
    return round(number, 2) if number is not None else None


def format_schedule(value: Any) -> str:
    return "" if value in (None, "") else str(value).strip()


def handle_matches_brands(handle: Any, brands: list[str] | None) -> bool:
    if not brands:
        return True
    handle_key = normalize_key(handle)
    return any(normalize_key(brand) in handle_key for brand in brands)


def brand_for_match_key(match_key: str, brand_lookup: dict[str, str] | None) -> str | None:
    if not brand_lookup:
        return None
    sku = match_key
    modcol = None
    if "|MODCOL:" in match_key:
        sku, modcol = match_key.split("|MODCOL:", 1)

    for candidate in (sku, modcol):
        if candidate:
            brand = brand_lookup.get(normalize_key(candidate))
            if brand:
                return brand
    return None


def filter_loads_by_brand(
    loads: list[DiscountLoad],
    brand_lookup: dict[str, str] | None,
    selected_brands: list[str] | None,
) -> list[DiscountLoad]:
    if not brand_lookup or not selected_brands:
        return loads

    selected = {normalize_key(brand) for brand in selected_brands}
    filtered_loads: list[DiscountLoad] = []

    for load in loads:
        scope_keys = {
            key for key in load.scope_keys
            if normalize_key(brand_for_match_key(key, brand_lookup) or "") in selected
        }
        discounts = {
            key: discount for key, discount in load.discounts.items()
            if normalize_key(brand_for_match_key(key, brand_lookup) or "") in selected
        }
        filtered_loads.append(
            DiscountLoad(load.label, load.kind, discounts, load.starts_at, load.ends_at, scope_keys)
        )
    return filtered_loads


def clean_sheet_name(name: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]", "-", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned) or "Descuento"
    cleaned = cleaned[:31].strip(" -")
    base = cleaned
    suffix = 2
    while cleaned in used:
        tail = f" {suffix}"
        cleaned = f"{base[:31 - len(tail)]}{tail}"
        suffix += 1
    used.add(cleaned)
    return cleaned


def find_header_row(ws: Worksheet, required: list[str], scan_rows: int = 30) -> tuple[int, dict[str, int]]:
    required_norm = {normalize(header): header for header in required}
    for row in range(1, min(ws.max_row, scan_rows) + 1):
        found: dict[str, int] = {}
        for col in range(1, ws.max_column + 1):
            cell_norm = normalize(ws.cell(row=row, column=col).value)
            if cell_norm in required_norm:
                found[required_norm[cell_norm]] = col
        if all(header in found for header in required):
            return row, found
    raise ValueError(f"No encontre encabezados requeridos: {', '.join(required)}")


def find_revenue_layout(ws: Worksheet) -> tuple[int, dict[str, int], list[DiscountColumn]]:
    header_row, columns = find_header_row(ws, ["ID PRODUCTO"], scan_rows=30)
    for col in range(1, ws.max_column + 1):
        header = normalize(ws.cell(row=header_row, column=col).value)
        if header:
            columns[header] = col

    discount_columns: list[DiscountColumn] = []
    for col in range(1, ws.max_column + 1):
        header_value = ws.cell(row=header_row, column=col).value
        header = normalize(header_value)
        if "DCTO" not in header and "DESCUENTO" not in header:
            continue

        top_labels = []
        for row in range(1, header_row):
            value = ws.cell(row=row, column=col).value
            if value not in (None, ""):
                top_labels.append(str(value).strip())

        if not top_labels:
            left = col - 1
            while left >= 1 and not top_labels:
                for row in range(1, header_row):
                    value = ws.cell(row=row, column=left).value
                    if value not in (None, ""):
                        top_labels.append(str(value).strip())
                left -= 1

        label = " - ".join(top_labels + [str(header_value).strip()])
        kind = "resto_mes" if "ANT" in header else "programado"
        discount_columns.append(DiscountColumn(col, label, str(header_value).strip(), kind))

    if not discount_columns:
        raise ValueError("No encontre columnas de descuento en el archivo Revenue.")
    return header_row, columns, discount_columns


def collect_discount_loads(ws: Worksheet) -> tuple[list[DiscountLoad], list[list[Any]]]:
    invalid_rows: list[list[Any]] = [["Variant SKU / ID PRODUCTO", "Columna/Carga", "Valor leido"]]

    try:
        header_row, revenue_cols, discount_columns = find_revenue_layout(ws)
        id_col = revenue_cols["ID PRODUCTO"]
        loads = [DiscountLoad(col.label, col.kind, {}, col.starts_at, col.ends_at) for col in discount_columns]

        for row in range(header_row + 1, ws.max_row + 1):
            product_id = ws.cell(row=row, column=id_col).value
            if product_id in (None, ""):
                continue
            sku = str(product_id).strip()
            for load in loads:
                load.scope_keys.add(sku)
            for load, discount_col in zip(loads, discount_columns):
                discount = as_number(ws.cell(row=row, column=discount_col.index).value)
                if discount is None:
                    continue
                if discount < 0 or discount >= 1:
                    invalid_rows.append([sku, discount_col.label, discount])
                    continue
                load.discounts[sku] = discount
        return loads, invalid_rows
    except ValueError:
        pass

    header_row, columns = find_header_row(ws, ["ID PRODUCTO"], scan_rows=30)
    id_col = columns["ID PRODUCTO"]
    ignored_headers = {
        "ID PRODUCTO",
        "SKU",
        "MODCOL",
        "MODELO",
        "COLOR",
        "OBSERVACION",
        "OBSERVACIONES",
        "SITIO",
        "MARCA",
    }
    loads: list[DiscountLoad] = []
    row_scope_keys: set[str] = set()

    for row in range(header_row + 1, ws.max_row + 1):
        sku_value = ws.cell(row=row, column=id_col).value
        if sku_value in (None, ""):
            continue
        modcol_col = columns.get("MODCOL")
        modcol_value = ws.cell(row=row, column=modcol_col).value if modcol_col else None
        match_key = str(sku_value).strip()
        if modcol_value not in (None, ""):
            match_key = f"{match_key}|MODCOL:{str(modcol_value).strip()}"
        row_scope_keys.add(match_key)

    for col in range(1, ws.max_column + 1):
        header_value = ws.cell(row=header_row, column=col).value
        header = normalize(header_value)
        if not header or header in ignored_headers:
            continue

        discounts: dict[str, float] = {}
        for row in range(header_row + 1, ws.max_row + 1):
            sku_value = ws.cell(row=row, column=id_col).value
            raw_discount = ws.cell(row=row, column=col).value
            if sku_value in (None, "") or raw_discount in (None, ""):
                continue

            discount = as_number(raw_discount)
            if discount is None or discount < 0 or discount >= 1:
                invalid_rows.append([str(sku_value).strip(), str(header_value).strip(), raw_discount])
                continue

            modcol_col = columns.get("MODCOL")
            modcol_value = ws.cell(row=row, column=modcol_col).value if modcol_col else None
            match_key = str(sku_value).strip()
            if modcol_value not in (None, ""):
                match_key = f"{match_key}|MODCOL:{str(modcol_value).strip()}"
            discounts[match_key] = discount

        if discounts:
            kind = "resto_mes" if "RESTO" in header else "programado"
            starts_at = ws.cell(row=header_row - 2, column=col).value if header_row > 2 else None
            ends_at = ws.cell(row=header_row - 1, column=col).value if header_row > 1 else None
            loads.append(DiscountLoad(str(header_value).strip(), kind, discounts, starts_at, ends_at, set(row_scope_keys)))

    if not loads:
        raise ValueError("No encontre un formato valido de descuentos.")
    return loads, invalid_rows


def copy_cell_style(source, target) -> None:
    if source.has_style:
        target.font = copy(source.font)
        target.fill = copy(source.fill)
        target.border = copy(source.border)
        target.alignment = copy(source.alignment)
        target.number_format = source.number_format
        target.protection = copy(source.protection)


def load_matrixify_index(
    matrix_ws: Worksheet,
    matrix_header_row: int,
    matrix_cols: dict[str, int],
    brand_filter: list[str] | None = None,
):
    sku_col = matrix_cols["Variant SKU"]
    group_col = matrix_cols.get("ID") or matrix_cols.get("Handle") or sku_col
    handle_col = matrix_cols.get("Handle")
    sku_to_group: dict[str, str] = {}
    group_variant_count: Counter[str] = Counter()
    modcol_to_group: dict[str, str] = {}
    handle_to_group: list[tuple[str, str]] = []

    for row in range(matrix_header_row + 1, matrix_ws.max_row + 1):
        sku = matrix_ws.cell(row=row, column=sku_col).value
        handle = matrix_ws.cell(row=row, column=handle_col).value if handle_col else ""
        if not handle_matches_brands(handle, brand_filter):
            continue
        group_key = str(matrix_ws.cell(row=row, column=group_col).value or sku or "").strip()
        if not group_key:
            continue
        group_variant_count[group_key] += 1
        if sku not in (None, ""):
            sku_to_group[str(sku).strip()] = group_key
        if handle_col:
            handle = str(handle or "")
            handle_key = normalize_key(handle)
            if handle_key:
                handle_to_group.append((handle_key, group_key))
            parts = handle.split("-")
            for size in range(1, min(len(parts), 4) + 1):
                suffix = "-".join(parts[-size:])
                modcol_to_group.setdefault(normalize_key(suffix), group_key)

    return sku_to_group, group_variant_count, modcol_to_group, handle_to_group, group_col, sku_col


def resolve_discount_groups(
    discounts: dict[str, float],
    sku_to_group: dict[str, str],
    modcol_to_group: dict[str, str],
    handle_to_group: list[tuple[str, str]],
) -> tuple[dict[str, float], list[tuple[str, float]]]:
    groups_to_discount: dict[str, float] = {}
    missing: list[tuple[str, float]] = []

    for match_value, discount in discounts.items():
        sku = match_value
        modcol = None
        if "|MODCOL:" in match_value:
            sku, modcol = match_value.split("|MODCOL:", 1)

        group_key = sku_to_group.get(sku)
        if not group_key and modcol:
            modcol_key = normalize_key(modcol)
            group_key = modcol_to_group.get(modcol_key)
            if not group_key:
                for handle_key, candidate_group in handle_to_group:
                    if handle_key.endswith(modcol_key):
                        group_key = candidate_group
                        break

        if not group_key:
            missing.append((modcol or sku, discount))
            continue
        groups_to_discount[group_key] = max(groups_to_discount.get(group_key, 0), discount)

    return groups_to_discount, missing


def resolve_scope_groups(
    scope_keys: set[str],
    sku_to_group: dict[str, str],
    modcol_to_group: dict[str, str],
    handle_to_group: list[tuple[str, str]],
) -> set[str]:
    scope_map = {key: 0.0 for key in scope_keys}
    groups, _missing = resolve_discount_groups(scope_map, sku_to_group, modcol_to_group, handle_to_group)
    return set(groups)


def analyze_discount_preview(
    matrixify_path: Path,
    revenue_path: Path,
    brand_filter: list[str] | None = None,
    brand_lookup: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    matrix_wb = load_workbook(matrixify_path, read_only=True)
    matrix_ws = matrix_wb["Products"] if "Products" in matrix_wb.sheetnames else matrix_wb.active
    matrix_header_row, matrix_cols = find_header_row(matrix_ws, MATRIXIFY_REQUIRED_HEADERS)

    revenue_wb = load_workbook(revenue_path, data_only=True, read_only=True)
    revenue_ws = revenue_wb.active
    discount_loads, _invalid_rows = collect_discount_loads(revenue_ws)
    discount_loads = filter_loads_by_brand(discount_loads, brand_lookup, brand_filter)

    sku_to_group, group_variant_count, modcol_to_group, handle_to_group, _group_col, _sku_col = load_matrixify_index(
        matrix_ws, matrix_header_row, matrix_cols, brand_filter
    )

    overview_rows: list[dict[str, Any]] = []
    percent_rows: list[dict[str, Any]] = []
    missing_total = 0

    for load in discount_loads:
        groups_to_discount, missing = resolve_discount_groups(
            load.discounts, sku_to_group, modcol_to_group, handle_to_group
        )
        scope_groups = resolve_scope_groups(load.scope_keys, sku_to_group, modcol_to_group, handle_to_group)
        missing_total += len(missing)
        affected_variants = sum(group_variant_count[group] for group in groups_to_discount)
        sheet_name = clean_sheet_name(load.label, set())

        overview_rows.append(
            {
                "Carga": sheet_name,
                "SKUs input con descuento": len(load.discounts),
                "Cod MODCOL / productos afectados": len(groups_to_discount),
                "Cod MODCOL / productos en archivo": len(scope_groups),
                "Variantes Matrixify afectadas": affected_variants,
                "SKUs no encontrados": len(missing),
                "Inicio": format_schedule(load.starts_at),
                "Fin": format_schedule(load.ends_at),
            }
        )

        percent_to_groups: dict[float, set[str]] = defaultdict(set)
        percent_to_skus: Counter[float] = Counter()
        for match_value, discount in load.discounts.items():
            groups_for_one, _missing_one = resolve_discount_groups(
                {match_value: discount}, sku_to_group, modcol_to_group, handle_to_group
            )
            for group in groups_for_one:
                percent_to_groups[discount].add(group)
                percent_to_skus[discount] += 1

        for discount, groups in sorted(percent_to_groups.items(), reverse=True):
            percent_rows.append(
                {
                    "Carga": sheet_name,
                    "% Descuento": f"{discount:.0%}",
                    "SKUs input": percent_to_skus[discount],
                    "Cod MODCOL / productos": len(groups),
                    "Variantes Matrixify": sum(group_variant_count[group] for group in groups),
                }
            )

    matrix_wb.close()
    revenue_wb.close()
    return overview_rows, percent_rows, missing_total


def build_discount_workbook(
    matrixify_path: Path,
    revenue_path: Path,
    output_path: Path,
    brand_filter: list[str] | None = None,
    brand_lookup: dict[str, str] | None = None,
) -> Path:
    matrix_wb = load_workbook(matrixify_path)
    matrix_ws = matrix_wb["Products"] if "Products" in matrix_wb.sheetnames else matrix_wb.active
    matrix_header_row, matrix_cols = find_header_row(matrix_ws, MATRIXIFY_REQUIRED_HEADERS)

    revenue_wb = load_workbook(revenue_path, data_only=True)
    revenue_ws = revenue_wb.active
    discount_loads, invalid_rows = collect_discount_loads(revenue_ws)
    discount_loads = filter_loads_by_brand(discount_loads, brand_lookup, brand_filter)

    sku_to_group, group_variant_count, modcol_to_group, handle_to_group, group_col, sku_col = load_matrixify_index(
        matrix_ws, matrix_header_row, matrix_cols, brand_filter
    )
    handle_col = matrix_cols.get("Handle")

    output_wb = Workbook()
    output_wb.remove(output_wb.active)
    used_names: set[str] = set()
    summary_rows = [
        [
            "Hoja",
            "Tipo",
            "Columna Revenue",
            "SKUs con descuento",
            "Productos/Modelo-color con descuento",
            "Productos/Modelo-color en archivo",
            "Filas Matrixify generadas",
            "Filas sin descuento",
            "SKUs Revenue no encontrados",
            "Inicio",
            "Fin",
        ]
    ]
    missing_rows: list[list[Any]] = [["Hoja", "Variant SKU / ID PRODUCTO", "Descuento"]]

    for load in discount_loads:
        if not load.discounts:
            continue

        sheet_name = clean_sheet_name(load.label, used_names)
        out_ws = output_wb.create_sheet(sheet_name)

        for col in range(1, len(MATRIXIFY_REQUIRED_HEADERS) + 1):
            source = matrix_ws.cell(row=matrix_header_row, column=col)
            target = out_ws.cell(row=1, column=col, value=source.value)
            copy_cell_style(source, target)
            out_ws.column_dimensions[target.column_letter].width = max(
                matrix_ws.column_dimensions[source.column_letter].width or 12, 12
            )

        groups_to_discount, missing_records = resolve_discount_groups(
            load.discounts, sku_to_group, modcol_to_group, handle_to_group
        )
        scope_groups = resolve_scope_groups(load.scope_keys, sku_to_group, modcol_to_group, handle_to_group)
        total_rows = sum(group_variant_count[group] for group in scope_groups)
        if missing_records:
            missing_rows.extend([[sheet_name, key, discount] for key, discount in missing_records])

        out_row = 2
        discounted_output_rows = 0
        for matrix_row in range(matrix_header_row + 1, matrix_ws.max_row + 1):
            handle = matrix_ws.cell(row=matrix_row, column=handle_col).value if handle_col else ""
            if not handle_matches_brands(handle, brand_filter):
                continue
            group_key = str(matrix_ws.cell(row=matrix_row, column=group_col).value or "").strip()
            if not group_key:
                group_key = str(matrix_ws.cell(row=matrix_row, column=sku_col).value or "").strip()
            if group_key not in scope_groups:
                continue
            discount = groups_to_discount.get(group_key)
            original_compare = money(matrix_ws.cell(row=matrix_row, column=matrix_cols["Variant Compare At Price"]).value)
            current_price = money(matrix_ws.cell(row=matrix_row, column=matrix_cols["Variant Price"]).value)
            original_price = original_compare or current_price

            if original_price is None:
                new_price = matrix_ws.cell(row=matrix_row, column=matrix_cols["Variant Price"]).value
                compare_at = None
            elif discount is None or discount <= 0:
                new_price = original_price
                compare_at = None
            else:
                new_price = round(original_price * (1 - discount), 2)
                compare_at = original_price if new_price != original_price else None
                if compare_at is not None:
                    discounted_output_rows += 1

            for col in range(1, len(MATRIXIFY_REQUIRED_HEADERS) + 1):
                source = matrix_ws.cell(row=matrix_row, column=col)
                value = source.value
                if col == matrix_cols["Variant Price"]:
                    value = new_price
                elif col == matrix_cols["Variant Compare At Price"]:
                    value = compare_at
                target = out_ws.cell(row=out_row, column=col, value=value)
                copy_cell_style(source, target)
                if col in (matrix_cols["Variant Price"], matrix_cols["Variant Compare At Price"]):
                    target.number_format = "0.00"
            out_row += 1

        out_ws.freeze_panes = "A2"
        out_ws.auto_filter.ref = out_ws.dimensions
        summary_rows.append(
            [
                sheet_name,
                "Resto del mes" if load.kind == "resto_mes" else "Programado",
                load.label,
                len(load.discounts),
                len(groups_to_discount),
                len(scope_groups),
                total_rows,
                total_rows - discounted_output_rows,
                len(missing_records),
                format_schedule(load.starts_at),
                format_schedule(load.ends_at),
            ]
        )

    summary_ws = output_wb.create_sheet("Resumen", 0)
    for row in summary_rows:
        summary_ws.append(row)
    summary_ws.freeze_panes = "A2"
    summary_ws.auto_filter.ref = summary_ws.dimensions
    for col in range(1, 12):
        summary_ws.column_dimensions[summary_ws.cell(row=1, column=col).column_letter].width = 28

    if len(missing_rows) > 1:
        missing_ws = output_wb.create_sheet("No encontrados")
        for row in missing_rows:
            missing_ws.append(row)
        missing_ws.freeze_panes = "A2"
        missing_ws.auto_filter.ref = missing_ws.dimensions

    if len(invalid_rows) > 1:
        invalid_ws = output_wb.create_sheet("Descuentos invalidos")
        for row in invalid_rows:
            invalid_ws.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_wb.save(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera Matrixify de descuentos por hoja/campana.")
    parser.add_argument("--matrixify", type=Path, required=True)
    parser.add_argument("--revenue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_discount_workbook(args.matrixify, args.revenue, args.output))


if __name__ == "__main__":
    main()
