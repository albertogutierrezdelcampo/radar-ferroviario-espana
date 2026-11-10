# Arquitectura técnica

## 1. Objetivos

La arquitectura prioriza disponibilidad degradada, aislamiento de proveedores, observabilidad y migración incremental desde una aplicación Flask monolítica. Una caída de Overpass, NAP o un operador no debe impedir servir el mapa, estaciones o trenes de otras fuentes.

## 2. Capas

### Entradas

- `app.py`: compatibilidad para desarrollo, Flask CLI y tests históricos.
- `wsgi.py`: objeto WSGI para Gunicorn.
- `templates/map.html`: estructura semántica de la interfaz.
- `static/js/map.js`: cliente de API, Leaflet, filtros y refresco.
- `static/css/map.css`: presentación independiente.

### Composición Flask

`src/radar_app/application.py` registra rutas, coordina servicios y conserva temporalmente lógica heredada. Es el composition root, no el destino final de la lógica de dominio. Las extracciones futuras deben ir a blueprints y servicios bajo `src/`.

### Dominio e infraestructura

- `config.py`: catálogos y constantes inmutables.
- `state.py`: propietario del estado mutable y locks.
- `extensions.py`: sesiones HTTP con pooling y reintentos acotados.
- `logging_config.py`: logging rotativo y buffer de diagnóstico.
- `cache_store.py`: persistencia JSON atómica.
- `overpass_service.py`: rotación, cooldown, stale cache y telemetría.
- `gtfs/`: lectura y calendario GTFS reutilizables.
- `utils.py`: funciones puras de geodesia, números, trenes y tiempos.

## 3. Flujo de arranque

1. `app.py` añade `src/` a `sys.path`.
2. Carga la composición dentro del namespace compatible.
3. Flask crea la aplicación y registra rutas.
4. `ensure_background_threads()` inicia las cargas idempotentes.
5. Operadores y redes intentan caché local antes de red cuando procede.
6. Estaciones y geometrías progresan de forma independiente.
7. `/health/live` responde mientras el proceso está activo.
8. `/health/ready` sólo pasa a ready tras una instantánea válida de trenes.

## 4. Estado y concurrencia

`ApplicationState` agrupa cachés y locks. Los diccionarios legados en la composición son aliases al contenedor para mantener compatibilidad. Los locks más importantes son:

- `metro_lock`: estados de redes urbanas.
- `open_access_lock`: operadores de acceso abierto.
- `overpass_lock`: caché, salud e inflight de Overpass.
- `train_refresh_lock`: impide dos renovaciones simultáneas de trenes.

### Limitación de multiproceso

El estado es local al proceso. Con Gunicorn y varios workers, cada worker tendrá sus propios snapshots, hilos y cachés. Hasta introducir un backend compartido, usar un worker con varios threads.

## 5. Resiliencia

### GTFS y operadores

- TTL evita descargas continuas.
- La caché ZIP reduce dependencia del proveedor.
- Los fallos se aíslan por red.
- El parser valida firma ZIP, tablas obligatorias y CSV.

### Overpass

- Varios mirrors.
- Un intento por mirror en cada fase.
- Cooldown tras fallo.
- Priorización por último éxito, latencia y fallos.
- Fallback a caché caducada si existe.
- Estados `idle`, `loading`, `stalled`, `partial`, `ready` y `failed`.

### Renfe tiempo real

- Lock para refresh.
- Snapshot con `last_attempt_at`, `last_success_at` y `last_error`.
- Respuesta degradada explícita si no existe snapshot utilizable.

## 6. Dependencias permitidas

Dirección preferida:

```text
app.py / wsgi.py
        ↓
radar_app.application
        ↓
servicios / blueprints futuros
        ↓
radar.state, radar.gtfs, radar.overpass_service
        ↓
radar.config, radar.extensions, radar.cache_store, radar.utils
```

Los módulos inferiores no deben importar Flask ni `radar_app.application`.

## 7. Plan de evolución

1. Extraer blueprints de health y diagnostics.
2. Extraer servicios GTFS/NAP.
3. Extraer servicio Renfe realtime.
4. Extraer catálogo ADIF y validar allowlist de hosts.
5. Sustituir aliases globales por inyección explícita de `ApplicationState`.
6. Añadir `pyproject.toml` e instalación editable.
7. Externalizar estado si se necesitan múltiples workers.
