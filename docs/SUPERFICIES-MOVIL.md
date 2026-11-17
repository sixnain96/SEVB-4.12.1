# Reparto de espacio entre superficies en celular (Fase L)

Regla: el panel A y B, el menú ☰ y los demás paneles **conservan su diseño**; solo se ajustó geometría y la coordinación de quién cede. Nada de búsqueda, cuentas, datos, API, permisos, cálculo de rutas, lógica del viaje, compartir, desvíos o alertas.

## Cómo se buscaron los choques
`e2e/rendimiento/sonda_superficies.py` (Chromium emulado, no un teléfono): para 320×568, 360×640, 390×844, 430×932 y 740×360 (horizontal), en normal y letra enorme (los tres primeros más el horizontal), recorre planificando (con y sin teclado emulado reduciendo la altura), menú (arriba y al final del scroll), viaje, viaje + menú, viaje + pregunta urgente y viaje + «Editar A y B» (con y sin teclado). Mide con `getBoundingClientRect` y `elementFromPoint` si **el toque llega al control**, si un control esencial queda fuera de pantalla y cuánto del alto cubren tarjeta y panel. Resultados: `docs/pruebas/sonda_superficies_antes.json` / `_despues.json`; capturas `antes-*.png` y `despues-*.png` en `docs/capturas-viaje/`.

## Lo que NO es un choque (diseño actual)
- Con el menú o un diálogo abiertos, lo de abajo queda inerte y oscurecido.
- Los botones flotantes del mapa (mi ubicación, ver ruta, centrar) quedan tapados por la tarjeta del viaje: la tarjeta recibe el toque y no se ven.
- Con «Buscar rutas» fuera de pantalla en 320×568 el panel está asomado (estado «peek») a propósito.
- La pregunta urgente del viaje cubre la cabecera del menú (incluido «×» y «Volver a mi viaje»): es la excepción de prioridad que ya existía; sus botones reciben el toque y, al responder, el menú vuelve a ser alcanzable. Escape también descarta la alerta.

## Choque reproducido y corregido
**Celular girado (≈ 740×360) con un viaje activo y «Editar A y B».**
1. *Antes:* el planificador lateral (380 px) y la tarjeta del viaje (480 px centrada) se superponían: la tarjeta quedaba con ≈ 209 px de alto, su texto debajo de los botones fijos y, con «Editar A y B», la tarjeta tapaba campos del planificador (`#pickDestination`, `#swapTrip`, `#tripDestination` recibían el toque de la tarjeta; cobertura 126–133 % del alto).
2. *Causa:* `superficies.js` solo trataba como «compacta» la pantalla estrecha; el celular girado de poca altura no cedía.
3. *Corrección:* en `superficies.js` el celular girado de poca altura (`max-height: 480px` y horizontal) cuenta como compacto **solo para decidir quién cede durante un viaje** (el planificador se oculta al empezar, como en vertical, y «Editar A y B» lo trae). En `viaje.css`, con el planificador traído en ese tamaño, la tarjeta compacta se coloca a la derecha del planificador (`left: calc(min(380px, 50vw) + 24px)`). El diseño del planificador y de la tarjeta no cambió.
4. *Después:* viaje activo y «Editar A y B» sin solapes; todos los controles reciben su toque (`despues-viaje-editar-ab-740x360.png`).

## Pruebas nuevas (`e2e/menu416_e2e.py`)
- `celular_girado_con_viaje_…`: horizontal, el planificador cede, «Editar A y B» sin solape (rectángulos) y con toques que llegan, el viaje no se reinicia.
- `con_el_menu_abierto_la_pregunta_urgente_…`: 320×568 y 430×932, botones de la alerta con toque llegando y ≥ 44 px, la respuesta sigue su curso y luego se puede cerrar el menú.
- `varios_ciclos_…`: 4 ciclos de abrir, cerrar, girar y volver al viaje: el mapa es el mismo objeto, sin consultas nuevas de rutas/viajes, el DOM no crece y los iconos no se duplican.
- Ya existían y se mantienen: menú en 320/360/390/escritorio, cabecera fija con letra enorme, cierre con Escape y foco, alerta con teclado (`desvio_bus_e2e`).

## Sin cambios (y por qué)
Arranque del mapa (`map_ids` y `preconnect` siguen apagados; ver `RENDIMIENTO-ARRANQUE-MAPA.md`), viewport de `sheet.js`, `--kb`, `--sheet-visible` y z-index: no se tocaron porque la sonda no reprodujo choques ligados a ellos. No se midió velocidad: no se afirma ninguna mejora de velocidad.

## Pendiente
Teclado virtual real, barras del navegador y áreas seguras en un Android/iPhone físico (aquí el teclado se emuló reduciendo la altura de la ventana).
