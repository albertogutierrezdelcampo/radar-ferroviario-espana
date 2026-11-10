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
