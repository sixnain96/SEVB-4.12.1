# Arranque del mapa: medición y experimentos (Fases A y B)

Regla seguida: **no se conserva una optimización sin una mejora repetible en un hito útil**. Aquí se midió con el **SDK de Google SIMULADO** (`e2e/harness/google_fake.js`, sin red). No se usó Google real (no hay una clave autorizada para pruebas) ni un teléfono físico: la descarga del SDK, las teselas y el dibujo de Google **no se midieron**.

## Cómo se mide
`e2e/rendimiento/medir_arranque_mapa.py --antes <copia del frontend> --n 5`: dos servidores simulados (antes/después), corridas **alternadas**, Chromium 157, 390×844 a 2×, CPU 4× más lenta, red normal y red lenta (150 ms, 1,6 Mb/s para lo que sirve el servidor simulado). *Primera apertura* = contexto nuevo sin caché ni service worker; *recarga* = segunda carga con service worker y caché. Hitos: inicio y fin de `/api/config/mapa`, `sevb-config-lista`, `sevb-adaptador-listo`, `sevb-sdk-listo`, `sevb-mapa-listo`, `spevb-planner-listo`, DCL y número de solicitudes, instancias de mapa y cargas del SDK.
Marcas de diagnóstico nuevas (no cambian ninguna señal existente): `sevb-config-inicio`, `sevb-config-respuesta` y `sevb-calles-visibles` (primer `tilesloaded` de la instancia; con el SDK simulado es instantáneo, solo es fiable con Google real).

## Línea base (misma copia contra sí misma, mediana, ms)
El ruido entre corridas **idénticas** es grande (20–40 %): `docs/pruebas/arranque_mapa_base_AA.json`. Solo cuenta una diferencia grande y consistente.
- Primera apertura, red normal: petición de configuración ≈ 410–980 ms (tras bajar y ejecutar los scripts), mapa ≈ 1,4 s, planificador ≈ 1,45 s.
- Primera apertura, red lenta: la petición de configuración **sale a los ≈ 4 s**; adaptador ≈ 7,4 s; mapa y planificador ≈ 7,5 s (el servidor simulado entrega ≈ 2,3 MB de JS **sin comprimir**).

## Experimento A1 · adelantar la petición de `/api/config/mapa` — RETIRADO
Un script mínimo al inicio de `<head>` pedía la configuración antes que el resto (una sola petición, misma promesa, mismo tiempo de espera; `docs/pruebas/arranque_mapa_config_temprana.json`).
| Escenario (mediana, ms) | inicio de la petición | config lista | mapa | planificador | DCL |
|---|---|---|---|---|---|
| Primera, normal: antes → después | 414 → **83** | 596 → 700 | 661 → 830 | 684 → 848 | 491 → 579 |
| Primera, lenta | 4074 → **1846** | 4319 → 4430 | 7444 → 7598 | 7466 → 7625 | 7233 → 7386 |
| Recarga, normal | 278 → 128 | 492 → 568 | 563 → 721 | 568 → 730 | 398 → 514 |
La petición sale mucho antes, pero **ningún hito útil se adelanta** (empeoran levemente) y el script en `<head>` bloquea el análisis del HTML. La espera no está en la petición de configuración sino en la cadena **descarga y ejecución del JS → adaptador**. Decisión: retirado. Se conservan las marcas.

## Fase B (experimentos de Google; **apagados por defecto**)
- **Map ID en el cargador (`map_ids`)**: el código no lo hacía. Se añadió como experimento: `localStorage['spevb-mapa-exp'] = 'map_ids'` agrega `map_ids=<el mismo Map ID>` a la URL del SDK. Con el stub solo se demuestra que la URL se construye bien (prueba `experimentos_de_carga_apagados_por_defecto_…`); **no se puede afirmar mejora sin Google real**, por eso no se activa por defecto.
- **`preconnect`**: experimento `'preconnect'`: tras conocer la configuración, y solo con proveedor Google, añade `<link rel=preconnect href=https://maps.googleapis.com>` una vez. Con Leaflet no se abre ninguna conexión (probado). Sin una traza real no se sabe si la espera de conexión es relevante.
- Para evaluarlos con una clave autorizada: cargar la página con y sin la bandera (`'map_ids,preconnect'`), 5–10 corridas alternadas, y comparar `sevb-calles-visibles` y `sevb-mapa-listo` en DevTools (Performance → Timings). Si no hay mejora repetible, borrar los experimentos.
- **Compresión**: `server.compression.enabled=true` (html, css, js, json, svg, ≥ 1 KB) en Spring y `encode zstd gzip` en el Caddy de `deploy/Caddyfile`. Verificado **por configuración**; no se pudo medir la transferencia real porque no había la base PostgreSQL para arrancar la aplicación. El servidor simulado no comprime, por eso la red lenta simulada exagera el costo del JS: es la principal causa de la espera medida y la mejora de mayor impacto probable es **entregar menos JS comprimido en la primera visita** (ya lo cubre la compresión real y el service worker en visitas posteriores).
- No se movieron módulos propios ni se cambió el service worker; no se intercepta ni se guarda nada de Google.

## Qué falta
Medir en Android/iPhone reales y con Google real: calles visibles (`tilesloaded`), mapa usable, efecto de `map_ids` y `preconnect`, y transferencia comprimida real.
