# Historial de versiones

## v2.0 – 27/10/2026

- Una sola herramienta para Sentinel-2 y Landsat 5, 7, 8 y 9 (se agrega Landsat 9).
- Ya no usa Google Earth Engine: imágenes desde el archivo abierto de Copernicus (AWS) y USGS
  Collection 2 (Microsoft Planetary Computer), sin cuentas ni librerías adicionales.
- Búsqueda por periodo (fecha de inicio y fecha de fin).
- Filtros de cobertura mínima del área y número máximo de fechas.
- Resolución de salida configurable (nativa, 20, 30, 60 y 100 m) y aviso para áreas grandes.
- Descarga en paralelo de las bandas, avance por banda y cada imagen se agrega al mapa al generarse.
- Salidas en reflectancia de superficie, GeoTIFF con pirámides internas, `resumen_escenas.csv` y visor web.
- Interfaz organizada por secciones y ayuda en cada parámetro.

## v1.0

- Cuatro notebooks de Google Earth Engine (Landsat 5, 7, 8 y Sentinel-2), disponibles en `notebooks_gee/`.
