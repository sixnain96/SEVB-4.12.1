"""Pruebas de navegador de «Instalar en tu celular» (instalar.js): detecta el navegador y el sistema y muestra el paso a paso para instalar SEVB como app (PWA).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/instalar_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
CAPTURAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'capturas-viaje')
MOVIL = {'viewport': {'width': 360, 'height': 740}, 'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2}

UA = {
    'android-chrome': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
    'android-edge': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 EdgA/126.0.0.0',
    'android-firefox': 'Mozilla/5.0 (Android 14; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0',
    'android-samsung': 'Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36',
    'android-opera': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 OPR/80.0.0.0',
    'ios-safari': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'ios-chrome': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.0.0 Mobile/15E148 Safari/604.1',
    'ios-firefox': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/127.0 Mobile/15E148 Safari/605.1.15',
    'ios-edge': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/126.0.0.0 Mobile/15E148 Safari/605.1.15',
    'desktop-chrome': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'desktop-edge': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
    'desktop-firefox': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'desktop-safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
}
BRAVE = "navigator.brave = { isBrave: () => Promise.resolve(true) };"


def prueba(f):
    PRUEBAS.append(f)
    return f


def abrir(nav, ua=None, init=None, **opts):
    extra = {'user_agent': ua} if ua else {}
    s = B.Sesion(nav, **{**MOVIL, **extra, **opts})
    if init:
        s.ctx.add_init_script(init)
    p = s.abrir()
    B.esperar(p, "!!(window.Spevb && Spevb.Instalar && Spevb.Instalar.actual())", 8000)
    return s, p


def ver_seccion(p):
    p.click('#menuButton'); p.wait_for_timeout(450)
    p.evaluate("document.getElementById('menuMas').open = true; document.getElementById('menuInstalar').open = true")
    p.wait_for_timeout(200)


def leer(p):
    return p.evaluate("({ det: document.getElementById('instalarDetectado').textContent, pasos: [...document.querySelectorAll('#instalarPasos li')].map(l => l.textContent), nota: document.getElementById('instalarNota').textContent, ahora: !document.getElementById('instalarAhoraCaja').hidden })")


@prueba
def la_deteccion_distingue_navegador_y_sistema_con_cada_user_agent(nav):
    s, p = abrir(nav)
    esperado = {'android-chrome': ('android', 'chrome'), 'android-edge': ('android', 'edge'), 'android-firefox': ('android', 'firefox'), 'android-samsung': ('android', 'samsung'), 'android-opera': ('android', 'opera'),
                'ios-safari': ('ios', 'safari'), 'ios-chrome': ('ios', 'chrome'), 'ios-firefox': ('ios', 'firefox'), 'ios-edge': ('ios', 'edge'),
                'desktop-chrome': ('desktop', 'chrome'), 'desktop-edge': ('desktop', 'edge'), 'desktop-firefox': ('desktop', 'firefox'), 'desktop-safari': ('desktop', 'safari')}
    for clave, (sis, navg) in esperado.items():
        r = p.evaluate("(ua) => Spevb.Instalar.detectar(ua, '', 0, false)", UA[clave])
        assert (r['sistema'], r['nav']) == (sis, navg), (clave, r)
    assert p.evaluate("(ua) => Spevb.Instalar.detectar(ua, '', 0, true)", UA['android-chrome'])['nav'] == 'brave', 'Brave se reconoce con su propia pregunta'
    assert p.evaluate("Spevb.Instalar.detectar('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 'MacIntel', 5, false)")['sistema'] == 'ios', 'un iPad que se presenta como Mac'
    assert p.evaluate("Spevb.Instalar.detectar('algo raro', '', 0, false)")['nav'] == 'otro'
    s.limpio('deteccion'); s.cerrar()


@prueba
def cada_navegador_muestra_su_paso_a_paso_en_el_menu(nav):
    casos = {'android-chrome': ('Chrome', 'Android', 'Instalar aplicación'), 'android-firefox': ('Firefox', 'Android', 'Instalar'), 'android-samsung': ('Samsung Internet', 'Android', 'Añadir página a'),
             'android-edge': ('Edge', 'Android', 'Añadir al teléfono'), 'ios-safari': ('Safari', 'iPhone', 'Añadir a pantalla de inicio'), 'ios-chrome': ('Chrome', 'iPhone', 'Compartir'),
             'desktop-chrome': ('Chrome', 'computador', 'icono de instalar'), 'desktop-firefox': ('Firefox', 'computador', 'Chrome o Edge')}
    for clave, (nombre, sistema, frase) in casos.items():
        s, p = abrir(nav, UA[clave])
        ver_seccion(p)
        r = leer(p)
        assert nombre in r['det'] and sistema in r['det'], (clave, r['det'])
        assert len(r['pasos']) >= 2 and any(frase in x for x in r['pasos']), (clave, r['pasos'])
        s.limpio(clave); s.cerrar()


@prueba
def brave_se_reconoce_y_explica_sus_pasos(nav):
    s, p = abrir(nav, UA['android-chrome'], init=BRAVE)
    B.esperar(p, "Spevb.Instalar.actual().nav === 'brave'", 4000)
    ver_seccion(p)
    r = leer(p)
    assert 'Brave' in r['det'] and any('Brave' in x for x in r['pasos']), r
    s.limpio('brave'); s.cerrar()


@prueba
def el_paso_a_paso_se_lee_bien_en_320_por_568_sin_desborde_y_con_iconos(nav):
    s, p = abrir(nav, UA['ios-safari'], viewport={'width': 320, 'height': 568})
    ver_seccion(p)
    p.locator('#menuInstalar').scroll_into_view_if_needed()
    d = p.evaluate("(() => { const m = document.getElementById('sideMenu'); return { ancho: m.scrollWidth <= m.clientWidth + 1, iconos: document.querySelectorAll('#instalarPasos svg').length, numeros: getComputedStyle(document.querySelector('#instalarPasos li'), '::before').content }; })()")
    assert d['ancho'] and d['iconos'] >= 1 and d['numeros'] != 'none', d
    p.evaluate("document.getElementById('menuInstalar').scrollIntoView({ block: 'start' })"); p.wait_for_timeout(200)
    p.screenshot(path=os.path.join(CAPTURAS, 'instalar-ios-safari-320.png'))
    s.limpio('320'); s.cerrar()


@prueba
def el_boton_instalar_ahora_aparece_solo_cuando_el_navegador_lo_permite_y_lo_usa(nav):
    s, p = abrir(nav, UA['android-chrome'])
    ver_seccion(p)
    assert not leer(p)['ahora'], 'sin el aviso del navegador no hay botón'
    p.evaluate("""() => { window.__prompt = 0; const e = new Event('beforeinstallprompt', { cancelable: true }); e.prompt = () => { window.__prompt++; return Promise.resolve(); }; e.userChoice = Promise.resolve({ outcome: 'accepted' }); window.dispatchEvent(e); }""")
    p.wait_for_timeout(200)
    assert leer(p)['ahora'] and p.is_visible('#instalarAhora')
    p.click('#instalarAhora'); p.wait_for_timeout(300)
    assert p.evaluate('window.__prompt') == 1 and not leer(p)['ahora'], 'usa el aviso del navegador una sola vez'
    p.screenshot(path=os.path.join(CAPTURAS, 'instalar-android-chrome.png'))
    s.limpio('instalar ahora'); s.cerrar()


@prueba
def si_ya_esta_instalada_lo_dice_y_sin_https_explica_por_que_no_se_puede(nav):
    s, p = abrir(nav, UA['android-chrome'], init="const mm = window.matchMedia.bind(window); window.matchMedia = (q) => /display-mode: standalone/.test(q) ? { matches: true, addEventListener() {}, removeEventListener() {} } : mm(q);")
    ver_seccion(p)
    r = leer(p)
    assert 'Ya tienes SEVB instalada' in r['det'] and r['pasos'] == [], r
    s.cerrar()
    s, p = abrir(nav, UA['android-chrome'], init="Object.defineProperty(window, 'isSecureContext', { value: false });")
    ver_seccion(p)
    r = leer(p)
    assert 'https://' in r['nota'] and r['pasos'] == [], r
    s.limpio('instalada y sin https'); s.cerrar()


@prueba
def si_la_deteccion_se_equivoca_la_persona_elige_su_navegador(nav):
    s, p = abrir(nav, UA['android-chrome'])
    ver_seccion(p)
    p.select_option('#instalarOtro', 'ios-safari'); p.wait_for_timeout(200)
    r = leer(p)
    assert 'Safari' in r['det'] and any('Compartir' in x for x in r['pasos']), r
    p.select_option('#instalarOtro', 'desktop-firefox'); p.wait_for_timeout(200)
    assert any('Chrome o Edge' in x for x in leer(p)['pasos'])
    s.limpio('elegir navegador'); s.cerrar()


@prueba
def la_seccion_se_abre_con_teclado_y_el_texto_es_texto_no_html(nav):
    s, p = abrir(nav, UA['android-chrome'])
    p.click('#menuButton'); p.wait_for_timeout(450)
    p.evaluate("document.getElementById('menuMas').open = true"); p.wait_for_timeout(100)
    p.focus('#menuInstalar > summary'); p.keyboard.press('Enter'); p.wait_for_timeout(200)
    assert p.evaluate("document.getElementById('menuInstalar').open")
    assert p.evaluate("document.querySelectorAll('#instalarPasos li').length") >= 3
    assert p.evaluate("[...document.querySelectorAll('#instalarPasos svg')].every(s => s.getAttribute('aria-hidden') === 'true')"), 'los iconos son decorativos: el texto ya dice el nombre del botón'
    assert 'APK' in p.inner_text('.instalar-intro') and 'Play Store' in p.inner_text('.instalar-intro'), 'explica que no es un APK ni va a una tienda'
    s.limpio('teclado'); s.cerrar()


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
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de «Instalar en tu celular»; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
