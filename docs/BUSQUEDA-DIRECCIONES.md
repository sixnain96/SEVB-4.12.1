# Sugerencias y búsqueda de direcciones del pasajero (Villavicencio)

Estado: implementado y probado con un **Google simulado** (servidor local y respuestas fijas ficticias). Sin publicar. **No se midió la calidad ni la velocidad reales de Google**: ver «Qué falta validar».
Código: `LugarController`, `LugarService`, `GoogleDireccionesService`, `DireccionesHibridasService` (solo sus funciones estáticas de comparación), `CityArea`, `LugarResponse`,
`planner.js` (lógica compartida por el planificador A/B y el flujo guiado), `home.css`.

## Causas reproducidas (antes de cambiar nada)

Se escribió `BusquedaPertinenciaTest` contra el código anterior: **10 de sus 17 comprobaciones fallaron** (ver `target/surefire-reports` de esa corrida; hoy pasan las 17).

| Clase | Qué se reprodujo | Dónde estaba la causa |
|---|---|---|
| 1. La interfaz no muestra lo que llegó | Las pruebas de `busqueda_e2e.py` ya cubren cancelación, respuestas tardías y A↔B; **no se reprodujo un fallo nuevo** en la lista (debounce de 220 ms, una consulta por pausa y control de generación funcionan) | — (se amplió la cobertura) |
| 2. El backend descartaba candidatos válidos | Escribiendo «Calle 3» se descartaba «Calle 30»; «Carrera 22 #3» descartaba «#38-10» | **Filtro** (`sugerenciaRelevante`): comparaba los dos primeros números de forma exacta, también el último fragmento que aún se estaba escribiendo |
| 3. Google sin candidatos o caído | Sin candidatos → `SIN_COINCIDENCIAS`; caído (503) → un estado distinto | Funcionaba; se dejó cubierto con pruebas |
| 4. Un lugar parecido que es otra cosa | «Calle 30 Bis #38-10» se aceptaba como «Calle 30 #38-10»; «Sur», «Norte» y sin sentido se mezclaban al escribir; una vía sin número no explicaba nada | **Filtro** de la búsqueda explícita (no comparaba Bis) y mensaje |
| 5. Tocar la opción correcta y recibir otra | Si Google devolvía **otra sede** con el mismo proveedor, el navegador aceptaba `lugares[0]` | **Resolución**: `LugarResponse` perdía el identificador de Google y nada lo validaba |

Además: «cra22 #38-10» (abreviatura pegada al número) no se normalizaba; un nombre comercial como «TV Center» corría el riesgo de reescribirse como «Transversal Center»; el texto de la búsqueda
explícita no llevaba el contexto «Villavicencio, Meta»; dos sedes con el mismo texto se colapsaban en una (se deduplicaba por texto, no por identificador).

**Configuración (`/api/lugares/diagnostico`):** el diagnóstico informa `soloGoogle`, `googleActivo`, `claveDelServidorConfigurada`, `mapaEsGoogle` y un `motivo`. En este equipo el `.env` define
`MAP_PROVIDER`, `GOOGLE_MAPS_API_KEY` (clave del servidor para Places), `GOOGLE_MAPS_MAP_ID` y `GOOGLE_CLIENT_ID`; **no define `GOOGLE_MAPS_BROWSER_KEY`** (la clave del mapa del navegador es otra
configuración). No se hicieron llamadas reales a Google con esa clave (decisión consciente: es una clave de pago y no se pidió autorización), así que **el problema no está en la configuración sino en el
filtro y en la resolución**, y la verificación con Google real queda pendiente.

## Qué cambió

**Mientras se escribe (consulta parcial)**
- El último fragmento numérico sin cerrar (la consulta no termina en espacio) es un **prefijo**: «Calle 3» admite Calle 30 y 31 y la coincidencia exacta («Calle 3») va **primero**. Con «Calle 30 »
  (espacio) el número queda cerrado: ya no valen «Calle 3» ni «Calle 30A». Los componentes completos se comparan exactos (Calle≠Carrera, 30≠30A, Sur≠Norte; «Bis» o un sentido escrito deben aparecer).
