"""Pruebas de navegador de la BÚSQUEDA de direcciones y de la CONFIRMACIÓN de A/B (contrato B.2–B.4 y C de docs/CONTRATO-RECOMENDACION-Y-BUSQUEDA.md).

Verifican comportamientos del producto con un navegador real contra el servidor simulado (e2e/stub_server.py): sugerencias que no reaparecen tras
confirmar, respuestas tardías o retenidas, errores por estado, elección fallida sin sustitución silenciosa, una sesión de Places por búsqueda,
composición de texto, intercambio A↔B y ocultar el panel con sugerencias abiertas. Este stub NO es el backend Java: el orden de proveedores
(Google → ArcGIS → local) lo prueban las pruebas Java; aquí se prueba lo que el NAVEGADOR hace con lo que recibe.

Uso: SEVB_E2E_URL=http://127.0.0.1:18110/ python e2e/busqueda_e2e.py [filtro]
Las pruebas que controlan «respuesta tardía» retienen la petición con Playwright (route) y la sueltan cuando quieren.
"""
import json
import os
import sys
import traceback
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
ID = {'origin': 'tripOrigin', 'destination': 'tripDestination'}


def prueba(f):
    PRUEBAS.append(f)
    return f


class Retenidas:
    """Retiene las peticiones que coincidan con el patrón hasta llamar a liberar() (o las deja pasar con soltar())."""

    def __init__(self, ctx, patron):
        self.pend = []
        self.activo = True
        ctx.route(patron, self._manejar)

    def _manejar(self, route):
        if self.activo:
            self.pend.append(route)
        else:
            route.continue_()

    def liberar(self, indice=None):
        lista = self.pend if indice is None else [self.pend[indice]]
        for r in lista:
            try:
                r.continue_()
            except Exception:  # noqa: BLE001
                pass
        if indice is None:
            self.pend = []

    def soltar(self):
        self.activo = False
        self.liberar()


def sesion(nav, **opts):
    s = B.Sesion(nav, **opts)
    p = s.abrir()
    limpiar_log()
    return s, p


def registro():
    return json.loads(urllib.request.urlopen(B.URL + '__log/busqueda').read())


def limpiar_log():
    urllib.request.urlopen(B.URL + '__log/limpiar').read()


def consultas(ruta=None):
    return [r for r in registro() if ruta is None or r['ruta'] == ruta]


def lista(p, modo):
    return p.locator(f'#{modo}Results .autosuggest-option')


def esperar_lista(p, modo, timeout=8000):
    B.esperar(p, f"document.querySelectorAll('#{modo}Results .autosuggest-option').length > 0", timeout)


def punto(p, modo):
    return p.evaluate("(m) => { const q = Spevb.Planner.puntos(); return q[m] && q[m].nombre; }", 'origen' if modo == 'origin' else 'destino')


def aria(p, modo):
    return p.evaluate(f"document.getElementById('{ID[modo]}').getAttribute('aria-expanded')")


def confirmar_por_sugerencia(p, modo='origin', texto='Carrera 22'):
    p.fill('#' + ID[modo], texto)
    esperar_lista(p, modo)
    lista(p, modo).first.click()
    B.esperar(p, f"!!Spevb.Planner.puntos()['{'origen' if modo == 'origin' else 'destino'}']", 6000)
    p.wait_for_timeout(300)


# ------------------------------------------------------------------------------------------------ confirmar cierra todo y se queda cerrado
@prueba
def sugerencias_no_reaparecen_tras_confirmar_ni_por_foco_ni_por_pasar_el_tiempo(nav):
    s, p = sesion(nav)
    confirmar_por_sugerencia(p)
    hechas = len(consultas('sugerencias'))
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false', 'al confirmar la lista se cierra y se vacía'
    assert p.evaluate("document.getElementById('tripOrigin').hasAttribute('aria-activedescendant')") is False
    # foco, desenfoque, foco otra vez, cambio de layout: nada de eso consulta ni reabre
    p.click('#tripOrigin'); p.wait_for_timeout(700)
    p.click('#tripDestination'); p.wait_for_timeout(300)
    p.click('#tripOrigin'); p.wait_for_timeout(900)
    p.set_viewport_size({'width': 900, 'height': 700}); p.wait_for_timeout(500)
    assert len(consultas('sugerencias')) == hechas, f'consultas nuevas tras confirmar: {consultas()}'
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false'
    assert punto(p, 'origin'), 'el punto sigue confirmado'
    s.limpio('confirmar'); s.cerrar()


@prueba
def enter_sobre_un_punto_confirmado_no_vuelve_a_buscar_ni_reabre_la_lista(nav):
    s, p = sesion(nav)
    confirmar_por_sugerencia(p)
    antes = len(registro())
    p.focus('#tripOrigin'); p.keyboard.press('Enter'); p.wait_for_timeout(900)
    p.click('#searchOrigin'); p.wait_for_timeout(900)
    assert len(registro()) == antes, f'Enter o «Buscar» sobre un punto confirmado no deben consultar: {registro()[antes:]}'
    assert lista(p, 'origin').count() == 0 and punto(p, 'origin')
    s.limpio('enter confirmado'); s.cerrar()


@prueba
def un_evento_input_sin_cambio_no_invalida_el_punto_confirmado(nav):
    """Autocompletado del navegador, dictado o composición terminada pueden emitir «input» sin cambiar el texto."""
    s, p = sesion(nav)
    confirmar_por_sugerencia(p)
    antes = len(registro())
    p.evaluate("document.getElementById('tripOrigin').dispatchEvent(new Event('input', { bubbles: true }))")
    p.wait_for_timeout(900)
    assert punto(p, 'origin'), 'el punto confirmado debe seguir ahí'
    assert len(registro()) == antes and lista(p, 'origin').count() == 0
    s.limpio('input sin cambio'); s.cerrar()


@prueba
def editar_de_verdad_un_punto_confirmado_lo_invalida_y_reactiva_la_busqueda(nav):
    s, p = sesion(nav)
    confirmar_por_sugerencia(p)
    antes = len(consultas('sugerencias'))
    p.click('#tripOrigin'); p.keyboard.press('End'); p.keyboard.type(' bis')
    esperar_lista(p, 'origin')
    assert punto(p, 'origin') is None, 'editar el texto invalida el punto confirmado'
    assert len(consultas('sugerencias')) == antes + 1, 'una sola consulta por la edición (con su espera)'
    s.limpio('editar confirmado'); s.cerrar()


