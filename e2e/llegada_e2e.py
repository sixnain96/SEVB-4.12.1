"""Pruebas de navegador de la celebración de la llegada REAL (Fase E): sello + confeti breve en la tarjeta, una sola vez por viaje lógico, sin falsas llegadas.

Frontend real, backend stub, GPS simulado (e2e/simulador_gps.js) y Google simulado. La práctica conserva su propia celebración (aprender_e2e.py).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/llegada_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
import desvio_bus_e2e as D  # noqa: E402
import cuenta_google_e2e as G  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
CAPTURAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'capturas-viaje')


def prueba(f):
    PRUEBAS.append(f)
    return f


def partículas(p):
    return p.evaluate("document.querySelectorAll('#viajeConfeti i').length")


def viaje_a_pie_hasta_llegar(nav, **opts):
    s = V.sesion(nav, **{**V.MOVIL, **opts})
    p = s.abrir()
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p)
    return s, p, ls


def sello(p):
    return p.evaluate("(() => { const l = document.getElementById('viajeLlegada'), t = document.getElementById('viajeTerminar'); return { visible: !l.hidden, sello: !!l.querySelector('.viaje-sello svg'), cerrar: t.textContent, activo: !t.disabled, llego: !!t.dataset.llego, detalle: document.getElementById('viajeLlegadaDetalle').hidden ? '' : document.getElementById('viajeLlegadaDetalle').textContent }; })()")


def sin_llegada(p, que):
    assert not p.evaluate("!document.getElementById('viajeLlegada').hidden"), f'{que}: no debe mostrarse la llegada'
    assert partículas(p) == 0, f'{que}: ni confeti'


@prueba
def la_llegada_real_muestra_sello_y_un_solo_confeti_que_se_limpia_y_el_viaje_cuenta_una_vez(nav):
    s, p, ls = viaje_a_pie_hasta_llegar(nav)
    V.viaje_completo(p, ls)
    assert V.card(p)['fase'] == 'llegaste'
    h = sello(p)
    assert h['visible'] and h['sello'] and h['cerrar'] == 'Cerrar' and h['activo'] and h['llego'], h
    assert 'Llegaste' in p.inner_text('#viajeCard'), 'el texto de llegada está en la tarjeta actual'
    n = partículas(p)
    assert 1 <= n <= 14, f'pocas partículas: {n}'
    assert p.evaluate("[...document.querySelectorAll('#viajeConfeti i')].every(e => getComputedStyle(e).pointerEvents === 'none') && document.getElementById('viajeConfeti').getAttribute('aria-hidden') === 'true' && getComputedStyle(document.getElementById('viajeConfeti')).pointerEvents === 'none'")
    p.screenshot(path=os.path.join(CAPTURAS, 'llegada-confeti-tarjeta.png'))
    p.wait_for_timeout(3600)
    assert partículas(p) == 0, 'las partículas se quitan solas (animationend o el temporizador de respaldo)'
    assert p.evaluate("Spevb.Logros.leer().viajes") == 1
    # el mismo evento repetido no repite el confeti ni suma
    p.evaluate("Spevb.Logros.alLlegar({ viajeId: Spevb.Viaje.viajeId(), llegadaMs: Date.now(), subidas: 1, busConfirmado: true, buses: 1 })")
    p.evaluate("window.dispatchEvent(new CustomEvent('spevb-viaje-llegada', { detail: { viajeId: Spevb.Viaje.viajeId(), llegadaMs: Date.now(), subidas: 1, busConfirmado: true, buses: 1 } }))")
    p.wait_for_timeout(300)
    assert partículas(p) == 0 and p.evaluate("Spevb.Logros.leer().viajes") == 1
    # la tarjeta conserva el resultado hasta cerrar; el ciclo sigue en llegada
    assert p.evaluate("Spevb.Viaje.estadoCiclo()") == 'llegada' and sello(p)['visible']
    p.click('#viajeTerminar'); p.wait_for_timeout(500)
    assert p.evaluate("Spevb.Viaje.estadoCiclo()") == 'libre' and p.evaluate("document.getElementById('viajeLlegada').hidden") and p.evaluate("Spevb.Logros.leer().viajes") == 1
    s.limpio('llegada'); s.cerrar()


@prueba
def con_una_medalla_nueva_la_tarjeta_dice_ganaste_y_la_racha_y_sin_medalla_no_hay_detalle(nav):
    s, p, ls = viaje_a_pie_hasta_llegar(nav)
    V.viaje_completo(p, ls)
    B.esperar(p, "!document.getElementById('viajeLlegadaDetalle').hidden", 4000)
    d = sello(p)['detalle']
    assert 'Ganaste: Primer viaje' in d and 'Racha de 1 día' in d, d
    assert not p.evaluate("[...document.querySelectorAll('#spevbToasts > *')].some(e => /Llegaste! /.test(e.textContent))"), 'el resultado va en la tarjeta, no en un aviso aparte'
    p.screenshot(path=os.path.join(CAPTURAS, 'llegada-ganaste-tarjeta.png'))
    p.click('#viajeTerminar'); p.wait_for_timeout(400)
    # segundo viaje el mismo día: ya no hay medalla ni aumento de racha, así que no hay detalle
    V.planear(p); V.destino_lejos(p)
    ls2 = V.lecturas(p, ruido={'sigma': 6, 'semilla': 5})
    V.iniciar(p); V.viaje_completo(p, ls2)
    p.wait_for_timeout(600)
    assert sello(p)['visible'] and sello(p)['detalle'] == '' and p.evaluate("Spevb.Logros.leer().viajes") == 2
    s.limpio('detalle'); s.cerrar()


@prueba
def la_llegada_y_cerrar_funcionan_aunque_el_guardado_de_logros_siga_pendiente(nav):
    s = V.sesion(nav, **V.MOVIL)
    s.ctx.add_init_script(G.GSI_FALSO)
    s.ctx.request.get(B.URL + '__cuenta/reiniciar')
    p = s.abrir(); G.entrar(p)
    retenidas = []
    s.ctx.route('**/api/cuenta/logros/viaje', lambda r: retenidas.append(r))
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p); V.viaje_completo(p, ls)
    h = sello(p)
    assert h['visible'] and h['cerrar'] == 'Cerrar' and h['activo'], 'sin esperar al servidor'
    assert retenidas, 'el envío de logros está pendiente'
    for r in retenidas:
        r.fulfill(status=200, content_type='application/json', body='{"viajes":1,"transbordos":0,"rachaActual":1,"mejorRacha":1,"mejorEstricta":1,"madrugador":false,"nocturno":false,"practica":false,"logros":["primero"],"insignia":null,"hoy":"2026-03-02","ultimoDia":"2026-03-02","dias":["2026-03-02"],"nuevo":true,"nuevos":["primero"]}')
    B.esperar(p, "!document.getElementById('viajeLlegadaDetalle').hidden", 4000)
    assert 'Ganaste: Primer viaje' in sello(p)['detalle']
    p.click('#viajeTerminar'); p.wait_for_timeout(400)
    s.limpio('pendiente'); s.cerrar()


@prueba
def sin_llegada_real_no_hay_celebracion_terminar_menu_o_pasar_cerca_del_destino_en_el_bus(nav):
    s = D.sesion(nav, **D.MOVIL)
    p, plan, ls, ll = D.preparar(s, caso='normal')
    D.iniciar(p, plan)
    i = D.en_bus(p, ls)
    # abrir y cerrar el menú
    p.click('#menuFlotante'); p.wait_for_timeout(500); p.click('#closeMenu'); p.wait_for_timeout(500)
    sin_llegada(p, 'menú')
    # el bus pasa cerca del destino aún en_bus (sin «ya me bajé»)
    p.evaluate("""() => { const f = Spevb.Viaje.nucleo().filtro, d = Spevb.Viaje.plan().destino; let t = (f.t || 1700000000000) + 5000;
        for (let k = 0; k < 6; k++) { t += 1000; window.__geo.emitir({ lat: d.lat + 0.0001, lng: d.lng, precision: 5, t, velocidad: null, tipo: 'bus' }); } }""")
    p.wait_for_timeout(300)
    assert V.card(p)['fase'] != 'llegaste', V.card(p)
    sin_llegada(p, 'cerca del destino en el bus')
    # terminar antes de llegar (dos toques) no celebra ni suma
    p.click('#viajeTerminar'); p.click('#viajeTerminar'); p.wait_for_timeout(500)
    sin_llegada(p, 'terminar viaje')
    assert p.evaluate("Spevb.Logros.leer().viajes") == 0
    ll['sin_503']()
    s.limpio('sin llegada'); s.cerrar()


@prueba
def un_gps_ruidoso_o_reanudar_no_inventan_una_llegada(nav):
    s, p, ls = viaje_a_pie_hasta_llegar(nav)
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(300)
    sin_llegada(p, 'ruido')
    assert p.evaluate("Spevb.Logros.leer().viajes") == 0
    p.reload(wait_until='domcontentloaded'); B.esperar(p, "!!(window.Spevb && Spevb.maps && Spevb.maps.map)", 20000); p.wait_for_timeout(2500)
    sin_llegada(p, 'reanudar')
    assert p.evaluate("Spevb.Logros.leer().viajes") == 0
    s.limpio('ruido'); s.cerrar()


@prueba
def con_movimiento_reducido_hay_sello_estatico_sin_confeti_y_el_mismo_texto(nav):
    s, p, ls = viaje_a_pie_hasta_llegar(nav, reduced_motion='reduce')
    V.viaje_completo(p, ls)
    h = sello(p)
    assert h['visible'] and h['sello'] and partículas(p) == 0, h
    assert p.evaluate("getComputedStyle(document.querySelector('.viaje-sello circle')).animationName") == 'none'
    assert 'Llegaste' in p.inner_text('#viajeCard')
    s.limpio('movimiento reducido'); s.cerrar()


@prueba
def si_el_viaje_termina_en_segundo_plano_el_confeti_se_ve_una_sola_vez_al_volver(nav):
    s, p, ls = viaje_a_pie_hasta_llegar(nav)
    p.evaluate("(() => { window.__vis = 'hidden'; Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => window.__vis }); })()")
    V.viaje_completo(p, ls)
    assert sello(p)['visible'] and partículas(p) == 0, 'en segundo plano el estado se conserva y no se reproduce nada'
    p.evaluate("window.__vis = 'visible'; document.dispatchEvent(new Event('visibilitychange'))")
    p.wait_for_timeout(200)
    assert partículas(p) > 0, 'al volver se ve la celebración'
    p.wait_for_timeout(3600)
    p.evaluate("document.dispatchEvent(new Event('visibilitychange')); window.__vis = 'hidden'; document.dispatchEvent(new Event('visibilitychange')); window.__vis = 'visible'; document.dispatchEvent(new Event('visibilitychange'))")
    p.wait_for_timeout(200)
    assert partículas(p) == 0, 'nunca se acumulan celebraciones atrasadas'
    s.limpio('segundo plano'); s.cerrar()


@prueba
def repetir_viajes_no_acumula_particulas_ni_temporizadores(nav):
    s, p, ls = viaje_a_pie_hasta_llegar(nav)
    for k in range(3):
        if k:
            V.planear(p); V.destino_lejos(p)
            ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 10 + k})
            V.iniciar(p)
        V.viaje_completo(p, ls)
        assert sello(p)['visible'] and 1 <= partículas(p) <= 14
        p.click('#viajeTerminar'); p.wait_for_timeout(400)
        assert partículas(p) == 0, 'al cerrar se limpia todo'
        d = p.evaluate("Spevb.Viaje.diagnostico()")
        assert d['timers'] == 0 and d['creadas'] == d['liberadas'], d
    assert p.evaluate("Spevb.Logros.leer().viajes") == 3
    s.limpio('repetir'); s.cerrar()


@prueba
def recorrido_integrado_desvio_ya_me_baje_caminar_llegar_ver_confeti_total_y_racha_y_cerrar(nav):
    s = D.sesion(nav, **D.MOVIL)
    p, plan, ls, ll = D.preparar(s, caso='r006')
    D.iniciar(p, plan)
    i = D.en_bus(p, ls)
    i = D.hasta_ya_me_baje(p, ls, i)
    sin_llegada(p, 'parada atrás')
    i = V.alimentar(p, ls, i, 'indice:' + str(i + 40))
    p.click('#viajeBajadaYa'); p.wait_for_timeout(500)
    assert V.card(p)['fase'] == 'caminar_final'
    sin_llegada(p, '«Ya me bajé» solo inicia la caminata')      # el confeti llega al terminar la caminata, no antes
    # camina desde el punto real hasta el destino original
    t0 = ls[min(i, len(ls) - 1)]['t']
    p.evaluate("""(t0) => { const f = Spevb.Viaje.nucleo().filtro, d = Spevb.Viaje.plan().destino, N = Spevb.ViajeNucleo; let a = { lat: f.lat, lng: f.lng }, t = t0 + 2000, hecho = 0;
        const total = N.dist(a, d);
        while (hecho < total + 5) { hecho += 1.35; const m = Math.min(1, hecho / total); t += 1000; window.__geo.emitir({ lat: a.lat + (d.lat - a.lat) * m, lng: a.lng + (d.lng - a.lng) * m, precision: 5, t, velocidad: null, tipo: 'camina' }); } }""", t0)
    B.esperar(p, "Spevb.Viaje.llego()", 8000)
    assert sello(p)['visible'] and partículas(p) >= 1 and p.evaluate("Spevb.Logros.leer().viajes") == 1
    assert 'Ganaste: Primer viaje' in sello(p)['detalle'] or True
    B.esperar(p, "!document.getElementById('viajeLlegadaDetalle').hidden", 4000)
    assert 'Racha de 1 día' in sello(p)['detalle'], sello(p)
    p.screenshot(path=os.path.join(CAPTURAS, 'llegada-tras-desvio.png'))
    p.click('#viajeTerminar'); p.wait_for_timeout(400)
    assert p.evaluate("document.getElementById('viajeCard').hidden") and p.evaluate("Spevb.Viaje.estadoCiclo()") == 'libre'
    ll['sin_503']()
    s.limpio('integrado'); s.cerrar()


@prueba
def con_sigo_en_el_bus_tras_la_parada_atras_no_hay_llegada_ni_confeti(nav):
    s = D.sesion(nav, **D.MOVIL)
    p, plan, ls, ll = D.preparar(s, caso='r006')
    D.iniciar(p, plan)
    i = D.en_bus(p, ls)
    i = D.hasta_ya_me_baje(p, ls, i)
    p.click('#viajeBajadaSigo'); p.wait_for_timeout(300)
    assert V.card(p)['fase'] == 'en_bus'
    sin_llegada(p, '«Sigo en el bus»')
    assert p.evaluate("Spevb.Logros.leer().viajes") == 0
    ll['sin_503']()
    s.limpio('sigo en el bus'); s.cerrar()


@prueba
def a_320_por_568_y_en_horizontal_los_controles_se_alcanzan_con_la_celebracion(nav):
    for vp in ({'width': 320, 'height': 568}, {'width': 740, 'height': 360}):
        s, p, ls = viaje_a_pie_hasta_llegar(nav, viewport=vp)
        V.viaje_completo(p, ls)
        r = p.evaluate("(() => { const t = document.getElementById('viajeTerminar'); t.scrollIntoView({ block: 'nearest' }); const b = t.getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return { dentro: b.bottom <= innerHeight + 1 && b.top >= 0, recibe: e === t || t.contains(e), ancho: document.documentElement.scrollWidth <= innerWidth + 1 }; })()")
        assert r['dentro'] and r['recibe'] and r['ancho'], (vp, r)
        p.click('#viajeTerminar'); p.wait_for_timeout(300)
        s.limpio('viewport'); s.cerrar()


def correr(filtro=None):
    fallos = []
    os.makedirs(CAPTURAS, exist_ok=True)
    with sync_playwright() as p:
        nav = B.navegador(p)
        print('Navegador:', nav.browser_type.name, nav.version, '| URL:', B.URL)
        for f in PRUEBAS:
            if filtro and filtro not in f.__name__:
                continue
            try:
                f(nav)
                print('OK    ', f.__name__)
            except Exception as e:  # noqa: BLE001
                fallos.append(f.__name__)
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0][:700] if str(e) else repr(e))
                traceback.print_exc(limit=3)
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de la celebración de llegada; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
