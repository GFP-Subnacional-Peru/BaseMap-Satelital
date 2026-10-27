# -*- coding: utf-8 -*-
"""
BaseMap Satelital - Toolbox para ArcGIS Pro

Genera una imagen por fecha (reflectancia de superficie) de Landsat 5/7/8/9 o Sentinel-2 para un
area de interes, sin Google Earth Engine y sin cuentas de usuario:
  - Sentinel-2 L2A: archivo abierto de Copernicus en AWS (catalogo STAC Earth Search).
  - Landsat Collection 2 Level-2 (USGS): copia de Microsoft Planetary Computer.

Solo usa librerias incluidas en ArcGIS Pro (arcpy, numpy, requests y GDAL); no requiere instalar nada.
"""
import csv
import datetime as _dt
import json
import math
import os
import time

import arcpy

VERSION = "2.0"

STAC_SENTINEL = "https://earth-search.aws.element84.com/v1/search"
COLECCION_SENTINEL = "sentinel-2-l2a"
STAC_LANDSAT = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
COLECCION_LANDSAT = "landsat-c2-l2"
TOKEN_LANDSAT = "https://planetarycomputer.microsoft.com/api/sas/v1/token/" + COLECCION_LANDSAT

NODATA = -9999.0
USER_AGENT = f"BaseMapSatelital-ArcGISPro/{VERSION}"

_BANDAS_L57 = [("blue", "B1", "Azul"), ("green", "B2", "Verde"), ("red", "B3", "Rojo"),
               ("nir08", "B4", "Infrarrojo cercano"), ("swir16", "B5", "SWIR 1"), ("swir22", "B7", "SWIR 2")]
_BANDAS_L89 = [("coastal", "B1", "Costero/aerosol"), ("blue", "B2", "Azul"), ("green", "B3", "Verde"),
               ("red", "B4", "Rojo"), ("nir08", "B5", "Infrarrojo cercano"), ("swir16", "B6", "SWIR 1"),
               ("swir22", "B7", "SWIR 2")]
_BANDAS_S2 = [("blue", "B02", "Azul"), ("green", "B03", "Verde"), ("red", "B04", "Rojo"),
              ("rededge1", "B05", "Borde rojo 1"), ("rededge2", "B06", "Borde rojo 2"),
              ("rededge3", "B07", "Borde rojo 3"), ("nir", "B08", "Infrarrojo cercano"),
              ("nir08", "B8A", "Infrarrojo cercano estrecho"), ("swir16", "B11", "SWIR 1"),
              ("swir22", "B12", "SWIR 2")]

COMBINACIONES = {
    "Color natural (Rojo, Verde, Azul)": ("rojo", "verde", "azul"),
    "Falso color infrarrojo (NIR, Rojo, Verde)": ("nir", "rojo", "verde"),
    "Vegetación y suelo desnudo (SWIR1, NIR, Rojo)": ("swir1", "nir", "rojo"),
    "Realce de vegetación (Rojo, NIR, Verde)": ("rojo", "nir", "verde"),
    "Agricultura y deforestación (SWIR1, NIR, Azul)": ("swir1", "nir", "azul"),
}
_COMB_NATURAL, _COMB_IR, _COMB_SWIR, _COMB_VEG, _COMB_AGRI = list(COMBINACIONES)

SATELITES = {
    "L5": dict(label="Landsat 5 TM", prefijo="Landsat5", fuente="landsat", plataforma="landsat-5", res=30,
               bandas=_BANDAS_L57, nir="nir08", periodo_def=("2009-01-01", "2009-12-31"),
               rango=(_dt.date(1984, 3, 16), _dt.date(2012, 5, 5)), comb_def=_COMB_SWIR,
               nota="Landsat 5 TM operó de 1984 a 2012."),
    "L7": dict(label="Landsat 7 ETM+", prefijo="Landsat7", fuente="landsat", plataforma="landsat-7", res=30,
               bandas=_BANDAS_L57, nir="nir08", periodo_def=("2011-01-01", "2011-12-31"),
               rango=(_dt.date(1999, 5, 28), _dt.date(2024, 1, 19)), comb_def=_COMB_SWIR,
               nota="Desde junio de 2003 Landsat 7 presenta franjas sin datos (falla SLC-off)."),
    "L8": dict(label="Landsat 8 OLI", prefijo="Landsat8", fuente="landsat", plataforma="landsat-8", res=30,
               bandas=_BANDAS_L89, nir="nir08", dias_def=90,
               rango=(_dt.date(2013, 3, 18), None), comb_def=_COMB_NATURAL, nota=""),
    "L9": dict(label="Landsat 9 OLI-2", prefijo="Landsat9", fuente="landsat", plataforma="landsat-9", res=30,
               bandas=_BANDAS_L89, nir="nir08", dias_def=90,
               rango=(_dt.date(2021, 10, 31), None), comb_def=_COMB_NATURAL, nota=""),
    "S2": dict(label="Sentinel-2 MSI", prefijo="Sentinel2", fuente="sentinel", plataforma=None, res=10,
               bandas=_BANDAS_S2, nir="nir", dias_def=30,
               rango=(_dt.date(2017, 3, 28), None), comb_def=_COMB_VEG, nota=""),
}

OPCIONES_SATELITE = {
    "Sentinel-2 · 10 m · 2017 a la fecha": "S2",
    "Landsat 9 · 30 m · 2021 a la fecha": "L9",
    "Landsat 8 · 30 m · 2013 a la fecha": "L8",
    "Landsat 7 · 30 m · 1999 a 2024": "L7",
    "Landsat 5 · 30 m · 1984 a 2012": "L5",
}
SATELITE_DEF = "Sentinel-2 · 10 m · 2017 a la fecha"

