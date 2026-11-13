"""Pruebas de navegador de la SALUD DEL MAPA (4.15.2): los avisos «El mapa se ve incompleto…», «Recuperar mapa» y «Sin ubicación actual» solo existen DENTRO de un viaje.

Fuera del viaje (escribiendo, comparando rutas, tutorial) la salud se registra pero no hay barra #estadosPagina, ni banner, ni reintentos, ni temporizadores. Con un viaje en curso el aviso va dentro de la
tarjeta (#viajeEstados), con «Recuperar mapa» limitado e idempotente; al terminar desaparece todo; una alerta de bajada siempre tiene prioridad visual.
La degradación del mapa se SIMULA con Spevb.MapaSalud.problema() y un doble de map.recuperar() (el comportamiento real de los adaptadores se prueba en continuidad414_e2e.py con el SDK simulado).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/salud_mapa_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
MOVIL = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
# doble de map.recuperar(): cuenta las llamadas y responde lo que diga window.__recuperar (true = el mapa volvió a dibujar)
DOBLE_RECUPERAR = """() => { window.__recup = []; window.__recuperar = true; const m = Spevb.maps.map; m.recuperar = async (nivel) => { window.__recup.push(nivel); await new Promise((r) => setTimeout(r, 120)); return window.__recuperar; }; }"""


def prueba(f):
    PRUEBAS.append(f)
    return f


def abrir(nav, **opts):
    s = V.sesion(nav, **{**MOVIL, **opts})
    p = s.abrir()
    p.evaluate(DOBLE_RECUPERAR)
    return s, p


def visibles(p):
    """Avisos de estado que la persona VE (en cualquier sitio de la página)."""
    return p.evaluate("[...document.querySelectorAll('.estado-pildora')].filter(e => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden').map(e => e.dataset.tipo)")


def sin_barra_ni_avisos(p, que):
    assert p.evaluate("document.getElementById('estadosPagina') === null"), f'{que}: la barra flotante #estadosPagina ni siquiera existe'
    assert not [t for t in visibles(p) if t in ('mapa', 'ubicacion')], f'{que}: ningún aviso del mapa ni de la ubicación'
    assert p.evaluate("!document.body.textContent.includes('El mapa se ve incompleto') || [...document.querySelectorAll('.estado-pildora')].length === 0"), f'{que}: ningún texto de continuidad de viaje'
    e = p.evaluate('Spevb.MapaSalud.estado()')
    assert not e['temporizador'] and e['visibles'] == [], f'{que}: sin temporizadores ni avisos en cola: {e}'
    assert p.evaluate('window.__recup.length') == 0, f'{que}: nadie intentó recuperar el mapa'
    assert p.evaluate('Spevb.MapaSalud.registro().filter(r => r.m === "intento").length') == 0, f'{que}: sin reintentos'


def en_viaje(nav, **opts):
    s, p = abrir(nav, **opts)
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    return s, p, ls


# ===================================================================================================================== fuera del viaje
@prueba
def mapa_degradado_mientras_se_escribe_el_destino_no_muestra_ningun_aviso(nav):
    s, p = abrir(nav)
    arriba = p.evaluate("document.getElementById('sheet').getBoundingClientRect().top")
    p.fill('#tripDestination', 'Terminal de transporte')
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    p.wait_for_timeout(2600)       # más que la primera espera automática (2 s) que había antes
    sin_barra_ni_avisos(p, 'escribiendo el destino')
    assert p.input_value('#tripDestination') == 'Terminal de transporte' and p.evaluate("document.activeElement.id") == 'tripDestination', 'no se interrumpe lo que se escribe'
    assert abs(p.evaluate("document.getElementById('sheet').getBoundingClientRect().top") - arriba) <= 1, 'la interfaz no se desplaza'
    assert p.evaluate("Spevb.MapaSalud.estado().problema") == 'tiles', 'la salud sí se registra internamente'
    s.limpio('escribiendo'); s.cerrar()


@prueba
def mapa_degradado_viendo_resultados_no_muestra_ningun_aviso_y_no_hay_reintentos(nav):
    s, p = abrir(nav)
    V.planear(p)
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    p.wait_for_timeout(2600)
    sin_barra_ni_avisos(p, 'resultados')
    # tampoco al elegir otra opción, abrir el menú o pedir A y B
    p.evaluate("document.getElementById('menuButton').click()"); p.wait_for_timeout(500)
    sin_barra_ni_avisos(p, 'menú')
    s.limpio('resultados'); s.cerrar()


@prueba
def volver_de_segundo_plano_fuera_del_viaje_no_abre_banners_ni_repinta(nav):
    s, p = abrir(nav)
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    p.evaluate("document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('pageshow'))")
    p.wait_for_timeout(500)
    sin_barra_ni_avisos(p, 'regreso sin viaje')
    s.limpio('segundo plano'); s.cerrar()


@prueba
def el_aviso_de_sin_internet_sigue_pudiendo_verse_fuera_del_viaje_en_una_barra_pequena(nav):
    s, p = abrir(nav)
    p.evaluate("Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false }); window.dispatchEvent(new Event('offline'))")
    p.wait_for_timeout(300)
    assert visibles(p) == ['internet'] and p.evaluate("!!document.getElementById('estadosPagina')")
    p.evaluate("Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => true }); window.dispatchEvent(new Event('online'))")
    p.wait_for_timeout(300)
    assert visibles(p) == [] and p.evaluate("document.getElementById('estadosPagina') === null"), 'al volver internet la barra desaparece del todo'
    s.limpio('internet'); s.cerrar()


# ===================================================================================================================== dentro del viaje
@prueba
def al_iniciar_el_viaje_con_el_problema_vigente_aparece_dentro_de_la_tarjeta(nav):
    s, p, ls = en_viaje(nav)
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    p.wait_for_timeout(300)
    assert visibles(p) == [], 'antes del viaje no se ve nada'
    V.iniciar(p)
    B.esperar(p, "!!document.querySelector('#viajeEstados .estado-pildora.mapa-incompleto')", 4000)
    r = p.evaluate("""() => { const e = document.querySelector('#viajeEstados .estado-pildora.mapa-incompleto'); const t = e.querySelector('.estado-texto').textContent;
        return { dentro: !!e.closest('#viajeCard'), texto: t, boton: e.querySelector('.estado-accion') ? e.querySelector('.estado-accion').textContent : null, barra: document.getElementById('estadosPagina') === null, visible: e.getClientRects().length > 0 }; }""")
    assert r['dentro'] and r['barra'] and r['visible'] and 'El mapa se ve incompleto' in r['texto'] and 'siguen funcionando' in r['texto'] and r['boton'] == 'Recuperar mapa', r
    assert p.evaluate('Spevb.Viaje.activo()') and p.evaluate('window.__geo.escuchas') == 1, 'las indicaciones y el GPS siguen activos'
    V.alimentar(p, ls, 0, 'fase:caminar')
    assert V.card(p)['fase'] == 'caminar', 'el viaje avanza con normalidad'
    s.limpio('aviso en tarjeta'); s.cerrar()


@prueba
def recuperar_con_exito_quita_el_aviso_y_no_toca_el_viaje(nav):
    s, p, ls = en_viaje(nav)
    V.iniciar(p)
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    B.esperar(p, "!!document.querySelector('#viajeEstados .estado-accion')", 3000)
    p.evaluate("window.__recuperar = true")
    p.click('#viajeEstados .estado-accion'); p.wait_for_timeout(700)
    assert visibles(p) == [] and p.evaluate('Spevb.MapaSalud.estado().problema') is None, 'recuperado: desaparece'
    assert p.evaluate('Spevb.Viaje.activo()') and p.evaluate('window.__geo.escuchas') == 1
    s.limpio('recuperar bien'); s.cerrar()


@prueba
def recuperacion_fallida_conserva_el_viaje_y_limita_los_intentos(nav):
    s, p, ls = en_viaje(nav)
    V.iniciar(p)
    id0 = p.evaluate('Spevb.Viaje.id()')
    p.evaluate("window.__recuperar = false; Spevb.MapaSalud.problema('tiles')")
    B.esperar(p, "!!document.querySelector('#viajeEstados .estado-accion')", 3000)
    p.evaluate("Spevb.MapaSalud.detener = Spevb.MapaSalud.detener")      # (sin efecto) el temporizador automático se deja correr tal cual
    p.click('#viajeEstados .estado-accion'); p.wait_for_timeout(900)
    t = p.inner_text('#viajeEstados .estado-texto')
    assert 'No pude recuperar el mapa' in t, t
    intentos = p.evaluate('Spevb.MapaSalud.registro().filter(r => r.m === "intento").length')
    llamadas = p.evaluate('window.__recup.length')
    # toques repetidos e inmediatos NO apilan intentos
    for _ in range(3):
        p.evaluate("document.querySelector('#viajeEstados .estado-accion').click()")
    p.wait_for_timeout(700)
    assert p.evaluate('window.__recup.length') == llamadas, 'idempotente: tres toques seguidos no crean más intentos'
    # y sin tocar nada no hay más: sin bucles
    p.wait_for_timeout(9000)
    assert p.evaluate('Spevb.MapaSalud.registro().filter(r => r.m === "intento").length') == intentos and p.evaluate('window.__recup.length') == llamadas, 'sin bucles tras fallar'
    assert p.evaluate('Spevb.Viaje.activo()') and p.evaluate('Spevb.Viaje.id()') == id0 and p.evaluate('window.__geo.escuchas') == 1, 'el viaje no se reinició ni se borró'
    assert p.evaluate("!!localStorage.getItem('spevb-viaje-curso')"), 'el viaje guardado sigue ahí'
    s.limpio('recuperar mal'); s.cerrar()


@prueba
def terminar_el_viaje_quita_el_aviso_cancela_los_reintentos_y_no_deja_temporizadores(nav):
    s, p, ls = en_viaje(nav)
    V.iniciar(p)
    p.evaluate("window.__recuperar = false; Spevb.MapaSalud.problema('tiles')")
    B.esperar(p, "!!document.querySelector('#viajeEstados .estado-pildora')", 3000)
    assert p.evaluate('Spevb.MapaSalud.estado().temporizador'), 'hay un reintento programado'
    p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(300)
    assert visibles(p) == [] and p.evaluate("document.getElementById('estadosPagina') === null"), 'desaparece de inmediato'
    e = p.evaluate('Spevb.MapaSalud.estado()')
    assert not e['temporizador'] and not e['recuperando'] and e['visibles'] == [], e
    antes = p.evaluate('window.__recup.length')
    p.wait_for_timeout(6500)
    assert p.evaluate('window.__recup.length') == antes and visibles(p) == [], 'ningún reintento tardío'
    s.limpio('terminar'); s.cerrar()


@prueba
def reanudar_un_viaje_con_el_mapa_degradado_muestra_el_aviso_en_la_tarjeta(nav):
    s, p, ls = en_viaje(nav)
    V.iniciar(p)
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.evaluate("window.dispatchEvent(new Event('pagehide'))")
    p.reload(wait_until='domcontentloaded')
    B.esperar(p, "!!(window.Spevb && Spevb.Viaje && Spevb.maps && Spevb.maps.map)", 20000)
    p.wait_for_timeout(1000)
    p.evaluate(DOBLE_RECUPERAR)
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    p.wait_for_timeout(400)
    assert p.evaluate("Spevb.Viaje.pendiente()") and visibles(p) == [] and p.evaluate("document.getElementById('estadosPagina') === null"), 'con la pregunta de reanudar aún no hay viaje: no se ve el aviso'
    p.click('#viajeSi'); p.wait_for_timeout(900)
    assert p.evaluate('Spevb.Viaje.activo()')
    r = p.evaluate("(() => { const e = document.querySelector('#viajeEstados .estado-pildora.mapa-incompleto'); return { dentro: !!e && !!e.closest('#viajeCard'), barra: document.getElementById('estadosPagina') === null }; })()")
    assert r['dentro'] and r['barra'], r
    s.limpio('reanudar degradado'); s.cerrar()


@prueba
def una_alerta_de_bajada_siempre_tiene_prioridad_visual_sobre_la_salud_del_mapa(nav):
    s, p, ls = en_viaje(nav)
    V.iniciar(p)
    p.evaluate("Spevb.MapaSalud.problema('tiles')")
    B.esperar(p, "!!document.querySelector('#viajeEstados .estado-pildora')", 3000)
    i = V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    V.alimentar(p, ls, i, 'bajada')
    r = p.evaluate("""() => { const caja = document.getElementById('viajeBajada'), ya = document.getElementById('viajeBajadaYa').getBoundingClientRect(), est = document.getElementById('viajeEstados');
        const el = document.elementFromPoint(ya.left + ya.width / 2, ya.top + ya.height / 2);
        return { visible: !caja.hidden && caja.getClientRects().length > 0, estados: est.getClientRects().length > 0 && getComputedStyle(est).display !== 'none', recibe: !!el && !!el.closest('#viajeBajadaYa'), ps: document.querySelectorAll('.estado-pildora').length }; }""")
    assert r['visible'] and r['recibe'] and not r['estados'], f'el recuadro manda y el aviso del mapa cede: {r}'
    s.limpio('prioridad'); s.cerrar()


def correr(filtro=None):
    fallos = []
    with sync_playwright() as p:
        nav = B.navegador(p)
        for f in PRUEBAS:
            if filtro and filtro not in f.__name__:
                continue
            try:
                f(nav)
                print('OK    ', f.__name__)
            except Exception as e:  # noqa: BLE001
                fallos.append(f.__name__)
                print('FALLA ', f.__name__, '|', str(e)[:700].replace('\n', ' '))
                if os.environ.get('SEVB_E2E_TRAZA'):
                    traceback.print_exc()
        nav.close()
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas de salud del mapa (solo dentro del viaje); fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
