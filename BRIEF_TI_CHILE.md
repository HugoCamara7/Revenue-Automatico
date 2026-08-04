# Solicitud a TI Chile: Discount Function "Compare At Price - Best Wins"

Este documento tiene dos partes: el mensaje corto para enviar y el anexo tecnico
para quien lo va a implementar.

---

## PARTE A - Mensaje para enviar

Asunto: Solicitud de Shopify Discount Function para cupones sobre Compare At Price

Hola equipo,

Necesitamos desplegar una Shopify Discount Function en las tiendas de Peru
(Columbia, Rockford, Hush Puppies, Bsoul, RKS Life, Keds, Supermall). En Vans ya
tenemos el flujo armado y queremos replicarlo.

**El problema de negocio.** Cuando un producto esta en promocion, Shopify guarda el
precio de lista en `Compare At Price` y el precio rebajado en `Variant Price`. Un
cupon normal de Shopify siempre calcula el porcentaje sobre el `Variant Price`, es
decir sobre el precio ya rebajado. Eso nos descuadra la campana: un cupon de 40%
sobre un producto que ya tiene 30% termina dando 58% de descuento real.

Lo que necesitamos es que el cupon calcule el 40% **sobre el `Compare At Price`** y,
si el precio vigente ya es mejor que ese resultado, que no toque nada. Es decir:
el cliente siempre se lleva el mejor precio, pero nunca los dos descuentos sumados.

**Por que no se puede de otra forma.** Esto no se resuelve con Liquid, con JavaScript
del tema, ni con un descuento porcentual nativo: Shopify siempre aplica el porcentaje
sobre el precio vigente. La unica forma soportada es una Shopify Function, que calcula
un monto fijo por linea del carrito y lo devuelve al checkout.

**Que les pedimos concretamente.** Una app de Shopify (creada con Shopify CLI) con una
extension del tipo Discount Function, desplegada e instalada en esas tiendas. Nosotros
no necesitamos acceso al codigo: solo necesitamos que exista y que nos pasen 3 datos:

1. El **handle** de la extension (el nombre corto que la identifica, ej. `compare-at-best-wins`).
2. El **client_id** de la app.
3. Un **access token** de esa misma app para cada tienda, con permiso `write_discounts`.

Con esos datos, nuestra aplicacion crea los cupones sola, sin que ustedes tengan que
intervenir en cada campana.

**Alcance y riesgo.** Es una extension aislada:

- no modifica el tema ni el codigo de la tienda;
- no cambia precios en el catalogo (el precio del producto queda igual);
- solo actua cuando el cliente ingresa un codigo de cupon creado por nosotros;
- si se desactiva el cupon, todo vuelve a la normalidad al instante;
- no interfiere con otras apps ni con los descuentos existentes.

En el anexo va la logica exacta y los ejemplos numericos, para que quede sin
ambiguedad. Quedamos atentos.

---

## PARTE B - Anexo tecnico

### B.1 Que es una Shopify Function

Es codigo (Rust o JavaScript compilado a WebAssembly) que Shopify ejecuta dentro de
su propia infraestructura cuando se arma el carrito o el checkout. No es un webhook ni
un servicio externo: corre en Shopify, en milisegundos, sin llamadas a servidores
nuestros. Se distribuye como una **extension** dentro de una app de Shopify.

### B.2 Que es el handle

El `handle` es el identificador corto de esa extension. No lo genera Shopify: lo define
quien crea la extension, en el archivo `shopify.extension.toml`:

```toml
api_version = "2026-04"

[[extensions]]
name = "Compare At Price - Best Wins"
handle = "compare-at-best-wins"      # <- esto es el handle
type = "function"
uid = "compare-at-best-wins"

  [[extensions.targeting]]
  target = "cart.lines.discounts.generate.run"
  input_query = "input.graphql"
  export = "run"
```

Cuando creamos el cupon por API con `discountCodeAppCreate`, mandamos ese handle para
decirle a Shopify "el monto de este descuento lo calcula esta Function". Si desplegan
la misma extension en las 8 tiendas, el handle es el mismo en las 8.

Se puede consultar en cualquier momento con esta query (Admin GraphQL, API 2026-04):

```graphql
query {
  shopifyFunctions(apiType: "discount", first: 50) {
    nodes { id handle title apiType appKey }
  }
}
```

`appKey` es el `client_id` de la app dueña de la Function.

### B.3 Importante: el token debe ser de la misma app

La Function guarda su configuracion en un metafield con namespace reservado
`$app:compare-at-best-wins`. Ese prefijo `$app:` se resuelve contra la app que hace la
llamada a la API. Por eso:

- un custom app creado desde el Admin de la tienda **no sirve** (no puede tener Functions);
- el token que nos pasen tiene que ser de la **misma app** que tiene la Function instalada.

### B.4 Target y version