RESOLUCIONES = {
    "Nativa del sensor (Sentinel-2: 10 m, Landsat: 30 m)": None,
    "20 m": 20,
    "30 m": 30,
    "60 m (áreas grandes)": 60,
    "100 m (vista regional)": 100,
}
RESOLUCION_DEF = "Nativa del sensor (Sentinel-2: 10 m, Landsat: 30 m)"

FUENTES = {
    "sentinel": "Copernicus Sentinel-2 L2A (archivo abierto en AWS, catálogo Earth Search)",
    "landsat": "USGS Landsat Collection 2 Level-2 (Microsoft Planetary Computer)",
}


def _clave(texto):
    return OPCIONES_SATELITE.get(texto or SATELITE_DEF, "S2")


def _a_fecha(valor):
    if isinstance(valor, _dt.datetime):
        return valor.date()
    if isinstance(valor, _dt.date):
        return valor
    return _dt.datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()


def _periodo_def(cfg):
    if cfg.get("periodo_def"):
        ini, fin = (_dt.datetime.strptime(x, "%Y-%m-%d") for x in cfg["periodo_def"])
        return ini, fin
    hoy = _dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return hoy - _dt.timedelta(days=cfg["dias_def"]), hoy


def _asset_rol(cfg, rol):
    return {"azul": "blue", "verde": "green", "rojo": "red", "nir": cfg["nir"],
            "swir1": "swir16", "swir2": "swir22"}[rol]


def _carpeta_proyecto():
    try:
        return arcpy.mp.ArcGISProject("CURRENT").homeFolder
    except Exception:
        return None


def _carpeta_por_defecto(capa):
    carpeta = _carpeta_proyecto()
    if carpeta:
        return carpeta
    try:
        carpeta = os.path.dirname(arcpy.Describe(capa).catalogPath)
        while carpeta and (".gdb" in carpeta.lower() or ".sde" in carpeta.lower()):
            carpeta = os.path.dirname(carpeta)
        if carpeta and os.path.isdir(carpeta):
            return carpeta
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _cancelado():
    return bool(getattr(arcpy.env, "isCancelled", False))


# --------------------------------------------------------------------------------------------
# Servicios
# --------------------------------------------------------------------------------------------
def _sesion():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    reintentos = Retry(total=5, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                       allowed_methods=frozenset(["GET", "POST"]))
    s.mount("https://", HTTPAdapter(max_retries=reintentos))
    return s


def _buscar_stac(sesion, url, cuerpo):
    items, vistos = [], set()
    metodo, destino, datos = "POST", url, cuerpo
    for _ in range(100):
        if metodo == "POST":
            r = sesion.post(destino, json=datos, timeout=120)
        else:
            r = sesion.get(destino, timeout=120)
        r.raise_for_status()
        pagina = r.json()
        for f in pagina.get("features", []):
            if f["id"] not in vistos:
                vistos.add(f["id"])
                items.append(f)
        sig = next((l for l in pagina.get("links", []) if l.get("rel") == "next"), None)
        if not sig or not pagina.get("features"):
            break
        if sig.get("method", "GET").upper() == "POST":
            datos = dict(cuerpo)
            datos.update(sig.get("body") or {})
            metodo, destino = "POST", sig["href"]
        else:
            metodo, destino, datos = "GET", sig["href"], None
    return items


class _FirmaLandsat(object):
    """Token SAS anonimo de Planetary Computer, renovado antes de expirar."""

    def __init__(self, sesion):
        self._s = sesion
        self._token = None
        self._expira = 0.0

    def __call__(self):
        if self._token is None or time.time() > self._expira - 300:
            r = self._s.get(TOKEN_LANDSAT, timeout=60)
            r.raise_for_status()
            d = r.json()
            self._token = d["token"]
            try:
                exp = _dt.datetime.strptime(d["msft:expiry"][:19], "%Y-%m-%dT%H:%M:%S")
                self._expira = exp.replace(tzinfo=_dt.timezone.utc).timestamp()
            except Exception:
                self._expira = time.time() + 1800
        return self._token


def _buscar_escenas(sesion, cfg, bbox, inicio, fin, nubes):
    rango = f"{inicio:%Y-%m-%d}T00:00:00Z/{fin:%Y-%m-%d}T23:59:59Z"
    if cfg["fuente"] == "sentinel":
        cuerpo = {"collections": [COLECCION_SENTINEL], "bbox": bbox, "datetime": rango, "limit": 100,
                  "query": {"eo:cloud_cover": {"lte": nubes}}}
        items = _buscar_stac(sesion, STAC_SENTINEL, cuerpo)
        for it in items:
            it["_nubes"] = float(it["properties"].get("eo:cloud_cover", 0) or 0)
        return [it for it in items if it["_nubes"] <= nubes]

    cuerpo = {"collections": [COLECCION_LANDSAT], "bbox": bbox, "datetime": rango, "limit": 100,
              "query": {"platform": {"in": [cfg["plataforma"]]}}}
    items = _buscar_stac(sesion, STAC_LANDSAT, cuerpo)
    salida = []
    for it in items:
        p = it["properties"]
        if p.get("platform") != cfg["plataforma"] or p.get("landsat:collection_category", "T1") != "T1":
            continue
        n = p.get("landsat:cloud_cover_land")
        if n is None or n < 0:
            n = p.get("eo:cloud_cover", 0)
        it["_nubes"] = float(n or 0)
        if it["_nubes"] <= nubes:
            salida.append(it)
    return salida