@prueba
def pegar_texto_consulta_una_vez_y_no_por_cada_letra(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'Avenida Catama con carrera 40')
    esperar_lista(p, 'origin')
    p.wait_for_timeout(700)
    assert len(consultas('sugerencias')) == 1, consultas()
    s.limpio('pegar'); s.cerrar()


# ------------------------------------------------------------------------------------------------ respuestas tardías
@prueba
def una_respuesta_retenida_no_reabre_la_lista_despues_de_confirmar_otro_punto(nav):
    s, p = sesion(nav)
    ret = Retenidas(s.ctx, '**/api/lugares/sugerencias*')
    p.fill('#tripOrigin', 'Calle 38 con carrera 22')
    p.wait_for_timeout(900)
    assert ret.pend, 'la consulta quedó retenida'
    p.evaluate("Spevb.Planner.poner('origin', { id: null, lat: 4.1450, lng: -73.6540, nombre: 'Favorito Casa', direccion: null, fuente: 'Favorito', confirmado: true })")
    ret.liberar(); p.wait_for_timeout(900)
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false', 'la respuesta tardía no debe reabrir la lista'
    assert punto(p, 'origin') == 'Favorito Casa', 'ni reemplazar lo confirmado'
    s.limpio('respuesta retenida'); s.cerrar()


@prueba
def borrar_el_texto_antes_de_la_respuesta_no_deja_sugerencias(nav):
    s, p = sesion(nav)
    ret = Retenidas(s.ctx, '**/api/lugares/sugerencias*')
    p.fill('#tripOrigin', 'Calle 38 con carrera 22'); p.wait_for_timeout(900)
    p.fill('#tripOrigin', ''); p.wait_for_timeout(200)
    ret.liberar(); p.wait_for_timeout(800)
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false'
    s.limpio('borrar antes'); s.cerrar()


@prueba
def intercambiar_A_y_B_con_consultas_pendientes_no_reabre_listas(nav):
    s, p = sesion(nav)
    confirmar_por_sugerencia(p, 'origin', 'Carrera 22')
    ret = Retenidas(s.ctx, '**/api/lugares/sugerencias*')
    p.fill('#tripDestination', 'Calle 10 sur'); p.wait_for_timeout(900)
    p.click('#swapTrip'); p.wait_for_timeout(300)
    ret.liberar(); p.wait_for_timeout(900)
    assert lista(p, 'destination').count() == 0 and lista(p, 'origin').count() == 0, 'ninguna lista debe reabrirse tras intercambiar'
    assert p.input_value('#tripDestination').startswith('Carrera 22') and p.input_value('#tripOrigin') == 'Calle 10 sur'
    s.limpio('intercambiar'); s.cerrar()


@prueba
def ocultar_el_panel_con_sugerencias_abiertas_las_cierra_y_cancela_lo_pendiente(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'Carrera 30'); esperar_lista(p, 'origin')
    p.click('#panelHide'); p.wait_for_timeout(400)
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false', 'con el panel oculto no deben quedar sugerencias abiertas'
    ret = Retenidas(s.ctx, '**/api/lugares/sugerencias*')
    p.click('#panelShow'); p.wait_for_timeout(300)
    p.fill('#tripOrigin', 'Carrera 31'); p.wait_for_timeout(900)
    p.click('#panelHide'); p.wait_for_timeout(300)
    ret.liberar(); p.wait_for_timeout(700)
    assert lista(p, 'origin').count() == 0, 'una respuesta que llega con el panel oculto no reabre la lista'
    s.limpio('ocultar panel'); s.cerrar()


# ------------------------------------------------------------------------------------------------ formas de confirmar
@prueba
def seleccionar_con_flechas_y_enter_o_con_toque_confirma_y_cierra(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'Carrera 22'); esperar_lista(p, 'origin')
    p.keyboard.press('ArrowDown'); p.keyboard.press('Enter')
    B.esperar(p, "!!Spevb.Planner.puntos().origen", 6000)
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false'
    p.fill('#tripDestination', 'Calle 10'); esperar_lista(p, 'destination')
    lista(p, 'destination').first.click()
    B.esperar(p, "!!Spevb.Planner.puntos().destino", 6000)
    assert lista(p, 'destination').count() == 0 and punto(p, 'origin') and punto(p, 'destination')
    s.limpio('flechas'); s.cerrar()


