"""Pruebas de navegador de los avatares regionales (4.15.1): manifiesto central, las seis ilustraciones REALES (/img/avatares/), selección estable y prioridad
foto de Google > regional > chigüiro local, también sin conexión (service worker).

El frontend es el real; el backend es un stub; Google y su foto se SIMULAN. Las ilustraciones NO se sustituyen por ningún PNG temporal. NO prueba una cuenta de Google
real ni un teléfono.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/avatares_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import pasajero414_e2e as P  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
PNG = B.PNG_1PX
FOTO = P.FOTO
ESPERADOS = [('chiguiro.png', 'Chigüiro'), ('danta.png', 'Danta'), ('venado.png', 'Venado'), ('guacamaya.png', 'Guacamaya'), ('moriche.png', 'Palma de moriche'), ('saman.png', 'Samán')]
CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'main', 'resources', 'static', 'img', 'avatares')


def prueba(f):
    PRUEBAS.append(f)
    return f


def regional(p, id):
    return p.evaluate("""(id) => { const e = document.getElementById(id), cs = getComputedStyle(e);
      return { archivo: e.dataset.avatar || '', clase: e.classList.contains('con-regional'), fondo: cs.backgroundImage, tamano: cs.backgroundSize, conFoto: e.classList.contains('con-foto'), img: !!e.querySelector('img') }; }""", id)


def con_regionales(s):
    """Las imágenes regionales son las REALES que sirve la aplicación: no se sustituyen ni se interceptan."""
    return s


@prueba
def el_manifiesto_vacio_conserva_el_chiguiro_y_el_modulo_existe(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=None)); p = s.abrir(espera=900)
    assert p.evaluate('Array.isArray(Spevb.Avatares.MANIFIESTO)'), 'el manifiesto central existe'
    p.evaluate('Spevb.Avatares.MANIFIESTO.length = 0')
    assert p.evaluate("Spevb.Avatares.para('id:1') === null"), 'sin imágenes no hay avatar regional'
    a = P.abrir_menu_y_leer(p)
    r = regional(p, 'accountAvatar')
    assert not r['clase'] and 'sevb-cabeza-96.png' in a['fondo'], f'conjunto vacío: chigüiro: {r}'
    s.limpio('manifiesto vacio'); s.cerrar()


@prueba
def la_seleccion_es_estable_determinista_y_reparte(nav):
    s = P.movil(nav); p = s.abrir(espera=700)
    r = p.evaluate("""() => { const A = Spevb.Avatares, a1 = A.para('id:7'), a2 = A.para('id:7'), mayus = A.para(' ID:7 '), ids = [], vistos = new Set();
      for (let i = 1; i <= 40; i++) vistos.add(A.para('id:' + i).archivo);
      return { igual: a1.archivo === a2.archivo && a1.archivo === mayus.archivo, distintos: vistos.size, nulo: A.para('') === null && A.para(null) === null && A.para(undefined) === null,
               url: a1.url, invalida: A.para('x', [{ archivo: '../x.png' }, { archivo: 'a.svg' }, null]) === null, h: A.hash('abc') }; }""")
    assert r['igual'] and r['nulo'] and r['invalida'], r
    assert r['distintos'] >= 2, f'40 cuentas no deben recibir todas el mismo avatar: {r}'
    assert r['url'].startswith('/img/avatares/') and r['h'] == 440920331, r        # FNV-1a de «abc»
    s.limpio('seleccion'); s.cerrar()


@prueba
def el_regional_se_pinta_al_instante_igual_en_menu_y_ajustes_y_y_no_cambia_al_recargar(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=None)); con_regionales(s)
    p = s.abrir(espera=900)
    P.toque(p, '#menuButton'); p.wait_for_timeout(900)
    m = regional(p, 'accountAvatar')
    assert m['clase'] and m['archivo'] and 'img/avatares/' in m['fondo'] and m['tamano'] == 'cover', f'regional en el menú: {m}'
    P.toque(p, '#accountSettings'); p.wait_for_timeout(700)
    a = regional(p, 'setAvatar')
    assert a['archivo'] == m['archivo'], f'el mismo avatar en menú y ajustes: {m} {a}'
    # tras recargar la página (mismo manifiesto) la misma cuenta recibe el mismo avatar
    p.reload(); p.wait_for_timeout(1200)
    P.toque(p, '#menuButton'); p.wait_for_timeout(900)
    assert regional(p, 'accountAvatar')['archivo'] == m['archivo'], 'el avatar no cambia al recargar'
    s.limpio('regional'); s.cerrar()


@prueba
def la_foto_de_google_reemplaza_al_regional_solo_si_carga_y_si_falla_queda_el_regional(nav):
    for modo in ('carga', 'falla', 'sin internet'):
        s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=FOTO)); con_regionales(s)
        if modo == 'carga':
            s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: r.fulfill(status=200, content_type='image/png', body=PNG))
        else:
            s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: r.fulfill(status=404, content_type='text/plain', body='no'))
        p = s.abrir(espera=900)
        if modo == 'sin internet':
            p.evaluate("Object.defineProperty(navigator, 'onLine', { get: () => false })")
        P.toque(p, '#menuButton'); p.wait_for_timeout(1000)
        r = regional(p, 'accountAvatar')
        assert r['clase'] and r['archivo'], f'{modo}: el regional se pinta primero y no desaparece: {r}'
        if modo == 'carga':
            assert r['conFoto'] and r['img'], f'{modo}: la foto de Google queda encima: {r}'
        else:
            assert not r['conFoto'] and not r['img'], f'{modo}: sin foto, se queda el regional sin imagen rota: {r}'
        if modo != 'carga':
            # La foto de Google que falla A PROPÓSITO deja un 404 en la consola del navegador: ese error esperado no es un fallo; cualquier otro error de JavaScript sí lo es.
            s.errores[:] = [e for e in s.errores if 'status of 404' not in e]
        s.limpio('regional foto ' + modo); s.cerrar()


@prueba
def cerrar_sesion_limpia_el_regional_y_dos_cuentas_no_se_mezclan(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=None)); con_regionales(s)
    p = s.abrir(espera=900)
    p.evaluate("window.dispatchEvent(new Event('spevb-superficies'))")
    P.toque(p, '#menuButton'); p.wait_for_timeout(800)
    assert regional(p, 'accountAvatar')['clase']
    s.ctx.route('**/api/cuenta/salir', lambda r: P.json_ok(r, {'ok': True}))
    p.evaluate("Spevb.Cuenta.salir(false)"); p.wait_for_timeout(600)
    r = regional(p, 'accountAvatar')
    assert not r['clase'] and r['archivo'] == '', f'al cerrar sesión no queda el avatar de la cuenta anterior: {r}'
    # dos cuentas distintas pueden recibir avatares distintos (cálculo puro, 40 cuentas)
    n = p.evaluate("new Set(Array.from({ length: 40 }, (_, i) => Spevb.Avatares.para('id:' + (i + 1)).archivo)).size")
    assert n > 1, n
    s.limpio('regional sesion'); s.cerrar()


@prueba
def la_csp_permite_los_avatares_locales_sin_ampliarse(nav):
    s = P.movil(nav); p = s.abrir()
    cab = p.evaluate("fetch('/').then(r => r.headers.get('content-security-policy'))")
    img = cab.split('img-src')[1].split(';')[0]
    assert "'self'" in img and 'https://*.googleusercontent.com' in img and 'evil' not in img, img
    assert p.evaluate("fetch('/js/avatares.js').then(r => r.status)") == 200
    s.limpio('csp avatares'); s.cerrar()


@prueba
def el_manifiesto_tiene_exactamente_las_seis_entradas_validas_y_unicas(nav):
    s = P.movil(nav); p = s.abrir(espera=500)
    m = p.evaluate("Spevb.Avatares.MANIFIESTO.map(e => ({ archivo: e.archivo, nombre: e.nombre, descripcion: e.descripcion }))")
    assert [(e['archivo'], e['nombre']) for e in m] == ESPERADOS, f'el manifiesto debe tener las seis entradas reales y en este orden: {m}'
    assert all(e['descripcion'] for e in m), 'todas llevan descripción'
    assert len({e['archivo'] for e in m}) == 6 and len({e['nombre'] for e in m}) == 6, 'archivos y nombres únicos'
    assert all(p.evaluate("(a) => /^[A-Za-z0-9][A-Za-z0-9._-]*[.](webp|png)$/.test(a)", e['archivo']) for e in m), 'nombres válidos para el validador'
    s.limpio('manifiesto real'); s.cerrar()


@prueba
def las_seis_imagenes_reales_responden_200_miden_128_y_conservan_la_transparencia(nav):
    s = P.movil(nav); p = s.abrir(espera=500)
    for archivo, nombre in ESPERADOS:
        # el archivo existe en el árbol de recursos; que también esté en el classpath final lo comprueba AvataresRecursosTest (mvn verify)
        assert os.path.isfile(os.path.join(CARPETA, archivo)), f'falta {archivo} en src/main/resources/static/img/avatares'
        r = p.evaluate("""async (a) => { const resp = await fetch('/img/avatares/' + a); const ct = resp.headers.get('content-type') || ''; const blob = await resp.blob();
          const bmp = await createImageBitmap(blob); const c = document.createElement('canvas'); c.width = bmp.width; c.height = bmp.height; const g = c.getContext('2d'); g.drawImage(bmp, 0, 0);
          const px = (x, y) => g.getImageData(x, y, 1, 1).data[3];
          return { status: resp.status, ct, w: bmp.width, h: bmp.height, esquinas: [px(0, 0), px(bmp.width - 1, 0), px(0, bmp.height - 1), px(bmp.width - 1, bmp.height - 1)], centro: px(bmp.width >> 1, bmp.height >> 1) }; }""", archivo)
        assert r['status'] == 200 and r['ct'].startswith('image/png'), f'{archivo}: {r}'
        assert r['w'] == 128 and r['h'] == 128, f'{archivo} debe medir 128 × 128: {r}'
        assert r['esquinas'] == [0, 0, 0, 0] and r['centro'] == 255, f'{archivo} conserva la transparencia en las esquinas: {r}'
    s.limpio('imagenes reales'); s.cerrar()


@prueba
def una_muestra_amplia_de_cuentas_reparte_los_seis_personajes(nav):
    s = P.movil(nav); p = s.abrir(espera=500)
    n = p.evaluate("new Set(Array.from({ length: 300 }, (_, i) => Spevb.Avatares.para('id:' + (i + 1)).archivo)).size")
    assert n == 6, f'300 cuentas deben usar los seis personajes, no {n}'
    s.limpio('reparto'); s.cerrar()


@prueba
def la_foto_lenta_no_reemplaza_al_regional_hasta_que_carga(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=FOTO)); pendiente = []
    s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: pendiente.append(r))
    p = s.abrir(espera=700)
    P.toque(p, '#menuButton'); p.wait_for_timeout(900)
    antes = regional(p, 'accountAvatar')
    assert pendiente, 'la foto se pide al ver el perfil'
    assert antes['clase'] and antes['archivo'] and 'img/avatares/' in antes['fondo'] and not antes['conFoto'], f'mientras la foto carga se ve el regional desde el primer cuadro: {antes}'
    pendiente[0].fulfill(status=200, content_type='image/png', body=PNG); p.wait_for_timeout(500)
    despues = regional(p, 'accountAvatar')
    assert despues['conFoto'] and despues['img'], f'al cargar, la foto de Google queda encima: {despues}'
    s.limpio('foto lenta'); s.cerrar()


@prueba
def una_foto_que_fallo_no_se_vuelve_a_pedir_en_la_misma_vista(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=FOTO)); pedidas = []
    s.ctx.route('https://lh3.googleusercontent.com/**', lambda r: (pedidas.append(r.request.url), r.fulfill(status=404, content_type='text/plain', body='no')))
    p = s.abrir(espera=700)
    for _ in range(3):
        P.toque(p, '#menuButton'); p.wait_for_timeout(700)
        P.toque(p, '#accountSettings'); p.wait_for_timeout(700)
        p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert len(pedidas) == 1, f'la foto fallida se pide una sola vez en la vista, no {len(pedidas)}: {pedidas}'
    P.toque(p, '#menuButton'); p.wait_for_timeout(900)
    assert regional(p, 'accountAvatar')['clase'] and not regional(p, 'accountAvatar')['img'], 'sigue el regional sin imagen rota'
    assert len(pedidas) == 1, f'abrir otra vez el menú tampoco repite la petición: {len(pedidas)}'
    s.errores[:] = [e for e in s.errores if 'status of 404' not in e]
    s.limpio('foto fallida una vez'); s.cerrar()


@prueba
def si_el_regional_no_carga_vuelve_el_chiguiro_local(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=None))
    s.ctx.route('**/img/avatares/*.png', lambda r: r.fulfill(status=404, content_type='text/plain', body='no'))
    p = s.abrir(espera=700)
    a = P.abrir_menu_y_leer(p, espera=1000)
    r = regional(p, 'accountAvatar')
    assert not r['clase'] and 'sevb-cabeza-96.png' in a['fondo'] and not r['img'], f'sin el regional queda el chigüiro local y ninguna imagen rota: {r} {a}'
    s.errores[:] = [e for e in s.errores if 'status of 404' not in e]
    s.limpio('regional roto'); s.cerrar()


@prueba
def sin_conexion_los_avatares_locales_siguen_disponibles_por_el_service_worker(nav):
    s = P.movil(nav, service_workers='allow'); P.con_cuenta(s, P.usuario(foto=FOTO))
    p = s.abrir(espera=500)
    B.esperar(p, "navigator.serviceWorker.ready.then(() => true)", 20000)
    B.esperar(p, "caches.keys().then(ks => Promise.all(ks.filter(k => k.includes('-mapa3')).map(k => caches.open(k).then(c => c.keys())))).then(l => l.some(k => k.length > 30 && k.some(r => r.url.includes('/img/avatares/saman.png'))))", 40000)
    p.reload(wait_until='domcontentloaded'); B.esperar(p, "navigator.serviceWorker.controller !== null", 15000)
    s.ctx.set_offline(True)
    for archivo, _ in ESPERADOS:
        r = p.evaluate("(a) => fetch('/img/avatares/' + a).then(r => ({ ok: r.ok, ct: r.headers.get('content-type') }))", archivo)
        assert r['ok'] and r['ct'].startswith('image/'), f'{archivo} sin conexión: {r}'
    p.reload(wait_until='domcontentloaded'); B.esperar(p, "!!(window.Spevb && Spevb.Avatares)", 20000); p.wait_for_timeout(700)
    P.toque(p, '#menuButton'); p.wait_for_timeout(1000)
    r = regional(p, 'accountAvatar')
    assert r['clase'] and r['archivo'] and not r['conFoto'] and not r['img'], f'sin conexión: avatar regional, sin foto de Google ni imagen rota: {r}'
    s.ctx.set_offline(False)
    s.errores[:] = [e for e in s.errores if 'Failed to load resource' not in e]      # la foto de Google sin internet falla a propósito
    s.limpio('avatares sin conexion'); s.cerrar()


@prueba
def en_320_por_568_el_avatar_no_produce_desplazamiento_horizontal(nav):
    s = P.movil(nav, 320, 568); P.con_cuenta(s, P.usuario(foto=None))
    p = s.abrir(espera=700)
    P.toque(p, '#menuButton'); p.wait_for_timeout(900)
    r = p.evaluate("""() => { const e = document.getElementById('accountAvatar').getBoundingClientRect(), d = document.documentElement, m = document.getElementById('sideMenu');
      return { ancho: Math.round(e.width), alto: Math.round(e.height), dentro: e.left >= 0 && e.right <= innerWidth, scrollX: d.scrollWidth > innerWidth, menuX: m.scrollWidth > m.clientWidth + 1 }; }""")
    assert r['ancho'] == 40 and r['alto'] == 40 and r['dentro'] and not r['scrollX'] and not r['menuX'], r
    P.toque(p, '#accountSettings'); p.wait_for_timeout(900)
    r = p.evaluate("() => ({ scrollX: document.documentElement.scrollWidth > innerWidth, a: Math.round(document.getElementById('setAvatar').getBoundingClientRect().width) })")
    assert r['a'] == 40 and not r['scrollX'], r
    s.limpio('320 avatar'); s.cerrar()


@prueba
def el_avatar_es_decorativo_junto_al_nombre_visible(nav):
    s = P.movil(nav); P.con_cuenta(s, P.usuario(foto=None)); p = s.abrir(espera=500)
    P.toque(p, '#menuButton'); p.wait_for_timeout(800)
    r = p.evaluate("() => ({ menu: document.getElementById('accountAvatar').getAttribute('aria-hidden'), nombre: document.getElementById('accountName').textContent, ajustes: document.getElementById('setAvatar').getAttribute('aria-hidden') })")
    assert r['menu'] == 'true' and r['ajustes'] == 'true' and r['nombre'], f'el avatar junto al nombre es decorativo y el nombre está en texto: {r}'
    s.limpio('avatar decorativo'); s.cerrar()


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
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas de avatares regionales; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
