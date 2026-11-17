"""Pruebas de navegador del DESVÍO DEL BUS y «Tu parada quedó atrás» (Fase A): caso R006 / KIRPAS con GPS SIMULADO (e2e/simulador_gps.js).

Frontend real, backend stub (e2e/stub_server.py); el detalle de la ruta (/api/rutas/6006) y la caminata (/api/caminata) se interceptan en el navegador para controlar sus respuestas
(demoras, fallos, geometría). NO prueba un teléfono ni un bus real. Las unidades puras (referencia, detector) se prueban en viaje_logica_e2e.py.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/desvio_bus_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import json
import os
import pathlib
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
RAIZ = pathlib.Path(__file__).resolve().parent.parent
CAPTURAS = RAIZ / 'docs' / 'capturas-viaje'
MOVIL = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)


def prueba(f):
    PRUEBAS.append(f)
    return f


# Escenario R006: la ruta corre 5 km al este; el pasajero sube en x = 600 y baja en x = 3000. El bus sale por una calle en obras en x = 1800, avanza 400 m al norte y retoma la ruta en x = 3600.
ESCENARIO_JS = """([caso, bus2, sinRutaId]) => {
    const R = SimGps.R006, plan = R.plan(), ll = (c) => ({ lat: c[1], lng: c[0] });
    if (bus2) { const t2 = R.tramo(3400, 4800); plan.buses.push({ codigo: 'R007', etiqueta: 'R007', nombre: 'Segunda', color: '#1e5fbf', rutaId: 6007, subida: ll(t2[0]), bajada: ll(t2[t2.length - 1]), tramo: t2 }); plan.destino = R.local(5100, 100); }
    if (sinRutaId) delete plan.buses[0].rutaId;
    const T = {
        r006: () => R.unir(R.ruta(600, 1800), R.recta([1800, 0], [1800, 400]), R.recta([1800, 400], [3600, 400]), R.recta([3600, 400], [3600, 0]), R.ruta(3600, 5000)),
        antes: () => R.unir(R.ruta(600, 1000), R.recta([1000, 0], [1000, 400]), R.recta([1000, 400], [1600, 400]), R.recta([1600, 400], [1600, 0]), R.ruta(1600, 3000)),
        normal: () => R.ruta(600, 3000),
    };
    return { plan, ls: SimGps.viajeLibre(plan, T[caso](), { sinCaminarFinal: true }) };
}"""


def sesion(nav, **opts):
    return V.sesion(nav, **opts)


def preparar(s, caso='r006', bus2=False, sin_ruta_id=False, ruta='ok', caminata=None):
    """Abre la aplicación, programa las respuestas del detalle de la ruta y de la caminata y devuelve (página, plan, lecturas, llamadas)."""
    p = s.abrir()
    e = p.evaluate(ESCENARIO_JS, [caso, bus2, sin_ruta_id])
    rec = p.evaluate('SimGps.R006.recorrido()')
    llamadas = {'rutas': [], 'codigo': [], 'caminata': [], 'planificar': [], 'retenidas': [], 'fallidas': 0}

    def detalle(i, codigo, sentido='IDA'):
        return {'id': i, 'codigo': codigo, 'nombre': 'KIRPAS', 'origen': 'A', 'destino': 'B', 'sentido': sentido, 'descripcion': '', 'color': '#d81b60', 'distanciaKm': 5.0, 'activa': True, 'demostrativa': False,
                'validada': True, 'fuente': 'prueba', 'inicio': {'type': 'Point', 'coordinates': rec[0]}, 'fin': {'type': 'Point', 'coordinates': rec[-1]},
                'recorrido': {'type': 'LineString', 'coordinates': rec}, 'paraderos': [], 'version': 1, 'actualizadoEn': None, 'notaValidacion': None, 'advertencias': []}

    def h_ruta(route):
        llamadas['rutas'].append(route.request.url)
        if ruta == 'colgada':
            llamadas['retenidas'].append(route); return
        if ruta == 'error':
            llamadas['fallidas'] += 1
            route.fulfill(status=503, content_type='application/json', body='{"status":503,"message":"sin servicio"}'); return
        route.fulfill(status=200, content_type='application/json', body=json.dumps(detalle(6006, 'R006')))

    def h_codigo(route):
        llamadas['codigo'].append(route.request.url)
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'id': 6006, 'codigo': 'R006', 'nombre': 'KIRPAS', 'aliasUsado': False, 'codigoConsultado': 'R006'}))

    def h_7(route):
        route.fulfill(status=200, content_type='application/json', body=json.dumps({**detalle(6007, 'R007'), 'recorrido': {'type': 'LineString', 'coordinates': rec}}))

    def h_caminata(route):
        llamadas['caminata'].append(route.request.url)
        if caminata is None:
            return route.fallback()
        if caminata == 'colgada':
            llamadas['retenidas'].append(route); return
        if caminata == 'error':
            return route.fulfill(status=503, content_type='application/json', body='{"status":503,"message":"Trayecto peatonal no disponible."}')
        if caminata == 'larga':
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'coordinates': [[-73.65, 4.15], [-73.64, 4.16]], 'metros': 3600, 'minutos': 46, 'fuente': 'prueba'}))
        route.fallback()

    p.route('**/api/rutas/6006', h_ruta); p.route('**/api/rutas/6007', h_7); p.route('**/api/rutas/codigo/R006', h_codigo); p.route('**/api/caminata?**', h_caminata)
    cerrar_original = s.cerrar

    def cerrar():
        for r in list(llamadas['retenidas']):      # las respuestas que la prueba dejó retenidas se cancelan antes de cerrar (sin tareas colgadas)
            try:
                r.abort()
            except Exception:  # noqa: BLE001
                pass
        cerrar_original()
    s.cerrar = cerrar
    llamadas['sin_503'] = lambda: setattr(s, 'errores', [x for x in s.errores if '503' not in x])      # un 503 que la prueba provoca a propósito no es un error de la aplicación
    p.on('request', lambda r: llamadas['planificar'].append(r.url) if '/api/viajes/planificar' in r.url else None)
    return p, e['plan'], e['ls'], llamadas


def iniciar(p, plan, **op):
    ok = p.evaluate("([plan, op]) => Spevb.Viaje.iniciar(plan, undefined, op)", [plan, op])
    assert ok, 'el viaje no arrancó'
    B.esperar(p, "!document.getElementById('viajeCard').hidden && window.__geo.escuchas === 1", 6000)


def en_bus(p, ls):
    """Camina, espera y se sube (respondiendo «Sí, me subí»). Devuelve el índice por el que va la simulación."""
    i = V.alimentar(p, ls, 0, 'pregunta')
    p.click('#viajeSi')
    assert V.card(p)['fase'] == 'en_bus'
    return i


def caja_atras(p):
    return p.evaluate("""() => { const b = document.getElementById('viajeBajada'); if (b.hidden) return null; const t = (id) => document.getElementById(id);
        return { tipo: b.dataset.tipo, titulo: t('viajeBajadaTitulo').textContent, texto: t('viajeBajadaTexto').textContent, rol: b.getAttribute('role'), etiquetado: b.getAttribute('aria-labelledby'), descrito: b.getAttribute('aria-describedby'),
            ya: t('viajeBajadaYa').textContent, sigo: t('viajeBajadaSigo').textContent, foco: document.activeElement.id, parada: t('viajeBajadaParada').hidden, cajas: document.querySelectorAll('#viajeBajada').length }; }""")


def vibraciones(p):
    return p.evaluate('window.__vibraciones.length')


def captura(p, nombre):
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    p.screenshot(path=str(CAPTURAS / nombre))


def desvio(p):
    return p.evaluate("(() => { const i = Spevb.Viaje.info(); return i ? { estado: i.desvio.estado, estimacion: i.estimacion, ref: i.desvio.referencia, fase: i.fase, instruccion: i.instruccion } : null; })()")


# ===================================================================================================================== el mapa y la tarjeta cuentan lo mismo
@prueba
def el_mapa_dibuja_el_conector_y_la_tarjeta_deja_de_decir_todo_va_bien(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'indice:' + str(i + 60))
    c = V.card(p)
    assert 'Todo va bien' in c['instruccion'] and p.evaluate("Spevb.Viaje.rutaEstado().conector") is False and desvio(p)['estado'] == 'normal', c
    # el MISMO instante en que el mapa dibuja el conector naranja, la tarjeta cambia (no dos historias)
    i = V.alimentar(p, ls, i, 'desvio:posible')
    c, d, r = V.card(p), desvio(p), p.evaluate('Spevb.Viaje.rutaEstado()')
    assert r['conector'] and r['desviada'], f'el mapa dibuja el conector ámbar: {r}'
    assert d['estado'] == 'posible' and 'El bus parece haberse apartado de la ruta. Estamos comprobando el recorrido' in c['instruccion'] and 'Todo va bien' not in c['instruccion'], (c, d)
    assert p.inner_text('#viajeMini') == 'Estimación incierta' and p.get_attribute('#viajeCard', 'data-desvio') == 'posible', p.inner_text('#viajeMini')
    assert p.evaluate("document.getElementById('viajeDist').textContent") == 'Incierta' and p.evaluate("document.getElementById('viajeEta').textContent") == 'Incierta'
    assert p.is_visible('#viajeDesvioNota') and 'no es el camino que seguirá el bus' in p.inner_text('#viajeDesvioNota'), 'el conector se explica: no es el camino del bus ni una obra'
    # se conservan el color, el marcador con el código del bus, la fase y la acción manual
    assert p.evaluate("document.querySelector('.viaje-yo-caja').dataset.modo") == 'bus' and p.evaluate("document.querySelector('.viaje-bus-cod').textContent") == 'R006'
    assert V.card(p)['fase'] == 'en_bus' and p.is_visible('#viajeYaBaje')
    assert p.evaluate("Spevb.Viaje.rutaEstado().etapas[1].objetivo") > 500, 'lo ya recorrido de la ruta consumible no se deshace'
    objetivo = p.evaluate("Spevb.Viaje.rutaEstado().etapas[1].objetivo")
    captura(p, 'desvio-posible-conector-y-tarjeta.png')
    # confirmado: aviso persistente pero discreto; sin sonido ni vibración, sin recuadro urgente
    v0 = vibraciones(p)
    i = V.alimentar(p, ls, i, 'desvio:confirmado')
    c = V.card(p)
    assert 'El bus se desvió de la ruta habitual. Te aviso si retoma la ruta y ya pasó tu bajada.' in c['instruccion'], c
    assert p.evaluate("document.getElementById('viajeBajada').hidden") and p.evaluate("document.getElementById('viajeCard').dataset.urgente") is None, 'discreto: no es urgente'
    assert vibraciones(p) == v0, 'el desvío no vibra: el único aviso urgente es «Tu parada quedó atrás»'
    assert p.evaluate("Spevb.Viaje.rutaEstado().conector") is True and p.evaluate("Spevb.Viaje.rutaEstado().etapas[1].objetivo") == objetivo, 'el conector sigue y el avance no cambia'
    captura(p, 'desvio-confirmado-tarjeta.png')
    # un desvío prolongado ofrece preguntar al conductor
    i = V.alimentar(p, ls, i, 'indice:' + str(i + 140))
    assert 'Pregunta al conductor si pasa por tu parada.' in V.card(p)['instruccion'], V.card(p)['instruccion']
    s.limpio('desvio posible/confirmado'); s.cerrar()


@prueba
def al_volver_a_la_ruta_antes_de_la_bajada_el_conector_y_el_aviso_se_retiran_sin_deshacer_el_progreso(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, caso='antes')
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'desvio:confirmado')
    antes = p.evaluate("Spevb.Viaje.rutaEstado().etapas[1].objetivo")
    i = V.alimentar(p, ls, i, 'sin-desvio')
    p.wait_for_timeout(200)
    c = V.card(p)
    assert 'se desvió' not in c['instruccion'] and 'apartado' not in c['instruccion'] and p.evaluate("Spevb.Viaje.rutaEstado().conector") is False, c
    assert p.get_attribute('#viajeCard', 'data-desvio') is None and p.is_hidden('#viajeDesvioNota')
    assert p.evaluate("Spevb.Viaje.rutaEstado().etapas[1].objetivo") >= antes, 'el progreso de la ruta consumible no se deshizo'
    # las instrucciones normales y las alertas ordinarias vuelven
    i = V.alimentar(p, ls, i, 'alerta:alerta')
    assert V.card(p)['aviso'].startswith('Te acercas a tu punto de bajada'), V.card(p)
    s.limpio('retoma antes'); s.cerrar()


# ===================================================================================================================== «Tu parada quedó atrás»
@prueba
def tu_parada_quedo_atras_es_una_sola_tarjeta_prioritaria_accesible_y_no_se_repite(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    iniciar(p, plan)
    i = en_bus(p, ls)
    # con la tarjeta minimizada: el aviso importante la trae al frente, igual que «Tu bajada está aquí»
    p.click('#viajeMinimizar'); assert p.get_attribute('#viajeCard', 'data-modo') == 'compacta'
    i = V.alimentar(p, ls, i, 'desvio:confirmado')
    v0 = vibraciones(p)
    i = V.alimentar(p, ls, i, 'atras')
    p.wait_for_timeout(300)
    caja = caja_atras(p)
    assert caja['tipo'] == 'atras' and caja['titulo'] == 'Tu parada quedó atrás', caja
    assert caja['texto'] == 'El bus retomó la ruta después de tu bajada. Baja en la próxima parada, cuando el bus se detenga.', caja['texto']
    assert caja['ya'] == 'Ya me bajé' and caja['sigo'] == 'Sigo en el bus' and caja['rol'] == 'alertdialog' and caja['etiquetado'] == 'viajeBajadaTitulo' and caja['descrito'] == 'viajeBajadaTexto', caja
    assert caja['cajas'] == 1 and caja['parada'] is True, 'una sola tarjeta, sin el nombre de la parada vieja'
    assert caja['foco'] == 'viajeBajadaYa', f"el foco entra en la acción principal: {caja['foco']}"
    assert p.get_attribute('#viajeCard', 'data-modo') == 'completa' or p.evaluate("document.getElementById('viajeCard').dataset.urgente") == '1', 'visible aunque estuviera minimizada'
    assert vibraciones(p) == v0 + 1 and p.evaluate("JSON.stringify(window.__vibraciones[window.__vibraciones.length - 1])") == '[700,200,700,200,700]', 'una sola vibración urgente'
    assert p.evaluate("Spevb.Viaje.alertas().avisadas.filter(k => k.startsWith('atras:')).length") == 1
    assert p.evaluate("Spevb.Viaje.info().desvio.estado") == 'atras' and p.evaluate("Spevb.Viaje.alertas().avisadas.includes('0:ahora')") is False, 'no sale también «Tu bajada está aquí»'
    # el mapa cuenta lo mismo: nada de conector, la ruta hasta la parada vieja se da por recorrida y la caminata que sale de ella se oculta
    r = p.evaluate('Spevb.Viaje.rutaEstado()')
    assert r['conector'] is False and r['etapas'][1]['objetivo'] == r['etapas'][1]['total'] and r['ocultas'][2] is True, f'el mapa no lleva a la parada original: {r}'
    captura(p, 'parada-atras-recuadro.png')
    # las lecturas siguientes NO repiten la alerta: ni sonido, ni vibración, ni otro recuadro ni otra captura de foco
    p.evaluate("document.getElementById('viajeBajadaSigo').focus()")
    V.alimentar(p, ls, i, 'indice:' + str(i + 120))
    assert vibraciones(p) == v0 + 1 and caja_atras(p)['cajas'] == 1 and p.evaluate("document.activeElement.id") == 'viajeBajadaSigo', 'sin repetir la alerta ni quitarle el foco a quien lo tiene'
    assert p.evaluate("Spevb.Viaje.alertas().avisadas.filter(k => k.startsWith('atras:')).length") == 1
    s.limpio('parada atras'); s.cerrar()


@prueba
def sigo_en_el_bus_y_escape_conservan_la_fase_y_la_instruccion_queda_accesible(nav):
    s = sesion(nav, **MOVIL)
    for como in ('boton', 'escape'):
        p, plan, ls, ll = preparar(s)
        iniciar(p, plan)
        i = en_bus(p, ls)
        i = V.alimentar(p, ls, i, 'atras')
        p.wait_for_timeout(200)
        v0 = vibraciones(p)
        if como == 'boton':
            p.click('#viajeBajadaSigo')
        else:
            assert p.evaluate("document.activeElement.id") == 'viajeBajadaYa'
            p.keyboard.press('Escape')
        p.wait_for_timeout(200)
        assert p.evaluate("document.getElementById('viajeBajada').hidden") and V.card(p)['fase'] == 'en_bus', como
        assert 'Tu parada quedó atrás' in V.card(p)['instruccion'] and p.get_attribute('#viajeInstruccion', 'aria-live') == 'polite', 'la instrucción sigue accesible en la tarjeta'
        assert p.evaluate("Spevb.Viaje.info().desvio.sigo") is True and p.is_visible('#viajeYaBaje'), 'y «Ya me bajé» sigue a mano'
        V.alimentar(p, ls, i, 'indice:' + str(i + 100))
        assert p.evaluate("document.getElementById('viajeBajada').hidden") and vibraciones(p) == v0, f'{como}: no vuelve a salir sola'
        p.click('#viajeTerminar'); p.click('#viajeTerminar'); p.wait_for_timeout(200)
    s.limpio('sigo en el bus'); s.cerrar()


@prueba
def con_el_menu_abierto_el_aviso_de_parada_atras_se_ve_y_se_puede_operar_con_teclado(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'desvio:confirmado')
    p.click('#menuFlotante'); p.wait_for_timeout(500)
    V.alimentar(p, ls, i, 'atras'); p.wait_for_timeout(400)
    assert caja_atras(p) and caja_atras(p)['tipo'] == 'atras', 'el aviso importante sale aunque el menú esté abierto'
    assert p.evaluate("document.activeElement.id") == 'viajeBajadaYa', 'y toma el foco una sola vez'
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert p.evaluate("document.getElementById('viajeBajada').hidden") and V.card(p)['fase'] == 'en_bus'
    s.limpio('menu abierto'); s.cerrar()


@prueba
def cambiar_de_pestana_o_volver_a_la_app_no_reactiva_el_aviso(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'atras')
    p.click('#viajeBajadaSigo'); p.wait_for_timeout(150)
    v0 = vibraciones(p)
    p.evaluate("""() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
        document.dispatchEvent(new Event('visibilitychange')); }""")
    p.wait_for_timeout(100)
    p.evaluate("""() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('focus')); }""")
    V.alimentar(p, ls, i, 'indice:' + str(i + 60)); p.wait_for_timeout(200)
    assert p.evaluate("document.getElementById('viajeBajada').hidden") and vibraciones(p) == v0, 'ocultar y volver no repite el aviso'
    assert p.evaluate("Spevb.Viaje.alertas().avisadas.filter(k => k.startsWith('atras:')).length") == 1
    s.limpio('visibilidad'); s.cerrar()


# ===================================================================================================================== «Ya me bajé»: caminata desde el punto real
def hasta_ya_me_baje(p, ls, i):
    i = V.alimentar(p, ls, i, 'atras')
    p.wait_for_timeout(150)
    return i


@prueba
def ya_me_baje_tras_la_parada_atras_calcula_la_caminata_desde_el_punto_real_y_conserva_el_destino(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, caminata='colgada')
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = hasta_ya_me_baje(p, ls, i)
    i = V.alimentar(p, ls, i, 'indice:' + str(i + 40))      # el bus sigue unos metros más allá de la retoma y la persona se baja de verdad
    ultima = p.evaluate("(() => { const f = Spevb.Viaje.nucleo().filtro; return { lat: f.lat, lng: f.lng }; })()")
    p.click('#viajeBajadaYa'); p.wait_for_timeout(300)
    c = V.card(p)
    assert c['fase'] == 'caminar_final' and p.evaluate("document.querySelector('.viaje-yo-caja').dataset.modo") == 'persona', 'recupera el círculo azul'
    assert p.is_visible('#viajeCaminata') and 'Buscando cómo seguir' in p.inner_text('#viajeCaminataTitulo') and 'Desde donde te bajaste hasta tu destino' in p.inner_text('#viajeCaminataTexto'), p.inner_text('#viajeCaminata')
    r = p.evaluate('Spevb.Viaje.rutaEstado()')
    assert r['ocultas'][-1] is True and r['etapas'][-1]['lineas'] == 0, f'mientras se calcula no se dibuja nada que lleve a la parada vieja ni una recta: {r}'
    assert len(ll['caminata']) == 1, ll['caminata']
    q = {k: float(v) for k, v in (x.split('=') for x in ll['caminata'][0].split('?')[1].split('&'))}
    de_bajada_plan = p.evaluate("(() => { const b = Spevb.Viaje.plan().buses[0].bajada; return [b.lat, b.lng]; })()")
    d_real = p.evaluate("([a, b]) => Spevb.ViajeNucleo.dist({ lat: a.lat, lng: a.lng }, { lat: b[0], lng: b[1] })", [ultima, [q['olat'], q['olng']]])
    d_vieja = p.evaluate("([a, b]) => Spevb.ViajeNucleo.dist({ lat: a[0], lng: a[1] }, { lat: b[0], lng: b[1] })", [de_bajada_plan, [q['olat'], q['olng']]])
    assert d_real < 25 and d_vieja > 800, f'la caminata parte de la posición real ({d_real:.0f} m de ella), no de la parada del plan ({d_vieja:.0f} m)'
    dest = p.evaluate("(() => { const d = Spevb.Viaje.plan().destino; return [d.lat, d.lng]; })()")
    assert abs(q['dlat'] - dest[0]) < 1e-6 and abs(q['dlng'] - dest[1]) < 1e-6, 'el destino original se conserva'
    # llega la respuesta: caminata nueva visible; el plan original queda intacto como referencia
    ll['retenidas'].pop().continue_()
    B.esperar(p, "Spevb.Viaje.caminataReal() && Spevb.Viaje.caminataReal().estado === 'lista'", 6000)
    r = p.evaluate('Spevb.Viaje.rutaEstado()')
    assert r['ocultas'][-1] is False and r['propias'][-1] is True and r['etapas'][-1]['lineas'] >= 1, r
    assert 'Sigue a pie' in p.inner_text('#viajeCaminataTitulo') and 'hasta tu destino' in p.inner_text('#viajeCaminataTexto')
    captura(p, 'caminata-desde-la-bajada-real.png')
    p.evaluate("([l]) => __geo.emitir(l)", [{**ls[min(i + 41, len(ls) - 1)]}]); p.wait_for_timeout(150)
    s.limpio('ya me baje'); s.cerrar()


@prueba
def la_caminata_con_falla_de_red_o_demasiado_larga_ofrece_reintentar_o_recalcular_y_mantiene_el_destino(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, caminata='error')
    iniciar(p, plan)
    i = hasta_ya_me_baje(p, ls, en_bus(p, ls))
    p.click('#viajeBajadaYa'); p.wait_for_timeout(500)
    assert p.get_attribute('#viajeCaminata', 'data-estado') == 'error' and 'Tu destino se mantiene' in p.inner_text('#viajeCaminataTitulo'), p.inner_text('#viajeCaminata')
    assert p.is_visible('#viajeCaminataReintentar') and p.is_visible('#viajeCaminataRecalcular') and p.evaluate("Spevb.Viaje.rutaEstado().etapas.slice(-1)[0].lineas") == 0, 'sin camino peatonal no se dibuja una recta'
    assert V.card(p)['fase'] == 'caminar_final'
    # reintentar con el servicio ya disponible: se calcula y se dibuja
    p.unroute('**/api/caminata?**')
    p.click('#viajeCaminataReintentar')
    B.esperar(p, "Spevb.Viaje.caminataReal().estado === 'lista'", 6000)
    assert p.evaluate("Spevb.Viaje.caminataReal().intentos") == 2 and p.is_hidden('#viajeCaminataReintentar')
    ll['sin_503'](); s.limpio('red'); s.cerrar()
    # demasiado larga a pie: se ofrece «Recalcular desde aquí» con el planificador de siempre (y la confirmación de recálculo)
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, caminata='larga')
    iniciar(p, plan)
    i = hasta_ya_me_baje(p, ls, en_bus(p, ls))
    p.click('#viajeBajadaYa'); p.wait_for_timeout(500)
    assert p.get_attribute('#viajeCaminata', 'data-estado') == 'larga' and p.is_visible('#viajeCaminataRecalcular') and p.is_hidden('#viajeCaminataReintentar')
    assert p.evaluate("Spevb.Viaje.rutaEstado().etapas.slice(-1)[0].lineas") == 0
    id0 = p.evaluate('Spevb.Viaje.id()')
    p.click('#viajeCaminataRecalcular'); p.wait_for_timeout(1200)
    assert len(ll['planificar']) == 1, ll['planificar']
    assert p.evaluate('Spevb.Viaje.id()') == id0 and V.card(p)['fase'] == 'caminar_final', 'el viaje no se reemplaza sin la confirmación de recálculo'
    s.limpio('larga'); s.cerrar()


@prueba
def con_transbordo_la_caminata_va_al_siguiente_bus_o_se_busca_otra_recomendacion(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, bus2=True, caminata='colgada')
    iniciar(p, plan)
    i = hasta_ya_me_baje(p, ls, en_bus(p, ls))
    i = V.alimentar(p, ls, i, 'indice:' + str(i + 50))
    p.click('#viajeBajadaYa'); p.wait_for_timeout(300)
    c = V.card(p)
    assert c['fase'] == 'caminar' and p.evaluate("Spevb.Viaje.info().codigo") == 'R007' and p.evaluate("Spevb.Viaje.info().leg") == 1, c
    q = {k: float(v) for k, v in (x.split('=') for x in ll['caminata'][0].split('?')[1].split('&'))}
    sub2 = p.evaluate("(() => { const b = Spevb.Viaje.plan().buses[1].subida; return [b.lat, b.lng]; })()")
    assert abs(q['dlat'] - sub2[0]) < 1e-6 and abs(q['dlng'] - sub2[1]) < 1e-6, 'la caminata nueva va al punto de subida del siguiente bus'
    ll['retenidas'].pop().continue_()
    B.esperar(p, "Spevb.Viaje.caminataReal() && Spevb.Viaje.caminataReal().estado === 'lista'", 6000)
    assert p.evaluate("Spevb.Viaje.caminataReal().tipo") == 'subida' and 'Camina hasta el siguiente bus' in p.inner_text('#viajeCaminataTitulo')
    assert p.evaluate("Spevb.Viaje.info().codigo") == 'R007', 'el siguiente bus se conserva'
    s.limpio('transbordo alcanzable'); s.cerrar()
    # el siguiente bus ya no es alcanzable a pie desde donde se bajó: se busca otra recomendación hasta el destino original (con la confirmación de siempre)
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, bus2=True, caminata='larga')
    iniciar(p, plan)
    i = hasta_ya_me_baje(p, ls, en_bus(p, ls))
    id0 = p.evaluate('Spevb.Viaje.id()')
    p.click('#viajeBajadaYa'); p.wait_for_timeout(1500)
    assert p.get_attribute('#viajeCaminata', 'data-estado') == 'no-alcanzable' and 'queda lejos a pie' in p.inner_text('#viajeCaminataTitulo')
    assert len(ll['planificar']) == 1, 'se pidió otra recomendación hasta el destino original'
    assert p.evaluate('Spevb.Viaje.id()') == id0, 'y no se reemplazó nada sin la confirmación'
    assert p.evaluate("Spevb.Viaje.rutaEstado().etapas[2].lineas") == 0, 'sin camino peatonal válido no se dibuja una recta hacia el otro bus'
    s.limpio('transbordo no alcanzable'); s.cerrar()


@prueba
def una_respuesta_tardia_de_la_caminata_no_toca_un_viaje_posterior(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, caminata='colgada')
    iniciar(p, plan)
    i = hasta_ya_me_baje(p, ls, en_bus(p, ls))
    p.click('#viajeBajadaYa'); p.wait_for_timeout(300)
    assert len(ll['retenidas']) == 1
    viejo = p.evaluate('Spevb.Viaje.id()')
    p.click('#viajeTerminar'); p.click('#viajeTerminar'); p.wait_for_timeout(300)      # termina ese viaje: el cálculo pendiente se cancela
    assert p.evaluate('Spevb.Viaje.estadoCiclo()') == 'libre'
    # otro viaje distinto empieza y recibe una lectura; ENTONCES llega la respuesta del primero
    p2, plan2, ls2, ll2 = plan, plan, ls, ll
    iniciar(p, plan)
    nuevo = p.evaluate('Spevb.Viaje.id()')
    assert nuevo != viejo
    try:
        ll['retenidas'].pop().fulfill(status=200, content_type='application/json', body=json.dumps({'coordinates': [[-73.64, 4.15], [-73.63, 4.16]], 'metros': 200, 'minutos': 3}))
    except Exception:  # noqa: BLE001  (el navegador ya había cancelado esa petición: es lo esperado)
        pass
    p.wait_for_timeout(400)
    assert p.evaluate('Spevb.Viaje.caminataReal()') is None and p.is_hidden('#viajeCaminata'), 'la respuesta vieja no cambia el viaje nuevo'
    assert p.evaluate("Spevb.Viaje.rutaEstado().ocultas.some(x => x)") is False and p.evaluate('Spevb.Viaje.id()') == nuevo
    s.limpio('respuesta tardia'); s.cerrar()


# ===================================================================================================================== la referencia del recorrido
@prueba
def la_referencia_se_pide_una_vez_no_bloquea_el_inicio_y_se_cancela_al_terminar(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, ruta='colgada')
    iniciar(p, plan)      # el detalle de la ruta NO responde: el viaje empieza igual
    assert V.card(p)['fase'] in ('iniciando', 'caminar', 'esperando') and p.evaluate("Spevb.Viaje.referencia().cargas['0'].estado") == 'cargando'
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'desvio:confirmado')
    V.alimentar(p, ls, i, 'indice:' + str(len(ls) - 1))
    assert len(ll['rutas']) == 1, f"el detalle se pide UNA vez, no con cada lectura del GPS: {len(ll['rutas'])}"
    d = desvio(p)
    assert d['estado'] == 'confirmado' and d['ref'] == 'cargando', f'sin referencia no se concluye que la parada quedó atrás: {d}'
    assert p.evaluate("document.getElementById('viajeBajada').hidden") and not p.evaluate("Spevb.Viaje.alertas().avisadas.some(k => k.startsWith('atras:'))")
    p.click('#viajeTerminar'); p.click('#viajeTerminar'); p.wait_for_timeout(400)
    assert p.evaluate('Spevb.Viaje.estadoCiclo()') == 'libre'
    s.cerrar()
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, ruta='error')
    iniciar(p, plan)
    B.esperar(p, "Spevb.Viaje.referencia().cargas['0'].estado === 'error'", 6000)
    i = en_bus(p, ls)
    V.alimentar(p, ls, i, 'indice:' + str(len(ls) - 1))
    d = desvio(p)
    assert d['estado'] == 'confirmado' and d['ref'] == 'sin-detalle', f'con el detalle de la ruta ausente el caso se mantiene sin confirmar: {d}'
    assert p.evaluate("Spevb.Viaje.referencia().cargas['0'].intentos") == 1 and len(ll['rutas']) == 1
    ll['sin_503'](); s.limpio('referencia ausente'); s.cerrar()


@prueba
def un_plan_guardado_sin_id_de_ruta_resuelve_el_codigo_y_la_referencia_se_verifica(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, sin_ruta_id=True)
    iniciar(p, plan)
    B.esperar(p, "Spevb.Viaje.referencia().estado === 'lista'", 6000)
    assert len(ll['codigo']) == 1 and len(ll['rutas']) == 1, (ll['codigo'], ll['rutas'])
    ref = p.evaluate('Spevb.Viaje.referencia()')
    assert abs(ref['a'] - 600) < 5 and abs(ref['b'] - 3000) < 5 and ref['despues'] > 1900, ref
    i = en_bus(p, ls)
    V.alimentar(p, ls, i, 'atras')
    assert p.evaluate("Spevb.Viaje.info().desvio.estado") == 'atras'
    s.limpio('sin id'); s.cerrar()
    # el detalle es de OTRA ruta o con otro sentido: no se usa (incertidumbre, no una referencia equivocada)
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    rec = p.evaluate('SimGps.R006.recorrido()')
    p.unroute('**/api/rutas/6006')
    p.route('**/api/rutas/6006', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'id': 6006, 'codigo': 'R006', 'sentido': 'REGRESO', 'version': 1, 'recorrido': {'type': 'LineString', 'coordinates': rec}})))
    iniciar(p, plan)
    B.esperar(p, "Spevb.Viaje.referencia().estado === 'sentido'", 6000)
    s.limpio('sentido distinto'); s.cerrar()


# ===================================================================================================================== reanudar
@prueba
def reanudar_con_el_desvio_confirmado_o_la_parada_atras_reconstruye_la_interfaz_sin_repetir_la_alerta(nav):
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'desvio:confirmado')
    i = V.alimentar(p, ls, i, 'indice:' + str(i + 30))
    guardado = p.evaluate("JSON.parse(localStorage.getItem('spevb-viaje-curso'))")
    assert guardado['estado']['dv']['estado'] == 'confirmado' and set(guardado['estado']['dv']) <= {'estado', 'incidente', 'atrasEmitido', 'largo', 'sigo', 'ult'}, guardado['estado']
    p.reload(); B.esperar(p, "!!(window.Spevb && Spevb.Viaje)", 15000); p.wait_for_timeout(600)
    assert V.card(p)['fase'] == 'reanudar'
    p.click('#viajeSi'); p.wait_for_timeout(500)
    d = desvio(p)
    assert d['estado'] == 'confirmado' and 'se desvió' in d['instruccion'], f'la interfaz se reconstruye con el desvío: {d}'
    assert p.evaluate("Spevb.Viaje.rutaEstado().conector") is False, 'sin posición actual todavía no hay dónde dibujar el conector (la ubicación guardada es antigua)'
    # unas pocas lecturas nuevas sobre la ruta NO cierran un caso incierto
    p.evaluate("""() => { const R = SimGps.R006; let t = Date.now() + 100000; for (let k = 0; k < 3; k++) { const q = R.local(3700 + k * 7, R.yRuta(3700 + k * 7)); t += 1000; __geo.emitir({ lat: q.lat, lng: q.lng, precision: 6, t }); } }""")
    p.wait_for_timeout(200)
    assert desvio(p)['estado'] == 'confirmado' and p.evaluate("document.getElementById('viajeBajada').hidden")
    s.limpio('reanudar confirmado'); s.cerrar()
    # con la parada atrás: el recuadro vuelve (sin sonido ni vibración) y la alerta no se repite
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s)
    iniciar(p, plan)
    i = en_bus(p, ls)
    i = V.alimentar(p, ls, i, 'atras')
    p.reload(); B.esperar(p, "!!(window.Spevb && Spevb.Viaje)", 15000); p.wait_for_timeout(600)
    p.click('#viajeSi'); p.wait_for_timeout(600)
    caja = caja_atras(p)
    assert caja and caja['tipo'] == 'atras', 'el recuadro de la parada atrás vuelve'
    assert vibraciones(p) == 0 and desvio(p)['estado'] == 'atras', 'sin repetir la vibración'
    p.evaluate("""() => { const R = SimGps.R006; let t = Date.now() + 100000; for (let k = 0; k < 20; k++) { const q = R.local(4300 + k * 7, R.yRuta(4300 + k * 7)); t += 1000; __geo.emitir({ lat: q.lat, lng: q.lng, precision: 6, t }); } }""")
    p.wait_for_timeout(200)
    assert vibraciones(p) == 0, 'las lecturas nuevas tampoco repiten la alerta'
    s.limpio('reanudar atras'); s.cerrar()


@prueba
def el_viaje_comun_y_el_cierre_no_cambian_con_la_fase_a(nav):
    """Un viaje sin desvío: las mismas fases, sin estados de desvío, sin recuadro nuevo y sin pedir nada raro; terminar libera todo (referencia y caminata incluidas)."""
    s = sesion(nav, **MOVIL)
    p, plan, ls, ll = preparar(s, caso='normal')
    iniciar(p, plan)
    i = en_bus(p, ls)
    V.alimentar(p, ls, i, 'indice:' + str(len(ls) - 1))
    assert desvio(p)['estado'] == 'normal' and p.get_attribute('#viajeCard', 'data-desvio') is None and p.is_hidden('#viajeDesvioNota') and p.is_hidden('#viajeCaminata')
    assert len(ll['rutas']) == 1 and len(ll['caminata']) == 0 and p.evaluate("Spevb.Viaje.referencia().estado") == 'lista'
    assert p.evaluate("Spevb.Viaje.rutaEstado().ocultas.some(x => x)") is False
    p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(300)      # con «Tu bajada está aquí» abierto el pie de la tarjeta no se ve: se termina por la API
    d = p.evaluate('Spevb.Viaje.diagnostico()')
    assert d['ciclo'] == 'libre' and d['gps'] is False and d['timers'] == 0 and d['creadas'] == d['liberadas'], d
    s.limpio('viaje comun'); s.cerrar()


def correr(filtro=None):
    fallos = []
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
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0][:600] if str(e) else repr(e))
                traceback.print_exc(limit=3)
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas del desvío del bus; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
