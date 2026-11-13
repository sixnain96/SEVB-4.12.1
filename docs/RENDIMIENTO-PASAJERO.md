# Rendimiento del flujo del pasajero (4.15.4): medición, optimización y lo que NO se pudo demostrar

Regla seguida: **no se declara «más rápido» sin datos comparables**. Las optimizaciones que no mostraron una mejora medible se revirtieron.

## Cómo se mide
- Herramienta: `e2e/rendimiento/medir_pasajero.py` (tiempos y fluidez) y `e2e/rendimiento/perfilar_pasajero.py` (perfil de CPU por función).
- Condiciones: Chromium headless 157, 390 × 844 a 2×, **CPU 4× más lenta**, servidor simulado local (`e2e/stub_server.py`, mapa Leaflet, sin compresión), GPS simulado. Red «rápida» (sin limitar) y «lenta» (150 ms de latencia, 1,6 Mb/s).
- Las mediciones de tiempo se hacen **sin instrumentación**; los contadores de oyentes, intervalos, temporizadores y MutationObservers se toman en otra corrida.
- Comparación A/B: `SEVB_STUB_STATIC` hace que el servidor simulado sirva otra copia del frontend. Se sirven «antes» y «después» desde **copias equivalentes** y las corridas se **alternan** (3 rondas × 4 repeticiones). Un primer A/B sirvió una versión desde otra carpeta y mostró mejoras de carga de ≈ 50 % que eran un artefacto de cómo se servían los archivos (la misma versión medida aparte daba otra cifra); se descartó (`docs/pruebas/ab_confundido/`).
- Entre corridas idénticas el ruido de esta máquina es grande (p. ej. tareas largas del marcador: 469, 914 y 1045 ms con el mismo código). Por eso solo cuenta lo que mejora **en las 3 rondas**.

## Línea base (estado al empezar; `docs/pruebas/rendimiento_4.15.4_antes.json`, CPU 4×, red rápida, n = 5, medianas)
| Métrica | Valor |
| --- | --- |
| Interfaz interactiva (`spevb-planner-listo`), arranque en frío | 617 ms |
| FCP / LCP en frío | 256 / 256 ms |
| Tareas largas durante la carga | 4 (341 ms; la peor 143 ms) |
| Última tecla → lista de sugerencias | 243 ms (220 ms son el retardo deliberado) |
| «Buscar rutas» → recomendación visible | 196 ms |
| «Iniciar viaje» → tarjeta y marcador | 344 ms |
| Oyentes / intervalos / temporizadores / MutationObservers (inactivo) | 340 / 1 / 1 / 9 |
| Tras terminar un viaje y tras 5 viajes seguidos | 437 / 1 / 1–2 / 9 (no crece; sin GPS, capas ni temporizadores sueltos) |
| Heap de JS tras viajes seguidos | +93 KB en el 2.º viaje y cada vez menos (≈ 20 KB hacia el 15.º): sin fuga lineal evidente |
| Red lenta (150 ms, 1,6 Mb/s), n = 3 | interfaz lista 7,4 s, FCP 2,3 s, carga 13 s: dominada por los 2,3 MB de JavaScript **sin comprimir** del servidor simulado |

## Cuellos de botella (perfil de CPU, tiempo propio de código de la aplicación)
- **Arrastre del panel:** `viewH` (221 ms) + `apply` (170 ms) + `fijarScroll` (120 ms) en `sheet.js`: `viewH()` leía `visualViewport` en cada `pointermove` y cada lectura obliga al navegador a recalcular estilo pendiente.
- Carga: `ordenarMenu` (51 ms), el resto es el motor del mapa. Iniciar: `prepararAudio` (48 ms). GPS a 10 Hz: `Motion.reduced` (40 ms) y el dibujo del mapa.

## Optimización conservada (demostrada)
| Cambio | Evidencia (A/B, 3 rondas, medianas) |
| --- | --- |
| `sheet.js`: `viewH()` en caché invalidada por `resize`, `orientationchange`, `visualViewport` (resize/scroll), `pageshow`, `visibilitychange` y el cambio de diseño; `apply()` no vuelve a leer el layout ni a escribir variables CSS si nada determinante cambió | **Arrastrar el panel: tareas largas 590 → 310 ms (−48 %), mejor en las 3 rondas**; el perfil muestra `viewH` desaparecer de la lista. El coste del recálculo que queda se paga una sola vez al soltar el panel (en `apply`). |

## Optimizaciones probadas y revertidas (sin mejora medible)
| Cambio | Resultado del A/B |
| --- | --- |
| `Motion.reduced` con `matchMedia` en caché | sin diferencia medible en la fluidez del marcador (ruido) |
| `ordenarMenu` sin mover nodos que ya están en su sitio | carga: FCP +6 %, interfaz lista −12 % en 2/3 rondas (dentro del ruido) |
| Crear el `AudioContext` tras pintar la tarjeta | «iniciar → tarjeta y marcador» −9 % en 2/3 rondas; el perfil solo movió el coste |
Se revirtieron para no dejar código con riesgo y sin beneficio demostrado.

## Lo que se encontró y NO se resolvió (con datos)
- **Carga con red lenta:** 2,3 MB de JS sin comprimir en el servidor simulado. El servidor real ya comprime (`server.compression.enabled=true`) y el service worker sirve la app guardada, así que **esa cifra no es la de producción**; además, en producción con `MAP_PROVIDER=google` no se carga MapLibre (1,4 MB del total): las cifras de carga del servidor simulado (Leaflet) no representan el sitio real. Medir contra el servidor real con Google queda pendiente.
- Inicializar de forma perezosa tutorial/compartir/herramientas: el tutorial (`guia.js`) pesa ≈ 62 KB de ≈ 800 KB propios; se descartó por riesgo para el modo sin conexión frente a un beneficio pequeño no demostrado.
- «Cuadros por segundo»: en Chromium headless `requestAnimationFrame` no está sincronizado con la pantalla (≈ 180 fps), por eso se informan tareas largas y cuadros lentos (> 50 ms), no FPS.
- No se midió en un teléfono real ni en un dispositivo modesto; no se midió con Google real.

## Animaciones
No se cambiaron duraciones ni curvas. Se verificaron (y ya tenían pruebas) la transición círculo ↔ bus de ≈ 220 ms con solo `transform` y `opacity`, su desactivación con `prefers-reduced-motion`, que las alertas críticas son persistentes y que `will-change` solo se usa durante el movimiento del panel.
