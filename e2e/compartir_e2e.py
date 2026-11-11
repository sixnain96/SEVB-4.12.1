"""Pruebas de navegador de «Compartir mi viaje» (4.15): diálogo, creación, envío limitado, revocación, llegada y la página pública /seguir.html.

Frontend real; backend = stub con el MISMO contrato que ViajeCompartidoController (el servidor real y su SQL se prueban en Java); GPS SIMULADO.
NO prueba WhatsApp ni Web Share de un teléfono real (se simula navigator.share) ni la red móvil.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/compartir_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
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
AVISO = 'Las personas con el enlace podrán ver tu avance aproximado durante este viaje. El enlace dejará de funcionar cuando termines o dejes de compartir.'


def prueba(f):
    PRUEBAS.append(f)
    return f


def log_compartir(p):
    return p.evaluate("fetch('/__log/compartir').then(r => r.json())")


def tokens(p):
    return p.evaluate("JSON.parse(localStorage.getItem('spevb-compartir') || 'null')")


def leer_publico(p, lectura):
    return p.evaluate("(t) => fetch('/api/compartir', { headers: { 'X-Seguimiento': t } }).then(async (r) => ({ status: r.status, cuerpo: r.status === 200 ? await r.json() : null }))", lectura)


def limpio_salvo_4xx(s, que):
    """Estas pruebas provocan a propósito respuestas 400/404 (token ajeno, enlace revocado): el navegador las anota como error de consola; cualquier OTRO error sí falla."""
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio(que)


def con_viaje(nav, escenario='multi', **opts):
    s = V.sesion(nav, **opts)
    p = s.abrir()
    p.evaluate("fetch('/__log/limpiar')")
    V.planear(p, escenario)
    V.destino_lejos(p)
    ls = V.lecturas(p)
    V.iniciar(p)
    return s, p, ls


def abrir_dialogo(p):
    if p.get_attribute('#viajeMas', 'aria-expanded') != 'true':
        p.click('#viajeMas')
    p.click('#viajeCompartir')
    p.wait_for_timeout(300)


def crear_enlace(p):
    abrir_dialogo(p)
    p.click('#compCrear')
    V.B.esperar(p, "!!JSON.parse(localStorage.getItem('spevb-compartir') || 'null')", 6000)
    p.wait_for_timeout(300)
    return tokens(p)


@prueba
def sin_ruta_valida_el_servidor_no_crea_nada_y_sin_viaje_no_hay_enlace(nav):
    s = V.sesion(nav)
    p = s.abrir()
    r = p.evaluate("fetch('/api/compartir', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ruta: null }) }).then((r) => r.status)")
    assert r == 400, f'sin viaje en curso no se crea: {r}'
    assert p.evaluate("Spevb.Compartir.activo()") is False and p.evaluate("document.getElementById('viajeCard').hidden"), 'sin viaje la tarjeta ni el enlace existen'
    limpio_salvo_4xx(s, 'sin viaje')
    s.cerrar()


@prueba
def el_dialogo_explica_la_privacidad_y_cancelar_no_crea_nada(nav):
    s, p, ls = con_viaje(nav)
    abrir_dialogo(p)
    assert p.inner_text('#compTitulo') == 'Compartir mi viaje' and p.inner_text('#compAviso').strip() == AVISO, p.inner_text('#compAviso')
    assert p.inner_text('#compCrear').strip() == 'Crear enlace' and p.inner_text('#compCancelar').strip() == 'Cancelar'
    for sel in ('#compCrear', '#compCancelar'):
        b = p.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.width, r.height]; }", sel)
        assert b[1] >= 44 and b[0] >= 44, f'{sel} objetivo táctil: {b}'
    p.click('#compCancelar')
    p.wait_for_timeout(300)
    assert not p.evaluate("Spevb.Modal.abierta(document.getElementById('compartirModal'))") and not any(x['metodo'] == 'POST' for x in log_compartir(p)), 'cancelar no crea nada'
    s.limpio('dialogo')
    s.cerrar()


@prueba
def el_dialogo_se_maneja_con_teclado_y_escape_lo_cierra(nav):
    s, p, ls = con_viaje(nav)
    abrir_dialogo(p)
    dentro = p.evaluate("(() => { const d = document.getElementById('compartirModal'); return d.contains(document.activeElement); })()")
    assert dentro, 'el foco entra al diálogo'
    for _ in range(12):
        p.keyboard.press('Tab')
        assert p.evaluate("document.getElementById('compartirModal').contains(document.activeElement)"), 'Tab no sale del diálogo'
    p.keyboard.press('Escape')
    p.wait_for_timeout(300)
    assert not p.evaluate("Spevb.Modal.abierta(document.getElementById('compartirModal'))"), 'Escape cierra'
    s.limpio('teclado')
    s.cerrar()


@prueba
def crear_el_enlace_muestra_copiar_whatsapp_y_el_enlace_con_el_token_en_el_fragmento(nav):
    s, p, ls = con_viaje(nav)
    p.evaluate("Object.defineProperty(navigator, 'share', { configurable: true, value: (d) => { window.__compartido = d; return Promise.resolve(); } })")
    t = crear_enlace(p)
    assert t and re.fullmatch(r'[A-Za-z0-9_-]{43}', t['lectura']) and re.fullmatch(r'[A-Za-z0-9_-]{43}', t['escritura']) and t['lectura'] != t['escritura'], t
    enlace = p.input_value('#compEnlace')
    assert enlace.endswith('/seguir.html#' + t['lectura']) and t['escritura'] not in enlace, f'el enlace solo lleva el token de lectura, en el fragmento: {enlace}'
    wa = p.get_attribute('#compWhatsapp', 'href')
    assert wa.startswith('https://wa.me/?text=') and 'seguir.html' in wa and t['escritura'] not in wa, wa
    assert p.get_attribute('#compWhatsapp', 'rel') == 'noopener noreferrer'
    assert p.is_visible('#compCopiar') and p.is_visible('#compDejar') and p.is_visible('#compCompartir'), 'copiar, dejar de compartir y compartir (hay Web Share)'
    p.click('#compCompartir')
    p.wait_for_timeout(200)
    assert p.evaluate("window.__compartido && window.__compartido.url") == enlace, 'Web Share recibe el enlace'
    p.evaluate("(() => { try { navigator.clipboard.writeText = () => Promise.reject(new Error('sin permiso')); } catch (e) {} return 1; })()")
    p.click('#compCopiar')
    p.wait_for_timeout(200)
    assert 'copia' in p.inner_text('#compEstado').lower(), 'si el portapapeles falla queda el respaldo de seleccionar y copiar'
    assert not any(t['lectura'] in x['ruta'] or t['escritura'] in x['ruta'] for x in log_compartir(p)), 'ningún token viaja en una URL de la API'
    s.limpio('crear')
    s.cerrar()


@prueba
def sin_web_share_el_boton_compartir_no_aparece_y_quedan_los_respaldos(nav):
    s, p, ls = con_viaje(nav)
    p.evaluate("Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })")
    crear_enlace(p)
    vis = {k: p.is_visible(k) for k in ('#compCompartir', '#compCopiar', '#compWhatsapp')}
    assert not vis['#compCompartir'] and vis['#compCopiar'] and vis['#compWhatsapp'], f'sin Web Share: {vis}, share={p.evaluate("typeof navigator.share")}'
    s.limpio('sin web share')
    s.cerrar()


@prueba
def el_enlace_de_lectura_no_puede_actualizar_ni_revocar(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    r = p.evaluate("""(t) => Promise.all([
        fetch('/api/compartir', { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Seguimiento-Escritura': t }, body: JSON.stringify({ fase: 'llegaste', leg: 0, progreso: 1 }) }).then((r) => r.status),
        fetch('/api/compartir', { method: 'DELETE', headers: { 'X-Seguimiento-Escritura': t } }).then((r) => r.status)])""", t['lectura'])
    assert r[0] == 404, f'el token de lectura no sirve para actualizar: {r}'
    assert leer_publico(p, t['lectura'])['status'] == 200, 'y tampoco lo revocó (DELETE con el token de lectura no hace nada)'
    limpio_salvo_4xx(s, 'lectura no escribe')
    s.cerrar()


@prueba
def el_envio_es_limitado_y_la_vista_publica_cambia_con_el_viaje(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    i = V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(600)
    antes = len([x for x in log_compartir(p) if x['metodo'] == 'PUT'])
    pub = leer_publico(p, t['lectura'])
    assert pub['status'] == 200 and pub['cuerpo']['fase'] in ('caminar', 'esperando') and pub['cuerpo'].get('posicion'), f'la vista pública trae fase y posición: {pub}'
    assert pub['cuerpo']['progreso'] > 0, pub
    p.evaluate("(ls) => SimGps.alimentar(ls, 0)", ls[i:i + 80])      # 80 lecturas crudas seguidas
    p.wait_for_timeout(600)
    despues = len([x for x in log_compartir(p) if x['metodo'] == 'PUT'])
    assert despues - antes <= 4, f'80 lecturas crudas no son 80 envíos: {antes} → {despues}'
    assert 'Última actualización' in p.inner_text('#compEstado') or 'Última actualización' in p.inner_text('#viajeCompartirEstado')
    s.limpio('envio limitado')
    s.cerrar()


@prueba
def sin_internet_se_conserva_el_viaje_y_al_volver_se_envia_solo_lo_ultimo(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    i = V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(400)
    p.context.set_offline(True)
    try:
        p.evaluate("window.dispatchEvent(new Event('offline'))")
        i = V.alimentar(p, ls, i, 'pregunta')
        n_off = len([x for x in log_compartir(p) if x['metodo'] == 'PUT']) if False else None
    finally:
        p.context.set_offline(False)
    assert p.evaluate("Spevb.Viaje.activo()") and p.evaluate("!document.getElementById('viajeCard').hidden"), 'el viaje local continúa sin internet'
    antes = len(log_compartir(p))
    p.evaluate("window.dispatchEvent(new Event('online'))")
    p.wait_for_timeout(800)
    assert len(log_compartir(p)) - antes <= 2, 'al volver la conexión se manda el estado más reciente, no una cola'
    assert leer_publico(p, t['lectura'])['status'] == 200
    s.limpio('sin internet')
    s.cerrar()


@prueba
def dejar_de_compartir_cierra_el_enlace_de_inmediato(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    assert 'quedó listo' in p.inner_text('#compOk')
    p.click('#compCerrar')
    p.wait_for_timeout(300)
    assert p.is_visible('#viajeCompartiendo') and p.inner_text('#viajeDejarCompartir').strip() == 'Dejar de compartir', 'la tarjeta muestra que se comparte y cómo dejar de hacerlo'
    p.click('#viajeDejarCompartir')
    p.wait_for_timeout(300)
    assert 'dejar de compartir' in p.inner_text('#compConfirmarTxt').lower() and p.is_visible('#compSiDejar') and p.is_visible('#compNoDejar'), 'antes de revocar se pide confirmación'
    assert leer_publico(p, t['lectura'])['status'] == 200, 'sin confirmar, el enlace sigue vivo'
    p.click('#compNoDejar')
    p.wait_for_timeout(200)
    assert leer_publico(p, t['lectura'])['status'] == 200 and p.evaluate("Spevb.Compartir.activo()") is True, 'No, seguir compartiendo no revoca'
    p.click('#compDejar')
    p.wait_for_timeout(200)
    p.click('#compSiDejar')
    p.wait_for_timeout(500)
    assert leer_publico(p, t['lectura'])['status'] == 404, 'revocado: el enlace deja de existir'
    assert p.evaluate("Spevb.Compartir.activo()") is False and tokens(p) is None and not p.is_visible('#viajeCompartiendo')
    limpio_salvo_4xx(s, 'dejar')
    s.cerrar()


@prueba
def terminar_el_viaje_cierra_el_enlace(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    p.click('#compCerrar')
    p.evaluate("Spevb.Viaje.detener()")
    p.wait_for_timeout(900)
    assert leer_publico(p, t['lectura'])['status'] == 404 and tokens(p) is None, 'al terminar el viaje no queda un enlace huérfano'
    limpio_salvo_4xx(s, 'terminar')
    s.cerrar()


@prueba
def al_llegar_el_enlace_muestra_llego_y_ya_no_expone_coordenadas(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    p.click('#compCerrar')
    V.viaje_completo(p, ls)
    p.wait_for_timeout(1200)
    pub = leer_publico(p, t['lectura'])
    assert pub['status'] == 200 and pub['cuerpo']['estado'] == 'llego' and 'posicion' not in pub['cuerpo'] and pub['cuerpo']['progreso'] == 1, f'llegó: sin posición: {pub}'
    assert tokens(p) is None and p.evaluate("Spevb.Compartir.activo()") is False, 'al llegar el teléfono deja de enviar'
    s.limpio('llegada')
    s.cerrar()


@prueba
def la_pagina_publica_es_solo_lectura_accesible_y_con_privacidad(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(600)
    pub = s.ctx.new_page()
    pub.set_viewport_size({'width': 360, 'height': 640})
    pub.goto(B.URL.rstrip('/') + '/seguir.html#' + t['lectura'])
    B.esperar(pub, "document.getElementById('estado').textContent.length > 5 && !/Buscando/.test(document.getElementById('estado').textContent)", 8000)
    txt = pub.inner_text('#estado')
    assert re.search(r'caminar|esperando|bus|destino', txt, re.I), txt
    assert pub.evaluate("document.querySelectorAll('form, input, textarea, select, button').length") == 0, 'solo lectura: ninguna herramienta ni formulario'
    assert pub.evaluate("document.querySelector('meta[name=robots]').content").startswith('noindex') and pub.evaluate("document.querySelector('meta[name=referrer]').content") == 'no-referrer'
    assert pub.evaluate("!document.querySelector('meta[property^=\"og:\"], meta[name^=\"twitter:\"]')"), 'sin metadatos sociales'
    assert pub.evaluate("document.documentElement.lang") == 'es' and pub.evaluate("!!document.querySelector('main') && !!document.querySelector('h1')")
    assert pub.evaluate("document.getElementById('barra').getAttribute('role')") == 'progressbar'
    assert pub.evaluate("document.documentElement.scrollWidth <= innerWidth"), 'sin desplazamiento horizontal a 360 px'
    assert pub.evaluate("!!document.querySelector('#mapa polyline') && !!document.querySelector('#mapa .seg-yo')"), 'se ve el recorrido y dónde va'
    assert t['escritura'] not in pub.content(), 'la página nunca contiene el token de escritura'
    # token inválido, mal formado o inexistente: el mismo mensaje genérico
    for frag in ('malo', 'A' * 43):
        otra = s.ctx.new_page()
        otra.goto(B.URL.rstrip('/') + '/seguir.html#' + frag)
        B.esperar(otra, "document.getElementById('estado').textContent.includes('ya no está disponible')", 6000)
        assert 'Puede haber terminado' in otra.inner_text('#detalle')
        otra.close()
    pub.close()
    s.limpio('publica')
    s.cerrar()


@prueba
def si_la_ultima_actualizacion_es_vieja_la_pagina_pide_esperar_una_nueva_senal(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(600)
    pub = s.ctx.new_page()
    pub.add_init_script("const _n = Date.now.bind(Date); Date.now = () => _n() + 200000;")
    pub.goto(B.URL.rstrip('/') + '/seguir.html#' + t['lectura'])
    B.esperar(pub, "!document.getElementById('aviso').hidden", 8000)
    assert 'Esperando una nueva señal' in pub.inner_text('#aviso') and 'Última actualización' in pub.inner_text('#actualizado')
    pub.close()
    s.limpio('vieja')
    s.cerrar()


@prueba
def el_enlace_vencido_responde_igual_que_uno_inexistente(nav):
    s, p, ls = con_viaje(nav)
    t = crear_enlace(p)
    i = V.alimentar(p, ls, 0, 'fase:esperando')
    p.evaluate("fetch('/__compartir/vencer')")
    p.wait_for_timeout(300)
    assert leer_publico(p, t['lectura'])['status'] == 404
    V.alimentar(p, ls[:i + 6], i)
    p.evaluate("window.dispatchEvent(new Event('online'))")
    p.wait_for_timeout(900)
    assert p.evaluate("Spevb.Compartir.activo()") is False, 'si el servidor dice que ya no existe, el teléfono deja de enviar'
    limpio_salvo_4xx(s, 'vencido')
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
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas de compartir el viaje; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
