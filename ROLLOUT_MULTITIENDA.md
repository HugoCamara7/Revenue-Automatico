# Rollout de cupones Best Wins a las 8 tiendas

Objetivo: que lo que ya funciona en Vans corra igual en Columbia, Rockford, Hushpuppies,
Bsoul, RKS Life, Keds y Supermall.

## 0. Que se replica y que no

- Este repo (Streamlit) **no contiene** la Function que corre en Vans. La carpeta
  `shopify.function/` es solo implementacion de referencia, y ademas tiene los nombres
  de archivo cruzados (ver seccion 6).
- Lo que hay que replicar tienda por tienda es la **app de Shopify CLI** que tiene
  desplegada la extension `compare-at-best-wins`.
- El codigo Python no cambia. Lo unico que cambia por tienda son los Secrets.

## 0.1 La carpeta `shopify_function_compare_at_best_wins/` no es desplegable

Tiene los 4 archivos correctos de referencia y el handle definitivo:

```toml
handle = "compare-at-best-wins"   # shopify.extension.toml, linea 5
```

Pero para que `shopify app deploy` la publique le falta lo que genera el CLI:

- `Cargo.toml` (el crate no existe, asi que no compila);
- el entrypoint real `#[shopify_function] fn run(input: ...) -> Result<FunctionRunResult>`;
- los bindings tipados que Shopify genera desde `input.graphql`;
- vivir dentro de un proyecto con `shopify.app.toml`, en `extensions/<nombre>/`.

`src/run.rs` solo tiene `calculate_best_wins_line`, y su propio comentario final lo dice:
es implementacion de referencia. **Falta el paso que arma el `ProductDiscountCandidate`
con `fixedAmount.amount = unit_discount` y devuelve `ProductDiscountSelectionStrategy::All`.**

Entonces, antes de tocar las otras tiendas hay que ubicar el proyecto del CLI desde el
cual se desplego la Function en Vans (el que si tiene `Cargo.toml` y `shopify.app.toml`).
Ese es el que se despliega en Columbia, Rockford y Hush Puppies. Si ese proyecto no
existe, el primer trabajo es crear la extension real:

```bash
shopify app generate extension --template discount_function
```

y mover ahi el calculo de `calculate_best_wins_line` mas el mapeo de cart lines.

## 1. La regla que decide todo el rollout

`discountCodeAppCreate` con `functionHandle` guarda la configuracion en el metafield
`$app:compare-at-best-wins`. El prefijo `$app:` se resuelve contra **la app que hace la
llamada**, y el handle de la Function tambien.

Entonces: **el `admin_access_token` de cada tienda tiene que pertenecer a la misma app
que tiene instalada la Discount Function en esa tienda.**

Consecuencia practica:

| Token | Price actual (`discountCodeBasicCreate`) | Compare At - Best Wins (`discountCodeAppCreate`) |
| --- | --- | --- |
| Custom app creada desde el Admin de la tienda | Funciona con `write_discounts` | **No funciona nunca** (esa app no tiene Functions) |
| Token de la app del CLI instalada en la tienda | Funciona | Funciona |

"Ya me pasaron los permisos" normalmente significa lo primero. Por eso el paso 2 es
verificar antes de tocar nada.

## 2. Paso 0: fotografia de Vans (5 minutos, solo lectura)

```bash
python diagnostico_multitienda.py --sitios vans
```

El script no crea ni borra nada: solo pregunta a Shopify quien es el token, que permisos
tiene y que Functions ve. Interesa la columna `App` y la columna `Function`.

- Si en Vans sale `App = <nombre de tu app del CLI>` y `Function = compare-at-best-wins`
  -> sigue con la seccion 3, hay que instalar esa misma app en las otras 7.
- Si en Vans sale un custom app del Admin y **aun asi** aparece la Function, avisame:
  cambia el plan y se simplifica (solo harian falta tokens + deploy por tienda).

Despues corre el diagnostico completo para ver el punto de partida de las 8:

```bash
python diagnostico_multitienda.py
```

Estados posibles por tienda:

- `LISTO (Best Wins)`: token valido + `write_discounts` + Function visible. Se puede lanzar.
- `SOLO PRECIO ACTUAL`: el token sirve para cupones normales, pero no ve la Function.
- `SIN CONFIGURAR`: falta `shop_domain` o `admin_access_token` en Secrets.
- `ERROR`: token invalido, tienda equivocada o faltan permisos. El detalle lo dice.

Para las tiendas pendientes el script imprime el bloque TOML exacto que hay que pegar en
Secrets, ya con el handle real que expone esa tienda.

## 2.1 De donde sale el handle (y por que no hay uno distinto por tienda)

