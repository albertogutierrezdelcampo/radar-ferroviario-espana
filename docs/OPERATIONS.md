# Operación y observabilidad

## Health checks

- Liveness: `/health/live`, intervalo recomendado 30 s, timeout 3 s.
- Readiness: `/health/ready`, intervalo 30 s, timeout 5 s.
- Un `503` de readiness durante arranque puede ser normal hasta obtener `/api/trains`.

## Logs

`logs/radar_errors.log` rota con tres archivos de 2 MB. Los warnings incluyen fallos de fuente aislados. Un warning no implica caída global.

```bash
tail -f logs/radar_errors.log
```

## Diagnóstico

```bash
curl -s http://127.0.0.1:5000/api/diagnostics | python -m json.tool
```

Revisar:

- `train_snapshot.last_success_at`;
- `background.tracks_status`;
- `overpass_mirrors[].attempt_in_progress`;
- `overpass_mirrors[].cooldown_seconds`;
- contadores de estaciones, rutas y trenes;
- errores recientes.

## Reinicio seguro

1. Detener aceptación de tráfico si existe balanceador.
2. Enviar SIGTERM a Gunicorn.
3. Esperar finalización de peticiones.
4. Mantener cachés en volumen persistente si se desea warm start.
5. Arrancar y comprobar live, ready y diagnostics.

## Alarmas recomendadas

- Liveness distinto de 200 durante 2 minutos.
- Readiness 503 durante más de 10 minutos tras arranque.
- Snapshot de trenes mayor de 5 minutos.
- Log creciendo de forma continua con el mismo proveedor.
- Todos los mirrors Overpass en cooldown.
- Disco por encima del 80 %.
