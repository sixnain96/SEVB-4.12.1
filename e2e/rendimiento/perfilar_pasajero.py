"""Perfil de CPU (CDP Profiler) de escenarios del pasajero: dice QUÉ funciones consumen el hilo principal (tiempo propio), para optimizar con datos y no con suposiciones.

Uso: SEVB_E2E_URL=http://127.0.0.1:18200/ python e2e/rendimiento/perfilar_pasajero.py carga|arrastre|iniciar|marcador [--cpu 4] [--top 14]
Escenarios: carga (arranque en frío), arrastre (arrastrar el asa del panel 3 veces), iniciar («Iniciar viaje» + primera lectura), marcador (GPS a 10 Hz durante 8 s)."""
import argparse
import collections
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
from playwright.sync_api import sync_playwright  # noqa: E402
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('escenario', choices=['carga', 'arrastre', 'iniciar', 'marcador'])
ap.add_argument('--cpu', type=float, default=4)
ap.add_argument('--top', type=int, default=14)
ap.add_argument('--padres', default=None, help='nombre de función: muestra quién la llama (cadena de 3 niveles) y cuánto tiempo propio aporta cada cadena')
args = ap.parse_args()
MOVIL = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)


def resumir(perfil, top):
    nodos = {n['id']: n for n in perfil['nodes']}
    propio = collections.Counter()
    dts = perfil['timeDeltas']
    for sid, dt in zip(perfil['samples'], dts):
        n = nodos[sid]
        cf = n['callFrame']
        clave = (cf['functionName'] or '(anónima)') + ' · ' + (cf['url'].rsplit('/', 1)[-1] or '(nativo)') + ':' + str(cf['lineNumber'] + 1)
        propio[clave] += dt
    total = sum(propio.values())
    inactivo = sum(v for k, v in propio.items() if k.startswith('(idle)') or k.startswith('(program)'))
    print(f'tiempo muestreado: {total / 1000:.0f} ms (de los cuales inactivo/programa: {inactivo / 1000:.0f} ms)')
    for k, v in propio.most_common(top):
        print(f'{v / 1000:8.1f} ms  {100 * v / total:5.1f} %  {k}')
    if args.padres:
        padre = {}
        for n in perfil['nodes']:
            for h in n.get('children', []):
                padre[h] = n['id']
        cadenas = collections.Counter()
        for sid, dt in zip(perfil['samples'], dts):
            if nodos[sid]['callFrame']['functionName'] != args.padres:
                continue
            c, partes, nivel = sid, [], 0
            while c in padre and nivel < 3:
                c = padre[c]; cf = nodos[c]['callFrame']; partes.append((cf['functionName'] or '(anónima)') + ':' + str(cf['lineNumber'] + 1)); nivel += 1
            cadenas[' ← '.join(partes)] += dt
        print(f'-- quién llama a {args.padres}:')
        for k, v in cadenas.most_common(6):
            print(f'{v / 1000:8.1f} ms  {k}')


def main():
    with sync_playwright() as pw:
        nav = B.navegador(pw)
        s = V.sesion(nav, **MOVIL)
        cdp = s.ctx.new_cdp_session(s.page)
        if args.cpu > 1:
            cdp.send('Emulation.setCPUThrottlingRate', {'rate': args.cpu})
        p = s.page
        cdp.send('Profiler.enable')
        cdp.send('Profiler.setSamplingInterval', {'interval': 200})
        if args.escenario == 'carga':
            cdp.send('Network.enable'); cdp.send('Network.setCacheDisabled', {'cacheDisabled': True})
            cdp.send('Profiler.start')
            p.goto(B.URL, wait_until='load'); p.wait_for_timeout(2500)
        else:
            s.abrir()
            V.planear(p); V.destino_lejos(p)
            ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
            p.wait_for_timeout(800)
            if args.escenario == 'arrastre':
                cdp.send('Profiler.start')
                for _ in range(3):
                    for dy in (-220, 220):
                        r = p.evaluate("(() => { const b = document.getElementById('sheetHandle').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()")
                        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': r[0], 'y': r[1], 'id': 1}]})
                        for i in range(1, 15):
                            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': r[0], 'y': r[1] + dy * i / 14, 'id': 1}]})
                            p.wait_for_timeout(16)
                        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                        p.wait_for_timeout(300)
            elif args.escenario == 'iniciar':
                cdp.send('Profiler.start')
                p.evaluate("([l]) => { document.getElementById('startTrip').click(); setTimeout(() => window.__geo.emitir(l), 30); }", [ls[0]])
                p.wait_for_timeout(1500)
            else:
                V.iniciar(p)
                p.wait_for_timeout(300)
                cdp.send('Profiler.start')
                p.evaluate("""async ([ls]) => { for (let i = 0; i < 80; i++) { window.__geo.emitir(ls[Math.min(ls.length - 1, 10 + i * 3)]); await new Promise((r) => setTimeout(r, 100)); } }""", [ls])
        perfil = cdp.send('Profiler.stop')['profile']
        resumir(perfil, args.top)
        s.cerrar(); nav.close()


if __name__ == '__main__':
    main()
