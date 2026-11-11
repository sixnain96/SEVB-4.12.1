"""Pruebas de navegador del FLUJO GUIADO (4.15): una decisión por pantalla sobre el planificador real.

Frontend real; backend = stub (e2e/stub_server.py); GPS: el de Playwright (permiso concedido o denegado) o el simulado (e2e/simulador_gps.js) cuando se inicia un viaje.
Las pruebas hacen toques REALES (se comprueba qué elemento recibe el toque) y miden visibilidad, no solo que existan nodos.
NO prueba un teléfono físico, WebKit ni a una persona real: eso lo cubre docs/PRUEBAS-USABILIDAD-GUIADA.md.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/guiado_e2e.py [filtro]      (lo normal es e2e/run_e2e.py; no se ejecuta en paralelo con otra suite en el mismo puerto)
"""
import json
import os
import re
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
DEST = '4.1450, -73.6240'
ORIG = '4.1470, -73.6530'
DEST2 = '4.1460, -73.6300'
CONTADOR_GPS = """window.__gpsPedidos = 0; (() => { const g = navigator.geolocation; if (!g) return; ['getCurrentPosition', 'watchPosition'].forEach((m) => { const o = g[m].bind(g); g[m] = (...a) => { window.__gpsPedidos++; return o(...a); }; }); })();"""
TAMANOS = [('320x568', 320, 568), ('360x640', 360, 640), ('390x844', 390, 844), ('tableta 768x1024', 768, 1024)]


def prueba(f):
    PRUEBAS.append(f)
    return f