# --------------------------------------------------------------------------------------------
# Geometria y grilla
# --------------------------------------------------------------------------------------------
def _preparar_aoi(capa, buffer_m):
    sr_wgs = arcpy.SpatialReference(4326)
    geoms = []
    with arcpy.da.SearchCursor(capa, ["SHAPE@"]) as cur:
        for (g,) in cur:
            if g is not None and g.area > 0:
                geoms.append(g)
    if not geoms:
        raise ValueError("El área de interés no tiene polígonos (revise la selección o la capa).")
    sr_in = geoms[0].spatialReference
    if sr_in is None or not sr_in.name or sr_in.name.lower() == "unknown":
        raise ValueError("El área de interés no tiene sistema de coordenadas definido.")

    union = geoms[0]
    for g in geoms[1:]:
        union = union.union(g)
    trans = arcpy.ListTransformations(sr_in, sr_wgs)
    g_wgs = union.projectAs(sr_wgs, trans[0]) if trans else union.projectAs(sr_wgs)

    c = g_wgs.centroid
    epsg = (32700 if c.Y < 0 else 32600) + int((c.X + 180) // 6) + 1
    sr_utm = arcpy.SpatialReference(epsg)
    original_utm = g_wgs.projectAs(sr_utm)
    aoi_utm = original_utm.buffer(buffer_m) if buffer_m > 0 else original_utm
    aoi_wgs = aoi_utm.projectAs(sr_wgs)
    return {
        "epsg": epsg, "zona": sr_utm.name, "utm": aoi_utm, "wgs": aoi_wgs, "original_wgs": g_wgs,
        "area_original_ha": original_utm.area / 1e4, "area_ha": aoi_utm.area / 1e4,
        "bbox": [aoi_wgs.extent.XMin, aoi_wgs.extent.YMin, aoi_wgs.extent.XMax, aoi_wgs.extent.YMax],
    }


def _srs(epsg):
    from osgeo import osr
    s = osr.SpatialReference()
    s.ImportFromEPSG(epsg)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def _agrupar_por_fecha(items, aoi_utm, epsg):
    """Agrupa escenas por fecha y calcula la cobertura del area de interes con sus huellas."""
    from osgeo import ogr, osr

    ct = osr.CoordinateTransformation(_srs(4326), _srs(epsg))
    aoi = ogr.CreateGeometryFromWkt(aoi_utm.WKT)
    area = aoi.Area()
    fechas = {}
    for it in items:
        try:
            g = ogr.CreateGeometryFromJson(json.dumps(it["geometry"]))
            g.Transform(ct)
            if not g.IsValid():
                g = g.Buffer(0)
            if not g.Intersects(aoi):
                continue
        except Exception:
            continue
        it["_huella"] = g
        fechas.setdefault(it["properties"]["datetime"][:10], []).append(it)

    grupos = []
    for fecha, escenas in sorted(fechas.items()):
        union = None
        for it in escenas:
            union = it["_huella"].Clone() if union is None else union.Union(it["_huella"])
        cobertura = 100.0 * aoi.Intersection(union).Area() / area if area else 0.0
        grupos.append({
            "fecha": fecha, "escenas": escenas, "cobertura": min(cobertura, 100.0),
            "nubes": sum(it["_nubes"] for it in escenas) / len(escenas),
        })
    return grupos


def _grilla(aoi, res):
    from osgeo import gdal, ogr

    ext = aoi["utm"].extent
    xmin = math.floor(ext.XMin / res) * res
    ymin = math.floor(ext.YMin / res) * res
    xmax = math.ceil(ext.XMax / res) * res
    ymax = math.ceil(ext.YMax / res) * res
    w, h = int(round((xmax - xmin) / res)), int(round((ymax - ymin) / res))
    srs = _srs(aoi["epsg"])

    ds = gdal.GetDriverByName("MEM").Create("", w, h, 1, gdal.GDT_Byte)
    ds.SetGeoTransform((xmin, res, 0, ymax, 0, -res))
    ds.SetProjection(srs.ExportToWkt())
    vec = ogr.GetDriverByName("Memory").CreateDataSource("aoi")
    capa = vec.CreateLayer("aoi", srs, ogr.wkbMultiPolygon)
    f = ogr.Feature(capa.GetLayerDefn())
    f.SetGeometry(ogr.CreateGeometryFromWkt(aoi["utm"].WKT))
    capa.CreateFeature(f)
    gdal.RasterizeLayer(ds, [1], capa, burn_values=[1], options=["ALL_TOUCHED=TRUE"])
    mascara = ds.GetRasterBand(1).ReadAsArray().astype(bool)
    return {"bounds": (xmin, ymin, xmax, ymax), "w": w, "h": h, "res": res,
            "gt": (xmin, res, 0, ymax, 0, -res), "wkt": srs.ExportToWkt(), "mascara": mascara}


# --------------------------------------------------------------------------------------------
# Lectura y escritura de imagenes
# --------------------------------------------------------------------------------------------
_CONFIG_GDAL = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GDAL_HTTP_TIMEOUT": "120",
    "GDAL_HTTP_USERAGENT": USER_AGENT,
    "VSI_CACHE": "TRUE",
    "TIFF_USE_OVR": "NO",
}


def _leer_banda(hrefs, grilla, remuestreo):
    from osgeo import gdal

    ultimo = None
    for intento in range(3):
        try:
            ds = gdal.Warp("", ["/vsicurl/" + h for h in hrefs], format="MEM", dstSRS=grilla["wkt"],
                           outputBounds=grilla["bounds"], width=grilla["w"], height=grilla["h"],
                           resampleAlg=remuestreo, srcNodata=0, dstNodata=0, multithread=True,
                           warpOptions=["NUM_THREADS=ALL_CPUS"])
            if ds is None:
                raise RuntimeError(gdal.GetLastErrorMsg() or "lectura vacía")
            arr = ds.GetRasterBand(1).ReadAsArray()
            ds = None
            return arr
        except Exception as ex:
            ultimo = ex
            time.sleep(3 * (intento + 1))
    nombre = hrefs[0].split("?")[0].rsplit("/", 1)[-1]
    raise RuntimeError(f"no se pudo leer {nombre}: {ultimo}")


