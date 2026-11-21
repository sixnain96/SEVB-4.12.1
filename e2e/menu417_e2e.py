"""Pruebas de navegador del menú principal simplificado (4.17): lo diario a la vista, todo lo demás dentro de «Más», título del panel y acciones del resultado.

Frontend real y stub. Capturas en docs/capturas-menu/ (las de «despues-*» las generan estas pruebas solo en parte: ver docs/MENU-PRINCIPAL-4.17.md).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/menu417_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
MOVIL = {'viewport': {'width': 375, 'height': 812}, 'is_mobile': True, 'has_touch': True}
SECUNDARIAS = ['menuAyuda', 'menuVista', 'menuInstalar', 'menuOffline', 'menuExplorar', 'colorGuide', 'menuLinks', 'menuCerca']


def prueba(f):
    PRUEBAS.append(f)
    return f


def abrir_menu(p):
    p.click('#menuButton'); p.wait_for_timeout(500)


@prueba
def el_menu_deja_a_la_vista_planear_cuenta_lugares_recientes_y_un_solo_mas(nav):
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    abrir_menu(p)
    for sel in ('#menuInicio', '#menuAccount', '#menuLugares > summary', '#menuEspacio > summary', '#logros > summary', '#rachaChip', '#menuMas > summary'):
        assert p.is_visible(sel), f'a la vista: {sel}'
    assert 'Planear un viaje' in p.inner_text('#menuInicio'), 'el botón principal dice qué hace'
    for id_ in SECUNDARIAS:
        assert not p.is_visible('#' + id_), f'{id_} va dentro de «Más» y llega plegado'
        assert p.evaluate("(id) => document.getElementById(id).closest('#menuMas') !== null", id_), f'{id_} vive dentro de «Más»'
    resumenes = p.evaluate("[...document.querySelectorAll('#sideMenu > details > summary')].filter(s => s.offsetParent !== null).length")
    assert resumenes == 4, f'solo Mis lugares, Recientes, Logros y racha y Más como secciones de primer nivel: {resumenes}'
    assert p.evaluate("document.getElementById('logros').closest('#menuMas') === null"), 'los logros ya NO viven dentro de «Más»'
    h = p.evaluate("(() => { const m = document.getElementById('sideMenu'); return m.scrollHeight / innerHeight; })()")
    assert h <= 1.45, f'el menú cabe casi en una pantalla a 375 × 812: {h:.2f}'
    assert p.evaluate("(() => { const m = document.getElementById('sideMenu'); return m.scrollWidth <= m.clientWidth + 1; })()"), 'sin desplazamiento horizontal'
    for sel in ('#menuInicio', '#menuMas > summary', '#menuLugares > summary', '#menuEspacio > summary'):
        alto = p.evaluate("(s) => document.querySelector(s).getBoundingClientRect().height", sel)
        assert alto >= 44, f'{sel} se toca bien: {alto}'
    s.limpio('menu a la vista'); s.cerrar()


@prueba
def mas_se_abre_con_teclado_agrupa_lo_secundario_y_conserva_todas_las_funciones(nav):
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    abrir_menu(p)
    p.focus('#menuMas > summary'); p.keyboard.press('Enter'); p.wait_for_timeout(200)
    assert p.evaluate("document.getElementById('menuMas').open"), 'Enter abre «Más»'
    nombres = p.evaluate("[...document.querySelectorAll('#menuMas > .menu-mas-cuerpo > details > summary')].map(s => s.textContent.replace(/\\s+/g, ' ').trim())")
    for t in ('Ayuda', 'Pantalla y accesibilidad', 'Instalar en tu celular', 'Mala señal o sin internet', 'Explorar recorridos'):
        assert any(n.startswith(t) for n in nombres), (t, nombres)
    for sel in ('#menuBienvenida', '#menuPractica', '[data-letra="grande"]', '[data-confort="mapaNoche"]', '#offlineDownload', '#routeSearch', '#nearOriginRoutes', '#colorGuide', '#logrosLista', '#instalarPasos'):
        assert p.locator(sel).count() == 1, f'sigue existiendo {sel}'
    p.click('#menuAyuda > summary'); p.wait_for_timeout(250)
    assert p.is_visible('#menuBienvenida') and p.is_visible('#menuPractica'), 'Ayuda muestra sus dos botones'
    p.keyboard.press('Escape'); p.wait_for_timeout(600)
    assert p.evaluate("document.activeElement.id") == 'menuButton', 'el foco vuelve al botón ☰'
    s.limpio('mas'); s.cerrar()


@prueba
def planear_un_viaje_desde_el_menu_limpia_a_y_b_y_el_menu_se_cierra(nav):
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    V.planear(p)
    abrir_menu(p)
    p.click('#menuInicio'); p.wait_for_timeout(700)
    assert p.evaluate("document.getElementById('tripOrigin').value") == '' and p.evaluate("document.getElementById('tripDestination').value") == '', 'A y B quedan vacíos'
    assert not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"), 'el menú se cierra'
    s.limpio('planear un viaje'); s.cerrar()


@prueba
def el_panel_inicial_dice_que_hacer_y_no_repite_la_instruccion(nav):
    for w, h in ((375, 812), (320, 568), (430, 932)):
        s = V.sesion(nav, viewport={'width': w, 'height': h}, is_mobile=True, has_touch=True)
        p = s.abrir()
        assert p.is_visible('#planIntro') and '¿A dónde vamos?' in p.inner_text('#planIntro h2'), f'{w}x{h}: título visible'
        assert not p.is_visible('#tripStatus'), f'{w}x{h}: la franja «Marca A y B…» ya no repite la instrucción'
        assert p.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f'{w}x{h}: sin desborde horizontal'
        for sel in ('#useMyLocation', '#pickOrigin', '#pickDestination', '#searchOrigin', '#searchDestination'):
            if p.is_visible(sel):
                r = p.evaluate("(s) => { const b = document.querySelector(s), r = b.getBoundingClientRect(); return { w: r.width, h: r.height, rec: b.scrollWidth > b.clientWidth + 1 }; }", sel)
                assert r['w'] >= 44 and r['h'] >= 44 and not r['rec'], f'{w}x{h} {sel}: {r}'
        t = p.evaluate("document.getElementById('useMyLocation').getAttribute('data-etiqueta')")
        assert t == 'Mi ubicación', t
        assert p.evaluate("document.getElementById('searchOrigin').getAttribute('aria-label')"), 'Buscar sigue teniendo nombre accesible aunque sea un icono'
        s.limpio(f'panel {w}x{h}'); s.cerrar()


@prueba
def las_acciones_del_resultado_son_tres_mas_un_mas_y_el_aviso_largo_se_abre_al_tocarlo(nav):
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    V.planear(p)
    assert p.evaluate("!document.getElementById('tripTools').hidden")
    visibles = p.evaluate("[...document.querySelectorAll('#tripTools > button')].filter(b => b.offsetParent !== null).map(b => b.id)")
    assert visibles == ['saveTrip', 'alightAlert', 'tripToolsMas'], visibles
    assert p.evaluate("document.getElementById('tripToolsExtra').hidden") and p.get_attribute('#tripToolsMas', 'aria-expanded') == 'false'
    p.evaluate("document.getElementById('tripTools').scrollIntoView({ block: 'center' })")
    p.click('#tripToolsMas'); p.wait_for_timeout(200)
    assert p.get_attribute('#tripToolsMas', 'aria-expanded') == 'true'
    extra = p.evaluate("[...document.querySelectorAll('#tripToolsExtra > button')].filter(b => b.offsetParent !== null).map(b => b.id)")
    assert extra == ['reportProblem'], extra      # Google Maps y WhatsApp salieron al panel «Compartir»
    # el aviso del resultado: dos líneas y se abre al tocarlo (el texto completo sigue en el DOM)
    est = p.evaluate("(() => { const e = document.getElementById('tripStatus'); return { largo: e.classList.contains('es-largo'), len: e.textContent.trim().length, h: e.getBoundingClientRect().height, tab: e.tabIndex }; })()")
    if est['largo']:
        assert est['h'] < 90 and est['tab'] == 0, est
        p.evaluate("document.getElementById('tripStatus').click()"); p.wait_for_timeout(150)
        assert p.evaluate("document.getElementById('tripStatus').classList.contains('abierto')") and p.get_attribute('#tripStatus', 'aria-expanded') == 'true'
        p.evaluate("document.getElementById('tripStatus').click()"); p.wait_for_timeout(100)
        assert not p.evaluate("document.getElementById('tripStatus').classList.contains('abierto')")
    # borrar A y B oculta la barra y «Más» vuelve a quedar plegado
    p.evaluate("document.getElementById('clearTripPoints').click()"); p.wait_for_timeout(500)
    assert p.evaluate("document.getElementById('tripTools').hidden") and p.evaluate("document.getElementById('tripToolsExtra').hidden")
    s.limpio('acciones del resultado'); s.cerrar()


@prueba
def en_320_el_menu_y_el_panel_no_se_desbordan_ni_cortan_texto(nav):
    s = V.sesion(nav, viewport={'width': 320, 'height': 568}, is_mobile=True, has_touch=True)
    p = s.abrir()
    abrir_menu(p)
    p.evaluate("document.getElementById('menuMas').open = true; document.querySelectorAll('#menuMas details').forEach((d) => { d.open = true; })"); p.wait_for_timeout(300)
    r = p.evaluate("""() => { const m = document.getElementById('sideMenu'); const mal = [];
        m.querySelectorAll('summary, button, strong, small, p').forEach((e) => { if (e.offsetParent && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible') mal.push(e.id || e.className || e.tagName); });
        return { ancho: m.scrollWidth <= m.clientWidth + 1, mal }; }""")
    assert r['ancho'] and not r['mal'], r
    s.limpio('320'); s.cerrar()


@prueba
def la_lupa_de_cada_campo_titila_mientras_se_escribe_y_buscar_rutas_cuando_a_y_b_estan_listos(nav):
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    p.wait_for_timeout(600)
    anim = lambda sel: p.evaluate("(s) => getComputedStyle(document.querySelector(s)).animationName", sel)
    assert 'busca-pulso' not in p.get_attribute('#searchOrigin', 'class') and 'busca-pulso' not in p.get_attribute('#searchDestination', 'class'), 'vacíos: nada titila'
    p.click('#tripDestination'); p.keyboard.type('Cll 38', delay=20); p.wait_for_timeout(250)
    assert 'busca-pulso' in p.get_attribute('#searchDestination', 'class'), 'escribiendo B: la lupa de B llama la atención'
    assert 'busca-pulso' not in p.get_attribute('#searchOrigin', 'class'), 'la de A no, porque A está vacío'
    assert 'busca-halo' in anim('#searchDestination'), 'es un halo (animación CSS), no un salto'
    p.fill('#tripDestination', ''); p.wait_for_timeout(250)
    assert 'busca-pulso' not in p.get_attribute('#searchDestination', 'class'), 'sin texto deja de titilar'
    p.click('#tripOrigin'); p.keyboard.type('Cra 22', delay=20); p.wait_for_timeout(250)
    assert 'busca-pulso' in p.get_attribute('#searchOrigin', 'class'), 'escribiendo A: la lupa de A titila'
    # con movimiento reducido el halo se apaga (queda un borde fijo)
    p.emulate_media(reduced_motion='reduce'); p.wait_for_timeout(200)
    assert anim('#searchOrigin') == 'none', anim('#searchOrigin')
    p.emulate_media(reduced_motion='no-preference')
    # A y B listos y todavía sin buscar: «Buscar rutas» invita a pulsarlo; después deja de titilar
    p.fill('#tripOrigin', V.ESC['multi']); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    p.fill('#tripDestination', V.DEST); p.keyboard.press('Enter'); p.wait_for_timeout(900)
    assert 'busca-pulso' in p.get_attribute('#planTrip', 'class'), 'A y B confirmados: «Buscar rutas» titila'
    assert 'busca-pulso' not in p.get_attribute('#searchOrigin', 'class') and 'busca-pulso' not in p.get_attribute('#searchDestination', 'class'), 'ya confirmados: las lupas se calman'
    p.evaluate("document.querySelector('#planTrip').click()")
    B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 12000)
    p.wait_for_timeout(600)
    assert 'busca-pulso' not in p.get_attribute('#planTrip', 'class'), 'con resultados deja de titilar'
    s.limpio('lupa titila'); s.cerrar()


@prueba
def al_buscar_el_panel_va_solo_a_mejor_opcion_aunque_el_campo_siga_enfocado(nav):
    for w, h in ((375, 812), (360, 640), (430, 932)):
        s = V.sesion(nav, viewport={'width': w, 'height': h}, is_mobile=True, has_touch=True)
        p = s.abrir()
        p.fill('#tripOrigin', V.ESC['multi']); p.keyboard.press('Enter'); p.wait_for_timeout(700)
        p.fill('#tripDestination', V.DEST); p.keyboard.press('Enter'); p.wait_for_timeout(700)
        p.evaluate("document.getElementById('tripDestination').focus()")      # el campo de B sigue enfocado (el teclado seguiría abierto)
        p.evaluate("document.querySelector('#planTrip').click()")
        B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 12000)
        p.wait_for_timeout(1600)
        r = p.evaluate("""() => { const t = document.getElementById('mejorOpcion'), b = document.querySelector('#sheet .sheet-body').getBoundingClientRect(), r = t.getBoundingClientRect(), f = document.activeElement;
            return { visible: !t.hidden && r.height > 0, arriba: r.top - b.top, foco: f && f.tagName, scroll: document.querySelector('#sheet .sheet-body').scrollTop }; }""")
        assert r['visible'] and -4 <= r['arriba'] <= 90, f'{w}x{h}: la tarjeta «Mejor opción» queda al inicio del panel: {r}'
        assert r['foco'] != 'INPUT', f'{w}x{h}: el teclado se cerró al llegar los resultados: {r}'
        s.limpio(f'mejor opcion {w}x{h}'); s.cerrar()


JS_CARTELES = """() => [...document.querySelectorAll('.map-tag-wrap')].filter((w) => w.querySelector(':scope > .map-tag, :scope > .leg-badge, :scope > .swap-callout'))
    .filter((w) => !w.classList.contains('sec-oculto')).map((w) => (w.textContent || '').trim().replace(/\\s+/g, ' '))"""


def muestrear(p, segundos, cada=400):
    vistos, orden, ultimo = set(), [], None
    for _ in range(int(segundos * 1000 / cada)):
        v = p.evaluate(JS_CARTELES)
        assert len(v) <= 2, f'a la vez se ve como mucho un paso (cartel + insignia): {v}'
        clave = '|'.join(sorted(v))
        if clave != ultimo and v:
            orden.append(clave); ultimo = clave
        vistos.update(v)
        p.wait_for_timeout(cada)
    return vistos, orden


@prueba
def los_carteles_del_mapa_salen_uno_a_uno_en_ciclo_con_y_sin_transbordo_y_al_iniciar_el_viaje_quedan_todos(nav):
    # sin transbordo: sube → baja → sube → baja…
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    V.planear(p); V.destino_lejos(p)
    p.wait_for_timeout(500)
    vistos, orden = muestrear(p, 8)
    assert any('Sube' in x for x in vistos) and any('Baja' in x for x in vistos), vistos
    assert len(orden) >= 3 and orden[0] == orden[2], f'es un ciclo: vuelve a empezar por el primero: {orden}'
    # al iniciar el viaje quedan todos a la vista (ya no hay secuencia)
    V.iniciar(p); p.wait_for_timeout(3500)
    ocultos = p.evaluate("document.querySelectorAll('.map-tag-wrap.sec-oculto').length")
    assert ocultos == 0, 'con el viaje en curso no queda ningún cartel escondido'
    s.limpio('secuencia directa'); s.cerrar()
    # con transbordo: sube(1) → baja → cambio de bus → sube(2) → bajada final
    s = V.sesion(nav, **MOVIL)
    p = s.abrir()
    V.planear(p, 'transbordos'); p.wait_for_timeout(800)
    vistos, orden = muestrear(p, 16)
    texto = ' / '.join(vistos)
    for esperado in ('Sube al primer bus', 'Baja del primer bus', 'CAMBIO DE BUS', 'Sube al segundo bus', 'Bajada final'):
        assert esperado in texto, (esperado, vistos)
    assert len(orden) >= 5, f'cinco pasos en orden: {orden}'
    primero = [i for i, x in enumerate(orden) if 'Sube al primer bus' in x][0]
    assert 'Baja del primer bus' in orden[primero + 1] and 'CAMBIO' in orden[primero + 2] and 'Sube al segundo bus' in orden[primero + 3] and 'Bajada final' in orden[primero + 4], orden
    # con movimiento reducido: todos a la vez y quietos
    s.limpio('secuencia transbordo'); s.cerrar()
    s = V.sesion(nav, **MOVIL, reduced_motion='reduce')
    p = s.abrir()
    V.planear(p, 'transbordos'); p.wait_for_timeout(3000)
    assert len(p.evaluate(JS_CARTELES)) >= 5, 'con movimiento reducido se ven todos a la vez'
    s.limpio('secuencia reducida'); s.cerrar()


@prueba
def la_tarjeta_mejor_opcion_cabe_en_todos_los_anchos_con_nombres_larguisimos_y_sin_desbordes(nav):
    largo = 'Universidad Santo Tomás de Villavicencio hacia los Capachos y más allá'
    for w, h in ((320, 568), (360, 740), (375, 812), (430, 932), (768, 1024)):
        s = V.sesion(nav, viewport={'width': w, 'height': h}, is_mobile=True, has_touch=True)
        p = s.abrir()
        r = p.evaluate("""(largo) => {
            const cont = document.getElementById('mejorOpcion'); cont.hidden = false;
            const buses = (n) => [{ nombre: 'el bus ' + n, color: '#1565C0' }];
            const op = (id, nombres, extra) => Object.assign({ id, buses: nombres.map((n) => ({ nombre: 'el bus ' + n, color: '#1565C0' })), minutos: 143, subeM: 1290, caminaM: 4580, busKm: 12.5, transbordo: nombres.length > 1,
                etiquetas: ['Primer bus más cercano', 'Menor caminata total'], recomendada: id === 'a', sentidoContrario: false, caminarMejor: false }, extra || {});
            const ctl = window.MejorOpcion.montar(cont, { opciones: [op('a', ['Galán', largo]), op('b', ['Porfía'])], alElegir() {}, alVerTodas() {} });
            const card = cont.querySelector('.mo-card'), c = card.getBoundingClientRect(), malos = [];
            card.querySelectorAll('*').forEach((e) => { const r = e.getBoundingClientRect(); if (r.width && (r.right > c.right + 0.5 || r.left < c.left - 0.5)) malos.push(e.className + ' ' + Math.round(r.right - c.right)); });
            const out = { malos, ancho: document.documentElement.scrollWidth <= innerWidth + 1, tarjeta: Math.round(c.width), alto: Math.round(c.height), pastillas: [...card.querySelectorAll('.mo-pastilla')].map((e) => e.getBoundingClientRect().width) };
            ctl.destruir(); cont.hidden = true; return out;
        }""", largo)
        assert not r['malos'] and r['ancho'], f'{w}x{h}: nada se sale de la tarjeta: {r}'
        s.limpio(f'tarjeta {w}x{h}'); s.cerrar()


def main():
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    fallos = []
    with sync_playwright() as pw:
        nav = B.navegador(pw)
        print('Navegador:', nav.browser_type.name, nav.version, '| URL:', B.URL)
        for f in PRUEBAS:
            if filtro and filtro not in f.__name__:
                continue
            try:
                f(nav)
                print('OK    ', f.__name__)
            except Exception as e:  # noqa: BLE001
                fallos.append(f.__name__)
                print('FALLA ', f.__name__, '|', str(e)[:300].replace('\n', ' '))
                traceback.print_exc()
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas del menú 4.17; fallos: {len(fallos)} {fallos}')
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