- El controlador conserva **un** espacio final para poder distinguir ambos casos (antes lo recortaba).
- La normalización (`cra22`, `Cra.`, `Kra`, `No.`, `#`) solo se aplica a lo que **parece una dirección** (vía + número); un nombre se envía tal cual. Se agregó `regionCode: co` al autocompletado.
- Se deduplica por **identificador de Google** (dos sedes con el mismo nombre se conservan, con su referencia secundaria distinta); no se añade nada sintético y no hay búsqueda de texto ni Place Details por
  predicción ni por tecla (una consulta por pausa; verificado).

**Búsqueda explícita (Enter / «Buscar»)**
- La comparación de la placa distingue ahora **Bis** además de vía, números, letras y sentido. Una vía sin número, el barrio, el centro o «#38-11» **nunca** se confirman como «#38-10»; si solo hay la vía se dice
  «Encontramos la vía, pero no ese número. Usa «Elegir en el mapa»…».
- Para una dirección numerada la consulta de Text Search lleva «Villavicencio, Meta» salvo que la persona haya nombrado otra ciudad (así «Bogotá» no se vuelve un sitio local). El rectángulo de
  `locationRestriction` **no se usa como garantía**: cada coordenada se revisa en el servidor y el área de servicio no se amplió. No se agregó ningún segundo intento (se documenta como posible mejora acotada).

**Al tocar una opción**
- `LugarResponse` lleva `googleId` (nuevo, compatible; separado del `id` interno). El servidor **exige** que el detalle devuelva el mismo identificador (`RESPUESTA_INVALIDA` si es otro o falta) y lo vuelve a
  comprobar en `LugarService`; el navegador también compara `googleId` con la opción tocada. Si no coincide, queda «Reintentar / Volver a elegir» con el texto conservado: nunca se sustituye por una búsqueda de
  texto ni por otro resultado. Fuera del área o coordenadas inválidas siguen el mismo camino.
- Mensajes junto al campo: «Todavía no encontramos ese lugar. Prueba con el barrio o marca el punto en el mapa.» y, ante fallos, «Google no pudo responder. Intenta de nuevo…» con «Elegir en el mapa» a mano.

**Sin cambios a propósito:** el debounce de 220 ms (la medición no mostró un problema de velocidad en la interfaz), el combobox/listbox y el manejo táctil existentes, el caché **solo en memoria** (no se guardan
predicciones, respuestas ni textos en localStorage, service worker ni analítica) y la atribución.

## Halo en «¿A dónde quieres ir?»

**Retirado.** El panel principal con A y B se conserva sin cambios visuales; ya no existe `halo-campo.js` ni su CSS.

## Antes y después (Google SIMULADO, mismas 16 entradas)

| Entrada | Esperada | Antes: top-3 | Después: top-3 | Consultas a Google |
|---|---|---|---|---|
| Calle 3 | c30 | NO | sí | 1 |
| Carrera 22 #3 | k38 | NO | sí | 1 |
| Carrera 22 #38-1 | k38 | sí | sí | 1 |
| Cra. 22 #38-10 | k38 | sí | sí | 1 |
| Kra 22 38 10 | k38 | sí | sí | 1 |
| Cll 30 | c30 | sí | sí | 1 |
| Calle 30 Sur | c30s | sí | sí | 1 |
| Calle 30A | c30a | sí | sí | 1 |
| Unicentro | uni | sí | sí | 1 |
| clinica meta | sedeN | sí | sí | 1 |
| terminal de transportes | term | sí | sí | 1 |
| universidad llanos | ul | sí | sí | 1 |
| barzal | bz | sí | sí | 1 |
| parque fundadores | pf | sí | sí | 1 |
| clinica villavicencio | (ninguna) | sí | sí | 1 |
| calle 99999 sin sentido | (ninguna) | sí | sí | 1 |

**Casos válidos con la opción pedida entre las 3 primeras:** antes 12/14 · después 14/14  
**Casos sin coincidencia válida resueltos como «nada»:** antes 2/2 · después 2/2  
**Selecciones que confirman un lugar equivocado:** antes 1 de 4 (la sede equivocada se aceptaba) · después 0 de 4 (se rechaza y se pide volver a elegir)  
**Consultas a Google:** 16 para 16 entradas (una por pausa; el filtro no añade ninguna) — idéntico antes y después.

Tiempo de la interfaz (stub sin latencia, móvil 360×640): **≈ 240 ms** desde la última tecla hasta la lista (220 ms de debounce + dibujo), igual antes y después porque no se cambió. La velocidad del proveedor
real no se midió. Resultado funcional ≠ velocidad: la mejora medida es de **pertinencia** (12/14 → 14/14 opciones pedidas entre las 3 primeras) y de **identidad** (1 de 4 selecciones equivocadas → 0), no de rapidez.

