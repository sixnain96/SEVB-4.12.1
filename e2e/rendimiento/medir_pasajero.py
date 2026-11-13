"""Rendimiento del flujo del PASAJERO (4.15.4), reproducible y comparable antes/después.

Mide, en un Chromium real (Playwright) contra el servidor simulado (frontend real, API simulada, GPS simulado, sin Internet):
  carga       arranque en frío (sin caché) y recarga con caché: DCL, load, FCP, LCP, tiempo hasta interfaz interactiva (spevb-planner-listo), tareas largas, bytes de JS/CSS
  teclado     última tecla → lista de sugerencias visible
  buscar      «Buscar rutas» → recomendación visible (opción elegida + «Iniciar viaje»)
  iniciar     «Iniciar viaje» → tarjeta y marcador visibles
  fluidez     cuadros por segundo, cuadro lento (p95/máx) y tareas largas al arrastrar el panel y al actualizar el marcador con GPS a 10 Hz
  recursos    oyentes de eventos, intervalos, temporizadores pendientes y MutationObservers ACTIVOS (inicio, planificando, en viaje, tras terminar, tras 5 viajes)
  memoria     heap de JS y nodos del DOM tras cada uno de varios viajes seguidos (con recolección de basura forzada)

Las mediciones de TIEMPO se hacen SIN instrumentación; la instrumentación de contadores va en otra corrida (para no falsear los tiempos).
Condiciones: --cpu N (ralentización de CPU; 1 = sin limitar, 4 = gama media), --red rapida|lenta (lenta = 150 ms de latencia y 1,6 Mb/s).
Uso: SEVB_E2E_URL=http://127.0.0.1:18200/ python e2e/rendimiento/medir_pasajero.py --cpu 4 --red rapida --n 5 --salida docs/pruebas/rendimiento_4.15.4_antes.json
Solo medianas con N ≥ 5; con menos repeticiones se informan los valores crudos. No es una prueba en un teléfono real: las cifras absolutas serán otras, la comparación relativa es la que importa."""
import argparse
import json
import os
import statistics
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from playwright.sync_api import sync_playwright  # noqa: E402
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--cpu', type=float, default=4)
ap.add_argument('--red', default='rapida', choices=['rapida', 'lenta'])
ap.add_argument('--n', type=int, default=5)
ap.add_argument('--viajes', type=int, default=5)
ap.add_argument('--salida', default=None)
args = ap.parse_args()
MOVIL = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)

OBS = """
window.__m = { lcp: 0, fcp: 0, largas: [], cls: 0, listo: 0 };
new PerformanceObserver(l => { for (const e of l.getEntries()) window.__m.lcp = Math.max(window.__m.lcp, e.startTime); }).observe({ type: 'largest-contentful-paint', buffered: true });
new PerformanceObserver(l => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__m.fcp = e.startTime; }).observe({ type: 'paint', buffered: true });
new PerformanceObserver(l => { for (const e of l.getEntries()) window.__m.largas.push([Math.round(e.startTime), Math.round(e.duration)]); }).observe({ type: 'longtask', buffered: true });
new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__m.cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
window.addEventListener('spevb-planner-listo', () => { window.__m.listo = performance.now(); });
"""

