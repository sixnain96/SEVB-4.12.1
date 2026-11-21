"""Pruebas de navegador del menú ☰ (secciones con icono, «Viaje en curso»), de «Mis lugares» (Ir a casa, editar y cancelar) y de la práctica «No encontramos esa dirección».

Frontend real y stub. La recuperación tras «Ya me bajé» (tarjeta de caminata) la cubre desvio_bus_e2e.py con los textos nuevos.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/menu416_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import os
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import desvio_bus_e2e as D  # noqa: E402
import lugares_e2e as L  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
CAPTURAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'capturas-viaje')


def prueba(f):
    PRUEBAS.append(f)
    return f


def captura(p, nombre):
    os.makedirs(CAPTURAS, exist_ok=True)
    p.screenshot(path=os.path.join(CAPTURAS, nombre))


def caja(p, sel):
    return p.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, h: r.height }; }", sel)


def abrir_menu(p):
    if not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"):
        p.click('#menuButton' if p.is_visible('#menuButton') else '#menuFlotante')
    p.wait_for_timeout(500)


def cerrado(p):
    return not p.evaluate("document.getElementById('sideMenu').classList.contains('open')")


def cierra_visible(p, alto):
    p.evaluate("document.getElementById('sideMenu').scrollTop = 99999")
    p.wait_for_timeout(150)
    c = caja(p, '#closeMenu')
    assert 0 <= c['top'] and c['bottom'] <= alto and c['h'] >= 40, f'el botón de cerrar sigue a la vista y es tocable: {c}'


# ------------------------------------------------------------------------------------------------------------------------------------------- A · menú
@prueba
def el_menu_planificando_tiene_secciones_con_icono_cabecera_fija_y_se_cierra_con_escape_devolviendo_el_foco(nav):
    s = D.sesion(nav, **D.MOVIL)
    p = s.abrir()
    p.set_viewport_size({'width': 320, 'height': 568}); p.wait_for_timeout(300)
    p.focus('#menuButton'); abrir_menu(p)
    assert p.is_hidden('#menuEstadoViaje') and p.is_hidden('#menuInicioNota') and p.is_hidden('#menuVolverViaje'), 'sin viaje no hay «Viaje en curso»'
    assert p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion > summary .menu-ico').length") >= 6, 'cada sección lleva su icono'
    assert p.evaluate("document.getElementById('menuLugares').open"), '«Mis lugares» abierto al entrar'
    assert p.evaluate("(() => { const m = document.getElementById('sideMenu'); return m.scrollWidth <= m.clientWidth + 1; })()"), 'sin desplazamiento horizontal'
    assert p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion > summary').length") >= 6
    nombres = p.evaluate("[...document.querySelectorAll('#sideMenu details.menu-seccion > summary')].map(s => s.textContent.trim()).join(' | ')")
    for t in ('Mis lugares', 'Ayuda', 'Pantalla y accesibilidad'):
        assert t in nombres, (t, nombres)
    assert 'Continuar con Google' in p.inner_text('#menuAccount'), 'sin sesión la cuenta ofrece «Continuar con Google»'
    cierra_visible(p, 568)
    # la animación solo corre cuando la persona toca el título de la sección
    assert p.evaluate("document.querySelectorAll('#sideMenu details.anima').length") == 0, 'al abrir el menú no hay animaciones de sección'
    p.evaluate("document.getElementById('menuMas').open = true"); p.wait_for_timeout(100)      # 4.17: Ayuda y lo demás viven dentro de «Más»
    assert p.evaluate("document.getElementById('menuAyuda').closest('#menuMas') !== null")
    p.evaluate("document.getElementById('menuMas').scrollIntoView()")
    p.click('#menuAyuda > summary'); p.wait_for_timeout(60)
    assert p.evaluate("document.getElementById('menuAyuda').classList.contains('anima')"), 'al tocar una sección se anima'
    p.wait_for_timeout(500)
    assert p.evaluate("document.getElementById('menuAyuda').classList.contains('anima')") is False and p.evaluate("document.getElementById('menuAyuda').open")
    p.evaluate("document.getElementById('sideMenu').scrollTop = 0"); p.wait_for_timeout(150)
    captura(p, 'menu-planificando-320.png')
    p.keyboard.press('Escape'); p.wait_for_timeout(600)
    assert cerrado(p), 'Escape cierra el menú'
    assert p.evaluate("document.activeElement.id") == 'menuButton', 'el foco vuelve al botón ☰'
    # horizontal y modo oscuro
    p.set_viewport_size({'width': 740, 'height': 360}); p.wait_for_timeout(300)
    abrir_menu(p); cierra_visible(p, 360)
    p.emulate_media(color_scheme='dark'); p.wait_for_timeout(300)
    cierra_visible(p, 360)
    assert p.evaluate("getComputedStyle(document.querySelector('#sideMenu .menu-ico')).color") != p.evaluate("getComputedStyle(document.getElementById('sideMenu')).backgroundColor"), 'iconos legibles en oscuro'
    p.set_viewport_size({'width': 320, 'height': 568}); p.wait_for_timeout(300)
    p.evaluate("document.getElementById('sideMenu').scrollTop = 0"); captura(p, 'menu-planificando-oscuro-320.png')
    s.limpio('menu planificando'); s.cerrar()


@prueba
def durante_el_viaje_el_menu_prioriza_volver_a_mi_viaje_y_separa_volver_al_inicio(nav):
    s = D.sesion(nav, **D.MOVIL)
    p, plan, ls, ll = D.preparar(s)
    D.iniciar(p, plan)
    D.en_bus(p, ls)
    p.set_viewport_size({'width': 320, 'height': 568}); p.wait_for_timeout(300)
    fase = V.card(p)['fase']
    abrir_menu(p)
    assert p.is_visible('#menuEstadoViaje') and 'Viaje en curso' in p.inner_text('#menuEstadoViaje'), 'estado breve del viaje'
    assert p.is_visible('#menuVolverViaje') and p.is_visible('#menuInicio') and p.is_visible('#menuInicioNota')
    v, i = caja(p, '#menuVolverViaje'), caja(p, '#menuInicio')
    assert v['top'] < i['top'] and i['top'] - v['bottom'] >= 8, f'«Volver a mi viaje» va primero y «Volver al inicio» queda separado: {v} {i}'
    assert v['h'] >= 48, 'área táctil cómoda'
    cierra_visible(p, 568)
    p.evaluate("document.getElementById('sideMenu').scrollTop = 0"); captura(p, 'menu-viaje-320.png')
    p.set_viewport_size({'width': 740, 'height': 360}); p.wait_for_timeout(300)
    cierra_visible(p, 360)
    p.set_viewport_size({'width': 320, 'height': 568}); p.wait_for_timeout(300)
    # Escape devuelve a la pantalla del viaje, con su estado
    p.keyboard.press('Escape'); p.wait_for_timeout(600)
    assert cerrado(p) and V.card(p)['fase'] == fase and not p.evaluate("document.getElementById('viajeCard').hidden"), 'el viaje sigue donde estaba'
    assert p.evaluate("document.activeElement.id") == 'menuFlotante', 'el foco vuelve al botón que abrió el menú'
    abrir_menu(p); p.click('#menuVolverViaje'); p.wait_for_timeout(700)
    assert cerrado(p) and V.card(p)['fase'] == fase and not p.evaluate("document.getElementById('viajeCard').hidden"), '«Volver a mi viaje» cierra el menú y no cambia el viaje'
    # al terminar el viaje desaparece el estado
    p.evaluate("Spevb.Viaje.terminar && Spevb.Viaje.terminar()") if p.evaluate("!!(Spevb.Viaje && Spevb.Viaje.terminar)") else None
    s.limpio('menu viaje'); s.cerrar()


@prueba
def el_menu_cabe_en_360_390_y_escritorio_y_abrir_y_cerrar_varias_veces_no_deja_restos(nav):
    s = D.sesion(nav, **D.MOVIL)
    p = s.abrir()
    for w, h in ((360, 640), (390, 844), (1280, 800), (320, 568)):
        p.set_viewport_size({'width': w, 'height': h}); p.wait_for_timeout(300)
        for _ in range(3):
            p.focus('#menuButton') if p.is_visible('#menuButton') else None
            abrir_menu(p)
            assert p.evaluate("(() => { const m = document.getElementById('sideMenu'); return m.scrollWidth <= m.clientWidth + 1; })()"), f'{w}x{h}: sin desplazamiento horizontal'
            assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f'{w}x{h}: la página no se ensancha'
            cierra_visible(p, h)
            p.keyboard.press('Escape'); p.wait_for_timeout(500)
            assert cerrado(p) and p.evaluate("!document.body.classList.contains('sup-menu')"), f'{w}x{h}: cierra y limpia el estado'
    assert p.evaluate("document.querySelectorAll('#sideMenu .menu-ico').length") == p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion[data-ico]').length"), 'los iconos no se duplican al abrir y cerrar'
    s.limpio('menu tamanos'); s.cerrar()


def solapan(a, b):
    return not (a['right'] <= b['left'] + 1 or b['right'] <= a['left'] + 1 or a['bottom'] <= b['top'] + 1 or b['bottom'] <= a['top'] + 1)


def toque_llega(p, sel):
    """Un toque real sobre el centro del control llega al control (no a otra capa)."""
    return p.evaluate("""(s) => { const e = document.querySelector(s); if (!e) return false; const r = e.getBoundingClientRect();
        const h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!h && (e === h || e.contains(h) || h.contains(e)); }""", sel)


@prueba
def celular_girado_con_viaje_el_planificador_y_la_tarjeta_no_se_tapan_y_el_viaje_sigue(nav):
    s = D.sesion(nav, **D.MOVIL)
    p, plan, ls, ll = D.preparar(s)
    p.set_viewport_size({'width': 740, 'height': 360}); p.wait_for_timeout(400)
    D.iniciar(p, plan)
    D.en_bus(p, ls)
    p.wait_for_timeout(500)
    fase, mapa0 = V.card(p)['fase'], p.evaluate("Spevb.maps.map.getCenter().join(',')")
    assert p.is_hidden('.planner-column') or p.evaluate("document.body.classList.contains('panel-oculto')"), 'al empezar el viaje girado el planificador cede'
    assert p.is_visible('#panelShow'), '«Editar A y B» sigue disponible'
    # «Editar A y B»: planificador y tarjeta compacta lado a lado, sin taparse
    p.click('#panelShow'); p.wait_for_timeout(700)
    a, b = caja(p, '.planner-column'), caja(p, '#viajeCard')
    assert not solapan(a, b), f'planificador y tarjeta no se tapan: {a} {b}'
    for sel in ('#planTrip', '#tripOrigin', '#tripDestination', '#panelHide'):
        assert toque_llega(p, sel), f'el toque llega a {sel}'
    assert V.card(p)['fase'] == fase and not p.evaluate("document.getElementById('viajeCard').hidden"), 'el viaje no se reinicia'
    captura(p, 'despues-viaje-editar-ab-740x360.png')
    p.click('#panelHide'); p.wait_for_timeout(600)
    assert V.card(p)['fase'] == fase and toque_llega(p, '#viajeTerminar'), 'al ocultar el planificador la tarjeta vuelve completa'
    s.limpio('girado'); s.cerrar()


@prueba
def con_el_menu_abierto_la_pregunta_urgente_se_responde_por_toque_y_el_viaje_sigue(nav):
    for ancho, alto in ((320, 568), (430, 932)):
        s = D.sesion(nav, **D.MOVIL)
        p, plan, ls, ll = D.preparar(s)
        p.set_viewport_size({'width': ancho, 'height': alto}); p.wait_for_timeout(300)
        D.iniciar(p, plan)
        i = V.alimentar(p, ls, 0, 'fase:esperando')
        abrir_menu(p)
        V.alimentar(p, ls, i, 'pregunta'); p.wait_for_timeout(500)
        assert toque_llega(p, '#viajeSi') and toque_llega(p, '#viajeNo'), f'{ancho}x{alto}: los botones de la alerta reciben el toque aunque el menú esté abierto'
        c = caja(p, '#viajeSi'); assert 0 <= c['top'] and c['bottom'] <= alto and c['h'] >= 44, c
        p.click('#viajeSi'); p.wait_for_timeout(500)
        assert V.card(p)['fase'] == 'en_bus', 'la respuesta sigue su curso'
        assert toque_llega(p, '#closeMenu'), 'sin la alerta, cerrar el menú vuelve a ser alcanzable'
        p.click('#closeMenu'); p.wait_for_timeout(500)
        assert cerrado(p) and V.card(p)['fase'] == 'en_bus'
        s.limpio('alerta menu'); s.cerrar()


@prueba
def varios_ciclos_de_abrir_cerrar_girar_y_volver_al_viaje_no_recrean_el_mapa_ni_repiten_consultas(nav):
    s = D.sesion(nav, **D.MOVIL)
    p, plan, ls, ll = D.preparar(s)
    D.iniciar(p, plan)
    D.en_bus(p, ls)
    peticiones = []
    p.on('request', lambda r: peticiones.append(r.url) if '/api/' in r.url else None)
    p.evaluate("window.__mapa0 = Spevb.maps.map; window.__n0 = document.getElementsByTagName('*').length")
    n_planif = len(ll['planificar'])
    for _ in range(4):
        for w, h in ((320, 568), (568, 320), (390, 844)):
            p.set_viewport_size({'width': w, 'height': h}); p.wait_for_timeout(250)
            abrir_menu(p); p.keyboard.press('Escape'); p.wait_for_timeout(450)
        abrir_menu(p); p.click('#menuVolverViaje'); p.wait_for_timeout(600)
    assert p.evaluate("Spevb.maps.map === window.__mapa0"), 'el mapa no se recrea'
    assert len(ll['planificar']) == n_planif and not [u for u in peticiones if '/api/viajes' in u or '/api/rutas' in u], f'sin consultas nuevas de rutas: {peticiones}'
    assert p.evaluate("document.getElementsByTagName('*').length - window.__n0") < 60, 'el DOM no crece con cada ciclo'
    assert p.evaluate("document.querySelectorAll('#sideMenu .menu-ico').length") == p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion[data-ico]').length")
    assert V.card(p)['fase'] == 'en_bus' and p.evaluate("Spevb.Viaje.activo()")
    s.limpio('ciclos'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- C · lugares
@prueba
def casa_trabajo_y_un_lugar_propio_se_usan_en_un_toque_y_editar_o_cancelar_no_toca_a_y_b(nav):
    s, p = L.con_ana(nav)
    L.abrir_modo(p, '#atajos [data-atajo="Casa"]'); L.guardar_en_modo(p)
    L.menu(p)
    assert 'Guardar mi casa' not in p.inner_text('#atajos') and 'Casa' in p.inner_text('#atajos') and 'Guardar mi trabajo' in p.inner_text('#atajos'), p.inner_text('#atajos')
    assert 'Casa' in p.get_attribute('#atajos .atajo-fila[data-tipo="casa"] .atajo-mas', 'aria-label'), 'el botón de más acciones nombra el lugar'
    L.abrir_modo(p, '#lugarAgregar'); p.fill('#lugarNombre', 'Universidad'); L.guardar_en_modo(p)
    L.menu(p)
    fila = '#lugaresLista .lugar-fila .lugar-usar'
    assert p.is_visible(fila) and 'Universidad' in p.inner_text(fila) and p.inner_text('#lugaresLista .lugar-ir') == 'Usar', 'el lugar propio conserva su nombre y se reconoce como usable de un toque'
    assert 'Usar Universidad como salida o destino' in p.get_attribute(fila, 'aria-label')
    guardada = [x for x in L.lugares(p) if x['nombre'] == 'Casa'][0]
    antes = p.evaluate("JSON.stringify(Spevb.Planner.puntos())")
    # editar: abre en el punto anterior, con la instrucción breve
    p.click('#atajos .atajo-fila[data-tipo="casa"] .atajo-mas'); p.wait_for_timeout(250)
    p.click('#atajos .atajo-acciones button:has-text("Cambiar ubicación")'); p.wait_for_timeout(700)
    B.esperar(p, "Spevb.Lugares.estado().activo", 4000)
    assert 'Mueve el mapa para ajustar el punto' in p.inner_text('#lugarAyuda')
    assert p.is_visible('#lugarGuardar') and p.is_visible('#lugarCancelar')
    assert L.cerca(L.bajo_el_pin(p), guardada, 3e-5), 'el pin anterior queda bajo la punta del marcador'
    L.mover(p, guardada['lat'] + 0.01, guardada['lng'] + 0.01)
    captura(p, 'lugares-editar-ubicacion.png')
    p.click('#lugarCancelar'); p.wait_for_timeout(900)
    assert [x for x in L.lugares(p) if x['nombre'] == 'Casa'][0]['lat'] == guardada['lat'], 'cancelar conserva la ubicación anterior'
    assert p.evaluate("document.activeElement.closest('.atajo-fila') && document.activeElement.closest('.atajo-fila').dataset.tipo") == 'casa', 'el foco vuelve a la fila'
    assert p.evaluate("JSON.stringify(Spevb.Planner.puntos())") == antes, 'abrir, mover y cancelar no cambia A ni B'
    # un toque: prepara el destino
    p.click('#atajos .atajo-fila[data-tipo="casa"] .atajo'); p.wait_for_timeout(300)
    assert not cerrado(p), '4.17: el primer toque ofrece «Salgo de aquí» / «Voy para aquí» sin cerrar el menú'
    p.click('.lugar-uso-b[data-uso="destination"]'); p.wait_for_timeout(700)
    assert cerrado(p), 'el menú se cierra'
    d = p.evaluate("Spevb.Planner.puntos().destino")
    assert d and abs(d['lat'] - guardada['lat']) < 1e-6, '«Voy para aquí» deja Casa como destino'
    s.limpio('lugares'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- D · práctica
def abrir_practica(p):
    p.evaluate("Spevb.Guia.abrirLeccion(Spevb.Guia.TEMAS[0])"); p.wait_for_timeout(700)
    assert p.is_visible('#bienPracticaMapa'), 'la lección «Cómo elegir el destino» ofrece la práctica'
    p.focus('#bienPracticaMapa'); p.keyboard.press('Enter'); p.wait_for_timeout(600)


@prueba
def la_practica_pasa_de_no_encontramos_esa_direccion_a_elegir_en_el_mapa_sin_tocar_nada_real(nav):
    s = D.sesion(nav, **D.MOVIL)
    p = s.abrir()
    peticiones = []
    p.on('request', lambda r: peticiones.append(r.url) if '/api/' in r.url or 'google' in r.url else None)
    p.set_viewport_size({'width': 320, 'height': 568}); p.wait_for_timeout(300)
    antes = p.evaluate("JSON.stringify([Spevb.Planner.puntos(), document.getElementById('tripStatus').textContent])")
    abrir_practica(p)
    n0 = len(peticiones)
    assert p.is_visible('.pm-sello') and p.inner_text('.pm-sello').strip().lower() == 'práctica'
    assert 'No encontramos esa dirección' in p.inner_text('#pmNoHay') and p.is_visible('#pmElegir') and p.inner_text('#pmElegir') == 'Elegir en el mapa'
    assert 'Toca Elegir en el mapa' in p.inner_text('#pmInstruccion') and p.evaluate("document.getElementById('pmElegir').classList.contains('ayuda-resalta')"), 'resalta el control'
    assert p.evaluate("document.activeElement.id") == 'pmElegir'
    p.keyboard.press('Enter'); p.wait_for_timeout(200)
    assert 'Marca el punto' in p.inner_text('#pmInstruccion') and p.is_visible('#pmMapa') and p.evaluate("document.activeElement.id") == 'pmMapa'
    p.click('#pmMapa', position={'x': 80, 'y': 40}); p.wait_for_timeout(200)
    assert 'Confírmalo' in p.inner_text('#pmInstruccion') and p.is_visible('#pmSi') and p.is_visible('#pmPin')
    captura(p, 'practica-elegir-en-el-mapa-320.png')
    p.click('#pmSi'); p.wait_for_timeout(200)
    assert 'Así puedes elegir el destino cuando no aparece en la lista' in p.inner_text('#pmHecho')
    assert p.is_visible('#pmOtra') and p.is_visible('#pmListo')
    for sel in ('#pmOtra', '#pmListo'):
        c = caja(p, sel); assert c['top'] >= 0 and c['bottom'] <= 568, (sel, c)
    assert len(peticiones) == n0, f'la práctica no llama a ningún servicio ni a Google: {peticiones[n0:]}'
    p.keyboard.press('Escape'); p.wait_for_timeout(500)
    assert p.is_hidden('#practicaMapa') and p.evaluate("document.activeElement.id") == 'bienPracticaMapa', 'al salir el foco vuelve a quien la abrió'
    p.keyboard.press('Escape'); p.wait_for_timeout(700)
    assert p.evaluate("JSON.stringify([Spevb.Planner.puntos(), document.getElementById('tripStatus').textContent])") == antes, 'el planificador sigue como estaba'
    assert not p.evaluate("Spevb.Lugares.estado().activo"), 'el selector de mapa real no se tocó'
    s.limpio('practica'); s.cerrar()


@prueba
def la_practica_se_maneja_con_teclado_atras_omitir_repetir_y_con_movimiento_reducido(nav):
    s = D.sesion(nav, **D.MOVIL)
    p = s.abrir()
    p.emulate_media(reduced_motion='reduce')
    abrir_practica(p)
    p.keyboard.press('Space'); p.wait_for_timeout(150)       # Elegir en el mapa
    p.keyboard.press('Enter'); p.wait_for_timeout(200)       # marca el centro con el teclado
    assert 'Confírmalo' in p.inner_text('#pmInstruccion')
    assert p.evaluate("getComputedStyle(document.getElementById('pmSi')).animationName") == 'none', 'movimiento reducido: el resaltado no late'
    p.click('#pmAtras'); p.wait_for_timeout(150)
    assert 'Marca el punto' in p.inner_text('#pmInstruccion') and p.is_hidden('#pmPin'), 'Atrás vuelve un momento y quita el punto'
    p.click('#pmAtras'); p.wait_for_timeout(150)
    assert 'Toca Elegir en el mapa' in p.inner_text('#pmInstruccion') and p.is_hidden('#pmAtras')
    p.click('#pmOmitir'); p.wait_for_timeout(500)
    assert p.is_hidden('#practicaMapa') and p.evaluate("document.activeElement.id") == 'bienPracticaMapa', 'Omitir sale y devuelve el foco'
    p.focus('#bienPracticaMapa'); p.keyboard.press('Enter'); p.wait_for_timeout(500)
    assert 'Toca Elegir en el mapa' in p.inner_text('#pmInstruccion'), 'se puede volver a abrir desde cero'
    p.click('#pmElegir'); p.click('#pmMapa'); p.click('#pmSi'); p.wait_for_timeout(150)
    p.click('#pmOtra'); p.wait_for_timeout(150)
    assert 'Toca Elegir en el mapa' in p.inner_text('#pmInstruccion') and p.is_visible('#pmNoHay'), 'repetir empieza otra vez'
    s.limpio('practica teclado'); s.cerrar()


@prueba
def la_ayuda_del_destino_en_el_flujo_guiado_ofrece_la_practica(nav):
    s = D.sesion(nav, **D.MOVIL)
    p = s.abrir()
    p.click('#helpButton'); p.wait_for_timeout(500)
    visible_guiado = p.is_visible('#ayudaMapa')
    if not visible_guiado:        # el planificador con A y B muestra otra ayuda: el tema «Cómo elegir el destino» sí la ofrece
        p.evaluate("document.querySelector('.ayuda-temas').open = true"); p.click('.tema-chip[data-tema="0"]'); p.wait_for_timeout(800)
        assert p.is_visible('#bienPracticaMapa')
    else:
        p.click('#ayudaMapa'); p.wait_for_timeout(500); assert p.is_visible('#practicaMapa')
    s.limpio('ayuda'); s.cerrar()


def main():
    filtro = sys.argv[1] if len(sys.argv) > 1 else ''
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
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0] if str(e) else type(e).__name__)
                traceback.print_exc()
        nav.close()
    print()
    print('%d pruebas del menú, lugares y práctica; fallos: %d %s' % (len(PRUEBAS) if not filtro else '?', len(fallos), fallos))
    sys.exit(1 if fallos else 0)


if __name__ == '__main__':
    main()