@prueba
def coordenadas_favorito_y_punto_en_el_mapa_se_resuelven_sin_consultar_proveedores(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', '4.1450, -73.6540'); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    assert punto(p, 'origin') and lista(p, 'origin').count() == 0
    assert not consultas('lugares') and not consultas('sugerencias'), f'las coordenadas no pasan por proveedores: {registro()}'
    p.evaluate("Spevb.Planner.poner('destination', { id: null, lat: 4.1450, lng: -73.6240, nombre: 'Favorito Trabajo', direccion: null, fuente: 'Favorito', confirmado: true })")
    p.wait_for_timeout(700)
    assert not registro() and lista(p, 'destination').count() == 0
    # punto elegido en el mapa: usa geocodificación inversa (otra operación), nunca sugerencias
    p.click('#pickDestination'); p.wait_for_timeout(200)
    p.evaluate("(() => { const m = Spevb.maps.map; const q = m.toLatLng({ x: m.getSize().x * 0.6, y: m.getSize().y * 0.5 }); Spevb.Planner.poner('destination', { id: null, lat: q[0], lng: q[1], nombre: 'Punto en mapa', direccion: null, fuente: 'Selección manual en mapa', confirmado: false }); })()")
    p.wait_for_timeout(600)
    assert not consultas('sugerencias')
    s.limpio('coordenadas'); s.cerrar()


@prueba
def usar_mi_ubicacion_confirma_el_origen_y_no_abre_sugerencias(nav):
    s, p = sesion(nav, geolocation=B.CENTRO, permissions=['geolocation'])
    p.fill('#tripOrigin', 'Cal'); p.wait_for_timeout(100)
    p.click('#useMyLocation')
    B.esperar(p, "!!Spevb.Planner.puntos().origen", 30000)
    p.wait_for_timeout(800)
    n = len(consultas('sugerencias'))
    p.wait_for_timeout(900)
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false'
    assert len(consultas('sugerencias')) == n, 'tras confirmar con el GPS no hay más consultas'
    s.limpio('gps'); s.cerrar()


@prueba
def seleccionar_y_cambiar_enseguida_al_otro_campo_no_reabre_el_primero(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'Carrera 22'); esperar_lista(p, 'origin')
    lista(p, 'origin').first.click()
    p.fill('#tripDestination', 'Calle 10'); esperar_lista(p, 'destination')
    p.wait_for_timeout(700)
    assert lista(p, 'origin').count() == 0 and punto(p, 'origin'), 'el origen sigue confirmado y su lista cerrada'
    assert lista(p, 'destination').count() >= 1
    s.limpio('cambio de campo'); s.cerrar()


# ------------------------------------------------------------------------------------------------ errores tipados
@prueba
def cada_estado_de_error_dice_algo_distinto_y_no_es_no_hay_direcciones(nav):
    s, p = sesion(nav)
    esperado = {'tiempo extra': 'tard', 'redca': 'no pudo responder', 'cuota': 'límite', 'clave': 'configur', 'pausa': 'pausa', 'fuera de la ciudad': 'fuera del área disponible',
                'basura json': 'no pude leer'}      # «sin coincidencias» mientras se escribe ya NO muestra mensaje (solo lo dice «Buscar»): se prueba aparte
    textos = {}
    for consulta, fragmento in esperado.items():
        p.fill('#tripOrigin', consulta)
        B.esperar(p, "document.querySelector('#originResults .search-hint, #originResults .address-warning, #originResults .search-error') !== null", 6000)
        t = p.locator('#originResults').inner_text().lower()
        textos[consulta] = t
        assert fragmento.lower() in t, f'«{consulta}»: se esperaba «{fragmento}» y salió «{t}»'
        assert p.locator('#originResults [role="status"], #originResults [role="alert"]').count() >= 1, f'«{consulta}»: el aviso debe anunciarse'
    assert len(set(textos.values())) == len(textos), f'los estados deben diferenciarse: {textos}'
    p.fill('#tripOrigin', 'nada que ver'); p.wait_for_timeout(1500)
    assert p.locator('#originResults').inner_text().strip() == '' and 'encontramos' not in p.inner_text('#tripStatus').lower(), 'escribiendo, sin sugerencias: ningún «no encontramos»'
    p.click('#searchOrigin'); p.wait_for_timeout(1500)
    assert 'No pudimos ubicar' in p.locator('#originResults').inner_text() or 'encontramos' in p.inner_text('#tripStatus').lower(), 'al pulsar «Buscar» sí se dice'
    s.limpio('estados'); s.cerrar()


@prueba
def la_eleccion_fallida_no_se_sustituye_en_silencio_y_ofrece_reintentar(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'goofallo carrera 22'); esperar_lista(p, 'origin')
    lista(p, 'origin').first.click()
    B.esperar(p, "document.querySelector('#originResults [data-accion=\"reintentar\"], #originResults .search-error') !== null", 6000)
    assert punto(p, 'origin') is None, 'no se ubica nada si el detalle del lugar elegido falló'
    t = p.locator('#originResults').inner_text().lower()
    assert 'reintent' in t, f'debe poder reintentar o elegir otra: {t}'
    assert p.input_value('#tripOrigin').lower().startswith('goofallo'), 'el texto elegido se conserva para reintentar'
    assert p.locator('#originResults .autosuggest-option').count() >= 0
    s.limpio('elección fallida'); s.cerrar()


@prueba
def un_lugar_de_otro_proveedor_no_reemplaza_la_sugerencia_elegida(nav):
    """Un backend viejo o defectuoso devuelve lugares[0] de ArcGIS para una sugerencia de Google: el navegador no debe aceptarlo."""
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'goosust carrera 22'); esperar_lista(p, 'origin')
    lista(p, 'origin').first.click()
    p.wait_for_timeout(1200)
    n = punto(p, 'origin')
    assert n is None or 'OTRO LUGAR' not in n, f'se aceptó un lugar de otro proveedor: {n}'
    s.limpio('sustitución'); s.cerrar()


@prueba
def elegir_una_sugerencia_de_google_resuelve_ese_identificador_y_ubica_el_punto(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'goo carrera 22'); esperar_lista(p, 'origin')
    lista(p, 'origin').first.click()
    B.esperar(p, "!!Spevb.Planner.puntos().origen", 6000)
    reg = [r for r in consultas('lugares') if r['magicKey']]
    assert reg and reg[-1]['magicKey'].startswith('g:ok'), f'se resuelve ESE identificador: {reg}'
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false'
    s.limpio('elegir google'); s.cerrar()


# ------------------------------------------------------------------------------------------------ sesión de Places y composición
@prueba
def cada_campo_tiene_su_propia_sesion_por_busqueda_y_se_descarta_al_confirmar(nav):
    s, p = sesion(nav)
    p.fill('#tripOrigin', 'goo carrera 22'); esperar_lista(p, 'origin')
    p.fill('#tripOrigin', 'goo carrera 22 con'); p.wait_for_timeout(900)
    p.fill('#tripDestination', 'goo calle 10'); esperar_lista(p, 'destination')
    sug = consultas('sugerencias')
    por_texto = {r['q']: r['sesion'] for r in sug}
    assert all(por_texto.values()), f'toda consulta lleva sesion=: {sug}'
    assert por_texto['goo carrera 22'] == por_texto['goo carrera 22 con'], 'una misma búsqueda comparte su sesión'
    assert por_texto['goo calle 10'] != por_texto['goo carrera 22'], 'A y B no comparten sesión'
    lista(p, 'origin').first.click() if lista(p, 'origin').count() else None
    p.fill('#tripOrigin', 'goo carrera 22'); esperar_lista(p, 'origin')
    lista(p, 'origin').first.click()
    B.esperar(p, "!!Spevb.Planner.puntos().origen", 6000)
    elegidas = [r for r in consultas('lugares') if r['magicKey']]
    assert elegidas and elegidas[-1]['sesion'], 'el detalle del lugar elegido usa la sesión de esa búsqueda'
    ultima = elegidas[-1]['sesion']
    p.click('#tripOrigin'); p.keyboard.press('End'); p.keyboard.type(' x'); esperar_lista(p, 'origin')
    nueva = [r for r in consultas('sugerencias') if r['q'].endswith(' x')][-1]['sesion']
    assert nueva and nueva != ultima, 'tras confirmar, una búsqueda nueva usa otra sesión'
    s.limpio('sesiones'); s.cerrar()


