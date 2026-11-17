# «Mis lugares» y menú ☰ (Fase C)

Estado: implementado y probado con Google **simulado**. Sin publicar. Frontend: `js/lugares.js` (reemplaza a `atajos.js`), `cuenta.js`, `planner.js` (dos ganchos), `superficies.js`,
`index.html`, `home.css`; backend: `DatosUsuario` (validador), `CuentaService.guardarDatos`, `CuentaController`.

## Menú ☰

Orden en planificación: cabecera compacta (título + cerrar) → «Volver al inicio» / «Planear paso a paso» → **perfil compacto** (foto, nombre y dos acciones en una fila) o **«Continuar con
Google»** (invitado) → **Mis lugares** (abierto: Casa, Trabajo, «Agregar lugar», lugares con nombre y «Administrar mis lugares») → **Mis viajes** (plegado) → **Mis viajes y logros**
(con la racha visible en el resumen) → Ayuda → enlaces → vista/ajustes/herramientas. Durante un viaje: «Volver a mi viaje» arriba, y Vista/Sin conexión/Ayuda primero; «Mis lugares» y
«Mis viajes» quedan plegados (siguen a un toque). El menú sigue siendo un diálogo con foco atrapado, Escape y devolución del foco; con una alerta de bajada abierta sigue pudiendo responderse (sin cambios respecto a la Fase A; lo cubre `marcador_alertas_e2e.py`).
A 320×568 el menú inicial mide ≈ 2,25 pantallas con scroll interno propio (antes 2,45 con el perfil sin compactar; la prueba exige ≤ 2,3).

## Guardar un lugar

- Los botones dicen **«Guardar mi casa»/«Guardar mi trabajo»** si no existen y **«Ir a Casa»/«Ir al Trabajo»** si ya existen (con «⋯» para cambiar ubicación o eliminar).
- **Exige sesión validada con el servidor.** Sin sesión se abre «Continuar con Google» (`Spevb.Cuenta.requiere`); al entrar se retoma lo que se quería hacer; si se cancela, vuelve el menú.
- Se cierra el menú y se abre un **modo de mapa propio** («Marca tu casa en el mapa»): pin en el centro del **área libre** del mapa (la barra de abajo —o de arriba durante un viaje, o a un
  costado en horizontal— tapa una parte), «Guardar este punto», «Cancelar», GPS solo al pulsar «Usar mi ubicación», y teclado (flechas mueven el mapa bajo el pin, +/− zoom, Enter guarda,
  Escape cancela). Se guardan las **coordenadas exactas bajo la punta del pin**, aunque la dirección aparezca lenta o nunca; una dirección que llega tarde no mueve el pin ni lo guardado.
- **Independiente de A/B:** usa un punto temporal propio; el destino viejo nunca se toma como Casa; `spevb-point-selected` de A/B no guarda nada. Si había un selector de A/B activo, **cede**
  (`Planner.cederSeleccion`) y se **restaura solo si sigue siendo pertinente** (`reanudarSeleccion`: no si A/B ya se llenó). A, B, resultados, recomendación, mapa del viaje y fase no se tocan.
- Valida coordenadas y zona de servicio (la misma de siempre), muestra «Guardando…» y el resultado real, impide el doble toque (una sola escritura) y confirma «Guardaste tu casa» devolviendo el foco.
- **«Agregar lugar»:** pide nombre (ejemplos «Universidad», «Casa de mamá»), recorta espacios, máx. 40 caracteres, siempre como **texto**, rechaza nombres repetidos y «Casa»/«Trabajo», pide
  confirmación si hay otro lugar a < 30 m («Guardar de todos modos»), hasta **30 lugares** en total (el contrato del servidor; `atajos.js` usaba 12).
- **Cambiar ubicación** reabre el mapa con el punto guardado bajo el pin (cancelar conserva la versión anterior); **Cambiar nombre** (solo personalizados); **Eliminar** con confirmación
  («No, conservar» tiene el foco). **Tocar un lugar** lo pone como destino por el punto de entrada de siempre (`Planner.poner('destination', …)`: el modo guiado conserva su paso; un viaje
  activo no se toca).

## Datos y sincronización

- Misma infraestructura: `Spevb.Datos`, clave `lugares`, `/api/cuenta/datos`, validador `DatosUsuario` (conserva `tipo`, `id`, `v` y lápidas). **Un solo lugar de verdad.**
- Los lugares de **una cuenta** viven aparte de los de un **invitado** (`spevb-lugares-cuenta` frente a `spevb-favoritos`): **nunca se fusionan**. Al entrar, la cuenta no hereda los favoritos del
  dispositivo y al salir se borra la copia de la cuenta; lo del invitado se conserva. Un favorito antiguo llamado «Casa»/«Trabajo» se interpreta por nombre (sin migrarlo a la fuerza).
- **Sin pisar cambios de otro dispositivo:** cada escritura es *leer lo último → aplicar → escribir condicionado a lo leído* (`base` = `actualizadoEn` del servidor; si alguien más escribió, el
  servidor responde **409** y el cliente repite, hasta 3 veces). Un borrado deja una **lápida** (`{id, borrado:true, v}`, 60 días, ≤ 30) para que **no reaparezca**; gana el cambio más reciente por
  lugar. Casa y Trabajo son únicos por cuenta (gana el más reciente).
- Cada operación comprueba identidad y **generación de sesión**: una respuesta tardía de otra cuenta, de otra pestaña con otra sesión o de una sesión anterior se descarta.
- **No hay guardado sin conexión:** cada cambio lo confirma el servidor; sin internet el mensaje lo dice («Sin conexión: tu lugar NO se guardó…»). Es una decisión: evita aplicar una escritura
  vieja sobre datos nuevos de otro dispositivo.

## Pruebas

Java: `DatosLugaresTest` (7), `CuentaIdentidadPostgresTest` (incluye la escritura con `base` y el borrado que no reaparece; PostgreSQL real). Navegador: `e2e/lugares_e2e.py` (22: invitado y
cancelar, favoritos antiguos, Casa/Trabajo exactos, A/B vacío/elegido/resultados/selector activo/viaje activo, «Universidad» y «Casa de mamá», duplicados y límite, editar/renombrar/eliminar,
doble toque, fallo del servidor, sin GPS, dirección tardía o lenta, fuera de zona, dos cuentas, dos dispositivos, respuesta vieja, teclado y roles, 320×568, letra grande, modo oscuro,
horizontal y pantalla grande) y la prueba de Casa/Trabajo de `mejoras414_e2e.py`. Capturas en `docs/capturas-viaje/lugares-*.png`.

## Qué no se probó

Google real; el mapa de teselas real en un teléfono (las pruebas usan el mapa con teselas vacías); teclado virtual real; lector de pantalla real.
