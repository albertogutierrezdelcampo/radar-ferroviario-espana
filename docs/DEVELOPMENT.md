# Guía de desarrollo

## Preparación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Principios de código

- Funciones puras en `src/radar/utils.py` o paquetes de dominio.
- Red, disco y logging detrás de servicios de infraestructura.
- Flask limitado a composición, validación HTTP y serialización.
- Nada de secretos en constantes o tests.
- Timeouts obligatorios en toda llamada de red.
- No introducir estado mutable global fuera de `ApplicationState`.
- Mantener respuestas compatibles; añadir campos es preferible a renombrarlos.

## Añadir una fuente GTFS

1. Añadir configuración inmutable.
2. Definir caché y TTL.
3. Descargar bytes con timeout.
4. Validar con `open_gtfs_archive()`.
5. Parsear calendario con `active_service_ids()`.
6. Actualizar estado bajo lock.
7. Mantener último dato válido ante fallo remoto.
8. Añadir diagnóstico y pruebas sin red.

## Añadir un endpoint

1. Definir contrato y códigos HTTP.
2. Separar lógica de negocio de Flask.
3. Validar parámetros y límites.
4. No exponer secretos ni tracebacks.
5. Añadir tests de éxito, entrada inválida y degradación.
6. Documentar en `docs/API.md`.

## Estilo de docstrings

Usar docstrings orientados a comportamiento:

```python
def load_feed(key: str, force: bool = False) -> dict:
    """Load one configured GTFS feed into its isolated state.

    Args:
        key: Configuration key present in the feed catalogue.
        force: Ignore a still-valid TTL and attempt a remote refresh.

    Returns:
        The mutable source-state mapping after the attempt.

    Side effects:
        Reads or writes the local ZIP cache and updates state under a lock.
    """
```

## Flujo Git

- Rama por cambio: `feature/gtfs-nap-service`.
- Commits pequeños: `refactor: extract NAP downloader`.
- Ejecutar tests antes del push.
- No confirmar ZIP, logs, cachés, `.env` ni `.venv`.
