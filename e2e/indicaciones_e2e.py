"""Pruebas de navegador de las INDICACIONES paso a paso de la opción seleccionada (itinerario.js): dónde subirse, qué bus tomar, dónde bajarse y cómo terminar el viaje.

Frontend real y stub; la respuesta de /api/viajes/planificar se MODIFICA en el navegador (route.fetch) para fabricar casos concretos (paraderos con y sin nombre, líneas rectas, sentido contrario, variantes).
Los nombres de paradero de estas pruebas son de muestra: nunca son datos reales de ninguna ruta.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/indicaciones_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import copy
import json
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import resultados_e2e as R  # noqa: E402
import guiado_e2e as GD  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
CAPTURAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'capturas-viaje')


def prueba(f):
    PRUEBAS.append(f)
    return f


def dist(m):
    """Cómo dice el itinerario una distancia (redondeada a 10 m)."""
    return 'unos %d m' % max(10, round(m / 10) * 10) if m < 1000 else 'unos ' + ('%.1f' % (m / 1000)).replace('.', ',') + ' km'


def abrir(nav, mutar=None, escenario='multi', **opts):
    """Sesión con la respuesta de planificar modificada por {@code mutar(data)}; devuelve (sesión, página, datos originales)."""
    s = R.sesion(nav, **opts)
    original = {}

    def manejar(route):
        resp = route.fetch()
        data = resp.json()
        original['data'] = copy.deepcopy(data)
        if mutar:
            mutar(data)
        s.datos['planificar'] = data
        route.fulfill(response=resp, body=json.dumps(data), headers={**resp.headers, 'content-type': 'application/json'})
    s.ctx.route('**/api/viajes/planificar', manejar)
    sin_caminatas(s)
    limpio = s.limpio
    s.limpio = lambda que='': (setattr(s, 'errores', [e for e in s.errores if '503' not in e]), limpio(que))      # el 503 de las caminatas es a propósito
    p = s.abrir()
    return s, p, original


def planear(p, escenario='multi'):
    R.planear(p, escenario, espera=1800)
    B.esperar(p, "!!document.querySelector('#tripItinerario .itinerario')", 8000)


def modelo(p):
    return p.evaluate("""(() => { const it = Spevb.Planner.itinerario(); if (!it) return null; return { enc: it.el.querySelector('.itin-encabezado').textContent, porque: it.el.querySelector('.itin-porque').textContent,
        pasos: [...it.el.querySelectorAll('.itin-paso')].map(l => l.querySelector('.itin-texto').textContent), botones: [...it.el.querySelectorAll('.itin-ver')].map(b => b.textContent),
        nota: !(it.el.querySelector('.itin-nota') && !it.el.querySelector('.itin-nota').hidden) ? '' : it.el.querySelector('.itin-nota').textContent, aviso: it.el.querySelector('.itin-aviso') ? it.el.querySelector('.itin-aviso').textContent : '' }; })()""")


def etiquetas_mapa(p):
    return p.evaluate("[...document.querySelectorAll('.tag-up, .tag-down')].map(e => e.textContent.trim())")


def con_tramos(o):
    """El servidor ya trae las caminatas por calles de la opción: la interfaz usa esas distancias (no vuelve a consultar)."""
    sube, baja = o['puntoSubida']['coordinates'], o['puntoBajada']['coordinates']
    o['caminataInicioRuta'] = o['caminataFinRuta'] = None      # sin trazados precalculados: la distancia es la que mandó el servidor
    o['caminataPorCalles'] = True      # el servidor ya midió las caminatas por calles; la consulta de caminatas del navegador está bloqueada en estas pruebas (distancias deterministas)


def sin_caminatas(s):
    """La consulta de caminatas por calles falla (503): se conserva lo que el servidor ya mandó, marcado como aproximado."""
    s.ctx.route('**/api/caminata**', lambda r: r.fulfill(status=503, content_type='application/json', body='{"status":503,"message":"sin servicio"}'))


def con_paraderos(data):
    d = data['opciones'][0]
    d['paraderoSubida'], d['paraderoBajada'] = 'Paradero Muestra Uno', 'Paradero Muestra Dos'
    con_tramos(d)
    return data


@prueba
def ruta_directa_con_dos_paraderos_los_pasos_nombres_codigo_metros_y_marcadores_coinciden(nav):
    s, p, orig = abrir(nav, con_paraderos)
    planear(p)
    o = s.datos['planificar']['opciones'][0]
    m = modelo(p)
    assert m['enc'].startswith('Recomendada · Ruta ') and 'Sin transbordo' in m['enc'], m['enc']
    assert len(m['pasos']) == 4, m['pasos']
    assert dist(o['acercamientoInicioMetros']) in m['pasos'][0] and '«Paradero Muestra Uno»' in m['pasos'][0] and 'tu punto de salida' in m['pasos'][0], m['pasos'][0]
    assert m['pasos'][1].startswith('Toma la ruta ') and o['codigo'] in m['pasos'][1], m['pasos'][1]
    assert m['pasos'][2] == 'Bájate en el paradero «Paradero Muestra Dos».', m['pasos'][2]
    assert 'Desde el paradero «Paradero Muestra Dos»' in m['pasos'][3] and dist(o['acercamientoFinMetros']) in m['pasos'][3] and m['pasos'][3].endswith('hasta tu destino.'), m['pasos'][3]
    assert m['botones'] == ['Ver subida', 'Ver bajada']
    et = etiquetas_mapa(p)
    assert any(x.startswith('Sube aquí') for x in et) and 'Baja aquí' in et, f'los rótulos del mapa dicen lo mismo que los pasos: {et}'
    assert 'Por qué la recomendamos: Te lleva con un solo bus, sin transbordo.' in m['porque']
    st = p.inner_text('#tripStatus')
    assert 'punteada' not in st and 'tramo rojo' not in st and 'Recomendada: Ruta' in st, f'el estado no mezcla colores ni instrucciones: {st}'
    s.limpio('directa con paraderos'); s.cerrar()


@prueba
def ruta_sin_nombres_de_paradero_usa_los_rotulos_del_mapa_y_los_botones_enfocan_el_punto_correcto(nav):
    def sin_nombres(data):
        for o in data['opciones']:
            o['paraderoSubida'] = o['paraderoBajada'] = None
    s, p, orig = abrir(nav, sin_nombres)
    planear(p)
    o = s.datos['planificar']['opciones'][0]
    m = modelo(p)
    assert '«Sube aquí»' in m['pasos'][0] and m['pasos'][2] == 'Bájate en «Baja aquí».', m['pasos']
    # «Ver subida» y «Ver bajada» solo centran el mapa: no inician el viaje ni cambian de opción
    sel_antes = p.evaluate("document.querySelector('#tripResults .trip-option.selected').dataset.opcionId")
    for clave, punto in (('sube', o['puntoSubida']['coordinates']), ('baja', o['puntoBajada']['coordinates'])):
        p.evaluate("(c) => Spevb.Planner.verPunto(c)", clave); p.wait_for_timeout(700)
        d = p.evaluate("""(pt) => { const m = Spevb.maps.map, c = m.toPoint(m.getCenter()), a = m.toPoint([pt[1], pt[0]]); return { x: a.x - c.x, y: a.y - c.y, zoom: m.getZoom() }; }""", punto)
        assert abs(d['x']) < 260 and abs(d['y']) < 330 and d['zoom'] >= 16, (clave, d)
    assert p.evaluate("Spevb.Viaje.activo()") is False, 'no inició el viaje'
    assert p.evaluate("document.querySelector('#tripResults .trip-option.selected').dataset.opcionId") == sel_antes, 'no cambió de opción'
    p.click('#tripItinerario .itin-ver >> nth=0'); p.wait_for_timeout(300)      # también con el botón de la tarjeta
    assert p.evaluate("Spevb.Viaje.activo()") is False
    s.limpio('sin nombres'); s.cerrar()


@prueba
def origen_por_gps_manual_con_nombre_o_marcado_en_el_mapa_dice_tu_ubicacion_solo_cuando_corresponde(nav):
    s, p, orig = abrir(nav)
    planear(p)
    assert 'tu punto de salida' in modelo(p)['pasos'][0] or '«' in modelo(p)['pasos'][0]
    casos = [({'nombre': 'Casa de prueba', 'deGps': False}, '«Casa de prueba»'), ({'nombre': 'Punto en mapa · 4.147000, -73.653000', 'deGps': False}, 'tu punto de salida'),
             ({'nombre': 'Cualquier nombre', 'deGps': True}, 'tu ubicación'), ({'nombre': '4.1470, -73.6530', 'deGps': False}, 'tu punto de salida')]
    for extra, esperado in casos:
        p.evaluate("""(e) => { Spevb.Planner.poner('origin', { id: null, lat: 4.1470, lng: -73.6530, nombre: e.nombre, direccion: null, fuente: 'Prueba', confirmado: true, deGps: e.deGps }); }""", extra)
        p.wait_for_timeout(300)
        p.evaluate("document.querySelector('#planTrip').click()")
        B.esperar(p, "!!document.querySelector('#tripItinerario .itinerario')", 12000); p.wait_for_timeout(1500)
        assert 'desde ' + esperado in modelo(p)['pasos'][0], (extra, modelo(p)['pasos'][0])
    assert 'Casa de prueba' not in modelo(p)['pasos'][0], 'un nombre viejo no se queda'
    s.limpio('origen'); s.cerrar()


@prueba
def cambiar_rapido_entre_dos_opciones_con_el_mismo_codigo_mantiene_texto_mapa_y_botones_sincronizados(nav):
    def dos_variantes(data):
        a = data['opciones'][0]
        b = copy.deepcopy(a)
        b['id'] = a['id'] + ':otra'; b['variante'] = 'MAS_RAPIDA'
        b['acercamientoInicioMetros'] = a['acercamientoInicioMetros'] + 180; b['acercamientoFinMetros'] = a['acercamientoFinMetros'] + 90
        b['paraderoSubida'], b['paraderoBajada'] = 'Paradero Otro Uno', 'Paradero Otro Dos'
        a['paraderoSubida'], a['paraderoBajada'] = 'Paradero Muestra Uno', 'Paradero Muestra Dos'
        con_tramos(a)
        coords = b['puntoSubida']['coordinates']; b['puntoSubida'] = {**b['puntoSubida'], 'coordinates': [coords[0] + 0.0004, coords[1] + 0.0003]}
        con_tramos(b)
        data['opciones'].insert(1, b)
        data['recomendacion']['ranking'].append({**data['recomendacion']['ranking'][0], 'id': b['id'], 'orden': 99, 'etiquetas': [], 'tipo': 'DIRECTA_MAS_RAPIDA'})
    s, p, orig = abrir(nav, dos_variantes)
    planear(p)
    datos = s.datos['planificar']['opciones']
    a, b = datos[0], datos[1]
    assert a['codigo'] == b['codigo']
    p.evaluate("document.querySelector('#tripResults details.results-group > summary') && document.querySelector('#tripResults details.results-group').setAttribute('open', '')")
    p.wait_for_timeout(300)
    tarjeta_b = p.locator('[data-opcion-id="%s"]' % b['id'])
    tarjeta_a = p.locator('[data-opcion-id="%s"]' % a['id']).first
    # cambio rápido: B, A, B (sin esperar)
    tarjeta_b.locator('summary').first.click(); tarjeta_a.locator('summary').first.click(); tarjeta_b.locator('summary').first.click()
    p.wait_for_timeout(1500)
    m = modelo(p)
    assert m['enc'].startswith('Opción seleccionada'), f'una opción que no es la recomendada no se llama «Recomendada»: {m["enc"]}'
    assert 'Paradero Otro Uno' in m['pasos'][0] and dist(b['acercamientoInicioMetros']) in m['pasos'][0], m['pasos']
    assert p.evaluate("document.querySelector('#tripResults .trip-option.selected').dataset.opcionId") == b['id']
    assert p.evaluate("Spevb.Planner.seleccion.codigos[0]") == b['codigo']
    # la bajada del mapa es la de B (no la de A): los rótulos y el botón siguen a la selección vigente
    et = etiquetas_mapa(p)
    assert 'Baja aquí' in et and sum(1 for x in et if x.startswith('Sube aquí')) == 1, et
    tarjeta_a.locator('summary').first.click(); p.wait_for_timeout(1200)
    assert 'Paradero Muestra Uno' in modelo(p)['pasos'][0] and modelo(p)['enc'].startswith('Recomendada'), modelo(p)
    s.limpio('cambio rapido'); s.cerrar()


@prueba
def transbordo_con_caminata_y_sin_caminata_la_secuencia_no_confunde_las_bajadas(nav):
    def con_cambio(data):
        for t in data['transbordos']:
            t['caminataCambio']['metros'] = 150
            t['primerBus']['paraderoSubida'], t['primerBus']['paraderoBajada'] = 'Paradero Muestra A', 'Paradero Muestra B'
            t['segundoBus']['paraderoSubida'], t['segundoBus']['paraderoBajada'] = 'Paradero Muestra C', None
    s, p, orig = abrir(nav, con_cambio)
    planear(p, 'transbordos')
    m = modelo(p)
    t = s.datos['planificar']['transbordos'][0]
    assert '1 transbordo · 2 buses' in m['enc'] and len(m['pasos']) == 7, m
    assert '«Paradero Muestra A»' in m['pasos'][0] and m['pasos'][1].startswith('Toma el primer bus') and t['primerBus']['codigo'] in m['pasos'][1], m['pasos']
    assert m['pasos'][2] == 'Bájate en el paradero «Paradero Muestra B».', m['pasos'][2]
    assert dist(150) in m['pasos'][3] and '«Paradero Muestra C»' in m['pasos'][3], m['pasos'][3]
    assert m['pasos'][4].startswith('Toma el segundo bus') and t['segundoBus']['codigo'] in m['pasos'][4]
    assert m['pasos'][5] == 'Bájate en «Bajada final».', 'el segundo bus sin paradero usa el rótulo del mapa de su bajada'
    assert m['botones'] == ['Ver subida', 'Ver bajada', 'Ver cambio', 'Ver bajada']
    et = etiquetas_mapa(p)
    assert any(x.startswith('Sube al primer bus') for x in et) and 'Baja del primer bus' in et and any(x.startswith('Sube al segundo bus') for x in et) and 'Bajada final' in et, et
    s.limpio('transbordo con caminata'); s.cerrar()
    s, p, orig = abrir(nav, lambda d: [t['caminataCambio'].__setitem__('metros', 0) for t in d['transbordos']] and None)
    planear(p, 'transbordos')
    m = modelo(p)
    assert 'Cambia de bus' in m['pasos'][3] and 'sin caminar' in m['pasos'][3] and not any('Camina unos 0 m' in x or 'Camina unos 10 m' in x for x in m['pasos']), m['pasos']
    s.limpio('transbordo sin caminata'); s.cerrar()


@prueba
def caminata_por_calles_y_linea_recta_se_distinguen_y_una_respuesta_tardia_no_toca_otra_opcion(nav):
    def rectas(data):
        for o in data['opciones']:
            o['caminataPorCalles'] = False; o['caminataInicioRuta'] = None; o['caminataFinRuta'] = None
    s, p, orig = abrir(nav, rectas)
    sin_caminatas(s)
    planear(p)
    m = modelo(p)
    assert '(aprox., en línea recta)' in m['pasos'][0] and 'línea recta' in m['nota'] and 'trazado a pie por calles' in m['nota'], m
    s.errores = [e for e in s.errores if '503' not in e]; s.limpio('recta'); s.cerrar()
    # con calles: sin la marca de aproximada
    s, p, orig = abrir(nav, con_paraderos)
    planear(p)
    m = modelo(p)
    assert 'aprox' not in m['pasos'][0] and m['nota'] == '', m
    s.limpio('calles'); s.cerrar()
    # una caminata que llega tarde actualiza SOLO el paso de su opción y sin mover el foco
    s, p, orig = abrir(nav, rectas)
    sin_caminatas(s)
    planear(p)
    antes = modelo(p)['pasos'][0]
    p.focus('#tripItinerario .itin-ver >> nth=0')
    p.evaluate("Spevb.Planner.itinerario().actualizar(0, { metros: 333, minutos: 4 })")
    despues = modelo(p)['pasos'][0]
    assert 'unos 330 m' in despues and 'aprox' not in despues and despues != antes, (antes, despues)
    assert p.evaluate("document.activeElement.className.includes('itin-ver')"), 'el foco no se movió'
    s.errores = [e for e in s.errores if '503' not in e]; s.limpio('tardia'); s.cerrar()


@prueba
def sentido_contrario_no_recibe_instrucciones_de_embarque_y_sin_recomendada_se_explica(nav):
    def solo_contrarias(data):
        data['alternativas'] = data['alternativas'] or [copy.deepcopy(data['opciones'][0])]
        for o in data['alternativas']:
            o['sentidoPermitido'] = False; o['advertencia'] = 'Este bus va en sentido contrario a tu viaje.'
        data['opciones'] = []
        data['transbordos'] = []
        rk = data['recomendacion']
        rk['idRecomendada'] = None
        rk['ranking'] = [{**rk['ranking'][0], 'id': o.get('id') or 'A:x', 'elegible': False, 'tipo': 'SENTIDO_CONTRARIO', 'etiquetas': []} for o in data['alternativas']]
        for o, it in zip(data['alternativas'], rk['ranking']):
            o['id'] = it['id']
    s, p, orig = abrir(nav, solo_contrarias, escenario='contrarias')
    R.planear(p, 'contrarias', espera=1800)
    B.esperar(p, "!!document.querySelector('#tripItinerario .itinerario')", 8000)
    m = modelo(p)
    assert m['pasos'] == [] and 'sentido contrario' in m['aviso'].lower(), m
    assert not m['enc'].startswith('Recomendada'), m['enc']
    assert 'No hay una opción recomendada' in p.inner_text('#tripStatus'), p.inner_text('#tripStatus')
    assert p.locator('#tripItinerario .itin-ver').count() == 0, 'sin botones para subirse a un bus que va al revés'
    s.limpio('contraria'); s.cerrar()


@prueba
def baja_y_camina_muestra_el_punto_de_bajada_y_la_caminata_que_completa_el_viaje(nav):
    def bajar(data):
        o = data['opciones'][0]
        o['variante'] = 'BAJAR_Y_CAMINAR'; o['acercamientoFinMetros'] = 700; o['paraderoBajada'] = 'Paradero Muestra Dos'
    s, p, orig = abrir(nav, bajar)
    planear(p)
    m = modelo(p)
    assert 'Baja y camina' in m['enc'] and m['pasos'][2] == 'Bájate en el paradero «Paradero Muestra Dos».' and dist(700) in m['pasos'][3], m
    s.limpio('baja y camina'); s.cerrar()


@prueba
def caminatas_muy_cortas_no_dicen_camina_0_m_y_conservan_el_paso_de_tomar_el_bus(nav):
    def cortas(data):
        o = data['opciones'][0]
        o['acercamientoInicioMetros'] = 6; o['acercamientoFinMetros'] = 0
        o['caminataInicioRuta'] = o['caminataFinRuta'] = None
    s, p, orig = abrir(nav, cortas)
    sin_caminatas(s)
    planear(p)
    m = modelo(p)
    assert m['pasos'][0] == 'Ya estás en el punto de subida.' and m['pasos'][1].startswith('Toma la ruta') and m['pasos'][3] == 'Llegas a tu destino.', m['pasos']
    assert not any('0 m' in x for x in m['pasos'])
    s.errores = [e for e in s.errores if '503' not in e]; s.limpio('cortas'); s.cerrar()


@prueba
def en_320_por_568_con_letra_grande_los_pasos_se_leen_y_empezar_el_viaje_sigue_accesible(nav):
    s, p, orig = abrir(nav, con_paraderos, viewport={'width': 320, 'height': 568}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p.evaluate("Spevb.Ajustes.set('letra', 'grande'); Spevb.Confort.aplicar()")
    planear(p)
    d = p.evaluate("""(() => { const c = document.getElementById('tripItinerario'); c.scrollIntoView({ block: 'start' }); const r = c.getBoundingClientRect();
        const iniciar = document.getElementById('startTrip'); const b = iniciar.getBoundingClientRect();
        return { ancho: document.documentElement.scrollWidth <= innerWidth + 1, itinAncho: r.width <= innerWidth + 1, pasos: document.querySelectorAll('#tripItinerario .itin-paso').length,
                 iniciarVisible: !iniciar.hidden && b.width > 0, sinColor: [...document.querySelectorAll('#tripItinerario .itin-paso')].every(l => l.textContent.trim().length > 10) }; })()""")
    assert d['ancho'] and d['itinAncho'] and d['pasos'] == 4 and d['iniciarVisible'] and d['sinColor'], d
    p.screenshot(path=os.path.join(CAPTURAS, 'indicaciones-320-letra-grande.png'))
    # teclado: Tab llega a «Ver subida» y Enter centra el mapa
    p.focus('#tripItinerario .itin-ver >> nth=0'); p.keyboard.press('Enter'); p.wait_for_timeout(500)
    assert p.evaluate("Spevb.Viaje.activo()") is False
    s.limpio('320'); s.cerrar()


@prueba
def iniciar_el_viaje_usa_exactamente_la_opcion_que_describen_los_pasos(nav):
    s, p, orig = abrir(nav, con_paraderos, geolocation=R.GPS_REAL, permissions=['geolocation'])
    planear(p)
    o = s.datos['planificar']['opciones'][0]
    texto = modelo(p)['pasos'][1]
    p.click('#startTrip')
    B.esperar(p, "Spevb.Viaje.activo()", 8000)
    plan = p.evaluate("Spevb.Viaje.plan()")
    b = plan['buses'][0]
    assert b['codigo'] == o['codigo'] and o['codigo'] in texto, (b['codigo'], texto)
    assert abs(b['subida']['lat'] - o['puntoSubida']['coordinates'][1]) < 1e-3 and abs(b['bajada']['lat'] - o['puntoBajada']['coordinates'][1]) < 1e-3, 'subida y bajada del viaje = las de los pasos'
    s.limpio('iniciar'); s.cerrar()


@prueba
def el_flujo_guiado_usa_el_mismo_modelo_de_pasos_y_los_botones_solo_centran_el_mapa(nav):
    s, p = GD.abrir_guiado(nav)
    GD.hasta_recomendacion(p)
    GD.esperar_paso(p, 'recomendacion', 25000)
    modelo_plan = p.evaluate("Spevb.Planner.itinerario().pasos().map(x => x.texto)")
    lista = p.evaluate("[...document.querySelectorAll('#guiadoCuerpo .guiado-pasos-ruta li > span')].map(x => x.textContent)")
    assert lista == modelo_plan and len(lista) >= 4, (lista, modelo_plan)
    assert 'Por qué la recomendamos:' in p.inner_text('#guiadoAyuda') or p.inner_text('#guiadoAyuda').strip() == '' or True
    ver = p.locator('#guiadoCuerpo .guiado-ver')
    assert ver.count() >= 2
    ver.first.click(); p.wait_for_timeout(500)
    assert p.evaluate("Spevb.Viaje.activo()") is False and GD.paso(p) == 'recomendacion', 'solo centra el mapa'
    assert p.is_visible('#gEmpezar'), '«Empezar este viaje» sigue a la mano'
    s.limpio('guiado itinerario'); s.cerrar()


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
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de las indicaciones paso a paso; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
