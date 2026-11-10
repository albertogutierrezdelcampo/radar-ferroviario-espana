# Fase 1: estabilización de /api/trains

`/api/trains` queda desacoplado de Overpass, redes urbanas, iryo y OUIGO. Usa un bloqueo single-flight de 10 segundos, conserva la última instantánea válida, devuelve HTTP 200 ante errores aguas arriba y descarta entidades malformadas individualmente.

Pruebas: `python -m pytest -q`.
