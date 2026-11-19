# Estilos de la página principal: `css/app.min.css`

`index.html` carga **un solo archivo de estilos**, `src/main/resources/static/css/app.min.css`. Sale de juntar y minificar las hojas listadas en `css/app.sources.txt`, en ese orden (las últimas ganan, igual que cuando `index.html` las cargaba una por una). Así el primer dibujo no espera 11 peticiones y los estilos pesan un cuarto menos.

## Cómo se edita un estilo

1. Edita la hoja de origen (`css/viaje.css`, `css/menu-figma.css`, etc.). **Nunca** `app.min.css`.
2. Regenera el archivo junto, desde la raíz del proyecto (necesita Node):

   ```powershell
   node scripts/build-css.mjs
   ```
3. Sube la hoja y `app.min.css` en el mismo commit.

Si olvidas el paso 2, `CssBundleTest` falla con «app.min.css está desactualizado». El archivo lleva en su primera línea la huella (SHA-256) de las hojas de origen y la prueba la recalcula; los saltos de línea se normalizan, así que da igual en Windows o Linux.

## Qué cambia al agregar una hoja

- Si es para `index.html`: agrégala a `css/app.sources.txt` y regenera. No pongas un `<link>` nuevo en `index.html` (la prueba lo rechaza).
- `styles.css` y `mapa.css` se siguen cargando sueltas en `editor.html`, `lugares.html`, `paraderos.html`, `pasos.html`, `puentes.html` y `reportes.html`; por eso el service worker (`sw.js`) guarda `app.min.css`, `styles.css` y `mapa.css`.
- Al cambiar la lista de archivos que guarda `sw.js`, sube el sufijo de `CACHE_APP` (p. ej. `-mapa5` → `-mapa6`).

## Por qué no hay un paso automático en Maven

El script usa `esbuild` (se descarga con `npx` en una versión fija) y requiere Node, que no está en la imagen de Docker de la aplicación. Dejar el archivo generado dentro del repositorio mantiene el despliegue como estaba y `CssBundleTest` hace de red de seguridad.

## Imágenes

Las del logo y las del pie del menú tienen versión WebP (`img/marca/sevb-chiguiro-logo.webp`, `sevb-chiguiro-menu.webp`); los PNG se conservan para las demás páginas y el manifiesto.