# Contadores de recursos ACTIVOS (solo en la corrida instrumentada)
CONTADORES = """
(() => {
  const act = new WeakMap(); let total = 0;
  const add = EventTarget.prototype.addEventListener, rem = EventTarget.prototype.removeEventListener;
  const cap = (o) => (typeof o === 'object' && o ? !!o.capture : !!o);
  EventTarget.prototype.addEventListener = function (t, f, o) { if (f) { let m = act.get(this); if (!m) act.set(this, m = new Map()); const k = t + '|' + cap(o); let s = m.get(f); if (!s) m.set(f, s = new Set()); if (!s.has(k)) { s.add(k); total++; } } return add.call(this, t, f, o); };
  EventTarget.prototype.removeEventListener = function (t, f, o) { const m = act.get(this), s = m && m.get(f), k = t + '|' + cap(o); if (s && s.delete(k)) total--; return rem.call(this, t, f, o); };
  const iv = new Set(), to = new Set();
  const si = window.setInterval, ci = window.clearInterval, st = window.setTimeout, ct = window.clearTimeout;
  window.setInterval = (f, ms, ...a) => { const id = si(f, ms, ...a); iv.add(id); return id; };
  window.clearInterval = (id) => { iv.delete(id); return ci(id); };
  window.setTimeout = (f, ms, ...a) => { let id; id = st((...x) => { to.delete(id); return typeof f === 'function' ? f(...x) : undefined; }, ms, ...a); to.add(id); return id; };
  window.clearTimeout = (id) => { to.delete(id); return ct(id); };
  const MO = window.MutationObserver, vivos = new Set();
  window.MutationObserver = class extends MO { constructor(cb) { super(cb); this._o = 0; vivos.add(this); }
      observe(...a) { this._o++; return super.observe(...a); } disconnect() { this._o = 0; vivos.delete(this); return super.disconnect(); } };
  window.__perf = { snap: () => ({ oyentes: total, intervalos: iv.size, temporizadores: to.size, observadores: [...vivos].filter((o) => o._o > 0).length, nodos: document.getElementsByTagName('*').length }) };
})();
"""

# Registro de cuadros (rAF) y tareas largas durante una interacción
CUADROS = """
window.__cuadros = { dts: [], largas: [], activo: false };
(() => { let ultimo = 0; const f = (t) => { if (window.__cuadros.activo && ultimo) window.__cuadros.dts.push(t - ultimo); ultimo = t; requestAnimationFrame(f); }; requestAnimationFrame(f); })();
new PerformanceObserver(l => { for (const e of l.getEntries()) if (window.__cuadros.activo) window.__cuadros.largas.push(Math.round(e.duration)); }).observe({ type: 'longtask' });
"""


def mediana(v):
    v = [x for x in v if x is not None]
    return round(statistics.median(v), 1) if v else None


def resumen(vals):
    vals = [x for x in vals if x is not None]
    if not vals:
        return None
    return {'mediana': mediana(vals), 'min': round(min(vals), 1), 'max': round(max(vals), 1), 'n': len(vals)}


def sesion(nav, instrumentada=False, cpu=None, cache=True):
    s = V.sesion(nav, **MOVIL)
    s.ctx.add_init_script(OBS)
    s.ctx.add_init_script(CUADROS)
    if instrumentada:
        s.ctx.add_init_script(CONTADORES)
    cdp = s.ctx.new_cdp_session(s.page)
    cdp.send('Network.enable')
    cdp.send('Network.setCacheDisabled', {'cacheDisabled': not cache})
    c = args.cpu if cpu is None else cpu
    if c > 1:
        cdp.send('Emulation.setCPUThrottlingRate', {'rate': c})
    if args.red == 'lenta':
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 150, 'downloadThroughput': 1.6 * 1024 * 1024 / 8, 'uploadThroughput': 750 * 1024 / 8})
    s.cdp = cdp
    return s


def cargar(s, espera=2500):
    p = s.page
    p.goto(B.URL, wait_until='load')
    p.wait_for_timeout(espera)
    return p


def lectura_carga(p):
    m = p.evaluate("""() => { const n = performance.getEntriesByType('navigation')[0], rs = performance.getEntriesByType('resource');
        const js = rs.filter(r => r.name.endsWith('.js')), css = rs.filter(r => r.name.endsWith('.css'));
        return { dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd), fcp: Math.round(window.__m.fcp), lcp: Math.round(window.__m.lcp), listo: Math.round(window.__m.listo),
                 cls: +window.__m.cls.toFixed(4), largas: window.__m.largas.length, largas_ms: window.__m.largas.reduce((a, d) => a + d[1], 0), peor_larga: Math.max(0, ...window.__m.largas.map(d => d[1])),
                 solicitudes: rs.length + 1, js_n: js.length, css_n: css.length, bytes_js_red: js.reduce((a, r) => a + r.transferSize, 0), bytes_css_red: css.reduce((a, r) => a + r.transferSize, 0),
                 bytes_js_dec: js.reduce((a, r) => a + r.decodedBodySize, 0), bytes_css_dec: css.reduce((a, r) => a + r.decodedBodySize, 0), nodos: document.getElementsByTagName('*').length }; }""")
    return m


