"""Pruebas de navegador del acceso «Continuar con Google» como ÚNICA vía de autenticación (Fase B).

Frontend real y backend stub (e2e/stub_server.py), que simula /api/cuenta/* con el mismo contrato que CuentaController (sesión por cookie HttpOnly, credenciales de un solo uso,
borrado con credencial reciente del mismo «sub», 410 en las vías con contraseña). GOOGLE ESTÁ SIMULADO: un `window.google.accounts.id` de mentira dibuja un botón (como el oficial, dentro
del contenedor que pide la app) y deja disparar el callback con credenciales «fake.…». NO prueba el botón oficial de Google, su ventana emergente, los Orígenes autorizados ni claves reales.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/cuenta_google_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import base64
import json
import os
import secrets
import sys
import time
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
CLIENT = 'stub-client.apps.googleusercontent.com'
MOVIL = dict(viewport={'width': 320, 'height': 568}, is_mobile=True, has_touch=True, device_scale_factor=2)

# Google de mentira: mismo recorrido que el real (initialize con un callback único + renderButton dentro del contenedor), con un botón <button> propio para poder usar el teclado.
GSI_FALSO = """
window.__gsi = { inicializado: 0, renders: 0, clics: 0, config: null, callback: null, ultimoAncho: null };
window.google = { accounts: { id: {
    initialize(cfg) { window.__gsi.inicializado++; window.__gsi.config = cfg; window.__gsi.callback = cfg.callback; },
    renderButton(el, opts) { window.__gsi.renders++; window.__gsi.ultimoAncho = opts.width; const b = document.createElement('button'); b.type = 'button'; b.className = 'gsi-falso';
        b.textContent = 'Continuar con Google (simulado)'; b.style.cssText = 'min-height:44px;width:' + opts.width + 'px;max-width:100%'; b.addEventListener('click', () => { window.__gsi.clics++; }); el.appendChild(b); },
    prompt() {}, cancel() {}, disableAutoSelect() {},
} } };
window.__gsi.emitir = (credential) => { window.__gsi.callback({ credential }); };      // no devuelve la promesa del callback: Google tampoco la espera
"""


def prueba(f):
    PRUEBAS.append(f)
    return f


def cred(sub, correo, nombre='Persona de prueba', edad=2, **extra):
    """Credencial «de mentira» (nunca un token real) con el formato que entiende el stub. Cada una es distinta (un solo uso)."""
    ahora = int(time.time())
    d = {'sub': sub, 'email': correo, 'name': nombre, 'aud': CLIENT, 'iat': ahora - edad, 'exp': ahora + 3000, 'email_verified': True, 'n': secrets.token_hex(4)}
    d.update(extra)
    return 'fake.' + base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip('=')


def sesion(nav, google=True, **opts):
    s = B.Sesion(nav, **opts)
    if google:
        s.ctx.add_init_script(GSI_FALSO)
    s.ctx.request.get(B.URL + '__cuenta/reiniciar')
    return s


def estado_stub(s):
    return s.ctx.request.get(B.URL + '__cuenta/estado').json()


def abrir_dialogo(p):
    p.click('#menuButton'); p.wait_for_timeout(350)
    p.click('#accountLogin'); p.wait_for_timeout(350)


def dlg(p):
    return p.evaluate("""() => { const e = document.getElementById('authEstado'), card = document.getElementById('authCard');
        return { abierto: !document.getElementById('authModal').hidden, estado: e.dataset.estado, texto: e.textContent, busy: e.getAttribute('aria-busy'), boton: document.querySelectorAll('#googleBtn .gsi-falso').length,
            googleVisible: !document.getElementById('googleBox').hidden, reintentar: !document.getElementById('authReintentar').hidden, seguir: !document.getElementById('authCancel').hidden && !document.getElementById('authCancel').disabled,
            foco: document.activeElement.id, dentro: card.contains(document.activeElement) }; }""")


def emitir(p, credencial):
    p.evaluate("(c) => window.__gsi.emitir(c)", credencial)


def usuario(p):
    return p.evaluate("(() => { const u = Spevb.Cuenta.usuario; return u ? { id: u.id, nombre: u.nombre, correo: u.correo } : null; })()")


def entrar(p, sub='111', correo='ana@example.com', nombre='Ana Pérez'):
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    emitir(p, cred(sub, correo, nombre))
    B.esperar(p, "!!Spevb.Cuenta.usuario", 5000)
    p.wait_for_timeout(300)


# ===================================================================================================================== una sola vía pública
@prueba
def el_menu_de_invitado_tiene_una_sola_via_y_la_planeacion_sigue_disponible(nav):
    s = sesion(nav)
    p = s.abrir()
    p.click('#menuButton'); p.wait_for_timeout(350)
    assert p.inner_text('#accountLogin').strip() == 'Continuar con Google'
    assert p.evaluate("document.querySelectorAll('#accountGuest button').length") == 1, 'una sola acción de acceso en el menú de invitado'
    for id_ in ('accountRegister', 'authForm', 'authEmail', 'authPass', 'authName', 'authShow', 'authSwitch', 'authSubmit', 'authHint', 'setPassForm', 'setCur', 'setNew', 'setPassBtn', 'setDel'):
        assert p.evaluate("(i) => !document.getElementById(i)", id_), f'#{id_} ya no existe'
    html = p.evaluate("[document.getElementById('authModal').innerHTML, document.getElementById('settingsModal').innerHTML, document.getElementById('menuAccount').innerHTML].join(' ').toLowerCase()")
    for malo in ('crear cuenta', 'correo y contraseña', 'mostrar u ocultar la contraseña', 'crear contraseña', 'cambiar contraseña', 'type="password"', 'type="email"'):
        assert malo not in html, f'ya no se ofrece: {malo}'
    assert p.evaluate("[...document.querySelectorAll('[data-abrir-cuenta]')].every((b) => b.textContent.trim() === 'Continuar con Google')"), 'los enlaces que recomendaban «Entrar» ahora dicen lo mismo'
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    # como invitado se planea una ruta y el modo viaje sigue disponible
    V.planear(p)
    assert p.is_visible('#startTrip') and p.evaluate("!!Spevb.Planner.seleccion && !!Spevb.Planner.seleccion.viaje"), 'sin cuenta: planear y poder iniciar el viaje'
    assert usuario(p) is None
    s.limpio('invitado'); s.cerrar()


@prueba
def las_vias_con_contrasena_estan_retiradas_en_el_servidor(nav):
    s = sesion(nav)
    for ruta in ('registro', 'entrar', 'clave'):
        r = s.ctx.request.post(B.URL + 'api/cuenta/' + ruta, data=json.dumps({'correo': 'ana@example.com', 'clave': 'clave-larga-1', 'nombre': 'Ana'}), headers={'Content-Type': 'application/json'})
        assert r.status == 410 and 'Continuar con Google' in r.json()['message'], (ruta, r.status)
        assert 'set-cookie' not in {k.lower() for k in r.headers}, f'{ruta} no emite sesión'
    assert estado_stub(s)['sesiones'] == 0
    s.cerrar()


@prueba
def continuar_con_google_abre_el_control_oficial_solo_por_accion_de_la_persona_y_entra(nav):
    s = sesion(nav)
    p = s.abrir()
    p.wait_for_timeout(800)
    assert p.evaluate('window.__gsi.inicializado') == 0 and p.evaluate('window.__gsi.renders') == 0, 'Google no se inicia solo: hace falta una acción de la persona'
    assert estado_stub(s)['intentos'] == 0
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    d = dlg(p)
    assert d['abierto'] and d['boton'] == 1 and d['googleVisible'] and d['seguir'], d
    assert p.evaluate('window.__gsi.config.client_id') == CLIENT and p.evaluate('window.__gsi.config.ux_mode') == 'popup' and p.evaluate('window.__gsi.config.auto_select') is False
    assert 'Toca el botón de Google' in d['texto'] and d['busy'] == 'false'
    assert p.get_attribute('#authCard', 'role') == 'dialog' and p.get_attribute('#authCard', 'aria-modal') == 'true' and p.get_attribute('#authCard', 'aria-labelledby') == 'authTitle'
    assert p.inner_text('#authTitle') == 'Continuar con Google' and p.get_attribute('#authEstado', 'aria-live') == 'polite'
    assert estado_stub(s)['intentos'] == 0, 'abrir el diálogo no envía nada al servidor'
    emitir(p, cred('111', 'ana@example.com', 'Ana Pérez'))
    B.esperar(p, "!!Spevb.Cuenta.usuario", 5000)
    p.wait_for_timeout(400)
    assert not dlg(p)['abierto'] and usuario(p)['nombre'] == 'Ana Pérez'
    p.click('#menuButton'); p.wait_for_timeout(500)
    assert p.is_visible('#accountUser') and p.is_hidden('#accountGuest') and p.inner_text('#accountName') == 'Ana Pérez' and 'ana@example.com · Google' in p.inner_text('#accountEmail')
    assert 'spevb_sesion' not in p.evaluate('document.cookie'), 'la cookie de sesión es HttpOnly'
    # el avatar regional / chigüiro sigue presente (con o sin imágenes en el manifiesto)
    assert p.evaluate("document.getElementById('accountAvatar').getBoundingClientRect().width") >= 36
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    # recargar conserva la sesión (la cookie la lleva el navegador); cerrar sesión y volver a entrar con el MISMO sub devuelve el mismo perfil
    p.reload(); B.esperar(p, "!!(window.Spevb && Spevb.Cuenta && Spevb.Cuenta.usuario)", 8000)
    id1 = usuario(p)['id']
    p.click('#menuButton'); p.wait_for_timeout(400)
    p.click('#accountLogout'); p.wait_for_timeout(600)
    assert usuario(p) is None
    entrar(p, '111', 'ana@example.com', 'Ana Pérez')
    assert usuario(p)['id'] == id1, 'mismo sub: mismo perfil'
    assert estado_stub(s)['usuarios'] == [id1]
    s.limpio('entrar'); s.cerrar()


@prueba
def la_credencial_rechazada_deja_una_salida_con_reintentar_y_seguir_sin_cuenta(nav):
    s = sesion(nav)
    p = s.abrir()
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    emitir(p, cred('112', 'beto@example.com', 'Beto', aud='otra-app.apps.googleusercontent.com'))
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'error'", 5000)
    d = dlg(p)
    assert d['abierto'] and 'no es para esta aplicación' in d['texto'] and d['reintentar'] and d['seguir'] and not d['googleVisible'], d
    assert usuario(p) is None
    renders = p.evaluate('window.__gsi.renders')
    p.click('#authReintentar'); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    assert p.evaluate('window.__gsi.renders') == renders + 1 and dlg(p)['boton'] == 1, 'Reintentar vuelve a dibujar UN botón'
    # una credencial repetida no sirve dos veces
    buena = cred('112', 'beto@example.com', 'Beto')
    emitir(p, buena); B.esperar(p, "!!Spevb.Cuenta.usuario", 5000); p.wait_for_timeout(300)
    p.click('#menuButton'); p.wait_for_timeout(400); p.click('#accountLogout'); p.wait_for_timeout(500)
    abrir_dialogo(p); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    emitir(p, buena); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'error'", 5000)
    assert 'ya se usó' in dlg(p)['texto'] and usuario(p) is None
    p.click('#authCancel'); p.wait_for_timeout(400)
    assert not dlg(p)['abierto'] and usuario(p) is None, 'Seguir sin cuenta cierra y la app sigue como invitado'
    s.errores = [e for e in s.errores if '401' not in e]      # los 401 de arriba son las credenciales que la prueba rechaza a propósito
    s.limpio('rechazo'); s.cerrar()


@prueba
def sin_configuracion_sin_google_sin_conexion_o_sin_servidor_el_dialogo_nunca_queda_vacio(nav):
    # servidor sin GOOGLE_CLIENT_ID
    s = sesion(nav)
    activo = {'google': False}
    s.ctx.route('**/api/cuenta/config', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'adminConfigurado': False} if not activo['google'] else {'google': CLIENT, 'adminConfigurado': False})))
    p = s.abrir()
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'no-configurado'", 5000)
    d = dlg(p)
    assert 'todavía no está configurado' in d['texto'] and d['reintentar'] and d['seguir'] and d['texto'].strip() and not d['googleVisible'], d
    activo['google'] = True
    p.click('#authReintentar'); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    assert dlg(p)['boton'] == 1, 'Reintentar vuelve a preguntar la configuración y sigue'
    s.limpio('no configurado'); s.cerrar()
    # Google bloqueado (el script no carga)
    s = sesion(nav, google=False)
    p = s.abrir()
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'bloqueado'", 15000)
    d = dlg(p)
    assert 'Google no cargó' in d['texto'] and d['reintentar'] and d['seguir'], d
    s.limpio('bloqueado'); s.cerrar()
    # el servidor no responde (con internet)
    s = sesion(nav)
    s.ctx.route('**/api/cuenta/config', lambda r: r.abort('connectionrefused'))
    p = s.abrir()
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'sin-servidor'", 8000)
    assert dlg(p)['reintentar'] and dlg(p)['seguir']
    s.cerrar()
    # sin conexión del dispositivo
    s = sesion(nav)
    p = s.abrir()
    s.ctx.set_offline(True)
    abrir_dialogo(p)
    B.esperar(p, "['sin-conexion', 'sin-servidor'].includes(document.getElementById('authEstado').dataset.estado)", 8000)
    d = dlg(p)
    assert d['texto'].strip() and d['reintentar'] and d['seguir'], d
    s.ctx.set_offline(False)
    s.cerrar()


@prueba
def en_una_direccion_temporal_se_explica_como_abrir_la_oficial_si_existe(nav):
    s = sesion(nav)
    s.ctx.add_init_script("window.__spevbPruebas = Object.assign(window.__spevbPruebas || {}, { hostname: 'abc.trycloudflare.com' });")
    s.ctx.request.get(B.URL + '__cuenta/config?direccionOficial=' + 'https://sevb.example.com')
    p = s.abrir()
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'origen'", 5000)
    d = dlg(p)
    assert 'dirección temporal' in d['texto'] and d['seguir'] and not d['googleVisible'] and not d['reintentar'], d
    enlace = p.evaluate("(() => { const a = document.querySelector('#authAyuda a'); return a ? { href: a.href, texto: a.textContent, rel: a.rel } : null; })()")
    assert enlace and enlace['href'] == 'https://sevb.example.com/' and 'noopener' in enlace['rel'] and 'sevb.example.com' in enlace['texto'], enlace
    assert p.evaluate('window.__gsi.renders') == 0, 'no se pide a Google algo que va a fallar'
    s.limpio('origen'); s.cerrar()
    # sin dirección oficial configurada: solo el mensaje
    s = sesion(nav)
    s.ctx.add_init_script("window.__spevbPruebas = Object.assign(window.__spevbPruebas || {}, { hostname: 'abc.loca.lt' });")
    p = s.abrir()
    abrir_dialogo(p)
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'origen'", 5000)
    assert p.evaluate("document.getElementById('authAyuda').hidden") and 'Pide a quien te compartió' in dlg(p)['texto']
    s.cerrar()


# ===================================================================================================================== diálogo: foco, Escape, 320 px, teclado
@prueba
def abrir_y_cerrar_muchas_veces_conserva_foco_escape_teclado_y_320_px(nav):
    s = sesion(nav, **MOVIL)
    p = s.abrir()
    for vuelta in range(6):
        p.click('#menuButton'); p.wait_for_timeout(350)
        p.click('#accountLogin'); p.wait_for_timeout(350)
        B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
        d = dlg(p)
        assert d['abierto'] and d['dentro'] and d['boton'] == 1, f'vuelta {vuelta}: {d}'
        if vuelta == 0:
            for b in p.locator('#authModal button:visible').all():
                bb = b.bounding_box()
                assert bb['height'] >= 43.5 and bb['width'] >= 43.5, f'área táctil: {b.inner_text()} {bb}'
        assert p.evaluate("document.querySelector('.app').inert") is True, 'el fondo queda inerte'
        # 320 px: nada se desborda y el botón de Google cabe en la tarjeta
        m = p.evaluate("""() => { const c = document.getElementById('authCard').getBoundingClientRect(), b = document.querySelector('#googleBtn .gsi-falso').getBoundingClientRect();
            return { ancho: document.documentElement.scrollWidth, vw: innerWidth, c: [c.left, c.right], b: [b.left, b.right], alto: c.height, vh: innerHeight }; }""")
        assert m['ancho'] <= m['vw'] and m['c'][0] >= 0 and m['c'][1] <= m['vw'] and m['b'][0] >= m['c'][0] and m['b'][1] <= m['c'][1], m
        # teclado: Tab y Shift+Tab se quedan en el diálogo y llegan al control de Google
        vistos = set()
        for _ in range(8):
            p.keyboard.press('Tab'); vistos.add(p.evaluate("document.activeElement.id || document.activeElement.className"))
            assert dlg(p)['dentro'], 'Tab no sale del diálogo'
        for _ in range(8):
            p.keyboard.press('Shift+Tab')
            assert dlg(p)['dentro'], 'Shift+Tab no sale del diálogo'
        assert 'gsi-falso' in vistos and 'authCancel' in vistos, vistos
        p.keyboard.press('Escape'); p.wait_for_timeout(350)
        d = dlg(p)
        assert not d['abierto'] and p.evaluate("document.querySelector('.app').inert") is False, f'vuelta {vuelta}: Escape cierra y el fondo revive'
        assert p.evaluate("document.getElementById('googleBtn').children.length") == 0, 'el botón de Google no se acumula'
        assert p.evaluate("document.querySelectorAll('.gsi-falso').length") == 0
    assert p.evaluate('window.__gsi.inicializado') == 1, 'Google se inicializa una sola vez, no en cada apertura'
    # el botón de Google se activa con el teclado
    abrir_dialogo(p); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    p.focus('.gsi-falso'); p.keyboard.press('Enter')
    assert p.evaluate('window.__gsi.clics') == 1
    p.click('#authCancel'); p.wait_for_timeout(300)
    assert estado_stub(s)['intentos'] == 0
    s.limpio('dialogo'); s.cerrar()


# ===================================================================================================================== respuestas tardías y cambios de sesión
@prueba
def un_callback_de_google_que_llega_despues_de_cerrar_no_entra_ni_envia_nada(nav):
    s = sesion(nav)
    p = s.abrir()
    abrir_dialogo(p); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    p.click('#authCancel'); p.wait_for_timeout(300)
    emitir(p, cred('120', 'tarde@example.com', 'Tarde'))
    p.wait_for_timeout(600)
    assert usuario(p) is None and estado_stub(s)['intentos'] == 0 and estado_stub(s)['usuarios'] == [], 'nada se envió ni se aplicó'
    # y con el diálogo ya cerrado por Escape, igual
    abrir_dialogo(p); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    emitir(p, cred('121', 'tarde2@example.com', 'Tarde 2')); p.wait_for_timeout(500)
    assert usuario(p) is None and estado_stub(s)['intentos'] == 0
    s.limpio('callback tardio'); s.cerrar()


@prueba
def si_la_sesion_cambia_con_el_dialogo_abierto_un_callback_posterior_no_la_pisa(nav):
    s = sesion(nav)
    p = s.abrir()
    abrir_dialogo(p); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    # otra pestaña abre sesión como Ana (mismo navegador, misma cookie): esta página lo descubre al volver la señal
    p.evaluate("(c) => fetch('/api/cuenta/google', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ credential: c }) })", cred('130', 'ana@example.com', 'Ana'))
    p.wait_for_timeout(300)
    p.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); B.esperar(p, "!!Spevb.Cuenta.usuario", 5000); p.wait_for_timeout(400)      # vuelve a esta pestaña
    assert usuario(p)['nombre'] == 'Ana' and not dlg(p)['abierto'], 'el diálogo se cerró: la sesión ya es de otra persona'
    emitir(p, cred('131', 'beto@example.com', 'Beto')); p.wait_for_timeout(600)
    assert usuario(p)['nombre'] == 'Ana', 'el callback posterior no cambia a la persona en sesión'
    assert estado_stub(s)['intentos'] == 1
    s.limpio('sesion cambia'); s.cerrar()


@prueba
def mientras_una_entrada_viaja_al_servidor_no_se_puede_cerrar_ni_entra_otra_y_nada_se_pisa(nav):
    s = sesion(nav)
    retenidas = []
    s.ctx.route('**/api/cuenta/google', lambda r: retenidas.append(r))
    p = s.abrir()
    abrir_dialogo(p); B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    emitir(p, cred('140', 'ana@example.com', 'Ana'))
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'entrando'", 3000)
    d = dlg(p)
    assert d['busy'] == 'true' and not d['seguir'] and 'Entrando' in d['texto'], d
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert dlg(p)['abierto'], 'no se cierra mientras la entrada viaja'
    emitir(p, cred('141', 'beto@example.com', 'Beto')); p.wait_for_timeout(300)
    assert len(retenidas) == 1, 'un segundo callback no genera otra entrada'
    retenidas[0].continue_()
    B.esperar(p, "!!Spevb.Cuenta.usuario", 5000); p.wait_for_timeout(400)
    assert usuario(p)['nombre'] == 'Ana' and not dlg(p)['abierto'] and estado_stub(s)['intentos'] == 1
    s.limpio('en curso'); s.cerrar()


@prueba
def los_datos_que_llegan_tarde_nunca_se_aplican_a_la_cuenta_siguiente_y_cada_cambio_de_usuario_limpia_lo_local(nav):
    s = sesion(nav)
    retenida = []
    s.ctx.route('**/api/cuenta/datos', lambda r: retenida.append(r) if r.request.method == 'GET' else r.fallback())
    p = s.abrir()
    entrar(p, '150', 'ana@example.com', 'Ana')
    p.wait_for_timeout(300)
    assert retenida, 'la sincronización de Ana está en vuelo'
    # Ana cierra sesión ANTES de que lleguen sus datos del servidor
    p.evaluate("Spevb.Cuenta.salir(false)"); p.wait_for_timeout(700)
    assert usuario(p) is None
    retenida[0].fulfill(status=200, content_type='application/json', body=json.dumps({'lugares': {'valor': [{'id': 'ana1', 'nombre': 'Casa de Ana', 'lat': 4.1, 'lng': -73.6}], 'actualizadoEn': 1}}))
    p.wait_for_timeout(600)
    assert p.evaluate("Spevb.Datos.leer('lugares').length") == 0 and p.evaluate("localStorage.getItem('spevb-favoritos')") in (None, '[]'), 'lo que llegó tarde no se guardó en este dispositivo'
    # otra persona entra: no ve nada de Ana
    s.ctx.unroute('**/api/cuenta/datos')
    entrar(p, '151', 'beto@example.com', 'Beto')
    assert p.evaluate("Spevb.Datos.leer('lugares').length") == 0 and usuario(p)['nombre'] == 'Beto'
    # Beto guarda un lugar local; al cerrar sesión se borra de este dispositivo y la siguiente persona no lo hereda
    p.evaluate("Spevb.Datos.escribir('lugares', [{ id: 'b1', nombre: 'Casa de Beto', lat: 4.14, lng: -73.62 }])"); p.wait_for_timeout(1200)
    p.evaluate("Spevb.Cuenta.salir(false)"); p.wait_for_timeout(700)
    assert p.evaluate("Spevb.Datos.leer('lugares').length") == 0, 'cerrar sesión limpia lo personal de este dispositivo'
    entrar(p, '152', 'carla@example.com', 'Carla')
    assert p.evaluate("Spevb.Datos.leer('lugares').length") == 0, 'Carla no hereda los lugares de Beto'
    s.limpio('datos tardios'); s.cerrar()


# ===================================================================================================================== cuenta anterior, API para lugares privados y borrado
@prueba
def una_cuenta_anterior_con_contrasena_no_se_une_sola_y_se_explica_la_recuperacion_sin_borrar_lo_local(nav):
    s = sesion(nav)
    s.ctx.request.get(B.URL + '__cuenta/config?soporte=ayuda@sevb.example.com')
    p = s.abrir()
    p.evaluate("Spevb.Datos.escribir('lugares', [{ id: 'l1', nombre: 'Mi lugar', lat: 4.14, lng: -73.62 }], { remoto: false })")
    # este navegador tenía una sesión nacida de una contraseña antigua: ya no vale, pero NO se borra lo de este dispositivo
    s.ctx.request.get(B.URL + '__cuenta/antigua?correo=ana@example.com')
    p.reload(); B.esperar(p, "!!(window.Spevb && Spevb.Cuenta)", 8000); p.wait_for_timeout(900)
    assert usuario(p) is None and p.evaluate('Spevb.Cuenta.cuentaAnterior') is True
    assert p.evaluate("Spevb.Datos.leer('lugares').length") == 1, 'lo de este dispositivo se conserva'
    p.click('#menuButton'); p.wait_for_timeout(450)
    assert p.is_visible('#accountAnterior') and 'Tenías una cuenta anterior' in p.inner_text('#accountAnterior')
    assert p.evaluate("document.querySelector('#accountAnterior a').getAttribute('href')") == 'mailto:ayuda@sevb.example.com'
    assert p.inner_text('#accountLogin').strip() == 'Continuar con Google', 'sigue habiendo UNA sola vía'
    assert p.evaluate("document.querySelectorAll('#menuAccount input').length") == 0, 'sin campos de contraseña ni de correo'
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    # al entrar con Google con ese correo: perfil nuevo (el stub lo marca) y el aviso sigue ahí
    entrar(p, '160', 'ana@example.com', 'Ana')
    assert p.evaluate('Spevb.Cuenta.cuentaAnterior') is True
    p.click('#menuButton'); p.wait_for_timeout(450)
    assert p.is_visible('#accountAnterior') and p.is_visible('#accountUser')
    s.limpio('cuenta anterior'); s.cerrar()


@prueba
def requiere_abre_el_mismo_dialogo_con_su_motivo_y_devuelve_el_usuario_o_null(nav):
    s = sesion(nav)
    p = s.abrir()
    p.evaluate("() => { window.__r = null; Spevb.Cuenta.requiere('Para guardar este lugar en tu cuenta necesitas continuar con Google.').then((u) => { window.__r = { u } }); }")
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    assert p.is_visible('#authMotivo') and 'Para guardar este lugar' in p.inner_text('#authMotivo')
    p.click('#authCancel'); p.wait_for_timeout(300)
    assert p.evaluate("window.__r") == {'u': None}, 'seguir sin cuenta resuelve null: la función decide qué hacer sin cuenta'
    p.evaluate("() => { window.__r = null; Spevb.Cuenta.requiere('Para guardar este lugar necesitas continuar con Google.').then((u) => { window.__r = { u: u && u.nombre } }); }")
    B.esperar(p, "document.getElementById('authEstado').dataset.estado === 'listo'", 5000)
    emitir(p, cred('170', 'ana@example.com', 'Ana')); B.esperar(p, "window.__r !== null", 5000)
    assert p.evaluate("window.__r") == {'u': 'Ana'}
    p.evaluate("() => { window.__r = null; Spevb.Cuenta.requiere('x').then((u) => { window.__r = { u: u && u.nombre } }); }"); p.wait_for_timeout(200)
    assert p.evaluate("window.__r") == {'u': 'Ana'} and not dlg(p)['abierto'], 'con sesión no abre nada'
    s.limpio('requiere'); s.cerrar()


@prueba
def eliminar_la_cuenta_exige_reautenticar_con_google_la_misma_cuenta_y_confirmar(nav):
    s = sesion(nav, **MOVIL)
    p = s.abrir()
    entrar(p, '180', 'ana@example.com', 'Ana')
    p.click('#menuButton'); p.wait_for_timeout(400); p.click('#accountSettings'); p.wait_for_timeout(450)
    assert p.evaluate("document.querySelectorAll('#settingsModal input').length") == 0, 'ni contraseñas ni correos que escribir'
    assert 'ninguna contraseña' in p.inner_text('#setGoogle')
    p.click('#setDelete'); B.esperar(p, "!document.getElementById('delGoogleBox').hidden", 5000)
    assert 'confirma que eres tú con Google' in p.inner_text('#setDelTexto') and p.evaluate("document.querySelectorAll('#delGoogleBtn .gsi-falso').length") == 1
    # cancelar deja todo como estaba (y Escape cierra Ajustes y reinicia el flujo)
    p.click('#setDelCancelar'); p.wait_for_timeout(300)
    assert p.is_visible('#setDelete') and p.is_hidden('#setDelPaso') and estado_stub(s)['borradas'] == 0
    p.click('#setDelete'); B.esperar(p, "!document.getElementById('delGoogleBox').hidden", 5000)
    p.keyboard.press('Escape'); p.wait_for_timeout(400)
    assert p.evaluate("document.getElementById('settingsModal').hidden") and usuario(p)['nombre'] == 'Ana'
    p.click('#menuButton'); p.wait_for_timeout(400); p.click('#accountSettings'); p.wait_for_timeout(450)
    assert p.is_hidden('#setDelPaso') and p.is_visible('#setDelete'), 'reabrir Ajustes parte de cero'
    # una confirmación de OTRA cuenta de Google: el servidor la rechaza y no se borra nada
    p.click('#setDelete'); B.esperar(p, "!document.getElementById('delGoogleBox').hidden", 5000)
    emitir(p, cred('999', 'otra@example.com', 'Otra')); B.esperar(p, "!document.getElementById('setDelConfirmar').hidden", 3000)
    p.click('#setDelConfirmar'); B.esperar(p, "document.getElementById('setMsg').className === 'error-msg'", 5000)
    assert 'otra cuenta de Google' in p.inner_text('#setMsg') and estado_stub(s)['borradas'] == 0 and usuario(p)['nombre'] == 'Ana'
    # una confirmación antigua (la sesión no basta): rechazada
    B.esperar(p, "!document.getElementById('delGoogleBox').hidden", 5000)
    emitir(p, cred('180', 'ana@example.com', 'Ana', edad=900)); B.esperar(p, "!document.getElementById('setDelConfirmar').hidden", 3000)
    p.click('#setDelConfirmar'); B.esperar(p, "document.getElementById('setMsg').className === 'error-msg'", 5000)
    assert 'vuelve a continuar con Google' in p.inner_text('#setMsg') and estado_stub(s)['borradas'] == 0
    # la correcta: reciente, del mismo sub y confirmada en un segundo paso
    B.esperar(p, "!document.getElementById('delGoogleBox').hidden", 5000)
    buena = cred('180', 'ana@example.com', 'Ana')
    emitir(p, buena); B.esperar(p, "!document.getElementById('setDelConfirmar').hidden", 3000)
    assert p.evaluate("document.activeElement.id") == 'setDelCancelar', 'la opción segura recibe el foco'
    assert 'No se puede deshacer' in p.inner_text('#setDelTexto') and estado_stub(s)['borradas'] == 0, 'confirmar con Google todavía no borra'
    p.click('#setDelConfirmar'); B.esperar(p, "!Spevb.Cuenta.usuario", 6000); p.wait_for_timeout(400)
    assert estado_stub(s)['borradas'] == 1 and estado_stub(s)['usuarios'] == [] and p.evaluate("document.getElementById('settingsModal').hidden")
    assert p.evaluate("Spevb.Datos.leer('lugares').length") == 0
    # esa credencial no vuelve a servir para nada
    r = s.ctx.request.post(B.URL + 'api/cuenta/google', data=json.dumps({'credential': buena}), headers={'Content-Type': 'application/json'})
    assert r.status == 401 and 'ya se usó' in r.json()['message']
    s.errores = [e for e in s.errores if '403' not in e and '401' not in e]      # los rechazos de arriba son a propósito
    s.limpio('borrado'); s.cerrar()


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
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0][:700] if str(e) else repr(e))
                traceback.print_exc(limit=3)
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas del acceso con Google; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
