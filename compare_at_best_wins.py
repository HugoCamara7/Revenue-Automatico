from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


METAFIELD_NAMESPACE = "$app:compare-at-best-wins"
METAFIELD_KEY = "function-configuration"
PRICE_BASIS_CURRENT = "price"
PRICE_BASIS_COMPARE_AT_BEST_WINS = "compare_at_price_best_wins"


@dataclass(frozen=True)
class BestWinsResult:
    compare_at_price: Decimal | None
    current_price: Decimal
    coupon_target_price: Decimal
    final_price: Decimal
    unit_discount: Decimal
    status: str


def money(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def best_wins_line_result(
    current_price: Any,
    compare_at_price: Any,
    percentage: Any,
    missing_compare_at_behavior: str = "use_current_price",
) -> BestWinsResult:
    current = money(current_price)
    compare_at = money(compare_at_price)
    pct = Decimal(str(percentage or 0))
    if current is None:
        current = Decimal("0.00")

    if compare_at is None or compare_at <= Decimal("0.00") or compare_at < current:
        if missing_compare_at_behavior == "do_not_apply":
            return BestWinsResult(
                compare_at_price=compare_at,
                current_price=current,
                coupon_target_price=current,
                final_price=current,
                unit_discount=Decimal("0.00"),
                status="Sin Compare At Price",
            )
        reference = current
        status_if_zero = "Sin Compare At Price"
    else:
        reference = compare_at
        status_if_zero = "Gana promocion actual"

    target = (reference * (Decimal("1") - pct / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    final = min(current, target)
    unit_discount = max(Decimal("0.00"), current - final).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    status = "Gana cupon" if unit_discount > 0 else status_if_zero
    return BestWinsResult(
        compare_at_price=compare_at,
        current_price=current,
        coupon_target_price=target,
        final_price=final,
        unit_discount=unit_discount,
        status=status,
    )


def build_function_configuration(data: dict) -> dict:
    return {
        "percentage": float(data.get("valorDescuento") or 0),
        "price_basis": "compare_at_price",
        "strategy": "best_wins",
        "missing_compare_at_behavior": data.get("missingCompareAtBehavior", "use_current_price"),
        "applies_to": data.get("appliesToFunction", "all_products"),
        "product_ids": data.get("productIds", []),
        "variant_ids": data.get("variantIds", []),
        "collection_ids": data.get("collectionIds", []),
        "excluded_product_ids": data.get("excludedProductIds", []),
        "excluded_variant_ids": data.get("excludedVariantIds", []),
        "maximum_discount_amount": float(data.get("descuentoMaximo") or 0) or None,
        "message": data.get("functionMessage") or "Se aplico el mejor precio disponible",
    }


def build_preview_rows(data: dict) -> list[dict]:
    examples = [
        {"Producto": "Promocion actual mejor", "Compare At Price": 100, "Price actual": 70},
        {"Producto": "Cupon mejor", "Compare At Price": 100, "Price actual": 90},
        {"Producto": "Sin promocion", "Compare At Price": 100, "Price actual": 100},
        {"Producto": "Sin Compare At Price", "Compare At Price": None, "Price actual": 100},
    ]
    rows = []
    for item in examples:
        result = best_wins_line_result(
            item["Price actual"],
            item["Compare At Price"],
            data.get("valorDescuento", 0),
            data.get("missingCompareAtBehavior", "use_current_price"),
        )
        rows.append(
            {
                "Producto ejemplo": item["Producto"],
                "Compare At Price": "" if result.compare_at_price is None else f"S/ {result.compare_at_price}",
                "Price actual": f"S/ {result.current_price}",
                "Precio calculado cupon": f"S/ {result.coupon_target_price}",
                "Precio final Best Wins": f"S/ {result.final_price}",
                "Descuento adicional": f"S/ {result.unit_discount}",
                "Estado": result.status,
            }
        )
    return rows
