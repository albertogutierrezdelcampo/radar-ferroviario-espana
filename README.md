# Renfe & ADIF Live Monitor

1. `python -m venv .venv`
2. Activa el entorno virtual.
3. `pip install -r requirements.txt`
4. `python app.py`
5. Abre `http://127.0.0.1:5000`

La caché de trazados se genera localmente. El detalle por parada depende de la disponibilidad de GTFS estático y GTFS-RT.

## Datos GTFS de OUIGO

El feed oficial del NAP/MITRAMS requiere autenticación. Usa una de estas opciones antes de iniciar:

```bash
# Opción A: token del NAP / proxy autorizado
export OUIGO_GTFS_TOKEN="TU_TOKEN"
python app.py

# Opción B: ZIP GTFS descargado legítimamente
export OUIGO_GTFS_FILE="$PWD/ouigo.zip"
python app.py
```

También puedes colocar el ZIP directamente en `cache/operators/ouigo.zip`. La aplicación conserva el último ZIP válido y no vuelve a descargarlo durante 24 horas. El panel muestra `CFG` cuando falta esta configuración.