El handle no lo asigna Shopify ni depende de la tienda: es el campo `handle` de
`shopify.extension.toml` de tu extension. Si despliegas la misma extension en las 8
tiendas, **el handle es el mismo en las 8** (en este repo: `compare-at-best-wins`).

Lo que si cambia por tienda es `shop_domain` y `admin_access_token`.

Si no recuerdas el valor, no hace falta buscarlo a mano: pon el `client_id` en Secrets y el
diagnostico lo resuelve solo. `shopifyFunctions` devuelve `appKey`, que es exactamente el
`client_id` de la app dueña de la Function, asi que aunque la tienda tenga Functions de
otras apps se elige la correcta y se imprime el handle real en el bloque de Secrets.

Si en una tienda `shopifyFunctions` vuelve vacio, **no falta el handle**: falta instalar o
desplegar la app en esa tienda. Ningun valor de handle va a funcionar hasta resolver eso.

## 2.2 Dos apps en la misma tienda (catalogo digital + app de cupones)

Si una tienda ya tenia un token (por ejemplo el de "catalogo digital") y ahora habilitaron
otro ("app cupones"), se pueden dejar los dos en Secrets, pero **la app usa uno solo**.

Dos reglas:

1. **Cuidado con la precedencia.** `get_shopify_config` lee
   `config.get("access_token") or config.get("admin_access_token")`: si dejas el token viejo
   bajo la clave `access_token`, ese gana y el de cupones se ignora en silencio. Nunca uses
   `access_token` para el token de catalogo.
2. **El que va en `admin_access_token` es el de la app dueña de la Function.** El de
   catalogo digital sirve para cupones de `Price actual`, pero no para Best Wins.

Para no adivinar cual es cual, el diagnostico prueba los dos:

```toml
[shopify_sites.columbia]
shop_domain = "columbiape.myshopify.com"
admin_access_token = "shpat_APP_CUPONES"
api_version = "2026-04"

[shopify_sites.columbia.tokens]
catalogo_digital = "shpat_TOKEN_VIEJO"

[shopify_sites.columbia.tokens.app_cupones]
admin_access_token = "shpat_APP_CUPONES"
client_id = "CLIENT_ID_DE_LA_APP_DE_CUPONES"
```

El bloque `tokens` **solo lo lee el diagnostico**, la app Streamlit lo ignora. La salida
muestra una fila por token y termina con una recomendacion concreta:

```text
Columbia.pe [catalogo_digital] | ... | Function: -                     | SOLO PRECIO ACTUAL
Columbia.pe [app_cupones]      | ... | Function: compare-at-best-wins  | LISTO (Best Wins)

Que token dejar en admin_access_token:
   - columbia: usa el token 'app_cupones' (es el unico que ve la Function 'compare-at-best-wins').
```

Si las dos filas salen `SOLO PRECIO ACTUAL`, ninguna de las dos apps tiene la Function
instalada en esa tienda: el problema no es el token ni el handle, es el deploy.

## 3. Elegir camino de distribucion

| Camino | Cuando | Costo | Tiempo |
| --- | --- | --- | --- |
| **A. Una app con custom distribution** | Si las 8 tiendas estan en la **misma organizacion Shopify Plus** | 1 app, 1 deploy | horas |
| **B. Una app por tienda** | Si las tiendas son cuentas sueltas o no son Plus | 7 apps, mismo codigo | 1-2 dias |
| **C. App publica / unlisted** | Solo si van a distribuirla fuera de Forus | Requiere revision de Shopify | semanas |

Custom distribution permite instalar la app en varias tiendas **de la misma organizacion
Plus**; fuera de eso es una tienda por app. Para lo urgente: camino A si aplica, si no
camino B. El camino C queda descartado por el tiempo de revision.

En el camino B no hay que duplicar codigo:

```bash
shopify app config link          # genera shopify.app.columbia.toml
shopify app deploy -c columbia
shopify app config link          # genera shopify.app.rockford.toml
shopify app deploy -c rockford
```

El `handle` de la extension sigue siendo `compare-at-best-wins` en todas, asi que los
Secrets quedan iguales salvo dominio y token.

## 4. Checklist por tienda (repetir 7 veces)

