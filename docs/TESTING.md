# Estrategia de pruebas

## Objetivos

1. Evitar regresiones de contratos API.
2. Validar parsing sin depender de Internet.
3. Asegurar aislamiento de estado mutable.
4. Probar degradación y stale cache.
5. Verificar invariantes arquitectónicos del source layout.

## Ejecución

```bash
RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q
```

Para un módulo:

```bash
pytest -q tests/test_overpass_service.py
```

## Familias

- `test_utils.py`: funciones puras.
- `test_state.py`: aislamiento de instancias y caches.
- `test_cache_store.py`: persistencia atómica.
- `test_extensions.py`: sesiones y retry.
- `test_logging_config.py`: handlers y buffer.
- `test_overpass_*`: rotación, cooldown, telemetría y planificación.
- `test_gtfs_*`: ZIP, CSV, calendarios e integración.
- `test_api_trains.py`: snapshot, locks y degradación.
- `test_src_layout.py`: reglas estructurales.

## Reglas

- No usar red real en tests unitarios.
- Usar ZIP GTFS mínimos construidos en memoria.
- Usar `tmp_path` para disco.
- Redirigir `RADAR_LOG_FILE` a `/tmp`.
- Los errores deliberados de mocks no deben confundirse con fallos del producto.
- Toda corrección de bug debe añadir una prueba de regresión que falle antes del fix.

## Suite exhaustiva desde la fase de calidad 7.2

Instala herramientas de desarrollo:

```bash
pip install -r requirements-dev.txt
```

Ejecuta todo:

```bash
PYTHONPATH=src RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q
```

Sólo integración HTTP sin red externa:

```bash
PYTHONPATH=src RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q -m integration
```

Cobertura con branches:

```bash
PYTHONPATH=src RADAR_LOG_FILE=/tmp/radar-pytest.log \
pytest -q --cov --cov-report=term-missing --cov-report=html --cov-report=xml
```

La suite de integración usa el `test_client` real de Flask, pero bloquea el
arranque de threads y sustituye I/O externo con dobles. Cubre contratos, códigos
HTTP, cabeceras de caché, aislamiento de estado, saneamiento de credenciales,
planificación de refresh y endpoints administrativos.
