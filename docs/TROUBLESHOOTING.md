# Resolución de problemas

## `ModuleNotFoundError: radar`

Ejecuta desde la raíz y confirma:

```bash
cat pytest.ini
find src/radar -maxdepth 2 -type f
```

`pythonpath` debe incluir `src`.

## Readiness devuelve 503

Consulta `/api/trains`. Si nunca se intentó el snapshot, `last_attempt_at` será cero. Después revisa `/api/diagnostics`.

## Overpass tarda o falla

- Timeout: el mirror rota automáticamente.
- HTTP 406: revisar cuerpo en `last_error`.
- Todos en cooldown: esperar o usar caché existente.
- `partial`: algunas fases produjeron vías y otras no.
- `failed`: ninguna fase produjo geometrías.

## Metrovalencia o Mallorca sin datos

Un HTTP 200 de NAP puede no contener URL descargable. Revisa configuración del dataset, token, respuesta y existencia de caché. La fase 6.3 debe ampliar este tratamiento.

## Tests escriben en log operativo

```bash
RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q
```

## Doble paquete `radar`

Después de migrar a `src/`, elimina el antiguo directorio raíz:

```bash
rm -rf radar
```

Confirma el import:

```bash
python -c 'import radar; print(radar.__file__)'
```

Debe apuntar a `src/radar/__init__.py`.

## Estado GTFS `stale`

`stale` indica que la renovación NAP y los fallbacks fallaron, pero la aplicación
conservó y volvió a validar el último ZIP local. Consulta `cache_age_seconds`,
`download_attempts`, `active_source` y `error` en el estado de la red. No borres
la caché hasta verificar que existe una fuente remota válida.
