# Menú ☰, recuperación tras «Ya me bajé», Mis lugares y práctica del tutorial (Fase J)

Estado: implementado y probado con el stub; sin publicar. **Sin cambios de backend, de contratos de API, de reglas de negocio ni de algoritmos.** Solo interfaz, textos y jerarquía.

## A · Menú lateral (#sideMenu)

- **Cabecera fija** (título, «Viaje en curso» y botón de cerrar): el propio menú es la única zona de desplazamiento; en 320×568 y en horizontal el botón de cerrar siempre queda a la vista. El contenido respeta las áreas seguras (`env(safe-area-inset-*)`).
- **Secciones con icono y color de apoyo** (siempre con texto): Mis lugares, Mis viajes, Mis viajes y logros, Ayuda, Instalar en tu celular, Pantalla y accesibilidad, Mala señal o sin internet y Explorar recorridos. El chevron indica abierta/cerrada y la sección abierta lleva una barra de color a la izquierda. Los iconos los inyecta `superficies.js` (`decorarMenu`) con el `Spevb.Iconos` existente; no hay iconos nuevos.
- **Cuenta compacta:** sin sesión, una frase corta y «Continuar con Google»; con sesión, avatar + nombre + los botones de siempre.
- **Planificando / en viaje:** el orden y las secciones abiertas siguen siendo los de `superficies.js` (se aplican al cerrar el menú, nunca con el menú abierto). Con un viaje activo aparece «Viaje en curso», «Volver a mi viaje» va primero (grande), «Volver al inicio» queda separado (borde discontinuo) con la nota «Te pedirá confirmar: termina tu viaje en curso.» Las confirmaciones, el aviso de bajada (que sigue operable encima del menú) y el regreso a la pantalla de antes son los actuales.
- **Movimiento:** al tocar el título de una sección corre una transición de ≈ 0,2 s (clase `anima` que solo pone el toque de la persona y se quita sola); no hay animación al abrir el menú, al cambiar de fase ni cuando llega el GPS. `prefers-reduced-motion` y el ajuste de movimiento la desactivan. Modo oscuro, letra grande, foco visible, Tab, Escape y devolución del foco siguen en `modales.js`.

## B · Recuperación tras «Ya me bajé» (`viaje.js`)

La tarjeta `#viajeCaminata` ahora tiene un título (`#viajeCaminataTitulo`) y una línea de apoyo (`#viajeCaminataTexto`). Las decisiones (GPS vigente, umbrales, transbordo, recálculo, confirmación) son las de antes.

| Estado | Título | Apoyo / acción |
|---|---|---|
| `sin-ubicacion` | Esperando tu ubicación actual | Tu destino se conserva. Cuando tengamos una ubicación reciente, podemos calcular desde donde te bajaste. · Reintentar |
| `calculando` | Buscando cómo seguir | Desde donde te bajaste hasta tu destino (o «hasta donde tomas el siguiente bus»). |
| `lista` (destino) | Sigue a pie | Camina unos X hasta tu destino (+ « · N min» solo si el cálculo devolvió minutos) |
| `lista` (transbordo) | Camina hasta el siguiente bus | Camina unos X hasta el paradero (si tiene nombre) · «Ahí tomas la ruta R» |
| `larga` | El destino queda lejos a pie | Distancia y «Recalcular desde aquí» (no dice que ya hay un bus) |
| `no-alcanzable` | El siguiente bus queda lejos a pie | Busca otra forma de llegar al destino original |
| `error` | Tu destino se mantiene | Motivo (sin internet / lenta / sin camino) · Reintentar y Recalcular |
| propuesta lista | (pregunta existente) «Encontré otra forma de llegar: ruta X…» | «Sí, cambiar» / «No, seguir con el actual» |

- **Destino:** se usa el del viaje activo (`sesion.plan`). El plan solo guarda coordenadas, no el nombre, así que se dice «tu destino» (no se añadió ningún dato nuevo ni consulta para nombrarlo). El origen del cálculo es «desde donde te bajaste».
- **Anuncios y foco:** el texto solo se reescribe cuando cambia (firma estado+título+apoyo): una lectura GPS más no vuelve a anunciar ni mueve el foco.

## C · Casa, Trabajo y Mis lugares (`lugares.js`)

- «Ir a casa» / «Ir al trabajo» (antes «Ir a Casa»), «Guardar mi casa/trabajo» si falta (con invitado: el acceso con Google de siempre). Un lugar propio conserva su nombre y lleva la etiqueta «Ir». `usar(f)` es el mismo.
- El botón «⋯» es aparte del toque principal (48 px) y su nombre accesible incluye el lugar («Más acciones de Casa»). Sus acciones (Cambiar ubicación, Cambiar nombre donde se permite, Eliminar) mantienen confirmaciones y permisos.
- «Cambiar ubicación»: el pin anterior queda bajo la punta del marcador; instrucción «Mueve el mapa para ajustar el punto.»; «Guardar este punto» y «Cancelar» visibles. Cancelar conserva el punto y **devuelve el foco a la fila correcta** (antes, al editar Trabajo, el foco podía caer en Casa). Abrir, mover o cancelar no cambia A ni B.
- La vista compacta solo muestra nombres (no direcciones completas).

## D · Práctica «No encontramos esa dirección» (`guia.js`)

Una pantalla de **ejemplo aislada** (sello amarillo «Práctica»): dirección de ejemplo → «No encontramos esa dirección» → «Elegir en el mapa» (mismo nombre y aspecto `guiado-boton` que el real, con el resaltado `ayuda-resalta`) → mapa de práctica «Marca el punto» → «Confírmalo» (Sí, continuar) → «Así puedes elegir el destino cuando no aparece en la lista» con «Repetir la práctica» y «Entendido». Atrás y Omitir en todo momento; Escape cierra.
Se abre desde la lección «Cómo elegir el destino» y desde la ayuda del paso de destino del flujo guiado. **No usa el buscador, Google, el selector real, A/B, la cuenta, el historial ni un viaje** (la prueba comprueba que no hay ninguna petición de red y que A/B y el estado quedan idénticos). Se apila sobre la ventana que la abrió y devuelve el foco a esa ventana.

## Pruebas

`e2e/menu416_e2e.py` (6, nuevo): menú planificando (iconos, cabecera fija en 320×568 y horizontal, oscuro, Escape y foco, animación solo al tocar), menú en viaje (orden, separación, estado, Escape y «Volver a mi viaje» sin cambiar el viaje), Casa/Trabajo/lugar propio en un toque + editar/cancelar sin tocar A/B, práctica completa (ratón, teclado, Atrás, Omitir, repetir, movimiento reducido, sin red) y la ayuda del destino. Ajustadas: `desvio_bus_e2e` (textos de la tarjeta), `continuidad414_e2e` («otra forma de llegar»), `lugares_e2e` y `mejoras414_e2e` («Ir a casa»).
Capturas: `menu-planificando-320.png`, `menu-planificando-oscuro-320.png`, `menu-viaje-320.png`, `caminata-desde-la-bajada-real.png`, `practica-elegir-en-el-mapa-320.png`, `lugares-editar-ubicacion.png`.

## Pendiente / no verificado

- No se probó en un celular real ni con lectores de pantalla reales (solo Chromium con emulación).
- El nombre del destino no se muestra en la tarjeta de recuperación porque el plan del viaje no lo guarda; guardarlo es un cambio de datos que no se hizo.
