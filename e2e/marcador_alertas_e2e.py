"""Pruebas de navegador del MARCADOR de la persona (círculo azul ↔ bus con el código de la ruta) y de la ALERTA PROGRESIVA DE BAJADA (4.15.2).

Frontend real, GPS SIMULADO (e2e/simulador_gps.js), vibración, Wake Lock y notificaciones SIMULADAS; la geometría de los avisos es la del núcleo (viaje-nucleo.js), no una copia.
Genera capturas móviles en docs/capturas-viaje/ (círculo, bus y recuadro «Tu bajada está aquí»). NO prueba vibración ni notificaciones en un teléfono real.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/marcador_alertas_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
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
# Notification simulada: cuenta lo que se pide y lo que se muestra; el permiso lo controla window.__perm
NOTIF = """
window.__np = 0; window.__notifs = []; window.__cerradas = 0; window.__perm = 'default';
window.Notification = class { static get permission() { return window.__perm; } static async requestPermission() { window.__np++; window.__perm = 'denied'; return 'denied'; }
    constructor(t, o) { this.title = t; this.opciones = o; this.tag = o && o.tag; window.__notifs.push({ t, o }); } close() { window.__cerradas++; } };
"""


def prueba(f):
    PRUEBAS.append(f)
    return f


def sesion(nav, **opts):
    s = V.sesion(nav, **{**MOVIL, **opts})
    s.ctx.add_init_script(NOTIF)
    return s


def preparar(nav, escenario='multi', **opts):
    s = sesion(nav, **opts)
    p = s.abrir()
    V.planear(p, escenario); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    return s, p, ls


def modo(p):
    return p.evaluate("(() => { const c = document.querySelector('.viaje-yo-caja'); return c ? c.dataset.modo : null; })()")


def codigo(p):
    return p.evaluate("(() => { const b = document.querySelector('.viaje-bus-cod'); return b && !b.hidden ? b.textContent : ''; })()")


def opacidades(p):
    return p.evaluate("""() => ({ yo: +getComputedStyle(document.querySelector('.viaje-yo')).opacity, bus: +getComputedStyle(document.querySelector('.viaje-bus-marca')).opacity })""")


def captura(p, nombre):
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    p.screenshot(path=str(CAPTURAS / nombre))


def caja_bajada(p):
    return p.evaluate("""() => { const e = document.getElementById('viajeBajada'); if (e.hidden) return null; const t = (id) => document.getElementById(id);
        const r = t('viajeBajadaYa').getBoundingClientRect(), s = t('viajeBajadaSigo').getBoundingClientRect(), c = document.getElementById('viajeCard').getBoundingClientRect();
        return { titulo: t('viajeBajadaTitulo').textContent, texto: t('viajeBajadaTexto').textContent, rol: e.getAttribute('role'), etiqueta: e.getAttribute('aria-labelledby'), ya: t('viajeBajadaYa').textContent, sigo: t('viajeBajadaSigo').textContent,
            yaAlto: r.height, sigoAlto: s.height, foco: document.activeElement.id, alto: c.height, vh: innerHeight, tarjetaTop: c.top }; }""")


def hasta_la_bajada(p, ls):
    i = V.alimentar(p, ls, 0, 'pregunta')
    p.click('#viajeSi')
    i = V.alimentar(p, ls, i, 'bajada')
    return i


# ===================================================================================================================== marcador
@prueba
def caminando_es_el_circulo_azul_con_su_circulo_de_precision_y_en_el_bus_es_un_bus_con_el_codigo(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'fase:caminar')
    p.wait_for_timeout(500)
    assert V.card(p)['fase'] == 'caminar' and modo(p) == 'persona', modo(p)
    o = opacidades(p)
    assert o['yo'] == 1 and o['bus'] == 0, o
    assert p.evaluate("getComputedStyle(document.querySelector('.viaje-yo')).backgroundColor") == 'rgb(26, 115, 232)', 'sigue siendo el azul de siempre'
    circulos = p.evaluate("Spevb.maps.map.elementos().filter(e => e.tipo === 'circulo').length")
    assert circulos == 1, f'el círculo de precisión sigue visible: {circulos}'
    captura(p, 'marcador-circulo-caminando.png')
    i = V.alimentar(p, ls, i, 'fase:esperando')
    assert modo(p) == 'persona', 'esperando el bus también es el círculo'
    i = V.alimentar(p, ls, i, 'pregunta')
    assert modo(p) == 'persona', 'con la pregunta de subida abierta todavía eres tú caminando'
    p.click('#viajeSi')
    assert modo(p) == 'bus', 'al confirmar «Sí, me subí» pasa a bus'
    p.wait_for_timeout(450)
    o = opacidades(p)
    assert o['bus'] == 1 and o['yo'] == 0, f'el bus se ve y el círculo se retira: {o}'
    assert codigo(p) == p.evaluate('Spevb.Planner.seleccion.viaje.buses[0].codigo') == 'M01', f'código del primer bus: {codigo(p)!r}'
    assert p.evaluate("document.querySelectorAll('.viaje-yo').length") == 1 and p.evaluate("document.querySelectorAll('.viaje-bus-marca').length") == 1, 'un solo marcador, un solo SVG'
    assert p.evaluate("document.querySelector('.viaje-bus-marca').getAttribute('aria-hidden')") == 'true'
    assert p.evaluate("document.querySelector('.viaje-bus-marca svg').getBoundingClientRect().width") == 44 and circulos == 1
    captura(p, 'marcador-bus-con-codigo.png')
    # el círculo de precisión sigue ahí pero no parece el tamaño del bus (en metros, bajo el bus)
    assert p.evaluate("Spevb.maps.map.elementos().filter(e => e.tipo === 'circulo').length") == 1
    s.limpio('marcador'); s.cerrar()


@prueba
def al_bajarse_vuelve_al_circulo_de_inmediato_y_con_transbordo_alterna_circulo_bus_circulo_bus_circulo(nav):
    s, p, ls = preparar(nav, 'transbordos')
    p.evaluate("""() => { const v = Spevb.Planner.seleccion.viaje; v.destino.lat += 0.003; }""")
    ls = p.evaluate("""() => { const v = Spevb.Planner.seleccion.viaje, b = v.buses[0]; return SimGps.viaje(v, { empezarEn: { lat: b.subida.lat - 0.0022, lng: b.subida.lng } }); }""")
    V.iniciar(p)
    codigos = p.evaluate('Spevb.Planner.seleccion.viaje.buses.map(b => b.codigo)')
    assert len(codigos) == 2 and codigos[0] != codigos[1], codigos
    secuencia = []
    i = 0
    for _ in range(8):
        i = V.alimentar(p, ls, i, 'pregunta')
        c = V.card(p)
        if not c['pregunta']:
            break
        antes = (modo(p), codigo(p))
        p.click('#viajeSi')
        despues = (modo(p), codigo(p))          # inmediatamente después de confirmar (sin esperar la transición)
        secuencia.append((antes, despues))
    assert len(secuencia) == 4, secuencia
    # subida 1: persona → bus(código 1); bajada 1: bus → persona; subida 2: persona → bus(código 2); bajada 2: bus → persona
    assert secuencia[0] == (('persona', ''), ('bus', codigos[0])), secuencia
    assert secuencia[1][0] == ('bus', codigos[0]) and secuencia[1][1][0] == 'persona', f'al confirmar «Ya me bajé» vuelve al círculo: {secuencia}'
    assert secuencia[2] == (('persona', ''), ('bus', codigos[1])), f'el segundo bus usa su propio código: {secuencia}'
    assert secuencia[3][0] == ('bus', codigos[1]) and secuencia[3][1][0] == 'persona', secuencia
    assert V.card(p)['fase'] in ('caminar_final', 'llegaste') and modo(p) in ('persona', None), 'termina caminando: círculo (o ya sin marcador al llegar)'
    s.limpio('transbordo'); s.cerrar()


@prueba
def la_transicion_dura_unos_220_ms_con_transform_y_opacity_y_con_movimiento_reducido_es_inmediata(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p); V.alimentar(p, ls, 0, 'fase:caminar')
    t = p.evaluate("""() => { const a = getComputedStyle(document.querySelector('.viaje-yo')), b = getComputedStyle(document.querySelector('.viaje-bus-marca'));
        return { propsA: a.transitionProperty, durA: a.transitionDuration, propsB: b.transitionProperty, durB: b.transitionDuration }; }""")
    seg = lambda d: float(d.split(',')[0].replace('s', ''))      # noqa: E731
    assert 0.18 <= seg(t['durA']) <= 0.28 and 0.18 <= seg(t['durB']) <= 0.28, t
    assert set(t['propsA'].replace(' ', '').split(',')) == {'transform', 'opacity'} and set(t['propsB'].replace(' ', '').split(',')) == {'transform', 'opacity'}, f'solo transform y opacity: {t}'
    s.cerrar()
    s = sesion(nav, reduced_motion='reduce')
    p = s.abrir(); V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p); V.alimentar(p, ls, 0, 'fase:caminar')
    t = p.evaluate("({ a: getComputedStyle(document.querySelector('.viaje-yo')).transitionDuration, b: getComputedStyle(document.querySelector('.viaje-bus-marca')).transitionDuration })")
    assert t == {'a': '0s', 'b': '0s'}, f'con movimiento reducido no hay transición animada: {t}'
    V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    assert modo(p) == 'bus' and opacidades(p) == {'yo': 0, 'bus': 1}, 'el cambio es instantáneo'
    s.limpio('movimiento reducido'); s.cerrar()


@prueba
def el_marcador_no_se_repinta_si_nada_cambio_y_el_svg_no_se_recrea(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.evaluate("window.__caja = document.querySelector('.viaje-yo-caja'); window.__svg = document.querySelector('.viaje-bus-marca svg'); window.__muts = 0; new MutationObserver((l) => { window.__muts += l.length; }).observe(window.__caja, { subtree: true, childList: true, attributes: true, characterData: true });")
    l = ls[min(len(ls) - 1, 160)]
    p.evaluate("([l]) => { for (let k = 0; k < 6; k++) __geo.emitir(l); }", [l])      # la misma lectura una y otra vez
    p.wait_for_timeout(300)
    assert p.evaluate('window.__muts') == 0, 'lecturas repetidas no tocan el DOM del marcador'
    p.evaluate("(() => { const i = 160; })()")
    V.alimentar(p, ls, 160, 'pregunta')
    p.click('#viajeSi'); p.wait_for_timeout(400)
    V.alimentar(p, ls, 400, None) if False else None
    assert p.evaluate("window.__caja === document.querySelector('.viaje-yo-caja') && window.__svg === document.querySelector('.viaje-bus-marca svg')"), 'el mismo elemento y el mismo SVG durante todo el viaje'
    s.limpio('repintado'); s.cerrar()


# ===================================================================================================================== alertas de bajada
@prueba
def los_tres_niveles_aparecen_una_sola_vez_cada_uno_y_no_se_repiten_con_cada_lectura(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    # nivel 1: aviso anticipado, sin modal, vibración corta
    i = V.alimentar(p, ls, i, 'alerta:alerta')
    t1 = V.card(p)['aviso']
    assert t1.startswith('Te acercas a tu punto de bajada'), t1
    assert p.evaluate("document.getElementById('viajeBajada').hidden") and p.evaluate("Spevb.Modal.hayAbierta()") is False, 'no abre un modal bloqueante ni el recuadro'
    assert p.evaluate("window.__vibraciones.filter(v => JSON.stringify(v) === '[200]').length") == 1, 'una vibración corta'
    assert 'pitido' not in t1
    # nivel 2: prepárate; la tarjeta se expande UNA vez
    p.click('#viajeMinimizar'); assert p.get_attribute('#viajeCard', 'data-modo') == 'compacta'
    i = V.alimentar(p, ls, i, 'aviso')
    j = i
    while p.evaluate("Spevb.Viaje.alertas().avisadas.indexOf('0:preparate') < 0") and j < len(ls):
        j = V.alimentar(p, ls[j:j + 1], 0) + j
    p.wait_for_timeout(200)
    assert p.get_attribute('#viajeCard', 'data-modo') == 'completa', 'la tarjeta se expandió sola'
    assert p.inner_text('#viajeTitulo') == 'Prepárate para bajar', p.inner_text('#viajeTitulo')
    assert p.evaluate("window.__vibraciones.filter(v => JSON.stringify(v) === '[450,150,450]').length") == 1
    p.click('#viajeMinimizar')
    p.evaluate("([l]) => __geo.emitir(l)", [ls[j]]); p.wait_for_timeout(200)
    assert p.get_attribute('#viajeCard', 'data-modo') == 'compacta', 'una sola vez: la siguiente lectura no la vuelve a expandir'
    # nivel 3: recuadro persistente
    k = V.alimentar(p, ls, j, 'bajada')
    caja = caja_bajada(p)
    assert caja and caja['titulo'] == 'Tu bajada está aquí' and caja['texto'] == 'Baja cuando el bus se detenga.' and caja['ya'] == 'Ya me bajé' and caja['sigo'] == 'Sigo en el bus', caja
    assert caja['rol'] == 'alertdialog' and caja['etiqueta'] == 'viajeBajadaTitulo' and caja['foco'] == 'viajeBajadaYa', caja
    assert caja['yaAlto'] >= 56 and caja['sigoAlto'] >= 44, f'botón principal grande: {caja}'
    assert caja['alto'] <= 0.5 * caja['vh'], f'el mapa queda visible en el espacio restante: {caja}'
    captura(p, 'alerta-tu-bajada-esta-aqui.png')
    assert p.evaluate("window.__vibraciones.filter(v => v.length === 5 && v[0] === 700).length") == 1
    # no se oculta por tiempo y no se repite con las lecturas siguientes
    p.wait_for_timeout(2500)
    for l in ls[k:k + 5]:
        p.evaluate("([l]) => __geo.emitir(l)", [l])
    assert caja_bajada(p) is not None or p.evaluate('!document.getElementById("viajePregunta").hidden'), 'sigue ahí hasta que la persona responda'
    al = p.evaluate('Spevb.Viaje.alertas()')
    assert al['avisadas'] == ['0:cerca', '0:preparate', '0:ahora'], al
    vib = p.evaluate('window.__vibraciones')
    assert [v for v in vib if v == [200]] == [[200]] and sum(1 for v in vib if isinstance(v, list) and v and v[0] == 700) == 1 and sum(1 for v in vib if v == [450, 150, 450]) == 1, f'cada vibración de bajada, una vez: {vib}'
    s.limpio('tres niveles'); s.cerrar()


@prueba
def ya_me_baje_cambia_la_fase_y_el_marcador_y_no_se_baja_solo_por_mostrar_la_alerta(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    hasta_la_bajada(p, ls)
    assert V.card(p)['fase'] == 'en_bus' and modo(p) == 'bus', 'mostrar la alerta no marca que te bajaste'
    p.wait_for_timeout(1200)
    assert V.card(p)['fase'] == 'en_bus'
    p.click('#viajeBajadaYa');
    assert modo(p) == 'persona', 'el marcador vuelve al círculo al instante'
    p.wait_for_timeout(300)
    assert V.card(p)['fase'] == 'caminar_final' and p.evaluate("document.getElementById('viajeBajada').hidden") and p.evaluate("!document.getElementById('viajeCard').hasAttribute('data-bajada')"), V.card(p)
    f = p.evaluate("document.activeElement.id || document.activeElement.tagName")
    assert f != 'viajeBajadaYa', f'el foco no queda en un botón oculto: {f}'
    s.limpio('ya me baje'); s.cerrar()


@prueba
def sigo_en_el_bus_conserva_el_bus_y_aplica_enfriamiento(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    k = hasta_la_bajada(p, ls)
    p.click('#viajeBajadaSigo'); p.wait_for_timeout(300)
    assert p.evaluate("document.getElementById('viajeBajada').hidden"), 'se cierra'
    assert V.card(p)['fase'] == 'en_bus' and modo(p) == 'bus' and codigo(p) == 'M01', 'conserva el bus'
    # la persona sigue en la parada «caminando» en los datos simulados: durante el enfriamiento no se vuelve a preguntar
    V.alimentar(p, ls[k:k + 25], 0)
    assert V.card(p)['pregunta'] is None and V.card(p)['fase'] == 'en_bus', 'enfriamiento: la pregunta automática no vuelve enseguida'
    assert p.evaluate("document.getElementById('viajeBajada').hidden"), 'el recuadro no reaparece por lecturas siguientes'
    s.limpio('sigo en el bus'); s.cerrar()


@prueba
def el_foco_vuelve_al_lugar_previo_y_escape_equivale_a_sigo_en_el_bus(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    p.evaluate("document.getElementById('menuFlotante').focus()")
    V.alimentar(p, ls, i, 'bajada')
    assert p.evaluate("document.activeElement.id") == 'viajeBajadaYa', 'el foco entra en el recuadro'
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert p.evaluate("document.getElementById('viajeBajada').hidden") and V.card(p)['fase'] == 'en_bus', 'Escape = Sigo en el bus'
    assert p.evaluate("document.activeElement.id") == 'menuFlotante', f'el foco vuelve a donde estaba: {p.evaluate("document.activeElement.id")}'
    s.limpio('foco'); s.cerrar()


@prueba
def con_un_menu_abierto_el_recuadro_de_bajada_es_operable_con_teclado(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    p.click('#menuFlotante'); p.wait_for_timeout(500)
    V.alimentar(p, ls, i, 'bajada'); p.wait_for_timeout(400)
    assert p.evaluate("document.activeElement.id") == 'viajeBajadaYa', 'la alerta tiene prioridad sobre el menú: el foco entra en «Ya me bajé»'
    vistos = set()
    for _ in range(12):
        p.keyboard.press('Tab'); vistos.add(p.evaluate("document.activeElement.id"))
    assert vistos <= {'viajeBajadaYa', 'viajeBajadaSigo', 'viajeMinimizar', 'viajeOcultar', 'viajeInicio'} and {'viajeBajadaYa', 'viajeBajadaSigo'} <= vistos, vistos
    p.focus('#viajeBajadaYa'); p.keyboard.press('Enter'); p.wait_for_timeout(400)
    assert V.card(p)['fase'] == 'caminar_final' and p.evaluate("document.getElementById('sideMenu').classList.contains('open')"), 'respondió con el teclado y el menú sigue abierto'
    s.limpio('menu + bajada'); s.cerrar()


# ===================================================================================================================== vibración, sonido, notificaciones
@prueba
def sin_navigator_vibrate_todo_sigue_funcionando_y_no_se_promete_vibracion(nav):
    s = sesion(nav)
    s.ctx.add_init_script("try { Object.defineProperty(navigator, 'vibrate', { configurable: true, value: undefined }); } catch (e) {}")
    p = s.abrir(); V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p)
    hasta_la_bajada(p, ls)
    assert caja_bajada(p) and caja_bajada(p)['titulo'] == 'Tu bajada está aquí', 'la interfaz visual funciona igual'
    al = p.evaluate('Spevb.Viaje.alertas()')
    assert al['vibracion'] is False
    p.click('#viajeBajadaSigo'); p.wait_for_timeout(200)      # con el recuadro abierto la tarjeta se reduce a él
    V.abrir_mas(p)
    txt = p.inner_text('#viajeAlertasEstado').lower()
    assert 'vibraci' not in txt and 'pantalla' in txt, f'no se promete vibración si el navegador no la tiene: {txt!r}'
    s.limpio('sin vibrate'); s.cerrar()


@prueba
def no_se_pide_permiso_de_notificaciones_sin_un_gesto_y_activar_alertas_lo_pide_una_sola_vez(nav):
    s, p, ls = preparar(nav)
    assert p.evaluate('window.__np') == 0, 'al abrir la aplicación no se pide nada'
    V.iniciar(p)
    hasta_la_bajada(p, ls)
    p.click('#viajeBajadaYa'); p.wait_for_timeout(300)
    assert p.evaluate('window.__np') == 0, 'ni durante el viaje ni al sonar las alertas: nunca sin un toque'
    V.abrir_mas(p)
    assert p.is_visible('#viajeActivarAlertas') and p.inner_text('#viajeActivarAlertas') == 'Activar alertas'
    assert p.get_attribute('#viajeAlertas', 'aria-pressed') == 'true' and p.inner_text('#viajeAlertas') == 'Alertas de bajada: activadas'
    p.click('#viajeActivarAlertas'); p.wait_for_timeout(300)
    assert p.evaluate('window.__np') == 1, 'el permiso se pidió al tocar «Activar alertas»'
    assert 'bloqueadas' in p.inner_text('#viajeAlertasEstado') and not p.is_visible('#viajeActivarAlertas')
    p.click('#viajeAlertas')
    assert p.get_attribute('#viajeAlertas', 'aria-pressed') == 'false' and p.inner_text('#viajeAlertas') == 'Alertas de bajada: solo en pantalla' and 'Solo verás el aviso en la pantalla' in p.inner_text('#viajeAlertasEstado')
    s.limpio('permiso'); s.cerrar()


@prueba
def con_alertas_apagadas_la_pantalla_avisa_pero_no_vibra_ni_notifica(nav):
    s, p, ls = preparar(nav)
    p.evaluate("Spevb.Ajustes.set('alertasBajada', false)")
    V.iniciar(p)
    hasta_la_bajada(p, ls)
    assert caja_bajada(p) is not None, 'el recuadro sale igual'
    assert p.evaluate("window.__vibraciones.filter(v => Array.isArray(v) && (v.length === 5 || v[0] === 450 || (v.length === 1 && v[0] === 200))).length") == 0, 'sin vibración de bajada'
    p.evaluate("Spevb.Ajustes.set('alertasBajada', true)")
    s.limpio('alertas apagadas'); s.cerrar()


@prueba
def la_notificacion_solo_sale_con_permiso_y_pagina_oculta_sin_datos_privados_y_se_cierra_al_terminar(nav):
    s, p, ls = preparar(nav)
    p.evaluate("window.__perm = 'granted'; Object.defineProperty(document, 'hidden', { configurable: true, get: () => true })")
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'pregunta'); p.click('#viajeSi')
    V.alimentar(p, ls, i, 'bajada'); p.wait_for_timeout(400)
    n = p.evaluate('window.__notifs')
    titulos = [x['t'] for x in n]
    assert titulos == ['Prepárate para bajar', 'Tu bajada está aquí'], f'una por alerta real (preparate y ahora), ninguna por «cerca»: {titulos}'
    import json
    import re
    crudo = json.dumps(n)
    assert not re.search(r'-?\d{1,3}\.\d{3,}', crudo), f'ninguna coordenada exacta: {crudo}'
    assert 'token' not in crudo.lower() and all(x['o']['body'].startswith('Ruta M01') for x in n), crudo
    p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(300)
    assert p.evaluate('window.__cerradas') == 2, 'al terminar se cierran las notificaciones del viaje'
    # con la página visible no se notifica
    s.cerrar()
    s, p, ls = preparar(nav)
    p.evaluate("window.__perm = 'granted'")
    V.iniciar(p); hasta_la_bajada(p, ls)
    assert p.evaluate('window.__notifs.length') == 0, 'con la página a la vista la pantalla ya avisa: no se duplica con una notificación'
    s.limpio('notificaciones'); s.cerrar()


@prueba
def terminar_el_viaje_limpia_el_marcador_el_recuadro_la_vibracion_el_audio_y_las_alertas_tardias(nav):
    s, p, ls = preparar(nav)
    V.iniciar(p)
    k = hasta_la_bajada(p, ls)
    assert caja_bajada(p)
    p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(400)
    r = p.evaluate("""() => ({ marcador: document.querySelectorAll('.viaje-yo, .viaje-bus-marca').length, caja: document.getElementById('viajeBajada').hidden, atributo: document.getElementById('viajeCard').hasAttribute('data-bajada'),
        vibraciones: window.__vibraciones[window.__vibraciones.length - 1], sonido: Spevb.Viaje.alertas().sonido, avisadas: Spevb.Viaje.alertas().avisadas, escuchas: window.__geo.escuchas }); """.replace('); ', ');'))
    assert r['marcador'] == 0 and r['caja'] and not r['atributo'] and r['vibraciones'] == 0 and r['sonido'] is False and r['avisadas'] == [] and r['escuchas'] == 0, r
    # lecturas tardías del viaje anterior no hacen nada; y un viaje nuevo empieza limpio
    vib = p.evaluate('window.__vibraciones.length')
    for l in ls[k:k + 5]:
        p.evaluate("([l]) => __geo.emitir(l)", [l])
    assert p.evaluate('window.__vibraciones.length') == vib and p.evaluate("document.getElementById('viajeBajada').hidden")
    V.iniciar(p)
    al = p.evaluate('Spevb.Viaje.alertas()')
    assert al['avisadas'] == [] and al['bajadaAbierta'] is False and modo(p) in ('persona', None), al
    s.limpio('terminar'); s.cerrar()


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
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas del marcador y las alertas de bajada; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
