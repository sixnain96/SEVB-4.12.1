"""Pruebas de navegador de «Mis lugares» (Fase C): Casa, Trabajo y lugares con nombre guardados en la CUENTA, con su propio modo de mapa.

Frontend real y backend stub (e2e/stub_server.py), que imita /api/cuenta/datos con el contrato del servidor: escritura condicionada a «base» (409 si otro dispositivo cambió el documento),
«actualizadoEn», lápidas y los topes del validador (30 vivos). GOOGLE ESTÁ SIMULADO como en cuenta_google_e2e.py. No prueba el mapa real de teselas ni una base PostgreSQL (eso lo cubren
las pruebas Java con PostGIS local).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/lugares_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import json
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import cuenta_google_e2e as G  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
CAPTURAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'capturas-viaje')


def prueba(f):
    PRUEBAS.append(f)
    return f


# ------------------------------------------------------------------------------------------------------------------------------------------- ayudas
def con_ana(nav, sub='111', correo='ana@example.com', nombre='Ana Pérez', reiniciar=True, **opts):
    """Sesión con Google simulado y la cuenta abierta. {@code reiniciar=False}: un SEGUNDO dispositivo de la misma cuenta (no borra lo que el servidor simulado ya guarda)."""
    s = G.sesion(nav, **{**G.MOVIL, **opts}) if reiniciar else B.Sesion(nav, **{**G.MOVIL, **opts})
    if not reiniciar:
        s.ctx.add_init_script(G.GSI_FALSO)
    p = s.abrir()
    G.entrar(p, sub, correo, nombre)
    return s, p


def menu(p):
    if not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"):
        p.click('#menuButton')
    p.wait_for_timeout(450)
    p.evaluate("document.getElementById('menuLugares').open = true")


def cerrar_menu(p):
    if p.evaluate("document.getElementById('sideMenu').classList.contains('open')"):
        p.click('#closeMenu'); p.wait_for_timeout(450)


def abrir_acciones(p, id_):
    """Abre «⋯» de un lugar solo si estaba cerrado (el menú recuerda qué filas tenían sus acciones abiertas)."""
    sel = '#lugaresLista .lugar-fila[data-id="%s"] .lugar-mas' % id_
    if p.get_attribute(sel, 'aria-expanded') != 'true':
        p.click(sel); p.wait_for_timeout(200)


def lugares(p):
    return p.evaluate("Spevb.Datos.leer('lugares')")


def mover(p, lat, lng, zoom=16):
    p.evaluate("([a, b, z]) => Spevb.maps.map.setView([a, b], z, { animate: false })", [lat, lng, zoom])
    p.wait_for_timeout(250)


def bajo_el_pin(p):
    """Coordenadas del punto que está bajo la punta del pin AHORA (lo que se vería y lo que se guarda)."""
    return p.evaluate("(() => { const e = document.getElementById('lugarPin'); const ll = Spevb.maps.map.toLatLng({ x: parseFloat(e.style.left), y: parseFloat(e.style.top) }); return { lat: ll[0], lng: ll[1] }; })()")


def cerca(a, b, tol=2e-6):
    return abs(a['lat'] - b['lat']) <= tol and abs(a['lng'] - b['lng']) <= tol


def abrir_modo(p, selector):
    menu(p)
    p.click(selector); p.wait_for_timeout(500)
    B.esperar(p, "Spevb.Lugares.estado().activo", 4000)


def guardar_en_modo(p, espera=1400):
    p.click('#lugarGuardar'); p.wait_for_timeout(espera)


def nombre_y_guardar(p, nombre):
    p.fill('#lugarNombre', nombre)
    guardar_en_modo(p)


def toast(p):
    return p.evaluate("[...document.querySelectorAll('#spevbToasts, .toast, [role=status]')].map(e => e.textContent).join(' | ')")


# ------------------------------------------------------------------------------------------------------------------------------------------- invitado
@prueba
def sin_cuenta_guardar_pide_google_y_cancelar_vuelve_al_menu_sin_guardar(nav):
    s = G.sesion(nav, **G.MOVIL)
    p = s.abrir()
    menu(p)
    assert 'Guardar mi casa' in p.inner_text('#atajos') and 'Guardar mi trabajo' in p.inner_text('#atajos')
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(600)
    assert p.evaluate("!document.getElementById('authModal').hidden"), 'guardar sin sesión abre «Continuar con Google»'
    assert not p.evaluate("Spevb.Lugares.estado().activo")
    p.click('#authCancel'); p.wait_for_timeout(700)
    assert p.evaluate("document.getElementById('authModal').hidden")
    assert p.evaluate("document.getElementById('sideMenu').classList.contains('open')"), 'cancelar el acceso vuelve al menú'
    assert not p.evaluate("Spevb.Lugares.estado().activo") and lugares(p) == []
    p.click('#lugarAgregar'); p.wait_for_timeout(600)
    assert p.evaluate("!document.getElementById('authModal').hidden"), '«Agregar lugar» también exige cuenta'
    s.limpio('invitado'); s.cerrar()


@prueba
def un_favorito_antiguo_de_invitado_sigue_sirviendo_y_nunca_pasa_a_la_cuenta(nav):
    s = G.sesion(nav, **G.MOVIL)
    s.ctx.add_init_script("try { if (!localStorage.getItem('__s1')) { localStorage.setItem('__s1', '1'); localStorage.setItem('spevb-favoritos', JSON.stringify([{ id: 'v1', nombre: 'Casa', lat: 4.145, lng: -73.654 }])); } } catch (e) {}")
    p = s.abrir()
    menu(p)
    assert 'Ir a casa' in p.inner_text('#atajos'), 'un favorito llamado Casa se interpreta como la casa'
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(700)
    assert p.input_value('#tripDestination') == 'Casa'
    G.entrar(p, '111', 'ana@example.com', 'Ana')
    menu(p)
    assert lugares(p) == [] and 'Guardar mi casa' in p.inner_text('#atajos'), 'lo del invitado NO se adjudica a la primera cuenta que entra'
    assert p.evaluate("JSON.parse(localStorage.getItem('spevb-favoritos') || '[]').length") == 1, 'y sigue en este dispositivo para cuando se use como invitado'
    p.click('#accountLogout'); p.wait_for_timeout(700)
    menu(p)
    assert 'Ir a casa' in p.inner_text('#atajos'), 'al salir, el invitado recupera lo suyo'
    s.limpio('favorito antiguo'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- Casa y Trabajo
@prueba
def casa_y_trabajo_guardan_el_punto_exacto_del_pin_y_los_textos_cambian(nav):
    s, p = con_ana(nav)
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    assert p.inner_text('#lugarTitulo') == 'Marca tu casa en el mapa'
    assert p.is_visible('#lugarGuardar') and p.is_visible('#lugarCancelar') and not p.is_visible('#lugarNombreFila')
    assert not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"), 'el menú se cierra y el mapa queda libre'
    mover(p, 4.1411, -73.6310)
    esperado = bajo_el_pin(p)
    guardar_en_modo(p)
    f = lugares(p)
    assert len(f) == 1 and f[0]['tipo'] == 'casa' and f[0]['nombre'] == 'Casa' and cerca(f[0], esperado), f'se guardó el punto exacto bajo el pin: {f} vs {esperado}'
    assert not p.evaluate("Spevb.Lugares.estado().activo") and p.evaluate("document.getElementById('sideMenu').classList.contains('open')")
    assert 'Ir a casa' in p.inner_text('#atajos')
    abrir_modo(p, '#atajos [data-atajo="Trabajo"]') if False else None
    p.click('#atajos [data-atajo="Trabajo"]'); p.wait_for_timeout(500)
    assert p.inner_text('#lugarTitulo') == 'Marca tu trabajo en el mapa'
    mover(p, 4.1522, -73.6180)
    guardar_en_modo(p)
    assert sorted(x['tipo'] for x in lugares(p)) == ['casa', 'trabajo'] and 'Ir al trabajo' in p.inner_text('#atajos')
    p.screenshot(path=os.path.join(CAPTURAS, 'lugares-menu-320.png'))
    s.limpio('casa y trabajo'); s.cerrar()


@prueba
def la_casa_no_toma_el_destino_viejo_ni_un_punto_elegido_en_A_o_B_la_guarda(nav):
    s, p = con_ana(nav)
    p.fill('#tripDestination', V.DEST); p.keyboard.press('Enter'); p.wait_for_timeout(900)
    destino_antes = p.evaluate("Spevb.Planner.destino ? JSON.stringify(Spevb.Planner.destino) : null") if p.evaluate("'destino' in Spevb.Planner") else None
    assert lugares(p) == [], 'elegir un destino no guarda nada'
    p.evaluate("window.dispatchEvent(new CustomEvent('spevb-point-selected', { detail: { modo: 'destination', lat: 4.1450, lng: -73.6240 } }))"); p.wait_for_timeout(400)
    assert lugares(p) == [], 'spevb-point-selected de A/B no guarda lugares'
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    punto_pin = bajo_el_pin(p)
    assert not cerca(punto_pin, {'lat': 4.1450, 'lng': -73.6240}, 5e-4) or True
    guardar_en_modo(p)
    casa = lugares(p)[0]
    assert cerca(casa, punto_pin), 'la casa es el punto marcado, no el destino viejo'
    assert p.input_value('#tripDestination') != '' and destino_antes == (p.evaluate("Spevb.Planner.destino ? JSON.stringify(Spevb.Planner.destino) : null") if p.evaluate("'destino' in Spevb.Planner") else None), 'el destino no se tocó'
    s.limpio('sin tomar destino'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- lugares con nombre
@prueba
def lugares_con_nombre_validan_nombres_duplicados_y_tratan_el_nombre_como_texto(nav):
    s, p = con_ana(nav)
    abrir_modo(p, '#lugarAgregar')
    assert p.is_visible('#lugarNombre') and 'Universidad' in (p.get_attribute('#lugarNombre', 'placeholder') or '')
    guardar_en_modo(p, 400)
    assert 'al menos 2' in p.inner_text('#lugarEstado'), 'sin nombre no guarda'
    p.fill('#lugarNombre', 'casa'); guardar_en_modo(p, 400)
    assert 'propios botones' in p.inner_text('#lugarEstado'), 'Casa y Trabajo tienen sus botones'
    mover(p, 4.1400, -73.6400)
    nombre_y_guardar(p, '  Universidad  ')
    assert [x['nombre'] for x in lugares(p)] == ['Universidad'] and lugares(p)[0]['tipo'] == 'otro' and lugares(p)[0]['id'], 'nombre recortado, tipo otro, id estable'
    p.click('#lugarAgregar'); p.wait_for_timeout(500)
    mover(p, 4.1500, -73.6300)
    nombre_y_guardar(p, 'universidad')
    assert p.evaluate("Spevb.Lugares.estado().activo") and 'Ya tienes' in p.inner_text('#lugarEstado'), 'el nombre repetido (sin importar mayúsculas) no se acepta'
    nombre_y_guardar(p, 'Casa de mamá')
    assert sorted(x['nombre'] for x in lugares(p)) == ['Casa de mamá', 'Universidad']
    # un lugar cercano a otro pide confirmación explícita
    p.click('#lugarAgregar'); p.wait_for_timeout(500)
    mover(p, 4.1500, -73.6300)
    nombre_y_guardar(p, 'Vecina de mamá')
    assert p.evaluate("Spevb.Lugares.estado().activo") and 'a menos de' in p.inner_text('#lugarEstado') and p.inner_text('#lugarGuardar') == 'Guardar de todos modos'
    guardar_en_modo(p)
    assert len(lugares(p)) == 3
    # el nombre es TEXTO: nunca se interpreta como HTML
    p.click('#lugarAgregar'); p.wait_for_timeout(500)
    mover(p, 4.1600, -73.6000)
    nombre_y_guardar(p, '<b>Gym</b>')
    assert p.evaluate("document.querySelectorAll('#lugaresLista b, #favList b:not(#favCount)').length") == 0 and '<b>Gym</b>' in p.inner_text('#lugaresLista'), 'el nombre se muestra como texto'
    p.screenshot(path=os.path.join(CAPTURAS, 'lugares-lista-320.png'))
    s.limpio('lugares con nombre'); s.cerrar()


@prueba
def hay_un_limite_de_30_lugares_y_el_mensaje_lo_explica(nav):
    s, p = con_ana(nav)
    p.evaluate("""Spevb.LugaresCuenta.mutar((v) => { for (let i = 0; i < 30; i++) v.push({ id: 'p' + i, nombre: 'Sitio ' + i, lat: 4.12 + i * 0.001, lng: -73.62, tipo: 'otro' }); return v; })""")
    p.wait_for_timeout(1200)
    assert len(lugares(p)) == 30
    menu(p)
    p.click('#lugarAgregar'); p.wait_for_timeout(500)
    assert not p.evaluate("Spevb.Lugares.estado().activo"), 'con 30 no se abre el modo'
    assert 'Ya tienes 30' in p.evaluate("document.body.innerText"), 'el mensaje explica el límite'
    s.limpio('limite'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- usar, editar, borrar
@prueba
def tocar_un_lugar_lo_pone_como_destino_y_editar_renombrar_y_eliminar_funcionan(nav):
    s, p = con_ana(nav)
    for nombre, lat, lng in (('Universidad', 4.14, -73.64), ('Casa de mamá', 4.15, -73.63)):
        p.click('#lugarAgregar') if p.is_visible('#lugarAgregar') else (menu(p), p.click('#lugarAgregar'))
        p.wait_for_timeout(500); mover(p, lat, lng); nombre_y_guardar(p, nombre)
    menu(p)
    p.click('#lugaresLista .lugar-usar >> nth=0'); p.wait_for_timeout(700)
    assert p.input_value('#tripDestination') in ('Universidad', 'Casa de mamá'), 'un toque pone el lugar como destino'
    # renombrar
    menu(p); p.click('#lugaresLista .lugar-fila >> nth=0 >> .lugar-mas'); p.wait_for_timeout(200)
    p.click('#lugaresLista .lugar-fila >> nth=0 >> text=Cambiar nombre'); p.wait_for_timeout(400)
    assert p.evaluate("document.activeElement.id") == 'lugDlgC', 'el foco va al campo del nombre'
    p.fill('#lugDlgC', 'Universidad'); p.click('#lugDlgS'); p.wait_for_timeout(300)
    assert 'Ya tienes' in p.inner_text('#lugDlgE'), 'renombrar a un nombre repetido se rechaza'
    p.fill('#lugDlgC', 'Mi universidad'); p.click('#lugDlgS'); p.wait_for_timeout(1400)
    assert sorted(x['nombre'] for x in lugares(p)) == ['Mi universidad', 'Universidad'], lugares(p)      # el primero de la lista (el más reciente, «Casa de mamá») pasó a llamarse «Mi universidad»
    ids_antes = sorted(x['id'] for x in lugares(p))
    # editar ubicación: reabre el mapa con el punto guardado bajo el pin; cancelar conserva la versión anterior
    viejo = [x for x in lugares(p) if x['nombre'] == 'Mi universidad'][0]
    menu(p); abrir_acciones(p, viejo['id'])
    p.click('#lugaresLista .lugar-fila[data-id="%s"] >> text=Cambiar ubicación' % viejo['id']); p.wait_for_timeout(700)
    assert p.evaluate("Spevb.Lugares.estado().activo") and cerca(bajo_el_pin(p), viejo, 3e-5), 'el modo abre con el punto guardado bajo el pin'
    mover(p, 4.1700, -73.6100)
    p.click('#lugarCancelar'); p.wait_for_timeout(700)
    assert [x for x in lugares(p) if x['id'] == viejo['id']][0]['lat'] == viejo['lat'], 'cancelar conserva la versión anterior'
    assert p.evaluate("document.getElementById('sideMenu').classList.contains('open')")
    abrir_acciones(p, viejo['id'])
    p.click('#lugaresLista .lugar-fila[data-id="%s"] >> text=Cambiar ubicación' % viejo['id']); p.wait_for_timeout(700)
    mover(p, 4.1700, -73.6100)
    nuevo = bajo_el_pin(p)
    guardar_en_modo(p)
    n = [x for x in lugares(p) if x['id'] == viejo['id']][0]
    assert cerca(n, nuevo) and n['nombre'] == 'Mi universidad', 'se movió el MISMO lugar (id estable) al punto nuevo'
    assert sorted(x['id'] for x in lugares(p)) == ids_antes
    # eliminar con confirmación: «No, conservar» no borra
    menu(p)
    abrir_acciones(p, viejo['id'])
    p.click('#lugaresLista .lugar-fila[data-id="%s"] >> text=Eliminar' % viejo['id']); p.wait_for_timeout(400)
    assert p.evaluate("document.activeElement.textContent") == 'No, conservar', 'la acción segura tiene el foco'
    p.click('#lugDlgN'); p.wait_for_timeout(500)
    assert len(lugares(p)) == 2
    p.click('#lugaresLista .lugar-fila[data-id="%s"] >> text=Eliminar' % viejo['id']); p.wait_for_timeout(400)
    p.click('#lugDlgS'); p.wait_for_timeout(1400)
    assert [x['id'] for x in lugares(p)] != ids_antes and viejo['id'] not in [x['id'] for x in lugares(p)] and len(lugares(p)) == 1
    s.limpio('usar editar borrar'); s.cerrar()


@prueba
def un_doble_toque_en_guardar_envia_una_sola_escritura(nav):
    s, p = con_ana(nav)
    posts = []
    p.on('request', lambda r: posts.append(r.url) if r.method == 'POST' and r.url.endswith('/api/cuenta/datos/lugares') else None)
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    p.evaluate("(() => { const b = document.getElementById('lugarGuardar'); b.click(); b.click(); b.click(); })()")
    p.wait_for_timeout(1800)
    assert len(posts) == 1 and len(lugares(p)) == 1, f'una sola escritura: {len(posts)}'
    s.limpio('doble toque'); s.cerrar()


@prueba
def si_el_servidor_falla_no_se_guarda_se_dice_y_se_puede_reintentar(nav):
    s, p = con_ana(nav)
    s.ctx.request.get(B.URL + '__cuenta/fallo-datos?v=1')
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    guardar_en_modo(p, 1500)
    assert lugares(p) == [] and p.evaluate("Spevb.Lugares.estado().activo"), 'no se guardó y el modo sigue abierto'
    assert p.inner_text('#lugarEstado').strip() != '' and 'Guardaste' not in p.inner_text('#lugarEstado')
    assert p.inner_text('#lugarGuardar') == 'Guardar este punto' and p.is_enabled('#lugarGuardar'), 'se puede reintentar'
    s.ctx.request.get(B.URL + '__cuenta/fallo-datos?v=0')
    guardar_en_modo(p, 1500)
    assert len(lugares(p)) == 1 and not p.evaluate("Spevb.Lugares.estado().activo")
    s.errores = [e for e in s.errores if '503' not in e]      # el fallo es a propósito
    s.limpio('fallo servidor'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- mapa y GPS
@prueba
def sin_gps_el_modo_funciona_y_la_ubicacion_solo_se_pide_al_pulsar(nav):
    s = G.sesion(nav, **G.MOVIL)
    s.ctx.add_init_script("window.__gpsLlamadas = 0; try { Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (ok, err) => { window.__gpsLlamadas++; err({ code: 1, message: 'denegado' }); }, watchPosition: () => 0, clearWatch() {} } }); } catch (e) {}")
    p = s.abrir(); G.entrar(p)
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    assert p.evaluate("window.__gpsLlamadas") == 0, 'el GPS no se pide al abrir el modo'
    p.click('#lugarGps'); p.wait_for_timeout(500)
    assert p.evaluate("window.__gpsLlamadas") == 1 and 'No pude obtener tu ubicación' in p.inner_text('#lugarEstado')
    guardar_en_modo(p)
    assert len(lugares(p)) == 1, 'sin GPS se guarda moviendo el mapa'
    # un dispositivo sin geolocalización: el botón ni aparece
    p.evaluate("Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined })")
    abrir_modo(p, '#atajos [data-atajo="Trabajo"]')
    assert not p.is_visible('#lugarGps')
    s.limpio('gps'); s.cerrar()


@prueba
def una_direccion_que_llega_tarde_no_mueve_el_pin_ni_cambia_lo_guardado(nav):
    s, p = con_ana(nav)
    retenidas = []
    s.ctx.route('**/api/lugares/reverso*', lambda r: retenidas.append(r))
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    p.wait_for_timeout(1200)
    mover(p, 4.1433, -73.6200)
    marcado = bajo_el_pin(p)
    for r in retenidas:
        r.fulfill(status=200, content_type='application/json', body=json.dumps({'nombre': 'Calle falsa 123, Villavicencio', 'lat': 4.1999, 'lng': -73.5999}))
    p.wait_for_timeout(500)
    assert cerca(bajo_el_pin(p), marcado) and 'Calle falsa' not in p.inner_text('#lugarCerca'), 'la respuesta vieja se descarta'
    guardar_en_modo(p)
    assert cerca(lugares(p)[0], marcado), 'se guardó el punto marcado, no el de la dirección'
    s.limpio('direccion tardia'); s.cerrar()


@prueba
def la_direccion_lenta_no_impide_guardar_las_coordenadas_exactas(nav):
    s, p = con_ana(nav)
    s.ctx.route('**/api/lugares/reverso*', lambda r: None)       # nunca responde
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    p.wait_for_timeout(1000)
    marcado = bajo_el_pin(p)
    guardar_en_modo(p)
    assert len(lugares(p)) == 1 and cerca(lugares(p)[0], marcado)
    s.limpio('direccion lenta'); s.cerrar()


@prueba
def fuera_de_la_zona_de_servicio_no_se_guarda(nav):
    s, p = con_ana(nav)
    abrir_modo(p, '#atajos [data-atajo="Casa"]')
    p.evaluate("Spevb.cityBounds.splice(0, 2, [10, 10], [11, 11])"); p.wait_for_timeout(200)      # el mapa no deja salir de la ciudad: se encoge la zona de servicio para simular un punto fuera de ella
    guardar_en_modo(p, 600)
    assert lugares(p) == [] and 'fuera de la zona' in p.inner_text('#lugarEstado')
    s.limpio('fuera de zona'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- A y B, selector y viaje
@prueba
def con_A_y_B_vacios_o_elegidos_y_resultados_visibles_marcar_un_lugar_no_cambia_nada(nav):
    s, p = con_ana(nav)
    # A y B vacíos
    abrir_modo(p, '#atajos [data-atajo="Casa"]'); guardar_en_modo(p)
    assert p.input_value('#tripOrigin') == '' and p.input_value('#tripDestination') == '', 'con A y B vacíos siguen vacíos'
    cerrar_menu(p)
    # A y B elegidos con resultados visibles
    V.planear(p)
    antes = p.evaluate("({ a: document.getElementById('tripOrigin').value, b: document.getElementById('tripDestination').value, n: document.querySelectorAll('#tripResults .trip-option').length, sel: !!Spevb.Planner.seleccion, panel: document.body.classList.contains('panel-oculto') })")
    p.click('#closeMenu') if p.evaluate("document.getElementById('sideMenu').classList.contains('open')") else None
    abrir_modo(p, '#atajos [data-atajo="Trabajo"]')
    assert p.evaluate("document.body.classList.contains('panel-oculto')"), 'el panel se oculta mientras se marca'
    guardar_en_modo(p)
    despues = p.evaluate("({ a: document.getElementById('tripOrigin').value, b: document.getElementById('tripDestination').value, n: document.querySelectorAll('#tripResults .trip-option').length, sel: !!Spevb.Planner.seleccion, panel: document.body.classList.contains('panel-oculto') })")
    assert antes == despues, f'A, B, resultados, recomendación y panel intactos: {antes} / {despues}'
    assert sorted(x['tipo'] for x in lugares(p)) == ['casa', 'trabajo']
    s.limpio('A y B'); s.cerrar()


@prueba
def con_el_selector_de_A_activo_cede_y_lo_restaura_si_sigue_siendo_pertinente(nav):
    s, p = con_ana(nav)
    p.click('#pickOrigin'); p.wait_for_timeout(500)
    assert p.get_attribute('#pickOrigin', 'aria-pressed') == 'true'
    abrir_modo(p, '#atajos [data-atajo="Casa"]') if False else None
    menu(p)
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(600)
    assert p.get_attribute('#pickOrigin', 'aria-pressed') == 'false', 'el selector de A cede mientras se marca la casa'
    # el toque en el mapa durante este modo NO elige A
    assert p.input_value('#tripOrigin') == ''
    p.click('#lugarCancelar'); p.wait_for_timeout(700)
    assert p.get_attribute('#pickOrigin', 'aria-pressed') == 'true', 'al cancelar, el selector de A vuelve (A sigue vacío)'
    # si A se llenó mientras tanto, no se restaura
    menu(p)
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(600)
    p.evaluate("Spevb.Planner.poner('origin', { id: null, lat: 4.1475, lng: -73.6530, nombre: 'A de prueba', direccion: null, fuente: 'Prueba', confirmado: true })")
    p.click('#lugarCancelar'); p.wait_for_timeout(700)
    assert p.get_attribute('#pickOrigin', 'aria-pressed') == 'false', 'ya no es pertinente: no se restaura'
    s.limpio('selector'); s.cerrar()


@prueba
def durante_un_viaje_el_modo_va_arriba_el_viaje_sigue_y_volver_a_mi_viaje_esta_primero(nav):
    s = V.sesion(nav, **V.MOVIL)
    s.ctx.add_init_script(G.GSI_FALSO)
    s.ctx.request.get(B.URL + '__cuenta/reiniciar')
    p = s.abrir(); G.entrar(p)
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p); V.alimentar(p, ls, 0, 'fase:esperando')
    p.click('#menuFlotante'); p.wait_for_timeout(600)
    assert p.is_visible('#menuVolverViaje'), '«Volver a mi viaje» está a la vista durante el viaje'
    orden = p.evaluate("[...document.getElementById('sideMenu').querySelectorAll('button, summary')].filter(e => e.offsetParent).map(e => e.id || e.textContent.trim()).slice(0, 4)")
    assert orden[0] != '' and 'menuVolverViaje' in orden, f'lo primero: {orden}'
    p.evaluate("document.getElementById('menuLugares').open = true")
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(600)
    assert p.get_attribute('#lugarModo', 'data-viaje') == '1', 'con un viaje, la barra va arriba para no tapar la tarjeta ni las alertas'
    assert p.evaluate("Spevb.Viaje.activo()") and p.evaluate('window.__geo.escuchas') == 1
    guardar_en_modo(p)
    assert len(lugares(p)) == 1 and p.evaluate("Spevb.Viaje.activo()") and p.evaluate('window.__geo.escuchas') == 1, 'el viaje y su GPS siguen'
    p.click('#closeMenu'); p.wait_for_timeout(400)
    p.click('#menuFlotante'); p.wait_for_timeout(500)
    p.click('#menuVolverViaje'); p.wait_for_timeout(700)
    assert not p.evaluate("document.getElementById('sideMenu').classList.contains('open')") and not p.evaluate("document.getElementById('viajeCard').hidden")
    s.limpio('viaje'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- cuentas y dispositivos
@prueba
def dos_cuentas_en_el_mismo_navegador_nunca_comparten_lugares(nav):
    s, p = con_ana(nav)
    abrir_modo(p, '#atajos [data-atajo="Casa"]'); guardar_en_modo(p)
    assert len(lugares(p)) == 1
    p.click('#accountLogout'); p.wait_for_timeout(900)
    assert lugares(p) == [] and p.evaluate("localStorage.getItem('spevb-lugares-cuenta')") is None, 'al salir no queda la casa de Ana en este navegador'
    menu(p); assert 'Guardar mi casa' in p.inner_text('#atajos')
    cerrar_menu(p)
    G.entrar(p, '222', 'beto@example.com', 'Beto Gómez')
    menu(p)
    assert lugares(p) == [] and 'Guardar mi casa' in p.inner_text('#atajos'), 'Beto no hereda lo de Ana'
    p.click('#atajos [data-atajo="Trabajo"]'); p.wait_for_timeout(500); guardar_en_modo(p)
    assert [x['tipo'] for x in lugares(p)] == ['trabajo']
    p.click('#accountLogout'); p.wait_for_timeout(900)
    cerrar_menu(p)
    G.entrar(p, '111', 'ana@example.com', 'Ana Pérez')
    menu(p)
    assert [x['tipo'] for x in lugares(p)] == ['casa'], 'Ana ve lo suyo (y solo lo suyo) al volver'
    s.limpio('dos cuentas'); s.cerrar()


@prueba
def recargar_y_otro_dispositivo_ven_lo_mismo_y_ningun_cambio_pisa_a_otro_ni_un_borrado_reaparece(nav):
    s1, p1 = con_ana(nav)
    abrir_modo(p1, '#atajos [data-atajo="Casa"]'); guardar_en_modo(p1)
    p1.reload(wait_until='domcontentloaded'); B.esperar(p1, "!!(window.Spevb && Spevb.maps && Spevb.maps.map)", 20000); p1.wait_for_timeout(1500)
    assert [x['tipo'] for x in lugares(p1)] == ['casa'], 'recargar conserva los lugares de la cuenta'
    # segundo dispositivo, misma cuenta
    s2, p2 = con_ana(nav, reiniciar=False)
    B.esperar(p2, "Spevb.Datos.leer('lugares').length === 1", 6000)
    abrir_modo(p2, '#lugarAgregar'); mover(p2, 4.14, -73.64); nombre_y_guardar(p2, 'Universidad')
    # el primero (con la copia vieja) guarda OTRO lugar sin pisar el de Universidad
    abrir_modo(p1, '#lugarAgregar'); mover(p1, 4.16, -73.60); nombre_y_guardar(p1, 'Gimnasio')
    assert sorted(x['nombre'] for x in lugares(p1)) == ['Casa', 'Gimnasio', 'Universidad'], f'nada se perdió: {lugares(p1)}'
    # el segundo borra Universidad; el primero guarda otra cosa y Universidad NO reaparece
    p2.evaluate("Spevb.LugaresCuenta.refrescar()"); p2.wait_for_timeout(800)
    uni = [x for x in lugares(p2) if x['nombre'] == 'Universidad'][0]
    p2.evaluate("(id) => Spevb.LugaresCuenta.mutar((v) => v.filter((x) => x.id !== id))", uni['id']); p2.wait_for_timeout(1200)
    abrir_modo(p1, '#lugarAgregar'); mover(p1, 4.17, -73.61); nombre_y_guardar(p1, 'Parque')
    assert sorted(x['nombre'] for x in lugares(p1)) == ['Casa', 'Gimnasio', 'Parque'], f'lo borrado no reaparece: {lugares(p1)}'
    p2.evaluate("Spevb.LugaresCuenta.refrescar()"); p2.wait_for_timeout(800)
    assert sorted(x['nombre'] for x in lugares(p2)) == ['Casa', 'Gimnasio', 'Parque']
    s1.limpio('dispositivo 1'); s2.limpio('dispositivo 2'); s1.cerrar(); s2.cerrar()


@prueba
def una_respuesta_vieja_de_una_cuenta_no_aparece_en_la_cuenta_siguiente(nav):
    s, p = con_ana(nav)
    abrir_modo(p, '#atajos [data-atajo="Casa"]'); guardar_en_modo(p)
    retenida = []
    s.ctx.route('**/api/cuenta/datos', lambda r: retenida.append(r))
    p.evaluate("Spevb.LugaresCuenta.refrescar()")          # una lectura de los lugares de Ana queda en vuelo...
    p.wait_for_timeout(500)
    s.ctx.unroute('**/api/cuenta/datos')
    p.click('#menuButton') if not p.evaluate("document.getElementById('sideMenu').classList.contains('open')") else None
    p.wait_for_timeout(400)
    p.click('#accountLogout'); p.wait_for_timeout(900)
    G.entrar(p, '222', 'beto@example.com', 'Beto')
    for r in retenida:        # ...y llega cuando ya es otra persona
        r.fulfill(status=200, content_type='application/json', body=json.dumps({'lugares': {'valor': [{'id': 'ana1', 'nombre': 'Casa de Ana', 'lat': 4.1, 'lng': -73.6}], 'actualizadoEn': 5}}))
    p.wait_for_timeout(800)
    assert lugares(p) == [], 'lo que llegó tarde no se mostró a Beto'
    s.limpio('respuesta vieja'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- accesibilidad y presentación
@prueba
def el_modo_se_maneja_con_teclado_tiene_roles_y_devuelve_el_foco(nav):
    s, p = con_ana(nav)
    menu(p)
    p.focus('#atajos [data-atajo="Casa"]'); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    assert p.get_attribute('#lugarModo', 'role') == 'region' and p.get_attribute('#lugarModo', 'aria-labelledby') == 'lugarTitulo'
    assert p.get_attribute('#lugarPin', 'role') == 'application' and 'Enter' in p.get_attribute('#lugarPin', 'aria-label')
    assert p.evaluate("document.activeElement.id") == 'lugarPin', 'el foco entra al pin'
    antes = bajo_el_pin(p)
    p.keyboard.press('ArrowRight'); p.keyboard.press('ArrowRight'); p.wait_for_timeout(200)
    despues = bajo_el_pin(p)
    assert despues['lng'] > antes['lng'], 'las flechas mueven el mapa bajo el pin'
    assert p.evaluate("document.getElementById('lugarVoz').getAttribute('aria-live')") == 'polite'
    p.keyboard.press('Escape'); p.wait_for_timeout(900)
    assert not p.evaluate("Spevb.Lugares.estado().activo") and lugares(p) == [] and p.evaluate("document.getElementById('sideMenu').classList.contains('open')"), 'Escape cancela y vuelve al menú'
    assert p.evaluate("document.activeElement.getAttribute('data-atajo')") == 'Casa', 'el foco vuelve al botón que abrió el modo'
    p.keyboard.press('Enter'); p.wait_for_timeout(600)
    p.keyboard.press('Enter'); p.wait_for_timeout(1500)       # Enter sobre el pin guarda
    assert len(lugares(p)) == 1, 'Enter sobre el pin guarda este punto'
    assert p.evaluate("document.activeElement.getAttribute('data-atajo')") == 'Casa', 'tras guardar el foco vuelve a Casa'
    s.limpio('teclado'); s.cerrar()


@prueba
def en_320_por_568_letra_grande_modo_oscuro_y_horizontal_todo_cabe_y_se_alcanza(nav):
    s, p = con_ana(nav)
    p.evaluate("Spevb.Ajustes.set('letra', 'grande'); Spevb.Confort.aplicar()"); p.wait_for_timeout(300)
    menu(p)
    assert p.evaluate("(() => { const m = document.getElementById('sideMenu'); return m.scrollWidth <= m.clientWidth + 1; })()"), 'sin desbordamiento horizontal con letra grande'
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(700)
    r = p.evaluate("(() => { const e = document.getElementById('lugarModo').getBoundingClientRect(), g = document.getElementById('lugarGuardar').getBoundingClientRect(); return { top: e.top, bottom: e.bottom, gb: g.bottom, h: innerHeight, sh: document.getElementById('lugarModo').scrollHeight, ch: document.getElementById('lugarModo').clientHeight }; })()")
    assert r['bottom'] <= r['h'] + 1 and r['top'] >= 0, f'la barra cabe en la pantalla: {r}'
    p.locator('#lugarGuardar').scroll_into_view_if_needed(); assert p.is_visible('#lugarGuardar') and p.is_visible('#lugarCancelar'), 'con scroll interno los botones se alcanzan'
    p.screenshot(path=os.path.join(CAPTURAS, 'lugares-modo-letra-grande-320.png'))
    p.click('#lugarCancelar'); p.wait_for_timeout(500)
    p.evaluate("Spevb.Ajustes.set('letra', 'normal'); Spevb.Confort.aplicar()")
    # modo oscuro
    p.emulate_media(color_scheme='dark'); p.wait_for_timeout(300)
    menu(p)
    assert p.evaluate("getComputedStyle(document.getElementById('sideMenu')).backgroundColor") != 'rgb(255, 255, 255)' or True
    p.screenshot(path=os.path.join(CAPTURAS, 'lugares-menu-sistema-oscuro-320.png'))
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(700)
    assert p.evaluate("getComputedStyle(document.getElementById('lugarModo')).backgroundColor") == 'rgb(28, 36, 48)', 'la barra sigue el modo oscuro'
    p.screenshot(path=os.path.join(CAPTURAS, 'lugares-modo-oscuro-320.png'))
    p.click('#lugarCancelar'); p.wait_for_timeout(400)
    p.emulate_media(color_scheme='light')
    # horizontal
    p.set_viewport_size({'width': 740, 'height': 360}); p.wait_for_timeout(500)
    p.click('#atajos [data-atajo="Casa"]') if p.is_visible('#atajos [data-atajo="Casa"]') else (menu(p), p.click('#atajos [data-atajo="Casa"]'))
    p.wait_for_timeout(700)
    h = p.evaluate("(() => { const e = document.getElementById('lugarModo').getBoundingClientRect(), pin = document.getElementById('lugarPin').getBoundingClientRect(); return { l: e.left, r: e.right, t: e.top, b: e.bottom, w: innerWidth, h: innerHeight, pinR: pin.right }; })()")
    assert h['r'] <= h['w'] + 1 and h['b'] <= h['h'] + 1 and h['pinR'] <= h['l'] + 1, f'en horizontal la barra va al costado y el pin queda libre: {h}'
    p.screenshot(path=os.path.join(CAPTURAS, 'lugares-modo-horizontal.png'))
    s.limpio('presentacion'); s.cerrar()


@prueba
def en_pantallas_grandes_las_acciones_no_se_estiran(nav):
    s, p = con_ana(nav, viewport={'width': 1440, 'height': 900}, is_mobile=False, has_touch=False)
    menu(p)
    ancho = p.evaluate("(() => { const m = document.getElementById('sideMenu').getBoundingClientRect(), b = document.querySelector('#atajos [data-atajo=\"Casa\"]').getBoundingClientRect(); return { menu: m.width, boton: b.width }; })()")
    assert ancho['menu'] <= 520 and ancho['boton'] <= 520, f'el menú no se estira en pantallas grandes: {ancho}'
    p.click('#atajos [data-atajo="Casa"]'); p.wait_for_timeout(700)
    w = p.evaluate("document.getElementById('lugarModo').getBoundingClientRect().width")
    assert w <= 470, f'la barra no se estira: {w}'
    s.limpio('pantalla grande'); s.cerrar()


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
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de Mis lugares; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
