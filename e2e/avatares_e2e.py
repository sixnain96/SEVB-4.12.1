"""Pruebas de navegador de los avatares regionales de respaldo (4.15): manifiesto central, selección estable y prioridad foto de Google > regional > chigüiro.

El frontend es el real; el backend es un stub; Google y su foto se SIMULAN. Las imágenes regionales no existen todavía en el repositorio: las pruebas inyectan un
manifiesto temporal con un PNG de 1 px servido por una ruta de Playwright. NO prueba una cuenta de Google real ni un teléfono.
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
MANIFIESTO_JS = """() => { const m = Spevb.Avatares.MANIFIESTO; m.length = 0;
  ['jaguar','garza','arpa','cunaguaro'].forEach((n) => m.push({ archivo: n + '.png', nombre: n, descripcion: 'prueba' })); return m.length; }"""


def prueba(f):
    PRUEBAS.append(f)
    return f


def regional(p, id):
    return p.evaluate("""(id) => { const e = document.getElementById(id), cs = getComputedStyle(e);
      return { archivo: e.dataset.avatar || '', clase: e.classList.contains('con-regional'), fondo: cs.backgroundImage, tamano: cs.backgroundSize, conFoto: e.classList.contains('con-foto'), img: !!e.querySelector('img') }; }""", id)


def con_regionales(s):
    s.ctx.route('**/img/avatares/*.png', lambda r: r.fulfill(status=200, content_type='image/png', body=PNG))


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
    p.evaluate(MANIFIESTO_JS)
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
    p = s.abrir(espera=900); p.evaluate(MANIFIESTO_JS)
    P.toque(p, '#menuButton'); p.wait_for_timeout(700)
    # el avatar se calcula al abrir el perfil: se fuerza el repintado con el manifiesto ya cargado
    p.evaluate("window.dispatchEvent(new Event('spevb-superficies'))"); p.wait_for_timeout(300)
    m = regional(p, 'accountAvatar')
    assert m['clase'] and m['archivo'] and 'img/avatares/' in m['fondo'] and m['tamano'] == 'cover', f'regional en el menú: {m}'
    P.toque(p, '#accountSettings'); p.wait_for_timeout(700)
    a = regional(p, 'setAvatar')
    assert a['archivo'] == m['archivo'], f'el mismo avatar en menú y ajustes: {m} {a}'
    # tras recargar la página (mismo manifiesto) la misma cuenta recibe el mismo avatar
    p.reload(); p.wait_for_timeout(1200); p.evaluate(MANIFIESTO_JS)
    p.evaluate("window.dispatchEvent(new Event('spevb-superficies'))")
    P.toque(p, '#menuButton'); p.wait_for_timeout(700)
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
        p = s.abrir(espera=900); p.evaluate(MANIFIESTO_JS)
        if modo == 'sin internet':
            p.evaluate("Object.defineProperty(navigator, 'onLine', { get: () => false })")
        p.evaluate("window.dispatchEvent(new Event('spevb-superficies'))")
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
    p = s.abrir(espera=900); p.evaluate(MANIFIESTO_JS)
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
