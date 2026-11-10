# Política de seguridad

No publiques vulnerabilidades con exploits o secretos en una issue pública. Comunícalas de forma privada al mantenedor del repositorio.

Incluye versión, impacto, pasos mínimos de reproducción y mitigación propuesta. No adjuntes tokens, `.env`, logs sin revisar ni datos personales.

Áreas especialmente sensibles:

- SSRF en consultas de capas externas;
- exposición de tokens NAP u operadores;
- endpoints administrativos sin autenticación;
- inyección en HTML generado;
- agotamiento de recursos mediante refresh o viewport;
- dependencias Python y JavaScript vulnerables.
