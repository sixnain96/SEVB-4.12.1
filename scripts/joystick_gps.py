#!/usr/bin/env python3
"""Joystick para mover la ubicación del emulador de Android EN TIEMPO REAL (como las apps que mueven el GPS en Pokémon Go), para demostrar el Modo viaje.

Abre una página en tu navegador con un joystick (ratón, dedo, teclado WASD / flechas o un control de Xbox/PlayStation), un mapa y botones de velocidad
(a pie, bus lento, bus). Cada segundo envía la posición al emulador con `adb emu geo fix`, así que la app de SEVB que corre dentro del teléfono virtual
«camina», «se sube a un bus» y «se baja» según lo que hagas con el joystick. Solo usa la biblioteca estándar de Python y escucha únicamente en tu
propio equipo (127.0.0.1).

DOS MODOS (los dos sirven con la app desplegada, p. ej. https://mapas.spebv.tech):
  · Emulador de Android: el joystick mueve el GPS del emulador con `adb emu geo fix`; con --url además abre la página en el navegador del emulador.
  · Navegador (--navegador URL): NO hace falta emulador. Abre una ventana de Edge/Chrome con la página y le fija la ubicación (Playwright). La app la recibe como un GPS real
    (precisión, avisos de bajada, desvíos, todo). Con --perfil conserva tu sesión de Google entre usos.

Uso (PowerShell, en la raíz del proyecto):
    py scripts/joystick_gps.py --lat 4.121275 --lng -73.628899 --abrir
    py scripts/joystick_gps.py --lat 4.121275 --lng -73.628899 --ruta viaje.gpx --abrir     # dibuja el recorrido como guía
    py scripts/joystick_gps.py --prueba                                                      # sin emulador: solo muestra lo que enviaría
    py scripts/joystick_gps.py --navegador https://mapas.spebv.tech --abrir                  # SIN emulador: una ventana del navegador con la app desplegada
    py scripts/joystick_gps.py --url https://mapas.spebv.tech --abrir                        # con emulador: abre la app desplegada dentro del teléfono virtual
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import queue
import webbrowser
from urllib.parse import urlparse as _urlparse
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

AQUI = os.path.dirname(os.path.abspath(__file__))
PAGINA = os.path.join(AQUI, 'joystick')
LEAFLET = os.path.normpath(os.path.join(AQUI, '..', 'src', 'main', 'resources', 'static', 'vendor', 'leaflet'))
TIPOS = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.json': 'application/json'}


def adb_por_defecto():
    """`adb` del PATH o, si no está, el del SDK de Android Studio en su carpeta habitual de Windows."""
    en_path = shutil.which('adb')
    if en_path:
        return en_path
    local = os.environ.get('LOCALAPPDATA')
    if local:
        candidato = os.path.join(local, 'Android', 'Sdk', 'platform-tools', 'adb.exe')
        if os.path.isfile(candidato):
            return candidato
    return 'adb'


def leer_gpx(ruta):
    """Puntos [lat, lng] de un GPX (trkpt, rtept o wpt)."""
    raiz = ET.parse(ruta).getroot()
    return [[float(p.get('lat')), float(p.get('lon'))] for p in raiz.iter() if p.tag.rsplit('}', 1)[-1] in ('trkpt', 'rtept', 'wpt')]


def leer_gps_del_telefono(texto):
    """Última ubicación del proveedor «gps» según `adb shell dumpsys location` → (lat, lng, precision_m) o None."""
    m = re.search(r'last location=Location\[gps (-?\d+\.\d+),(-?\d+\.\d+) hAcc=([\d.]+)', texto)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3))) if m else None


def comando_fix(adb, serial, lat, lng):
    """`adb emu geo fix` recibe la LONGITUD primero y luego la latitud. Se pasa como lista (nunca por un shell)."""
    return [adb] + (['-s', serial] if serial else []) + ['emu', 'geo', 'fix', f'{lng:.7f}', f'{lat:.7f}']


def coordenada_valida(lat, lng):
    return isinstance(lat, (int, float)) and isinstance(lng, (int, float)) and not isinstance(lat, bool) and not isinstance(lng, bool) \
        and -90 <= lat <= 90 and -180 <= lng <= 180


def url_valida(url):
    """Solo http(s) con un servidor (nada de file:, javascript: ni cadenas raras)."""
    try:
        u = _urlparse(url)
    except ValueError:
        return False
    return u.scheme in ('http', 'https') and bool(u.netloc) and len(url) <= 300 and not any(c in url for c in ' \t\r\n"\'<>`')


class EmisorNavegador:
    """Fija la ubicación de una ventana de Edge/Chrome abierta en la app (Playwright), sin emulador. Todo Playwright vive en SU propio hilo (la API es de un solo hilo):
    el servidor HTTP solo deja la última posición pedida y este hilo la aplica; si llegan varias seguidas, solo importa la última."""
    prueba = False

    def __init__(self, url, precision=8.0, perfil=None, canal=None, sin_ventana=False, inicio=(4.1370, -73.6266)):
        if not url_valida(url):
            raise ValueError('La URL debe ser http(s) válida, p. ej. https://mapas.spebv.tech')
        self.url, self.precision, self.perfil, self.canal, self.sin_ventana = url, float(precision), perfil, canal, sin_ventana
        self.adb = 'navegador'
        self.ultimo = None
        self.enviados = 0
        self.error = None
        self.listo = threading.Event()
        self.abierto = False
        self._pendiente = None
        self._trabajos = queue.Queue()
        self._senal = threading.Event()
        self._parar = threading.Event()
        self._inicio = inicio
        self._hilo = threading.Thread(target=self._bucle, name='joystick-navegador', daemon=True)

    def arrancar(self, espera=40):
        self._hilo.start()
        self.listo.wait(espera)
        return self.abierto

    def parar(self):
        self._parar.set(); self._senal.set()
        self._hilo.join(10)

    def dispositivos(self):
        return ['navegador: ' + self.url] if self.abierto else []

    def ejecutar(self, funcion, espera=10):
        """Corre `funcion(pagina)` en el hilo de Playwright y devuelve su resultado (None si no hay ventana o tarda demasiado)."""
        if not self.abierto:
            return None
        caja = {}
        hecho = threading.Event()
        self._trabajos.put((funcion, caja, hecho)); self._senal.set()
        hecho.wait(espera)
        return caja.get('r')

    def telefono(self):
        """Lo que la PÁGINA recibe de verdad del navegador (comprobación independiente de lo que enviamos); si no se puede leer, lo último enviado."""
        leida = self.ejecutar(lambda pg: pg.evaluate("""() => new Promise((ok) => navigator.geolocation.getCurrentPosition(
            (p) => ok({ lat: p.coords.latitude, lng: p.coords.longitude, precision: p.coords.accuracy }), () => ok(null), { timeout: 3000, maximumAge: 0 }))"""))
        if leida:
            return leida
        return {'lat': self.ultimo[0], 'lng': self.ultimo[1], 'precision': self.precision} if self.ultimo else None

    def enviar(self, lat, lng):
        if not coordenada_valida(lat, lng):
            return False, 'Coordenada inválida.'
        if not self.abierto:
            return False, self.error or 'La ventana del navegador no está abierta.'
        self._pendiente = (lat, lng)
        self._senal.set()
        self.ultimo = [lat, lng]
        self.enviados += 1
        return True, None

    def _bucle(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.error = 'Falta Playwright: py -m pip install playwright  (y  py -m playwright install chromium)'
            self.listo.set(); return
        try:
            with sync_playwright() as pw:
                ctx = self._abrir(pw)
                pagina = ctx.pages[0] if ctx.pages else ctx.new_page()
                lat0, lng0 = self._inicio
                ctx.set_geolocation({'latitude': lat0, 'longitude': lng0, 'accuracy': self.precision})
                pagina.goto(self.url, wait_until='domcontentloaded', timeout=45000)
                self.abierto = True; self.error = None; self.listo.set()
                while not self._parar.is_set():
                    self._senal.wait(0.5); self._senal.clear()
                    if not ctx.pages:      # la persona cerró la ventana
                        self.abierto = False; self.error = 'Cerraste la ventana del navegador. Vuelve a abrir el joystick.'; break
                    while not self._trabajos.empty():
                        f, caja, hecho = self._trabajos.get_nowait()
                        try:
                            caja['r'] = f(pagina)
                        except Exception:  # noqa: BLE001
                            caja['r'] = None
                        hecho.set()
                    p = self._pendiente; self._pendiente = None
                    if p:
                        try:
                            ctx.set_geolocation({'latitude': p[0], 'longitude': p[1], 'accuracy': self.precision})
                        except Exception as e:  # noqa: BLE001
                            self.error = f'No se pudo mover la ubicación: {e}'
                ctx.close()
        except Exception as e:  # noqa: BLE001
            self.error = f'No se pudo abrir el navegador: {e}'
        finally:
            self.abierto = False; self.listo.set()

    def _abrir(self, pw):
        opciones = dict(permissions=['geolocation'], viewport={'width': 412, 'height': 860}, is_mobile=True, has_touch=True, device_scale_factor=2.5,
                        locale='es-CO', timezone_id='America/Bogota')
        canales = [self.canal] if self.canal else ['msedge', 'chrome', None]
        ultimo = None
        for canal in canales:
            try:
                kw = {'headless': self.sin_ventana}
                if canal:
                    kw['channel'] = canal
                if self.perfil:
                    return pw.chromium.launch_persistent_context(self.perfil, **kw, **opciones)
                return pw.chromium.launch(**kw).new_context(**opciones)
            except Exception as e:  # noqa: BLE001
                ultimo = e
        raise RuntimeError(f'ningún navegador disponible ({ultimo})')


def abrir_en_emulador(adb, serial, url):
    """Abre la página en el navegador del emulador (intent VIEW). Devuelve (ok, mensaje)."""
    if not url_valida(url):
        return False, 'URL inválida.'
    try:
        r = subprocess.run([adb] + (['-s', serial] if serial else []) + ['shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', url], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f'adb falló: {e}'
    return r.returncode == 0 and 'Error' not in r.stdout, (r.stdout + r.stderr).strip()


class Emisor:
    """Envía las posiciones al emulador de una en una (si llegan más rápido de lo que adb responde, las intermedias no importan)."""

    def __init__(self, adb, serial, prueba=False):
        self.adb, self.serial, self.prueba = adb, serial, prueba
        self.bloqueo = threading.Lock()
        self.ultimo = None
        self.enviados = 0
        self.fixes = []          # solo en modo prueba
        self.error = None

    def dispositivos(self):
        if self.prueba:
            return ['prueba']
        try:
            r = subprocess.run([self.adb, 'devices'], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.SubprocessError) as e:
            self.error = f'No se pudo ejecutar adb: {e}'
            return []
        return [l.split('\t')[0] for l in r.stdout.splitlines()[1:] if l.strip().endswith('device')]

    def telefono(self):
        """Lo que el sistema Android del emulador tiene como ubicación del GPS (comprobación independiente de lo que enviamos)."""
        if self.prueba:
            return {'lat': self.ultimo[0], 'lng': self.ultimo[1], 'precision': 5.0} if self.ultimo else None
        try:
            r = subprocess.run([self.adb] + (['-s', self.serial] if self.serial else []) + ['shell', 'dumpsys', 'location'], capture_output=True, text=True, timeout=10, errors='replace')
        except (OSError, subprocess.SubprocessError):
            return None
        g = leer_gps_del_telefono(r.stdout)
        return {'lat': g[0], 'lng': g[1], 'precision': g[2]} if g else None

    def enviar(self, lat, lng):
        if not coordenada_valida(lat, lng):
            return False, 'Coordenada inválida.'
        with self.bloqueo:
            if self.prueba:
                self.fixes.append([lat, lng])
            else:
                try:
                    r = subprocess.run(comando_fix(self.adb, self.serial, lat, lng), capture_output=True, text=True, timeout=8)
                except (OSError, subprocess.SubprocessError) as e:
                    self.error = f'adb falló: {e}'
                    return False, self.error
                if r.returncode != 0 or 'KO' in r.stdout:
                    self.error = (r.stderr or r.stdout).strip() or 'adb no pudo mover la ubicación.'
                    return False, self.error
            self.error = None
            self.ultimo = [lat, lng]
            self.enviados += 1
        return True, None


def crear_servidor(puerto, emisor, config, ruta_gpx=None):
    ruta = leer_gpx(ruta_gpx) if ruta_gpx else []

    class H(BaseHTTPRequestHandler):
        server_version = 'SEVB-joystick'

        def log_message(self, *a):
            pass

        def _enviar(self, codigo, cuerpo, tipo):
            data = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode('utf-8')
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def _json(self, obj, codigo=200):
            self._enviar(codigo, json.dumps(obj), 'application/json')

        def _archivo(self, base, relativa):
            # Solo se sirven archivos que estén dentro de la carpeta indicada (nada de «..»).
            destino = os.path.normpath(os.path.join(base, relativa))
            if os.path.commonpath([base, destino]) != base or not os.path.isfile(destino):
                return self._enviar(404, 'No encontrado', 'text/plain; charset=utf-8')
            with open(destino, 'rb') as f:
                self._enviar(200, f.read(), TIPOS.get(os.path.splitext(destino)[1].lower(), 'application/octet-stream'))

        def do_GET(self):
            u = urlparse(self.path).path
            if u == '/api/estado':
                return self._json({'modo': 'prueba' if emisor.prueba else ('navegador' if isinstance(emisor, EmisorNavegador) else 'adb'), 'url': getattr(emisor, 'url', None), 'dispositivos': emisor.dispositivos(), 'ultimo': emisor.ultimo,
                                   'enviados': emisor.enviados, 'error': emisor.error, 'adb': emisor.adb})
            if u == '/api/telefono':
                return self._json({'telefono': emisor.telefono(), 'enviado': emisor.ultimo})
            if u == '/api/config':
                return self._json(config)
            if u == '/api/ruta':
                return self._json(ruta)
            if u == '/api/fixes' and emisor.prueba:
                return self._json(emisor.fixes)
            if u.startswith('/vendor/leaflet/'):
                return self._archivo(LEAFLET, u[len('/vendor/leaflet/'):])
            self._archivo(PAGINA, 'index.html' if u in ('/', '') else u.lstrip('/'))

        def do_POST(self):
            if urlparse(self.path).path != '/api/fix':
                return self._json({'ok': False, 'error': 'No encontrado'}, 404)
            try:
                n = int(self.headers.get('Content-Length') or 0)
                cuerpo = json.loads(self.rfile.read(min(n, 4096)) or b'{}')
            except (ValueError, json.JSONDecodeError):
                return self._json({'ok': False, 'error': 'JSON inválido'}, 400)
            ok, error = emisor.enviar(cuerpo.get('lat'), cuerpo.get('lng'))
            self._json({'ok': ok, 'error': error}, 200 if ok else 400)

    return ThreadingHTTPServer(('127.0.0.1', puerto), H)


def principal(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lat', type=float, default=4.1370, help='latitud donde empieza el teléfono (por defecto, centro de Villavicencio)')
    ap.add_argument('--lng', type=float, default=-73.6266, help='longitud donde empieza el teléfono')
    ap.add_argument('--ruta', help='GPX opcional (el de scripts/gpx_viaje.py) para dibujar el recorrido como guía')
    ap.add_argument('--puerto', type=int, default=8765)
    ap.add_argument('--intervalo', type=float, default=1.0, help='segundos entre posiciones enviadas (1 = como un GPS real)')
    ap.add_argument('--serial', help='emulador concreto, p. ej. emulator-5554 (si hay varios dispositivos)')
    ap.add_argument('--adb', default=adb_por_defecto())
    ap.add_argument('--prueba', action='store_true', help='no llama a adb: guarda las posiciones en memoria (para las pruebas automáticas)')
    ap.add_argument('--abrir', action='store_true', help='abre la página en tu navegador')
    ap.add_argument('--navegador', metavar='URL', help='SIN emulador: abre una ventana de Edge/Chrome en esa URL (p. ej. https://mapas.spebv.tech) y le fija la ubicación')
    ap.add_argument('--url', metavar='URL', help='con emulador: abre esta URL en el navegador del teléfono virtual')
    ap.add_argument('--precision', type=float, default=8.0, help='precisión (m) que verá la app en modo --navegador (por defecto 8: una lectura buena)')
    ap.add_argument('--perfil', help='carpeta para conservar tu sesión (Google) entre usos del modo --navegador')
    ap.add_argument('--canal', choices=['msedge', 'chrome'], help='navegador del modo --navegador (por defecto: Edge, luego Chrome)')
    ap.add_argument('--sin-ventana', action='store_true', help='modo --navegador sin ventana visible (pruebas automáticas)')
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if not coordenada_valida(a.lat, a.lng):
        raise SystemExit('Coordenada inicial inválida.')
    if a.navegador:
        try:
            emisor = EmisorNavegador(a.navegador, a.precision, a.perfil, a.canal, a.sin_ventana, (a.lat, a.lng))
        except ValueError as e:
            raise SystemExit(str(e))
        print('Abriendo el navegador en', a.navegador, '…')
        if not emisor.arrancar():
            raise SystemExit(emisor.error or 'No se pudo abrir el navegador.')
    else:
        emisor = Emisor(a.adb, a.serial, a.prueba)
    config = {'lat': a.lat, 'lng': a.lng, 'intervalo': a.intervalo}
    srv = crear_servidor(a.puerto, emisor, config, a.ruta)
    url = f'http://127.0.0.1:{a.puerto}/'
    disp = emisor.dispositivos()
    print(f'Joystick de GPS en {url}')
    if isinstance(emisor, EmisorNavegador):
        print('Navegador:', ', '.join(disp))
    else:
        print('Emulador:', ', '.join(disp) if disp else 'NO se ve ningún emulador encendido (enciéndelo y vuelve a abrir la página).')
        if a.url and disp and not a.prueba:
            ok, msg = abrir_en_emulador(a.adb, a.serial, a.url)
            print('Abriendo', a.url, 'en el emulador:', 'listo' if ok else 'no se pudo (' + msg + ')')
    print('Detener: Ctrl+C')
    if a.abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('Detenido.')
    finally:
        if isinstance(emisor, EmisorNavegador):
            emisor.parar()
    return 0


if __name__ == '__main__':
    sys.exit(principal())
