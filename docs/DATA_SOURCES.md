# Fuentes de datos

## Principios

Cada fuente se considera no confiable a nivel operativo: puede cambiar esquema, caducar, limitar tráfico, responder lentamente o desaparecer. La aplicación debe validar contenido, aplicar timeout, aislar errores y conservar datos válidos previos cuando sea seguro.

## Renfe GTFS-RT

Se consumen posiciones y alertas disponibles públicamente. Los identificadores de ruta, viaje y vehículo no siempre se corresponden de forma uniforme entre feeds. La clasificación nacional combina metadatos y heurísticas.

Riesgos:

- posiciones ausentes o sin velocidad;
- timestamps desalineados;
- etiquetas inconsistentes;
- cambios no anunciados;
- cobertura parcial de FEVE/RAM.

## GTFS estático

Los feeds ZIP deben incluir `stops.txt`, `routes.txt`, `trips.txt` y `stop_times.txt`. El calendario puede venir en `calendar.txt`, `calendar_dates.txt` o ambos. GTFS admite horas superiores a `24:00:00`.

## NAP

Algunas redes se descargan mediante endpoints del Punto de Acceso Nacional. Una respuesta HTTP 200 no garantiza un ZIP: puede ser JSON con enlace, texto, una respuesta intermedia o un dataset sin fichero activo. La fase 6.3 debe endurecer estas variantes.

## OpenStreetMap y Overpass

Las geometrías son datos colaborativos. Debe mantenerse la atribución exigida por OpenStreetMap y respetar las políticas de uso de cada instancia Overpass.

La aplicación rota entre mirrors, pero no debe tratar las instancias comunitarias como infraestructura garantizada. Evita consultas globales repetitivas y conserva caché local.

## ADIF y ArcGIS

El catálogo y capas pueden variar en esquema, paginación y límites. No todas las URLs catalogadas devuelven GeoJSON directamente.

## Datos derivados

Velocidad, bearing, posición ajustada a vía, trenes estimados y posibles horarios inferidos son cálculos de la aplicación. Deben etiquetarse como estimados y nunca confundirse con telemetría certificada.
