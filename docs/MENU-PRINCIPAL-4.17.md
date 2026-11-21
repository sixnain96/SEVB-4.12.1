# Menú principal simplificado (4.17)

Pedido: el profesor dijo que el menú principal tenía demasiada información. Se simplifica **contenido y jerarquía**; la identidad no cambia (verde `#176650`, mascota, tarjetas redondeadas, tipografía, iconos propios).
Capturas antes/después: `docs/capturas-menu/` (`antes-*.png`, `despues-*.png`, 375 × 812).
Sin commit ni publicación: todo está en el árbol de trabajo.

## 1. Inventario de lo que había

**Menú ☰ (13 bloques, ≈ 1 400 px a 375 px de ancho):** cabecera con «SEVB · Villavicencio» · «Volver al inicio» · tarjeta «Mi cuenta» con título y párrafo de 3 líneas · Mis lugares (Casa, Trabajo, Agregar, aviso largo, «Administrar») · **Mis viajes** · **Mis viajes y logros** (dos secciones con casi el mismo nombre) · Ayuda · Instalar en tu celular · Pantalla y accesibilidad · Guía de colores (suelta) · Mala señal o sin internet (con título repetido y dos textos) · Rutas cerca del origen (botón suelto, a menudo desactivado) · Explorar recorridos · enlaces de administración · mascota grande.

**Panel de abajo, planificando:** asa · marca · «?» · ocultar · ☰ · campo A con 3 herramientas (Buscar, En el mapa, Mi ubicación — «ubicació-n» partido en dos líneas) · intercambiar · campo B con 2 herramientas · Buscar rutas · Limpiar A y B · franja azul «Marca A y B en el mapa o escribe una dirección».

**Panel de abajo, con resultado:** tarjeta «Mejor opción» · «También puedes tomar» · Iniciar viaje · Editar A y B · Ver otras opciones · **párrafo de 4–5 líneas** («Recomendada: … Sigue los pasos de abajo… Toca otra tarjeta… Hay un paradero a 44 m…») · **6 botones** (Compartir, Google Maps, WhatsApp, Avisarme al bajar, Guardar viaje, Reportar) · itinerario · lista de opciones.

## 2. Diseño nuevo

**Menú ☰ — cuatro cosas a la vista y un solo «Más»** (≈ 910 px, −35 %):

| A la vista | Qué es |
|---|---|
| **Planear un viaje** | Botón principal verde con «Elige de dónde sales y a dónde vas» (es el antiguo «Volver al inicio»; mismo `#menuInicio`, misma confirmación si hay viaje). |
| **Cuenta** | Una frase corta + «Continuar con Google» (o foto, nombre y ajustes si ya entró). |
| **Mis lugares** | Casa, Trabajo y «Agregar lugar» a un toque (abierta). |
| **Recientes** | Viajes recientes; se abre sola si los hay. «Historial y guardados» queda dentro. |
| **Más** | Logros y racha · Ayuda · Pantalla y accesibilidad (con la Guía de colores dentro) · Instalar · Mala señal o sin internet · Explorar recorridos (con «Rutas cerca del origen» dentro) · enlaces de administración. Plegado siempre al abrir el menú. |

Durante el viaje: «Volver a mi viaje» primero, y «Más» (letra grande, mapa sin internet, ayuda) sube arriba de Mis lugares.

**Arriba del panel:** título «¿A dónde vamos?» + «Dinos de dónde sales y a dónde vas.» (y desaparece la franja azul que repetía la instrucción). «Buscar» pasa a icono (con su nombre accesible), así «Mi ubicación» ya no se parte.

**Abajo, con resultado:** el aviso largo queda en 2 líneas (tocarlo lo abre entero; el texto completo sigue en el DOM para lectores de pantalla) y las acciones pasan de 6 a **3 + «Más»**: Compartir, Guardar viaje, Avisarme al bajar · «Más» → Google Maps, WhatsApp, Reportar.

## 3. Qué se quitó, agrupó y añadió

