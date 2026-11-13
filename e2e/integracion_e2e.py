"""Recorrido INTEGRADO del pasajero (auditoría 4.15.x): un viaje completo en la misma sesión que ejercita juntas las piezas que las demás suites prueban por separado.

Flujo guiado (destino → origen → revisión → recomendación) → «Empezar este viaje» → un segundo inicio es bloqueado (diálogo) → círculo → bus con código → «Compartir mi viaje» → alertas
`cerca`, `preparate` y `ahora` (una vez cada una) con la salud del mapa degradada (visible solo dentro del viaje; el recuadro de bajada manda) → «Ya me bajé» → llegada (sigue bloqueando
hasta «Cerrar», el enlace compartido se revoca) → cierre completo (sin GPS, capas, temporizadores ni estado guardado) → se puede planear de nuevo.
Se corre con y sin movimiento reducido. GPS, red y Google SIMULADOS; no prueba un teléfono real.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/integracion_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
import compartir_e2e as C  # noqa: E402
import guiado_e2e as G  # noqa: E402
import marcador_alertas_e2e as M  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []


def prueba(f):
    PRUEBAS.append(f)
    return f


def recorrido(nav, reducido):
    extra = {'reduced_motion': 'reduce'} if reducido else {}
    s = M.sesion(nav, guiado=True, **extra)
    p = s.abrir()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.evaluate("fetch('/__log/limpiar')")
    # 1 · flujo guiado hasta la recomendación (la búsqueda del pasajero es Google: el stub solo recibe la API propia)
    G.hasta_recomendacion(p)
    assert G.paso(p) == 'recomendacion' and G.visible(p, '#gEmpezar')
    # 10 · la salud del mapa degradada NO se ve mientras se planea
    p.evaluate("Spevb.MapaSalud.problema('tiles')"); p.wait_for_timeout(2600)
    assert p.evaluate("document.getElementById('estadosPagina') === null") and not p.evaluate("[...document.querySelectorAll('.estado-pildora')].some(e => e.getClientRects().length > 0)"), 'sin aviso del mapa fuera del viaje'
    V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    # 3 · un solo viaje: doble toque = una sesión; un segundo inicio abre el diálogo y no cambia nada
    p.evaluate("(() => { const b = document.getElementById('gEmpezar'); b.click(); b.click(); })()")
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas >= 1", 8000)
    p.wait_for_timeout(500)
    d = p.evaluate('Spevb.Viaje.diagnostico()')
    assert d['ciclo'] == 'activo' and d['creadas'] == 1 and p.evaluate('window.__geo.escuchas') == 1, d
    p.evaluate("document.getElementById('startTrip').click()"); p.wait_for_timeout(450)
    assert p.evaluate("document.getElementById('conflTitulo') && !document.getElementById('viajeConflicto').hidden && document.getElementById('conflTitulo').textContent") == 'Ya tienes un viaje en curso'
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert p.evaluate('Spevb.Viaje.diagnostico().id') == d['id']
    # 10 · con el viaje activo el problema del mapa SÍ se ve, dentro de la tarjeta
    B.esperar(p, "!!document.querySelector('#viajeEstados .estado-pildora.mapa-incompleto')", 6000)
    assert p.evaluate("document.getElementById('estadosPagina') === null")
    # 4 · círculo caminando → bus con código al subir
    V.alimentar(p, ls, 0, 'fase:caminar')
    assert M.modo(p) == 'persona'
    i = V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    assert M.modo(p) == 'bus' and M.codigo(p) == 'M01'
    # 9 · compartir
    C.crear_enlace(p)
    assert p.evaluate('Spevb.Compartir.activo()') and C.tokens(p)
    p.keyboard.press('Escape'); p.wait_for_timeout(200)
    # 5 · alertas, cada una una vez
    i = V.alimentar(p, ls, i, 'alerta:alerta')
    assert p.evaluate("document.getElementById('viajeBajada').hidden")
    i = V.alimentar(p, ls, i, 'bajada')
    caja = M.caja_bajada(p)
    assert caja and caja['titulo'] == 'Tu bajada está aquí' and caja['rol'] == 'alertdialog', caja
    assert p.evaluate('Spevb.Viaje.alertas().avisadas') == ['0:cerca', '0:preparate', '0:ahora']
    # 10 · la alerta manda sobre la salud del mapa
    assert not p.evaluate("(() => { const e = document.getElementById('viajeEstados'); return e.getClientRects().length > 0 && getComputedStyle(e).display !== 'none'; })()"), 'el aviso del mapa cede'
    # 6 · vibración opcional: hubo vibraciones y la interfaz no depende de ellas
    assert p.evaluate('window.__vibraciones.length') >= 3
    # 4 · «Ya me bajé» → círculo
    p.click('#viajeBajadaYa')
    assert M.modo(p) == 'persona'
    # 16 · llegada: sigue siendo el mismo viaje hasta «Cerrar»; el enlace compartido se revoca
    V.alimentar(p, ls, i, 'fase:llegaste'); p.wait_for_timeout(500)
    assert p.evaluate('Spevb.Viaje.llego()') and p.evaluate('Spevb.Viaje.estadoCiclo()') == 'llegada'
    p.evaluate("document.getElementById('startTrip').click()"); p.wait_for_timeout(450)
    assert 'llegada' in p.inner_text('#conflTexto').lower(), 'la llegada bloquea otro viaje'
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert C.tokens(p) is None and p.evaluate('Spevb.Compartir.activo()') is False, 'al llegar se dejó de compartir'
    p.evaluate('Spevb.Viaje.volverAMiViaje()'); p.wait_for_timeout(300)
    p.click('#viajeTerminar'); p.wait_for_timeout(700)
    # cierre completo
    d = p.evaluate('Spevb.Viaje.diagnostico()')
    assert d['ciclo'] == 'libre' and not d['gps'] and d['timers'] == 0 and not d['capa'] and not d['ruta'] and not d['latido'] and d['bloqueo'] is None, d
    assert p.evaluate('window.__geo.escuchas') == 0 and p.evaluate('Spevb.ViajeRuta.vivas()') == 0 and p.evaluate("document.querySelectorAll('.viaje-yo, .viaje-bus-marca').length") == 0
    assert p.evaluate("localStorage.getItem('spevb-viaje-curso')") is None
    assert not p.evaluate("[...document.querySelectorAll('.estado-pildora')].some(e => e.getClientRects().length > 0)"), 'el aviso del mapa desapareció con el viaje'
    # 11 · Google como única búsqueda: la API del pasajero solo recibió sugerencias/lugares de la API propia
    registro = p.evaluate("fetch('/__log/busqueda').then(r => r.json())")
    externos = [r for r in registro if r['ruta'] not in ('sugerencias', 'lugares', 'reverso')]
    assert not externos, externos
    # 12 · GPS y mapa siguen siendo alternativas del flujo
    p.evaluate("Spevb.Inicio ? Spevb.Inicio.volver('prueba') : 0"); p.wait_for_timeout(500)
    assert G.paso(p) == 'destino' and G.visible(p, '#gBuscarDestino') and G.visible(p, '#gMapaDestino')
    assert p.evaluate("document.getElementById('startTrip').getAttribute('aria-disabled')") == 'false', 'se puede planear otro viaje'
    if reducido:
        t = p.evaluate("(() => { const a = document.querySelector('.viaje-yo'); return a ? getComputedStyle(a).transitionDuration : '0s'; })()")
        assert t == '0s', f'movimiento reducido: sin transición animada ({t})'
    C.limpio_salvo_4xx(s, 'integracion')
    s.cerrar()


@prueba
def recorrido_completo_guiado_viaje_alertas_compartir_salud_y_cierre(nav):
    recorrido(nav, False)


@prueba
def el_mismo_recorrido_con_movimiento_reducido(nav):
    recorrido(nav, True)


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
                print('FALLA ', f.__name__, '|', str(e)[:800].replace('\n', ' '))
                if os.environ.get('SEVB_E2E_TRAZA'):
                    traceback.print_exc()
        nav.close()
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas del recorrido integrado; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
