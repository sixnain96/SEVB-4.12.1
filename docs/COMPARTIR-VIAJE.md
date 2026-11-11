# Compartir mi viaje · SEVB 4.15.0

Una persona que viaja puede dejar que alguien de confianza vea **su avance aproximado** durante ese viaje. Es opcional, nunca bloquea el viaje y se cierra sola.

## Qué ve cada quien
- **Quien viaja** (modo viaje → «Más» → **Compartir mi viaje**): lee una explicación, toca **Crear enlace** (nada se crea sin esa acción) y recibe el enlace para **Compartir de nuevo** (Web Share si el navegador lo ofrece), **Copiar enlace** o **Compartir por WhatsApp** (acción explícita; si algo no existe queda «Copiar enlace»). Mientras comparte, la tarjeta del viaje muestra «Compartiendo tu viaje» y **Dejar de compartir** (pide confirmación).
- **Quien acompaña** abre `/seguir.html#<token>` sin iniciar sesión: estado en palabras («Va en el bus M01», «Llegó a su destino»…), barra de avance, esquema del recorrido con un punto donde va, «Última actualización» y, si el dato está viejo (> 90 s), **«Esperando una nueva señal»**. Es **de solo lectura**: sin formularios, menú, cuenta, historial ni herramientas del planificador.

## Arquitectura
| Pieza | Archivo |
|---|---|
| Interfaz de quien viaja | `static/js/compartir.js`, estilos en `css/viaje.css` |
| Página pública | `static/seguir.html`, `js/seguir.js`, `css/seguir.css` |
| API | `controller/ViajeCompartidoController.java` (`/api/compartir`) |
| Lógica y SQL | `service/ViajeCompartidoService.java` |
| Tabla | `db/migration/V13__viaje_compartido.sql` (`viajes_compartidos`) |
| Cabeceras de la página pública | `config/EditorSecurityFilter.java` |

API (los tokens viajan en **cabeceras**, nunca en la URL de la API):
- `POST /api/compartir` `{ruta:{tramos,etiquetas}}` → `{lectura, escritura, expira}`. Sin una ruta válida responde 400: no se puede compartir sin un viaje.
- `PUT /api/compartir` (cabecera `X-Seguimiento-Escritura`) `{fase, leg, progreso, lat, lng, precision, etaMin}` → actualiza la **última** posición.
- `DELETE /api/compartir` (cabecera `X-Seguimiento-Escritura`) → revoca (borra la fila). Es idempotente.
- `GET /api/compartir` (cabecera `X-Seguimiento`) → vista pública. Admite `If-None-Match` (ETag = versión) y responde 304 si nada cambió.

## Privacidad y seguridad
- **Dos tokens de 256 bits** (`SecureRandom`, base64url de 43 caracteres): uno de **lectura** (va en el enlace) y otro de **escritura** (queda solo en el dispositivo de quien viaja, `localStorage` bajo `spevb-compartir`, hasta que termina). El de lectura **no puede** actualizar ni revocar.
- **En la base solo hay SHA-256** de cada token (`lectura_hash`, `escritura_hash`); ni la base ni un respaldo permiten reconstruir un enlace.
- El enlace es `…/seguir.html#<token>`: el token está en el **fragmento**, que el navegador no envía al servidor (no queda en registros de acceso ni en el `Referer`).
- **Sin historial**: una sola fila con última posición, fase, progreso y metadatos mínimos. La ruta se valida, se redondea a 5 decimales y se limita (2 tramos, 4 000 puntos); **no se guardan direcciones ni nombres de lugares**. Ojo: la geometría del recorrido sí permite ver hacia dónde va esa persona; por eso se avisa antes de crear el enlace.
- **Nada de tokens ni coordenadas en registros**: el controlador no los escribe en logs y el stub de pruebas solo anota método y ruta.
- Errores **genéricos**: token inválido, vencido, revocado o inexistente responden igual (404 «Este enlace ya no está disponible.»). Cuerpo vacío o `null` en `PUT` → 400 controlado, sin detalles internos.
- Límites: crear 8/hora por red; actualizar 12/min por enlace; consultar 60/min por red; además el límite general de `/api/`.
- Página pública: `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`, `<meta name="robots" content="noindex">`, sin metadatos sociales; `mismoSitio` en las operaciones de escritura (anti-CSRF).

## Caducidad y limpieza
- Vida máxima **3 horas** desde la creación.
- **Llegó:** el servidor deja de aceptar coordenadas, **borra** `lat/lng/precisión`, y el estado final vive **10 minutos** (para que el acompañante vea «Llegó a su destino»).
- **Revocar** (Dejar de compartir, terminar el viaje, cancelar o recalcular el recorrido) **borra la fila al instante**.
- **Cerrar sesión** (una sola o todas) y **eliminar la cuenta** borran los enlaces de esa persona (no quedan huérfanos). Compartir también funciona sin cuenta; esos enlaces solo caducan por tiempo, llegada o revocación.
- No hay tareas programadas en el proyecto: lo vencido se borra **al crear** un enlace nuevo (`limpiar()`) y las consultas ignoran siempre lo vencido.

## Frecuencia y consumo
Se envía como máximo **cada 12 s** o **al cambiar de fase** (no cada lectura cruda del GPS), con un solo envío a la vez y siempre el estado **más reciente** (no una cola). Sin internet el viaje local continúa; al volver la conexión se manda lo último. Se detiene al llegar, revocar, terminar, vencer o si el servidor dice que el enlace ya no existe. La página pública consulta cada 12 s con ETag.

## Pruebas
```powershell
mvn clean verify "-Dsevb.sinDocker=true"          # ViajeCompartidoServiceTest, ViajeCompartidoControllerTest (sin base: JdbcTemplate simulado)
python e2e/run_e2e.py                              # incluye e2e/compartir_e2e.py (navegador, stub con el mismo contrato)
```
La migración V13 y el SQL real solo se ejecutan con Docker (Testcontainers, `MigracionesPostgisTest`); sin Docker se **omiten** y se informan como omitidas.

## Limitaciones
- La página pública dibuja un **esquema** del recorrido (SVG propio), **no un mapa de calles**: así no depende de proveedores de mapa ni de la CSP del mapa.
- La hora de llegada solo se muestra si el viaje tiene una estimación (la del modo viaje); es aproximada.
- Un navegador en segundo plano (pantalla bloqueada) puede dejar de enviar posiciones: la página pública lo muestra como «Esperando una nueva señal».
- Si el recorrido cambia (recalcular), el enlace se cierra y hay que crear otro: el servidor guarda el recorrido original.
- WhatsApp y Web Share se prueban simulados; falta probarlos en un teléfono real.