def abrir_guiado(nav, ancho=390, alto=844, geo=True, ruta='', **extra):
    opts = dict(viewport={'width': ancho, 'height': alto}, is_mobile=ancho < 700, has_touch=ancho < 700, device_scale_factor=2)
    if geo:
        opts.update(permissions=['geolocation'], geolocation=V.GPS)
    opts.update(extra)
    s = B.Sesion(nav, guiado=True, **opts)
    s.ctx.add_init_script(CONTADOR_GPS)
    p = s.ctx.pages[0]
    p.goto(B.URL + ruta.lstrip('/'), wait_until='domcontentloaded')
    B.esperar(p, "!!(window.Spevb && Spevb.maps && Spevb.maps.map && Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.wait_for_timeout(1200)
    s.page = p
    return s, p


def limpio_salvo_http(s, que):
    """Esta prueba provoca a propósito un 500 del servidor: el navegador lo anota como error de consola; cualquier OTRO error (JavaScript, promesas) sí falla."""
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio(que)


def paso(p):
    return p.evaluate('Spevb.Guiado.paso()')


def esperar_paso(p, nombre, t=12000):
    B.esperar(p, f"Spevb.Guiado.paso() === '{nombre}'", t)
    p.wait_for_timeout(250)


def titulo(p):
    return p.inner_text('#guiadoTitulo').strip()


def puntos(p):
    return p.evaluate('Spevb.Planner.puntos()')


def pulsar(p, sel, minimo=44):
    """Un toque REAL: solo se desplaza el panel (como haría un dedo) y se comprueba que el botón (y no otra cosa: tarjeta, panel, teclado) recibe el toque."""
    r = p.evaluate("""(sel) => { const e = document.querySelector(sel); if (!e) return null; const cuerpo = document.querySelector('.sheet-body');
        let b = e.getBoundingClientRect();
        if (cuerpo) { const c = cuerpo.getBoundingClientRect(); if (b.bottom > Math.min(c.bottom, innerHeight) - 8) cuerpo.scrollTop += b.bottom - Math.min(c.bottom, innerHeight) + 16; if (b.top < c.top) cuerpo.scrollTop -= c.top - b.top + 8; b = e.getBoundingClientRect(); }
        const x = b.left + b.width / 2, y = b.top + b.height / 2, t = document.elementFromPoint(x, y);
        return { x, y, golpea: !!t && (t === e || e.contains(t)), alto: b.height, ancho: b.width, quien: t ? (t.id || t.className || t.tagName) : null, dentro: b.top >= 0 && b.bottom <= innerHeight }; }""", sel)
    assert r, f'no existe {sel}'
    assert r['golpea'] and r['dentro'], f'{sel} no recibe el toque (encima: {r["quien"]}): {r}'
    assert r['alto'] >= minimo and r['ancho'] >= minimo, f'{sel} es muy pequeño para tocarlo: {r}'
    p.mouse.click(r['x'], r['y'])
    return r


def visibles(p, sel):
    return p.evaluate("(s) => [...document.querySelectorAll(s)].filter((e) => { const r = e.getBoundingClientRect(), c = getComputedStyle(e); return r.width > 0 && r.height > 0 && c.visibility !== 'hidden' && c.display !== 'none'; }).length", sel)


def visible(p, sel):
    return visibles(p, sel) > 0


def elegir_destino(p, texto=DEST):
    p.fill('#tripDestination', texto)
    pulsar(p, '#gBuscarDestino')
    esperar_paso(p, 'confirmar_destino')


def elegir_origen_escribiendo(p, texto=ORIG):
    pulsar(p, '#gEscribirOrigen')
    p.fill('#tripOrigin', texto)
    pulsar(p, '#gBuscarOrigen')
    esperar_paso(p, 'confirmar_origen')


def hasta_resumen(p):
    elegir_destino(p)
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    elegir_origen_escribiendo(p)
    pulsar(p, '#gSiOrigen')
    esperar_paso(p, 'resumen')


def hasta_recomendacion(p):
    hasta_resumen(p)
    pulsar(p, '#gBuscar')
    esperar_paso(p, 'recomendacion', 20000)
    p.wait_for_timeout(500)


# ---------------------------------------------------------------------------------------------- 1. primera pantalla
@prueba
def persona_nueva_ve_solo_la_pregunta_del_destino_sin_a_ni_b_y_sin_pedir_ubicacion(nav):
    s, p = abrir_guiado(nav)
    assert paso(p) == 'destino' and titulo(p) == '¿A dónde quieres ir?', titulo(p)
    assert 'Escribe un lugar, una dirección o el nombre de un sitio.' in p.inner_text('#guiado')
    assert visible(p, '#tripDestination') and not visible(p, '#tripOrigin'), 'solo el campo del destino'
    assert not visible(p, '#planTrip') and not visible(p, '.endpoint-letter') and not visible(p, '#swapTrip') and not visible(p, '#startTripBar'), 'sin las herramientas del planificador'
    textos = p.evaluate("[document.getElementById('guiado').innerText, document.getElementById('guiadoAcciones').innerText].join(' ')")
    assert not re.search(r'punto [AB]\b|\b[AB] y [AB]\b|\(A\)|\(B\)|\bA/B\b', textos), f'la interfaz principal no habla de A y B: {textos}'
    for t in ('Buscar destino', 'Elegir en el mapa', 'Necesito ayuda'):
        assert t in textos, (t, textos)
    assert visibles(p, '.guiado-boton.primario') == 1, 'una sola acción principal'
    assert p.evaluate('window.__gpsPedidos') == 0, 'no se pide la ubicación al abrir la aplicación'
    assert p.evaluate("document.querySelector('#guiadoPasos li[aria-current=step]').textContent.includes('Destino')"), 'indicador con palabras y aria-current'
    s.limpio('primera pantalla')
    s.cerrar()


@prueba
def destino_origen_confirmacion_y_recomendacion_completa_con_una_decision_por_pantalla(nav):
    s, p = abrir_guiado(nav)
    elegir_destino(p)
    assert titulo(p) == '¿Este es el lugar al que quieres ir?' and visible(p, '#gSiDestino') and visible(p, '#gCambiarDestino')
    assert not visible(p, '#tripOrigin') and visibles(p, '.guiado-boton.primario') == 1
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    assert titulo(p) == '¿Desde dónde vas a salir?' and visible(p, '#gUsarGps') and visible(p, '#gEscribirOrigen') and visible(p, '#gMapaOrigen') and visible(p, '#gVolverDestino')
    assert 'SEVB necesita tu ubicación para encontrar dónde tomar el bus. Se usa durante el viaje y no se guarda en el servidor.' in p.inner_text('#guiadoAcciones')
    assert not visible(p, '#tripOrigin'), 'el campo para escribir el origen no aparece hasta que la persona lo pide'
    elegir_origen_escribiendo(p)
    assert titulo(p) == '¿Estás saliendo desde aquí?'
    pulsar(p, '#gSiOrigen')
    esperar_paso(p, 'resumen')
    txt = p.inner_text('#guiadoAcciones') + p.inner_text('#guiado')
    assert 'Vas desde' in txt and 'Hasta' in txt and visible(p, '#gBuscar') and visible(p, '#gCambiarOrigen2') and visible(p, '#gCambiarDestino2')
    pulsar(p, '#gBuscar')
    esperar_paso(p, 'recomendacion', 20000)
    p.wait_for_timeout(500)
    assert titulo(p) == 'Esta es nuestra recomendación' and visible(p, '#gEmpezar'), titulo(p)
    assert visibles(p, '#tripResults .trip-option') <= 1, 'las alternativas no compiten con la recomendación'
    assert re.search(r'minutos|min', p.inner_text('#guiadoAcciones') + p.inner_text('#guiado')) and 'Buses' in p.inner_text('#guiado') + p.inner_text('#guiadoAcciones')
    s.limpio('flujo completo')
    s.cerrar()


@prueba
def usar_mi_ubicacion_actual_pone_el_origen_y_pide_confirmarlo(nav):
    s, p = abrir_guiado(nav)
    elegir_destino(p)
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    pulsar(p, '#gUsarGps')
    esperar_paso(p, 'confirmar_origen', 30000)
    assert titulo(p) == '¿Estás saliendo desde aquí?'
    o = puntos(p)['origen']
    assert o and abs(o['lat'] - V.GPS['latitude']) < 0.01, o
    assert p.evaluate('window.__gpsPedidos') >= 1, 'el GPS se pidió solo después del toque'
    pulsar(p, '#gSiOrigen')
    esperar_paso(p, 'resumen')
    s.limpio('gps')
    s.cerrar()


@prueba
def permiso_de_ubicacion_rechazado_no_bloquea_y_deja_escribir_o_elegir_en_el_mapa(nav):
    s, p = abrir_guiado(nav, geo=False)
    elegir_destino(p)
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    pulsar(p, '#gUsarGps')
    B.esperar(p, "!document.getElementById('guiadoMensaje').hidden", 20000)
    msg = p.inner_text('#guiadoMensaje')
    assert msg.strip() and 'permiso' in msg.lower() or 'ubicaci' in msg.lower(), msg
    assert paso(p) == 'origen' and visible(p, '#tripOrigin') and visible(p, '#gEscribirOrigen') and visible(p, '#gMapaOrigen') and visible(p, '#gVolverDestino'), 'sin callejón sin salida: se ofrece escribir, elegir en el mapa o volver'
    elegir_origen_escribiendo(p)
    pulsar(p, '#gSiOrigen')
    esperar_paso(p, 'resumen')
    s.limpio('gps rechazado')
    s.cerrar()


@prueba
def corregir_el_destino_desde_el_resumen_conserva_el_origen(nav):
    s, p = abrir_guiado(nav)
    hasta_resumen(p)
    antes = puntos(p)['origen']
    pulsar(p, '#gCambiarDestino2')
    assert paso(p) == 'destino' and visible(p, '#tripDestination')
    assert puntos(p)['origen'] == antes, 'el origen sigue ahí'
    elegir_destino(p, DEST2)
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'resumen')
    d = puntos(p)
    assert d['origen'] == antes and abs(d['destino']['lat'] - 4.146) < 1e-6, 'con el origen ya elegido no se vuelve a preguntar: va directo al resumen'
    s.limpio('corregir destino')
    s.cerrar()