def planear(p):
    V.planear(p)
    V.destino_lejos(p)
    return V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})


def cuadros_resultado(p):
    r = p.evaluate("""() => { const c = window.__cuadros; c.activo = false; const d = c.dts.slice().sort((a, b) => a - b); const tot = c.dts.reduce((a, x) => a + x, 0);
        return { cuadros: c.dts.length, fps: tot ? +(1000 * c.dts.length / tot).toFixed(1) : 0, dt_mediana: d.length ? +d[Math.floor(d.length / 2)].toFixed(1) : 0, dt_p95: d.length ? +d[Math.floor(d.length * 0.95)].toFixed(1) : 0,
                 dt_max: d.length ? +d[d.length - 1].toFixed(1) : 0, lentos_mas_de_50ms: d.filter(x => x > 50).length, largas: c.largas.length, largas_ms: c.largas.reduce((a, x) => a + x, 0) }; }""")
    return r


def arrastrar_asa(s, dy, pasos=14):
    """Arrastre táctil REAL (CDP) del asa del panel inferior: dedo abajo, movimientos cada ≈ 16 ms, dedo arriba."""
    r = s.page.evaluate("(() => { const b = document.getElementById('sheetHandle').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()")
    x, y0 = r
    s.cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y0, 'id': 1}]})
    for i in range(1, pasos + 1):
        s.cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y0 + dy * i / pasos, 'id': 1}]})
        s.page.wait_for_timeout(16)
    s.cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})


def snap(p):
    return p.evaluate('window.__perf.snap()')


def heap(s):
    s.cdp.send('HeapProfiler.collectGarbage')
    return s.cdp.send('Runtime.getHeapUsage')['usedSize']