def _escala_offset(cfg, item, meta):
    rb = (meta.get("raster:bands") or [{}])[0]
    if cfg["fuente"] == "landsat":
        escala, offset = rb.get("scale", 2.75e-05), rb.get("offset", -0.2)
    else:
        escala, offset = rb.get("scale", 1e-4), rb.get("offset", 0.0)
        # Earth Search already subtracted the 1000 DN BOA offset (baseline >= 04.00) but still
        # advertises offset -0.1 in raster:bands.
        if item["properties"].get("earthsearch:boa_offset_applied"):
            offset = 0.0
    return float(escala), float(offset), rb.get("spatial_resolution")


def _remuestreo(res_nativa, res_salida):
    if not res_nativa or float(res_nativa) == res_salida:
        return "near"
    return "bilinear" if res_salida < float(res_nativa) else "average"


def _componer_fecha(cfg, grupo, assets, grilla, firmar, al_terminar_banda):
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor, as_completed

    token = firmar() if firmar else ""

    def leer(asset):
        banda = np.full((grilla["h"], grilla["w"]), NODATA, dtype="float32")
        lotes = {}
        for it in grupo["escenas"]:
            meta = it["assets"].get(asset)
            if not meta:
                continue
            escala, offset, res_nat = _escala_offset(cfg, it, meta)
            href = meta["href"]
            if token:
                href += ("&" if "?" in href else "?") + token
            lotes.setdefault((escala, offset, _remuestreo(res_nat, grilla["res"])), []).append(href)
        for (escala, offset, remuestreo), hrefs in lotes.items():
            dn = _leer_banda(hrefs, grilla, remuestreo)
            libre = (dn > 0) & (banda == NODATA)
            banda[libre] = dn[libre].astype("float32") * np.float32(escala) + np.float32(offset)
            del dn, libre
        return banda

    cubo = np.empty((len(assets), grilla["h"], grilla["w"]), dtype="float32")
    with ThreadPoolExecutor(max_workers=min(len(assets), 4)) as pool:
        tareas = {pool.submit(leer, a): bi for bi, a in enumerate(assets)}
        for t in as_completed(tareas):
            bi = tareas[t]
            cubo[bi] = t.result()
            al_terminar_banda(assets[bi])

    invalido = (cubo == NODATA).any(axis=0) | ~grilla["mascara"]
    cubo[:, invalido] = NODATA
    n_aoi = int(grilla["mascara"].sum())
    pct = 100.0 * (n_aoi - int((invalido & grilla["mascara"]).sum())) / n_aoi if n_aoi else 0.0
    return cubo, pct


def _escribir_tif(ruta, cubo, grilla, descripciones, metadatos, precision):
    from osgeo import gdal

    # Write straight to GTiff: in ArcGIS Pro's GDAL 3.9.2e, copying a MEM dataset that has a nodata
    # value (Translate/CreateCopy) returns every pixel as nodata.
    # LERC tolerance = half the sensor quantization step, so source values are preserved.
    ds = gdal.GetDriverByName("GTiff").Create(
        ruta, grilla["w"], grilla["h"], cubo.shape[0], gdal.GDT_Float32,
        options=["COMPRESS=LERC_DEFLATE", f"MAX_Z_ERROR={precision / 2:.8f}", "TILED=YES", "BIGTIFF=IF_SAFER"])
    ds.SetGeoTransform(grilla["gt"])
    ds.SetProjection(grilla["wkt"])
    ds.SetMetadata(metadatos)
    for i in range(cubo.shape[0]):
        b = ds.GetRasterBand(i + 1)
        b.SetNoDataValue(NODATA)
        b.WriteArray(cubo[i])
        b.SetDescription(descripciones[i])
    ds.FlushCache()
    ds = None

    niveles = [f for f in (2, 4, 8, 16, 32) if min(grilla["w"], grilla["h"]) / f >= 128]
    if niveles:
        ds = gdal.Open(ruta, gdal.GA_Update)
        ds.BuildOverviews("AVERAGE", niveles, options=["COMPRESS_OVERVIEW=DEFLATE"])
        ds = None


# --------------------------------------------------------------------------------------------
# Visor web
# --------------------------------------------------------------------------------------------
def _png_visor(tif, indices, png):
    import numpy as np
    from osgeo import gdal, osr

    vrt = gdal.Translate("", tif, format="VRT", bandList=list(indices))
    lado_max = 2500
    escala = min(1.0, lado_max / max(vrt.RasterXSize, vrt.RasterYSize))
    ds = gdal.Warp("", vrt, format="MEM", dstSRS="EPSG:3857", srcNodata=NODATA, dstNodata=NODATA,
                   width=max(1, int(vrt.RasterXSize * escala)), height=max(1, int(vrt.RasterYSize * escala)),
                   resampleAlg="average" if escala < 1 else "bilinear")
    bandas = [ds.GetRasterBand(i + 1).ReadAsArray() for i in range(3)]
    valido = np.all([b != NODATA for b in bandas], axis=0)
    rgba = np.zeros((4, ds.RasterYSize, ds.RasterXSize), dtype="uint8")
    for i, b in enumerate(bandas):
        v = b[valido]
        if v.size:
            lo, hi = np.percentile(v, (2, 98))
            rgba[i] = (np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1) * 255).astype("uint8")
    rgba[3] = np.where(valido, 255, 0)

    mem = gdal.GetDriverByName("MEM").Create("", ds.RasterXSize, ds.RasterYSize, 4, gdal.GDT_Byte)
    for i in range(4):
        mem.GetRasterBand(i + 1).WriteArray(rgba[i])
    gdal.GetDriverByName("PNG").CreateCopy(png, mem)
    aux = png + ".aux.xml"
    if os.path.exists(aux):
        os.remove(aux)

    gt = ds.GetGeoTransform()
    x0, y0 = gt[0], gt[3]
    x1, y1 = x0 + gt[1] * ds.RasterXSize, y0 + gt[5] * ds.RasterYSize
    ct = osr.CoordinateTransformation(_srs(3857), _srs(4326))
    lon0, lat0, _ = ct.TransformPoint(x0, y1)
    lon1, lat1, _ = ct.TransformPoint(x1, y0)
    return [[lat0, lon0], [lat1, lon1]]