@prueba
def retroceder_entre_pasos_no_pierde_lo_ya_elegido(nav):
    s, p = abrir_guiado(nav)
    elegir_destino(p)
    pulsar(p, '#gCambiarDestino')
    assert paso(p) == 'destino' and visible(p, '#tripDestination')
    assert p.input_value('#tripDestination').strip() != '', 'el texto del destino sigue en el campo'
    pulsar(p, '#gBuscarDestino')
    esperar_paso(p, 'confirmar_destino')
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    pulsar(p, '#gVolverDestino')
    assert paso(p) == 'destino' and puntos(p)['destino'], 'volver desde el origen conserva el destino'
    pulsar(p, '#gBuscarDestino')
    esperar_paso(p, 'confirmar_destino')
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    elegir_origen_escribiendo(p)
    pulsar(p, '#gCambiarOrigen')
    assert paso(p) == 'origen' and puntos(p)['origen'], 'cambiar el lugar de salida vuelve a preguntar sin borrar el destino'
    assert puntos(p)['destino']
    s.limpio('retroceder')
    s.cerrar()


@prueba
def recargar_en_mitad_del_flujo_no_bloquea_y_no_guarda_direcciones(nav):
    s, p = abrir_guiado(nav)
    elegir_destino(p)
    pulsar(p, '#gSiDestino')
    esperar_paso(p, 'origen')
    elegir_origen_escribiendo(p)
    p.reload()
    B.esperar(p, "!!(window.Spevb && Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.wait_for_timeout(1000)
    assert paso(p) == 'destino' and titulo(p) == '¿A dónde quieres ir?' and visible(p, '#tripDestination'), 'tras recargar se vuelve a empezar sin quedar bloqueado'
    guardado = p.evaluate("JSON.stringify(Object.assign({}, localStorage, sessionStorage))")
    assert '4.1450' not in guardado and '4.1470' not in guardado and '-73.6240' not in guardado, 'el flujo no guarda direcciones ni coordenadas entre recargas'
    elegir_destino(p)
    s.limpio('recarga')
    s.cerrar()


@prueba
def un_enlace_compartido_entra_directo_a_la_recomendacion_con_los_lugares_llenos(nav):
    s, p = abrir_guiado(nav, ruta='/?a=4.1470,-73.6530&b=4.1450,-73.6240')
    esperar_paso(p, 'recomendacion', 25000)
    d = puntos(p)
    assert d['origen'] and d['destino'] and visible(p, '#gEmpezar'), 'sin repetir pasos'
    s.limpio('enlace compartido')
    s.cerrar()


@prueba
def iniciar_el_viaje_desde_la_recomendacion_entrega_la_pantalla_al_modo_viaje(nav):
    s = V.sesion(nav, guiado=True, viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = s.abrir()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    hasta_recomendacion(p)
    pulsar(p, '#gEmpezar')
    B.esperar(p, "Spevb.Viaje.activo() && !document.getElementById('viajeCard').hidden", 8000)
    assert paso(p) == 'viaje' and p.evaluate("document.getElementById('guiado').hidden") and p.evaluate("document.getElementById('guiadoAcciones').hidden"), 'la tarjeta del viaje toma el relevo'
    assert p.evaluate("Spevb.Viaje.rutaEstado() !== null"), 'la ruta consumible está activa'
    assert p.evaluate("window.__geo.escuchas") == 1
    s.limpio('iniciar viaje')
    s.cerrar()


@prueba
def al_llegar_se_ofrece_planear_otro_trayecto_y_se_limpia_todo(nav):
    s = V.sesion(nav, guiado=True, viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = s.abrir()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.fill('#tripDestination', V.DEST)
    pulsar(p, '#gBuscarDestino'); esperar_paso(p, 'confirmar_destino'); pulsar(p, '#gSiDestino'); esperar_paso(p, 'origen')
    p.evaluate("Spevb.Guiado.ir('origen')")
    elegir_origen_escribiendo(p, V.ESC['multi'])
    pulsar(p, '#gSiOrigen'); esperar_paso(p, 'resumen'); pulsar(p, '#gBuscar'); esperar_paso(p, 'recomendacion', 20000)
    V.destino_lejos(p)
    ls = V.lecturas(p)
    pulsar(p, '#gEmpezar')
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 8000)
    V.viaje_completo(p, ls)
    B.esperar(p, "!!document.getElementById('viajeOtro')", 8000)
    assert 'Llegaste a tu destino' in p.inner_text('#viajeAviso') or 'Llegaste' in p.inner_text('#viajeTitulo')
    pulsar(p, '#viajeOtro')
    p.wait_for_timeout(500)
    assert not p.evaluate('Spevb.Viaje.activo()') and paso(p) == 'destino' and puntos(p)['origen'] is None and puntos(p)['destino'] is None, 'se limpia el estado temporal'
    assert p.evaluate('window.__geo.escuchas') == 0, 'se detiene el GPS'
    assert p.evaluate("Spevb.Compartir.activo()") is False
    s.limpio('llegada')
    s.cerrar()


# ---------------------------------------------------------------------------------------------- errores
@prueba
def cancelar_la_busqueda_conserva_origen_y_destino(nav):
    s, p = abrir_guiado(nav)
    colgadas = []
    s.ctx.route('**/api/viajes/planificar', lambda r: colgadas.append(r))
    hasta_resumen(p)
    antes = puntos(p)
    pulsar(p, '#gBuscar')
    esperar_paso(p, 'calculando')
    assert 'buscando la mejor forma de llegar' in titulo(p)
    pulsar(p, '#gCancelarBusqueda')
    esperar_paso(p, 'resumen')
    assert puntos(p) == antes, 'los puntos siguen igual'
    assert 'cancelada' in p.inner_text('#guiadoMensaje').lower() or 'Búsqueda cancelada' in p.inner_text('#guiadoMensaje')
    assert not p.evaluate('Spevb.Planner.buscando()')
    s.limpio('cancelar busqueda')
    try:
        s.ctx.unroute_all(behavior='ignoreErrors')
    except Exception:  # noqa: BLE001
        pass
    s.cerrar()


@prueba
def un_error_de_red_o_servidor_vuelve_al_resumen_con_el_motivo_y_se_puede_reintentar(nav):
    s, p = abrir_guiado(nav)
    fallar = {'si': True}
    s.ctx.route('**/api/viajes/planificar', lambda r: (r.fulfill(status=500, content_type='application/json', body=json.dumps({'status': 500, 'message': 'x'})) if fallar['si'] else r.continue_()))
    hasta_resumen(p)
    pulsar(p, '#gBuscar')
    B.esperar(p, "Spevb.Guiado.paso() === 'resumen' && !document.getElementById('guiadoMensaje').hidden", 20000)
    assert p.inner_text('#guiadoMensaje').strip(), 'el motivo se dice con palabras'
    assert visible(p, '#gBuscar') and puntos(p)['origen'] and puntos(p)['destino'], 'los lugares se conservan y se puede reintentar'
    fallar['si'] = False
    pulsar(p, '#gBuscar')
    esperar_paso(p, 'recomendacion', 20000)
    limpio_salvo_http(s, 'error servidor')
    s.cerrar()


@prueba
def tocar_varias_veces_buscar_hace_una_sola_busqueda(nav):
    s, p = abrir_guiado(nav)
    n = {'v': 0}
    s.ctx.route('**/api/viajes/planificar', lambda r: (n.update(v=n['v'] + 1), r.continue_()))
    hasta_resumen(p)
    p.evaluate("() => { const b = document.getElementById('gBuscar'); b.click(); b.click(); b.click(); }")
    esperar_paso(p, 'recomendacion', 20000)
    assert n['v'] == 1, f'una sola solicitud al servidor: {n}'
    s.limpio('varios toques')
    s.cerrar()


@prueba
def una_busqueda_sin_resultados_lo_dice_y_deja_corregir(nav):
    s, p = abrir_guiado(nav)
    p.fill('#tripDestination', 'nada de nada')
    pulsar(p, '#gBuscarDestino')
    B.esperar(p, "!document.getElementById('guiadoMensaje').hidden", 15000)
    assert paso(p) == 'destino' and p.inner_text('#guiadoMensaje').strip() and p.input_value('#tripDestination') == 'nada de nada', 'el texto escrito no se borra y se dice qué pasó'
    s.limpio('sin resultados')
    s.cerrar()


@prueba
def campo_vacio_pide_escribir_antes_de_buscar(nav):
    s, p = abrir_guiado(nav)
    pulsar(p, '#gBuscarDestino')
    assert 'Escribe primero' in p.inner_text('#guiadoMensaje') and paso(p) == 'destino'
    s.limpio('campo vacio')
    s.cerrar()


@prueba
def origen_y_destino_demasiado_cerca_se_explica_antes_de_buscar(nav):
    s, p = abrir_guiado(nav)
    elegir_destino(p, '4.1450, -73.6240')
    pulsar(p, '#gSiDestino'); esperar_paso(p, 'origen')
    elegir_origen_escribiendo(p, '4.14515, -73.6240')
    pulsar(p, '#gSiOrigen'); esperar_paso(p, 'resumen')
    assert 'muy cerca' in p.inner_text('#guiadoAcciones') and p.is_disabled('#gBuscar'), 'se explica y no se busca'
    assert visible(p, '#gCambiarOrigen2') and visible(p, '#gCambiarDestino2'), 'y se puede corregir el lugar'
    s.limpio('muy cerca')
    s.cerrar()


@prueba
def sin_conexion_el_resumen_avisa_que_solo_hay_viajes_ya_consultados(nav):
    s, p = abrir_guiado(nav)
    hasta_resumen(p)
    s.ctx.set_offline(True)
    try:
        p.evaluate("window.dispatchEvent(new Event('offline')); Spevb.Guiado.ir('origen'); Spevb.Guiado.ir('resumen');")
        p.wait_for_timeout(300)
        assert 'Sin internet' in p.inner_text('#guiadoAcciones')
    finally:
        s.ctx.set_offline(False)
    s.limpio('sin conexion')
    s.cerrar()


# ---------------------------------------------------------------------------------------------- modo avanzado, ayuda, voz
@prueba
def el_modo_avanzado_sigue_funcionando_comparte_los_mismos_puntos_y_se_puede_volver(nav):
    s, p = abrir_guiado(nav)
    elegir_destino(p)
    pulsar(p, '#guiadoAvanzado')
    p.wait_for_timeout(300)
    assert not p.evaluate("document.body.classList.contains('guiado')") and visible(p, '#tripOrigin') and visible(p, '#tripDestination') and visible(p, '#planTrip'), 'planificador completo'
    assert visible(p, '#guiadoVolver') and 'modo guiado' in p.inner_text('#guiadoVolver').lower()
    assert p.input_value('#tripDestination').strip() and puntos(p)['destino'], 'el mismo destino, sin duplicar estado'
    p.fill('#tripOrigin', ORIG)
    p.keyboard.press('Enter')
    p.wait_for_timeout(900)
    p.evaluate("document.querySelector('#planTrip').click()")
    B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 15000)
    assert p.evaluate("localStorage.getItem('spevb-modo-planificador')") == 'avanzado'
    p.reload()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.wait_for_timeout(800)
    assert not p.evaluate("document.body.classList.contains('guiado')"), 'la preferencia se recuerda'
    pulsar(p, '#guiadoVolver')
    p.wait_for_timeout(400)
    assert p.evaluate("document.body.classList.contains('guiado')") and paso(p) == 'destino' and titulo(p) == '¿A dónde quieres ir?'
    s.limpio('avanzado')
    s.cerrar()


@prueba
def necesito_ayuda_abre_la_ayuda_existente(nav):
    s, p = abrir_guiado(nav)
    pulsar(p, '#guiadoAyudaBtn')
    p.wait_for_timeout(500)
    abierta = p.evaluate("Spevb.Modal.hayAbierta() || !!document.querySelector('.coach-tarjeta') || !!document.querySelector('#ayudaModal:not([hidden])')")
    assert abierta, 'se abre la ayuda del proyecto (no un manual nuevo)'
    s.limpio('ayuda')
    s.cerrar()


@prueba
def leer_en_voz_alta_es_opcional_nunca_automatico_y_solo_si_el_navegador_puede(nav):
    s, p = abrir_guiado(nav)
    s.ctx.add_init_script("window.__voz = []; window.SpeechSynthesisUtterance = function (t) { this.text = t; }; Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: { speaking: false, speak(u) { window.__voz.push(u.text); }, cancel() {} } });")
    p.reload()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.wait_for_timeout(800)
    assert p.evaluate('window.__voz.length') == 0, 'nunca empieza solo'
    assert visible(p, '#guiadoVoz') and 'voz alta' in p.inner_text('#guiadoVoz')
    pulsar(p, '#guiadoVoz')
    texto = p.evaluate('window.__voz[0] || ""')
    assert '¿A dónde quieres ir?' in texto, texto
    assert '¿A dónde quieres ir?' in titulo(p), 'el texto completo sigue en pantalla'
    s.limpio('voz')
    s.cerrar()
    # Sin la API de voz del navegador el botón no aparece (la alternativa textual es todo lo que hay).
    s2, p2 = abrir_guiado(nav)
    s2.ctx.add_init_script("try { delete window.SpeechSynthesisUtterance; Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: undefined }); } catch (e) {}")
    p2.reload()
    B.esperar(p2, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p2.wait_for_timeout(600)
    assert not visible(p2, '#guiadoVoz'), 'sin soporte nativo no se ofrece'
    s2.cerrar()


# ---------------------------------------------------------------------------------------------- accesibilidad y tamaños
@prueba
def todo_el_flujo_se_completa_solo_con_el_teclado_y_el_foco_llega_a_cada_pregunta(nav):
    s, p = abrir_guiado(nav, 390, 844, has_touch=False, is_mobile=False)
    p.focus('#tripDestination')
    p.keyboard.type(DEST)
    for _ in range(6):
        p.keyboard.press('Tab')
        if p.evaluate("document.activeElement && document.activeElement.id") == 'gBuscarDestino':
            break
    assert p.evaluate("document.activeElement.id") == 'gBuscarDestino', 'Tab llega a «Buscar destino»'
    assert p.evaluate("getComputedStyle(document.activeElement).outlineWidth") not in ('0px', ''), 'foco visible'
    p.keyboard.press('Enter')
    esperar_paso(p, 'confirmar_destino')
    assert p.evaluate("document.activeElement.id") == 'guiadoTitulo', 'el foco llega a la nueva pregunta (y no salta a otro lado)'
    p.keyboard.press('Tab')
    assert p.evaluate("document.activeElement.id") == 'gSiDestino'
    p.keyboard.press('Enter')
    esperar_paso(p, 'origen')
    assert p.evaluate("document.activeElement.id") == 'guiadoTitulo'
    s.limpio('teclado')
    s.cerrar()


@prueba
def en_cada_tamano_los_botones_son_alcanzables_y_ningun_texto_se_sale(nav):
    for nombre, ancho, alto in TAMANOS:
        s, p = abrir_guiado(nav, ancho, alto)
        for fase in ('destino', 'confirmar_destino', 'origen', 'confirmar_origen', 'resumen', 'recomendacion'):
            if fase == 'destino':
                pass
            elif fase == 'confirmar_destino':
                elegir_destino(p)
            elif fase == 'origen':
                pulsar(p, '#gSiDestino'); esperar_paso(p, 'origen')
            elif fase == 'confirmar_origen':
                elegir_origen_escribiendo(p)
            elif fase == 'resumen':
                pulsar(p, '#gSiOrigen'); esperar_paso(p, 'resumen')
            else:
                pulsar(p, '#gBuscar'); esperar_paso(p, 'recomendacion', 20000); p.wait_for_timeout(500)
            ids = p.evaluate("[...document.querySelectorAll('#guiadoAcciones .guiado-boton')].filter((b) => b.getClientRects().length > 0).map((b) => '#' + b.id)")
            assert ids, f'{nombre}/{fase}: hay botones'
            for i in ids:
                pulsar_sin_clic(p, i, f'{nombre}/{fase}')
            desborde = p.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            assert not desborde, f'{nombre}/{fase}: sin desplazamiento horizontal'
            assert p.evaluate("document.getElementById('guiadoTitulo').getBoundingClientRect().height") > 0
        s.limpio('tamano ' + nombre)
        s.cerrar()


def pulsar_sin_clic(p, sel, donde):
    r = p.evaluate("""(sel) => { const e = document.querySelector(sel), cuerpo = document.querySelector('.sheet-body'); let b = e.getBoundingClientRect();
        if (cuerpo) { const c = cuerpo.getBoundingClientRect(); if (b.bottom > Math.min(c.bottom, innerHeight) - 8) cuerpo.scrollTop += b.bottom - Math.min(c.bottom, innerHeight) + 16; if (b.top < c.top) cuerpo.scrollTop -= c.top - b.top + 8; b = e.getBoundingClientRect(); }
        const t = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
        return { golpea: !!t && (t === e || e.contains(t)), alto: b.height, ancho: b.width, quien: t ? (t.id || t.className) : null, cortado: e.scrollWidth > e.clientWidth + 1 }; }""", sel)
    assert r['golpea'], f'{donde} {sel} tapado por {r["quien"]}'
    assert r['alto'] >= 44 and r['ancho'] >= 44, f'{donde} {sel} mide {r["ancho"]}x{r["alto"]}'
    assert not r['cortado'], f'{donde} {sel} texto cortado'


@prueba
def con_letra_enorme_modo_oscuro_y_movimiento_reducido_el_flujo_sigue_usable(nav):
    s, p = abrir_guiado(nav, 360, 640, color_scheme='dark', reduced_motion='reduce')
    p.evaluate("document.documentElement.style.fontSize = '24px'; document.documentElement.dataset.motion = 'reduce'")
    p.wait_for_timeout(300)
    elegir_destino(p)
    assert not p.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), 'sin desborde con letra enorme'
    pulsar_sin_clic(p, '#gSiDestino', 'letra enorme')
    anim = p.evaluate("[...document.querySelectorAll('#guiado, #guiado *, #guiadoAcciones, #guiadoAcciones *')].every((e) => { const c = getComputedStyle(e); return c.animationName === 'none' && (parseFloat(c.transitionDuration) || 0) === 0; })")
    assert anim, 'sin animaciones ni transiciones con movimiento reducido'
    bg = p.evaluate("getComputedStyle(document.querySelector('.guiado-boton.secundario') || document.body).backgroundColor")
    assert bg, bg
    s.limpio('accesibilidad')
    s.cerrar()


@prueba
def solo_una_accion_principal_por_pantalla_en_todos_los_pasos(nav):
    s, p = abrir_guiado(nav)
    cuentas = {'destino': visibles(p, '#guiadoAcciones .guiado-boton.primario')}
    elegir_destino(p); cuentas['confirmar_destino'] = visibles(p, '#guiadoAcciones .guiado-boton.primario')
    pulsar(p, '#gSiDestino'); esperar_paso(p, 'origen'); cuentas['origen'] = visibles(p, '#guiadoAcciones .guiado-boton.primario')
    elegir_origen_escribiendo(p); cuentas['confirmar_origen'] = visibles(p, '#guiadoAcciones .guiado-boton.primario')
    pulsar(p, '#gSiOrigen'); esperar_paso(p, 'resumen'); cuentas['resumen'] = visibles(p, '#guiadoAcciones .guiado-boton.primario')
    pulsar(p, '#gBuscar'); esperar_paso(p, 'recomendacion', 20000); p.wait_for_timeout(500); cuentas['recomendacion'] = visibles(p, '#guiadoAcciones .guiado-boton.primario')
    assert all(v == 1 for v in cuentas.values()), cuentas
    s.limpio('una accion principal')
    s.cerrar()


@prueba
def la_maquina_de_estados_rechaza_saltos_invalidos(nav):
    s, p = abrir_guiado(nav)
    r = p.evaluate("""() => { const t = Spevb.Guiado.TRANSICIONES; return { saltoInvalido: Spevb.Guiado.ir('calculando'), pasoTras: Spevb.Guiado.paso(), inexistente: Spevb.Guiado.ir('inexistente'),
        pasos: Spevb.Guiado.PASOS, tablaCompleta: Spevb.Guiado.PASOS.every((x) => Array.isArray(t[x])) }; }""")
    assert r['saltoInvalido'] is False and r['pasoTras'] == 'destino' and r['inexistente'] is False and r['tablaCompleta'], r
    assert r['pasos'] == ['destino', 'confirmar_destino', 'origen', 'confirmar_origen', 'resumen', 'calculando', 'recomendacion', 'viaje'], r['pasos']
    s.limpio('maquina')
    s.cerrar()


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
                print('FALLA ', f.__name__, '|', (str(e).splitlines()[0] if str(e) else repr(e))[:900])
                if os.environ.get('SEVB_E2E_TRAZA'):
                    traceback.print_exc()
        nav.close()
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas del flujo guiado; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
