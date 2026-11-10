# Suite de pruebas

Ejecutar desde la raíz:

```bash
RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q
```

Las pruebas unitarias no deben usar Internet. Para red se usan doubles o mocks; para GTFS, ZIP mínimos en memoria; para disco, `tmp_path`. Toda corrección de incidencia debe incluir una prueba que reproduzca el fallo anterior.
