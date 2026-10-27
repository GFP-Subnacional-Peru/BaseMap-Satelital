# Notebooks originales (versión 1 – Google Earth Engine)

Notebooks de Jupyter que dieron origen al toolbox. Se conservan como referencia; la versión actual
(`BaseMap_Satelites.pyt`) ya no depende de Google Earth Engine.

| Notebook | Satélite |
|---|---|
| `BaseMap_Landsat5_GEE.ipynb` | Landsat 5 |
| `BaseMap_Landsat7_GEE.ipynb` | Landsat 7 |
| `BaseMap_Landsat8_GEE.ipynb` | Landsat 8 |
| `BaseMap_Sentinel2_GEE.ipynb` | Sentinel-2 |

Para ejecutarlos se necesita una cuenta de Google Earth Engine y las librerías `earthengine-api`,
`geemap` y `geopandas`. Antes de usarlos reemplace:

- `TU-PROYECTO-GEE` por el ID de su proyecto de Earth Engine.
- `C:\ruta\a\tu\area_de_interes.shp` por la ruta de su shapefile.
