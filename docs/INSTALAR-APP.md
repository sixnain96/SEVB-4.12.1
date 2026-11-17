# Instalar SEVB como app (PWA) · «Instalar en tu celular»

Estado: implementado y probado con navegadores simulados (User-Agent y eventos). Sin publicar. Código: `js/instalar.js`, sección `#menuInstalar` de `index.html`, bloque «Instalar en tu celular» de `home.css`, `sw.js` (lista de archivos).

## Qué es y qué no es

SEVB es una **PWA** (aplicación web progresiva): `manifest.webmanifest` + `sw.js` + iconos. El navegador la **instala** como una app (icono propio, pantalla completa, arranque rápido, caché sin conexión).
**No genera un archivo `.apk`** ni va a Play Store: se instala desde el navegador, a partir del mismo enlace. Si en algún momento se necesitara un APK real, habría que empaquetar la PWA aparte
(p. ej. una Trusted Web Activity con Bubblewrap); no es parte de esta función.

## Cómo funciona

- En el menú ☰ → **«Instalar en tu celular»** (se oculta durante un viaje). Explica con palabras simples qué es y que no hace falta Play Store ni APK.
- **Detecta** el sistema (Android, iPhone/iPad, computador) y el navegador (Chrome, Edge, Brave, Firefox, Safari, Samsung Internet, Opera) con el User-Agent; Brave se reconoce con `navigator.brave.isBrave()`
  y un iPad que se presenta como Mac, por sus puntos de toque. Muestra «Estás usando Safari en iPhone o iPad» y los **pasos numerados** de ese navegador, con iconos de los botones ({⋮}, {≡}, Compartir, instalar).
- Si la detección se equivoca, la lista **«¿No es tu navegador? Elige el tuyo»** cambia los pasos.
- Si el navegador avisa que puede instalar (`beforeinstallprompt`: Chrome/Edge/Brave/Samsung), aparece **«Instalar ahora»** (un toque, sin pasos).
- Si ya está instalada (`display-mode: standalone`) lo dice. Si la página se abrió por `http://` (fuera de `localhost`) explica que solo se puede instalar desde `https://`.
- No guarda ni envía nada; los pasos son texto fijo del propio archivo (nunca HTML de fuera).

## Pasos por navegador (resumen)

| Dónde | Pasos |
|---|---|
| Android · Chrome / Brave | ⋮ → «Instalar aplicación» (o «Añadir a la pantalla de inicio») → Instalar |
| Android · Edge | menú … → «Añadir al teléfono» → Instalar |
| Android · Firefox | ⋮ → «Instalar» → Añadir |
| Android · Samsung Internet | ≡ → «Añadir página a» → «Pantalla de inicio» |
| iPhone/iPad · Safari | Compartir → «Añadir a pantalla de inicio» → Añadir |
| iPhone · Chrome/Edge/Firefox | Compartir → «Añadir a pantalla de inicio» (iOS 16.4 o más; si no aparece, abrir en Safari) |
| Computador · Chrome / Edge / Brave | icono de instalar a la derecha de la barra de direcciones |
| Computador · Safari (Mac) | Archivo → «Añadir al Dock…» |
| Computador · Firefox | normalmente no instala apps web: usar Chrome o Edge |

## Pruebas

`e2e/instalar_e2e.py` (8): detección con 13 User-Agent distintos + Brave + iPad-Mac, el paso a paso de ocho combinaciones en el menú, 320×568 sin desborde (captura `docs/capturas-viaje/instalar-ios-safari-320.png`),
«Instalar ahora» solo con el aviso del navegador y usado una vez, «ya instalada» y «sin https», elegir otro navegador, teclado y texto sin HTML.

## Qué falta validar

Las formas exactas de los menús cambian con las versiones de cada navegador (los nombres de las opciones se redactaron según su documentación y pueden variar): conviene probar **a mano** en un Android con Chrome,
en un iPhone con Safari y en Samsung Internet, y corregir los textos si algún menú se llama distinto. Tampoco se probó la instalación real (solo la guía y el botón con eventos simulados), y Brave/Opera/Edge móviles
no se probaron en dispositivo.
