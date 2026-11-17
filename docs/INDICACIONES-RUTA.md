# Indicaciones paso a paso de la ruta recomendada (Fase I)

Estado: implementado y probado con el stub (datos de muestra); sin publicar. **Sin cambios en el backend**: la política de recomendación, el orden, la elegibilidad y `idRecomendada` son los de siempre.
Código: `js/itinerario.js` (modelo y vista, nuevo), `planner.js` (tarjetas, selección, mapa), `flujo-guiado.js` (paso «recomendación»), `viaje.css`/`guiado.css`, `index.html` (`#tripItinerario`).

## Qué cambió

Antes el estado mezclaba motivo, instrucciones y explicación de colores («…camina por la línea punteada… toma el bus por el tramo rojo y bájate en el otro punto») y «el otro punto» no decía dónde bajar.
Ahora hay **tres cosas separadas**, para la opción **seleccionada**:

1. **Encabezado:** «Recomendada · Ruta 876 · Sin transbordo» (solo la que indica `idRecomendada`) u «Opción seleccionada · …» si la persona toca otra tarjeta. Un transbordo dice «Ruta A + Ruta B · 1 transbordo · 2 buses».
2. **Por qué la recomendamos:** una frase armada **solo con datos estructurados del servidor** (`buses` y las `etiquetas` de comparación `SIN_TRANSBORDO`, `PRIMER_BUS_MAS_CERCANO`, `MENOR_CAMINATA_TOTAL`, `MENOR_TIEMPO`, que el servidor manda únicamente si de verdad se compararon). No se lee `rec.motivo` (se conserva como dato en `data-motivo-servidor`).
3. **Pasos numerados** (verbos simples), con «Ver subida» / «Ver bajada» / «Ver cambio»: centran el mapa en ese marcador; **no** inician el viaje ni cambian de opción.

La línea de estado queda corta: «Recomendada: Ruta 876 · Sin transbordo. Sigue los pasos de abajo; «Ver subida» y «Ver bajada» centran el mapa en esos puntos.» Los pasos se muestran en el panel (`#tripItinerario`), a la vista aunque la tarjeta
esté cerrada. El flujo guiado usa **el mismo modelo** (`Planner.itinerario()`): su paso «Esta es nuestra recomendación» lista los mismos pasos y los mismos botones.

## Reglas (qué dato sale de dónde)

| Dato | Fuente |
|---|---|
| Nombre/código de la ruta | `Spevb.rutaPopular(codigo)` (nombre popular) y `codigo` de la opción: «Catama (M02)» o «M01» una vez |
| Subida / bajada | `puntoSubida`/`puntoBajada` y `paraderoSubida`/`paraderoBajada` de **ese tramo** (nunca el paradero de otra opción). Sin nombre: rótulos «Sube aquí» / «Baja aquí» (los mismos del mapa); transbordo: «Sube al primer bus», «Baja del primer bus», «Sube al segundo bus», «Bajada final» |
| Distancias | `acercamientoInicioMetros`, `acercamientoFinMetros` y, en transbordos, `caminataInicio/Cambio/Fin.metros`; si llega la caminata por calles, **ese** paso toma su distancia. Redondeo a 10 m: «unos 30 m» |
| Origen | «tu ubicación» **solo** si el origen salió del GPS (`deGps`); si no, el nombre del punto elegido; sin nombre útil (coordenadas, «Punto en mapa»), «tu punto de salida» |
| Destino | nombre del punto elegido o «tu destino» |
| Aproximada | `caminataPorCalles = false` → «(aprox., en línea recta)» y una nota: todavía no hay trazado a pie por calles para esa parte |

Cosas que **no** se hacen: no hay «gira a la derecha», lado de la calle, número de paradas ni nombres de calles (no existen en los datos); no se muestra «hacia [lugar]» ni el letrero del bus (la planificación no trae un destino/letrero fiable de la ruta);
no se muestran coordenadas; no se dibuja la recta como si fuera una indicación a pie. Caminatas de menos de 15 m: «Ya estás en el punto de subida.» o «Llegas a tu destino.» (nunca «Camina 0 m»). Cambio sin caminata: «Cambia de bus: el segundo bus se toma donde te bajaste, sin caminar.»
**Sentido contrario:** no recibe pasos de embarque (solo la advertencia). **Sin recomendada elegible:** «No hay una opción recomendada que respete el sentido de las rutas…». **Baja y camina:** muestra el punto de bajada y la caminata final.

