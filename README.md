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
enabled = "true"
project_id = "TU_PROJECT_ID"
dataset = "TU_DATASET"
table = "TU_TABLA"
location = "US"

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

Tambien puedes usar `query` en vez de `dataset/table`:

```toml
[bigquery]
enabled = "true"
project_id = "TU_PROJECT_ID"
query = """
SELECT
  CODINT_MA,
  `COD MOD COL`,
  MARCA
FROM `proyecto.dataset.tabla`
"""
location = "US"
```

La consulta debe traer al menos una llave de producto (`CODINT_MA`, `ID_PRODUCTO`, `SKU` o `COD MOD COL`) y una columna de marca (`MARCA` o `brand`).
