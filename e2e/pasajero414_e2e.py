"""Pruebas de navegador del flujo del pasajero (4.14): «Editar A y B», pregunta urgente sobre menús y diálogos, menú por fases y foto de perfil de Google.

Qué es y qué NO es: el frontend es el real; el backend es un stub (e2e/stub_server.py); Google, su foto y el GPS se SIMULAN (rutas de Playwright y e2e/simulador_gps.js);
los tamaños son emulaciones de Chromium/Edge. NO prueba una cuenta de Google real ni un teléfono físico.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/pasajero414_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
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
FOTO = 'https://lh3.googleusercontent.com/a/foto-de-prueba=s96-c'
FOTO_B = 'https://lh3.googleusercontent.com/a/foto-de-b=s96-c'
PNG = B.PNG_1PX
TAMANOS = [('320x568', 320, 568), ('390x844', 390, 844), ('tableta 768x1024', 768, 1024)]


def prueba(f):
    PRUEBAS.append(f)
    return f


def movil(nav, ancho=390, alto=844, **extra):
    return V.sesion(nav, viewport={'width': ancho, 'height': alto}, is_mobile=True, has_touch=True, device_scale_factor=2, **extra)


def usuario(correo='ana@example.com', nombre='Ana Prueba', foto=None, google=True):
    u = {'id': 1, 'nombre': nombre, 'correo': correo, 'tieneClave': not google, 'conGoogle': google, 'admin': False}
    if foto is not None:
        u['foto'] = foto
    return u


def json_ok(route, cuerpo, status=200):
    route.fulfill(status=status, content_type='application/json', body=json.dumps(cuerpo))


def con_cuenta(s, u, admin_configurado=True):
    """La API de la cuenta responde como si ya hubiera una sesión abierta (sin Google real)."""
    s.ctx.route('**/api/cuenta/yo', lambda r: json_ok(r, {'autenticado': True, 'usuario': u}))
    s.ctx.route('**/api/cuenta/config', lambda r: json_ok(r, {'adminConfigurado': admin_configurado}))
    s.ctx.route('**/api/cuenta/datos', lambda r: json_ok(r, {}))
    s.ctx.route('**/api/cuenta/datos/**', lambda r: json_ok(r, {'ok': True}))


def toque(p, selector):
    """Un toque REAL: se comprueba qué elemento hay bajo el punto central y se pulsa ahí (no un click() programático)."""
    r = p.evaluate("""(sel) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); const x = b.left + b.width / 2, y = b.top + b.height / 2;
        const el = document.elementFromPoint(x, y); return { x, y, golpea: !!el && (el === e || e.contains(el)), dentro: b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth, alto: b.height, ancho: b.width,
        quien: el ? (el.id || el.className || el.tagName) : null }; }""", selector)
    assert r, f'no existe {selector}'
    assert r['dentro'], f'{selector} queda fuera de la pantalla: {r}'
    assert r['golpea'], f'{selector} no recibe el toque (encima hay {r["quien"]}): {r}'
    p.mouse.click(r['x'], r['y'])
    return r


def sup(p):
    return p.evaluate('Spevb.Superficies.estado()')


def espera_menu(p):
    p.wait_for_timeout(480)


def iniciar_viaje(p, ruido=None):
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido=ruido or {'sigma': 6, 'semilla': 3})
    V.iniciar(p)
    V.alimentar(p, ls, 0, 'fase:esperando')
    return ls


# ============================================================================================================================ 1 · EDITAR A Y B
JS_FORM = """() => { const sh = document.getElementById('sheet'), body = sh.querySelector('.sheet-body'); const sb = body.getBoundingClientRect();
  const top = Math.max(sb.top, 0), bottom = Math.min(sb.bottom, innerHeight);
  const vis = (id) => { const e = document.getElementById(id), b = e.getBoundingClientRect(); const x = b.left + b.width / 2, y = b.top + b.height / 2; const el = document.elementFromPoint(x, y);
      return { dentro: b.top >= top - 1 && b.bottom <= bottom + 1, recibe: !!el && (el === e || e.contains(el)), top: Math.round(b.top), bottom: Math.round(b.bottom) }; };
  return { estado: sh.dataset.state, motivo: sh.dataset.motivo, area: [Math.round(top), Math.round(bottom)], A: vis('tripOrigin'), B: vis('tripDestination'), foco: document.activeElement.id,
           tecladoAbierto: document.activeElement.tagName === 'INPUT', scroll: Math.round(body.scrollTop) }; }"""


@prueba
def editar_A_y_B_es_alcanzable_tras_buscar_y_lleva_al_formulario_con_un_toque(nav):
    for nombre, w, h in TAMANOS + [('escritorio 1280x860', 1280, 860)]:
        s = movil(nav, w, h) if w < 1000 else V.sesion(nav, viewport={'width': w, 'height': h})
        p = s.abrir()
        V.planear(p)
        # tras buscar: «Iniciar viaje», «Editar A y B» y (si hay más) «Ver otras opciones» se alcanzan con un toque real
        for sel in ('#startTrip', '#editarAB'):
            r = p.evaluate("""(sel) => { const e = document.querySelector(sel), b = e.getBoundingClientRect(); const x = b.left + b.width / 2, y = b.top + b.height / 2, el = document.elementFromPoint(x, y);
                const sb = document.querySelector('#sheet .sheet-body').getBoundingClientRect(); return { visible: !e.hidden && b.height > 0, golpea: !!el && (el === e || e.contains(el)), alto: b.height, dentroDePantalla: b.bottom <= innerHeight && b.top >= 0, dentroDelPanel: b.bottom <= sb.bottom + 1 && b.top >= sb.top - 1 }; }""", sel)
            assert r['visible'] and r['golpea'] and r['dentroDePantalla'] and r['dentroDelPanel'] and r['alto'] >= 44, f'{nombre}: {sel} no se alcanza con un toque: {r}'
        if p.evaluate("!document.getElementById('verOpciones').hidden"):
            r = p.evaluate("""() => { const e = document.getElementById('verOpciones'), b = e.getBoundingClientRect(), el = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); const sb = document.querySelector('#sheet .sheet-body').getBoundingClientRect();
                return { golpea: !!el && (el === e || e.contains(el)), alto: b.height, dentroDelPanel: b.bottom <= sb.bottom + 1 }; }""")
            assert r['golpea'] and r['alto'] >= 44 and r['dentroDelPanel'], f'{nombre}: «Ver otras opciones» no se alcanza: {r}'
        antes = p.evaluate("[document.getElementById('tripOrigin').value, document.getElementById('tripDestination').value, document.querySelectorAll('#tripResults .trip-option').length, !!Spevb.Planner.seleccion.viaje]")
        toque(p, '#editarAB'); p.wait_for_timeout(900)
        f = p.evaluate(JS_FORM)
        assert f['A']['dentro'] and f['B']['dentro'] and f['A']['recibe'] and f['B']['recibe'], f'{nombre}: tras UN toque A y B deben verse y recibir toques: {f}'
        assert f['foco'] == 'formAB' and not f['tecladoAbierto'], f'{nombre}: el foco queda en el grupo del formulario, sin abrir el teclado: {f}'
        if w < 1000:
            assert f['estado'] in ('half', 'full') and f['motivo'] == 'editar-ab', f'{nombre}: el panel gana altura con el controlador existente: {f}'
        despues = p.evaluate("[document.getElementById('tripOrigin').value, document.getElementById('tripDestination').value, document.querySelectorAll('#tripResults .trip-option').length, !!Spevb.Planner.seleccion.viaje]")
        assert antes == despues, f'{nombre}: abrir para editar conserva texto, puntos, opciones y selección: {antes} → {despues}'
        # volver sin editar: el resultado sigue y se puede iniciar la ruta elegida
        if w < 1000:      # la persona vuelve a la vista compacta con el asa (flecha abajo): «Iniciar viaje» queda a la vista y recibe el toque
            p.focus('#sheetHandle'); p.keyboard.press('ArrowDown'); p.wait_for_timeout(900)
            assert p.evaluate("document.getElementById('sheet').dataset.state") == 'peek'
        toque(p, '#startTrip')
        B.esperar(p, "!document.getElementById('viajeCard').hidden && window.__geo.escuchas === 1", 6000)
        assert p.evaluate('Spevb.Viaje.activo()'), f'{nombre}: la ruta elegida inicia después de abrir y volver sin editar'
        s.limpio(nombre); s.cerrar()


@prueba
def editar_A_y_B_respeta_el_gesto_de_la_persona_y_cancela_el_posicionamiento_automatico(nav):
    s = movil(nav, 320, 568); p = s.abrir()
    p.fill('#tripOrigin', V.ESC['multi']); p.keyboard.press('Enter'); p.wait_for_timeout(500)
    p.fill('#tripDestination', V.DEST); p.keyboard.press('Enter'); p.wait_for_timeout(500)
    p.evaluate("document.querySelector('#planTrip').click()")
    B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 12000)
    # el posicionamiento automático de los resultados todavía está pendiente: la petición de la persona lo cancela y no lo deja pisar el formulario
    p.evaluate("window.dispatchEvent(new CustomEvent('spevb-editar-ab'))")
    p.wait_for_timeout(1400)
    f = p.evaluate(JS_FORM)
    assert f['A']['dentro'] and f['B']['dentro'] and f['foco'] == 'formAB', f
    s.limpio('editar tras resultados'); s.cerrar()


@prueba
def cambiar_un_punto_de_verdad_invalida_el_resultado_y_sin_cambios_no(nav):
    s = movil(nav, 390, 844); p = s.abrir()
    V.planear(p)
    toque(p, '#editarAB'); p.wait_for_timeout(700)
    assert p.evaluate("!document.getElementById('startTripBar').hidden"), 'abrir para editar no invalida nada'
    p.fill('#tripDestination', '4.1500, -73.6200'); p.keyboard.press('Enter'); p.wait_for_timeout(900)
    r = p.evaluate("({ barra: !document.getElementById('startTripBar').hidden, opciones: document.querySelectorAll('#tripResults .trip-option').length, sel: !!(Spevb.Planner.seleccion && Spevb.Planner.seleccion.viaje) })")
    assert not r['barra'] and r['opciones'] == 0 and not r['sel'], f'cambiar el destino aplica la invalidación normal del planificador: {r}'
    s.limpio('invalidar'); s.cerrar()


@prueba
def durante_el_viaje_un_toque_lleva_a_A_y_B_y_el_viaje_sigue_con_su_gps(nav):
    for nombre, w, h in TAMANOS[:2]:
        s = movil(nav, w, h); p = s.abrir()
        ls = iniciar_viaje(p)
        fase0 = V.card(p)['fase']
        assert p.is_visible('#panelShow') and p.inner_text('#panelShow').strip() == 'Editar A y B', f'{nombre}: durante el viaje el botón que trae el planificador dice «Editar A y B»: {p.inner_text("#panelShow")!r}'
        etiqueta = p.get_attribute('#panelShow', 'aria-label').lower()
        assert 'editar a y b' in etiqueta and 'viaje sigue' in etiqueta, etiqueta
        toque(p, '#panelShow'); p.wait_for_timeout(900)
        f = p.evaluate(JS_FORM)
        assert f['A']['dentro'] and f['B']['dentro'] and f['A']['recibe'] and f['foco'] == 'formAB' and not f['tecladoAbierto'], f'{nombre}: {f}'
        assert V.card(p)['fase'] == fase0 and p.evaluate('window.__geo.escuchas') == 1 and p.evaluate('Spevb.Viaje.activo()'), f'{nombre}: ver o editar A y B no reinicia el viaje ni duplica el GPS'
        assert p.get_attribute('#startTrip', 'aria-disabled') == 'true', f'{nombre}: con un viaje en curso no se puede sustituir sin una acción explícita («Iniciar viaje» sigue bloqueado)'
        # la persona edita B y busca otro plan: el viaje en curso sigue con SU plan
        titulo = p.evaluate("document.getElementById('viajeInstruccion').textContent")
        p.fill('#tripDestination', '4.1500, -73.6200'); p.keyboard.press('Enter'); p.wait_for_timeout(600)
        assert p.evaluate('Spevb.Viaje.activo()') and V.card(p)['fase'] == fase0 and p.evaluate('window.__geo.escuchas') == 1, f'{nombre}: editar B no toca el viaje'
        V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(300)
        assert V.card(p)['pregunta'] is not None, f'{nombre}: el viaje en curso siguió avisando con su plan original'
        s.limpio(nombre + ' viaje + editar'); s.cerrar()


@prueba
def al_terminar_el_viaje_el_boton_vuelve_a_su_rotulo_normal(nav):
    s = movil(nav, 390, 844); p = s.abrir()
    iniciar_viaje(p)
    assert p.inner_text('#panelShow').strip() == 'Editar A y B'
    p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(500)
    p.evaluate("Spevb.Panel.ocultar('usuario')"); p.wait_for_timeout(300)
    assert p.inner_text('#panelShow').strip() in ('Ver rutas', 'Buscar ruta'), p.inner_text('#panelShow')
    s.limpio('rotulo'); s.cerrar()


@prueba
def con_texto_muy_grande_movimiento_reducido_y_modo_oscuro_editar_A_y_B_y_la_pregunta_siguen_operables(nav):
    for variante in ('texto enorme', 'movimiento reducido', 'modo oscuro'):
        extra = {'reduced_motion': 'reduce'} if variante == 'movimiento reducido' else {'color_scheme': 'dark'} if variante == 'modo oscuro' else {}
        s = movil(nav, 320, 568, **extra); p = s.abrir()
        if variante == 'texto enorme':
            p.evaluate("document.documentElement.dataset.letra = 'enorme'"); p.wait_for_timeout(300)
        V.planear(p)
        p.evaluate("document.querySelector('#sheet .sheet-body').scrollTop = 0")
        p.focus('#sheetHandle'); p.keyboard.press('ArrowDown'); p.wait_for_timeout(500)
        r = p.evaluate("""() => { const e = document.getElementById('editarAB'), b = e.getBoundingClientRect(), t = getComputedStyle(e);
            const sb = document.querySelector('#sheet .sheet-body').getBoundingClientRect(); return { alto: b.height, visible: b.bottom <= innerHeight && b.bottom <= sb.bottom + 1 && b.top >= sb.top - 1, color: t.color, fondo: t.backgroundColor }; }""")
        if variante != 'texto enorme':
            assert r['visible'] and r['alto'] >= 44, f'{variante}: «Editar A y B» a la vista en la vista compacta: {r}'
        toque(p, '#editarAB') if r['visible'] else p.evaluate("document.getElementById('editarAB').click()")
        p.wait_for_timeout(900)
        f = p.evaluate(JS_FORM)
        assert f['A']['dentro'] and f['B']['dentro'] and f['foco'] == 'formAB', f'{variante}: {f}'
        # la pregunta urgente sobre el menú
        s.limpio(variante); s.cerrar()
    s = movil(nav, 320, 568, reduced_motion='reduce', color_scheme='dark'); p = s.abrir()
    ls = iniciar_viaje(p)
    p.click('#menuFlotante'); espera_menu(p)
    V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(500)
    comprobar_pregunta_compacta(p, 'oscuro + movimiento reducido')
    s.limpio('pregunta oscuro'); s.cerrar()
    s = movil(nav, 320, 568); p = s.abrir()
    p.evaluate("document.documentElement.dataset.letra = 'enorme'")
    ls = iniciar_viaje(p)
    p.click('#menuFlotante'); espera_menu(p)
    V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(500)
    d = p.evaluate(JS_PREGUNTA)
    assert d['urgente'] == '1' and d['siGolpea'] and d['noGolpea'] and d['bottom'] <= d['vh'] and d['alto'] <= 0.7 * d['vh'], f'texto enorme: la pregunta cabe y sus botones reciben el toque: {d}'
    assert set(recorrer_tab(p, 20)) <= {'viajeSi', 'viajeNo'}
    s.limpio('pregunta texto enorme'); s.cerrar()


# ============================================================================================================================ 2 · PRIORIDAD DE SUPERFICIES
JS_PREGUNTA = """() => { const c = document.getElementById('viajeCard'), r = c.getBoundingClientRect(); const si = document.getElementById('viajeSi').getBoundingClientRect(), no = document.getElementById('viajeNo').getBoundingClientRect();
  const golpe = (b) => { const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return !!e && !!e.closest('#viajePregunta'); };
  const menu = document.getElementById('sideMenu');
  return { vh: innerHeight, urgente: c.dataset.urgente, top: Math.round(r.top), bottom: Math.round(r.bottom), alto: Math.round(r.height), siAlto: Math.round(si.height), noAlto: Math.round(no.height), siAncho: Math.round(si.width),
    siGolpea: golpe(si), noGolpea: golpe(no), foco: document.activeElement.id, menuInert: menu.inert, menuAbierto: menu.classList.contains('open'), visibles: [...c.querySelectorAll('.viaje-pregunta, .viaje-aviso')].filter(e => e.offsetParent !== null).length,
    texto: document.getElementById('viajePreguntaTexto').textContent }; }"""


def comprobar_pregunta_compacta(p, nombre):
    d = p.evaluate(JS_PREGUNTA)
    assert d['urgente'] == '1' and d['visibles'] == 1, f'{nombre}: una sola pregunta vigente: {d}'
    assert d['alto'] <= 0.4 * d['vh'] and d['alto'] <= 290, f'{nombre}: la pregunta se ajusta a su contenido (no media pantalla): {d}'
    assert 44 <= d['siAlto'] <= 72 and 44 <= d['noAlto'] <= 72 and d['siAncho'] >= 100, f'{nombre}: botones cómodos, sin estirarse: {d}'
    assert d['siGolpea'] and d['noGolpea'], f'{nombre}: ambos botones reciben el toque: {d}'
    assert d['top'] >= 0 and d['bottom'] <= d['vh'], d
    return d


def recorrer_tab(p, veces=30, atras=False):
    vistos = []
    for _ in range(veces):
        p.keyboard.press('Shift+Tab' if atras else 'Tab')
        vistos.append(p.evaluate("document.activeElement.id || document.activeElement.tagName"))
    return vistos


@prueba
def la_pregunta_de_subida_sobre_el_menu_es_compacta_y_operable_con_tacto_teclado_y_escape(nav):
    for nombre, w, h in TAMANOS[:2]:
        s = movil(nav, w, h); p = s.abrir()
        ls = iniciar_viaje(p)
        fase0 = V.card(p)['fase']
        p.click('#menuFlotante'); espera_menu(p)
        p.evaluate("document.getElementById('sideMenu').scrollTop = 260"); p.wait_for_timeout(150)
        scroll0 = p.evaluate("document.getElementById('sideMenu').scrollTop")
        V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(500)
        d = comprobar_pregunta_compacta(p, nombre)
        assert d['foco'] == 'viajeSi' and d['menuInert'], f'{nombre}: el foco entra en la pregunta y el menú queda inerte debajo: {d}'
        assert 'ruta' in d['texto'].lower(), d
        vistos = recorrer_tab(p, 30)
        assert set(vistos) <= {'viajeSi', 'viajeNo'} and {'viajeSi', 'viajeNo'} <= set(vistos), f'{nombre}: en 30 Tab se llega a «Sí» y «Todavía no» y no se sale de la pregunta: {sorted(set(vistos))}'
        assert set(recorrer_tab(p, 8, atras=True)) <= {'viajeSi', 'viajeNo'}, f'{nombre}: Shift+Tab también se queda en la pregunta'
        # Escape se aplica a la superficie con el foco (la pregunta): «Todavía no». El menú sigue abierto, en su mismo sitio, y el foco vuelve a un control suyo.
        p.keyboard.press('Escape'); p.wait_for_timeout(450)
        r = p.evaluate("""() => ({ pregunta: document.getElementById('viajePregunta').hidden, urgente: document.getElementById('viajeCard').dataset.urgente || null, menuAbierto: document.getElementById('sideMenu').classList.contains('open'),
            menuInert: document.getElementById('sideMenu').inert, foco: document.activeElement.id || document.activeElement.tagName, focoEnMenu: !!document.activeElement.closest('#sideMenu'), scroll: document.getElementById('sideMenu').scrollTop })""")
        assert r['pregunta'] and r['urgente'] is None, f'{nombre}: Escape resolvió la pregunta: {r}'
        assert r['menuAbierto'] and not r['menuInert'] and r['focoEnMenu'], f'{nombre}: el menú sigue abierto, activo, y el foco vuelve a un control visible suyo: {r}'
        assert abs(r['scroll'] - scroll0) <= 2, f'{nombre}: el menú conserva su desplazamiento ({scroll0} → {r["scroll"]})'
        assert V.card(p)['fase'] == fase0 and p.evaluate('window.__geo.escuchas') == 1 and p.evaluate('Spevb.Viaje.activo()'), f'{nombre}: el viaje sigue sin duplicar el GPS'
        # Escape ahora cierra el MENÚ (ya es la superficie de arriba), no la pregunta
        p.keyboard.press('Escape'); p.wait_for_timeout(450)
        assert sup(p)['overlay'] is None, f'{nombre}: con la pregunta resuelta, Escape cierra el menú'
        s.limpio(nombre + ' subida/menu'); s.cerrar()


@prueba
def responder_si_con_el_teclado_sobre_el_menu_avanza_el_viaje_y_devuelve_el_control(nav):
    s = movil(nav, 320, 568); p = s.abrir()
    ls = iniciar_viaje(p)
    p.click('#menuFlotante'); espera_menu(p)
    V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(450)
    assert p.evaluate("document.activeElement.id") == 'viajeSi'
    p.keyboard.press('Enter'); p.wait_for_timeout(450)
    assert V.card(p)['fase'] == 'en_bus', 'la respuesta con teclado llegó al viaje'
    r = p.evaluate("({ menuAbierto: document.getElementById('sideMenu').classList.contains('open'), inert: document.getElementById('sideMenu').inert, focoEnMenu: !!document.activeElement.closest('#sideMenu') })")
    assert r['menuAbierto'] and not r['inert'] and r['focoEnMenu'], r
    assert p.evaluate('window.__geo.escuchas') == 1
    s.limpio('responder con teclado'); s.cerrar()


@prueba
def la_pregunta_de_bajada_sobre_el_menu_tambien_es_compacta_y_operable(nav):
    s = movil(nav, 320, 568); p = s.abrir()
    ls = iniciar_viaje(p)
    i = V.alimentar(p, ls, 0, 'pregunta')                          # primero la de subida, que se contesta como siempre
    p.click('#viajeSi'); p.wait_for_timeout(300)
    assert V.card(p)['fase'] == 'en_bus'
    p.click('#menuFlotante'); espera_menu(p)
    V.alimentar(p, ls, i, 'pregunta'); p.wait_for_timeout(500)
    d = comprobar_pregunta_compacta(p, 'bajada')
    assert d['foco'] == 'viajeSi' and 'baj' in d['texto'].lower(), f'es la pregunta de bajada, con el foco dentro: {d}'
    assert set(recorrer_tab(p, 30)) <= {'viajeSi', 'viajeNo'}
    p.keyboard.press('Escape'); p.wait_for_timeout(450)
    assert p.evaluate("document.getElementById('viajePregunta').hidden") and sup(p)['overlay'] == 'menu'
    assert V.card(p)['fase'] == 'en_bus' and p.evaluate('window.__geo.escuchas') == 1
    s.limpio('bajada/menu'); s.cerrar()


@prueba
def la_pregunta_sobre_un_dialogo_de_cuenta_es_operable_y_el_dialogo_conserva_lo_escrito(nav):
    s = movil(nav, 320, 568); p = s.abrir()
    ls = iniciar_viaje(p)
    p.click('#menuFlotante'); espera_menu(p)
    toque(p, '#accountLogin'); p.wait_for_timeout(500)
    assert sup(p)['overlay'] == 'modal', sup(p)
    p.fill('#authEmail', 'persona@example.com')
    V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(500)
    d = comprobar_pregunta_compacta(p, 'cuenta')
    assert d['foco'] == 'viajeSi', d
    assert set(recorrer_tab(p, 30)) <= {'viajeSi', 'viajeNo'}, 'Tab se queda en la pregunta, no en el diálogo de cuenta de abajo'
    p.keyboard.press('Escape'); p.wait_for_timeout(450)
    r = p.evaluate("({ pregunta: document.getElementById('viajePregunta').hidden, modal: !document.getElementById('authModal').hidden, valor: document.getElementById('authEmail').value, foco: document.activeElement.id, inert: document.getElementById('authModal').inert })")
    assert r['pregunta'] and r['modal'] and r['valor'] == 'persona@example.com' and not r['inert'], f'Escape resolvió la pregunta y NO cerró el diálogo: {r}'
    assert r['foco'] == 'authEmail', f'el foco vuelve al campo que la persona usaba: {r}'
    assert V.card(p)['fase'] == 'esperando' and p.evaluate('window.__geo.escuchas') == 1
    s.limpio('pregunta/dialogo'); s.cerrar()


@prueba
def abrir_el_menu_con_una_pregunta_pendiente_deja_la_pregunta_con_prioridad(nav):
    s = movil(nav, 360, 640); p = s.abrir()
    ls = iniciar_viaje(p)
    V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(400)
    assert V.card(p)['pregunta'], 'la pregunta está a la vista antes de abrir el menú'
    p.click('#menuFlotante'); espera_menu(p)
    d = comprobar_pregunta_compacta(p, 'menu después')
    assert d['foco'] == 'viajeSi', d
    assert set(recorrer_tab(p, 30)) <= {'viajeSi', 'viajeNo'}
    p.click('#viajeSi'); p.wait_for_timeout(400)
    assert V.card(p)['fase'] == 'en_bus' and sup(p)['overlay'] == 'menu'
    s.limpio('menu con pregunta'); s.cerrar()


@prueba
def sin_menu_ni_dialogo_la_pregunta_no_encierra_el_foco_ni_apaga_el_resto(nav):
    s = movil(nav, 390, 844); p = s.abrir()
    ls = iniciar_viaje(p)
    V.alimentar(p, ls, 0, 'pregunta'); p.wait_for_timeout(400)
    assert not p.evaluate("document.getElementById('menuFlotante').closest('[inert]') !== null"), 'sin menú abierto, el resto de la pantalla sigue activo'
    assert p.evaluate("Spevb.Modal.hayAbierta()") is False
    s.limpio('pregunta libre'); s.cerrar()


# ============================================================================================================================ 2b · MENÚ POR FASES
JS_MENU = """() => { const m = document.getElementById('sideMenu'); return +(m.scrollHeight / innerHeight).toFixed(2); }"""
FUNCIONES = ['#accountSettings', '#accountLogout', '[data-atajo="Casa"]', '[data-atajo="Trabajo"]', '#espacio', '#favorites', '#logros', '#menuBienvenida', '#menuPractica', '#menuVista', '#menuOffline', '#colorGuide', '#nearOriginRoutes', '#menuExplorar', '#closeMenu', '#menuInicio']


@prueba
def el_menu_mide_menos_en_cada_fase_y_conserva_todas_las_funciones(nav):
    s = movil(nav, 320, 568); con_cuenta(s, usuario()); p = s.abrir()
    p.click('#menuButton'); espera_menu(p)
    inicial = p.evaluate(JS_MENU)
    assert inicial <= 2.2, f'menú inicial a 320 × 568: {inicial} pantallas (antes ≈ 2,6)'
    for sel in FUNCIONES:
        assert p.locator(sel).count() == 1, f'falta {sel} en el menú'
    assert p.evaluate("document.getElementById('menuEspacio').open"), 'en planificación «Mi espacio» (Casa/Trabajo, historial, lugares) va abierto'
    assert p.is_visible('#closeMenu')
    p.click('#closeMenu'); espera_menu(p)
    iniciar_viaje(p)
    p.click('#menuFlotante'); espera_menu(p)
    viaje = p.evaluate(JS_MENU)
    assert viaje <= 1.7 and viaje < inicial, f'menú durante el viaje: {viaje} pantallas (antes ≈ 3,6); inicial {inicial}'
    orden = p.evaluate("[...document.getElementById('sideMenu').children].map(e => e.id).filter(Boolean)")
    assert orden.index('menuVista') < orden.index('menuEspacio') and orden.index('menuOffline') < orden.index('menuEspacio'), f'en viaje lo que necesita el pasajero va primero: {orden}'
    assert not p.evaluate("document.getElementById('menuEspacio').open"), 'en viaje lo de planear queda plegado (sigue disponible)'
    for sel in FUNCIONES:
        assert p.locator(sel).count() == 1, f'durante el viaje falta {sel}'
    # lo plegado sigue disponible con un toque
    p.evaluate("document.getElementById('menuEspacio').querySelector('summary').click()"); p.wait_for_timeout(200)
    assert p.is_visible('[data-atajo="Casa"]') and p.is_visible('#favorites summary')
    assert p.evaluate('window.__geo.escuchas') == 1 and p.evaluate('Spevb.Viaje.activo()')
    # al terminar el viaje el menú vuelve al orden de planificación
    p.click('#closeMenu'); espera_menu(p)
    p.evaluate('Spevb.Viaje.detener()'); p.wait_for_timeout(400)
    p.click('#menuButton') if p.is_visible('#menuButton') else p.click('#menuFlotante'); espera_menu(p)
    orden = p.evaluate("[...document.getElementById('sideMenu').children].map(e => e.id).filter(Boolean)")
    assert orden.index('menuEspacio') < orden.index('menuVista'), f'de nuevo el orden de planificación: {orden}'
    s.limpio('menu fases'); s.cerrar()


@prueba
def la_ficha_de_la_ruta_ya_no_alarga_el_menu_del_viaje(nav):
    s = movil(nav, 320, 568); con_cuenta(s, usuario()); p = s.abrir()
    assert p.evaluate("document.getElementById('routeCard').closest('#menuExplorar') !== null"), 'la ficha vive dentro de «Explorar recorridos»'
    s.limpio('ficha'); s.cerrar()


# ============================================================================================================================ 3 · FOTO DE PERFIL
JS_AVATAR = """(id) => { const e = document.getElementById(id), img = e.querySelector('img'), cs = getComputedStyle(e), ci = img ? getComputedStyle(img) : null;
  return { conFoto: e.classList.contains('con-foto'), img: !!img, src: img ? img.getAttribute('src') : null, alt: img ? img.getAttribute('alt') : null, ancho: Math.round(e.getBoundingClientRect().width), alto: Math.round(e.getBoundingClientRect().height),
    radio: cs.borderRadius, fondo: cs.backgroundImage, ajuste: ci ? ci.objectFit : null, opacidad: ci ? ci.opacity : null, natural: img ? img.naturalWidth : 0, referrer: img ? img.referrerPolicy : null }; }"""


def abrir_menu_y_leer(p, id='accountAvatar', espera=700):
    if not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"):
        p.click('#menuButton')
    p.wait_for_timeout(espera)
    return p.evaluate(JS_AVATAR, id)


@prueba
def la_foto_de_google_se_ve_en_un_circulo_fijo_recortada_y_solo_al_ver_el_perfil(nav):
    s = movil(nav, 390, 844); con_cuenta(s, usuario(foto=FOTO))
    pedidas = []
    s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: (pedidas.append(r.request.url), r.fulfill(status=200, content_type='image/png', body=PNG)))
    p = s.abrir(espera=1200)
    assert not pedidas, f'la foto no se pide hasta que el perfil se va a ver: {pedidas}'
    a = abrir_menu_y_leer(p)
    assert pedidas and a['conFoto'] and a['img'] and a['natural'] > 0, f'la foto carga y se muestra: {a}'
    assert a['alt'] == '' and a['referrer'] == 'no-referrer', a
    assert a['ancho'] == 40 and a['alto'] == 40 and '50%' in a['radio'] and a['ajuste'] == 'cover' and a['opacidad'] == '1', f'círculo de tamaño fijo con recorte centrado: {a}'
    assert 'sevb-cabeza-96.png' in a['fondo'], 'el chigüiro de respaldo queda debajo'
    # «Ajustes de la cuenta» muestra el mismo perfil
    toque(p, '#accountSettings'); p.wait_for_timeout(600)
    a2 = p.evaluate(JS_AVATAR, 'setAvatar')
    assert a2['conFoto'] and a2['ancho'] == 40 and a2['alto'] == 40 and a2['src'] == FOTO, f'la foto también está en los ajustes: {a2}'
    s.limpio('foto valida'); s.cerrar()


@prueba
def sin_foto_o_con_una_foto_no_valida_se_ve_el_chiguiro_y_no_se_pide_nada(nav):
    for nombre, foto in (('ausente', None), ('http', 'http://lh3.googleusercontent.com/a/x'), ('otro host', 'https://evil.example.com/foto.png'), ('esquema raro', 'javascript:alert(1)'), ('vacía', '')):
        s = movil(nav, 390, 844); con_cuenta(s, usuario(foto=foto))
        pedidas = []
        s.ctx.route('**/*googleusercontent*/**', lambda r: (pedidas.append(r.request.url), r.fulfill(status=200, content_type='image/png', body=PNG)))
        s.ctx.route('https://evil.example.com/**', lambda r: (pedidas.append(r.request.url), r.abort()))
        s.ctx.route('http://lh3.googleusercontent.com/**', lambda r: (pedidas.append(r.request.url), r.abort()))
        p = s.abrir(espera=1000)
        a = abrir_menu_y_leer(p)
        assert not a['img'] and not a['conFoto'] and 'sevb-cabeza-96.png' in a['fondo'] and a['ancho'] == 40, f'{nombre}: avatar local de inmediato: {a}'
        assert not pedidas, f'{nombre}: una foto no válida no se pide nunca: {pedidas}'
        assert p.evaluate("!document.getElementById('accountUser').hidden"), f'{nombre}: la foto nunca es requisito para la sesión'
        s.limpio('foto ' + nombre); s.cerrar()


@prueba
def si_la_foto_falla_al_cargar_o_no_hay_internet_queda_el_avatar_local_sin_imagen_rota(nav):
    s = movil(nav, 390, 844); con_cuenta(s, usuario(foto=FOTO))
    s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: r.fulfill(status=404, content_type='text/plain', body='no'))
    p = s.abrir(espera=1000)
    a = abrir_menu_y_leer(p)
    assert not a['conFoto'] and not a['img'] and 'sevb-cabeza-96.png' in a['fondo'], f'foto rota: se queda el chigüiro: {a}'
    s.cerrar()
    s = movil(nav, 390, 844); con_cuenta(s, usuario(foto=FOTO))
    s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: r.abort('internetdisconnected'))
    p = s.abrir(espera=1000)
    a = abrir_menu_y_leer(p)
    assert not a['conFoto'] and not a['img'] and 'sevb-cabeza-96.png' in a['fondo'], f'sin internet: {a}'
    s.limpio('foto falla'); s.cerrar()


@prueba
def sesion_restaurada_sin_conexion_con_la_foto_guardada_no_rompe_el_avatar(nav):
    s = movil(nav, 390, 844)
    p = s.abrir(espera=800)
    p.evaluate("(u) => localStorage.setItem('spevb-usuario', JSON.stringify(u))", usuario(foto=FOTO))
    s.ctx.route('**/api/cuenta/yo', lambda r: r.abort('internetdisconnected'))
    s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: r.abort('internetdisconnected'))
    p.reload(wait_until='domcontentloaded'); p.wait_for_timeout(1500)
    a = abrir_menu_y_leer(p)
    assert p.evaluate("!document.getElementById('accountUser').hidden") and 'sin conexión' in p.inner_text('#accountEmail'), 'se muestra el último usuario conocido'
    assert not a['conFoto'] and 'sevb-cabeza-96.png' in a['fondo'], a
    s.limpio('sesion restaurada'); s.cerrar()


@prueba
def al_cerrar_sesion_o_cambiar_de_cuenta_una_foto_tardia_nunca_se_muestra_en_otra_persona(nav):
    s = movil(nav, 390, 844); con_cuenta(s, usuario(foto=FOTO))
    retenida = []
    s.ctx.route(FOTO, lambda r: retenida.append(r))
    s.ctx.route(FOTO_B, lambda r: r.fulfill(status=200, content_type='image/png', body=PNG))
    s.ctx.route('**/api/cuenta/salir', lambda r: json_ok(r, {'ok': True}))
    s.ctx.route('**/api/cuenta/entrar', lambda r: json_ok(r, {'usuario': usuario('beto@example.com', 'Beto', FOTO_B)}))
    p = s.abrir(espera=1000)
    p.click('#menuButton'); p.wait_for_timeout(600)
    assert retenida, 'la foto de Ana está pendiente (la respuesta se retiene)'
    toque(p, '#accountLogout'); p.wait_for_timeout(700)          # cierra sesión mientras la foto de Ana aún no llegó
    assert p.evaluate(JS_AVATAR, 'accountAvatar')['img'] is False, 'al cerrar sesión se limpia el avatar'
    p.evaluate("Spevb.Cuenta.entrar('beto@example.com', 'clave-larga-1')"); p.wait_for_timeout(500)
    p.click('#menuButton'); p.wait_for_timeout(900)
    for r in retenida:           # ahora llega, tarde, la foto de Ana
        r.fulfill(status=200, content_type='image/png', body=PNG)
    p.wait_for_timeout(600)
    a = p.evaluate(JS_AVATAR, 'accountAvatar')
    assert a['src'] == FOTO_B and a['conFoto'], f'solo se ve la foto de la cuenta actual (Beto): {a}'
    assert p.inner_text('#accountName') == 'Beto'
    s.limpio('cambio de cuenta'); s.cerrar()


@prueba
def la_politica_csp_de_ambos_mapas_permite_solo_el_origen_de_imagenes_de_la_foto(nav):
    for modo in ('leaflet', 'google'):
        texto = (RAIZ / 'src' / 'test' / 'resources' / 'csp' / (modo + '.txt')).read_text(encoding='utf-8')
        img = [d.strip() for d in texto.split(';') if d.strip().startswith('img-src')][0]
        assert 'googleusercontent.com' in img, f'{modo}: img-src permite las fotos de Google: {img}'
        assert 'googleusercontent.com' not in [d.strip() for d in texto.split(';') if d.strip().startswith('connect-src')][0], f'{modo}: connect-src no se amplía'
        if modo == 'leaflet':
            assert 'googleusercontent.com' not in [d.strip() for d in texto.split(';') if d.strip().startswith('script-src')][0], 'leaflet: script-src no se amplía'
    s = movil(nav, 390, 844); p = s.abrir()
    cabecera = p.evaluate("fetch('/').then(r => r.headers.get('content-security-policy'))")
    assert cabecera and 'googleusercontent.com' in cabecera.split('img-src')[1].split(';')[0], cabecera
    s.limpio('csp'); s.cerrar()


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
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas del flujo del pasajero 4.14; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
