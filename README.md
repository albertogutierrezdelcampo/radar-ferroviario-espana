# Radar Ferroviario de España

Aplicación web para visualizar sobre un mapa la circulación ferroviaria disponible en tiempo real, horarios GTFS, estaciones, infraestructura ferroviaria y estado operativo de múltiples fuentes españolas.

> **Estado del proyecto:** desarrollo activo. La aplicación integra fuentes heterogéneas que pueden cambiar, limitar peticiones o sufrir indisponibilidades. Los datos mostrados son informativos y no deben utilizarse para seguridad operacional, conducción, señalización ni toma de decisiones críticas.

## Índice

- [Qué ofrece](#qué-ofrece)
- [Arquitectura](#arquitectura)
- [Fuentes de datos](#fuentes-de-datos)
- [Requisitos](#requisitos)
- [Instalación local](#instalación-local)
- [Configuración](#configuración)
- [Ejecución](#ejecución)
- [API HTTP](#api-http)
- [Pruebas](#pruebas)
- [Cachés y persistencia](#cachés-y-persistencia)
- [Observabilidad](#observabilidad)
- [Docker y producción](#docker-y-producción)
- [Seguridad y limitaciones](#seguridad-y-limitaciones)
- [Documentación técnica](#documentación-técnica)
- [Contribución](#contribución)

## Qué ofrece

- Posiciones GTFS-RT de Cercanías y servicios nacionales de Renfe cuando la fuente está disponible.
- Clasificación de AVE, Larga Distancia, Media Distancia, Cercanías y servicios de ancho métrico.
- Integración de operadores de acceso abierto como iryo y OUIGO mediante GTFS estático.
- Redes urbanas y regionales, entre ellas Metro de Madrid, TMB, Metro Bilbao, Metro Málaga, Euskotren y redes ferroviarias andaluzas.
- Adquisición NAP endurecida: ZIP directo, URL temporal, fallbacks públicos y conservación de caché stale validada.
- Estaciones, rutas, horarios, próximas paradas y estimaciones derivadas de GTFS.
- Geometrías ferroviarias de OpenStreetMap mediante varias instancias Overpass.
- Alertas GTFS-RT e información pública de infraestructura de ADIF cuando las fuentes responden.
- Health checks, diagnóstico de feeds, registro rotativo de errores y degradación controlada.

## Arquitectura

El repositorio usa un **source layout**. El archivo raíz `app.py` es sólo una entrada compatible; el código Python vive bajo `src/`.

```text
.
├── app.py                       # Entrada local compatible: python app.py
├── wsgi.py                      # Entrada WSGI: gunicorn wsgi:app
├── src/
│   ├── radar/                   # Dominio, infraestructura y utilidades
│   │   ├── config.py
│   │   ├── state.py
│   │   ├── extensions.py
│   │   ├── logging_config.py
│   │   ├── cache_store.py
│   │   ├── overpass_service.py
│   │   ├── utils.py
│   │   └── gtfs/
│   └── radar_app/
│       └── application.py       # Composition root Flask legado
├── templates/map.html
├── static/css/map.css
├── static/js/map.js
├── tests/
└── docs/
```

La descripción detallada de componentes, dependencias y flujos está en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Fuentes de datos

| Área | Fuente o mecanismo | Tipo | Comportamiento ante fallo |
|---|---|---|---|
| Renfe Cercanías | GTFS-RT Renfe | Tiempo real | Conserva snapshot válido cuando corresponde |
| Renfe nacional | GTFS-RT Renfe LD | Tiempo real | Diagnóstico por categoría y último error |
| iryo / OUIGO | GTFS estático | Horarios | Caché ZIP local con TTL |
| Metros y redes regionales | NAP o URL directa | GTFS estático | Fallback y caché local |
| Vías | OpenStreetMap Overpass | Geometría | Rotación de mirrors, cooldown y caché |
| Infraestructura | ADIF / ArcGIS públicos | Catálogo y GeoJSON | Caché en memoria y error estructurado |

Los detalles, licencias y restricciones técnicas se documentan en [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Requisitos

- Python 3.12 recomendado.
- `pip` y `venv` o `pyenv`.
- Acceso de red a las fuentes externas.
- Entre 300 MB y 1 GB de memoria según el volumen de GTFS y geometrías cargado.
- Espacio local para ZIP de operadores, logs y cachés JSON.

## Instalación local

```bash
git clone <URL_DEL_REPOSITORIO>
cd radar-ferroviario-espana

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuración

Copia el ejemplo sin secretos:

```bash
cp .env.example .env
```

Variables relevantes:

| Variable | Uso | Valor típico |
|---|---|---|
| `RADAR_LOG_FILE` | Cambia el fichero de log | `logs/radar_errors.log` |
| Tokens NAP u operadores | Descargas que requieren autorización | Sólo en `.env` o configuración local |
| Puerto Flask | Desarrollo local | `5000` |

Nunca confirmes al repositorio `.env`, tokens, certificados ni `cache/operators/operator_config.json`.

## Ejecución

Desarrollo:

```bash
source .venv/bin/activate
python app.py
```

Abre `http://127.0.0.1:5000`.

Producción con Gunicorn:

```bash
gunicorn --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:5000 wsgi:app
```

Se recomienda inicialmente **un worker** porque el estado y los locks actuales están en memoria. Varios workers tendrían cachés independientes hasta migrar el estado a Redis, PostgreSQL u otro backend compartido.

## API HTTP

Resumen de endpoints:

| Método | Ruta | Finalidad |
|---|---|---|
| GET | `/` | Interfaz web |
| GET | `/health/live` | Proceso vivo |
| GET | `/health/ready` | Snapshot ferroviario disponible |
| GET | `/api/trains` | Trenes y diagnóstico de feeds |
| GET | `/api/stations` | Estaciones conocidas |
| GET | `/api/routes` | Rutas y geometrías disponibles |
| GET | `/api/routes/viewport` | Geometría bajo demanda por viewport |
| GET | `/api/alerts` | Alertas de servicio |
| GET | `/api/operators` | Estado de operadores |
| GET | `/api/transit-networks` | Redes urbanas y regionales |
| POST | `/api/feeds/refresh` | Fuerza renovación de feeds |
| GET/POST/DELETE | `/api/operators/config` | Configuración local de operadores |
| GET | `/api/diagnostics` | Estado interno seguro |
| GET | `/api/diagnostics/log` | Descarga del log operativo |
| DELETE | `/api/diagnostics/errors` | Limpia errores recientes |
| GET | `/api/adif/catalog` | Catálogo público ADIF |
| GET | `/api/adif/layer` | Capa ArcGIS/GeoJSON permitida |

Contratos y ejemplos completos: [docs/API.md](docs/API.md).

## Pruebas

```bash
source .venv/bin/activate
RADAR_LOG_FILE=/tmp/radar-pytest.log pytest -q
```

Comprobación de sintaxis:

```bash
python -m py_compile \
  app.py wsgi.py \
  src/radar_app/application.py \
  src/radar/*.py \
  src/radar/gtfs/*.py \
  tests/*.py
```

La estrategia de tests se explica en [docs/TESTING.md](docs/TESTING.md).

## Cachés y persistencia

- `cache/operators/*.zip`: GTFS descargados.
- `cache/operators/operator_config.json`: configuración local sensible.
- `real_tracks_cache_v6.json`: geometrías procesadas cuando existe.
- `overpass_viewport_cache_v1.json`: consultas Overpass persistidas.
- `logs/radar_errors.log`: warnings y errores rotativos.

Las escrituras JSON críticas usan fichero temporal, `fsync` y `os.replace` para reducir corrupción ante interrupciones.

## Observabilidad

```bash
curl -s http://127.0.0.1:5000/health/live | python -m json.tool
curl -s http://127.0.0.1:5000/health/ready | python -m json.tool
curl -s http://127.0.0.1:5000/api/diagnostics | python -m json.tool
```

Interpretación y runbooks: [docs/OPERATIONS.md](docs/OPERATIONS.md) y [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Docker y producción

```bash
docker compose build
docker compose up
```

Antes de producción revisa:

- Gunicorn en lugar del servidor de desarrollo de Flask.
- Terminación TLS en AWS Application Load Balancer, CloudFront, Nginx o servicio equivalente.
- Secretos fuera de la imagen.
- Límites de memoria y disco.
- Egress permitido hacia fuentes GTFS, Overpass y ADIF.
- Persistencia explícita para cachés si se desea warm start.

Más información: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Seguridad y limitaciones

- No es una herramienta de control ferroviario ni evita colisiones.
- Las posiciones pueden estar retrasadas, ausentes o ser aproximadas.
- Nunca confíes en el mapa para decisiones de seguridad física.
- `/api/adif/layer` debe conservar validaciones para evitar SSRF al evolucionar.
- Los endpoints de configuración y borrado deben protegerse antes de exponer la aplicación a Internet.
- Revisa las condiciones de uso y atribución de cada proveedor.

Consulta [SECURITY.md](SECURITY.md) para comunicar vulnerabilidades.

## Documentación técnica

- [Arquitectura](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [Fuentes de datos](docs/DATA_SOURCES.md)
- [Desarrollo](docs/DEVELOPMENT.md)
- [Pruebas](docs/TESTING.md)
- [Operación](docs/OPERATIONS.md)
- [Despliegue](docs/DEPLOYMENT.md)
- [Resolución de problemas](docs/TROUBLESHOOTING.md)
- [Decisiones de arquitectura](docs/ADR.md)
- [Historial de modularización](MODULARIZATION.md)
- [Contribución](CONTRIBUTING.md)

## Contribución

Consulta [CONTRIBUTING.md](CONTRIBUTING.md). Cada cambio debe mantener los contratos HTTP, añadir pruebas relevantes y no incluir datos descargados, logs ni secretos.

## Licencia

Añade un fichero `LICENSE` antes de publicar formalmente el repositorio. Hasta entonces, el código no concede automáticamente derechos de reutilización a terceros.
