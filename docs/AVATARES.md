# Avatares regionales de respaldo

**Estado (4.15.x):** el mecanismo está implementado y **las seis ilustraciones regionales están integradas** en `src/main/resources/static/img/avatares/` (PNG de 128 × 128, fondo transparente). Si el manifiesto quedara vacío se vería el chigüiro de siempre.

| Archivo | Nombre visible | Descripción |
| --- | --- | --- |
| `chiguiro.png` | Chigüiro | Chigüiro de la Orinoquía |
| `danta.png` | Danta | Danta de los bosques del Llano |
| `venado.png` | Venado | Venado de la sabana |
| `guacamaya.png` | Guacamaya | Guacamaya de la Orinoquía |
| `moriche.png` | Palma de moriche | Palma de moriche junto al agua |
| `saman.png` | Samán | Samán de los Llanos |

Son ilustraciones originales entregadas por la persona propietaria del proyecto; no se copiaron obras con derechos de autor.

## Prioridad en «Mi cuenta» y «Ajustes de la cuenta»
1. Foto de Google, solo si es válida (HTTPS, subdominio de `googleusercontent.com`) **y carga**.
2. Avatar regional estable (este documento).
3. Chigüiro local (`/img/marca/sevb-cabeza-96.png`).

El regional se pinta de inmediato (sin círculo vacío) y la foto de Google lo reemplaza solo si carga. Si falla o no hay internet, se queda el regional y **esa foto no se vuelve a pedir en la misma vista**. Si por una condición excepcional tampoco carga el regional, vuelve el chigüiro local (`/img/marca/sevb-cabeza-96.png`): nunca una imagen rota. Sin sesión se ve la identidad genérica (chigüiro).

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
**Limitación:** si cambia la cantidad de imágenes, la asignación puede cambiar (con las seis actuales, 300 cuentas de muestra usan los seis personajes). Si se necesitara estabilidad absoluta habría que guardar un identificador de avatar en el perfil (migración pequeña).

## CSP
Las imágenes son locales (`img-src 'self'`); no se amplía ninguna política. Se mantiene `https://*.googleusercontent.com` solo para la foto de Google.

## Pruebas
- `python e2e/avatares_e2e.py` (15 casos, con las imágenes **reales**, sin PNG temporal): manifiesto con exactamente seis entradas válidas y únicas; cada URL responde 200 con `image/png`, mide 128 × 128 y conserva la transparencia en las esquinas; mismo id → mismo avatar; reparto de 300 cuentas entre los seis; la foto lenta no reemplaza al regional hasta cargar; foto fallida mantiene el regional y no se pide dos veces; regional roto → chigüiro local; **sin conexión** los avatares siguen disponibles por el service worker; «Mi cuenta» y «Ajustes» muestran lo mismo; 320 × 568 sin desplazamiento horizontal; avatar decorativo junto al nombre.
- `AvataresRecursosTest` (JUnit, `mvn verify`): las seis imágenes existen en el **classpath final**, se decodifican, miden 128 × 128 y conservan transparencia.
- Las seis rutas están en el `SHELL` de `sw.js` (caché `-mapa3`).
- **No se probó:** una cuenta de Google real con foto ni un teléfono.
