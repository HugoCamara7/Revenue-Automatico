# Matrixify Revenue

Aplicacion Streamlit rapida para generar cargas Matrixify de descuentos por campana/fecha.

## Flujo

1. Elegir sitio destino.
2. Elegir marcas a afectar.
3. Subir Revenue/input comercial.
4. Subir ultimo catalogo Matrixify del mismo sitio.
5. La app cruza `COD MOD COL` contra BigQuery para traer SKUs y marca.
6. Generar y descargar el Excel.

## Formato requerido del Revenue

Columnas minimas:

```text
Fila 1: Inicio | fecha/hora inicio campana 1 | fecha/hora inicio campana 2 | ...
Fila 2: Fin    | fecha/hora fin campana 1    | fecha/hora fin campana 2    | ...
Fila 3: Cod Mod Col | nombre campana 1 | nombre campana 2 | ...
```

Ejemplo:

```text
Inicio      | 2026-06-06 20:00 | 2026-06-15 10:00 | 2026-06-01 10:00
Fin         | 2026-06-07 23:59 | 2026-06-30 23:59 | 2026-06-30 23:59
Cod Mod Col | CLB 40           | SALE             | RESTO DEL MES
ABC123-001  | 40%              | 30%              | 0%
```

Reglas:

- El comercial solo debe mandar `COD MOD COL`.
- BigQuery es obligatorio: trae los SKUs/ID PRODUCTO y la marca asociados a cada modelo-color.
- Si eliges `COLUMBIA`, solo se cambian filas donde `MARCA` sea Columbia.
- Las otras marcas quedan en `No afectados por marca`.
- Si un `COD MOD COL` no existe en BigQuery, la app se detiene para corregir el input.
- Si un producto no existe en Matrixify queda en `No encontrados`.
- `Variant Compare At Price` solo se llena cuando hay descuento real.
- Si el descuento es 0% o vacio, se conserva precio original y compare queda vacio.
- `Product ID`, `Variant ID` e `Inventory Item ID` se conservan desde el ultimo Matrixify cargado.

## Validaciones

- Usa BigQuery para detectar la marca real de cada `COD MOD COL` y solo modifica las marcas seleccionadas.
- Genera hoja `Resumen`.
- Genera hoja `Descuentos por %`.
- Genera hoja `No encontrados` con codigos modelo-color unicos cuando algo no existe en Matrixify.
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

## BigQuery obligatorio para SKUs/MODCOL/MARCA

La app completa SKUs y marca desde ARTI/BigQuery usando `COD MOD COL`. Es obligatorio porque el Revenue comercial ya no necesita traer SKU ni marca.

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