1. Crear/enlazar la app: `shopify app config link` (nombre sugerido: `Revenue Automatico - <marca>`).
2. Confirmar scopes en `shopify.app.<marca>.toml`: `write_discounts,read_discounts`.
3. `shopify app deploy -c <marca>` y publicar la version.
4. Instalar la app en la tienda con el link de custom distribution.
5. Guardar el `admin_access_token` de **esa** instalacion (no uno del Admin).
6. Pegar el bloque en Secrets (ver `secrets_multitienda_ejemplo.toml`).
7. `python diagnostico_multitienda.py --sitios <id>` hasta que diga `LISTO`.
8. Cupon de prueba con fecha futura, codigo `TEST-<MARCA>-BW`, y validar en carrito:
   - producto con `Compare At Price` -> el descuento sale del compare at;
   - producto sin `Compare At Price` -> cae al price actual;
   - producto con promocion vigente mejor que el cupon -> no baja mas el precio.
9. Recien ahi lanzar el cupon real desde la app.

## 5. Antes de disparar en 8 tiendas a la vez

- **Codigos repetidos**: si el codigo ya existe, la fila sale como `exists` y el proceso
  sigue con las demas. Revisa siempre la tabla de resultados.
- **Sin rollback**: si falla la tienda 5 de 8, las 4 primeras ya quedaron creadas. No hay
  deshacer automatico; hay que borrarlas a mano desde el Admin.
- **Horario**: `build_iso_datetime` fija `-05:00`. Correcto para Peru, ojo si algun dia
  entra una tienda de otro pais.
- **Ritmo de la API**: la creacion es secuencial (8 tiendas x N codigos). Para cargas
  masivas grandes conviene lanzar por tandas para no chocar con el limite de Shopify.
- **Combinaciones**: revisa `combinesWith` antes de un Cyber; un cupon que combina con
  descuentos de producto sobre precios ya rebajados puede regalar margen.

## 6. Hallazgos del repo (arreglar cuando se pueda)

1. **`context` con booleano**: `build_shopify_discount_payload` mandaba `{"all": True}`,
   pero en 2026-04 `context.all` es el enum `DiscountBuyerSelection` (unico valor `ALL`).
   Los cupones de `Price actual` fallarian con ese payload. Corregido en el
   `shopify_coupon_service.py` de esta entrega, con pruebas.
2. **Codigo muerto**: `render_coupon_builder` (app.py linea 1825) no lo llama nadie; el
   que corre es `render_coupon_builder_stable` (linea 2247, invocado en 2583). Riesgo real
   de editar el que no es y no ver cambios.
3. **Archivos cruzados en el repo**: `run.rs` contiene el TOML de la extension,
   `shopify.extension.toml` contiene el README, `shopify.function/input.graphql` contiene
   el Rust, `README (1).md` contiene el GraphQL, y hay dos archivos vacios llamados `md`.
   Conviene renombrarlos antes de que alguien mas los use como fuente.
4. **`functionId` esta deprecado** en 2026-04 y `functionHandle` es lo vigente: la app ya
   prefiere el handle, esta bien. El fallback a `functionId` se puede documentar o quitar.

## 7. Centro de Control (pagina nueva, sin tocar app.py)

`pages/1_Centro_de_control.py` va tal cual en la raiz del repo, dentro de una carpeta
`pages/`. Streamlit la detecta sola y la agrega al menu lateral: **no hay que modificar
`app.py` ni una linea**. Usa el mismo login (lee `st.session_state["authenticated"]`); si
alguien entra sin sesion, la pagina se bloquea.

Tres pestanas, todas de solo lectura:

1. **Estado de tiendas**: semaforo por tienda con token, permisos, app dueña del token y
   Function detectada. Incluye el bloque de Secrets sugerido para las que faltan. Esta es
   la pantalla para mostrarle a Chile que el circuito esta sano.
2. **Simulador Best Wins**: trae productos reales de la tienda y muestra como quedaria el
   precio con el cupon, cuantas variantes gana el cupon y cuantas gana la promocion
   vigente. Necesita `read_products` en la app; si falta, lo dice con ese nombre exacto.
3. **Verificar codigo**: busca un codigo en las 8 tiendas antes de crearlo, para no chocar
   con "code already exists" a mitad del lanzamiento.

## 8. Archivos de esta entrega

| Archivo | Que hace |
| --- | --- |
| `shopify_multisite.py` | Logica de diagnostico, sin Streamlit ni red (testeable) |
| `diagnostico_multitienda.py` | CLI que revisa las 8 tiendas y sugiere los Secrets |
| `shopify_coupon_service.py` | Reemplazo con el fix de `context` |
| `tests/test_shopify_multisite.py` | 29 pruebas nuevas |
| `secrets_multitienda_ejemplo.toml` | Plantilla de Secrets para las 8 tiendas |
| `BRIEF_TI_CHILE.md` | Mensaje + anexo tecnico para pedir la Function a TI Chile |
| `pages/1_Centro_de_control.py` | Panel visual multitienda (pagina nueva de Streamlit) |

Para correr todo:

```bash
python -m pytest tests/ -q
```
