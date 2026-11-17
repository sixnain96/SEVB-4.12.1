"""Mide el ARRANQUE del mapa (config → adaptador → SDK → mapa → planificador) comparando dos copias del frontend con las mismas condiciones.

Qué mide y qué NO:
  · Google con el SDK SIMULADO (e2e/harness/google_fake.js, servido sin red): mide el trabajo y el orden de SEVB (cuándo empieza y termina la petición de configuración, cuándo está
    el adaptador, el mapa y el planificador). NO mide la descarga del SDK real, ni teselas, ni dibujo de Google: eso exige una clave autorizada y un teléfono.
  · La red lenta (CDP Network.emulateNetworkConditions) afecta a lo que sale del servidor simulado (HTML, JS, CSS, /api/config/mapa); el SDK simulado lo entrega el navegador de pruebas.
  · Primera apertura = contexto nuevo, sin caché ni service worker instalado. Recarga = segunda carga del mismo contexto con el service worker activo y la caché HTTP.
  · CPU 4× más lenta, 390×844 a 2×. Las dos copias se sirven desde dos servidores simulados y las corridas se ALTERNAN (antes/después) para repartir el ruido.

Uso: python e2e/rendimiento/medir_arranque_mapa.py --antes RUTA_STATIC_ANTES [--n 7] [--red normal|lenta|ambas] [--salida archivo.json]
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import sevb_e2e as B  # noqa: E402
import mapa_adaptadores_e2e as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(AQUI))
MOVIL = {'viewport': {'width': 390, 'height': 844}, 'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2}
RED = {'normal': None, 'lenta': {'latencia': 150, 'bajada': 1.6e6 / 8, 'subida': 750e3 / 8}}      # lenta: 150 ms y 1,6 Mb/s (igual que medir_pasajero.py)

INIT = """
window.__t = { listo: 0 };
window.addEventListener('spevb-planner-listo', () => { window.__t.listo = performance.now(); });
"""


def lanzar(puerto, estatico=None):
    env = {**os.environ, 'SEVB_STUB_MAPA': 'google'}
    if estatico:
        env['SEVB_STUB_STATIC'] = estatico
    p = subprocess.Popen([sys.executable, '-I', os.path.join(RAIZ, 'e2e', 'stub_server.py'), str(puerto)], cwd=RAIZ, env=env, stdin=subprocess.DEVNULL)
    fin = time.time() + 30
    while time.time() < fin:
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{puerto}/api/estado', timeout=2).status == 200:
                return p, f'http://127.0.0.1:{puerto}/'
        except OSError:
            time.sleep(0.5)
    raise SystemExit('el servidor simulado no respondió')


JS_METRICAS = """() => {
  const m = (n) => { const e = performance.getEntriesByName(n)[0]; return e ? Math.round(e.startTime) : null; };
  const rec = performance.getEntriesByType('resource');
  const cfg = rec.filter((x) => x.name.includes('/api/config/mapa'));
  const nav = performance.getEntriesByType('navigation')[0];
  return { cfg_inicio: cfg[0] ? Math.round(cfg[0].startTime) : null, cfg_fin: cfg[0] ? Math.round(cfg[0].responseEnd) : null, cfg_peticiones: cfg.length,
    config: m('sevb-config-lista'), adaptador: m('sevb-adaptador-listo'), sdk: m('sevb-sdk-listo'), mapa: m('sevb-mapa-listo'),
    calles: m('sevb-calles-visibles'), planificador: Math.round(window.__t.listo) || null,
    dcl: nav ? Math.round(nav.domContentLoadedEventEnd) : null, carga: nav ? Math.round(nav.loadEventEnd) : null,
    solicitudes: rec.length, instancias: window.__gfake ? window.__gfake.mapas : null, escuchas: window.__gfake ? window.__gfake.escuchas : null,
    sdk_cargas: rec.filter((x) => x.name.includes('maps.googleapis.com/maps/api/js')).length };
}"""


def una(nav, base, red, recarga):
    g = M.Google(nav, base, service_workers='allow', **MOVIL)
    s = g.s
    s.ctx.add_init_script(INIT)
    cdp = s.ctx.new_cdp_session(s.page)
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    if RED[red]:
        r = RED[red]
        cdp.send('Network.enable')
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': r['latencia'], 'downloadThroughput': r['bajada'], 'uploadThroughput': r['subida']})
    p = s.page
    p.goto(base, wait_until='domcontentloaded')
    B.esperar(p, '!!(window.Spevb && Spevb.maps && Spevb.maps.map) && window.__t.listo > 0', 60000)
    p.wait_for_timeout(700)
    if recarga:
        try:
            p.evaluate("navigator.serviceWorker ? navigator.serviceWorker.ready.then(() => true) : false")
        except Exception:  # noqa: BLE001
            pass
        p.wait_for_timeout(1500)
        p.reload(wait_until='domcontentloaded')
        B.esperar(p, '!!(window.Spevb && Spevb.maps && Spevb.maps.map) && window.__t.listo > 0', 60000)
        p.wait_for_timeout(700)
    r = p.evaluate(JS_METRICAS)
    g.cerrar()
    return r


def resumen(lista, clave):
    v = sorted(x[clave] for x in lista if x.get(clave) is not None)
    if not v:
        return None
    q = statistics.quantiles(v, n=4) if len(v) >= 4 else [v[0], v[0], v[-1]]
    return {'mediana': round(statistics.median(v)), 'min': v[0], 'max': v[-1], 'q1': round(q[0]), 'q3': round(q[2]), 'n': len(v)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--antes', required=True)
    ap.add_argument('--n', type=int, default=7)
    ap.add_argument('--red', default='ambas', choices=['normal', 'lenta', 'ambas'])
    ap.add_argument('--salida', default=None)
    ap.add_argument('--puertos', default='18310,18311')
    a = ap.parse_args()
    pa, pd = [int(x) for x in a.puertos.split(',')]
    sa, ba = lanzar(pa, a.antes)
    sd, bd = lanzar(pd, None)
    res = {'n': a.n, 'fecha': time.strftime('%Y-%m-%d'), 'nota': 'SDK de Google SIMULADO; sin Google real. CPU 4x. Corridas alternadas antes/despues.'}
    try:
        with sync_playwright() as pw:
            nav = B.navegador(pw)
            res['navegador'] = nav.browser_type.name + ' ' + nav.version
            for red in (['normal', 'lenta'] if a.red == 'ambas' else [a.red]):
                for recarga in (False, True):
                    cuenta = {'antes': [], 'despues': []}
                    for i in range(a.n):
                        orden = (('antes', ba), ('despues', bd)) if i % 2 == 0 else (('despues', bd), ('antes', ba))
                        for nombre, base in orden:
                            cuenta[nombre].append(una(nav, base, red, recarga))
                    clave = f"{'recarga' if recarga else 'primera'}_{red}"
                    res[clave] = {n: {k: resumen(v, k) for k in ('cfg_inicio', 'cfg_fin', 'config', 'adaptador', 'sdk', 'mapa', 'planificador', 'dcl', 'carga', 'solicitudes', 'cfg_peticiones', 'sdk_cargas', 'instancias')} for n, v in cuenta.items()}
                    print(clave, json.dumps({n: {k: (x or {}).get('mediana') for k, x in d.items()} for n, d in res[clave].items()}, ensure_ascii=False))
            nav.close()
    finally:
        sa.terminate(); sd.terminate()
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.salida:
        open(a.salida, 'w', encoding='utf-8').write(txt)


if __name__ == '__main__':
    main()