@prueba
def la_composicion_de_texto_no_consulta_hasta_terminar(nav):
    s, p = sesion(nav)
    p.focus('#tripOrigin')
    p.evaluate("""() => { const i = document.getElementById('tripOrigin');
        i.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
        for (const t of ['Ca', 'Car', 'Carr']) { i.value = t; i.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true })); } }""")
    p.wait_for_timeout(1100)
    assert not consultas('sugerencias'), f'no se consulta durante una composición incompleta: {consultas()}'
    p.evaluate("""() => { const i = document.getElementById('tripOrigin'); i.value = 'Carrera';
        i.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true, data: 'Carrera' }));
        i.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: false })); }""")
    esperar_lista(p, 'origin')
    assert len(consultas('sugerencias')) == 1
    s.limpio('composición'); s.cerrar()


@prueba
def el_final_de_una_busqueda_antigua_no_cambia_el_boton_de_la_nueva(nav):
    s, p = sesion(nav)
    ret = Retenidas(s.ctx, '**/api/lugares?*')
    p.fill('#tripOrigin', 'Calle 38 con carrera 22'); p.click('#searchOrigin'); p.wait_for_timeout(500)
    assert p.is_disabled('#searchOrigin') and len(ret.pend) == 1
    p.fill('#tripOrigin', 'Calle 40 con carrera 23'); p.focus('#tripOrigin'); p.keyboard.press('Enter'); p.wait_for_timeout(500)
    ret.liberar(0); p.wait_for_timeout(700)
    assert p.is_disabled('#searchOrigin'), 'el finally de la búsqueda anterior no debe habilitar el botón de la que sigue en curso'
    ret.soltar(); p.wait_for_timeout(900)
    assert not p.is_disabled('#searchOrigin')
    s.limpio('finally'); s.cerrar()


# ------------------------------------------------------------------------------------------------ 4.15.3 · búsqueda 100 % Google, rápida y honesta
INSTRUMENTAR = """
window.__f = []; window.__teclas = []; const _fetch = window.fetch.bind(window);
window.fetch = (u, o) => { const url = String(u && u.url || u); if (url.includes('/api/lugares')) window.__f.push({ url, t: performance.now(), signal: o && o.signal || null }); return _fetch(u, o); };
document.addEventListener('input', () => window.__teclas.push(performance.now()), true);
"""


def sesion_instrumentada(nav, **opts):
    s = B.Sesion(nav, **opts)
    s.ctx.add_init_script(INSTRUMENTAR)
    p = s.abrir()
    limpiar_log()
    return s, p


def sug(p):
    return p.evaluate("window.__f.filter(f => f.url.includes('/api/lugares/sugerencias')).map(f => ({ q: decodeURIComponent(new URL(f.url, location.href).searchParams.get('q')), t: f.t, abortada: !!(f.signal && f.signal.aborted) }))")


@prueba
def las_sugerencias_salen_solas_tras_un_retardo_corto_y_una_sola_consulta_por_pausa(nav):
    s, p = sesion_instrumentada(nav)
    p.click('#tripOrigin')
    p.keyboard.type('goo carrera 22', delay=35)
    esperar_lista(p, 'origin', 4000)
    c = sug(p)
    assert len(c) == 1 and c[0]['q'] == 'goo carrera 22', f'una consulta por pausa, no una por letra: {c}'
    espera = c[0]['t'] - p.evaluate('window.__teclas[window.__teclas.length - 1]')
    assert 170 <= espera <= 330, f'retardo tras la última tecla ≈ 220 ms: {espera:.0f}'
    p.fill('#tripDestination', 'go'); p.wait_for_timeout(700)
    assert not [x for x in sug(p) if x['q'] == 'go'], 'con menos de tres caracteres no se consulta'
    s.limpio('debounce'); s.cerrar()


@prueba
def escribir_mas_cancela_la_consulta_anterior_con_abortcontroller_y_la_vieja_no_reemplaza_a_la_nueva(nav):
    s, p = sesion_instrumentada(nav)
    r = Retenidas(s.ctx, '**/api/lugares/sugerencias*')
    p.click('#tripOrigin')
    p.keyboard.type('goo carr', delay=30); p.wait_for_timeout(500)
    p.keyboard.type('era 22', delay=30); p.wait_for_timeout(500)
    c = sug(p)
    assert len(c) == 2 and c[0]['abortada'] and not c[1]['abortada'], f'la consulta vieja se abortó al escribir más: {c}'
    r.liberar(1); p.wait_for_timeout(500)
    esperar_lista(p, 'origin', 3000)
    nuevo = lista(p, 'origin').first.inner_text()
    r.soltar(); p.wait_for_timeout(400)
    assert lista(p, 'origin').first.inner_text() == nuevo and 'carrera 22' in nuevo, 'la respuesta vieja nunca reemplaza a la nueva'
    s.limpio('abort'); s.cerrar()


@prueba
def cada_sugerencia_muestra_nombre_principal_y_referencia_y_es_navegable_con_teclado(nav):
    s, p = sesion_instrumentada(nav)
    p.fill('#tripOrigin', 'goo unicentro'); esperar_lista(p, 'origin')
    o = p.evaluate("(() => { const b = document.querySelector('#originResults .autosuggest-option'); return { principal: b.querySelector('strong').textContent, secundario: b.querySelector('small').textContent, aria: b.getAttribute('aria-label'), rol: b.getAttribute('role') }; })()")
    assert o['principal'] == 'goo unicentro (Google)' and o['secundario'] == 'Villavicencio, Meta, Colombia' and o['rol'] == 'option', o
    assert o['aria'] == 'goo unicentro (Google), Villavicencio, Meta, Colombia', 'el lector de pantalla oye nombre y referencia'
    p.focus('#tripOrigin')
    p.keyboard.press('ArrowDown')
    ad = p.evaluate("(() => { const i = document.getElementById('tripOrigin'); const id = i.getAttribute('aria-activedescendant'); return { id, existe: !!document.getElementById(id), sel: document.getElementById(id).getAttribute('aria-selected'), expandido: i.getAttribute('aria-expanded') }; })()")
    assert ad['id'] == 'origin-suggestion-0' and ad['existe'] and ad['sel'] == 'true' and ad['expandido'] == 'true', ad
    p.keyboard.press('Escape'); p.wait_for_timeout(200)
    assert lista(p, 'origin').count() == 0 and aria(p, 'origin') == 'false' and p.evaluate("!document.getElementById('tripOrigin').hasAttribute('aria-activedescendant')"), 'Escape cierra la lista'
    p.fill('#tripOrigin', 'goo unicentro'); esperar_lista(p, 'origin')
    p.keyboard.press('ArrowDown'); p.keyboard.press('Enter')
    B.esperar(p, "!!Spevb.Planner.puntos().origen", 6000)
    reg = [r for r in consultas('lugares') if r['magicKey']]
    assert reg and reg[-1]['magicKey'].startswith('g:ok'), f'Enter sobre la opción activa resuelve su identificador de Google: {reg}'
    s.limpio('teclado'); s.cerrar()


