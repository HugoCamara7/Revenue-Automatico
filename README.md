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

## Formato comercial requerido

Esta version no usa BigQuery. La marca debe venir en el Revenue/input comercial para que la app pueda filtrar de forma segura.

Columnas minimas recomendadas:

```text
ID PRODUCTO
MODCOL
MARCA
```

Despues de esas columnas puedes agregar las campanas/fechas de descuento, por ejemplo:

```text
ID PRODUCTO | MODCOL | MARCA | RESTO DEL MES | CLB 40 | 06 ABRIL
```

Si eliges `COLUMBIA` en `Marcas a afectar`, solo se cambian las filas del input donde `MARCA` sea Columbia. Las otras marcas quedan reportadas en la hoja `No afectados por marca`.