_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #mapa { height: 100%; margin: 0; font-family: "Segoe UI", Arial, sans-serif; }
  .ficha { position: absolute; top: 12px; left: 56px; z-index: 1000; background: rgba(255,255,255,.95);
           padding: 10px 14px; border-radius: 6px; box-shadow: 0 1px 6px rgba(0,0,0,.35); font-size: 12px;
           max-width: 360px; line-height: 1.45; }
  .ficha h1 { font-size: 15px; margin: 0 0 4px; color: #1f3b57; }
  .ficha span { color: #555; }
</style>
</head>
<body>
<div id="mapa"></div>
<div class="ficha"><h1>__TITULO__</h1>__FICHA__</div>
<script>
const mapa = L.map("mapa");
const esri = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {attribution: "Esri World Imagery", maxZoom: 19}).addTo(mapa);
const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  {attribution: "&copy; OpenStreetMap", maxZoom: 19});
const capas = __CAPAS__;
const superpuestas = {};
capas.forEach((c, i) => {
  const capa = L.imageOverlay(c.png, c.bounds);
  superpuestas[c.nombre] = capa;
  if (i === capas.length - 1) capa.addTo(mapa);
});
const area = L.geoJSON(__AOI__, {style: {color: "#ffd400", weight: 2, fill: false}}).addTo(mapa);
const buffer = L.geoJSON(__BUFFER__, {style: {color: "#ff3b30", weight: 1.5, dashArray: "6 4", fill: false}}).addTo(mapa);
superpuestas["Área de interés"] = area;
superpuestas["Buffer"] = buffer;
L.control.layers({"Esri World Imagery": esri, "OpenStreetMap": osm}, superpuestas, {collapsed: false}).addTo(mapa);
L.control.scale({imperial: false}).addTo(mapa);
mapa.fitBounds(buffer.getBounds());
</script>
</body>
</html>
"""


def _escribir_visor(ruta, titulo, ficha, capas, aoi):
    html = (_HTML.replace("__TITULO__", titulo).replace("__FICHA__", ficha)
            .replace("__CAPAS__", json.dumps(capas, ensure_ascii=False))
            .replace("__AOI__", json.dumps(aoi["original_wgs"].__geo_interface__))
            .replace("__BUFFER__", json.dumps(aoi["wgs"].__geo_interface__)))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)


# --------------------------------------------------------------------------------------------
# Mapa de ArcGIS Pro
# --------------------------------------------------------------------------------------------
def _mapa_activo():
    try:
        mapa = arcpy.mp.ArcGISProject("CURRENT").activeMap
    except Exception:
        arcpy.AddWarning("No hay un proyecto de ArcGIS Pro abierto; las imágenes no se agregarán al mapa.")
        return None
    if mapa is None:
        arcpy.AddWarning("No hay un mapa activo; abra un mapa para agregar las imágenes.")
    return mapa


def _agregar_al_mapa(mapa, tif, indices_rgb):
    try:
        capa = mapa.addDataFromPath(tif)
        if tuple(indices_rgb) != (1, 2, 3):
            cim = capa.getDefinition("V3")
            col = cim.colorizer
            col.redBandIndex, col.greenBandIndex, col.blueBandIndex = [i - 1 for i in indices_rgb]
            capa.setDefinition(cim)
        return True
    except Exception as ex:
        arcpy.AddWarning(f"No se pudo agregar {os.path.basename(tif)} al mapa: {ex}")
        return False


# --------------------------------------------------------------------------------------------
# Proceso principal
# --------------------------------------------------------------------------------------------
def generar_basemap(clave, capa, inicio, fin, nubes, cobertura_min, max_fechas, buffer_m,
                    combinacion, todas_bandas, carpeta, agregar_mapa, visor, abrir_visor, resolucion=None):
    from osgeo import gdal

    cfg = SATELITES[clave]
    res = float(resolucion) if resolucion else float(cfg["res"])
    inicio, fin = _a_fecha(inicio), _a_fecha(fin)
    t0 = time.time()

    arcpy.AddMessage(f"BaseMap Satelital v{VERSION}")
    arcpy.AddMessage(f"  Satélite : {cfg['label']}")
    arcpy.AddMessage(f"  Fuente   : {FUENTES[cfg['fuente']]}")
    arcpy.AddMessage(f"  Periodo  : {inicio:%d/%m/%Y} – {fin:%d/%m/%Y}")
    if cfg["nota"]:
        arcpy.AddMessage(f"  Nota     : {cfg['nota']}")

    arcpy.SetProgressor("default", "Preparando el área de interés...")
    aoi = _preparar_aoi(capa, buffer_m)
    arcpy.AddMessage(f"  Área     : {aoi['area_original_ha']:,.0f} ha (con buffer de {buffer_m:,.0f} m: "
                     f"{aoi['area_ha']:,.0f} ha) · {aoi['zona']}")

    sesion = _sesion()
    arcpy.SetProgressorLabel("Consultando el catálogo de imágenes...")
    try:
        items = _buscar_escenas(sesion, cfg, aoi["bbox"], inicio, fin, nubes)
    except Exception as ex:
        arcpy.AddError(f"No se pudo consultar el catálogo de imágenes. Verifique la conexión a internet. ({ex})")
        return None
    grupos = _agrupar_por_fecha(items, aoi["utm"], aoi["epsg"])
    if not grupos:
        arcpy.AddError(f"No se encontraron imágenes {cfg['label']} con nubosidad ≤ {nubes:g}% en el periodo. "
                       "Amplíe el periodo o aumente la nubosidad máxima.")
        return None

    for g in grupos:
        g["estado"] = "Procesar" if g["cobertura"] >= cobertura_min else "Descartada: cobertura baja"
    aptos = [g for g in grupos if g["estado"] == "Procesar"]
    if max_fechas and len(aptos) > max_fechas:
        elegidos = {g["fecha"] for g in sorted(aptos, key=lambda g: (g["nubes"], -g["cobertura"]))[:max_fechas]}
        for g in aptos:
            if g["fecha"] not in elegidos:
                g["estado"] = "Descartada: límite de fechas"
        aptos = [g for g in aptos if g["fecha"] in elegidos]

    arcpy.AddMessage(f"\nEscenas encontradas: {len(items)} en {len(grupos)} fechas")
    arcpy.AddMessage(f"  {'Fecha':<12}{'Escenas':>8}{'Nubes %':>10}{'Cobertura %':>13}   Estado")
    for g in grupos:
        arcpy.AddMessage(f"  {g['fecha']:<12}{len(g['escenas']):>8}{g['nubes']:>10.1f}{g['cobertura']:>13.1f}   {g['estado']}")
    if not aptos:
        arcpy.AddError(f"Ninguna fecha cubre al menos el {cobertura_min:g}% del área de interés. "
                       "Reduzca la cobertura mínima o amplíe el periodo.")
        return None

    roles = COMBINACIONES.get(combinacion, COMBINACIONES[cfg["comb_def"]])
    assets_rgb = [_asset_rol(cfg, r) for r in roles]
    if todas_bandas:
        assets = [b[0] for b in cfg["bandas"]]
        indices_rgb = [assets.index(a) + 1 for a in assets_rgb]
    else:
        assets, indices_rgb = assets_rgb, [1, 2, 3]
    info = {b[0]: b for b in cfg["bandas"]}
    descripciones = [f"{info[a][2]} ({info[a][1]})" for a in assets]

    salida = os.path.join(carpeta, f"{cfg['prefijo']}_{inicio:%Y%m%d}_{fin:%Y%m%d}")
    os.makedirs(salida, exist_ok=True)
    grilla = _grilla(aoi, res)
    arcpy.AddMessage(f"\nCarpeta de resultados: {salida}")
    arcpy.AddMessage(f"Grilla: {grilla['w']:,} x {grilla['h']:,} px a {res:g} m · bandas: "
                     + ", ".join(descripciones))
    mpx = grilla["w"] * grilla["h"] / 1e6
    if mpx > 40:
        sugerida = next((r for r in (20, 30, 60, 100) if r > res and mpx * (res / r) ** 2 <= 40), 100)
        arcpy.AddWarning(
            f"Área grande: {mpx:,.0f} millones de píxeles por banda a {res:g} m. Cada fecha puede tardar "
            f"varios minutos. Para un BaseMap más rápido use «Resolución de salida» = {sugerida} m "
            "o reduzca el buffer.")

    mapa = _mapa_activo() if agregar_mapa else None
    firmar = _FirmaLandsat(sesion) if cfg["fuente"] == "landsat" else None
    tifs, capas_visor = [], []
    pasos = len(aptos) * len(assets)
    arcpy.SetProgressor("step", "Generando imágenes...", 0, pasos, 1)
    config_previa = {k: gdal.GetConfigOption(k) for k in _CONFIG_GDAL}
    try:
        for k, v in _CONFIG_GDAL.items():
            gdal.SetConfigOption(k, v)
        with gdal.ExceptionMgr(useExceptions=True):
            for i, g in enumerate(aptos, 1):
                if _cancelado():
                    arcpy.AddWarning("Proceso cancelado por el usuario.")
                    break
                etiqueta = f"{cfg['label']} {g['fecha']} ({i}/{len(aptos)})"
                arcpy.SetProgressorLabel(f"{etiqueta}: descargando {len(assets)} bandas "
                                         f"de {len(g['escenas'])} escenas...")
                ruta = os.path.join(salida, f"{cfg['prefijo']}_{g['fecha']}.tif")
                listas = []

                def banda_lista(asset, etiqueta=etiqueta, listas=listas):
                    listas.append(asset)
                    arcpy.SetProgressorPosition()
                    arcpy.SetProgressorLabel(f"{etiqueta}: {len(listas)}/{len(assets)} bandas listas")
                    arcpy.AddMessage(f"    · {info[asset][2]} ({info[asset][1]}) descargada")

                try:
                    cubo, pct = _componer_fecha(cfg, g, assets, grilla, firmar, banda_lista)
                    arcpy.SetProgressorLabel(f"{etiqueta}: guardando GeoTIFF...")
                    if pct <= 0:
                        g["estado"] = "Descartada: sin datos válidos"
                        arcpy.AddWarning(f"  {g['fecha']}: sin píxeles válidos en el área; se omite.")
                        continue
                    _escribir_tif(ruta, cubo, grilla, descripciones, {
                        "SATELITE": cfg["label"], "FECHA": g["fecha"], "FUENTE": FUENTES[cfg["fuente"]],
                        "ESCENAS": ";".join(it["id"] for it in g["escenas"]),
                        "NUBOSIDAD_ESCENA": f"{g['nubes']:.1f}", "PRODUCTO": "Reflectancia de superficie",
                        "GENERADO_POR": USER_AGENT,
                    }, 1e-4 if cfg["fuente"] == "sentinel" else 2.75e-05)
                    g["archivo"], g["validos"], g["estado"] = ruta, pct, "Generada"
                    tifs.append(ruta)
                    del cubo
                    arcpy.AddMessage(f"  ✔ {g['fecha']}: {os.path.basename(ruta)} ({pct:.1f}% del área con datos)")
                    if mapa is not None and _agregar_al_mapa(mapa, ruta, indices_rgb):
                        arcpy.AddMessage("    · agregada al mapa")
                    if visor:
                        try:
                            carpeta_png = os.path.join(salida, "visor")
                            os.makedirs(carpeta_png, exist_ok=True)
                            png = os.path.join(carpeta_png, f"{cfg['prefijo']}_{g['fecha']}.png")
                            bounds = _png_visor(ruta, indices_rgb, png)
                            capas_visor.append({"nombre": f"{cfg['label']} {g['fecha']}",
                                                "png": f"visor/{os.path.basename(png)}", "bounds": bounds})
                        except Exception as ex:
                            arcpy.AddWarning(f"  No se generó la vista web de {g['fecha']}: {ex}")
                except Exception as ex:
                    g["estado"] = "Error"
                    arcpy.AddWarning(f"  ✖ {g['fecha']}: {ex}")
                for _ in range(len(assets) - len(listas)):
                    arcpy.SetProgressorPosition()
    finally:
        for k, v in config_previa.items():
            gdal.SetConfigOption(k, v)
        arcpy.ResetProgressor()

    with open(os.path.join(salida, "resumen_escenas.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "escenas", "nubosidad_escena_pct", "cobertura_area_pct", "datos_validos_pct",
                    "estado", "archivo", "ids_escenas"])
        for g in grupos:
            w.writerow([g["fecha"], len(g["escenas"]), round(g["nubes"], 2), round(g["cobertura"], 2),
                        round(g.get("validos", 0), 2) if g.get("archivo") else "", g["estado"],
                        os.path.basename(g.get("archivo", "")), ";".join(it["id"] for it in g["escenas"])])

    if not tifs:
        arcpy.AddError("No se generó ninguna imagen.")
        return None

    html = None
    if visor and capas_visor:
        html = os.path.join(salida, f"visor_{cfg['prefijo'].lower()}_{inicio:%Y%m%d}_{fin:%Y%m%d}.html")
        ficha = (f"<span>{cfg['label']} · {combinacion}</span><br>"
                 f"<span>Periodo: {inicio:%d/%m/%Y} – {fin:%d/%m/%Y} · {len(capas_visor)} fechas</span><br>"
                 f"<span>Fuente: {FUENTES[cfg['fuente']]}</span>")
        _escribir_visor(html, f"BaseMap {cfg['label']}", ficha, capas_visor, aoi)

    arcpy.AddMessage(f"\nListo: {len(tifs)} imágenes en {salida} ({(time.time() - t0) / 60:.1f} min).")
    if html:
        arcpy.AddMessage(f"Visor web: {html}")
        if abrir_visor:
            try:
                os.startfile(html)
            except Exception:
                pass
    return salida


# --------------------------------------------------------------------------------------------
# Toolbox
# --------------------------------------------------------------------------------------------
class Toolbox(object):
    def __init__(self):
        self.label = "BaseMap Satelital"
        self.alias = "basemapsat"
        self.tools = [BaseMapSatelital]


class BaseMapSatelital(object):
    def __init__(self):
        self.label = "Generar BaseMap Satelital"
        self.description = (
            "Genera imágenes de reflectancia de superficie por fecha (Landsat 5, 7, 8, 9 o Sentinel-2) "
            "recortadas al área de interés, a partir de los archivos abiertos de Copernicus y USGS. "
            "No requiere Google Earth Engine ni cuentas de usuario."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        cfg = SATELITES[_clave(SATELITE_DEF)]
        ini, fin = _periodo_def(cfg)

        def par(nombre, etiqueta, tipo, requerido=True, direccion="Input", categoria=None):
            p = arcpy.Parameter(name=nombre, displayName=etiqueta, datatype=tipo,
                                parameterType=requerido if isinstance(requerido, str) else
                                ("Required" if requerido else "Optional"), direction=direccion)
            if categoria:
                p.category = categoria
            return p

        p_sat = par("satelite", "Satélite", "GPString")
        p_sat.filter.type = "ValueList"
        p_sat.filter.list = list(OPCIONES_SATELITE)
        p_sat.value = SATELITE_DEF

        p_aoi = par("area_interes", "Área de interés", "GPFeatureLayer")
        p_aoi.filter.list = ["Polygon"]

        p_ini = par("fecha_inicio", "Fecha de inicio", "GPDate")
        p_ini.value = ini
        p_fin = par("fecha_fin", "Fecha de fin", "GPDate")
        p_fin.value = fin

        p_carpeta = par("carpeta_salida", "Carpeta de salida", "DEFolder", requerido=False)
        p_carpeta.value = _carpeta_proyecto()

        cat_f = "Filtros de búsqueda"
        p_nubes = par("nubosidad_max", "Nubosidad máxima de la escena (%)", "GPDouble", categoria=cat_f)
        p_nubes.filter.type = "Range"
        p_nubes.filter.list = [0, 100]
        p_nubes.value = 30

        p_cob = par("cobertura_min", "Cobertura mínima del área de interés (%)", "GPDouble", categoria=cat_f)
        p_cob.filter.type = "Range"
        p_cob.filter.list = [0, 100]
        p_cob.value = 60

        p_max = par("max_fechas", "Número máximo de fechas (0 = todas, prioriza las menos nubosas)", "GPLong",
                    categoria=cat_f)
        p_max.filter.type = "Range"
        p_max.filter.list = [0, 1000]
        p_max.value = 0

        p_buf = par("buffer_m", "Buffer alrededor del área (m)", "GPDouble", categoria=cat_f)
        p_buf.filter.type = "Range"
        p_buf.filter.list = [0, 100000]
        p_buf.value = 5000

        cat_b = "Bandas y resolución"
        p_comb = par("combinacion", "Combinación de bandas (RGB)", "GPString", categoria=cat_b)
        p_comb.filter.type = "ValueList"
        p_comb.filter.list = list(COMBINACIONES)
        p_comb.value = cfg["comb_def"]

        p_todas = par("todas_bandas", "Exportar todas las bandas espectrales", "GPBoolean", requerido=False,
                      categoria=cat_b)
        p_todas.value = False

        p_res = par("resolucion", "Resolución de salida", "GPString", categoria=cat_b)
        p_res.filter.type = "ValueList"
        p_res.filter.list = list(RESOLUCIONES)
        p_res.value = RESOLUCION_DEF

        cat_r = "Resultados"
        p_add = par("agregar_mapa", "Agregar imágenes al mapa activo", "GPBoolean", requerido=False,
                    categoria=cat_r)
        p_add.value = True
        p_visor = par("visor_web", "Generar visor web (HTML)", "GPBoolean", requerido=False, categoria=cat_r)
        p_visor.value = True
        p_abrir = par("abrir_visor", "Abrir el visor web al finalizar", "GPBoolean", requerido=False,
                      categoria=cat_r)
        p_abrir.value = False

        p_out = par("carpeta_resultados", "Carpeta de resultados", "DEFolder", requerido="Derived",
                    direccion="Output")

        return [p_sat, p_aoi, p_ini, p_fin, p_carpeta, p_nubes, p_cob, p_max, p_buf,
                p_comb, p_todas, p_res, p_add, p_visor, p_abrir, p_out]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        p = {x.name: x for x in parameters}
        # Reset defaults only when the user picks another satellite in the dialog; in scripted calls
        # every parameter arrives unvalidated and the passed values must be kept.
        if not p["satelite"].hasBeenValidated and p["fecha_inicio"].hasBeenValidated:
            cfg = SATELITES[_clave(p["satelite"].valueAsText)]
            ini, fin = _periodo_def(cfg)
            p["fecha_inicio"].value = ini
            p["fecha_fin"].value = fin
            p["combinacion"].value = cfg["comb_def"]
        p["abrir_visor"].enabled = bool(p["visor_web"].value)
        return

    def updateMessages(self, parameters):
        p = {x.name: x for x in parameters}
        carpeta = p["carpeta_salida"].valueAsText
        if carpeta and not os.path.isdir(carpeta):
            p["carpeta_salida"].clearMessage()
            p["carpeta_salida"].setWarningMessage("La carpeta no existe; se creará al ejecutar.")

        if p["fecha_inicio"].value is None or p["fecha_fin"].value is None:
            return
        try:
            ini, fin = _a_fecha(p["fecha_inicio"].value), _a_fecha(p["fecha_fin"].value)
        except Exception:
            return
        if fin < ini:
            p["fecha_fin"].setErrorMessage("La fecha de fin debe ser igual o posterior a la fecha de inicio.")
            return
        cfg = SATELITES[_clave(p["satelite"].valueAsText)]
        desde, hasta = cfg["rango"]
        if fin < desde or (hasta and ini > hasta):
            lim = f"{desde:%d/%m/%Y} – {hasta:%d/%m/%Y}" if hasta else f"desde {desde:%d/%m/%Y}"
            p["fecha_inicio"].setWarningMessage(f"{cfg['label']} tiene imágenes {lim}; el periodo queda fuera.")
        elif (fin - ini).days > 366 and not p["max_fechas"].value:
            p["fecha_fin"].setWarningMessage(
                "Periodo mayor a un año: puede generar muchas imágenes. "
                "Considere limitar el número máximo de fechas.")
        return

    def execute(self, parameters, messages):
        p = {x.name: x for x in parameters}
        capa = p["area_interes"].value
        carpeta = p["carpeta_salida"].valueAsText or _carpeta_por_defecto(capa)
        resultado = generar_basemap(
            clave=_clave(p["satelite"].valueAsText),
            capa=capa,
            inicio=p["fecha_inicio"].value,
            fin=p["fecha_fin"].value,
            nubes=float(p["nubosidad_max"].value),
            cobertura_min=float(p["cobertura_min"].value),
            max_fechas=int(p["max_fechas"].value or 0),
            buffer_m=float(p["buffer_m"].value),
            combinacion=p["combinacion"].valueAsText,
            todas_bandas=bool(p["todas_bandas"].value),
            carpeta=carpeta,
            agregar_mapa=bool(p["agregar_mapa"].value),
            visor=bool(p["visor_web"].value),
            abrir_visor=bool(p["abrir_visor"].value),
            resolucion=RESOLUCIONES.get(p["resolucion"].valueAsText),
        )
        if resultado:
            p["carpeta_resultados"].value = resultado
        return
