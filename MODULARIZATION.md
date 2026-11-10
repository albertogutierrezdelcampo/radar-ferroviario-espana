# Modularización incremental

## Fase aplicada

- `templates/map.html`: sólo estructura HTML y referencias a recursos.
- `static/css/map.css`: estilos del mapa y paneles.
- `static/js/map.js`: estado de interfaz, Leaflet, filtros y clientes API.
- `app.py:create_app()`: punto de entrada compatible con `gunicorn 'app:create_app()'`.

La separación no cambia rutas, contratos JSON ni comportamiento funcional.

## Siguiente corte recomendado del backend

1. `radar/config.py`: URLs, TTL, catálogos de operadores y núcleos.
2. `radar/extensions.py`: logging, sesiones HTTP y políticas de reintento.
3. `radar/domain/`: geometría, cinemática, clasificación Renfe y GTFS.
4. `radar/services/`: Renfe RT, operadores, metros, Overpass y ADIF.
5. `radar/repositories/`: cachés en memoria y persistencia en disco.
6. `radar/api/`: blueprints `health`, `trains`, `infrastructure`, `operators`, `diagnostics`.

## Regla de migración

Mover un dominio por pull request, conservar temporalmente imports de compatibilidad desde `app.py` y ejecutar pruebas de contrato sobre cada endpoint antes de continuar.

## Fase 2 aplicada

- `radar/config.py`: configuración inmutable, rutas del proyecto, catálogos Renfe/NAP, TTL, mirrors Overpass, núcleos y estaciones base.
- `radar/utils.py`: utilidades puras de números, geodesia, identificación ferroviaria, geometría y tiempos GTFS.
- `tests/test_utils.py`: pruebas unitarias rápidas sin Flask ni red.
- `app.py`: consume ambos módulos mediante imports explícitos; cachés, locks, sesiones HTTP y estado mutable permanecen en el orquestador.

Se mantiene `BASE_DIR` apuntando a la raíz del repositorio, no al directorio `radar/`, para conservar las rutas actuales de caché.

## Fase 3 aplicada

- `radar/logging_config.py`: logging rotativo, buffer de diagnósticos, captura de excepciones y hook de hilos.
- `radar/extensions.py`: factoría común de sesiones HTTP, pooling y reintentos acotados.
- `DEFAULT_HTTP`: sustituye llamadas GET aisladas para reutilizar conexiones y aplicar backoff.
- `OVERPASS_HTTP` y `OPERATOR_HTTP`: mantienen políticas distintas según la fuente y el método seguro.
- Configuración idempotente del logger para evitar mensajes duplicados con tests, Flask y futuros workers WSGI.

## Fase 4 aplicada

- `radar/state.py`: propietario único del estado mutable, cachés en memoria y locks.
- `ApplicationState`: agrupa estado de metros, operadores, Overpass, estáticos, tiempo real, alertas y ADIF.
- `create_application_state()`: crea instancias aisladas para aplicación y pruebas.
- `radar/cache_store.py`: lectura tolerante y escritura JSON atómica con `fsync` y `os.replace`.
- `app.py`: mantiene aliases compatibles para no cambiar todavía servicios ni contratos API.

La separación evita estado mutable creado de forma dispersa y prepara la inyección de dependencias en los futuros servicios y blueprints.

## Fase 5 aplicada

- `radar/overpass_service.py`: consulta, rotación, cooldown, deduplicación y persistencia Overpass.
- Un solo intento por mirror y ronda, sin reintentos automáticos internos para POST.
- Timeout acotado a 5 s de conexión y 30 s de lectura.
- Fallback a caché caducada cuando todos los mirrors fallan.
- Progreso visible por mirror y telemetría de latencia, último intento, último éxito y último error.
- Watchdog diagnóstico: `loading`, `ready`, `idle` o `stalled` tras 120 s sin progreso.
- Persistencia Overpass mediante escritura JSON atómica.

## Fase 5.2 correctiva

- Cabeceras Overpass dedicadas para evitar incompatibilidades HTTP 406.
- Las respuestas HTTP 200 vacías se consideran fallo y provocan rotación.
- Los errores HTTP incluyen hasta 500 caracteres del cuerpo de respuesta.
- Estado terminal explícito: `idle`, `loading`, `stalled`, `partial`, `ready` o `failed`.
- Diagnóstico por fases completadas y fallidas, último error y finalización.
- Las cuatro fases se intentan aunque una anterior falle.
- `RADAR_LOG_FILE` permite aislar el fichero de log en tests y CI.

## Fase 5.3 aplicada

- Cooldown conservado entre ciclos, pero cada fase de una carga obtiene una ronda real de mirrors.
- Priorización: último éxito, menor latencia, menos fallos y orden de configuración.
- Telemetría al comienzo y final de cada intento: en curso, duración y timestamp.
- Latencia registrada también en timeouts y errores de conexión.
- Watchdog de 90 s que no marca `stalled` mientras existe una petición identificada como activa.
- Las fases 2, 3 y 4 ya no quedan falsamente fallidas por el cooldown consumido en fase 1.

## Fase 5.3.1 correctiva

- Corregida la integración del planificador en el bucle real, que usa `q_str` y claves `seed-stage-*`.
- Cada etapa pasa ahora `ignore_cooldown=True` y un `cycle_id` distinto al servicio Overpass.
- Añadida prueba de regresión sobre la integración en `app.py`, además de las pruebas unitarias del servicio.

