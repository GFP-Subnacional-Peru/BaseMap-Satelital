# BaseMap Satelital – Toolbox para ArcGIS Pro

Herramienta de geoprocesamiento para **ArcGIS Pro** que genera imágenes satelitales por fecha
(reflectancia de superficie) de **Sentinel-2** y **Landsat 5, 7, 8 y 9**, recortadas a un área de interés.

- Sin Google Earth Engine, sin cuentas de usuario y sin instalar librerías: usa solo lo que trae ArcGIS Pro.
- Busca por **periodo** (fecha de inicio y fecha de fin) y filtra por nubosidad y cobertura del área.
- Entrega GeoTIFF listos para el mapa, un resumen de escenas (CSV) y un visor web (HTML) para compartir.

Desarrollado por el **Programa GFP Subnacional** (Perú).

---

## Requisitos

| Requisito | Detalle |
|---|---|
| ArcGIS Pro | 3.x (probado con el Python 3.11 que incluye ArcGIS Pro) |
| Internet | Necesario durante la ejecución para consultar y descargar imágenes |
| Licencia | Cualquier nivel de ArcGIS Pro (Basic, Standard o Advanced) |

No requiere Google Earth Engine, ni cuentas de Copernicus o USGS, ni instalar paquetes de Python.

## Instalación

1. Descargue el ZIP de la última versión desde **[Releases](../../releases/latest)**
   (por ejemplo `BaseMap_Satelital_v2.0.zip`).
2. Descomprímalo en una carpeta de su equipo (por ejemplo `Documentos\Toolboxes\BaseMap_Satelital`).
   Los tres archivos deben quedar juntos:
   - `BaseMap_Satelites.pyt` (la herramienta)
   - `BaseMap_Satelites.pyt.xml` y `BaseMap_Satelites.BaseMapSatelital.pyt.xml` (ayuda de la herramienta)
3. En ArcGIS Pro: panel **Catalog** → clic derecho en **Toolboxes** → **Add Toolbox** → seleccione
   `BaseMap_Satelites.pyt`.
4. Abra **BaseMap Satelital → Generar BaseMap Satelital**.

> **Actualizar a una nueva versión:** reemplace los tres archivos por los del nuevo ZIP y, en Catalog,
> clic derecho en el toolbox → **Refresh**.

## Uso rápido

1. **Satélite**: elija Sentinel-2 (10 m) o Landsat 5/7/8/9 (30 m). Al cambiarlo se proponen fechas y
   combinación de bandas adecuadas.
2. **Área de interés**: capa o shapefile de polígonos (si hay selección, solo usa lo seleccionado).
3. **Fecha de inicio / Fecha de fin**: periodo de búsqueda.
4. **Carpeta de salida**: si se deja vacía se usa la carpeta del proyecto.
5. Clic en **Run**. Cada imagen se agrega al mapa apenas se genera.

### Parámetros

| Sección | Parámetro | Descripción |
|---|---|---|
| Principal | Satélite | Sentinel-2, Landsat 9, 8, 7 o 5 |
| | Área de interés | Polígonos en cualquier sistema de coordenadas |
| | Fecha de inicio / fin | Periodo de búsqueda (ambas fechas incluidas) |
| | Carpeta de salida | Dónde se crea la carpeta de resultados |
| Filtros de búsqueda | Nubosidad máxima (%) | Descarta escenas más nubosas |
| | Cobertura mínima del área (%) | Descarta fechas que cubren solo una parte del área (bordes de órbita) |
| | Número máximo de fechas | 0 = todas; si no, elige las menos nubosas |
| | Buffer (m) | Amplía el área antes de recortar (0 = exacto al polígono) |
| Bandas y resolución | Combinación de bandas | Color natural, falso color infrarrojo, vegetación, agricultura, etc. |
| | Exportar todas las bandas | Incluye todas las bandas espectrales en cada GeoTIFF |
| | Resolución de salida | Nativa, 20, 30, 60 o 100 m |
| Resultados | Agregar al mapa / Visor web | Opciones de visualización |

### Recomendación de resolución

| Tamaño del área (con buffer) | Resolución sugerida | Tiempo aproximado por fecha* |
|---|---|---|
| Hasta ~100 000 ha | Nativa (10 m S2 / 30 m Landsat) | < 1 min |
| 100 000 – 500 000 ha | 20 – 30 m | 1 – 3 min |
| Más de 500 000 ha | 30 – 60 m | ~1 min a 30 m (≈ 4 min a 10 m) |

\* Referencia: 906 000 ha con Sentinel-2 → 56 s a 30 m y 4 min 15 s a 10 m. Depende de la conexión.

## Resultados

Se crea una carpeta `Satélite_inicio_fin` (por ejemplo `Sentinel2_20260915_20261027`) con:

| Archivo | Contenido |
|---|---|
| `Sentinel2_AAAA-MM-DD.tif` | Reflectancia de superficie (0–1), Float32, NoData = −9999, UTM WGS 84, pirámides internas, compresión LERC sin pérdida significativa |
| `resumen_escenas.csv` | Todas las fechas encontradas: nubosidad, cobertura del área, escenas usadas y estado (generada o descartada) |
| `visor_*.html` + carpeta `visor/` | Visor web con cada fecha como capa sobre Esri World Imagery / OpenStreetMap |

## Fuentes de datos

| Satélite | Producto | Origen |
|---|---|---|
| Sentinel-2 | L2A (reflectancia de superficie) | Copernicus, archivo abierto en AWS – catálogo STAC [Earth Search](https://earth-search.aws.element84.com/v1) (Element 84) |
| Landsat 5, 7, 8, 9 | Collection 2 Level-2, Tier 1 (USGS) | [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/) |

Citas sugeridas:
- *Contains modified Copernicus Sentinel data [año].*
- *Landsat imagery courtesy of the U.S. Geological Survey.*

## Solución de problemas

| Situación | Qué hacer |
|---|---|
| La barra avanza lento con áreas grandes | Es normal: vea los mensajes («Rojo (B04) descargada…»). Use resolución 30 o 60 m |
| «No se encontraron imágenes…» | Amplíe el periodo o aumente la nubosidad máxima |
| «Ninguna fecha cubre al menos el X %…» | Reduzca la cobertura mínima o amplíe el periodo |
| «No se pudo consultar el catálogo…» | Revise la conexión a internet o el proxy institucional |
| Landsat 7 con franjas negras | Falla SLC-off del sensor desde junio de 2003 (no es un error de la herramienta) |
| La herramienta muestra opciones antiguas | En Catalog: clic derecho en el toolbox → **Refresh** |

## Estructura del repositorio

```
BaseMap-Satelital/
├── BaseMap_Satelites.pyt                       # Toolbox (herramienta)
├── BaseMap_Satelites.pyt.xml                   # Metadatos del toolbox
├── BaseMap_Satelites.BaseMapSatelital.pyt.xml  # Ayuda de cada parámetro
├── notebooks_gee/                              # Notebooks originales (versión 1, Google Earth Engine)
├── CHANGELOG.md
└── LICENSE
```

## Licencia

Distribuido bajo licencia MIT. Ver [LICENSE](LICENSE).
