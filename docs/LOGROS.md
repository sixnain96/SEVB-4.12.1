# Logros, medallas y racha de viajes (Fase D)

Estado: implementado y probado con Google y GPS **simulados** (ver «Qué no se probó»). Sin publicar. Frontend en `js/logros.js` (más `iconos.js`, `viaje.js`, `viaje-nucleo.js`, `cuenta.js`,
`home.css`, `index.html`); backend en `LogrosService`, `Racha`, `LogrosController` y la migración `V15__logros_viajes.sql`.

## Qué cuenta como viaje

Un viaje suma **una sola vez**, al **llegar de verdad** con **al menos una subida a un bus confirmada**.

- El núcleo del viaje (`viaje-nucleo.js`) lleva `subidas`: los tramos en los que la persona confirmó «Sí, me subí» (pregunta automática o botón «Ya me subí»). Se guarda con el viaje
  (`serializar`/`restaurar`); un estado guardado por una versión anterior las deduce de la fase.
- `viaje.js` crea un **id lógico** (`viajeId`) por viaje. Se conserva al **reanudar** (se guarda como `vid`) y al **recalcular** (el recorrido nuevo tiene su propio `id` interno, que
  «Compartir mi viaje» necesita, pero el mismo `viajeId`; las subidas ya confirmadas pasan como `previas`).
- El evento `spevb-viaje-llegada` trae `{ viajeId, llegadaMs, subidas, busConfirmado, buses, inicio, resumen }` (compatible con `compartir.js` y `flujo-guiado.js`, que lo ignoran).
- **No suman:** abandonar el viaje, pulsar «Cerrar» sobre una llegada ya registrada, recargar, repetir el evento, el tutorial/práctica, ni un evento sin id, sin hora o sin subida confirmada.
- **Transbordo:** un viaje de dos buses cuenta como **un** viaje; el logro «Con transbordo» exige **dos subidas confirmadas**, no solo que el plan tuviera dos buses.
- **Recuperación tras un desvío:** cuenta si hubo una subida confirmada y se llegó de verdad.

## Racha

Calculada por `Racha.java` (servidor) y su espejo en `logros.js`, con los **mismos vectores** (`src/test/resources/racha-vectores.json`).

- Días de calendario de **Bogotá (UTC-5 fijo)**, nunca los de la zona del teléfono. Un día cuenta **una** vez aunque tenga varios viajes; el total cuenta todos.
- **Un día vacío de gracia** entre dos días con viaje: lunes y miércoles siguen en la misma racha (2 días). Dos o más días vacíos seguidos la cortan.
- La racha **actual** sigue vigente mientras el último día con viaje esté a ≤ 2 días de hoy: lunes con viaje → el martes y el miércoles aún se puede continuar; el **jueves vale 0** y el
  primer viaje del jueves vale 1.
- Se conservan la **mejor racha** (con gracia) y la **racha estricta** (días consecutivos sin hueco). «3 días seguidos» y «Una semana» **conservan su significado antiguo** (usan la estricta).
- Se deriva al abrir el menú, al volver de segundo plano, al volver la conexión y con **un solo temporizador** a la próxima medianoche de Bogotá (sin intervalos frecuentes).
- El reloj es controlable para probar: `Spevb.Reloj.fijar(ms)`, `.avanzar(ms)`, `.restaurar()`.

Niveles de la llama (dibujo propio `llamaN1…4` en `iconos.js`, misma cuadrícula 24×24): 1–2 días, 3–6, 7–13, 14 o más. El **número y el texto** dicen la racha («Racha de 3 días»;
sin racha: «Empieza tu racha con tu próximo viaje»); el icono y el color solo acompañan. Al subir de nivel hay un destello breve; con «reducir movimiento» queda un aro fijo.

## Catálogo y recompensas

| Logro | Cómo se consigue | Recompensa visual (privada) |
|---|---|---|
| Primer viaje | 1 viaje | Insignia «Mi primer viaje» |
| 5 viajes | 5 viajes | Marco de ruta (círculo discontinuo con un bus) para la foto |
| 20 viajes | 20 viajes | Medalla «20 viajes» |
| Con transbordo | 1 viaje con dos subidas confirmadas | Medalla con dos líneas de bus |
| 3 días seguidos / Una semana | racha estricta de 3 / 7 | Medallas de llama |
| Madrugador / De noche | llegada antes de las 7 a. m. / después de las 7 p. m. (Bogotá) | Insignias |
| Aprendiz | terminar la práctica (no suma viajes ni racha) | Insignia «Aprendiz» |
| Viajero del Llano | 30 viajes **y** racha (con gracia) de 7 días | Borde ilustrado del Llano y medalla «Viajero del Llano» |

