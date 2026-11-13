# Tutorial de SEVB (bienvenida, ayudas rápidas y práctica)

**Estado (4.15.1):** el tutorial completo enseña el **flujo guiado real** («Planear paso a paso»), con el destino primero. El planificador con origen A y destino B sigue siendo el predeterminado de la aplicación y solo se explica al final, como una ayuda rápida opcional. Código: `src/main/resources/static/js/guia.js` y `css/guia.css`; ventanas en `index.html` (`#bienvenida`, `#ayudaModal`).

## Qué enseña (una acción principal por escena)
| # | Escena de la bienvenida | Idea que enseña |
| --- | --- | --- |
| 1 | Primero, dime a dónde vas | «¿A dónde quieres ir?», escribir, tocar la sugerencia de Google correcta y «Sí, continuar» |
| 2 | Ahora, dónde estás | «Usar mi ubicación actual»; «Escribir una dirección» o «Elegir en el mapa» como alternativas |
| 3 | Revisa y busca | «Vas desde / Hasta» en lenguaje natural y «Buscar cómo llegar» |
| 4 | Esta es la recomendación | minutos, caminata, bus y transbordo («2 buses») |
| 5 | Empieza un solo viaje | «Empezar este viaje»; solo un viaje a la vez (hay que terminar el actual) |
| 6 | Sigue tu marcador | círculo azul caminando → bus con el código de la ruta → círculo azul al bajar |
| 7 | Te aviso antes de bajar | niveles Cerca / Prepárate / Ahora, tarjeta «Tu bajada está aquí»; la vibración y la notificación son opcionales y dependen del teléfono (no se promete en todos los equipos) |
| 8 | Termina tu viaje | «Ya me bajé», último tramo a pie y «Terminar viaje»; después, práctica o explorar |

Las **ayudas rápidas** (menú «?» → «Más ayudas rápidas») son 11 temas: nueve reutilizan una escena y dos son consejos en texto («Si no aparece una ruta» y «El planificador con A y B (opcional)», que lo presenta como opción para quien ya conoce SEVB).

## La práctica (8 pasos sobre los botones reales)
1. **Destino primero** (1 de 2 escribir/elegir, 2 de 2 confirmar): señala `#tripDestination` y luego `#gSiDestino`.
2. **Dónde estás** (5 subpasos): señala `#gUsarGps` (no se puede tocar: la práctica no usa el GPS), `#gEscribirOrigen` y `#gMapaOrigen` (una alternativa por pantalla), pone un lugar de ejemplo y señala `#gSiOrigen`.
3. **Revisa y busca**: señala el resumen real y `#gBuscar` (la persona lo toca; la búsqueda es la real).
4. **Recomendación**: una cosa por vez sobre la tarjeta real (razón, tiempo, caminata, buses/transbordo, ruta, otras opciones).
5. **Un solo viaje**: señala `#gEmpezar` con escudo (no se puede tocar: no se inicia ningún viaje).
6–8. **Marcador, avisos de bajada y terminar**: explicación con miniaturas (no hay viaje real).

Garantías: la práctica **pasa temporalmente al paso a paso** con el mismo botón del menú («Planear paso a paso») y **devuelve** el modo, los puntos y los resultados que la persona tenía; no pide GPS, no inicia viajes, no escribe en la cuenta ni en el historial; «Atrás» no borra lo elegido; «Salir» (o Escape) no da logro. Si el servicio de rutas falla, sigue con un ejemplo ilustrado marcado como simulación.

## Accesibilidad y movimiento
- Botones de al menos 44 × 44 px; «Atrás», «Siguiente» y «Omitir» en la bienvenida; «Atrás», «Siguiente» y «Salir» en la práctica; se reabre desde el menú (Ayuda) y desde «?».
- Región `aria-live="polite"` con «Paso k de 8» y otra con el título y la explicación; ilustraciones decorativas (`aria-hidden`); la ventana es un diálogo con foco atrapado y Escape.
- El resaltado de la práctica nunca cubre el control señalado: la tarjeta se coloca del lado donde cabe, siguiendo el área visible (teclado virtual, barras) y se vuelve a medir al girar o redimensionar. Con el teclado abierto sobre el campo señalado (poca altura), la tarjeta pasa a una versión mínima (una línea de texto y los botones) para que el campo y las sugerencias queden libres; los botones de la tarjeta siempre quedan a la vista.
- Con `prefers-reduced-motion` (o el ajuste de la aplicación) no hay animaciones: cada escena se ve terminada. Solo se anima la escena visible; al cerrar se pausan las animaciones y se liberan temporizadores y observadores.

## Pruebas
`python e2e/aprender_e2e.py` (ver `docs/PRUEBAS.md`). Cubre, entre otras, los 10 puntos del cierre del tutorial: tamaños 320 × 568, 360 × 640, 390 × 844 y horizontal bajo (800 × 360), avanzar/retroceder/omitir/reabrir, orden destino → origen, ausencia de A/B como flujo principal, práctica sobre controles reales sin datos reales, movimiento reducido + teclado, lector de pantalla (roles, regiones en vivo, nombres), limpieza al cerrar en cualquier escena, ayudas que coinciden con los botones verdaderos, teclado virtual y cambios de altura/orientación.
Capturas representativas (320 × 568 incluida): `docs/capturas-tutorial/` (se regeneran con `python e2e/capturas_tutorial.py`).

**Límites honestos:** las pruebas usan un navegador de escritorio con emulación móvil, un backend simulado y Google simulado; **no** se probó en un teléfono real ni con un lector de pantalla real (TalkBack/VoiceOver): lo del lector de pantalla se comprueba por atributos y roles, no por la voz. **NO VERIFICADO EN ENTORNO REAL:** teclado virtual real de Android/iOS (se emula reduciendo la altura de la ventana).
