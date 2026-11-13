# Flujo guiado de planificación · SEVB 4.15.0

> **El planificador con origen A y destino B (el de siempre) es el predeterminado y no cambia.** El flujo guiado es una **opción aparte**: se entra desde el menú ☰ → **«Planear paso a paso»** y se vuelve con **«Usar el planificador con A y B»** (menú o pie de cada paso). La elección se recuerda en este dispositivo.

Una persona que casi no usa el celular ve **una pregunta, una acción principal y una salida segura por pantalla**. No es un tutorial encima de la interfaz: es una máquina de estados (opcional) que controla el **planificador real** (mismos campos, misma búsqueda, mismo GPS, mismo mapa, mismo modo viaje). Los puntos elegidos siguen viviendo en `planner.js`; no hay un segundo origen/destino que pueda desincronizarse.

Archivos: `static/js/flujo-guiado.js`, `static/css/guiado.css`; ganchos pequeños en `planner.js` (`Planner.buscando()`, `Planner.cancelarBusqueda()`) y `sheet.js` (evento `spevb-panel-medio`).

## Pasos (máquina de estados)
`destino → confirmar_destino → origen → confirmar_origen → resumen → calculando → recomendacion → viaje`

| Paso | Pregunta | Acción principal | Otras |
|---|---|---|---|
| destino | «¿A dónde quieres ir?» | Buscar destino | Elegir en el mapa · Necesito ayuda |
| confirmar_destino | «¿Este es el lugar al que quieres ir?» | Sí, continuar | Cambiar destino |
| origen | «¿Desde dónde vas a salir?» | Usar mi ubicación actual | Escribir una dirección · Elegir en el mapa · Volver al destino |
| confirmar_origen | «¿Estás saliendo desde aquí?» | Sí, continuar | Cambiar lugar |
| resumen | «Revisa tu viaje» (Vas desde / Hasta) | Buscar cómo llegar | Cambiar origen · Cambiar destino |
| calculando | «Estamos buscando la mejor forma de llegar.» | — | Cancelar (conserva los lugares) |
| recomendacion | «Esta es nuestra recomendación» | Empezar este viaje | Ver otras opciones · Cambiar desde o hasta |
| viaje | (la tarjeta del modo viaje toma el relevo) | | Planear otro trayecto al llegar |

- `TRANSICIONES` define qué salto es válido; `Spevb.Guiado.ir()` ignora los inválidos. Retroceder **conserva** lo ya elegido (cambiar el destino no borra el origen y viceversa; con ambos puestos, «Sí, continuar» va directo al resumen).
- Tras recargar se **deduce** el paso del estado real (`Spevb.Guiado.derivar()`): viaje en curso → `viaje`; búsqueda en curso → `calculando`; opción elegida → `recomendacion`; ambos lugares → `resumen`; si no, `destino`. **No se guarda ninguna dirección ni coordenada**; un enlace compartido (`/?a=lat,lng&b=lat,lng`) entra directo a la recomendación.
- La **explicación de la recomendación** es la razón real que da el servidor (`.reco-motivo`); si no hay, se usa un texto según el resumen (dos buses / poca caminata / más directa).
- Los mensajes del planificador (GPS, errores, «sin resultados», «cancelada») se muestran en una región `aria-live` del paso, con «A» y «B» dichos como «origen» y «destino».

## Ubicación
El permiso del navegador **no se pide al abrir** ni antes del toque en «Usar mi ubicación actual». Se explica antes: «SEVB necesita tu ubicación… no se guarda en el servidor». GPS lento: se puede **Cancelar**. Permiso rechazado, GPS no disponible, mala precisión o fuera de la ciudad: el mensaje del planificador aparece en palabras sencillas y el paso **abre solo el campo para escribir** (además de «Elegir en el mapa» y «Volver al destino»): nunca hay un callejón sin salida.

## Cómo se cambia de modo
Por defecto se ve el planificador con A y B. El menú ☰ trae la entrada aparte **«Planear paso a paso»** (`#menuPasoAPaso`); dentro del flujo guiado esa misma entrada pasa a decir **«Usar el planificador con A y B»**, y el pie de cada paso tiene el mismo enlace. La preferencia se guarda en `localStorage` (`spevb-modo-planificador` = `guiado` | `avanzado`). Ambos modos usan el mismo estado del planificador.

## Accesibilidad
Objetivos táctiles de ≥ 48 px (la prueba exige ≥ 44), pregunta de 22–28 px, indicador **con palabras** («Destino · Origen · Confirmar») y `aria-current="step"`, etiquetas visibles en los campos, foco visible de 3 px, el foco llega a la nueva pregunta tras una acción de la persona (nunca al cargar), `aria-live` sin repetir mensajes, `prefers-reduced-motion`, modo oscuro y letra grande. El panel sube a media altura en cada paso para que la pregunta y el botón queden a la vista (320 × 568 incluido).

**Leer instrucciones en voz alta** (opcional): solo si el navegador tiene síntesis de voz, **nunca** empieza solo y el texto completo siempre está en pantalla. Nota: una regla previa del proyecto evitaba las instrucciones por voz; esta es una ayuda opt-in pedida expresamente.

## Pruebas
`python e2e/run_e2e.py` (incluye `e2e/guiado_e2e.py`). Las suites anteriores usan el planificador con A y B (el predeterminado); solo las de este flujo piden el modo guiado (`sevb_e2e.Sesion(guiado=True)`). **No** se ejecutan suites en paralelo sobre el mismo puerto (da `ERR_CONNECTION_REFUSED`).

## Limitaciones
- Probado con Chromium/Edge emulado y GPS simulado; falta probar en teléfono, en WebKit y con personas reales (`docs/PRUEBAS-USABILIDAD-GUIADA.md`).
- «Lugares recientes/favoritos» en el primer paso reutiliza el bloque «Tu viaje de siempre» del proyecto (solo aparece si ya existen datos reales).
- La bienvenida de primera visita y la práctica (`guia.js`) enseñan este flujo desde 4.15.1 (destino primero, 8 escenas y una práctica de 8 pasos sobre sus botones reales): ver `docs/TUTORIAL.md`. No es un segundo tutorial: es el mismo, alineado con el paso a paso.
