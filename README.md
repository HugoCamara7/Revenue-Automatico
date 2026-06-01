# Matrixify Revenue

Aplicacion Streamlit rapida para generar cargas Matrixify de descuentos por campana/fecha.

## Flujo

1. Elegir sitio destino.
2. Elegir marcas a afectar.
3. Subir Revenue/input comercial.
4. Subir ultimo catalogo Matrixify del mismo sitio.
5. Generar y descargar el Excel.

## Formato requerido del Revenue

Columnas minimas:

```text
ID PRODUCTO
```

o, si el comercial trabaja por modelo-color:

```text
MODCOL
```

Columnas recomendadas cuando no se use BigQuery:

```text
ID PRODUCTO | MODCOL | MARCA | RESTO DEL MES | CLB 40 | 06 ABRIL
```

Reglas:

- `ID PRODUCTO` debe coincidir con `Variant SKU` de Matrixify.
- `MODCOL` puede venir solo; BigQuery trae los SKUs/ID PRODUCTO asociados a ese modelo-color.
- `MARCA` decide si el producto se puede modificar.
- Si `ID PRODUCTO`, `MODCOL` o `MARCA` faltan, la app puede completarlos desde BigQuery usando lo que el Revenue traiga.
- Si eliges `COLUMBIA`, solo se cambian filas donde `MARCA` sea Columbia.
- Las otras marcas quedan en `No afectados por marca`.
- Si un producto no existe en Matrixify queda en `No encontrados`.
- `Variant Compare At Price` solo se llena cuando hay descuento real.
- Si el descuento es 0% o vacio, se conserva precio original y compare queda vacio.
- `Product ID`, `Variant ID` e `Inventory Item ID` se conservan desde el ultimo Matrixify cargado.

## Validaciones

- Bloquea Matrixify de otro vendor cuando la columna `Vendor` permite validarlo.
- Genera hoja `Resumen`.
- Genera hoja `Descuentos por %`.
- Genera hoja `No encontrados`.
- Genera hoja `No afectados por marca`.

## Ejecutar local

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Aviso por correo

Opcionalmente la app puede enviar el Excel generado por correo al terminar.

En Streamlit Cloud, configura `Settings > Secrets`:

```toml
[email]
smtp_host = "smtp.office365.com"
smtp_port = "587"
smtp_user = "usuario@forus.com"
smtp_password = "PASSWORD_O_APP_PASSWORD"
from_email = "usuario@forus.com"
use_tls = "true"
use_ssl = "false"
```

Luego, en la app, abre `Aviso por correo` y escribe el correo destino antes de generar.

## BigQuery opcional para SKUs/MODCOL/MARCA

La app puede completar `ID PRODUCTO`, `MODCOL` y `MARCA` desde ARTI/BigQuery. Si el Revenue trae solo `MODCOL`, BigQuery trae todos los SKUs asociados y esos SKUs se cruzan contra `Variant SKU` del ultimo Matrixify.

Secrets minimos:

```toml
[bigquery]
enabled = true
project_id = "forus-pe-shared-prod-ti"
table = "forus-analitica-prod-datalake.bronze.stg_pe_central_arti"
location = "US"
id_column = "CODINT_MA"
modcol_column = "COD MOD COL"
brand_column = "MARCA_MA"
timeout_seconds = "45"
```

Si usas una cuenta de servicio:

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

## Dependencias

```text
pandas
openpyxl
streamlit
google-cloud-bigquery
google-auth
```
