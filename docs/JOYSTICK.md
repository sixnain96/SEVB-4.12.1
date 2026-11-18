# Joystick de GPS para probar el Modo viaje (también con la app desplegada)

`scripts/joystick_gps.py` mueve la ubicación que ve la app, con un joystick en pantalla, teclado (WASD/flechas) o control de juegos. Sirve para probar caminar, subir al bus, avisos de bajada, desvíos y llegada **sin salir a la calle**. Dos modos:

## 1. Modo navegador (sin emulador) — el más simple, funciona con `https://mapas.spebv.tech`
```powershell
py -m pip install playwright            # una sola vez
py -m playwright install chromium       # una sola vez (si no tienes Edge ni Chrome)
py scripts/joystick_gps.py --navegador https://mapas.spebv.tech --abrir
```
Se abren **dos** pestañas/ventanas: el joystick (`http://127.0.0.1:8765`) y una ventana de Edge/Chrome (tamaño de celular) con la app desplegada. Lo que muevas en el joystick es el GPS que recibe la app (precisión 8 m por defecto: `--precision`). La app lo trata como un GPS real: «vigente», avisos de bajada, desvío del bus, recuperación, etc.
- `--perfil C:\sevb-perfil` conserva tu sesión de Google entre usos.
- `--canal msedge|chrome` elige el navegador. `--lat/--lng` fija el punto de inicio; `--ruta viaje.gpx` dibuja una guía.

## 2. Modo emulador de Android
```powershell
py scripts/joystick_gps.py --lat 4.121275 --lng -73.628899 --url https://mapas.spebv.tech --abrir
```
Con el emulador encendido; mueve el GPS con `adb emu geo fix` y `--url` abre la app desplegada en el navegador del teléfono virtual.

## Cuidados con la app desplegada
- Un viaje hecho con el joystick es un viaje **real** de la cuenta con la que entres (historial, logros, racha, «Compartir mi viaje»). Para probar usa una cuenta de prueba o la práctica del tutorial.
- Un teléfono físico no se puede mover así: eso es solo para navegador y emulador.
- Solo se aceptan URL `http(s)`; el joystick escucha únicamente en `127.0.0.1`.

## Pruebas
`e2e/joystick_e2e.py` (19), sin ventana ni emulador: incluye el modo navegador (la página recibe justo las coordenadas enviadas) y la validación de la URL.