## Ejemplos reales de la salida (datos de muestra del stub; los nombres de paradero son inventados para la prueba)

**Ruta directa** (con paraderos): `Recomendada · Ruta M01 · Sin transbordo`
- Por qué la recomendamos: Te lleva con un solo bus, sin transbordo.
- 1. Camina unos 240 m desde tu punto de salida hasta el paradero «Paradero Muestra Uno». [Ver subida]
- 2. Toma la ruta M01.  (vas unos X km en el bus)
- 3. Bájate en el paradero «Paradero Muestra Dos». [Ver bajada]
- 4. Desde el paradero «Paradero Muestra Dos», camina unos 40 m hasta tu destino.

Sin nombres de paradero: «…hasta «Sube aquí».», «Toma la ruta M01.», «Bájate en «Baja aquí».», «Camina unos 40 m hasta tu destino.»

**Transbordo:** `Recomendada · Ruta R001 + Ruta R002 · 1 transbordo · 2 buses`
- Por qué: Usa dos buses con un transbordo. Menos caminata en total. Menor tiempo estimado.  (etiquetas que mandó el servidor)
- 1. Camina unos 120 m desde tu punto de salida hasta «Sube al primer bus». [Ver subida]
- 2. Toma el primer bus: la ruta R001.
- 3. Bájate en «Baja del primer bus». [Ver bajada]
- 4. Camina unos 150 m hasta «Sube al segundo bus». [Ver cambio]
- 5. Toma el segundo bus: la ruta R002.
- 6. Bájate en «Bajada final». [Ver bajada]
- 7. Camina unos … m hasta tu destino.

Qué viene de los datos del proyecto: ruta, código y nombre popular, puntos y paraderos de subida/bajada, distancias de cada tramo, número de buses y etiquetas de comparación. Qué es redacción de la interfaz: los verbos, los rótulos «Sube aquí/Baja aquí» y las frases de apoyo.

## Sincronía y caminatas que llegan tarde

Cada tarjeta tiene su propio modelo. Una caminata por calles que llega actualiza **solo el texto de su paso** (no se recrea la lista: el foco se conserva) y solo si la tarjeta sigue conectada y es de la búsqueda vigente (`current === sequence`); la respuesta de una opción anterior no toca la selección actual. En el flujo guiado el paso se vuelve a
pintar con el foco restaurado en el mismo botón. Los rótulos y puntos del mapa se redibujan con la selección vigente; el inicio del viaje usa la misma opción (`Spevb.Viaje.plan()` coincide con los pasos).

## Pruebas

- `e2e/indicaciones_e2e.py` (12): directa con dos paraderos (nombres, código, metros y rótulos), sin nombres + botones (no inician el viaje ni cambian de opción), origen por GPS/manual/con nombre/sin nombre, cambio rápido entre dos opciones con el mismo código, transbordo con y sin caminata, línea recta frente a calles y una caminata tardía con el foco intacto,
  sentido contrario y sin recomendada, «Baja y camina», caminatas muy cortas, 320×568 con letra grande y teclado, el inicio del viaje, y el flujo guiado con el mismo modelo. Se ajustaron dos pruebas de `resultados_e2e.py` al contrato nuevo (el motivo ya no se pega al texto).
- Capturas: `docs/capturas-viaje/indicaciones-320-letra-grande.png`.

## Datos que aún faltan para indicaciones más específicas

- **Sentido / letrero del bus** («hacia el Centro») y su destino final: la respuesta de planificación no los trae de forma fiable.
- **Nombre del paradero en todas las rutas**: hoy solo cuando está asociado al trayecto; si no, «Sube aquí / Baja aquí».
- **Trazado y referencias peatonales** (calles, cruces, giros, puentes con evidencia) por opción: hoy solo hay distancia y geometría de la caminata.
- **Número de paradas** y **tiempo de espera** reales (no hay horarios).
