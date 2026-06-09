# Matrixify Revenue

Aplicacion Streamlit rapida para generar cargas Matrixify de descuentos por campana/fecha.

## Flujo

1. Iniciar sesion.
2. Elegir modulo: `Carga de descuentos` o `Generar cupones`.
3. Elegir sitio destino.
4. Para descuentos, subir Revenue/input comercial y ultimo catalogo Matrixify.
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
- Cada hoja devuelve todo el ultimo Matrixify cargado, con la misma cantidad de filas.
- Solo se modifican los modelo-color indicados por el Revenue y validados por marca.
- `Variant Compare At Price` solo se llena cuando hay descuento real.
- Si el descuento del Revenue es 0%, se limpia el descuento de ese modelo-color: precio original y compare vacio.
- Los productos que no vienen en Revenue quedan exactamente como estaban en el Matrixify cargado.
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

## Login

Configura usuarios en `Secrets`:

```toml
[[auth.users_list]]
email = "hugo.camara@forus.pe"
password = "CONTRASENA_SEGURA"

[[auth.users_list]]
email = "rosa.terrones@forus.pe"
password = "CONTRASENA_SEGURA"
```

Tambien puedes usar una clave compartida:

```toml
[auth]
allowed_emails = ["hugo.camara@forus.pe"]
password = "CONTRASENA_SEGURA"
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

## Shopify API para cupones

Para crear cupones directamente en Shopify, configura un Custom App por tienda con permisos:

```text
write_discounts
read_discounts
read_customers / acceso a segmentos si se usaran grupos
```

Secrets por sitio:

```toml
[shopify.columbia]
shop_domain = "columbiape.myshopify.com"
access_token = "shpat_xxxxxxxxxxxxxxxxx"
api_version = "2026-04"

[shopify.rockford]
shop_domain = "rockfordpe.myshopify.com"
access_token = "shpat_xxxxxxxxxxxxxxxxx"
api_version = "2026-04"
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
