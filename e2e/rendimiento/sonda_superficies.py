"""Sonda de colisiones entre superficies móviles (mapa, panel A y B, menú ☰, tarjeta del viaje, alertas): mide, no prueba.

Para cada tamaño y estado registra: controles que NO reciben su propio toque (otra capa encima), controles esenciales fuera de la pantalla, desbordamiento horizontal
y cuánto de la pantalla queda libre para el mapa. Los «choques» de la lista son los que hay que corregir; un menú que oscurece el mapa es diseño, no un choque.
Uso: SEVB_E2E_URL=http://127.0.0.1:18090/ python e2e/rendimiento/sonda_superficies.py [prefijo_capturas] [salida.json]
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
import ux414_e2e as U  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CAP = os.path.join(os.path.dirname(os.path.dirname(AQUI)), 'docs', 'capturas-viaje')
PREFIJO = sys.argv[1] if len(sys.argv) > 1 else ''
SALIDA = sys.argv[2] if len(sys.argv) > 2 else None
TAMANOS = [(320, 568), (360, 640), (390, 844), (430, 932), (740, 360)]
if os.environ.get('SONDA_TAMANOS'):
    TAMANOS = [tuple(int(v) for v in t.split('x')) for t in os.environ['SONDA_TAMANOS'].split(',')]
SIN_CAPTURA = os.environ.get('SONDA_SIN_CAPTURAS') == '1'

JS = r"""(esenciales) => {
  const vw = innerWidth, vh = innerHeight;
  const vis = (e) => { const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false; const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return false; for (let n = e; n; n = n.parentElement) { if (n.hidden) return false; } return true; };
  const menuAbierto = document.getElementById('sideMenu').classList.contains('open');
  const modal = document.querySelector('.modal-backdrop:not([hidden])');
  const urgente = document.querySelector('#viajeCard[data-urgente]');
  // Solo cuentan los controles de la superficie operable: con el menú o un diálogo abiertos lo de abajo queda inerte A PROPÓSITO (salvo la alerta urgente, que es la excepción).
  const sels = modal ? ['.modal-backdrop:not([hidden]) button, .modal-backdrop:not([hidden]) input']
    : menuAbierto ? ['#sideMenu.open button', '#sideMenu.open summary', '#sideMenu.open a', '#sideMenu.open input', '#sideMenu.open select'].concat(urgente ? ['#viajeCard button'] : [])
    : ['#viajeCard button', '#viajeBajada button', '#sheet button', '#sheet input', '.map-fabs button', '#menuFlotante', '#menuButton', '#panelShow', '#panelHide'];
  const todos = new Set(); sels.forEach((s) => document.querySelectorAll(s).forEach((e) => todos.add(e)));
  const bloqueados = [], fuera = [], pequenos = [];
  const nombre = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '')) + (e.textContent ? '«' + e.textContent.trim().slice(0, 18).replace(/\s+/g, ' ') + '»' : '');
  const scrollPadre = (e) => { for (let n = e.parentElement; n; n = n.parentElement) { const o = getComputedStyle(n).overflowY; if ((o === 'auto' || o === 'scroll') && n.scrollHeight > n.clientHeight + 1) return n; } return null; };
  todos.forEach((e) => {
    if (!vis(e)) return;
    const r = e.getBoundingClientRect();
    const dentro = r.left >= -1 && r.right <= vw + 1 && r.top >= -1 && r.bottom <= vh + 1;
    if (!dentro) { if (!scrollPadre(e)) fuera.push(nombre(e)); return; }
    const x = Math.min(vw - 1, Math.max(0, r.left + r.width / 2)), y = Math.min(vh - 1, Math.max(0, r.top + r.height / 2));
    const hit = document.elementFromPoint(x, y);
    const sp = scrollPadre(e);
    const tapaPropia = sp && hit && sp.contains(hit);      // dentro de una zona con scroll, la cabecera fija puede cubrir una fila: se desplaza, no es un choque
    if (!hit || !(e === hit || e.contains(hit) || hit.contains(e) || tapaPropia)) bloqueados.push(nombre(e) + ' ← ' + (hit ? nombre(hit) : 'nada'));
    else if ((r.width < 40 || r.height < 40) && !e.matches('summary,a,input[type=checkbox]')) pequenos.push(nombre(e) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  });
  const faltan = esenciales.filter((s) => { const e = document.querySelector(s); if (!e || !vis(e)) return true; const r = e.getBoundingClientRect(); return !(r.left >= -1 && r.right <= vw + 1 && r.top >= -1 && r.bottom <= vh + 1); });
  const cubierto = (() => { let abajo = 0, arriba = 0; for (const s of ['#viajeCard', '#sheet']) { const e = document.querySelector(s); if (e && vis(e)) { const r = e.getBoundingClientRect(); if (r.top > vh / 2) abajo = Math.max(abajo, vh - r.top); else arriba = Math.max(arriba, r.bottom); } } return Math.round((abajo + arriba) / vh * 100); })();
  return { desborde: document.documentElement.scrollWidth - vw, bloqueados, fuera, pequenos, faltan, cubierto_pct: cubierto };
}"""


def medir(p, esenciales=()):
    return p.evaluate(JS, list(esenciales))


def sesion(nav, w, h, letra=None):
    s = U.movil(nav, w, h)
    p = s.abrir()
    if letra:
        p.evaluate("document.documentElement.dataset.letra = %r" % letra); p.wait_for_timeout(300)
    return s, p


def abrir_menu(p):
    p.click('#menuButton' if p.is_visible('#menuButton') else '#menuFlotante'); p.wait_for_timeout(600)


def cerrar_menu(p):
    if p.evaluate("document.getElementById('sideMenu').classList.contains('open')"):
        p.keyboard.press('Escape'); p.wait_for_timeout(500)


def captura(p, nombre):
    if SIN_CAPTURA or not PREFIJO:
        return
    os.makedirs(CAP, exist_ok=True)
    p.screenshot(path=os.path.join(CAP, f'{PREFIJO}-{nombre}.png'))


def correr():
    res = []

    def reg(w, h, letra, estado, p, esenciales=()):
        r = medir(p, esenciales); r.update({'w': w, 'h': h, 'letra': letra or 'normal', 'estado': estado})
        res.append(r)
        malo = r['desborde'] > 0 or r['bloqueados'] or r['fuera'] or r['faltan']
        print(('CHOQUE ' if malo else 'ok     ') + f'{w}x{h} {letra or "normal"} {estado}: ' + json.dumps({k: v for k, v in r.items() if k in ('desborde', 'bloqueados', 'fuera', 'faltan', 'cubierto_pct') and v}, ensure_ascii=False)[:420])

    with sync_playwright() as pw:
        nav = B.navegador(pw)
        for w, h in TAMANOS:
            for letra in (None, 'enorme'):
                if letra and (w, h) not in ((320, 568), (360, 640), (740, 360)):
                    continue
                # --- planificación
                s, p = sesion(nav, w, h, letra)
                reg(w, h, letra, 'planificando', p, ['#planTrip'] if h > 400 else [])
                if h > 400:
                    p.evaluate("document.getElementById('tripOrigin').focus()")
                    p.set_viewport_size({'width': w, 'height': max(300, h - 280)}); p.wait_for_timeout(500)
                    reg(w, h, letra, 'planificando con teclado (alto reducido)', p, ['#tripOrigin'])
                    p.set_viewport_size({'width': w, 'height': h}); p.wait_for_timeout(400)
                    p.evaluate("document.activeElement.blur()")
                # --- menú en planificación
                abrir_menu(p)
                reg(w, h, letra, 'menú abierto (planificando)', p, ['#closeMenu'])
                if not letra:
                    captura(p, f'menu-planificando-{w}x{h}')
                p.evaluate("document.getElementById('sideMenu').scrollTop = 99999"); p.wait_for_timeout(200)
                reg(w, h, letra, 'menú abierto, al final del scroll', p, ['#closeMenu'])
                cerrar_menu(p)
                s.cerrar()
                # --- viaje
                s, p = sesion(nav, w, h, letra)
                V.planear(p); V.destino_lejos(p)
                ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
                V.iniciar(p); i = V.alimentar(p, ls, 0, 'fase:esperando'); p.wait_for_timeout(400)
                reg(w, h, letra, 'viaje activo', p, ['#viajeCard'])
                if not letra:
                    captura(p, f'viaje-{w}x{h}')
                # menú durante el viaje
                abrir_menu(p)
                reg(w, h, letra, 'viaje + menú', p, ['#closeMenu', '#menuVolverViaje'])
                if not letra:
                    captura(p, f'viaje-menu-{w}x{h}')
                p.evaluate("document.getElementById('sideMenu').scrollTop = 99999"); p.wait_for_timeout(200)
                reg(w, h, letra, 'viaje + menú, final del scroll', p, ['#closeMenu'])
                p.evaluate("document.getElementById('sideMenu').scrollTop = 0")
                # alerta con el menú abierto (se responde TOCANDO: Escape también la descarta)
                try:
                    V.alimentar(p, ls, i, 'pregunta'); p.wait_for_timeout(400)
                    reg(w, h, letra, 'viaje + menú + pregunta urgente', p, ['#viajeSi'])
                    if not letra:
                        captura(p, f'viaje-menu-alerta-{w}x{h}')
                    p.click('#viajeSi', timeout=3000); p.wait_for_timeout(400)
                except Exception as e:  # noqa: BLE001
                    print('  (no se pudo responder la pregunta con el menú abierto)', str(e).splitlines()[0][:100])
                cerrar_menu(p)
                try:
                    p.evaluate("document.getElementById('closeMenu').click()") if p.evaluate("document.getElementById('sideMenu').classList.contains('open')") else None
                except Exception:  # noqa: BLE001
                    pass
                p.wait_for_timeout(400)
                reg(w, h, letra, 'viaje (tras responder y cerrar el menú)', p, ['#viajeCard'])
                # planificador traído durante el viaje
                if p.is_visible('#panelShow'):
                    try:
                        p.click('#panelShow', timeout=3000)
                    except Exception as e:  # noqa: BLE001
                        print('  (no se pudo abrir Editar A y B)', str(e).splitlines()[0][:100]); s.cerrar(); continue
                    p.wait_for_timeout(700)
                    reg(w, h, letra, 'viaje + planificador (Editar A y B)', p, ['#panelHide'])
                    if not letra:
                        captura(p, f'viaje-editar-ab-{w}x{h}')
                    if h > 400:
                        p.evaluate("document.getElementById('tripOrigin').focus()")
                        p.set_viewport_size({'width': w, 'height': max(300, h - 280)}); p.wait_for_timeout(500)
                        reg(w, h, letra, 'viaje + planificador + teclado', p, ['#tripOrigin'])
                else:
                    print('  (sin botón Editar A y B visible)', w, h)
                s.cerrar()
        nav.close()
    if SALIDA:
        json.dump(res, open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    malos = [r for r in res if r['desborde'] > 0 or r['bloqueados'] or r['fuera'] or r['faltan']]
    print(f'\n{len(res)} casos medidos; con choque: {len(malos)}')


if __name__ == '__main__':
    correr()