@prueba
def la_sesion_de_places_se_renueva_al_borrar_y_al_abandonar_el_campo(nav):
    s, p = sesion_instrumentada(nav)
    sesion_de = lambda texto: [r for r in consultas('sugerencias') if r['q'] == texto][-1]['sesion']      # noqa: E731
    p.fill('#tripOrigin', 'goo uno'); esperar_lista(p, 'origin'); s1 = sesion_de('goo uno')
    p.fill('#tripOrigin', ''); p.wait_for_timeout(300)      # borrar todo el texto equivale a la X
    p.fill('#tripOrigin', 'goo dos'); esperar_lista(p, 'origin'); s2 = sesion_de('goo dos')
    assert s1 and s2 and s1 != s2, 'borrar cierra la sesión y la siguiente búsqueda usa otra'
    p.focus('#tripDestination'); p.wait_for_timeout(500)
    p.focus('#tripOrigin'); p.keyboard.press('End'); p.keyboard.type('s'); esperar_lista(p, 'origin'); s3 = sesion_de('goo doss')
    assert s3 and s3 != s2, 'abandonar el campo descarta la sesión'
    s.limpio('sesiones'); s.cerrar()


@prueba
def sin_google_configurado_y_sin_conexion_el_mensaje_es_honesto_y_no_hay_respaldo(nav):
    s, p = sesion_instrumentada(nav)
    p.fill('#tripOrigin', 'sinconfig prueba')
    B.esperar(p, "document.querySelector('#originResults .search-error') !== null", 6000)
    t = p.inner_text('#originResults .search-error')
    assert t.startswith('La búsqueda de Google no está configurada'), t
    assert p.evaluate("document.querySelector('#originResults .search-error').dataset.estado") == 'NO_CONFIGURADO' and p.locator('#originResults [role="status"]').count() >= 1
    antes = len(sug(p))
    p.evaluate("Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })")
    p.fill('#tripDestination', 'goo sin red'); p.wait_for_timeout(900)
    t2 = p.inner_text('#destinationResults .search-error')
    assert t2.startswith('No hay conexión para buscar lugares'), t2
    assert len(sug(p)) == antes, 'sin conexión no se pide nada'
    assert p.locator('#destinationResults .search-retry').count() == 1, 'se ofrece reintentar'
    p.evaluate("Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => true })")
    p.click('#destinationResults .search-retry'); esperar_lista(p, 'destination')
    s.limpio('mensajes honestos'); s.cerrar()