- API version: `2026-04`
- Target: `cart.lines.discounts.generate.run`
- Permisos de la app: `write_discounts`, `read_discounts` y **`read_products`**
  (este ultimo lo necesitamos para listar colecciones y productos al armar cupones
  dirigidos a una coleccion o a SKUs puntuales)

### B.5 Configuracion que enviamos en el metafield

Al crear cada cupon, nuestra app guarda este JSON en el descuento:

- namespace: `$app:compare-at-best-wins`
- key: `function-configuration`
- type: `json`

```json
{
  "percentage": 40,
  "price_basis": "compare_at_price",
  "strategy": "best_wins",
  "missing_compare_at_behavior": "use_current_price",
  "applies_to": "all_products",
  "product_ids": [],
  "variant_ids": [],
  "collection_ids": [],
  "excluded_product_ids": [],
  "excluded_variant_ids": [],
  "maximum_discount_amount": null,
  "minimum_subtotal": 299,
  "message": "Se aplico el mejor precio disponible"
}
```

La Function necesita leer `percentage`, `missing_compare_at_behavior`, **`minimum_subtotal`**
y **`applies_to` + `collection_ids` / `variant_ids`**: cuando el cupon apunta a una coleccion
o a SKUs concretos, la Function solo debe descontar en las lineas que pertenezcan a esos IDs.

Ojo con `minimum_subtotal`: `DiscountCodeAppInput` de la API 2026-04 **no acepta**
`minimumRequirement`, asi que la compra minima de un cupon con Function no la valida
Shopify. Tiene que evaluarla la Function: si el subtotal del carrito es menor a
`minimum_subtotal`, no debe generar ningun candidato de descuento. Los demas campos
estan reservados para reglas futuras.

### B.6 Logica exacta a implementar

Por cada linea del carrito:

```text
precio_actual   = cost.amountPerQuantity                 (Variant Price vigente)
compare_at      = cost.compareAtAmountPerQuantity        (puede venir vacio)

si compare_at existe y compare_at > 0 y compare_at >= precio_actual:
    referencia = compare_at
si no:
    referencia = precio_actual        (comportamiento use_current_price)

precio_objetivo = redondear(referencia * (1 - porcentaje / 100), 2)
precio_final    = minimo(precio_actual, precio_objetivo)
descuento_linea = maximo(0, precio_actual - precio_final)
```

Si `descuento_linea` es 0, no se genera candidato para esa linea. Si es mayor a 0, se
devuelve un `ProductDiscountCandidate` con:

- `fixedAmount.amount = descuento_linea`
- `fixedAmount.appliesToEachItem = true`
- estrategia: `ProductDiscountSelectionStrategy::All`

La clave del negocio esta en `precio_final = minimo(...)`: **la Function nunca sube un
precio ni descuenta de mas cuando la promocion vigente ya es mejor que el cupon.**

### B.7 Ejemplos numericos (cupon de 40%)

| Caso | Compare At | Price actual | Precio objetivo | Precio final | Descuento aplicado |
| --- | --- | --- | --- | --- | --- |
| Promocion vigente ya es mejor | 100.00 | 55.00 | 60.00 | 55.00 | 0.00 |
| El cupon es mejor | 100.00 | 90.00 | 60.00 | 60.00 | 30.00 |
| Producto sin promocion | 100.00 | 100.00 | 60.00 | 60.00 | 40.00 |
| Sin Compare At Price | (vacio) | 100.00 | 60.00 | 60.00 | 40.00 |

Estos cuatro casos son los que vamos a probar en cada tienda antes de activar un cupon
real. Si los cuatro dan estos numeros, la Function esta correcta.

### B.8 Input query

```graphql
query Input {
  cart {
    lines {
      id
      quantity
      cost {
        amountPerQuantity { amount currencyCode }
        compareAtAmountPerQuantity { amount currencyCode }
      }
      merchandise {
        __typename
        ... on ProductVariant {
          id
          sku
          product { id }
        }
      }
    }
  }
  discount {
    metafield(namespace: "$app:compare-at-best-wins", key: "function-configuration") {
      jsonValue
    }
  }
}
```

### B.9 Pasos del lado de ustedes

```bash
shopify app generate extension --template discount_function
# elegir API 2026-04 y target cart.lines.discounts.generate.run
# implementar la logica de B.6
shopify app deploy
# instalar la app en cada tienda
```

Sobre la distribucion: si las tiendas estan en la misma organizacion Shopify Plus, una
sola app con custom distribution se puede instalar en todas. Si son cuentas separadas,
hace falta una app por tienda (mismo codigo, mismo handle).

### B.10 Que nos devuelven

Por cada tienda:

| Dato | Ejemplo |
| --- | --- |
| Dominio | `columbiape.myshopify.com` |
| Handle de la Function | `compare-at-best-wins` |
| client_id de la app | `1a2b3c...` |
| Access token de esa app | `shpat_...` |

Nosotros validamos que quedo bien corriendo un diagnostico de solo lectura contra cada
tienda: verifica el token, los permisos y que la Function este visible. No creamos nada
hasta que ese diagnostico este en verde.