«Ajustes de la cuenta → Mis medallas» muestra las ganadas y permite **destacar o quitar una**. Se ve junto a la foto (marco o insignia pequeña); los colores quedan dentro del marco, la
medalla o el detalle. La foto de Google y el avatar regional conservan su prioridad. El servidor **valida** que la insignia exista y esté ganada.

Cada medalla es un botón (también las bloqueadas): al tocarla o con Enter/Espacio se lee el **requisito, el progreso y la recompensa** (región `aria-live`). El estado se dice con texto
(«Ganado» / «Por conseguir»), no solo con color. Tras llegar hay **una** celebración agrupada (racha y logros nuevos) y nada si no hay nada nuevo.

## Dónde se guarda

- **Con sesión:** en la **cuenta** (tablas `logros_viaje` y `logros_perfil`). El estado se **deriva** de los viajes: dos dispositivos con la misma cuenta no suman contadores, suman viajes
  distintos. Operación **idempotente por cuenta + `viajeId`**. Solo se guarda: id del viaje (aleatorio), momento de llegada, día de Bogotá, buses confirmados (1–6) y hora local;
  **nunca** coordenadas, direcciones, trayectorias ni tokens. Límites: 5 000 viajes por cuenta, 60 por día, llegada entre hace 30 días y +5 min. Se borran al borrar la cuenta (`ON DELETE CASCADE`).
- **Sin sesión:** solo en el dispositivo (`spevb-logros-v2`).
- **Envíos pendientes** (sin conexión): cola `spevb-logros-cola` por cuenta; se reintenta al volver la conexión, al volver a primer plano y al abrir el menú; el servidor ignora repetidos.
  Un rechazo definitivo (400/409/429) se descarta. Al **cerrar sesión o cambiar de cuenta** se borran la copia (`spevb-logros-cuenta`), la cola y los resúmenes de la cuenta, y una respuesta
  tardía de otra cuenta o de una sesión anterior se descarta (identidad + generación de sesión).
- **Progreso antiguo del dispositivo (`spevb-logros`, versiones ≤ 4.15.0):** se **conserva** para quien usa SEVB como invitado (sus viajes, transbordos, logros ganados y su racha de días
  seguidos cuentan en su vista) y **nunca se adjudica automáticamente a la primera cuenta que entra**: la cuenta empieza desde sus propios viajes. No se borra.
- **Nivel de confianza: recreativo.** Lo envía el dispositivo; el servidor valida formato, ventana de tiempo y límites, pero no puede demostrar que la persona viajó. No hay premios con valor.

## API (solo con sesión; mismo origen; limitada a 120/min por cuenta)

- `GET /api/cuenta/logros` → estado `{ viajes, transbordos, rachaActual, mejorRacha, mejorEstricta, madrugador, nocturno, practica, logros[], insignia, hoy, ultimoDia, dias[≤120] }`.
- `POST /api/cuenta/logros/viaje` `{ viajeId, llegadaMs, buses }` → estado + `nuevo` + `nuevos[]`.
- `POST /api/cuenta/logros/practica` · `POST /api/cuenta/logros/insignia` `{ id|null }`.

## Pruebas

- Java: `RachaTest` (vectores, día/hora de Bogotá, significado antiguo de los logros), `LogrosPostgresTest` (PostgreSQL real: idempotencia, validaciones, racha con gracia, fuera de orden,
  transbordo, práctica sin viajes, insignias, aislamiento entre cuentas, límites, borrado en cascada; Testcontainers o `SEVB_TEST_PG_URL`).
- Navegador: `e2e/logros_e2e.py` (24 pruebas: vectores compartidos, zonas horarias del teléfono, gracia, mes/año/bisiesto, fuera de orden, medianoche, qué cuenta, viaje real con transbordo y
  recálculo, estado antiguo, práctica, progreso antiguo, cuenta en dos dispositivos y dos pestañas, cola sin conexión, rechazo, cambio de cuenta, niveles de la llama, teclado y roles,
  perfil/insignia, celebración única, reducir movimiento y modo oscuro). Capturas en `docs/capturas-viaje/logros-*.png`.

## Qué no se probó

Google real; un viaje real en bus (todo con GPS simulado); lectores de pantalla reales (se verificaron roles, nombres y regiones `aria-live`); el destello a velocidad real en un dispositivo.
