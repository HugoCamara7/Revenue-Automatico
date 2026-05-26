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
ID PRODUCTO | MODCOL | MARCA
```

Luego agregar una columna por campana o fecha:

```text
ID PRODUCTO | MODCOL | MARCA | RESTO DEL MES | CLB 40 | 06 ABRIL
```

Reglas:

- `ID PRODUCTO` debe coincidir con `Variant SKU` de Matrixify.
- `MODCOL` sirve como respaldo para ubicar el modelo-color.
- `MARCA` decide si el producto se puede modificar.
- Si eliges `COLUMBIA`, solo se cambian filas donde `MARCA` sea Columbia.
- Las otras marcas quedan en `No afectados por marca`.
- Si un producto no existe en Matrixify queda en `No encontrados`.
- `Variant Compare At Price` solo se llena cuando hay descuento real.
- Si el descuento es 0% o vacio, se conserva precio original y compare queda vacio.

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

## Dependencias

```text
pandas
openpyxl
streamlit
```

No usa BigQuery.