@prueba
def guiado_y_avanzado_comparten_la_misma_logica_y_hacen_una_sola_consulta(nav):
    resultados = {}
    for modo in ('avanzado', 'guiado'):
        if modo == 'avanzado':
            s, p = sesion_instrumentada(nav)
        else:
            s = B.Sesion(nav, guiado=True, viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            s.ctx.add_init_script(INSTRUMENTAR)
            p = s.ctx.pages[0]
            p.goto(B.URL, wait_until='domcontentloaded')
            B.esperar(p, "!!(window.Spevb && Spevb.Guiado && Spevb.Planner.puntos)", 20000)
            p.wait_for_timeout(1000)
            limpiar_log()
        p.fill('#tripDestination', 'goo carrera 22'); esperar_lista(p, 'destination', 5000)
        c = sug(p)
        sesiones = [r['sesion'] for r in consultas('sugerencias')]
        resultados[modo] = (len(c), c[0]['q'], bool(sesiones and sesiones[0]), lista(p, 'destination').first.locator('strong').inner_text())
        externos = [r for r in registro() if r['ruta'] not in ('sugerencias', 'lugares')]
        assert not externos, f'{modo}: la consulta del pasajero solo toca la API propia de lugares: {externos}'
        s.limpio('paridad ' + modo); s.cerrar()
    assert resultados['avanzado'] == resultados['guiado'] and resultados['guiado'][0] == 1, f'misma conducta y una sola consulta: {resultados}'


@prueba
def la_cache_en_memoria_evita_repetir_la_misma_consulta_de_la_misma_sesion_y_no_guarda_nada(nav):
    s, p = sesion_instrumentada(nav)
    p.fill('#tripOrigin', 'goo carrera 22'); esperar_lista(p, 'origin')
    p.fill('#tripOrigin', 'goo carrera 2'); p.wait_for_timeout(700)
    p.fill('#tripOrigin', 'goo carrera 22'); esperar_lista(p, 'origin'); p.wait_for_timeout(500)
    c = [x for x in sug(p) if x['q'] == 'goo carrera 22']
    assert len(c) == 1, f'volver a escribir el mismo texto en la misma sesión no repite la consulta: {c}'
    assert p.evaluate('Spevb.BusquedaMetricas.ultima().cache') is True
    guardado = p.evaluate("JSON.stringify(Object.assign({}, localStorage, sessionStorage))")
    assert 'goo carrera' not in guardado.lower(), 'las predicciones no se guardan en el navegador'
    # al elegir, la caché de esa sesión desaparece
    lista(p, 'origin').first.click(); B.esperar(p, "!!Spevb.Planner.puntos().origen", 6000)
    assert p.evaluate('Spevb.BusquedaMetricas.cache()') == 0, 'la caché murió con su sesión'
    s.limpio('cache'); s.cerrar()


@prueba
def se_mide_el_tiempo_hasta_la_lista_y_con_conexion_lenta_se_avisa_sin_bloquear_la_escritura(nav):
    s, p = sesion_instrumentada(nav)
    p.fill('#tripOrigin', 'goo carrera 22'); esperar_lista(p, 'origin')
    m = p.evaluate('Spevb.BusquedaMetricas.ultima()')
    assert m and m['campo'] == 'origin' and 150 <= m['ms'] <= 1500, f'última tecla → lista visible: {m}'
    r = Retenidas(s.ctx, '**/api/lugares/sugerencias*')
    p.fill('#tripDestination', 'goo calle 10'); p.wait_for_timeout(1200)
    assert p.is_visible('#destinationResults .search-buscando') and p.inner_text('#destinationResults .search-buscando') == 'Buscando lugares…', 'con la respuesta lenta se dice que se está buscando'
    assert p.is_enabled('#tripDestination')
    p.click('#tripDestination'); p.keyboard.press('End'); p.keyboard.type(' 5', delay=20)
    assert p.input_value('#tripDestination') == 'goo calle 10 5', 'la escritura no se bloquea'
    r.soltar(); esperar_lista(p, 'destination', 5000)
    assert p.locator('#destinationResults .search-buscando').count() == 0, 'el aviso desaparece con la lista'
    s.limpio('lenta'); s.cerrar()


@prueba
def si_la_busqueda_falla_siguen_a_mano_buscar_usar_mi_ubicacion_y_elegir_en_el_mapa(nav):
    s = B.Sesion(nav, permissions=['geolocation'], geolocation={'latitude': 4.15, 'longitude': -73.63287, 'accuracy': 15})
    p = s.abrir(); limpiar_log()
    p.fill('#tripOrigin', 'redca algo')
    B.esperar(p, "document.querySelector('#originResults .search-error') !== null", 6000)
    t = p.inner_text('#originResults .search-error')
    assert t.startswith('Google no pudo responder. Intenta de nuevo'), t
    assert [b.inner_text() for b in p.locator('#originResults .search-alt').all()] == ['Usar mi ubicación', 'Elegir en el mapa'], 'en el origen: ubicación y mapa'
    assert p.is_enabled('#searchOrigin') and p.is_visible('#searchOrigin'), 'la búsqueda manual sigue disponible'
    p.click('#originResults .search-alt[data-accion="mapa"]')
    assert p.get_attribute('#pickOrigin', 'aria-pressed') == 'true', '«Elegir en el mapa» activa la selección'
    p.click('#pickOrigin')
    p.fill('#tripOrigin', 'redca otra')
    B.esperar(p, "document.querySelector('#originResults .search-alt[data-accion=\"gps\"]') !== null", 6000)
    p.click('#originResults .search-alt[data-accion="gps"]')
    B.esperar(p, "!!Spevb.Planner.puntos().origen", 8000)
    assert p.evaluate("Spevb.Planner.puntos().origen.fuente") != 'Google Maps', 'el punto de «Usar mi ubicación» no se presenta como de Google'
    p.fill('#tripDestination', 'redca destino')
    B.esperar(p, "document.querySelector('#destinationResults .search-error') !== null", 6000)
    assert [b.inner_text() for b in p.locator('#destinationResults .search-alt').all()] == ['Elegir en el mapa'], 'en el destino: el mapa'
    s.limpio('alternativas'); s.cerrar()


@prueba
def los_cinco_mensajes_honestos_dicen_exactamente_lo_acordado(nav):
    s, p = sesion_instrumentada(nav)
    esperado = {'sinconfig x': 'La búsqueda de Google no está configurada', 'cuota x': 'Google no pudo responder. Intenta de nuevo',
                'fuera x': 'Ese lugar queda fuera del área disponible', 'tiempo x': 'Google no pudo responder. Intenta de nuevo'}
    for consulta, inicio in esperado.items():
        p.fill('#tripOrigin', consulta)
        B.esperar(p, "document.querySelector('#originResults .search-error') !== null", 6000)
        assert p.inner_text('#originResults .search-error').startswith(inicio), (consulta, p.inner_text('#originResults .search-error'))
    p.evaluate("Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })")
    p.fill('#tripOrigin', 'goo sin red'); p.wait_for_timeout(700)
    assert p.inner_text('#originResults .search-error').startswith('No hay conexión para buscar lugares')
    s.limpio('mensajes'); s.cerrar()


# ============================================================================================================== pertinencia (Villavicencio): identidad, sedes, vía sin número, una consulta por pausa
@prueba
def otra_sede_del_mismo_proveedor_no_se_acepta_aunque_el_proveedor_coincida(nav):
    """El backend defectuoso devuelve OTRA sede de Google (otro googleId) para la opción tocada: el navegador compara la identidad, no solo el proveedor."""
    s, p = sesion(nav)
    p.fill('#tripDestination', 'gooid clinica meta'); esperar_lista(p, 'destination')
    lista(p, 'destination').first.click()
    B.esperar(p, "document.querySelector('#destinationResults [data-accion=\"reintentar\"], #destinationResults .search-error') !== null", 6000)
    assert punto(p, 'destination') is None, 'no se pone en el mapa un lugar con otra identidad'
    assert 'reintent' in p.locator('#destinationResults').inner_text().lower()
    assert p.input_value('#tripDestination').lower().startswith('gooid'), 'se conserva lo escrito'
    s.limpio('otra sede'); s.cerrar()


@prueba
def dos_sedes_con_el_mismo_nombre_se_distinguen_y_se_resuelve_exactamente_la_tocada(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goosedes clinica meta'); esperar_lista(p, 'destination')
    assert lista(p, 'destination').count() == 2
    t = p.evaluate("[...document.querySelectorAll('#destinationResults .autosuggest-option')].map(b => [b.querySelector('strong').textContent, b.querySelector('small').textContent])")
    assert t[0][0] == t[1][0] == 'Clínica Meta' and t[0][1] != t[1][1] and '#31-10' in t[0][1] and '#5-20' in t[1][1], t
    lista(p, 'destination').nth(1).click()
    B.esperar(p, "!!Spevb.Planner.puntos().destino", 6000)
    reg = [r for r in consultas('lugares') if r['magicKey']]
    assert reg[-1]['magicKey'] == 'g:sedeNorte01', f'se resolvió la sede tocada: {reg}'
    s.limpio('dos sedes'); s.cerrar()


@prueba
def una_via_sin_el_numero_pedido_se_explica_ofrece_el_mapa_y_conserva_el_texto(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'vianum Carrera 22 #38-10')
    p.keyboard.press('Escape')
    p.click('#searchDestination')
    B.esperar(p, "document.getElementById('destinationResults').innerText.includes('Encontramos la carrera, pero no ese número')", 8000)
    assert punto(p, 'destination') is None, 'nunca se confirma otra puerta como esa'
    assert p.input_value('#tripDestination') == 'vianum Carrera 22 #38-10', 'se conserva lo escrito'
    assert p.is_visible('#pickDestination'), '«Elegir en el mapa» sigue a la mano'
    s.limpio('vía sin número'); s.cerrar()


@prueba
def una_posible_coincidencia_se_revisa_antes_de_usarla_y_no_cambia_a_ni_b_hasta_confirmar(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'posible Carrera 27 935A 50')
    p.keyboard.press('Escape')
    p.click('#searchDestination')
    B.esperar(p, "document.getElementById('destinationResults').innerText.includes('Posible coincidencia')", 8000)
    assert 'Posible coincidencia' in p.inner_text('#destinationResults') and 'Carrera 27 # 35A-50' in p.inner_text('#destinationResults')
    assert punto(p, 'destination') is None, 'una posible coincidencia no se aplica sola'
    p.click('#destinationResults .autosuggest-option'); p.wait_for_timeout(500)
    assert '¿Te referías a esta dirección?' in p.inner_text('#destinationResults') and 'Carrera 27 # 35A-50' in p.inner_text('#destinationResults')
    assert p.evaluate("document.activeElement.className.includes('place-review-use')"), 'el foco queda en «Usar este punto»'
    assert punto(p, 'destination') is None and punto(p, 'origin') is None, 'revisar no cambia A ni B'
    assert p.input_value('#tripDestination') == 'posible Carrera 27 935A 50', 'se conserva lo escrito'
    p.click('.place-review-back'); p.wait_for_timeout(300)
    assert 'Posible coincidencia' in p.inner_text('#destinationResults'), 'volver regresa a la lista'
    p.click('#destinationResults .autosuggest-option'); p.click('.place-review-use'); p.wait_for_timeout(500)
    d = p.evaluate("Spevb.Planner.puntos().destino")
    assert d and abs(d['lat'] - 4.1470) < 1e-6, f'«Usar este punto» confirma el pin que se revisó: {d}'
    s.limpio('posible'); s.cerrar()


@prueba
def solo_la_via_se_ofrece_como_referencia_y_lleva_al_mapa_sin_confirmar_nada(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'referencia Carrera 27 #99-99')
    p.keyboard.press('Escape')
    p.click('#searchDestination')
    B.esperar(p, "document.getElementById('destinationResults').innerText.includes('Referencia en el mapa')", 8000)
    assert 'no ese número' in p.inner_text('#destinationResults')
    p.click('#destinationResults .autosuggest-option'); p.wait_for_timeout(500)
    assert p.get_attribute('#pickDestination', 'aria-pressed') == 'true', 'se activa «Elegir en el mapa»'
    assert punto(p, 'destination') is None, 'la vía no se confirma como destino'
    assert p.input_value('#tripDestination') == 'referencia Carrera 27 #99-99'
    s.limpio('referencia'); s.cerrar()


@prueba
def con_una_exacta_y_una_parecida_la_exacta_va_primero_y_se_elige_en_un_toque(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'mixto Carrera 27 #35A-50')
    p.keyboard.press('Escape')
    p.click('#searchDestination')
    B.esperar(p, "document.getElementById('destinationResults').innerText.includes('Coincidencia exacta')", 8000)
    t = p.inner_text('#destinationResults')
    assert t.index('Coincidencia exacta') < t.index('Posible coincidencia'), t
    p.click('#destinationResults .autosuggest-option >> nth=0'); p.wait_for_timeout(500)
    d = p.evaluate("Spevb.Planner.puntos().destino")
    assert d and abs(d['lat'] - 4.1460) < 1e-6, f'la exacta se elige en un toque: {d}'
    s.limpio('mixto'); s.cerrar()


@prueba
def sin_ninguna_opcion_se_dice_que_no_se_ubico_el_numero_y_quedan_las_salidas(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'nada Carrera 27 #99-99')
    p.keyboard.press('Escape')
    p.click('#searchDestination'); p.wait_for_timeout(1500)
    t = p.inner_text('#destinationResults') + ' ' + p.inner_text('#tripStatus')
    assert 'No pudimos ubicar ese número' in t or 'No encontramos' in t or 'Todavía no encontramos' in t, t
    assert punto(p, 'destination') is None and p.input_value('#tripDestination') == 'nada Carrera 27 #99-99'
    assert p.is_visible('#pickDestination')
    s.limpio('sin opcion'); s.cerrar()


@prueba
def borrar_quita_en_el_acto_la_direccion_de_google_bajo_el_campo_y_deja_el_mapa_sin_ruta(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'mixto Carrera 27 #35A-50'); p.keyboard.press('Escape')
    p.click('#searchDestination')
    B.esperar(p, "document.getElementById('destinationResults').innerText.includes('Coincidencia exacta')", 8000)
    p.click('#destinationResults .autosuggest-option >> nth=0'); p.wait_for_timeout(700)
    # la dirección de Google ya NO se dibuja bajo el campo (ocupaba el espacio de «Buscar rutas»): queda en el elemento oculto que lee el lector de pantalla y en el tooltip
    assert not p.is_visible('#destinationCompleto') and 'Carrera 27' in p.text_content('#destinationCompleto'), 'la dirección que devolvió Google queda en el texto oculto, no a la vista'
    p.click('#clearDestination'); p.wait_for_timeout(120)
    assert not p.is_visible('#destinationCompleto') and p.text_content('#destinationCompleto').strip() == '', 'al borrar, el texto de la dirección desaparece en el acto'
    # A y B con una ruta dibujada: «Limpiar A y B» deja el mapa sin ruta ni pines
    p.fill('#tripOrigin', 'mixto Carrera 27 #35A-50'); p.keyboard.press('Escape'); p.click('#searchOrigin'); p.wait_for_timeout(1200)
    p.click('#originResults .autosuggest-option >> nth=0'); p.wait_for_timeout(500)
    p.evaluate("Spevb.Planner.poner('destination', { id: null, lat: 4.133, lng: -73.6065, nombre: 'Destino de prueba', direccion: null, fuente: 'Prueba', confirmado: true })"); p.wait_for_timeout(500)
    p.evaluate("document.querySelector('#planTrip').click()"); p.wait_for_timeout(2500)
    p.click('#clearTripPoints'); p.wait_for_timeout(300)
    assert p.evaluate("Spevb.maps.map.elementos().length") == 0, 'sin ruta ni pines en el mapa'
    assert p.evaluate("!document.querySelector('#tripResults .trip-option') && document.getElementById('tripItinerario').children.length === 0")
    assert not p.is_visible('#originCompleto') and not p.is_visible('#destinationCompleto')
    p.wait_for_timeout(1500)
    assert p.evaluate("Spevb.maps.map.elementos().length") == 0, 'tampoco reaparece algo tardío'
    s.limpio('borrar'); s.cerrar()


@prueba
def escribir_letra_por_letra_hace_pocas_consultas_y_pegar_hace_una(nav):
    s, p = sesion(nav)
    p.click('#tripDestination')
    p.keyboard.type('goo carrera 22 #38', delay=70)      # ≈ 1,3 s tecleando: el debounce de 220 ms junta las teclas
    esperar_lista(p, 'destination')
    n = len(consultas('sugerencias'))
    assert 1 <= n <= 3, f'una consulta por pausa, no una por tecla: {n}'
    limpiar_log()
    p.fill('#tripDestination', ''); p.wait_for_timeout(300)
    p.fill('#tripDestination', 'goo calle 30 # 38-10'); esperar_lista(p, 'destination'); p.wait_for_timeout(500)
    assert len(consultas('sugerencias')) == 1, 'pegar la dirección completa hace una sola consulta'
    s.limpio('letra por letra'); s.cerrar()


@prueba
def escape_cierra_la_lista_sin_borrar_y_enter_sin_opcion_activa_ejecuta_buscar(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goo calle 30'); esperar_lista(p, 'destination')
    p.keyboard.press('Escape')
    assert lista(p, 'destination').count() == 0 and p.input_value('#tripDestination') == 'goo calle 30', 'Escape cierra sin borrar'
    limpiar_log()
    p.keyboard.press('Enter'); p.wait_for_timeout(900)
    reg = consultas('lugares')
    assert reg and not reg[-1]['magicKey'], f'sin opción activa, Enter es «Buscar» (búsqueda explícita): {reg}'
    s.limpio('escape y enter'); s.cerrar()


@prueba
def con_el_teclado_las_flechas_recorren_y_enter_confirma_solo_la_opcion_resaltada(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goosedes clinica'); esperar_lista(p, 'destination')
    assert punto(p, 'destination') is None, 'perder el foco o dejar de escribir no elige el primer resultado'
    p.keyboard.press('ArrowDown'); p.keyboard.press('ArrowDown'); p.keyboard.press('Enter')
    B.esperar(p, "!!Spevb.Planner.puntos().destino", 6000)
    assert [r for r in consultas('lugares') if r['magicKey']][-1]['magicKey'] == 'g:sedeNorte01', 'Enter confirmó la segunda (resaltada)'
    s.limpio('flechas'); s.cerrar()


# ============================================================================================================== nomenclatura colombiana: lo escrito se conserva y la dirección de Google se ve
@prueba
def lo_escrito_se_conserva_en_origen_y_destino_y_el_numeral_viaja_codificado(nav):
    """La versión normalizada («Carrera 27 # 35A-50») la arma el SERVIDOR para consultar a Google: el campo no se reescribe con cada tecla y el # llega a la API sin perderse."""
    s, p = sesion(nav)
    for modo, escrito in (('origin', 'goo Kra 27 #35A - 50'), ('destination', 'goo carrera 27 número 35A 50')):
        limpiar_log()
        p.fill('#' + ID[modo], '')
        p.click('#' + ID[modo])
        p.keyboard.type(escrito, delay=25)      # tecla a tecla
        esperar_lista(p, modo)
        assert p.input_value('#' + ID[modo]) == escrito, 'el campo muestra lo que la persona escribió, sin normalizar'
        q = [r['q'] for r in consultas('sugerencias')][-1]
        assert q == escrito, f'el servidor recibe lo escrito (con el # intacto): {q!r}'
        assert p.evaluate("(m) => document.activeElement.id === m", ID[modo]) and p.evaluate("document.activeElement.selectionStart") == len(escrito), 'el cursor sigue en su sitio'
        p.keyboard.press('Escape')
    s.limpio('conserva lo escrito'); s.cerrar()


@prueba
def pegar_una_direccion_y_editar_en_medio_hacen_una_consulta_por_pausa(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goo carrera 27 numero 35A 50'); esperar_lista(p, 'destination'); p.wait_for_timeout(500)
    assert len(consultas('sugerencias')) == 1, 'pegar = una consulta'
    limpiar_log()
    p.evaluate("(() => { const i = document.getElementById('tripDestination'); i.focus(); i.setSelectionRange(14, 14); })()")      # en medio de «goo carrera 27 …»
    p.keyboard.type('X', delay=10); p.wait_for_timeout(700)
    assert p.input_value('#tripDestination') == 'goo carrera 27X numero 35A 50' and len(consultas('sugerencias')) == 1, 'editar en medio: el texto queda donde se editó y sale una sola consulta'
    s.limpio('pegar y editar'); s.cerrar()


@prueba
def una_via_se_ve_como_via_y_una_puerta_muestra_su_placa(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goovia carrera 27'); esperar_lista(p, 'destination')
    t = p.evaluate("[...document.querySelectorAll('#destinationResults .autosuggest-option')].map(b => [b.querySelector('strong').textContent, b.querySelector('small').textContent, b.getAttribute('aria-label')])")
    assert t[0][0] == 'Carrera 27' and t[0][1].startswith('Vía ·') and t[0][2].startswith('Vía,'), f'sin placa: se ve como vía y no aparenta una puerta: {t}'
    assert t[1][0] == 'Carrera 27 #35A-50' and not t[1][1].startswith('Vía'), f'con placa: la placa se ve: {t}'
    s.limpio('vía y placa'); s.cerrar()


@prueba
def al_elegir_se_ve_la_direccion_que_devolvio_google_y_el_punto_es_ese(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goodir carrera 27'); esperar_lista(p, 'destination')
    lista(p, 'destination').first.click()
    B.esperar(p, "!!Spevb.Planner.puntos().destino", 6000)
    B.esperar(p, "document.getElementById('destinationCompleto').textContent.trim() !== ''", 3000)
    assert 'Cra. 27 #35A-50, Villavicencio, Meta' in p.text_content('#destinationCompleto'), p.text_content('#destinationCompleto')
    assert [r for r in consultas('lugares') if r['magicKey']][-1]['magicKey'] == 'g:dir000001'
    s.limpio('dirección de Google'); s.cerrar()


@prueba
def si_google_solo_ubico_la_via_se_dice_y_se_ofrece_ajustar_en_el_mapa(nav):
    s, p = sesion(nav)
    p.fill('#tripDestination', 'goovia carrera 27'); esperar_lista(p, 'destination')
    lista(p, 'destination').first.click()      # la opción «Carrera 27» (solo la vía)
    B.esperar(p, "!!Spevb.Planner.puntos().destino", 6000)
    B.esperar(p, "document.getElementById('tripStatus').textContent.includes('Google ubicó la vía')", 3000)
    assert 'Elegir en el mapa' in p.inner_text('#tripStatus') and p.is_visible('#pickDestination')
    s.limpio('solo vía'); s.cerrar()


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
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0][:300] if str(e) else repr(e))
                traceback.print_exc(limit=2)
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de búsqueda y confirmación; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
