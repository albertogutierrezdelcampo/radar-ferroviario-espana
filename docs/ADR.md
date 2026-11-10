# Registro de decisiones de arquitectura

## ADR-001: Flask y migración incremental

**Decisión:** mantener Flask y extraer responsabilidades por fases.  
**Motivo:** reducir riesgo sobre endpoints y frontend ya funcionales.  
**Consecuencia:** existe temporalmente un composition root grande.

## ADR-002: Source layout

**Decisión:** código Python bajo `src/`.  
**Motivo:** imports explícitos, empaquetado futuro y separación del repositorio.  
**Consecuencia:** tests y ejecución deben incluir `src` en el path hasta disponer de paquete instalable.

## ADR-003: Estado único en memoria

**Decisión:** `ApplicationState` centraliza caches y locks.  
**Motivo:** eliminar mutables dispersos y facilitar inyección.  
**Consecuencia:** un worker recomendado hasta externalizar estado.

## ADR-004: Stale cache ante fallo externo

**Decisión:** preferir datos anteriores identificados como stale frente a ausencia total cuando resulte seguro.  
**Motivo:** los proveedores externos no tienen disponibilidad garantizada.  
**Consecuencia:** la API debe indicar edad y procedencia.

## ADR-005: Rotación Overpass

**Decisión:** un intento acotado por mirror y fase, con cooldown y telemetría.  
**Motivo:** evitar bloqueo prolongado en un mirror comunitario.  
**Consecuencia:** una carga completa puede tardar varios minutos si todos fallan.