## Fase 6.1 aplicada

- `radar/gtfs/models.py`: resultados tipados y errores de validación.
- `radar/gtfs/parser.py`: descubrimiento en subdirectorios, validación ZIP y lectura CSV UTF-8 BOM.
- `radar/gtfs/calendar.py`: fechas, horas GTFS extendidas y servicios activos con excepciones.
- Los cuatro ficheros estructurales requeridos son `stops`, `routes`, `trips` y `stop_times`.
- `calendar.txt` y `calendar_dates.txt` son opcionales; su ausencia produce advertencias.
- Esta fase añade primitivas sin reemplazar aún el parser productivo de `app.py`; la migración delegada corresponde a 6.2.

## Fase 6.2 aplicada

- `parse_operator_gtfs()` delega la validación y lectura ZIP/CSV en `radar.gtfs`.
- El calendario productivo delega la selección diaria en `active_service_ids()`.
- `parse_metro_gtfs()` hereda automáticamente la misma validación al reutilizar el parser de operadores.
- Se mantienen intactos los contratos de salida de iryo, OUIGO, metros y redes regionales.
- Añadida prueba de integración para impedir que el parser monolítico vuelva a introducir lectura ZIP/CSV propia.

## Fase 7.0: estructura `src/` y punto de entrada mantenible

- Todo el paquete `radar` vive en `src/radar/` siguiendo el patrón source layout.
- La composición Flask reside en `src/radar_app/application.py`.
- `app.py` queda como entrada compatible de menos de 40 líneas.
- `wsgi.py` ofrece la entrada de producción `gunicorn wsgi:app`.
- `pytest.ini` y `tests/conftest.py` incluyen explícitamente raíz y `src/`.
- El cargador ejecuta temporalmente la composición en el namespace de `app.py` para conservar monkeypatches existentes de `test_api_trains.py`.
- Los tests de arquitectura inspeccionan la implementación real dentro de `src/radar_app/`.

### Siguiente extracción

`application.py` sigue siendo el composition root legado. A partir de esta base se migrarán por pull requests los blueprints (`health`, `diagnostics`, `operators`, `infrastructure`) y servicios, sin volver a engordar `app.py`.

## Fase 6.3 aplicada

- `src/radar/nap_service.py`: adquisición GTFS independiente de Flask.
- Soporta ZIP directo, redirect, JSON anidado, texto JSON y URL temporal.
- Valida el ZIP y las tablas GTFS antes de sustituir la caché.
- Escritura binaria atómica mediante temporal, `fsync` y `os.replace`.
- Política: caché fresca, NAP, fallbacks públicos y finalmente caché stale válida.
- Una descarga inválida nunca destruye el último GTFS válido.
- Estado por red con `stale`, edad de caché, intentos, último intento y último éxito.
- Los wrappers históricos permanecen para conservar contratos y tests existentes.

## Fase 6.3.1 aplicada

- `/api/transit-networks` expone metadatos completos de adquisición, caché y fuente.
- `/api/diagnostics` añade `gtfs_sources` con el mismo contrato resumido.
- Metrovalencia usa el identificador de fichero NAP vigente `1168`; `967` queda sólo como página de catálogo.
- Mallorca deja de depender del endpoint NAP `1071` y usa el GTFS oficial directo de TIB.
- La adquisición omite NAP cuando `nap_id` es `None` y continúa con URLs oficiales directas.

## Fase 6.3.2 correctiva

- `radar.config.METRO_GTFS` pasa a ser la fuente autoritativa en runtime.
- La composición Flask sobrescribe el literal legado antes de construir `METRO_CACHE`.
- Añadida prueba de regresión para impedir que IDs antiguos vuelvan a gobernar la aplicación.
- La eliminación física del literal duplicado se realizará al extraer completamente el servicio de redes.

## Fase 6.3.3 aplicada

- `src/radar/redaction.py` centraliza saneamiento de URLs, texto y estructuras JSON.
- Se eliminan credenciales embebidas, fragmentos y valores sensibles de query (`X-Amz-*`, `X-Goog-*`, `sig`, `token`, `ApiKey`, etc.).
- NAP guarda intentos y errores ya saneados; las URLs firmadas nunca entran completas en estado nuevo.
- `/api/transit-networks` y `/api/diagnostics` vuelven a sanear en el límite de salida como defensa en profundidad.
- Los handlers de fichero y memoria aplican `RedactingFilter` antes de persistir o exponer logs.
- Se conserva host, ruta y parámetros no sensibles para que el diagnóstico siga siendo útil.

## Fase 7.2: calidad y pruebas exhaustivas

- Fixtures comunes para `app`, cliente Flask y restauración de caches mutables.
- Integración HTTP en proceso para health, UI, estaciones, rutas, viewport, redes, operadores, alertas, ADIF y diagnóstico.
- Pruebas administrativas para refresh, configuración OUIGO y limpieza/descarga de log.
- Pruebas de contratos, 404, readiness reciente/caducado y redacción en el límite HTTP.
- Marcador `integration` registrado en pytest.
- `.coveragerc`, `requirements-dev.txt` y workflow GitHub Actions con Python 3.12.
- Todas las pruebas impiden red real y escriben logs de test fuera del repositorio.
