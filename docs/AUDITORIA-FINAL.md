# Auditoría integral y entrega (cierre de las fases A–F)

Esta auditoría comprueba que las piezas trabajan **juntas** y deja la evidencia verificable. Las pruebas de navegador usan el frontend real con **Google, GPS, red, vibración y notificaciones simulados** (servidor `e2e/stub_server.py`); no equivalen a una cuenta de Google real ni a un teléfono físico.

## Defecto encontrado y corregido

| Hallazgo | Causa | Corrección | Prueba |
| --- | --- | --- | --- |
| La **ayuda** («?» / «Necesito ayuda») del flujo guiado hablaba de «¿De dónde sales?» y «Buscar rutas», botones que ese flujo no tiene; la ayuda del viaje no mencionaba el marcador bus, «Tu bajada está aquí», «Editar A y B» ni el viaje único | `guia.js` solo conocía el planificador avanzado | `AYUDAS_GUIADO` por paso (botones reales: «Buscar destino», «Usar mi ubicación actual», «Buscar cómo llegar», «Empezar este viaje»…) y consejos al día en las ayudas de ruta y de viaje | `guiado_e2e.py::la_ayuda_del_flujo_guiado_habla_de_los_botones_reales…` |

Limitación que se mantiene: las **escenas** de la bienvenida y las lecciones animadas del tutorial (`guia.js`) enseñan el planificador avanzado; no se rehicieron (sería una idea grande, fuera del alcance de este cierre).

## Matriz funcional → evidencia

| # | Punto | Dónde se comprueba |
| --- | --- | --- |
| 1 | Flujo guiado destino → origen → confirmación → recomendación | `guiado_e2e.py` (27 casos), `integracion_e2e.py` |
| 2 | Planificador avanzado | `sevb_e2e.py`, `resultados_e2e.py`, `busqueda_e2e.py`, `puntos_e2e.py` |
| 3 | Un solo viaje (doble toque, recarga, dos pestañas) | `ciclo_viaje_e2e.py` (14 casos), `integracion_e2e.py` |
| 4 | Círculo caminando, bus en `en_bus`, círculo al bajarse (también transbordo) | `marcador_alertas_e2e.py` |
| 5 | Alertas `cerca`, `preparate`, `ahora` una sola vez | `marcador_alertas_e2e.py`, `integracion_e2e.py` |
| 6 | Vibración opcional / sin `navigator.vibrate` | `marcador_alertas_e2e.py` |
| 7 | Notificaciones solo con permiso pedido por un toque | `marcador_alertas_e2e.py` |
| 8 | Ruta consumible y transbordos | `ruta_consumible_e2e.py`, `viaje_e2e.py` |
| 9 | Compartir: crear, actualizar, revocar, caducar | `compartir_e2e.py` (14 casos) y `ViajeCompartido*Test` (Java) |
| 10 | Salud del mapa solo dentro de un viaje | `salud_mapa_e2e.py`, `continuidad414_e2e.py`, `integracion_e2e.py` |
| 11 | Google como única búsqueda del pasajero | `busqueda_e2e.py` (30), `LugarServiceSoloGoogleTest`, `GoogleDireccionesServiceTest` |
| 12 | GPS y mapa como alternativas explícitas | `busqueda_e2e.py::si_la_busqueda_falla_siguen_a_mano…`, `integracion_e2e.py` |
| 13 | Tutorial alineado con el flujo real | `aprender_e2e.py` (30), `guiado_e2e.py` (ayuda por paso) — ver limitación arriba |
| 14 | Pantallas pequeñas y teclado virtual | `ux414_e2e.py`, `movil_e2e.py`, `layout_panel_e2e.py`, `aprender_e2e.py` (320 × 568) |
| 15 | Movimiento reducido | `marcador_alertas_e2e.py`, `pasajero414_e2e.py`, `integracion_e2e.py` (segunda variante) |
| 16 | Reanudación y cierre completo | `ciclo_viaje_e2e.py`, `continuidad414_e2e.py`, `integracion_e2e.py` |

## Resultados de esta auditoría

Ver la sección «Resultados» del informe de entrega (se rellena con las corridas finales): `mvn clean verify`, comprobación de sintaxis de los 240 archivos JavaScript y las 32 suites de navegador ejecutadas **de forma secuencial** con `python e2e/run_e2e.py`.

## Qué NO está verificado

- Google real (clave, cuota, facturación) y una cuenta de Google real con foto.
- Un teléfono físico (Android/iPhone), Safari y WebKit; vibración y notificaciones reales (iPhone y algunos navegadores no tienen `navigator.vibrate`).
- Wake Lock y GPS con la pantalla realmente bloqueada.
- El **rendimiento** (fase E) está medido con datos comparables en `docs/RENDIMIENTO-PASAJERO.md`; solo una optimización quedó demostrada y las cifras de carga del servidor simulado no representan el sitio real (Google, compresión).
- La causa del defecto de «calles que desaparecen» en Google Maps sigue sin confirmarse (solo hay detección y «Recuperar mapa»).
- Nada se desplegó: el servidor de AWS sigue en el commit anterior.