## Pruebas

- Java: `BusquedaPertinenciaTest` (17), `ComparacionBusquedaTest` (tabla de arriba, en `target/comparacion-busqueda.md`) y las suites existentes de `Lugar*`, `Google*` y `Direccion*` (fixtures actualizados: el detalle
  ahora debe traer el `id` pedido).
- Navegador: `busqueda_e2e.py` (+6: otra sede, dos sedes, vía sin número, letra por letra y pegar, Escape/Enter, flechas), `guiado_e2e.py` (+1) y `halo_destino_e2e.py` (8).

## Qué falta validar (teléfono y Google real)

1. Con una clave autorizada: las 16 búsquedas con Google real (¿entre las 3 primeras?, ¿se confirma el ID?, ¿el pin es el esperado?). Los casos de la tabla son ficticios.
2. Teclado virtual real a 320×568, 360×640 y 390×844 (la lista junto al campo y sobre el teclado), `inputOffset` al editar en medio del texto (no se usa: el texto completo se envía normalizado),
   composición de teclados con predicción en Android/iOS.
3. Latencia real de Places y comportamiento ante cuota; segundo intento acotado de Text Search si el uso real lo justifica.

---

# Fase G · Nomenclatura colombiana: «carrera 27 número 35A 50» → «Carrera 27 # 35A-50»

Estado: implementada y probada con un **Google simulado**; sin publicar. Código: `CityArea.normalizeColombianAddress` (normalizador compartido), `Nomenclatura` (nuevo), `LugarService`, `GoogleDireccionesService`, `LugarResponse`, `planner.js`.

## Patrones que admite

