# Generador Matrixify Descuentos

Herramienta para cruzar una base Matrixify de 9 columnas con un archivo Revenue de descuentos por `ID PRODUCTO`.

## Que genera

- Una hoja por cada columna de descuento nueva encontrada en Revenue.
- Cruce por `Matrixify.Variant SKU` = `Revenue.ID PRODUCTO`.
- Cada hoja carga todo el catalogo Matrixify.
- Si un SKU tiene descuento, se aplica a todo el producto/modelo-color usando el `ID` del producto.
- Si un producto no tiene descuento, se mantiene con precio original.
- `Variant Price` queda como precio original con descuento.
- `Variant Compare At Price` queda como precio original solo cuando hay descuento; si no hay descuento queda vacio.
- Hoja `Resumen` con conteos de SKUs y filas generadas.
- Hoja `No encontrados` si hay SKUs en Revenue que no existen en Matrixify.

## Uso con ventana

```powershell
python generar_matrixify_descuentos.py --gui
```

## Uso por consola

```powershell
python generar_matrixify_descuentos.py `
  --matrixify "C:\ruta\Export.xlsx" `
  --revenue "C:\ruta\REVENUE.xlsx" `
  --output "C:\ruta\matrixify_descuentos.xlsx"
```

## Regla de descuentos

La herramienta lee columnas tipo `DCTO ANT`, `NUEVO DCTO` o `DESCUENTO`, y toma el nombre de la hoja desde las filas superiores de fecha/campana.

Ejemplo:

- `RESTO DEL MES - DCTO ANT`
- `26.05 (17:00 A 23:00) - CLB40 - NUEVO DCTO`

## App Streamlit

Instala dependencias:

```powershell
pip install -r requirements.txt
```

Ejecuta la app:

```powershell
streamlit run app.py
```

En la pantalla cargas:

- Sitio destino.
- Matrixify base.
- Revenue con descuentos.

Luego presionas `Generar archivo Matrixify` y descargas el Excel final.

## Salidas por sitio

- Rockford.pe: `matrixify_revenue_rockford.xlsx`
- Columbia.pe: `matrixify_revenue_columbia.xlsx`
- Hushpuppies.pe: `matrixify_revenue_hushpuppies.xlsx`
- Vans.pe: `matrixify_revenue_vans.xlsx`
- Supermall.pe: `matrixify_revenue_supermall.xlsx`

## Vista previa comercial

Antes de descargar el archivo, la app muestra:

- cargas detectadas;
- cod MODCOL / productos afectados;
- variantes Matrixify afectadas;
- resumen por carga;
- distribucion por porcentaje de descuento.

## Secrets BigQuery

Usa el mismo formato de la app Matrixify. En Streamlit, entra a `Manage app > Settings > Secrets` y pega:

```toml
[bigquery]
enabled = true
project_id = "forus-pe-shared-prod-ti"
table = "forus-analitica-prod-datalake.bronze.stg_pe_central_arti"
location = "US"
id_column = "CODINT_MA"
modcol_column = "COD MOD COL"
brand_column = "MARCA_MA"
lookup_strategy = "brand"
timeout_seconds = "35"

[gcp_service_account]
type = "service_account"
project_id = "TU_PROJECT_ID"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

La estrategia `lookup_strategy = "brand"` sigue el mismo enfoque del app Matrixify: BigQuery trae las columnas clave filtradas por marca y la app cruza los codigos del input en memoria. Suele ser mas rapido que enviar miles de IDs como parametro.

Tambien puedes usar `query` en vez de `table`:

```toml
[bigquery]
enabled = "true"
project_id = "TU_PROJECT_ID"
query = """
SELECT
  CODINT_MA,
  `COD MOD COL`,
  MARCA_MA
FROM `proyecto.dataset.tabla`
"""
location = "US"
id_column = "CODINT_MA"
modcol_column = "COD MOD COL"
brand_column = "MARCA_MA"
timeout_seconds = "90"
```

La app filtra BigQuery por los IDs/MODCOL del input y por las marcas elegidas en el sidebar. Para que cargue rapido, la consulta debe traer solo estas columnas clave: producto (`CODINT_MA`), modelo-color (`COD MOD COL`) y marca (`MARCA_MA` o la columna real de marca que configures en `brand_column`).
