# Contribuir

## Antes de empezar

1. Crea una issue o describe el problema.
2. Trabaja en una rama dedicada.
3. No incluyas secretos ni datos descargados.
4. Mantén el cambio pequeño y verificable.

## Calidad obligatoria

```bash
python -m py_compile app.py wsgi.py src/radar_app/application.py src/radar/*.py src/radar/gtfs/*.py tests/*.py
RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q
```

## Pull request

Incluye:

- problema y alcance;
- diseño elegido;
- pruebas añadidas;
- riesgos y compatibilidad;
- instrucciones de validación manual;
- actualización de README o `docs/` cuando cambie comportamiento.

## Convenciones

- `feat:` nueva capacidad.
- `fix:` corrección.
- `refactor:` estructura sin cambio funcional.
- `test:` pruebas.
- `docs:` documentación.
- `chore:` mantenimiento.
