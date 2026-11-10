# Paquete `radar`

Este paquete contiene dominio e infraestructura reutilizables y no debe depender del módulo Flask de composición.

- `config.py`: valores inmutables y catálogos.
- `state.py`: caches y locks en un contenedor explícito.
- `extensions.py`: clientes HTTP compartidos.
- `logging_config.py`: logger rotativo y buffer de diagnóstico.
- `cache_store.py`: JSON atómico.
- `overpass_service.py`: acceso resiliente a Overpass.
- `gtfs/`: lectura, validación y calendario GTFS.
- `utils.py`: funciones puras.

Regla de dependencia: `radar` no importa `radar_app`. La aplicación puede importar `radar`.
