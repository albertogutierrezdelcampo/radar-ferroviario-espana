# Productivización

## Flujo de ramas
- `feature/*` -> Pull Request a `dev`
- `dev` -> integración continua
- `qa` -> candidato validado
- `main` -> producción

## Ejecución local
```bash
docker compose up --build
curl http://localhost:8080/health/live
```

## Controles
- Un solo worker Gunicorn: la aplicación mantiene cachés e hilos en memoria.
- 8 threads para peticiones concurrentes.
- Liveness `/health/live`; readiness `/health/ready`.
- CI compila Python, ejecuta pytest, valida Jinja, construye el contenedor y hace smoke test.
- Dependabot semanal para pip y GitHub Actions.
- Releases automáticas al crear una etiqueta `v*`.

## AWS
La base queda preparada para contenedor. No se activa un despliegue automático hasta crear una cuenta AWS, presupuesto, alarmas y una identidad OIDC. No se deben guardar access keys permanentes en GitHub.
