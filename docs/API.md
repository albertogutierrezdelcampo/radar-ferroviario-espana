# API HTTP

## Convenciones

- JSON UTF-8.
- Los errores esperados usan `success: false` y `error` descriptivo.
- Los timestamps Unix están en segundos.
- Los datos externos pueden ser parciales o stale.
- Los clientes deben tolerar campos adicionales.

## Health

### `GET /health/live`

Indica que Flask responde. No garantiza fuentes externas ni snapshot ferroviario.

```json
{"service":"radar-ferroviario","status":"ok"}
```

### `GET /health/ready`

Devuelve `200` con snapshot útil y `503` mientras está degradado.

```json
{"status":"ready","trains":299,"snapshot_age_seconds":14,"last_error":null}
```

## Trenes

### `GET /api/trains`

Renueva o reutiliza el snapshot según TTL y lock.

Campos principales:

- `success`: ejecución utilizable.
- `cached`: proviene del snapshot.
- `stale`: snapshot antiguo usado como degradación.
- `trains`: lista normalizada.
- `diagnostics`: resultado por feed.

Cada tren puede incluir `id`, `label`, `lat`, `lon`, `raw_lat`, `raw_lon`, `speed`, `speed_source`, `bearing`, `route_id`, `nucleo`, `origin_dest`, `next_stop`, `delay_min`, `current_status`, `is_feve` y `stops`.

No asumas que `speed`, `bearing`, `next_stop` o `delay_min` siempre existen.

## Estaciones y rutas

### `GET /api/stations`

Lista estaciones conocidas de Renfe y GTFS cargados.

### `GET /api/routes`

Devuelve geometrías actuales y metadatos de carga.

### `GET /api/routes/viewport`

Parámetros de viewport geográfico. El cliente debe limitar la frecuencia para evitar sobrecargar Overpass.

## Operadores y redes

### `GET /api/operators`

Estado de iryo, OUIGO y operadores configurados.

### `GET /api/transit-networks`

Estado, rutas y trenes estimados de redes urbanas o regionales.

### `POST /api/feeds/refresh`

Fuerza renovación. Debe protegerse con autenticación antes de publicar en Internet.

### `/api/operators/config`

- `GET`: consulta configuración segura.
- `POST`: actualiza token autorizado.
- `DELETE`: elimina token.

Nunca devuelvas secretos completos en respuestas.

## Diagnóstico

### `GET /api/diagnostics`

Incluye:

- uptime;
- contadores;
- estado del snapshot;
- feeds;
- background loading;
- mirrors Overpass;
- últimos warnings/errores;
- fichero y retención del log.

### `GET /api/diagnostics/log`

Descarga el log. Es un endpoint administrativo y puede contener URLs, excepciones y estructura interna.

### `DELETE /api/diagnostics/errors`

Limpia buffer y fichero. Debe autenticarse en producción.

## ADIF

### `GET /api/adif/catalog`

Descubre recursos públicos compatibles.

### `GET /api/adif/layer?url=<URL>`

Consulta FeatureServer, MapServer o GeoJSON. Antes de producción debe existir allowlist estricta de esquema `https`, host y rutas admitidas para reducir SSRF.