- **Quitado:** título «Mis viajes» duplicado, «Mi cuenta» (rótulo) y párrafo largo, rótulos repetidos dentro de Pantalla/Mala señal/Explorar, la nota «¿Quieres SEVB como app?», la franja azul inicial, el recuadro del resultado de 5 líneas, mascota grande al pie (ahora 56 px).
- **Agrupado en «Más» (menú):** 7 secciones. **Agrupado en «Más» (resultado):** 3 botones.
- **Añadido:** botón «Planear un viaje», título del panel, `js/menu-simple.js`, `css/menu-simple.css`.
- **No se tocó:** ids, lógica de rutas/viaje/cuenta/lugares, el planificador A/B, «Planear paso a paso», el coordinador de superficies, el tutorial, el acceso solo con Google.

## 4. Archivos

`index.html` (estructura del menú, título, barra de acciones) · `js/menu-simple.js` (nuevo) · `js/superficies.js` (orden por fase: `menuLugares`, `menuEspacio`, `menuMas`) · `css/menu-simple.css` (nuevo, al final del paquete; `node scripts/build-css.mjs`) · `css/app.sources.txt` · `sw.js` (precarga el script nuevo; caché `-mapa11`).

## 5. Accesibilidad

Todo sigue siendo `<details>`/`<button>` nativos con foco visible; objetivos ≥ 44 px; el aviso largo es un control con `tabindex`, `aria-expanded` y Enter/Espacio; «Buscar» conserva `aria-label`/`title`; movimiento reducido apaga la flecha animada de «Más».

## 6. Verificación (stub + Edge/Chromium emulado, no teléfonos físicos)

- **Nuevas:** `e2e/menu417_e2e.py` 6/6. `mvn test` de las pruebas Java que leen `index.html`/CSS/`sw.js` (CssBundleTest, PwaResourcesTest, MejorOpcionTest, MotionCssTest, AnimacionesAbTest, RutasPublicasTest, MapaContextualTest): verde.
- **Adaptadas** (abren «Más» antes de usar lo que contiene, o ya no esperan que el menú se desplace plegado): `menu416`, `ux414`, `aprender`, `accesibilidad`, `instalar`, `logros`, `mejoras414`, `puntos`, `sevb`, `pasajero414` (orden por fase). En `aprender_e2e`, durante la práctica la tarjeta del coach puede quedar sobre el ☰: sigue bloqueando el toque.
- **Verdes tras los cambios:** menu416 · menu417 · ux414 (36/36) · lugares · logros · mejoras414 · puntos · sevb · aprender · accesibilidad · instalar · estados · cuenta_google · guiado · busqueda · layout_panel · panel_gestos · desvio_bus · llegada · indicaciones · compartir · continuidad414.
- **Fallos que ya existían (se corrió el mismo conjunto sobre `HEAD` y salen igual, con las mismas cifras):** `resultados_e2e` (4: «Iniciar viaje» a 320 × 568 queda fuera de pantalla tras buscar, aviso de elegir punto, flujo de movimiento), `viaje_e2e` (1, 384 × 848), `movil_e2e` (1, 320 × 568) y `pasajero414` (3, «Editar A y B» a 320 × 568). Vienen de la tarjeta «Mejor opción» (Fase R) y no se tocaron aquí.
- Error real que las pruebas atraparon y se corrigió: una regla de `display` sobre `#accountGuest` ignoraba el atributo `hidden` (se veía «Continuar con Google» con sesión iniciada).

## 7. Sin verificar
Teléfono físico (teclado virtual, áreas seguras), modo oscuro del menú nuevo (el menú ya era claro fijo), lectores de pantalla reales (solo etiquetas, roles y foco por prueba), `mvn verify` completo y `run_e2e.py` con PostGIS.

## 8. Segunda tanda (Fase T)
Logros salen de «Más» y vuelven al menú como sección propia; racha animada; reglas «las mejores opciones», racha gradual y racha estática de la cuenta demo; compartir con pasos; borrar rutas en el editor; animaciones de A/B, «Toma el bus», indicaciones y «Por qué la recomendamos»; botón del bus separado de «Ver rutas». Detalle en `CHANGELOG.md` (Fase T). La atribución de Google se queda: es obligatoria.