def main():
    URL = B.URL
    salida = {'url': URL, 'cpu': args.cpu, 'red': args.red, 'n': args.n, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'navegador': None}
    with sync_playwright() as pw:
        nav = B.navegador(pw)
        salida['navegador'] = nav.version
        # ---------------------------------------------------------------- carga en frío y recarga con caché
        frio, caliente = [], []
        for _ in range(args.n):
            s = sesion(nav, cache=False)
            p = cargar(s)
            frio.append(lectura_carga(p))
            s.cdp.send('Network.setCacheDisabled', {'cacheDisabled': False})
            p.reload(wait_until='load'); p.wait_for_timeout(2500)
            caliente.append(lectura_carga(p))
            s.cerrar()
        claves = [k for k in frio[0]]
        salida['carga_frio'] = {k: resumen([f[k] for f in frio]) for k in claves}
        salida['carga_recarga_con_cache'] = {k: resumen([f[k] for f in caliente]) for k in claves}

        # ---------------------------------------------------------------- teclado → sugerencia, buscar → recomendación, iniciar → tarjeta y marcador
        tecla, buscar, iniciar, fluido_panel, fluido_marcador = [], [], [], [], []
        for _ in range(args.n):
            s = sesion(nav)
            p = cargar(s, 1500)
            p.evaluate("""() => { window.__sug = null; document.addEventListener('input', () => { window.__ultimaTecla = performance.now(); }, true);
                const o = new MutationObserver(() => { if (window.__sug === null && document.querySelector('#originResults .autosuggest-option')) window.__sug = performance.now() - window.__ultimaTecla; });
                o.observe(document.getElementById('originResults'), { childList: true, subtree: true }); }""")
            p.click('#tripOrigin')
            p.keyboard.type('goo carrera 22', delay=40)
            B.esperar(p, 'window.__sug !== null', 8000)
            tecla.append(round(p.evaluate('window.__sug'), 1))
            p.fill('#tripOrigin', '')
            ls = planear(p)
            p.reload(wait_until='load'); p.wait_for_timeout(1500)
            p.evaluate("window.__cuadros.activo = false")
            # buscar → recomendación
            p.fill('#tripOrigin', V.ESC['multi']); p.keyboard.press('Enter'); p.wait_for_timeout(700)
            p.fill('#tripDestination', V.DEST); p.keyboard.press('Enter'); p.wait_for_timeout(700)
            t = p.evaluate("""() => new Promise((res) => { const t0 = performance.now();
                const f = () => { if (document.querySelector('#tripResults .trip-option') && !document.getElementById('startTripBar').hidden) res(performance.now() - t0); else requestAnimationFrame(f); };
                document.getElementById('planTrip').click(); requestAnimationFrame(f); })""")
            buscar.append(round(t, 1))
            p.wait_for_timeout(800)
            V.destino_lejos(p)
            ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
            # fluidez al arrastrar el panel (planificando)
            p.evaluate("window.__cuadros.dts = []; window.__cuadros.largas = []; window.__cuadros.activo = true")
            for _ in range(3):
                arrastrar_asa(s, -220)
                p.wait_for_timeout(300)
                arrastrar_asa(s, 220)
                p.wait_for_timeout(300)
            fluido_panel.append(cuadros_resultado(p))
            # iniciar → tarjeta y marcador
            t = p.evaluate("""([l]) => new Promise((res) => { const t0 = performance.now();
                const f = () => { const c = document.getElementById('viajeCard'); if (!c.hidden && document.querySelector('.viaje-yo-caja, .viaje-yo')) res(performance.now() - t0); else requestAnimationFrame(f); };
                document.getElementById('startTrip').click(); setTimeout(() => window.__geo.emitir(l), 30); requestAnimationFrame(f); })""", [ls[0]])
            iniciar.append(round(t, 1))
            # fluidez del marcador con GPS a 10 Hz
            p.wait_for_timeout(500)
            p.evaluate("window.__cuadros.dts = []; window.__cuadros.largas = []; window.__cuadros.activo = true")
            p.evaluate("""async ([ls]) => { for (let i = 0; i < 120; i++) { window.__geo.emitir(ls[Math.min(ls.length - 1, 10 + i * 3)]); await new Promise((r) => setTimeout(r, 100)); } }""", [ls])
            fluido_marcador.append(cuadros_resultado(p))
            s.cerrar()
        salida['tecla_a_sugerencia_ms'] = resumen(tecla)
        salida['buscar_a_recomendacion_ms'] = resumen(buscar)
        salida['iniciar_a_tarjeta_y_marcador_ms'] = resumen(iniciar)
        for nombre, lista in (('fluidez_arrastrar_panel', fluido_panel), ('fluidez_marcador_gps_10hz', fluido_marcador)):
            salida[nombre] = {k: resumen([x[k] for x in lista]) for k in lista[0]}

        # ---------------------------------------------------------------- recursos activos y memoria en varios viajes seguidos (corrida INSTRUMENTADA)
        s = sesion(nav, instrumentada=True, cpu=1)
        p = cargar(s, 3500)
        recursos = {'inicio_inactivo': snap(p)}
        ls = planear(p)
        p.wait_for_timeout(800)
        recursos['planificando'] = snap(p)
        memoria = []
        for i in range(args.viajes):
            V.iniciar(p)
            V.alimentar(p, ls, 0, 'fase:caminar')
            if i == 0:
                recursos['en_viaje'] = snap(p)
            p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(500)
            if i == 0:
                recursos['tras_terminar_el_primer_viaje'] = snap(p)
            memoria.append({'viaje': i + 1, 'heap_bytes': heap(s), **snap(p), 'escuchas_gps': p.evaluate('window.__geo.escuchas')})
        recursos[f'tras_{args.viajes}_viajes'] = snap(p)
        salida['recursos_activos'] = recursos
        salida['memoria_por_viaje'] = memoria
        s.cerrar()
        nav.close()
    if args.salida:
        os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)
        with open(args.salida, 'w', encoding='utf-8') as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
    print(json.dumps(salida, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
