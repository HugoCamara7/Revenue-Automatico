use rust_decimal::prelude::*;
use rust_decimal::Decimal;
use serde::Deserialize;

#[derive(Clone, Debug, Deserialize)]
struct FunctionConfiguration {
    percentage: Decimal,
    #[serde(default = "default_missing_compare_at_behavior")]
    missing_compare_at_behavior: String,
    #[serde(default = "default_message")]
    message: String,
}

fn default_missing_compare_at_behavior() -> String {
    "use_current_price".to_string()
}

fn default_message() -> String {
    "Se aplico el mejor precio disponible".to_string()
}

#[derive(Clone, Debug, PartialEq)]
pub struct BestWinsLine {
    pub coupon_target_price: Decimal,
    pub final_price: Decimal,
    pub unit_discount: Decimal,
}

pub fn calculate_best_wins_line(
    current_price: Decimal,
    compare_at_price: Option<Decimal>,
    percentage: Decimal,
    missing_compare_at_behavior: &str,
) -> BestWinsLine {
    let zero = Decimal::ZERO;
    let reference_price = match compare_at_price {
        Some(compare_at) if compare_at > zero && compare_at >= current_price => compare_at,
        _ if missing_compare_at_behavior == "do_not_apply" => current_price,
        _ => current_price,
    };

    if compare_at_price.is_none() && missing_compare_at_behavior == "do_not_apply" {
        return BestWinsLine {
            coupon_target_price: current_price.round_dp(2),
            final_price: current_price.round_dp(2),
            unit_discount: zero,
        };
    }

    let coupon_target_price =
        (reference_price * (Decimal::ONE - percentage / Decimal::new(100, 0))).round_dp(2);
    let final_price = current_price.min(coupon_target_price).round_dp(2);
    let unit_discount = (current_price - final_price).max(zero).round_dp(2);

    BestWinsLine {
        coupon_target_price,
        final_price,
        unit_discount,
    }
}

// Integracion requerida dentro de una Shopify Function generada con Shopify CLI:
// 1. Ejecutar `shopify app generate extension --template discount_function`.
// 2. Copiar este calculo y el input.graphql en la extension real.
// 3. Mapear cada cart line del schema generado por Shopify al calculo.
// 4. Crear un ProductDiscountCandidate por linea con:
//    fixedAmount.amount = unit_discount
//    fixedAmount.appliesToEachItem = true
// 5. Devolver ProductDiscountSelectionStrategy::All.
//
// Este archivo se deja como implementacion de referencia porque el repo actual
// es Streamlit y no contiene el crate generado por Shopify CLI ni los bindings
// tipados que Shopify crea a partir del schema de la tienda.
