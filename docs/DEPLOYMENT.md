# Despliegue

## Gunicorn

Configuración inicial conservadora:

```bash
gunicorn \
  --workers 1 \
  --threads 8 \
  --timeout 180 \
  --graceful-timeout 30 \
  --bind 0.0.0.0:5000 \
  wsgi:app
```

Un worker evita duplicar el estado y los hilos de fondo. Escalar horizontalmente requiere externalizar cachés, coordinación de refresh y locks.

## Docker

- Imagen sin `.env`, cachés ni logs.
- Usuario no root.
- Volumen opcional para `cache/` y `logs/`.
- Health check contra `/health/live`.
- Límites explícitos de CPU y memoria.

## AWS con coste controlado

Para un entorno personal de bajo tráfico, opciones habituales son una instancia pequeña con Docker o servicios serverless, pero el uso de hilos, estado en memoria y tareas largas favorece inicialmente una VM o contenedor persistente. Configura presupuestos y alertas antes de desplegar.

## Checklist

- [ ] TLS activo.
- [ ] Endpoints administrativos autenticados.
- [ ] Allowlist para proxy ADIF.
- [ ] Secretos en almacén seguro.
- [ ] Egress restringido a proveedores necesarios.
- [ ] Logs centralizados o rotados.
- [ ] Backups de configuración, no de datos regenerables.
- [ ] Readiness separado de liveness.
