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

## Política NAP desde la fase 6.3

La adquisición acepta cuatro respuestas válidas: ZIP GTFS directo, redirección HTTP,
JSON con URL temporal y texto que contiene JSON o una URL. Antes de guardar se
validan la firma ZIP y las tablas `stops`, `routes`, `trips` y `stop_times`.

Orden de resolución: caché fresca, NAP autenticado, fallbacks públicos y caché
caducada validada. Si NAP responde `Archivo no encontrado`, Metrovalencia o
Mallorca pueden continuar como `stale` cuando existe un ZIP local anterior.

## Actualización de fuentes de Metrovalencia y Mallorca (fase 6.3.1)

- Metrovalencia conserva la página de catálogo NAP `Detail/967`, pero la descarga
  autenticada usa el identificador de fichero vigente `1168`.
- Mallorca utiliza como estrategia primaria directa el ZIP oficial publicado por
  TIB, sin depender del antiguo `downloadLink/1071`.
- Los endpoints muestran `source_page`, `source_strategy`, `nap_file_id`,
  `fallback_urls`, intentos, edad y estado stale para facilitar auditoría.
