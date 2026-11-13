"""Pruebas de navegador del CICLO DE VIDA ÚNICO del viaje (4.15.1): un solo viaje a la vez, en esta pestaña y entre pestañas.

Qué demuestran: doble toque = una sola sesión; un segundo intento (planificador, flujo guiado) abre «Ya tienes un viaje en curso» y no cambia nada; cancelar y «Volver a mi viaje»;
terminar exige confirmación y solo entonces se libera TODO (GPS, temporizadores, Wake Lock, audio, capas, ruta consumible, enlace compartido y su token, clases, estado guardado, bloqueo);
recargar conserva el bloqueo y ofrece «Reanudar viaje»; un estado guardado corrupto o vencido se limpia; la llegada bloquea hasta «Cerrar»; dos pestañas no pueden iniciar dos viajes.
Qué NO es: el GPS, el Wake Lock y la red son simulados (e2e/simulador_gps.js, dobles de viaje_e2e.py); el backend es un stub; no prueba un teléfono real.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/ciclo_viaje_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import json
import os
import sys
import time
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
import compartir_e2e as C  # noqa: E402
import guiado_e2e as G  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
MOVIL = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
CLAVE_VIAJE, CLAVE_BLOQUEO = 'spevb-viaje-curso', 'spevb-viaje-bloqueo'
# cuenta cuántas veces se PIDIÓ un observador de GPS (window.__geo.escuchas solo dice cuántos hay vivos ahora)
CONTAR_WATCH = "(() => { const g = navigator.geolocation; const w = g.watchPosition.bind(g); window.__watches = 0; g.watchPosition = (...a) => { window.__watches++; return w(...a); }; })();"


def prueba(f):
    PRUEBAS.append(f)
    return f


def preparar(nav, **opts):
    """Sesión móvil con un plan calculado y SIN viaje iniciado."""
    s = V.sesion(nav, **{**MOVIL, **opts})
    s.ctx.add_init_script(CONTAR_WATCH)
    p = s.ctx.pages[0]
    p.goto(B.URL, wait_until='domcontentloaded')
    B.esperar(p, "!!(window.Spevb && Spevb.maps && Spevb.maps.map)", 20000)
    p.wait_for_timeout(1500)
    p.evaluate("fetch('/__log/limpiar')")
    V.planear(p)
    V.destino_lejos(p)
    return s, p, V.lecturas(p)


def empezar(nav, **opts):
    s, p, ls = preparar(nav, **opts)
    V.iniciar(p)
    return s, p, ls


def diag(p):
    return p.evaluate('Spevb.Viaje.diagnostico()')


def rutas_vivas(p):
    return p.evaluate('Spevb.ViajeRuta.vivas()')


def lineas_viaje(p):
    return p.evaluate("""() => { let n = 0; Spevb.maps.map.elementos().forEach((e) => { if (e.tipo === 'linea' && (e.peso === 7 || e.peso === 11)) n++; }); return n; }""")


def dialogo(p):
    return p.evaluate("""() => { const d = document.getElementById('viajeConflicto'); if (!d || d.hidden) return null; const t = (id) => document.getElementById(id);
        const b = (id) => ({ texto: t(id).textContent.trim(), visible: !t(id).hidden && t(id).getClientRects().length > 0 });
        return { titulo: t('conflTitulo').textContent.trim(), texto: t('conflTexto').textContent.trim(), volver: b('conflVolver'), terminar: b('conflTerminar'), cancelar: b('conflCancelar'), foco: document.activeElement.id }; }""")


def intentar_otro(p):
    """Elige la segunda opción (si hay) y toca «Iniciar viaje» como lo haría la persona desde el planificador (el panel se trae primero)."""
    p.evaluate("Spevb.Panel.mostrar('usuario')")
    p.evaluate("(() => { const s = document.querySelectorAll('#tripResults .trip-option > summary')[1]; if (s) s.click(); })()")
    p.wait_for_timeout(200)
    p.evaluate("document.getElementById('startTrip').click()")
    p.wait_for_timeout(450)


def sin_nada_vivo(p):
    d = diag(p)
    assert d['ciclo'] == 'libre' and d['id'] is None and not d['gps'] and d['timers'] == 0 and not d['capa'] and not d['ruta'] and not d['wake'] and not d['latido'] and d['bloqueo'] is None, d
    assert p.evaluate('window.__geo.escuchas') == 0, 'no queda ningún observador GPS'
    assert rutas_vivas(p) == 0 and lineas_viaje(p) == 0, 'no queda ninguna ruta consumible ni sus líneas'
    assert p.evaluate("localStorage.getItem('spevb-viaje-curso')") is None and p.evaluate("localStorage.getItem('spevb-viaje-bloqueo')") is None, 'ni estado guardado ni bloqueo'
    assert p.evaluate("!document.body.classList.contains('viaje-activo')") and p.evaluate("document.getElementById('viajeCard').hidden")
    w = p.evaluate('window.__wake')
    assert w['pedidos'] == w['soltados'], f'todo Wake Lock pedido fue soltado: {w}'


def viaje_unico(p, creadas=1):
    d = diag(p)
    assert d['ciclo'] == 'activo' and d['gps'] and d['timers'] == 2 and d['capa'] is not None and d['ruta'] and d['creadas'] == creadas and d['creadas'] - d['liberadas'] == 1, d
    assert p.evaluate('window.__geo.escuchas') == 1, 'exactamente un observador GPS'
    assert rutas_vivas(p) == 1, 'exactamente una ruta consumible'
    return d


# ================================================================================================================== 1 · doble toque
@prueba
def doble_toque_sobre_iniciar_viaje_crea_una_sola_sesion(nav):
    s, p, ls = preparar(nav)
    p.evaluate("(() => { const b = document.getElementById('startTrip'); b.click(); b.click(); b.click(); })()")      # tres toques en el mismo instante
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas >= 1", 6000)
    p.wait_for_timeout(600)
    d = viaje_unico(p)
    assert p.evaluate('window.__watches') == 1, 'se pidió UN solo observador GPS en total'
    assert dialogo(p) is None, 'el segundo toque durante la preparación no abre ninguna explicación'
    # un doble toque real con el ratón sobre el botón, antes de empezar, en otra sesión de navegador
    s.limpio('doble toque'); s.cerrar()
    s, p, ls = preparar(nav)
    r = p.evaluate("(() => { const b = document.getElementById('startTrip').getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return { x: b.left + b.width / 2, y: b.top + b.height / 2, golpea: !!e && !!e.closest('#startTrip') }; })()")
    assert r['golpea'], f'el botón recibe el toque: {r}'
    p.mouse.dblclick(r['x'], r['y'])      # doble toque REAL
    B.esperar(p, "Spevb.Viaje.activo()", 6000)
    p.wait_for_timeout(600)
    viaje_unico(p)
    assert p.evaluate('window.__watches') == 1
    s.limpio('doble clic'); s.cerrar()


@prueba
def el_boton_comunica_ocupado_y_en_curso_sin_dejar_de_recibir_toques(nav):
    s, p, ls = preparar(nav)
    assert p.get_attribute('#startTrip', 'aria-disabled') == 'false' and (p.text_content('#startTrip') or '').strip() == 'Iniciar viaje'
    V.iniciar(p)
    assert p.get_attribute('#startTrip', 'aria-disabled') == 'true' and (p.text_content('#startTrip') or '').strip() == 'Viaje en curso' and p.get_attribute('#startTrip', 'aria-busy') == 'false'
    assert not p.evaluate("document.getElementById('startTrip').disabled"), 'no está deshabilitado: el toque abre la explicación'
    s.limpio('boton'); s.cerrar()


@prueba
def terminar_antes_de_que_llegue_el_permiso_cancela_el_inicio_sin_dejar_nada_vivo(nav):
    s, p, ls = preparar(nav)
    p.evaluate("(() => { Spevb.Viaje.iniciar(); Spevb.Viaje.detener(); })()")      # el inicio espera el permiso de GPS; se cancela antes de que llegue
    p.wait_for_timeout(900)
    sin_nada_vivo(p)
    # y después se puede empezar con normalidad
    V.iniciar(p)
    viaje_unico(p)
    s.limpio('cancelar preparacion'); s.cerrar()


# ================================================================================================================== 2-4 · segundo intento
@prueba
def un_segundo_inicio_muestra_ya_tienes_un_viaje_en_curso_y_cancelar_conserva_el_primero(nav):
    s, p, ls = empezar(nav)
    V.alimentar(p, ls, 0, 'fase:esperando')
    antes = viaje_unico(p)
    lineas0 = lineas_viaje(p)
    fase0 = V.card(p)['fase']
    intentar_otro(p)
    d = dialogo(p)
    assert d, 'se muestra el diálogo'
    assert d['titulo'] == 'Ya tienes un viaje en curso' and d['texto'] == 'Termina el viaje actual antes de empezar otro.', d
    assert d['volver']['texto'] == 'Volver a mi viaje' and d['terminar']['texto'] == 'Terminar viaje actual' and d['cancelar']['texto'] == 'Cancelar', d
    assert d['foco'] == 'conflVolver', f'la opción segura recibe el foco: {d}'
    assert not any(c in d['texto'].lower() for c in ('reemplaz',)), 'no se ofrece «reemplazar»'
    # lo primero que se ve no cambió nada
    assert diag(p)['id'] == antes['id'] and p.evaluate('window.__geo.escuchas') == 1 and lineas_viaje(p) == lineas0 and V.card(p)['fase'] == fase0
    # Escape = Cancelar
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert dialogo(p) is None, 'Escape cierra sin hacer nada'
    intentar_otro(p)
    assert dialogo(p) is not None
    p.click('#conflCancelar'); p.wait_for_timeout(300)
    assert dialogo(p) is None
    despues = viaje_unico(p)
    assert despues['id'] == antes['id'] and despues['creadas'] == 1 and rutas_vivas(p) == 1 and lineas_viaje(p) == lineas0, 'el primer viaje sigue intacto'
    assert V.card(p)['fase'] == fase0 and p.evaluate('Spevb.Viaje.activo()')
    s.limpio('cancelar'); s.cerrar()


@prueba
def volver_a_mi_viaje_abre_la_tarjeta_y_el_mapa_del_primero(nav):
    s, p, ls = empezar(nav)
    V.alimentar(p, ls, 0, 'fase:caminar')
    id0 = diag(p)['id']
    p.click('#viajeOcultar'); p.wait_for_timeout(300)                  # la persona ocultó la tarjeta…
    p.evaluate("Spevb.maps.map.setView([4.2, -73.5], 12)")      # … movió el mapa lejos…
    p.evaluate("Spevb.Panel.mostrar('usuario')")                       # … y trajo el planificador
    p.wait_for_timeout(300)
    intentar_otro(p)
    assert dialogo(p)
    p.click('#conflVolver'); p.wait_for_timeout(700)
    r = p.evaluate("""() => { const c = document.getElementById('viajeCard'), m = Spevb.maps.map, ctr = m.getCenter(), lat = ctr.lat !== undefined ? ctr.lat : ctr[0], lng = ctr.lng !== undefined ? ctr.lng : ctr[1];
        return { visible: !c.hidden && getComputedStyle(c).visibility !== 'hidden', modo: c.dataset.modo, panelOculto: document.body.classList.contains('panel-oculto'), lat, lng, seguir: document.getElementById('viajeSeguir').getAttribute('aria-pressed'),
                 dialogo: !!document.querySelector('#viajeConflicto:not([hidden])') }; }""")
    assert r['visible'] and r['modo'] == 'completa' and r['panelOculto'] and not r['dialogo'], r
    assert abs(r['lat'] - 4.15) < 0.06 and abs(r['lng'] + 73.63) < 0.06 and r['seguir'] == 'true', f'el mapa volvió a la posición del viaje: {r}'
    assert diag(p)['id'] == id0 and p.evaluate('window.__geo.escuchas') == 1
    s.limpio('volver a mi viaje'); s.cerrar()


# ================================================================================================================== 5 · terminar explícito
@prueba
def terminar_exige_confirmacion_libera_todo_y_solo_entonces_permite_el_segundo(nav):
    s, p, ls = empezar(nav)
    V.alimentar(p, ls, 0, 'fase:caminar')
    C.crear_enlace(p)                                         # el viaje también se está compartiendo
    assert p.evaluate('Spevb.Compartir.activo()') and C.tokens(p), 'hay un enlace con token de escritura'
    p.keyboard.press('Escape'); p.wait_for_timeout(200)
    id0 = diag(p)['id']
    intentar_otro(p)
    p.click('#conflTerminar'); p.wait_for_timeout(300)
    d = dialogo(p)
    assert d and 'No se puede deshacer' in d['texto'] and d['terminar']['texto'] == 'Sí, terminar viaje' and d['volver']['texto'] == 'No, seguir con mi viaje' and not d['cancelar']['visible'], d
    assert d['foco'] == 'conflVolver', 'en la confirmación la opción segura tiene el foco'
    assert p.evaluate('Spevb.Viaje.activo()') and diag(p)['id'] == id0, 'un solo toque NO termina el viaje'
    # «No, seguir con mi viaje»: nada cambia
    p.click('#conflVolver'); p.wait_for_timeout(500)
    assert dialogo(p) is None and diag(p)['id'] == id0 and p.evaluate('window.__geo.escuchas') == 1
    # ahora sí: confirmación explícita
    intentar_otro(p)
    p.click('#conflTerminar'); p.wait_for_timeout(250)
    p.click('#conflTerminar'); p.wait_for_timeout(900)
    assert dialogo(p) is None
    sin_nada_vivo(p)
    assert p.evaluate('Spevb.Compartir.activo()') is False and C.tokens(p) is None, 'el enlace compartido y su token se liberaron'
    log = C.log_compartir(p)
    assert [x['metodo'] for x in log].count('POST') == 1 and [x['metodo'] for x in log].count('DELETE') == 1, f'un enlace creado y revocado: {log}'
    assert p.evaluate('Spevb.Viaje.llego()') is False
    # el segundo viaje ya puede empezar
    p.evaluate("Spevb.Panel.mostrar('usuario')")
    p.evaluate("document.getElementById('startTrip').click()")
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 6000)
    d2 = viaje_unico(p, creadas=2)
    assert d2['id'] != id0, 'es otro viaje, con otra identidad'
    assert p.evaluate('Spevb.Compartir.activo()') is False, 'el nuevo viaje no hereda el enlace del anterior'
    C.limpio_salvo_4xx(s, 'terminar')
    s.cerrar()


# ================================================================================================================== 6 · recargar
@prueba
def recargar_conserva_el_bloqueo_y_permite_reanudar_el_mismo_viaje(nav):
    s, p, ls = empezar(nav)
    V.alimentar(p, ls, 0, 'fase:esperando')
    id0 = diag(p)['id']
    p.evaluate("window.dispatchEvent(new Event('pagehide'))")
    p.reload(wait_until='domcontentloaded')
    B.esperar(p, "!!(window.Spevb && Spevb.Viaje && Spevb.maps && Spevb.maps.map)", 20000)
    p.wait_for_timeout(1200)
    c = V.card(p)
    assert c['fase'] == 'reanudar' and p.inner_text('#viajeSi') == 'Reanudar viaje', c
    assert p.evaluate('Spevb.Viaje.estadoCiclo()') == 'pendiente' and p.evaluate('Spevb.Viaje.bloqueado()') and p.evaluate('window.__geo.escuchas') == 0, 'pendiente: bloqueado y sin GPS todavía'
    # intentar empezar otro con un viaje guardado esperando
    V.planear(p); V.destino_lejos(p)
    p.evaluate("document.getElementById('startTrip').click()"); p.wait_for_timeout(450)
    d = dialogo(p)
    assert d and d['titulo'] == 'Ya tienes un viaje en curso' and d['volver']['texto'] == 'Reanudar viaje', d
    assert p.evaluate('window.__geo.escuchas') == 0 and p.evaluate('Spevb.Viaje.activo()') is False, 'el intento no empezó nada'
    p.click('#conflVolver'); p.wait_for_timeout(900)
    assert p.evaluate('Spevb.Viaje.activo()') and p.evaluate('window.__geo.escuchas') == 1, 'se reanudó'
    d2 = diag(p)
    assert d2['id'] == id0 and d2['ciclo'] == 'activo' and rutas_vivas(p) == 1, f'es el MISMO viaje: {d2}'
    s.limpio('recargar'); s.cerrar()


@prueba
def un_estado_guardado_corrupto_incompleto_o_vencido_se_limpia_y_deja_empezar_otro(nav):
    s, p, ls = preparar(nav)
    plan = p.evaluate('Spevb.Viaje.plan && Spevb.Planner.seleccion.viaje')
    ahora = p.evaluate('Date.now()')
    casos = {
        'json roto': '{esto no es json',
        'vacío': '{}',
        'sin plan': json.dumps({'v': 2, 'estado': {'fase': 'caminar'}, 't': ahora}),
        'plan sin buses': json.dumps({'v': 2, 'plan': {'buses': [], 'destino': {'lat': 4.1, 'lng': -73.6}}, 'estado': {'fase': 'caminar'}, 't': ahora}),
        'vencido': json.dumps({'v': 2, 'plan': plan, 'estado': {'fase': 'caminar', 'leg': 0}, 't': ahora - 4 * 3600 * 1000}),
        'del futuro': json.dumps({'v': 2, 'plan': plan, 'estado': {'fase': 'caminar', 'leg': 0}, 't': ahora + 10 * 3600 * 1000}),
        'ya terminado': json.dumps({'v': 2, 'plan': plan, 'estado': {'fase': 'llegaste'}, 't': ahora}),
        'tramo corrupto': json.dumps({'v': 2, 'plan': {**plan, 'buses': [{**plan['buses'][0], 'tramo': 'xx'}]}, 'estado': {'fase': 'caminar', 'leg': 0}, 't': ahora}),
    }
    for nombre, valor in casos.items():
        p.evaluate("(v) => { localStorage.setItem('spevb-viaje-curso', v); localStorage.removeItem('spevb-viaje-bloqueo'); }", valor)
        p.reload(wait_until='domcontentloaded')
        B.esperar(p, "!!(window.Spevb && Spevb.Viaje && Spevb.maps && Spevb.maps.map)", 20000)
        p.wait_for_timeout(700)
        assert p.evaluate("localStorage.getItem('spevb-viaje-curso')") is None, f'{nombre}: se limpió el estado guardado'
        assert p.evaluate('Spevb.Viaje.estadoCiclo()') == 'libre' and not p.evaluate('Spevb.Viaje.bloqueado()') and p.evaluate("document.getElementById('viajeCard').hidden"), f'{nombre}: queda libre y sin tarjeta'
        assert p.get_attribute('#startTrip', 'aria-disabled') == 'false', nombre
    V.planear(p); V.destino_lejos(p)
    V.iniciar(p)
    viaje_unico(p)
    s.limpio('estado invalido'); s.cerrar()


# ================================================================================================================== 7 · dos pestañas
def segunda_pestana(s):
    p2 = s.ctx.new_page()
    p2.on('pageerror', lambda e: s.errores.append('pageerror(2): ' + str(e)))
    p2.goto(B.URL, wait_until='domcontentloaded')
    B.esperar(p2, "!!(window.Spevb && Spevb.Viaje && Spevb.maps && Spevb.maps.map)", 20000)
    p2.wait_for_timeout(1000)
    return p2


@prueba
def dos_pestanas_no_pueden_iniciar_dos_viajes_y_la_segunda_puede_pedir_terminar_el_primero(nav):
    s, p, ls = empezar(nav)
    V.alimentar(p, ls, 0, 'fase:esperando')
    id0 = diag(p)['id']
    p2 = segunda_pestana(s)
    assert p2.evaluate('Spevb.Viaje.bloqueado()') and p2.evaluate('window.__geo.escuchas') == 0
    assert p2.evaluate("document.getElementById('viajeCard').hidden") and p2.evaluate('Spevb.Viaje.pendiente()') is False, 'la otra pestaña NO ofrece reanudar el viaje que ya está abierto'
    assert (p2.text_content('#startTrip') or '').strip() == 'Viaje abierto en otra pestaña' and p2.get_attribute('#startTrip', 'aria-disabled') == 'true'
    V.planear(p2); V.destino_lejos(p2)
    p2.evaluate("document.getElementById('startTrip').click()"); p2.wait_for_timeout(500)
    d = dialogo(p2)
    assert d and d['titulo'] == 'Ya tienes un viaje en curso' and 'otra pestaña' in d['texto'] and d['volver']['texto'] == 'Volver a mi viaje', d
    assert p2.evaluate('Spevb.Viaje.activo()') is False and p2.evaluate('window.__geo.escuchas') == 0 and p2.evaluate('window.__watches || 0') == 0, 'la segunda pestaña no creó nada'
    assert p.evaluate('window.__geo.escuchas') == 1 and diag(p)['id'] == id0, 'el viaje de la primera sigue intacto'
    p2.click('#conflVolver'); p2.wait_for_timeout(400)
    # terminar el viaje de la otra pestaña, con confirmación
    p2.evaluate("document.getElementById('startTrip').click()"); p2.wait_for_timeout(400)
    p2.click('#conflTerminar'); p2.wait_for_timeout(250)
    assert 'No se puede deshacer' in dialogo(p2)['texto'] and p.evaluate('Spevb.Viaje.activo()'), 'sin confirmar no se termina nada'
    p2.click('#conflTerminar'); p2.wait_for_timeout(1500)
    assert p.evaluate('Spevb.Viaje.activo()') is False and p.evaluate('window.__geo.escuchas') == 0, 'la primera pestaña terminó y liberó todo'
    assert p2.evaluate('Spevb.Viaje.bloqueado()') is False
    p2.evaluate("document.getElementById('startTrip').click()")
    B.esperar(p2, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 6000)
    assert p2.evaluate('Spevb.Viaje.diagnostico().creadas') == 1 and p.evaluate('Spevb.Viaje.activo()') is False, 'ahora el viaje vive solo en la segunda pestaña'
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio('dos pestañas'); s.cerrar()


@prueba
def el_bloqueo_de_una_pestana_muerta_vence_y_el_viaje_guardado_se_puede_reanudar(nav):
    s, p, ls = empezar(nav)
    V.alimentar(p, ls, 0, 'fase:esperando')
    id0 = diag(p)['id']
    p.evaluate("window.dispatchEvent(new Event('pagehide'))")       # guarda el avance
    p.evaluate("Spevb.Viaje.diagnostico()")
    guardado = p.evaluate("localStorage.getItem('spevb-viaje-curso')")
    assert guardado
    p2 = segunda_pestana(s)
    assert p2.evaluate('Spevb.Viaje.bloqueado()') is True
    p.evaluate("Storage.prototype.removeItem = function () {}")      # cierre abrupto: no alcanza a soltar la concesión (un cierre normal sí la suelta)
    p.close()                                                       # esa pestaña «muere» sin soltar nada
    p2.evaluate("(() => { const b = JSON.parse(localStorage.getItem('spevb-viaje-bloqueo')); b.t = Date.now() - 60000; localStorage.setItem('spevb-viaje-bloqueo', JSON.stringify(b)); })()")
    p2.reload(wait_until='domcontentloaded')
    B.esperar(p2, "!!(window.Spevb && Spevb.Viaje && Spevb.maps && Spevb.maps.map)", 20000)
    p2.wait_for_timeout(1000)
    assert p2.evaluate('Spevb.Viaje.estadoCiclo()') == 'pendiente' and p2.inner_text('#viajeSi') == 'Reanudar viaje', 'con el bloqueo vencido se ofrece reanudar'
    p2.click('#viajeSi'); p2.wait_for_timeout(900)
    assert p2.evaluate('Spevb.Viaje.activo()') and p2.evaluate('Spevb.Viaje.diagnostico().id') == id0
    s.page = p2
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio('bloqueo vencido'); s.cerrar()


# ================================================================================================================== 8-9 · llegada
@prueba
def la_llegada_sigue_bloqueando_hasta_cerrar_y_cerrar_permite_un_viaje_nuevo(nav):
    s, p, ls = empezar(nav)
    V.viaje_completo(p, ls)
    B.esperar(p, "Spevb.Viaje.llego()", 8000)
    id0 = diag(p)['id']
    assert p.evaluate('Spevb.Viaje.estadoCiclo()') == 'llegada' and p.text_content('#viajeTerminar').strip() == 'Cerrar', 'llegó pero la pantalla de llegada sigue activa'
    intentar_otro(p)
    d = dialogo(p)
    assert d and d['titulo'] == 'Ya tienes un viaje en curso' and 'llegada' in d['texto'].lower() and d['terminar']['texto'] == 'Cerrar llegada', d
    assert p.evaluate('Spevb.Viaje.activo()') and diag(p)['id'] == id0 and p.evaluate('Spevb.Viaje.estadoCiclo()') == 'llegada', 'la llegada sigue siendo el mismo viaje'
    p.click('#conflCancelar'); p.wait_for_timeout(300)
    assert p.evaluate('Spevb.Viaje.llego()'), 'cancelar no cierra la llegada'
    # «Cerrar» (el botón de la tarjeta) libera todo
    p.evaluate('Spevb.Viaje.volverAMiViaje()'); p.wait_for_timeout(400)      # el planificador cede y la tarjeta de llegada se ve completa
    p.click('#viajeTerminar'); p.wait_for_timeout(700)
    sin_nada_vivo(p)
    p.evaluate("Spevb.Panel.mostrar('usuario')")
    p.evaluate("document.getElementById('startTrip').click()")
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 6000)
    d2 = viaje_unico(p, creadas=2)
    assert d2['id'] != id0
    s.limpio('llegada'); s.cerrar()


@prueba
def desde_el_dialogo_cerrar_llegada_libera_y_permite_empezar(nav):
    s, p, ls = empezar(nav)
    V.viaje_completo(p, ls)
    B.esperar(p, "Spevb.Viaje.llego()", 8000)
    intentar_otro(p)
    p.click('#conflTerminar'); p.wait_for_timeout(700)
    assert dialogo(p) is None
    sin_nada_vivo(p)
    s.limpio('cerrar llegada desde el dialogo'); s.cerrar()


# ================================================================================================================== 10 · recursos
@prueba
def tras_varios_ciclos_nunca_hay_dos_gps_dos_capas_dos_rutas_ni_dos_enlaces(nav):
    s, p, ls = preparar(nav)
    base = None
    for vuelta in range(1, 4):
        V.iniciar(p)
        V.alimentar(p, ls, 0, 'fase:caminar')
        viaje_unico(p, creadas=vuelta)
        if base is None:
            base = lineas_viaje(p)
            assert base > 0
        assert lineas_viaje(p) == base, f'vuelta {vuelta}: las capas no se duplican ({lineas_viaje(p)} ≠ {base})'
        assert p.evaluate("document.querySelectorAll('.viaje-yo').length") <= 1, 'un solo marcador de la persona'
        if vuelta == 2:
            C.crear_enlace(p)
        assert p.evaluate('window.__geo.escuchas') == 1
        p.evaluate("Spevb.Viaje.detener()"); p.wait_for_timeout(500)
        sin_nada_vivo(p)
        assert p.evaluate('Spevb.Compartir.activo()') is False and C.tokens(p) is None
    log = [x['metodo'] for x in C.log_compartir(p)]
    assert log.count('POST') == 1 and log.count('DELETE') == 1, f'una sola sesión compartida, creada y revocada: {log}'
    assert p.evaluate('window.__watches') == 3, 'tres viajes, tres observadores GPS (cada uno liberado)'
    C.limpio_salvo_4xx(s, 'ciclos'); s.cerrar()


@prueba
def en_el_flujo_guiado_el_doble_toque_en_empezar_crea_una_sola_sesion_y_planear_otro_exige_cerrar_la_llegada(nav):
    s = V.sesion(nav, guiado=True, **MOVIL)
    s.ctx.add_init_script(CONTAR_WATCH)
    p = s.abrir()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    G.hasta_recomendacion(p)
    V.destino_lejos(p)
    ls = V.lecturas(p)
    p.evaluate("(() => { const b = document.getElementById('gEmpezar'); b.click(); b.click(); })()")
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas >= 1", 8000)
    p.wait_for_timeout(500)
    viaje_unico(p)
    assert p.evaluate('window.__watches') == 1
    V.viaje_completo(p, ls)
    B.esperar(p, "!!document.getElementById('viajeOtro')", 8000)
    p.evaluate("document.getElementById('viajeOtro').click()"); p.wait_for_timeout(700)
    sin_nada_vivo(p)
    assert G.paso(p) == 'destino', 'tras cerrar la llegada el flujo guiado vuelve a empezar'
    s.limpio('guiado'); s.cerrar()


# ================================================================================================================== 11 · concesión (lease) entre pestañas · 4.15.1+
# Duraciones cortas SOLO para estas pruebas (window.__spevbPruebas): la suite no espera 20 s reales por caso. Una pestaña «congelada» se simula con el ciclo de vida REAL del navegador
# (CDP Page.setWebLifecycleState = frozen): sus temporizadores y mensajes se detienen igual que en una pestaña suspendida por el sistema.
def preparar_lease(nav, vida=8000, latido=500, espera=1200, sin_canal=False, sin_locks=False, **opts):
    s = V.sesion(nav, **{**MOVIL, **opts})
    ini = f"window.__spevbPruebas = {{ vidaBloqueoMs: {vida}, latidoMs: {latido}, esperaTerminarMs: {espera}, verificacionMs: 60 }};"
    if sin_canal:
        ini += " try { delete window.BroadcastChannel; } catch (e) {}"
    if sin_locks:
        ini += " try { Object.defineProperty(navigator, 'locks', { value: undefined, configurable: true }); } catch (e) {}"
    s.ctx.add_init_script(ini)
    s.ctx.add_init_script(CONTAR_WATCH)
    p = s.ctx.pages[0]
    p.goto(B.URL, wait_until='domcontentloaded')
    B.esperar(p, "!!(window.Spevb && Spevb.maps && Spevb.maps.map)", 20000)
    p.wait_for_timeout(1500)
    p.evaluate("fetch('/__log/limpiar')")
    V.planear(p)
    V.destino_lejos(p)
    return s, p, V.lecturas(p)


def empezar_lease(nav, **cfg):
    s, p, ls = preparar_lease(nav, **cfg)
    V.iniciar(p)
    V.alimentar(p, ls, 0, 'fase:esperando')
    return s, p, ls


def segunda_con_plan(s):
    p2 = segunda_pestana(s)
    V.planear(p2); V.destino_lejos(p2)
    return p2


def congelar(s, p):
    """Detiene TODO el JavaScript de la pestaña (depurador pausado): no corren sus temporizadores ni atiende mensajes ni eventos, como una pestaña suspendida por el sistema.
    El reloj sigue avanzando, así que su concesión vence de verdad. (CDP Page.setWebLifecycleState no congela una página visible, por eso se usa la pausa.)"""
    cdp = s.ctx.new_cdp_session(p)
    cdp.send('Debugger.enable')
    cdp.send('Debugger.pause')
    time.sleep(1.2)      # el siguiente tic de su latido dispara la pausa
    return cdp


def reanudar(cdp):
    cdp.send('Debugger.resume')
    cdp.send('Debugger.disable')


def bloqueo_crudo(p):
    return p.evaluate("localStorage.getItem('spevb-viaje-bloqueo')")


def guardado_crudo(p):
    return p.evaluate("localStorage.getItem('spevb-viaje-curso')")


def coherente(p):
    """Ninguna pestaña muestra un viaje activo sin ser la propietaria de la concesión vigente."""
    d = diag(p)
    visible = p.evaluate("!document.getElementById('viajeCard').hidden && document.body.classList.contains('viaje-activo')")
    if d['ciclo'] == 'activo' or visible:
        assert d['poseo'] and d['latido'], f'UI de viaje activo sin ser propietaria: {d}'
    return d


def intentar_empezar(p2):
    p2.evaluate("document.getElementById('startTrip').click()")
    p2.wait_for_timeout(500)


def toque_desfasado(p, p2, en_ms=700):
    """Dispara «Iniciar viaje» en las dos pestañas al MISMO instante (hora absoluta compartida)."""
    t = p.evaluate('Date.now()') + en_ms
    for pg in (p, p2):
        pg.evaluate("(t) => { setTimeout(() => document.getElementById('startTrip').click(), Math.max(0, t - Date.now())); }", t)
    p.wait_for_timeout(en_ms + 1800)


@prueba
def inicio_simultaneo_en_dos_pestanas_crea_un_solo_viaje_con_y_sin_web_locks(nav):
    for sin_locks in (False, True):
        s, p, ls = preparar_lease(nav, sin_locks=sin_locks)
        p2 = segunda_con_plan(s)
        toque_desfasado(p, p2)
        a1, a2 = p.evaluate('Spevb.Viaje.activo()'), p2.evaluate('Spevb.Viaje.activo()')
        assert a1 != a2, f'exactamente UNA pestaña inicia el viaje (sin_locks={sin_locks}): {a1} {a2}'
        ganadora, perdedora = (p, p2) if a1 else (p2, p)
        d = coherente(ganadora); dp = coherente(perdedora)
        assert d['creadas'] == 1 and d['creadas'] - d['liberadas'] == 1 and d['poseo'], d
        assert dp['creadas'] == 0 and not dp['poseo'] and not dp['gps'] and dp['timers'] == 0 and not dp['capa'] and not dp['ruta'], f'la perdedora no deja capas, timers ni estado parcial: {dp}'
        assert perdedora.evaluate('window.__geo.escuchas') == 0 and ganadora.evaluate('window.__geo.escuchas') == 1
        assert json.loads(bloqueo_crudo(ganadora))['nonce'] and json.loads(bloqueo_crudo(ganadora))['instancia'] == d['instancia'], 'la concesión es de la ganadora'
        s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
        s.limpio(f'simultaneo sin_locks={sin_locks}'); s.cerrar()


@prueba
def la_propietaria_que_responde_termina_y_la_segunda_empieza_con_y_sin_broadcastchannel(nav):
    for sin_canal in (False, True):
        s, p, ls = empezar_lease(nav, sin_canal=sin_canal)
        assert diag(p)['canal'] is (not sin_canal), diag(p)
        id0 = diag(p)['id']
        p2 = segunda_con_plan(s)
        assert diag(p2)['canal'] is (not sin_canal)
        intentar_empezar(p2)
        assert dialogo(p2) and 'otra pestaña' in dialogo(p2)['texto'] and not p2.evaluate('Spevb.Viaje.activo()')
        p2.click('#conflTerminar'); p2.wait_for_timeout(200)
        p2.click('#conflTerminar'); p2.wait_for_timeout(1800)      # confirmación explícita; la propietaria responde y suelta la concesión
        assert p.evaluate('Spevb.Viaje.activo()') is False and p.evaluate('window.__geo.escuchas') == 0, f'la propietaria terminó y liberó todo (sin_canal={sin_canal})'
        assert bloqueo_crudo(p2) is None and guardado_crudo(p2) is None, 'nadie conserva concesión ni estado'
        intentar_empezar(p2)
        B.esperar(p2, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 6000)
        d2 = coherente(p2)
        assert d2['id'] != id0 and d2['poseo'], d2
        s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
        s.limpio(f'propietaria responde sin_canal={sin_canal}'); s.cerrar()


@prueba
def una_propietaria_congelada_conserva_su_concesion_vigente_y_la_segunda_no_borra_ni_inicia_nada(nav):
    for sin_canal in (False, True):
        s, p, ls = empezar_lease(nav, vida=9000, latido=500, espera=1200, sin_canal=sin_canal)
        id0 = diag(p)['id']
        p.evaluate("window.dispatchEvent(new Event('pagehide'))")      # deja guardado el avance (sin soltar la concesión: el evento no es real)
        p2 = segunda_con_plan(s)
        cdp = congelar(s, p)      # la pestaña propietaria deja de responder (sin cerrar nada)
        antes_b, antes_g = bloqueo_crudo(p2), guardado_crudo(p2)
        assert antes_b and antes_g
        intentar_empezar(p2)
        assert dialogo(p2) and 'otra pestaña' in dialogo(p2)['texto']
        p2.click('#conflTerminar'); p2.wait_for_timeout(200)
        p2.click('#conflTerminar'); p2.wait_for_timeout(2200)      # no hay confirmación: pasa la espera de 1,2 s y la concesión vigente se respeta
        assert bloqueo_crudo(p2) == antes_b, f'la concesión vigente NO se borra ni se sobrescribe (sin_canal={sin_canal})'
        assert guardado_crudo(p2) == antes_g, 'el estado guardado de la propietaria tampoco se borra'
        d2 = diag(p2)
        assert d2['ciclo'] == 'libre' and d2['creadas'] == 0 and not d2['poseo'] and not d2['gps'] and not d2['capa'], f'la segunda NO inició ningún viaje: {d2}'
        assert p2.evaluate('window.__geo.escuchas') == 0 and p2.evaluate("document.getElementById('viajeCard').hidden")
        assert 'otra pestaña' in (p2.text_content('#startTrip') or ''), 'el botón sigue diciendo que el viaje está abierto en otra pestaña'
        toasts = p2.evaluate("Array.from(document.querySelectorAll('.spevb-toast')).map(t => t.textContent).join(' | ')")
        assert 'otra pestaña' in toasts and 'no respondió' in toasts, f'mensaje claro: {toasts}'
        reanudar(cdp); p.wait_for_timeout(900)      # al despertar sigue siendo la propietaria (su concesión nunca venció)
        dp = coherente(p)
        assert dp['ciclo'] == 'activo' and dp['poseo'] and dp['id'] == id0 and dp['concesionesPerdidas'] == 0, dp
        s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
        s.limpio(f'congelada sin_canal={sin_canal}'); s.cerrar()


def vencer_y_tomar(nav, **cfg):
    """Propietaria congelada + concesión que VENCE de verdad; la segunda pestaña ofrece reanudar y toma el viaje guardado. Devuelve el contexto para seguir comprobando."""
    s, p, ls = empezar_lease(nav, vida=2500, latido=400, espera=800, **cfg)
    id0 = diag(p)['id']
    p.evaluate("window.dispatchEvent(new Event('pagehide'))")
    p2 = segunda_pestana(s)
    assert p2.evaluate('Spevb.Viaje.bloqueado()') is True
    cdp = congelar(s, p)
    b0 = json.loads(bloqueo_crudo(p2))
    B.esperar(p2, "Spevb.Viaje.estadoCiclo() === 'pendiente'", 9000)      # al vencer su concesión, la segunda pestaña lo nota SOLA y ofrece reanudar el viaje guardado
    assert p2.inner_text('#viajeSi') == 'Reanudar viaje'
    b1 = json.loads(bloqueo_crudo(p2))
    assert b1['nonce'] != b0['nonce'] and b1['instancia'] == diag(p2)['instancia'] and b1['estado'] == 'pendiente', (b0, b1)
    p2.click('#viajeSi'); p2.wait_for_timeout(1200)
    d2 = coherente(p2)
    assert d2['ciclo'] == 'activo' and d2['id'] == id0 and d2['poseo'], f'la segunda reutilizó el estado guardado coherente (mismo viaje): {d2}'
    return s, p, p2, cdp, id0


@prueba
def la_concesion_se_toma_solo_despues_de_vencer_de_verdad_y_reutiliza_el_estado_guardado(nav):
    for sin_canal in (False, True):
        s, p, p2, cdp, id0 = vencer_y_tomar(nav, sin_canal=sin_canal)
        assert p2.evaluate('window.__geo.escuchas') == 1 and rutas_vivas(p2) == 1, 'un único viaje vivo, en la segunda pestaña'
        reanudar(cdp); p.wait_for_timeout(300)
        s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
        s.limpio(f'vencida sin_canal={sin_canal}'); s.cerrar()


@prueba
def una_pestana_vieja_que_se_reanuda_sin_concesion_detiene_sus_efectos_y_no_recupera_el_control(nav):
    s, p, p2, cdp, id0 = vencer_y_tomar(nav)
    g_nuevo, b_nuevo = guardado_crudo(p2), json.loads(bloqueo_crudo(p2))
    reanudar(cdp)      # la pestaña vieja despierta: debe descubrir que ya no es propietaria
    B.esperar(p, "Spevb.Viaje.diagnostico().concesionesPerdidas >= 1", 6000)
    p.wait_for_timeout(900)
    dp = diag(p)
    assert dp['ciclo'] == 'libre' and dp['id'] is None and not dp['poseo'] and not dp['gps'] and dp['timers'] == 0 and not dp['capa'] and not dp['ruta'] and not dp['wake'] and not dp['latido'], f'la vieja detuvo todos sus efectos: {dp}'
    assert p.evaluate('window.__geo.escuchas') == 0 and rutas_vivas(p) == 0 and lineas_viaje(p) == 0
    assert p.evaluate("document.getElementById('viajeCard').hidden") and p.evaluate("!document.body.classList.contains('viaje-activo')"), 'su pantalla ya no muestra un viaje activo'
    nuevo = json.loads(bloqueo_crudo(p))
    assert nuevo['nonce'] == b_nuevo['nonce'] and nuevo['instancia'] == diag(p2)['instancia'], 'la concesión sigue siendo de la segunda pestaña: la vieja no la recuperó ni la borró'
    assert json.loads(guardado_crudo(p))['id'] == id0 and p2.evaluate('Spevb.Viaje.activo()'), 'el estado guardado y el viaje vivo son los de la nueva propietaria'
    p.wait_for_timeout(1200)      # y pasado un rato tampoco lo recupera (sin latido propio)
    assert bloqueo_crudo(p) == bloqueo_crudo(p2) and not diag(p)['poseo'] and not diag(p)['latido']
    coherente(p); dp2 = coherente(p2)
    assert dp2['creadas'] == 1 and dp2['creadas'] - dp2['liberadas'] == 1 and p2.evaluate('window.__geo.escuchas') == 1
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio('vieja reanuda'); s.cerrar()


@prueba
def recargar_la_pestana_propietaria_suelta_la_concesion_y_reanuda_el_mismo_viaje(nav):
    s, p, ls = empezar_lease(nav)
    id0 = diag(p)['id']
    p.reload(wait_until='domcontentloaded')      # recarga real: el evento pagehide real suelta la concesión (el avance ya quedó guardado)
    B.esperar(p, "!!(window.Spevb && Spevb.Viaje && Spevb.maps && Spevb.maps.map)", 20000)
    B.esperar(p, "Spevb.Viaje.estadoCiclo() === 'pendiente'", 8000)
    assert p.inner_text('#viajeSi') == 'Reanudar viaje' and diag(p)['poseo'], 'tras recargar se ofrece reanudar y la concesión es de la nueva carga'
    p.click('#viajeSi'); p.wait_for_timeout(1000)
    d = coherente(p)
    assert d['ciclo'] == 'activo' and d['id'] == id0 and d['creadas'] == 1, d
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio('recarga propietaria'); s.cerrar()


@prueba
def terminar_en_una_pestana_y_empezar_en_la_otra_varias_veces_no_deja_fugas(nav):
    s, p, ls = empezar_lease(nav, vida=8000, latido=500)
    p2 = segunda_con_plan(s)
    activa, otra = p, p2
    for ronda in range(3):
        d = coherente(activa)
        assert d['ciclo'] == 'activo' and d['creadas'] - d['liberadas'] == 1 and activa.evaluate('window.__geo.escuchas') == 1 and rutas_vivas(activa) == 1, (ronda, d)
        assert diag(otra)['ciclo'] == 'libre' and otra.evaluate('window.__geo.escuchas') == 0 and rutas_vivas(otra) == 0
        activa.evaluate("Spevb.Viaje.detener()")
        B.esperar(otra, "!Spevb.Viaje.bloqueado()", 5000)
        assert bloqueo_crudo(activa) is None and guardado_crudo(activa) is None, f'ronda {ronda}: nada queda guardado'
        sin_nada_vivo(activa)
        activa, otra = otra, activa
        intentar_empezar(activa)
        B.esperar(activa, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 6000)
    activa.evaluate("Spevb.Viaje.detener()"); activa.wait_for_timeout(300)
    sin_nada_vivo(activa); sin_nada_vivo(otra)
    assert diag(p)['creadas'] + diag(p2)['creadas'] == 4 and diag(p)['liberadas'] + diag(p2)['liberadas'] == 4, 'cuatro viajes creados, cuatro liberados'
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]
    s.limpio('rondas entre pestañas'); s.cerrar()


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
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas del ciclo de vida del viaje; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
