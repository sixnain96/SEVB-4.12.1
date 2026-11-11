# Avatares regionales de respaldo

**Estado:** el mecanismo está implementado; **las ilustraciones aún no existen en el repositorio**. Mientras el manifiesto esté vacío se ve el chigüiro de siempre.

## Prioridad en «Mi cuenta» y «Ajustes de la cuenta»
1. Foto de Google, solo si es válida (HTTPS, subdominio de `googleusercontent.com`) **y carga**.
2. Avatar regional estable (este documento).
3. Chigüiro local (`/img/marca/sevb-cabeza-96.png`).

El regional se pinta de inmediato (sin círculo vacío) y la foto de Google lo reemplaza solo si carga. Si falla o no hay internet, se queda el regional; no hay reintentos. Sin sesión se ve la identidad genérica (chigüiro).

## Cómo agregar o retirar una imagen (una sola lista)
1. Pon el archivo en `src/main/resources/static/img/avatares/` (la carpeta se crea con la primera imagen).
2. Agrega un elemento a `MANIFIESTO` en `src/main/resources/static/js/avatares.js`:
   `{ archivo: 'jaguar.webp', nombre: 'Jaguar', descripcion: 'Jaguar de los llanos' }`
3. Agrega la ruta a `SHELL` en `sw.js` para que esté disponible sin conexión.
Retirar una imagen es borrar su elemento. No hay que tocar ningún otro módulo.

## Requisitos de los archivos
- WebP o PNG optimizado, relación 1:1, mínimo 96 × 96 (ideal 192 × 192), fondo y recorte compatibles con máscara circular, sin texto.
- Nombre del archivo: letras, números, punto, guion y guion bajo (`^[A-Za-z0-9][A-Za-z0-9._-]*\.(webp|png)$`); cualquier otra entrada se ignora.
- El avatar es decorativo junto al nombre visible (`alt` vacío); la descripción del manifiesto es documentación.

## Selección estable
Hash FNV-1a de 32 bits del identificador de la cuenta (`id:<id>`, o el correo normalizado si no hubiera `id`) módulo la cantidad de imágenes válidas. El mismo usuario recibe siempre el mismo avatar, también en otro dispositivo. El identificador nunca sale del navegador ni va en una URL.
**Limitación:** si cambia la cantidad de imágenes, la asignación puede cambiar. Si se necesitara estabilidad absoluta habría que guardar un identificador de avatar en el perfil (migración pequeña); no se hizo porque hoy no hay imágenes.

## CSP
Las imágenes son locales (`img-src 'self'`); no se amplía ninguna política. Se mantiene `https://*.googleusercontent.com` solo para la foto de Google.

## Pruebas
`python e2e/avatares_e2e.py` (6 casos; la suite inyecta un manifiesto temporal con un PNG de 1 px). Lo que **no** prueba: las ilustraciones reales ni una cuenta de Google real.

## Estado de los recursos (honesto)
A 2026-11-11 **no existen** ilustraciones de fauna, flora o cultura de la Orinoquía en el repositorio: `MANIFIESTO` está vacío a propósito y la aplicación muestra el chigüiro. El archivo `PING_Avatares_Editables.zip` que circula **no sirve**: son otros personajes (conejo, gato, nutria, panda rojo) de otro proyecto. Cuando haya archivos propios, siga «Cómo agregar o retirar una imagen» y sus nombres reales quedarán en el manifiesto; no se generan imágenes falsas ni se copian obras con derechos de autor.