- **Vía:** Carrera, Calle, Avenida, Diagonal y Transversal, y sus abreviaturas (Cra., Kra., Kr, Cr, Cll., Cl., Av., Avda., Dg., Diag., Tv., Transv.), también pegadas al número («cra22», «cll30»).
- **Identificador de la vía:** número con letra, `Bis` y sentido (Norte, Sur, Este, Oeste): «Calle 15 Bis Sur».
- **Separador:** `#`, «No.», «No», «N.º», «Nº», «N°», «número», «numero», «nro», «num» (solo si le sigue una cifra y solo si hay una vía con número: «Clínica Número 5» y «Colegio Nacional No. 3» no se tocan; «Cra 27 número» a medio escribir queda «Carrera 27 #»).
- **Placa:** dos fragmentos con letra en cualquiera de los dos, separados por guion, «a» o **solo espacios** (si tras la vía hay exactamente dos cifras): «35A 50», «35A - 50», «20A 10B». Con tres cifras o con una sola se conserva el texto (admite dos lecturas) para que Google sugiera.
- **Barrio o referencia al final:** se conserva y acompaña la búsqueda («… # 35A-50 barrio Cataluña»).
- Mayúsculas y signos se arreglan (`35a` → `35A`, `bis` → `Bis`); no se cambia «35A» por «35», «50» por «5», Calle por Carrera ni se quita Sur/Norte/Bis. Es **idempotente**.

| Entrada | Antes | Después |
|---|---|---|
| carrera 27 número 35A 50 | sin cambio (Google recibía el texto crudo) | Carrera 27 # 35A-50 |
| carrera 48 numero 25A 50 | sin cambio | Carrera 48 # 25A-50 |
| Cra. 27 No. 35A-50 / Kra 27 #35A - 50 | Carrera 27 # 35A-50 (ya funcionaba) | igual |
| Cra 27 35A 50 | placa sin separar | Carrera 27 # 35A-50 |
| Cll. 30 N° 38 10 | placa sin separar | Calle 30 # 38-10 |
| Carrera 27 Norte número 5 50 | sin cambio | Carrera 27 Norte # 5-50 |
| Calle 15 Bis Sur # 20A 10B | letra del 2.º fragmento sin guion | Calle 15 Bis Sur # 20A-10B |
| cra 27 nº 35a-50 | Carrera 27 # 35a-50 (letra en minúscula) | Carrera 27 # 35A-50 |
| Colegio Nacional No. 3 | Colegio Nacional # 3 (cambiaba un nombre) | sin cambio |

`NormalizacionDireccionTest` falló 8 de 9 comprobaciones antes del cambio y pasa 9 de 9; el `#` viaja en el JSON tal cual y por URL como `%23` (probado).

## Escritura, búsqueda y selección

- **Escribiendo:** el campo conserva lo que la persona escribió (cursor incluido); la versión normalizada la arma el servidor solo para consultar a Google. «Cra 27», «Cra 27 número», «Cra 27 número 35A» funcionan: «número» cierra la vía y el último fragmento sin cerrar es un prefijo (`35A` admite `35A-50` pero no `35-50`). Debounce de 220 ms, cancelación, un token de Places por campo y una consulta por pausa se mantienen. Pegar y editar en medio del texto hacen una sola consulta.
- **Buscar / Enter sin opción resaltada:** la consulta normalizada + «Villavicencio, Meta» (salvo otra ciudad) sale a Text Search **una sola vez** (no hay segundo intento: los números no se tocan, la forma ya es la canónica y no hay evidencia que justifique una variante). La respuesta se compara **por componentes** con `Nomenclatura` (tipo, vía, Bis, sentido y los dos fragmentos de la placa, letras incluidas), usando los componentes estructurados de Google (`route` + `street_number`) cuando vienen y, si no, la dirección devuelta con las mismas reglas. «35A-50» ≠ «35-50» ≠ «35A-51»; Calle ≠ Carrera; Sur ≠ sin sentido. Si solo hay la vía: «Encontramos la carrera, pero no ese número. Puedes marcar el punto en el mapa»; si falta un fragmento: «Falta un dato de la placa: escribe los dos números, por ejemplo «Carrera 27 # 35A-50»».
- **Elegir una opción:** se resuelve ese `placeId` con Place Details (el identificador devuelto debe ser el elegido, con coordenadas válidas y dentro del área; si no, «Reintentar / Volver a elegir» con el texto conservado) y se **muestra la dirección formateada de Google** bajo el campo («goodir carrera 27 — Cra. 27 #35A-50, Villavicencio, Meta»: lo elegido y la dirección que devolvió Google). Una sugerencia de vía se rotula «Vía ·» (no aparenta una puerta) y una puerta muestra su placa; si Google ubicó solo la vía o el sector se dice con su alcance real. Una respuesta vieja no mueve el pin (generación vigente; cubierto por las pruebas ya existentes).
- **Campos nuevos y costo:** `LugarResponse.nomenclatura` (vía + placa armada con los componentes de Google; compatible) y la máscara de campos pide ahora `addressComponents` (según la documentación de Places API (New) es Essentials en Place Details y, en Text Search, va junto a `displayName`, que ya se pedía). **Verifica el SKU en la tabla de Google antes de producción:** https://developers.google.com/maps/documentation/places/web-service/place-details

## Pruebas (todas con Google SIMULADO)

- `NormalizacionDireccionTest` (9): tabla de ejemplos, otros formatos, barrio al final, parciales, ambiguas, pares distintos, nombres de establecimientos, idempotencia y `#` en la URL.
- `BusquedaNomenclaturaTest` (11): qué consulta sale; misma placa escrita de otra forma (con y sin componentes); otra placa, otra vía u otro sentido devuelta primero (nunca se confirma); solo vía o barrio; falta la placa; fuera del área, cero coincidencias y error; otra ciudad escrita; una sola consulta sin segundo intento; parciales; dos opciones parecidas con identificadores distintos; nombres de establecimientos sin tocar. Más `BusquedaPertinenciaTest` (identificador distinto en el detalle).
- `busqueda_e2e.py` (41) y `guiado_e2e.py` (29): escritura tecla a tecla en origen y destino, `#` intacto en la consulta, pegar y editar en medio, vía frente a puerta, dirección de Google visible, solo vía y las pruebas anteriores (respuesta tardía, A↔B, teclado y toque).

## Pendiente de verificar con Google real y teléfono

1. Con un entorno autorizado: al menos 12 búsquedas de Villavicencio (vías, placas y abreviaturas distintas) comparando antes y después: ¿la dirección esperada entre las 3 primeras?, ¿se confirma el mismo lugar elegido?, ¿cuántas consultas? **No se hizo ninguna llamada real** (no se usó la clave de pago del `.env` sin autorización). Los ejemplos ficticios solo prueban la gramática.
2. Cómo formatea Google las placas con letra o Bis en Villavicencio (los componentes `route` y `street_number` reales) y si hay variantes que `Nomenclatura` no reconozca.
3. Teclado virtual real y composición con predicción en Android/iOS.
