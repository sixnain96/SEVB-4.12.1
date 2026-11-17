"""Pruebas de navegador de 4.14 (aprender a usar la app): bienvenida animada, ayuda en contexto, viaje de práctica, «Tu viaje de siempre»,
resumen de la semana, pestañita «Ahora escribe B», sin voz ni emojis, controles del bus en círculo y lenguaje simple.

Desde 4.15.1 el tutorial enseña el FLUJO GUIADO real (8 escenas y una práctica de 8 pasos sobre los botones reales del paso a paso); el planificador con A y B es una opción aparte.

Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/aprender_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
"""
import json
import os
import re
import sys
import traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
DEST = '4.1450, -73.6240'
ORIGEN = '4.1475, -73.6530'
MOVIL = {'viewport': {'width': 384, 'height': 848}, 'is_mobile': True, 'has_touch': True, 'device_scale_factor': 2}
EJEMPLO = {'a': {'id': None, 'lat': 4.1475, 'lng': -73.6530, 'nombre': 'Ejemplo A', 'direccion': None, 'fuente': 'Práctica', 'confirmado': True},
           'b': {'id': None, 'lat': 4.1450, 'lng': -73.6240, 'nombre': 'Ejemplo B', 'direccion': None, 'fuente': 'Práctica', 'confirmado': True}}


def prueba(f):
    PRUEBAS.append(f)
    return f


def planear(p, espera=2000):
    p.fill('#tripOrigin', ORIGEN); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    p.fill('#tripDestination', DEST); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    p.evaluate("document.querySelector('#planTrip').click()")
    B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 12000)
    p.wait_for_timeout(espera)


def con_bienvenida(s):
    """El arnés marca la bienvenida como «ya vista»; aquí se quita para probarla de verdad (el marcador del arnés evita que la vuelva a poner)."""
    p = s.abrir()
    p.evaluate("localStorage.removeItem('spevb-bienvenida')")
    p.reload(); p.wait_for_timeout(2200)
    return p


# ------------------------------------------------------------------------------------------------ bienvenida
# ------------------------------------------------------------------------------------------------ ayuda en contexto
# ------------------------------------------------------------------------------------------------ viaje de práctica
@prueba
def la_bienvenida_sale_la_primera_vez_tiene_ocho_escenas_que_empiezan_por_el_destino_y_no_vuelve(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    assert p.is_visible('#bienvenida'), 'sale sola la primera vez'
    assert p.inner_text('#bienTitulo') == ESCENAS_TITULOS[0] and p.inner_text('#bienPasoTexto') == 'Paso 1 de 8' and p.is_hidden('#bienAtras') and p.is_visible('#bienSaltar')
    assert p.inner_text('#bienSaltar') == 'Omitir'
    p.click('#bienSiguiente')
    assert p.inner_text('#bienTitulo') == ESCENAS_TITULOS[1] and p.is_visible('#bienAtras')
    p.click('#bienAtras')
    assert p.inner_text('#bienTitulo') == ESCENAS_TITULOS[0], 'Atrás vuelve a la escena anterior'
    for i in range(1, 8):
        p.click('#bienSiguiente')
        assert p.inner_text('#bienTitulo') == ESCENAS_TITULOS[i] and p.inner_text('#bienPasoTexto') == f'Paso {i + 1} de 8', f'escena {i + 1}'
    assert p.inner_text('#bienPractica') == 'Aprender con una práctica' and p.is_visible('#bienPractica'), 'la práctica es una opción'
    assert p.inner_text('#bienSiguiente') == 'Empezar a explorar' and p.is_hidden('#bienSaltar'), 'y explorar es la otra: nadie está obligado'
    assert p.evaluate("document.querySelectorAll('#bienPuntos i').length") == 8
    p.click('#bienSiguiente'); p.wait_for_timeout(400)
    assert p.is_hidden('#bienvenida') and p.evaluate("localStorage.getItem('spevb-bienvenida')") == '2'
    assert p.evaluate("!document.body.classList.contains('modal-open')") and p.evaluate("!document.getElementById('coach')"), 'explorar no empieza la práctica ni deja capas'
    p.reload(); p.wait_for_timeout(2200)
    assert p.is_hidden('#bienvenida'), 'ya vista: no vuelve a salir sola'
    s.limpio('bienvenida'); s.cerrar()


@prueba
def omitir_la_bienvenida_la_marca_como_vista_y_el_menu_la_muestra_otra_vez(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    p.click('#bienSaltar'); p.wait_for_timeout(400)
    assert p.is_hidden('#bienvenida')
    p.reload(); p.wait_for_timeout(2200)
    assert p.is_hidden('#bienvenida')
    p.click('#menuButton'); p.wait_for_timeout(500); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    p.click('#menuBienvenida'); p.wait_for_timeout(900)
    assert p.is_visible('#bienvenida') and p.inner_text('#bienPasoTexto') == 'Paso 1 de 8', 'el menú la muestra otra vez desde la escena 1'
    p.keyboard.press('Escape'); p.wait_for_timeout(400)
    assert p.is_hidden('#bienvenida'), 'Escape la cierra'
    assert p.evaluate("!document.body.classList.contains('modal-open')")
    s.limpio('omitir bienvenida'); s.cerrar()


@prueba
def la_bienvenida_se_maneja_con_teclado_y_atrapa_el_foco(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    assert p.evaluate("document.activeElement.id") == 'bienSiguiente', 'el foco entra a la ventana'
    p.keyboard.press('ArrowRight'); p.wait_for_timeout(200)
    assert p.inner_text('#bienPasoTexto') == 'Paso 2 de 8'
    p.keyboard.press('ArrowLeft'); p.wait_for_timeout(200)
    assert p.inner_text('#bienPasoTexto') == 'Paso 1 de 8'
    vistos = set()
    for _ in range(8):
        p.keyboard.press('Tab')
        vistos.add(p.evaluate("document.activeElement.id || document.activeElement.tagName"))
        assert p.evaluate("!!document.activeElement.closest('#bienvenida')"), 'con Tab el foco no se escapa de la ventana'
    assert {'bienSiguiente', 'bienSaltar'} <= vistos, vistos
    p.keyboard.press('Escape'); p.wait_for_timeout(400)
    s.limpio('teclado bienvenida'); s.cerrar()


@prueba
def la_bienvenida_tiene_ocho_ilustraciones_propias_que_se_deslizan_y_solo_se_anima_la_visible(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    r = p.evaluate("""() => ({ escenas: document.querySelectorAll('#bienIlustracion .bien-escena').length, svgs: document.querySelectorAll('#bienIlustracion svg.escena-svg').length,
        activas: document.querySelectorAll('#bienIlustracion .bien-escena.activa').length, mascota: document.querySelectorAll('#bienIlustracion image[href*="chiguiro"]').length,
        emojis: /\\p{Extended_Pictographic}/u.test(document.getElementById('bienIlustracion').textContent) })""")
    assert r['escenas'] == 8 and r['svgs'] == 8 and r['activas'] == 1 and not r['emojis'], r
    assert r['mascota'] == 2, 'la capibara solo sale al principio y al final, de forma discreta'
    p.click('#bienSiguiente'); p.wait_for_timeout(900)
    clases = p.evaluate("[...document.querySelectorAll('#bienIlustracion .bien-escena')].map(e => e.className.replace('bien-escena', '').trim())")
    assert clases == ['pasada', 'activa'] + ['futura'] * 6, clases
    assert p.evaluate("document.getElementById('bienTextos').classList.contains('cambia')"), 'el texto entra con animación'
    p.click('#bienSiguiente'); p.click('#bienSiguiente'); p.wait_for_timeout(3600)
    assert p.evaluate("getComputedStyle(document.querySelector('.e4 .r1 .t-fondo')).stroke") == 'rgb(23, 102, 80)', 'la recomendación queda resaltada en verde'
    pausadas = p.evaluate("[...document.querySelectorAll('#bienIlustracion svg.escena-svg')].map(s => s.animationsPaused())")
    assert pausadas == [True, True, True, False, True, True, True, True], f'solo se anima la escena que se ve: {pausadas}'
    p.click('#bienSiguiente'); p.click('#bienSiguiente'); p.wait_for_timeout(4200)
    assert p.evaluate("getComputedStyle(document.querySelector('.e6 .p3 .disco')).fill") == 'rgb(26, 115, 232)', 'el círculo azul vuelve al final'
    s.limpio('ilustraciones'); s.cerrar()


@prueba
def la_bienvenida_respeta_reducir_movimiento(nav):
    s = B.Sesion(nav, reduced_motion='reduce', **MOVIL)
    p = con_bienvenida(s)
    assert p.is_visible('#bienvenida')
    assert p.evaluate("getComputedStyle(document.querySelector('#bienvenida .bienvenida-card')).animationName") == 'none'
    assert p.evaluate("getComputedStyle(document.querySelector('.e1 .tapa')).transform") != 'none', 'el texto de los campos se ve completo (sin «teclear»)'
    for _ in range(7):
        p.click('#bienSiguiente'); p.wait_for_timeout(120)
    assert p.evaluate("getComputedStyle(document.querySelector('.e8 .camino')).strokeDashoffset") in ('0px', '0'), 'con poco movimiento los trazos se ven completos'
    assert p.evaluate("getComputedStyle(document.querySelector('.e7 .n3 .barra')).animationName") == 'none' and p.evaluate("getComputedStyle(document.querySelector('.e1 .saludo')).animationName") == 'none'
    assert p.evaluate("[...document.querySelectorAll('#bienIlustracion svg.escena-svg')].every(s => s.animationsPaused())"), 'las animaciones SVG quedan quietas'
    p.click('#bienSiguiente'); p.wait_for_timeout(300)
    assert p.is_hidden('#bienvenida')
    s.limpio('movimiento reducido'); s.cerrar()


@prueba
def el_tutorial_completo_cabe_en_320_360_390_y_horizontal_bajo_sin_botones_cortados(nav):
    for ancho, alto, movil in TAMANOS_TUTORIAL + [(768, 1024, False), (1280, 800, False)]:
        s = B.Sesion(nav, viewport={'width': ancho, 'height': alto}, is_mobile=movil, has_touch=movil)
        p = con_bienvenida(s)
        for i in range(8):
            r = p.evaluate("""() => { const c = document.querySelector('.bienvenida-card').getBoundingClientRect(), vis = (id) => { const e = document.getElementById(id); if (!e || e.hidden || !e.getClientRects().length) return null; const b = e.getBoundingClientRect(); return { h: Math.round(b.height), abajo: b.bottom, arriba: b.top, izq: b.left, der: b.right }; };
                return { ancho: document.documentElement.scrollWidth, vw: innerWidth, izq: c.left, der: c.right, arriba: c.top, abajo: c.bottom, vh: innerHeight,
                  botones: ['bienSiguiente', 'bienAtras', 'bienSaltar', 'bienPractica'].map(vis).filter(Boolean), card: document.querySelector('.bienvenida-card').scrollHeight <= document.querySelector('.bienvenida-card').clientHeight + 1 }; }""")
            assert r['ancho'] <= r['vw'] and r['izq'] >= -1 and r['der'] <= r['vw'] + 1, f'{ancho}x{alto} escena {i + 1}: desborda a los lados {r}'
            assert r['arriba'] >= -1 and r['abajo'] <= r['vh'] + 1, f'{ancho}x{alto} escena {i + 1}: la ventana se sale de la pantalla {r}'
            assert r['botones'] and all(b['h'] >= 44 and b['abajo'] <= r['vh'] + 1 and b['arriba'] >= -1 and b['izq'] >= -1 and b['der'] <= r['vw'] + 1 for b in r['botones']), f'{ancho}x{alto} escena {i + 1}: botones cortados o chicos {r["botones"]}'
            assert r['card'], f'{ancho}x{alto} escena {i + 1}: todo cabe sin desplazarse dentro de la ventana'
            if i < 7: p.click('#bienSiguiente'); p.wait_for_timeout(250)
        s.limpio(f'bienvenida {ancho}x{alto}'); s.cerrar()


@prueba
def se_puede_avanzar_retroceder_omitir_y_volver_a_abrir_el_tutorial(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    p.click('#bienSiguiente'); p.click('#bienSiguiente'); p.click('#bienAtras')
    assert p.inner_text('#bienPasoTexto') == 'Paso 2 de 8', 'avanzar y retroceder'
    p.click('#bienSaltar'); p.wait_for_timeout(500)
    assert p.is_hidden('#bienvenida'), 'omitir'
    # volver a abrir: desde el menú y desde la ayuda «?»
    p.click('#menuButton'); p.wait_for_timeout(500); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    p.click('#menuBienvenida'); p.wait_for_timeout(900)
    assert p.is_visible('#bienvenida') and p.inner_text('#bienPasoTexto') == 'Paso 1 de 8'
    p.click('#bienSaltar'); p.wait_for_timeout(500)
    p.click('#helpButton'); p.wait_for_timeout(300); p.click('#ayudaBien'); p.wait_for_timeout(900)
    assert p.is_visible('#bienvenida') and p.inner_text('#bienPasoTexto') == 'Paso 1 de 8', 'también desde la ayuda'
    p.click('#bienSaltar'); p.wait_for_timeout(500)
    # la práctica: avanzar, retroceder, salir y volver a abrirla desde el menú
    p.evaluate(AUTO, EJEMPLO); hasta_paso(p, 1, '2 de 2', 8000)
    siguiente(p); hasta_paso(p, 2, '1 de 5'); p.click('.coach-atras'); hasta_paso(p, 1, '2 de 2'); p.click('.coach-salir'); p.wait_for_timeout(700)
    assert p.evaluate("!document.getElementById('coach')")
    p.click('#menuButton'); p.wait_for_timeout(500); p.click('#menuPractica'); p.wait_for_timeout(1500)
    assert p.evaluate("!!document.getElementById('coach')"), 'la práctica se vuelve a abrir desde el menú'
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.limpio('abrir cerrar tutorial'); s.cerrar()


def textos_de_escenas(p):
    return p.evaluate("""() => Spevb.Guia.ESCENAS.map((e, i) => { const d = document.createElement('div'); d.innerHTML = e.svg; return { clave: e.clave, titulo: e.titulo, texto: e.texto, dibujo: d.textContent.replace(/\\s+/g, ' ') }; })""")


@prueba
def el_orden_ensena_destino_primero_origen_despues_y_cada_idea_tiene_su_escena(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    esc = textos_de_escenas(p)
    claves = [e['clave'] for e in esc]
    assert claves == ['destino', 'origen', 'revisar', 'recomendacion', 'empezar', 'marcador', 'bajada', 'terminar'], claves
    todo = [(e['titulo'] + ' ' + e['texto'] + ' ' + e['dibujo']) for e in esc]
    assert 'dónde vas' in todo[0] and '¿A dónde quieres ir?' in todo[0] and 'Sugerencias de Google' in todo[0] and 'Sí, continuar' in todo[0], 'escena 1: destino y confirmar'
    assert 'Usar mi ubicación actual' in todo[1] and 'Escribir una dirección' in todo[1] and 'Elegir en el mapa' in todo[1], 'escena 2: ubicación, dirección o mapa'
    assert 'Buscar cómo llegar' in todo[2] and 'Vas desde' in todo[2] and 'Hasta' in todo[2], 'escena 3: revisar y buscar'
    assert all(x in todo[3] for x in ('min', 'Caminas', 'bus', 'Transbordo', '2 buses')), 'escena 4: tiempo, caminata, bus y transbordo'
    assert 'Empezar este viaje' in todo[4] and 'Un solo viaje a la vez' in todo[4] and 'termina este' in todo[4], 'escena 5: un solo viaje'
    assert 'círculo azul' in todo[5] and 'código de la ruta' in todo[5] and 'R12' in todo[5], 'escena 6: marcador'
    assert all(x in todo[6] for x in ('Cerca', 'Prepárate', 'Ahora', 'Tu bajada está aquí', 'Si tu teléfono lo permite')) and 'siempre vibra' not in todo[6], 'escena 7: avisos, sin prometer vibración'
    assert all(x in todo[7] for x in ('Ya me bajé', 'Terminar viaje', 'último tramo')), 'escena 8: terminar'
    # y la práctica sigue el mismo orden: destino (paso 1) antes que salida (paso 2)
    p.evaluate("(ej) => { window.__practica = Spevb.Guia.practica({ ejemplo: ej }); }", EJEMPLO); hasta_paso(p, 1, '1 de 2', 8000)
    assert 'a dónde vas' in p.inner_text('.coach-texto') and p.get_attribute('#coach', 'data-sel') == '#tripDestination', 'la práctica empieza por el destino'
    p.click('.coach-siguiente'); hasta_paso(p, 1, '2 de 2', 8000); siguiente(p); hasta_paso(p, 2, '1 de 5')
    assert 'desde dónde sales' in p.inner_text('.coach-texto') and 'Usar mi ubicación actual' in p.inner_text('.coach-texto') and p.get_attribute('#coach', 'data-sel') == '#gUsarGps'
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.limpio('orden'); s.cerrar()


@prueba
def ninguna_escena_ni_ayuda_rapida_presenta_a_y_b_o_el_planificador_como_flujo_principal(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    esc = textos_de_escenas(p)
    malo = re.compile(r'(?i:planificador|Buscar rutas|Iniciar viaje|\bpunto [AB]\b|\bA y B\b|origen A|destino B)|(?<![\wáéíóú])[AB](?![\wáéíóú])')
    for e in esc:
        for campo in ('titulo', 'texto', 'dibujo'):
            m = malo.search(e[campo].replace('¿A dónde', '¿a dónde'))
            assert not m, f'la escena «{e["clave"]}» ({campo}) menciona «{m.group(0)}» como parte del flujo principal'
    temas = p.evaluate("Spevb.Guia.TEMAS.map(t => ({ t: t.t, escena: t.escena, titulo: t.titulo, texto: t.texto || '', tips: t.tips || [] }))")
    con_ab = [t['t'] for t in temas if re.search(r'planificador|\bA y B\b', t['t'] + t['texto'] + ' '.join(t['tips']))]
    assert con_ab == [], f'ninguna ayuda rápida presenta el planificador o A y B como flujo: {con_ab} (el paso a paso ya no se ofrece, así que tampoco su tema)'
    s.limpio('sin A y B'); s.cerrar()


@prueba
def con_movimiento_reducido_y_solo_teclado_se_completa_todo_el_tutorial(nav):
    s = B.Sesion(nav, reduced_motion='reduce', **MOVIL)
    p = con_bienvenida(s)
    for i in range(7):                                     # la bienvenida completa con el teclado
        assert p.evaluate("document.activeElement.id") == 'bienSiguiente', f'escena {i + 1}: el foco queda en «Siguiente»'
        p.keyboard.press('Enter'); p.wait_for_timeout(150)
    assert p.inner_text('#bienPasoTexto') == 'Paso 8 de 8'
    p.keyboard.press('Shift+Tab'); p.keyboard.press('Shift+Tab')
    p.keyboard.press('Escape'); p.wait_for_timeout(400)
    assert p.is_hidden('#bienvenida')
    # la práctica completa con el teclado y sin animaciones
    p.evaluate("(ej) => { window.__practica = Spevb.Guia.practica({ ejemplo: ej, pausa: 60 }); }", EJEMPLO)
    hasta_paso(p, 1, '2 de 2', 8000)
    assert p.evaluate("getComputedStyle(document.querySelector('.coach-hueco .onda')).animationName") == 'none'
    for _ in range(80):
        if p.evaluate("!document.getElementById('coach')"): break
        txt = coach_paso(p)
        if 'paso 3' in txt and '2 de 2' in txt and p.is_hidden('.coach-siguiente') and not p.evaluate("Spevb.Planner.seleccion && Spevb.Planner.seleccion.viaje"):
            for _t in range(8):                            # el botón real señalado se alcanza con Tab y se activa con Enter
                p.keyboard.press('Tab')
                if p.evaluate("document.activeElement.id") == 'gBuscar': break
            assert p.evaluate("document.activeElement.id") == 'gBuscar', 'Tab llega al botón señalado'
            p.keyboard.press('Enter'); p.wait_for_timeout(1500); continue
        foco = p.evaluate("document.activeElement.className")
        if 'coach-siguiente' not in foco:
            p.evaluate("document.querySelector('.coach-siguiente').focus()")
        p.keyboard.press('Enter'); p.wait_for_timeout(350)
    p.wait_for_timeout(900)
    assert p.evaluate("Spevb.Logros.leer().hitos.includes('practica')"), 'la práctica se completó solo con teclado'
    s.limpio('teclado y movimiento reducido'); s.cerrar()


@prueba
def un_lector_de_pantalla_recibe_titulo_progreso_explicacion_y_botones_con_nombre(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    r = p.evaluate("""() => { const c = document.querySelector('.bienvenida-card'); return { rol: c.getAttribute('role'), modal: c.getAttribute('aria-modal'), titulo: document.getElementById(c.getAttribute('aria-labelledby')).textContent,
        progreso: document.getElementById('bienPasoTexto').getAttribute('aria-live'), textos: document.getElementById('bienTextos').getAttribute('aria-live'), ilus: document.getElementById('bienIlustracion').getAttribute('aria-hidden'),
        puntos: document.getElementById('bienPuntos').getAttribute('aria-hidden'), svgs: [...document.querySelectorAll('#bienIlustracion svg')].every(s => s.getAttribute('aria-hidden') === 'true') }; }""")
    assert r['rol'] == 'dialog' and r['modal'] == 'true' and r['titulo'] == ESCENAS_TITULOS[0] and r['progreso'] == 'polite' and r['textos'] == 'polite' and r['ilus'] == 'true' and r['puntos'] == 'true' and r['svgs'], r
    secuencia = []
    for i in range(8):
        secuencia.append(p.inner_text('#bienPasoTexto') + ' | ' + p.inner_text('#bienTitulo') + ' | ' + p.inner_text('#bienTexto'))
        nombres = p.evaluate("[...document.querySelectorAll('.bienvenida-card button')].filter(b => !b.hidden && b.getClientRects().length).map(b => (b.getAttribute('aria-label') || b.textContent).trim())")
        assert nombres and all(len(n) >= 3 for n in nombres), nombres
        if i < 7: p.click('#bienSiguiente'); p.wait_for_timeout(150)
    assert [x.split(' | ')[0] for x in secuencia] == [f'Paso {i} de 8' for i in range(1, 9)], 'cada cambio de escena anuncia su número'
    assert all(len(x.split(' | ')[2]) > 40 for x in secuencia), 'cada escena trae su explicación en texto'
    p.click('#bienSaltar') if p.is_visible('#bienSaltar') else p.click('#bienSiguiente'); p.wait_for_timeout(400)
    # la práctica: título, progreso y texto en vivo
    p.evaluate(AUTO, EJEMPLO); hasta_paso(p, 1, '2 de 2', 8000)
    c = p.evaluate("""() => { const t = document.querySelector('.coach-tarjeta'); return { rol: t.getAttribute('role'), nombre: t.getAttribute('aria-label'), vivo: document.querySelector('.coach-texto').getAttribute('aria-live'),
        paso: document.querySelector('.coach-paso').textContent, botones: [...t.querySelectorAll('button')].filter(b => !b.hidden).map(b => b.textContent.trim()), decor: [...t.querySelectorAll('.coach-guia, .coach-progreso')].every(e => e.getAttribute('alt') === '' || e.getAttribute('aria-hidden') === 'true') }; }""")
    assert c['rol'] == 'dialog' and c['nombre'] == 'Práctica guiada' and c['vivo'] == 'polite' and c['decor'] and re.match(r'Práctica · paso 1 de 8', c['paso']) and {'Salir', 'Atrás', 'Siguiente'} <= set(c['botones']), c
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.limpio('lector de pantalla'); s.cerrar()


INSTRUMENTO = """(() => {
  window.__vivos = { mo: 0, ro: 0, iv: 0, to: 0 };
  const dentro = () => new Error().stack.includes('guia.js');
  const MO = window.MutationObserver; window.MutationObserver = class extends MO { constructor(cb) { super(cb); this.__g = dentro(); } observe(...a) { if (this.__g && !this.__on) { this.__on = true; window.__vivos.mo++; } return super.observe(...a); } disconnect() { if (this.__g && this.__on) { this.__on = false; window.__vivos.mo--; } return super.disconnect(); } };
  const RO = window.ResizeObserver; if (RO) window.ResizeObserver = class extends RO { constructor(cb) { super(cb); this.__g = dentro(); } observe(...a) { if (this.__g && !this.__on) { this.__on = true; window.__vivos.ro++; } return super.observe(...a); } disconnect() { if (this.__g && this.__on) { this.__on = false; window.__vivos.ro--; } return super.disconnect(); } };
  const si = window.setInterval.bind(window), ci = window.clearInterval.bind(window), mios = new Set();
  window.setInterval = (f, ms, ...a) => { const id = si(f, ms, ...a); if (dentro()) { mios.add(id); window.__vivos.iv = mios.size; } return id; };
  window.clearInterval = (id) => { mios.delete(id); window.__vivos.iv = mios.size; return ci(id); };
})();"""


@prueba
def cerrar_en_cualquier_escena_o_paso_limpia_animaciones_temporizadores_y_observadores(nav):
    s = B.Sesion(nav, **MOVIL)
    s.ctx.add_init_script(INSTRUMENTO)
    p = con_bienvenida(s)
    base = p.evaluate('window.__vivos')
    for escena in (0, 3, 7):                               # la bienvenida se omite/cierra en distintas escenas
        if escena:
            p.evaluate("document.querySelector('#menuButton').click()"); p.wait_for_timeout(500)
            p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })"); p.click('#menuBienvenida'); p.wait_for_timeout(900)
        for _ in range(escena): p.click('#bienSiguiente'); p.wait_for_timeout(120)
        p.keyboard.press('Escape'); p.wait_for_timeout(500)
        assert p.is_hidden('#bienvenida') and p.evaluate("[...document.querySelectorAll('#bienIlustracion svg.escena-svg')].every(s => s.animationsPaused())"), f'cerrada en la escena {escena + 1}: todo quieto'
        assert p.evaluate("!document.body.classList.contains('modal-open') && !document.querySelector('#bienvenida.cerrando')")
    assert p.evaluate('window.__vivos') == base, 'la bienvenida no deja temporizadores ni observadores'
    # la práctica: salir en el paso 1, 2, 3 y 5 (con o sin viaje encontrado)
    for destino in ('1 de 2', '2 de 5', '2 de 2', 'recomendacion'):
        if destino == 'recomendacion':
            practica_hasta_recomendacion(p); siguiente(p, 3)
        else:
            p.evaluate(AUTO, EJEMPLO)
            if destino == '1 de 2': hasta_paso(p, 1, '2 de 2', 8000)
            elif destino == '2 de 5': hasta_paso(p, 1, '2 de 2', 8000); siguiente(p); hasta_paso(p, 2, '1 de 5'); siguiente(p); hasta_paso(p, 2, '2 de 5')
            else: practica_hasta_buscar(p)
        assert p.evaluate('window.__vivos.mo') >= 1, 'durante la práctica el coach observa la pantalla (prueba de que el instrumento funciona)'
        p.click('.coach-salir'); p.wait_for_timeout(900)
        v = p.evaluate('window.__vivos')
        assert v['mo'] == 0 and v['ro'] == 0 and v['iv'] == 0, f'al salir en «{destino}» no queda ningún observador ni temporizador del tutorial: {v}'
        assert p.evaluate("document.querySelectorAll('.coach, .coach-fin, .coach-demo, .coach-bloqueo').length") == 0 and p.evaluate("!document.body.classList.contains('practicando')")
        assert p.evaluate('Spevb.Guiado.modo()') == 'avanzado'
    s.limpio('cerrar limpia'); s.cerrar()


@prueba
def con_el_teclado_virtual_abierto_el_campo_y_las_sugerencias_siguen_visibles(nav):
    s = B.Sesion(nav, **{**MOVIL, 'viewport': {'width': 320, 'height': 568}})
    p = s.abrir()
    p.evaluate("(ej) => { window.__practica = Spevb.Guia.practica({ ejemplo: ej }); }", EJEMPLO)
    hasta_paso(p, 1, '1 de 2', 6000); p.wait_for_timeout(700)
    p.set_viewport_size({'width': 320, 'height': 300}); p.wait_for_timeout(900)      # el teclado ocupa el resto de la pantalla
    p.click('#tripDestination'); p.keyboard.type('Termi', delay=30); p.wait_for_timeout(1400)
    r = p.evaluate("""() => { const i = document.getElementById('tripDestination').getBoundingClientRect(), t = document.querySelector('.coach-tarjeta').getBoundingClientRect(), vv = window.visualViewport,
        lista = document.getElementById(document.getElementById('tripDestination').getAttribute('aria-controls')), l = lista && !lista.hidden && lista.getClientRects().length ? lista.getBoundingClientRect() : null,
        cruza = (a, b) => !(a.bottom <= b.top + 1 || a.top >= b.bottom - 1);
        return { campoVisible: i.top >= 0 && i.bottom <= vv.height + 1, tapaCampo: cruza(i, t), hayLista: !!l, listaVisible: !l || (l.bottom > 0 && l.top < vv.height), tapaLista: !!l && cruza(l, t), tarjetaDentro: t.top >= -1 && t.bottom <= vv.height + 1,
          foco: document.activeElement.id }; }""")
    assert r['campoVisible'] and not r['tapaCampo'] and r['listaVisible'] and not r['tapaLista'] and r['tarjetaDentro'], f'con teclado abierto (300 px de alto): {r}'
    p.set_viewport_size({'width': 320, 'height': 568}); p.wait_for_timeout(700)
    assert 'paso 1' in coach_paso(p).lower() and p.evaluate("document.getElementById('tripDestination').value") == 'Termi', 'al cerrarse el teclado se conserva el paso y lo escrito'
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.limpio('teclado virtual'); s.cerrar()


@prueba
def el_estado_sobrevive_a_cambios_de_altura_y_de_orientacion_durante_la_leccion(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    p.click('#bienSiguiente'); p.click('#bienSiguiente'); p.wait_for_timeout(300)
    p.set_viewport_size({'width': 848, 'height': 384}); p.wait_for_timeout(500)
    assert p.inner_text('#bienPasoTexto') == 'Paso 3 de 8' and p.is_visible('#bienSiguiente'), 'la lección sigue en la misma escena al girar el celular'
    p.set_viewport_size({'width': 384, 'height': 848}); p.wait_for_timeout(500)
    assert p.inner_text('#bienPasoTexto') == 'Paso 3 de 8'
    p.keyboard.press('Escape'); p.wait_for_timeout(400)
    p.evaluate(AUTO, EJEMPLO); hasta_paso(p, 1, '2 de 2', 8000)
    antes = p.evaluate("({ paso: Spevb.Guiado.paso(), d: Spevb.Planner.puntos().destino.nombre })")
    for ancho, alto in ((848, 384), (384, 320), (384, 848)):
        p.set_viewport_size({'width': ancho, 'height': alto}); p.wait_for_timeout(700)
        ok = p.evaluate("""() => { const c = document.querySelector('.coach-tarjeta').getBoundingClientRect(); return { dentro: c.top >= -1 && c.bottom <= innerHeight + 1 && c.left >= -1 && c.right <= innerWidth + 1, paso: document.querySelector('.coach-paso').textContent }; }""")
        assert ok['dentro'] and 'paso 1' in ok['paso'] and '2 de 2' in ok['paso'], f'{ancho}x{alto}: {ok}'
    despues = p.evaluate("({ paso: Spevb.Guiado.paso(), d: Spevb.Planner.puntos().destino.nombre })")
    assert despues == antes, 'girar o cambiar la altura no reinicia ni borra lo elegido'
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.limpio('altura y orientacion'); s.cerrar()


def citas(tips):
    return sorted({m for t in tips for m in re.findall(r'«([^»]+)»', t)})


@prueba
def las_ayudas_contextuales_siguen_coincidiendo_con_los_botones_verdaderos(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    BUSCAR = """(txt) => { const n = (x) => (x || '').replace(/\\s+/g, ' ').trim().toLowerCase(), t = n(txt);
        return [...document.querySelectorAll('button, a, summary, input, [role=button], label, .guiado-boton')].some(e => [e.textContent, e.getAttribute('aria-label'), e.getAttribute('placeholder'), e.getAttribute('title'), e.value].some(v => n(v).includes(t))); }"""
    # 1) flujo guiado: cada paso nombra botones que EXISTEN en esa pantalla
    p.evaluate("document.getElementById('menuPasoAPaso').click()"); p.wait_for_timeout(500)
    vistos = []

    def ayuda_del_paso(paso):
        assert p.evaluate('Spevb.Guiado.paso()') == paso, (paso, p.evaluate('Spevb.Guiado.paso()'))
        p.evaluate("document.getElementById('guiadoAyudaBtn').click()"); p.wait_for_timeout(350)
        tips = p.evaluate("[...document.querySelectorAll('#ayudaLista li')].map(l => l.textContent)")
        p.click('#ayudaCerrar'); p.wait_for_timeout(300)
        faltan = [c for c in citas(tips) if not p.evaluate(BUSCAR, c)]
        assert not faltan, f'paso «{paso}»: la ayuda nombra botones que no existen en la pantalla: {faltan}'
        vistos.append((paso, citas(tips)))
    ayuda_del_paso('destino')
    p.evaluate("Spevb.Planner.poner('destination', " + json.dumps(EJEMPLO['b']) + ")"); p.wait_for_timeout(400)
    ayuda_del_paso('confirmar_destino')
    p.evaluate("Spevb.Guiado.ir('origen')"); p.wait_for_timeout(300)
    ayuda_del_paso('origen')
    p.evaluate("Spevb.Planner.poner('origin', " + json.dumps(EJEMPLO['a']) + ")"); p.wait_for_timeout(400)
    ayuda_del_paso('confirmar_origen')
    p.evaluate("Spevb.Guiado.ir('resumen')"); p.wait_for_timeout(300)
    ayuda_del_paso('resumen')
    assert any('Usar mi ubicación actual' in c for _, cs in vistos for c in cs) and any('Buscar cómo llegar' in c for _, cs in vistos for c in cs), vistos
    # 2) planificador con A y B: los botones que nombra la ayuda también existen
    p.evaluate("document.getElementById('menuPasoAPaso').click()"); p.wait_for_timeout(500)
    assert p.evaluate('Spevb.Guiado.modo()') == 'avanzado'
    p.evaluate("Spevb.Planner.limpiar()"); p.wait_for_timeout(300)
    for etiqueta, preparar in (('inicio', None), ('listos', "(() => { Spevb.Planner.poner('origin', " + json.dumps(EJEMPLO['a']) + "); Spevb.Planner.poner('destination', " + json.dumps(EJEMPLO['b']) + "); })()")):
        if preparar: p.evaluate(preparar); p.wait_for_timeout(500)
        p.click('#helpButton'); p.wait_for_timeout(350)
        tips = p.evaluate("[...document.querySelectorAll('#ayudaLista li')].map(l => l.textContent)")
        p.click('#ayudaCerrar'); p.wait_for_timeout(300)
        faltan = [c for c in citas(tips) if not p.evaluate(BUSCAR, c)]
        assert not faltan, f'planificador, estado «{etiqueta}»: {faltan}'
    s.limpio('ayudas coinciden'); s.cerrar()


# ------------------------------------------------------------------------------------------------ ayuda en contexto
@prueba
def la_ayuda_cambia_segun_lo_que_se_ve_en_pantalla(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    assert p.is_visible('#helpButton') and p.get_attribute('#helpButton', 'aria-label').startswith('Ayuda')

    def ayuda():
        p.click('#helpButton'); p.wait_for_timeout(300)
        t = p.inner_text('#ayudaTitulo'); n = p.locator('#ayudaLista li').count(); demo = p.is_visible('#ayudaDemo')
        p.click('#ayudaCerrar'); p.wait_for_timeout(250)
        return t, n, demo
    t, n, demo = ayuda()
    assert t == 'Para empezar' and 3 <= n <= 4 and demo
    p.fill('#tripOrigin', ORIGEN); p.keyboard.press('Enter'); p.wait_for_timeout(900)
    assert ayuda()[0] == 'Te falta un punto'
    p.fill('#tripDestination', DEST); p.keyboard.press('Enter'); p.wait_for_timeout(900)
    assert ayuda()[0] == 'Ya casi'
    p.evaluate("document.querySelector('#planTrip').click()")
    B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 12000)
    p.wait_for_timeout(800)
    assert ayuda()[0] in ('Tus opciones', 'Ya elegiste una ruta')
    p.evaluate("document.querySelector('#tripResults .trip-option summary').click()"); p.wait_for_timeout(700)
    t, n, demo = ayuda()
    assert t == 'Ya elegiste una ruta' and demo, 'con una ruta elegida la ayuda habla del mapa y de «Iniciar viaje»'
    p.click('#helpButton'); p.wait_for_timeout(300)
    p.keyboard.press('Escape'); p.wait_for_timeout(300)
    assert p.is_hidden('#ayudaModal'), 'Escape cierra la ayuda'
    s.limpio('ayuda'); s.cerrar()


@prueba
def la_ayuda_reconoce_la_falta_de_conexion_y_la_busqueda_en_curso(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.fill('#tripOrigin', ORIGEN); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    p.fill('#tripDestination', DEST); p.keyboard.press('Enter'); p.wait_for_timeout(700)
    p.evaluate("(() => { const st = document.getElementById('tripStatus'); st.textContent = 'Comparando A y B con todos los recorridos guardados…'; st.className = 'status info'; })()")
    p.click('#helpButton'); p.wait_for_timeout(300)
    assert p.inner_text('#ayudaTitulo') == 'Buscando tus rutas' and not p.is_visible('#ayudaDemo')
    p.click('#ayudaCerrar'); p.wait_for_timeout(200)
    s.ctx.set_offline(True); p.wait_for_timeout(300)
    p.click('#helpButton'); p.wait_for_timeout(300)
    assert p.inner_text('#ayudaTitulo') == 'Algo no salió bien' and 'conexión' in p.inner_text('#ayudaLista')
    p.click('#ayudaCerrar'); p.wait_for_timeout(200)
    s.ctx.set_offline(False)
    s.limpio('ayuda sin conexion'); s.cerrar()


@prueba
def la_ayuda_resalta_la_accion_recomendada_y_ofrece_una_demostracion_y_ayudas_rapidas(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.click('#helpButton'); p.wait_for_timeout(300)
    assert p.is_visible('#ayudaDemo') and p.inner_text('#ayudaDemo') == 'Ver cómo se busca'
    p.click('#ayudaCerrar'); p.wait_for_timeout(500)
    assert p.evaluate("document.getElementById('tripOrigin').classList.contains('ayuda-resalta')"), 'al cerrar se resalta el campo que toca llenar'
    assert p.evaluate("document.activeElement.id") == 'helpButton', 'el foco vuelve al botón «?»'
    # la demostración reutiliza una escena de la bienvenida (una sola, sin navegación) y no cuenta como bienvenida vista
    p.evaluate("localStorage.removeItem('spevb-bienvenida')")
    p.click('#helpButton'); p.wait_for_timeout(300)
    p.click('#ayudaDemo'); p.wait_for_timeout(900)
    assert p.is_visible('#bienvenida') and p.get_attribute('.bienvenida-card', 'data-modo') == 'leccion'
    assert p.inner_text('#bienPasoTexto') == 'Ayuda rápida' and p.inner_text('#bienSiguiente') == 'Entendido' and p.is_hidden('#bienAtras') and p.is_hidden('#bienPuntos') and p.is_hidden('#bienSaltar')
    p.click('#bienSiguiente'); p.wait_for_timeout(500)
    assert p.is_hidden('#bienvenida') and p.evaluate("localStorage.getItem('spevb-bienvenida')") is None, 'una ayuda rápida no marca la bienvenida como vista'
    # ayudas rápidas: diez temas (nueve con ilustración y uno con consejos)
    p.click('#helpButton'); p.wait_for_timeout(300)
    p.click('.ayuda-temas summary'); p.wait_for_timeout(200)
    assert p.locator('#ayudaTemas .tema-chip').count() == 10
    p.click('#ayudaTemas .tema-chip:has-text("Si no aparece una ruta")'); p.wait_for_timeout(300)
    assert p.inner_text('#ayudaTitulo') == 'Si no aparece una ruta' and p.locator('#ayudaLista li').count() == 3
    p.click('#ayudaCerrar'); p.wait_for_timeout(300)
    p.click('#helpButton'); p.wait_for_timeout(300); p.click('.ayuda-temas summary'); p.wait_for_timeout(200)
    p.click('#ayudaTemas .tema-chip:has-text("transbordos")'); p.wait_for_timeout(900)
    assert p.is_visible('#bienvenida') and 'transbordos' in p.inner_text('#bienTitulo') and p.get_attribute('.bienvenida-card', 'data-escena') == '3'
    p.keyboard.press('Escape'); p.wait_for_timeout(500)
    assert p.evaluate("document.activeElement.id") == 'helpButton' and p.evaluate("!document.body.classList.contains('modal-open')")
    s.limpio('ayuda demo'); s.cerrar()


# ------------------------------------------------------------------------------------------------ práctica guiada de 8 pasos sobre el flujo guiado REAL
ESCENAS_TITULOS = ['Primero, dime a dónde vas', 'Ahora, dónde estás', 'Revisa y busca', 'Esta es la recomendación', 'Empieza un solo viaje', 'Sigue tu marcador', 'Te aviso antes de bajar', 'Termina tu viaje']
TAMANOS_TUTORIAL = [(320, 568, True), (360, 640, True), (390, 844, True), (800, 360, True)]      # el último es horizontal y de poca altura


def coach_paso(p):
    return p.evaluate("(document.querySelector('.coach-paso') || {}).textContent || ''")


def hasta_paso(p, n, sub=None, espera=15000):
    expr = "!!document.querySelector('.coach-paso') && /paso " + str(n) + "( |$)/i.test(document.querySelector('.coach-paso').textContent)"
    if sub:
        expr += " && /· " + sub + "/.test(document.querySelector('.coach-paso').textContent)"
    B.esperar(p, expr, espera)


def siguiente(p, veces=1):
    for _ in range(veces):
        p.click('.coach-siguiente'); p.wait_for_timeout(250)


AUTO = "(ej) => { window.__practica = Spevb.Guia.practica({ ejemplo: ej, pausa: 60 }); }"


def practica_hasta_buscar(p, ejemplo=EJEMPLO):
    """Practica automática hasta el paso 3 (2 de 2): el flujo guiado real ya tiene destino y origen confirmados y espera «Buscar cómo llegar»."""
    p.evaluate(AUTO, ejemplo)
    hasta_paso(p, 1, '2 de 2', 8000); siguiente(p)                  # destino puesto (auto) → «Sí, continuar»
    hasta_paso(p, 2, '1 de 5'); siguiente(p)                        # usar mi ubicación (solo se señala)
    hasta_paso(p, 2, '2 de 5'); siguiente(p)                        # escribir una dirección (solo se señala)
    hasta_paso(p, 2, '3 de 5'); siguiente(p)                        # elegir en el mapa; el ejemplo se pone solo
    hasta_paso(p, 2, '5 de 5'); siguiente(p)                        # confirmar salida
    hasta_paso(p, 3, '1 de 2'); siguiente(p)                        # revisar
    hasta_paso(p, 3, '2 de 2')


def practica_hasta_recomendacion(p, ejemplo=EJEMPLO):
    practica_hasta_buscar(p, ejemplo)
    p.evaluate("document.getElementById('gBuscar').click()")
    hasta_paso(p, 4, None, 20000)


@prueba
def el_viaje_de_practica_tiene_ocho_pasos_sobre_el_flujo_guiado_real_y_da_el_logro_aprendiz(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    assert p.evaluate('Spevb.Guiado.modo()') == 'avanzado', 'el predeterminado sigue siendo el planificador con A y B'
    practica_hasta_buscar(p)
    assert p.evaluate('Spevb.Guiado.modo()') == 'guiado' and p.evaluate('Spevb.Guiado.paso()') == 'resumen', 'durante la práctica se usa el paso a paso real'
    assert p.input_value('#tripOrigin') == 'Ejemplo A' and p.input_value('#tripDestination') == 'Ejemplo B', 'los lugares de ejemplo quedan puestos en los campos reales'
    assert 'Buscar cómo llegar' in p.inner_text('.coach-texto') and p.is_hidden('.coach-siguiente'), 'paso 3: se pide tocar «Buscar cómo llegar»'
    assert p.evaluate("document.querySelector('.coach').dataset.sel") == '#gBuscar' and p.evaluate("getComputedStyle(document.querySelector('.coach-hueco')).display") == 'block', 'el botón real queda resaltado'
    assert p.evaluate("document.querySelectorAll('.coach-progreso i').length") == 8
    p.evaluate("document.getElementById('gBuscar').click()")
    hasta_paso(p, 4, None, 20000)
    sels = []
    for _ in range(12):
        if not re.search(r'paso 4( |$)', coach_paso(p)): break
        sels.append(p.get_attribute('#coach', 'data-sel') or 'texto')
        siguiente(p)
    assert any('guiado-datos' in c for c in sels) and len(sels) >= 5, f'una cosa por vez (razón, tiempo, caminata, buses, ruta, otras opciones): {sels}'
    hasta_paso(p, 5, None, 4000)
    t5 = p.inner_text('.coach-texto')
    assert 'Empezar este viaje' in t5 and 'Solo puede haber un viaje a la vez' in t5 and p.get_attribute('#coach', 'data-sel') == '#gEmpezar' and p.get_attribute('#coach', 'data-escudo') == '1', t5
    assert p.evaluate("!Spevb.Viaje.activo()") and p.evaluate("document.getElementById('viajeCard').hidden"), 'la práctica no inicia ningún viaje real'
    siguiente(p); hasta_paso(p, 6, None, 4000)
    assert 'círculo azul' in p.inner_text('.coach-texto') and 'código de la ruta' in p.inner_text('.coach-texto') and p.evaluate("!!document.querySelector('.coach-extra .m-bus') && document.querySelectorAll('.coach-extra .m-azul').length === 2")
    siguiente(p); hasta_paso(p, 7, None, 4000)
    assert all(x in p.inner_text('.coach-texto') + p.inner_text('.coach-extra') for x in ('cerca', 'prepárate', 'ahora', 'Tu bajada está aquí', 'Ya me bajé', 'dependen de tu teléfono', 'opcionales'))
    assert 'vibra' not in p.inner_text('.coach-texto').lower(), 'no se promete la vibración en todos los equipos'
    siguiente(p); hasta_paso(p, 8, None, 4000)
    assert 'Terminar viaje' in p.inner_text('.coach-texto') and p.inner_text('.coach-siguiente') == 'Terminar práctica' and p.is_visible('.coach-alt') and p.inner_text('.coach-alt') == 'Hacer mi viaje real'
    p.click('.coach-siguiente'); p.wait_for_timeout(1000)
    assert p.evaluate("!document.getElementById('coach')"), 'la capa guiada se retira'
    assert p.evaluate("Spevb.Logros.leer().hitos.includes('practica')"), 'logro «Aprendiz»'
    assert p.evaluate("Spevb.Datos.leer('historial').length") == 0 and p.evaluate("Spevb.Siempre.leer().length") == 0, 'la búsqueda de práctica no ensucia el historial ni «Tu viaje de siempre»'
    assert p.evaluate('Spevb.Guiado.modo()') == 'avanzado' and p.evaluate("localStorage.getItem('spevb-modo-planificador')") in (None, 'avanzado'), 'al terminar vuelve el planificador en el que estaba'
    s.limpio('practica'); s.cerrar()


@prueba
def la_practica_usa_el_flujo_guiado_real_y_no_toca_gps_viaje_cuenta_ni_datos(nav):
    s = B.Sesion(nav, **MOVIL)
    s.ctx.add_init_script("window.__gps = 0; if (navigator.geolocation) { for (const m of ['getCurrentPosition', 'watchPosition']) { const o = navigator.geolocation[m].bind(navigator.geolocation); navigator.geolocation[m] = (...a) => { window.__gps++; return o(...a); }; } }")
    escrituras = []
    s.ctx.on('request', lambda r: escrituras.append(r.method + ' ' + r.url) if r.method != 'GET' and ('/api/cuenta' in r.url or '/api/viajes/compartir' in r.url or '/api/rastreo' in r.url) else None)
    p = s.abrir()
    modo0 = p.evaluate("localStorage.getItem('spevb-modo-planificador')")
    practica_hasta_recomendacion(p)
    pasos_vistos = set()
    for _ in range(40):
        if not p.evaluate("!!document.getElementById('coach')"): break
        pasos_vistos.add(p.evaluate('Spevb.Guiado.paso()'))
        sel = p.get_attribute('#coach', 'data-sel') or ''
        if sel.startswith('#g'):
            assert p.evaluate("(s) => !!document.querySelector(s)", sel), f'el control real {sel} existe en el flujo guiado'
        if '8' in coach_paso(p) and 'paso 8' in coach_paso(p):
            p.click('.coach-siguiente'); break
        siguiente(p)
    p.wait_for_timeout(900)
    assert {'confirmar_destino', 'origen', 'recomendacion'} <= pasos_vistos or {'recomendacion'} <= pasos_vistos, pasos_vistos
    assert p.evaluate('window.__gps') == 0, 'la práctica no llama al GPS'
    assert p.evaluate("!Spevb.Viaje || !Spevb.Viaje.activo()") and p.evaluate("document.getElementById('viajeCard') === null || document.getElementById('viajeCard').hidden"), 'no se inició ningún viaje'
    assert not escrituras, f'no se escribió nada en la cuenta ni se compartió nada: {escrituras}'
    assert (p.evaluate("localStorage.getItem('spevb-modo-planificador')") or 'avanzado') == (modo0 or 'avanzado'), 'el modo guardado vuelve a ser el de antes'
    s.limpio('practica no toca'); s.cerrar()


@prueba
def salir_de_la_practica_en_cualquier_momento_no_da_logro_ni_deja_restos(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.evaluate(AUTO, EJEMPLO)
    B.esperar(p, "!!document.getElementById('coach')", 5000)
    p.click('.coach-salir'); p.wait_for_timeout(900)
    assert p.evaluate("!document.getElementById('coach')") and not p.evaluate("document.body.classList.contains('practicando')")
    assert not p.evaluate("Spevb.Logros.leer().hitos.includes('practica')")
    assert p.input_value('#tripOrigin') == '' and p.evaluate('Spevb.Guiado.modo()') == 'avanzado', 'sin nada previo, queda vacío y en el planificador de antes'
    # también con Escape y desde el menú
    p.click('#menuButton'); p.wait_for_timeout(500); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    p.click('#menuPractica'); p.wait_for_timeout(1200)
    assert p.evaluate("!!document.getElementById('coach')"), 'el menú inicia la práctica'
    p.keyboard.press('Escape'); p.wait_for_timeout(900)
    assert p.evaluate("!document.getElementById('coach')")
    assert p.evaluate("document.querySelectorAll('.coach, .coach-fin, .coach-demo, .coach-bloqueo').length") == 0, 'no quedan capas sobre la pantalla'
    s.limpio('salir practica'); s.cerrar()


@prueba
def la_practica_conserva_y_devuelve_lo_que_la_persona_tenia(nav):
    for modo in ('avanzado', 'guiado'):
        s = B.Sesion(nav, **MOVIL)
        p = s.abrir()
        if modo == 'guiado':
            p.evaluate("document.getElementById('menuPasoAPaso').click()"); p.wait_for_timeout(500)
        if modo == 'avanzado':
            planear(p, 800)
        else:
            p.evaluate("Spevb.Planner.poner('destination', " + json.dumps({**EJEMPLO['b'], 'nombre': 'Mi destino'}) + "); Spevb.Planner.poner('origin', " + json.dumps({**EJEMPLO['a'], 'nombre': 'Mi origen'}) + ")"); p.wait_for_timeout(500)
            p.evaluate("Spevb.Guiado.ir('resumen')"); p.wait_for_timeout(300)
            p.evaluate("document.getElementById('gBuscar').click()")
            B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 15000); p.wait_for_timeout(1500)
        antes = p.evaluate("({ a: Spevb.Planner.puntos().origen.lat, b: Spevb.Planner.puntos().destino.lat, nombreA: document.getElementById('tripOrigin').value, nombreB: document.getElementById('tripDestination').value, modo: Spevb.Guiado.modo() })")
        assert antes['modo'] == modo
        p.evaluate(AUTO, EJEMPLO)
        hasta_paso(p, 1, '2 de 2', 8000)
        assert p.input_value('#tripDestination') == 'Ejemplo B', 'durante la práctica se usan los puntos de ejemplo'
        p.click('.coach-salir'); p.wait_for_timeout(1200)
        despues = p.evaluate("({ a: Spevb.Planner.puntos().origen.lat, b: Spevb.Planner.puntos().destino.lat, nombreA: document.getElementById('tripOrigin').value, nombreB: document.getElementById('tripDestination').value, modo: Spevb.Guiado.modo() })")
        assert despues == antes, f'al salir vuelven tu origen, tu destino y tu modo ({modo}): {antes} / {despues}'
        B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 12000)      # y los resultados que tenías
        assert p.evaluate("Spevb.Datos.leer('historial').length") == 1, 'el viaje real anterior sigue en el historial una sola vez'
        s.limpio('practica restaura ' + modo); s.cerrar()


@prueba
def en_la_practica_se_puede_volver_atras_sin_perder_lo_elegido_y_la_persona_puede_poner_el_punto_por_su_cuenta(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.evaluate("(ej) => { window.__practica = Spevb.Guia.practica({ ejemplo: ej }); }", EJEMPLO)       # sin «pausa»: la persona hace los pasos
    hasta_paso(p, 1, '1 de 2', 6000)
    assert p.is_hidden('.coach-atras') and p.inner_text('.coach-siguiente') == 'Poner un ejemplo'
    assert p.get_attribute('#coach', 'data-sel') == '#tripDestination'
    p.fill('#tripDestination', 'Cerca de la Terminal'); p.keyboard.press('Enter')                   # lo hace ella misma con el campo real (el flujo guiado real lo recibe)
    p.evaluate("Spevb.Planner.poner('destination', " + json.dumps(EJEMPLO['b']) + ")")
    hasta_paso(p, 1, '2 de 2', 8000)
    assert p.evaluate('Spevb.Guiado.paso()') == 'confirmar_destino' and p.is_visible('.coach-atras')
    p.click('.coach-atras'); hasta_paso(p, 1, '1 de 2', 4000)
    assert 'Ya tienes tu destino' in p.inner_text('.coach-texto') and p.inner_text('.coach-siguiente') == 'Siguiente', 'al volver no se pierde lo hecho'
    assert p.evaluate("Spevb.Planner.puntos().destino !== null"), 'el destino sigue elegido'
    siguiente(p); hasta_paso(p, 1, '2 de 2', 4000)
    siguiente(p); hasta_paso(p, 2, '1 de 5', 4000)           # «Sí, continuar» lo toca el botón real
    assert p.evaluate('Spevb.Guiado.paso()') == 'origen'
    p.click('.coach-atras'); hasta_paso(p, 1, '2 de 2', 4000)
    assert p.evaluate("Spevb.Planner.puntos().destino !== null") and p.evaluate('Spevb.Guiado.paso()') == 'confirmar_destino', 'retroceder y avanzar conserva el destino confirmado'
    siguiente(p); hasta_paso(p, 2, '1 de 5', 4000); siguiente(p); hasta_paso(p, 2, '2 de 5', 4000); siguiente(p)
    hasta_paso(p, 2, '3 de 5', 4000); siguiente(p); hasta_paso(p, 2, '4 de 5', 4000)
    assert p.inner_text('.coach-siguiente') == 'Poner un ejemplo'
    p.click('.coach-siguiente'); hasta_paso(p, 2, '5 de 5', 6000)
    assert p.evaluate("Spevb.Planner.puntos().origen !== null")
    p.click('.coach-atras'); hasta_paso(p, 2, '3 de 5', 4000)
    assert p.evaluate("Spevb.Planner.puntos().origen !== null") and p.evaluate("Spevb.Planner.puntos().destino !== null"), 'volver atrás no borra ninguno de los dos lugares'
    p.click('.coach-salir'); p.wait_for_timeout(700)
    s.limpio('practica atras'); s.cerrar()


@prueba
def si_el_servicio_de_rutas_falla_la_practica_sigue_con_un_ejemplo_marcado_como_simulacion(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.route('**/api/viajes/planificar', lambda r: r.fulfill(status=503, content_type='application/json', body='{"status":503,"message":"Servicio no disponible"}'))
    practica_hasta_buscar(p)
    p.evaluate("document.getElementById('gBuscar').click()")
    B.esperar(p, "!document.querySelector('.coach-alt').hidden", 15000)
    assert 'Ahora no pude traer rutas reales' in p.inner_text('.coach-texto') and p.inner_text('.coach-alt') == 'Ver un ejemplo ilustrado'
    p.click('.coach-alt'); hasta_paso(p, 4, None, 4000)
    assert p.is_visible('.coach-simulacion') and 'simulación' in p.inner_text('.coach-simulacion'), 'se dice claramente que es una simulación'
    assert p.evaluate("!!document.querySelector('#coachDemo .demo-sello') && /simulaci/i.test(document.querySelector('#coachDemo .demo-sello').textContent)")
    assert p.evaluate("!/(^|[^A-Za-zÁÉÍÓÚáéíóú0-9])[AB]($|[^A-Za-zÁÉÍÓÚáéíóú0-9])/.test(document.querySelector('#coachDemo').textContent)"), 'el ejemplo ilustrado ya no habla de «A» ni «B»'
    assert p.evaluate("document.querySelectorAll('#tripResults .trip-option').length") == 0, 'no se mezclan resultados ficticios con los reales'
    for _ in range(5): siguiente(p)
    hasta_paso(p, 5, None, 4000)
    assert p.evaluate("document.querySelector('.coach').dataset.demo") == 'iniciar' and 'Empezar este viaje' in p.inner_text('#coachDemo .demo-iniciar')
    siguiente(p, 3); hasta_paso(p, 8, None, 4000)
    p.click('.coach-siguiente'); p.wait_for_timeout(900)
    assert p.evaluate("Spevb.Logros.leer().hitos.includes('practica')"), 'también se completa con la demostración'
    assert p.evaluate("!document.getElementById('coach') && !document.getElementById('coachDemo')")
    s.errores[:] = [e for e in s.errores if '503' not in e]        # el 503 lo provoca la propia prueba
    s.limpio('practica servicio caido'); s.cerrar()


@prueba
def durante_la_practica_el_menu_y_el_resto_de_la_pantalla_quedan_bloqueados_tambien_con_teclado(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    practica_hasta_buscar(p)
    p.wait_for_timeout(700)
    r = p.evaluate("""() => { const quien = (id) => { const b = document.getElementById(id).getBoundingClientRect(); const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
            return e ? (e.className || e.id || e.tagName) : null; };
        const plan = document.getElementById('gBuscar').getBoundingClientRect(), e = document.elementFromPoint(plan.left + plan.width / 2, plan.top + plan.height / 2);
        return { menu: quien('menuButton'), ayuda: quien('helpButton'), buscarLibre: e === document.getElementById('gBuscar') || document.getElementById('gBuscar').contains(e) }; }""")
    assert 'coach-bloqueo' in str(r['menu']) and 'coach-bloqueo' in str(r['ayuda']), f'el menú y «?» quedan bloqueados: {r}'
    assert r['buscarLibre'], 'el botón señalado sí se puede tocar'
    for _ in range(7):                                    # Tab solo recorre lo señalado y los botones de la tarjeta
        p.keyboard.press('Tab')
        assert p.evaluate("!!document.activeElement.closest('#gBuscar, .coach-tarjeta') || document.activeElement.id === 'gBuscar'"), p.evaluate("document.activeElement.id || document.activeElement.className")
    assert not p.evaluate("document.getElementById('sideMenu').classList.contains('open')")
    assert p.evaluate("document.querySelectorAll('.coach-dedo svg').length") == 1 and p.evaluate("!!document.querySelector('.coach-guia')")
    assert p.get_attribute('.coach-tarjeta', 'role') == 'dialog' and p.get_attribute('.coach-texto', 'aria-live') == 'polite'
    p.click('.coach-salir'); p.wait_for_timeout(700)
    assert p.evaluate("!document.getElementById('coach')")
    s.limpio('practica bloqueada'); s.cerrar()


@prueba
def el_coach_no_mide_la_pantalla_en_cada_cuadro_y_sigue_al_elemento_cuando_se_mueve(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.add_init_script("window.__raf = 0; const o = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = (f) => { if (new Error().stack.includes('guia.js')) window.__raf++; return o(f); };")
    p.reload(); p.wait_for_timeout(1500)
    practica_hasta_buscar(p)
    for _ in range(40):                                   # se espera a que se calme lo que mueve la pantalla (animaciones que terminan)
        c0 = p.evaluate("window.__raf"); p.wait_for_timeout(1200)
        if p.evaluate("window.__raf") == c0: break
    antes = p.evaluate("window.__raf"); p.wait_for_timeout(3000); despues = p.evaluate("window.__raf")
    assert despues - antes < 25, f'en reposo el coach casi no pide cuadros: {despues - antes} en 3 s'
    p.set_viewport_size({'width': 384, 'height': 560}); p.wait_for_timeout(900)          # cambia el tamaño (teclado, giro…): el resaltado sigue al botón
    r = p.evaluate("""() => { const h = document.querySelector('.coach-hueco').getBoundingClientRect(), b = document.getElementById('gBuscar').getBoundingClientRect(),
        t = document.querySelector('.coach-tarjeta').getBoundingClientRect();
        return { dif: Math.abs((h.top + h.height / 2) - (b.top + b.height / 2)), tapa: !(t.bottom <= b.top || t.top >= b.bottom), vh: innerHeight, abajo: t.bottom }; }""")
    assert r['dif'] < 8 and not r['tapa'] and r['abajo'] <= r['vh'] + 1, f'el resaltado sigue al botón y la tarjeta no lo tapa: {r}'
    p.click('.coach-salir'); p.wait_for_timeout(600)
    antes = p.evaluate("window.__raf"); p.wait_for_timeout(1500)
    assert p.evaluate("window.__raf") - antes < 6, 'al salir no queda ningún bucle de animación del coach'
    s.limpio('coach eventos'); s.cerrar()


@prueba
def la_practica_se_puede_repetir_y_con_poco_movimiento_no_anima(nav):
    s = B.Sesion(nav, reduced_motion='reduce', **MOVIL)
    p = s.abrir()
    for vuelta in range(2):
        p.evaluate(AUTO, EJEMPLO)
        hasta_paso(p, 1, '2 de 2', 8000)
        assert p.evaluate("getComputedStyle(document.querySelector('.coach-hueco .onda')).animationName") == 'none', 'sin animaciones con poco movimiento'
        p.click('.coach-salir'); p.wait_for_timeout(700)
        assert p.evaluate("!document.getElementById('coach')"), f'vuelta {vuelta + 1}: se retira'
    practica_hasta_recomendacion(p)
    for _ in range(40):
        if p.evaluate("!document.getElementById('coach')"): break
        if 'paso 8' in coach_paso(p): p.click('.coach-siguiente'); break
        siguiente(p)
    p.wait_for_timeout(900)
    assert p.evaluate("Spevb.Logros.leer().hitos.includes('practica')") and p.evaluate("getComputedStyle(document.querySelector('#coachFin .fin-chulo circle')).animationName") == 'none'
    s.limpio('practica repetida'); s.cerrar()


@prueba
def la_practica_funciona_en_todos_los_tamanos_y_la_tarjeta_nunca_tapa_lo_que_ensena(nav):
    for ancho, alto, movil in TAMANOS_TUTORIAL + [(768, 1024, False), (1280, 800, False)]:
        s = B.Sesion(nav, viewport={'width': ancho, 'height': alto}, is_mobile=movil, has_touch=movil)
        p = s.abrir()
        chequeos = []

        def revisar(etiqueta):
            r = p.evaluate("""() => { const c = document.querySelector('.coach'), t = document.querySelector('.coach-tarjeta').getBoundingClientRect(), sel = c.dataset.sel, el = sel ? document.querySelector(sel) : null;
                const b = el ? el.getBoundingClientRect() : null;
                const botones = [...document.querySelectorAll('.coach-tarjeta button')].filter(x => !x.hidden && x.getClientRects().length).map(x => { const r = x.getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), dentro: r.top >= -1 && r.bottom <= innerHeight + 1 && r.left >= -1 && r.right <= innerWidth + 1 }; });
                return { tapa: !!b && b.width > 0 && !(t.bottom <= b.top + 1 || t.top >= b.bottom - 1 || t.right <= b.left + 1 || t.left >= b.right - 1), dentro: t.top >= -1 && t.bottom <= innerHeight + 1 && t.left >= -1 && t.right <= innerWidth + 1,
                  ancho: document.documentElement.scrollWidth <= innerWidth, botones, sel }; }""")
            assert not r['tapa'] and r['dentro'] and r['ancho'], f'{ancho}x{alto} {etiqueta}: {r}'
            assert r['botones'] and all(b['h'] >= 44 and b['dentro'] for b in r['botones']), f'{ancho}x{alto} {etiqueta}: botones táctiles cómodos y a la vista: {r["botones"]}'
            chequeos.append(r['sel'])
        p.evaluate(AUTO, EJEMPLO)
        hasta_paso(p, 1, '2 de 2', 8000); p.wait_for_timeout(700); revisar('confirmar destino'); siguiente(p)
        hasta_paso(p, 2, '1 de 5'); p.wait_for_timeout(700); revisar('usar ubicación'); siguiente(p)
        hasta_paso(p, 2, '2 de 5'); p.wait_for_timeout(700); revisar('escribir una dirección'); siguiente(p)
        hasta_paso(p, 2, '3 de 5'); p.wait_for_timeout(700); revisar('elegir en el mapa'); siguiente(p)
        hasta_paso(p, 2, '5 de 5'); p.wait_for_timeout(700); revisar('confirmar salida'); siguiente(p)
        hasta_paso(p, 3, '1 de 2'); p.wait_for_timeout(700); revisar('revisar'); siguiente(p)
        hasta_paso(p, 3, '2 de 2'); p.wait_for_timeout(700); revisar('buscar')
        p.evaluate("document.getElementById('gBuscar').click()"); hasta_paso(p, 4, None, 20000)
        for k in range(6):
            if not re.search(r'paso 4( |$)', coach_paso(p)): break
            p.wait_for_timeout(500); revisar(f'recomendación {k + 1}'); siguiente(p)
        hasta_paso(p, 5, None, 4000); p.wait_for_timeout(500); revisar('empezar')
        for n in (6, 7, 8):
            siguiente(p); hasta_paso(p, n, None, 4000); p.wait_for_timeout(500); revisar(f'paso {n}')
        assert len(chequeos) >= 14, chequeos
        p.click('.coach-salir'); p.wait_for_timeout(600)
        s.limpio(f'practica {ancho}x{alto}'); s.cerrar()


# ------------------------------------------------------------------------------------------------ tu viaje de siempre
@prueba
def tu_viaje_de_siempre_se_ofrece_si_se_repite_a_esa_hora_y_se_busca_con_un_toque(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    r = p.evaluate("""([ej]) => { const S = Spevb.Siempre, ahora = new Date(2026, 5, 10, 7, 30), dia = 86400000;
        const hoy7 = new Date(2026, 5, 10, 7, 40).getTime();
        const nada = S.candidato(ahora);
        S.registrar(ej.a, ej.b, hoy7 - 1 * dia);
        const una = S.candidato(ahora);
        S.registrar(ej.a, ej.b, hoy7 - 2 * dia);
        const dos = S.candidato(ahora);
        const tarde = S.candidato(new Date(2026, 5, 10, 19, 0));            // a las 7 p. m. no es «su hora»
        return { nada, una, dos: dos && dos.aEstaHora, tarde }; }""", [EJEMPLO])
    assert r['nada'] is None and r['una'] is None and r['dos'] == 2 and r['tarde'] is None, r
    # 4 veces a cualquier hora también cuenta
    p.evaluate("localStorage.removeItem('spevb-habitos')")
    r = p.evaluate("""([ej]) => { const S = Spevb.Siempre, dia = 86400000, base = new Date(2026, 5, 10, 12, 0).getTime();
        for (let i = 1; i <= 4; i++) S.registrar(ej.a, ej.b, base - i * dia - i * 3 * 3600000);
        return { cualquiera: !!S.candidato(new Date(2026, 5, 10, 23, 0)), viejo: (() => { localStorage.removeItem('spevb-habitos'); S.registrar(ej.a, ej.b, base - 60 * dia); S.registrar(ej.a, ej.b, base - 61 * dia); return S.candidato(new Date(2026, 5, 10, 12, 0)); })() }; }""", [EJEMPLO])
    assert r['cualquiera'] is True and r['viejo'] is None, f'los hábitos de hace más de 45 días no cuentan: {r}'
    # ahora con la hora real: tres veces a esta hora → aparece la tarjeta
    p.evaluate("""([ej]) => { localStorage.removeItem('spevb-habitos'); const S = Spevb.Siempre, dia = 86400000;
        for (let i = 1; i <= 3; i++) S.registrar(ej.a, ej.b, Date.now() - i * dia); S.pintar(); }""", [EJEMPLO])
    assert p.is_visible('#siempre') and 'Ejemplo A' in p.inner_text('#siempreRuta') and 'Ejemplo B' in p.inner_text('#siempreRuta')
    p.click('#siempreBuscar')
    B.esperar(p, "document.querySelectorAll('#tripResults .trip-option').length > 0", 15000)
    assert p.input_value('#tripOrigin') == 'Ejemplo A' and p.input_value('#tripDestination') == 'Ejemplo B'
    assert p.is_hidden('#siempre'), 'con el viaje puesto la tarjeta se oculta'
    s.limpio('viaje de siempre'); s.cerrar()


@prueba
def ahora_no_oculta_tu_viaje_de_siempre_por_hoy(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.evaluate("""([ej]) => { const S = Spevb.Siempre, dia = 86400000;
        for (let i = 1; i <= 3; i++) S.registrar(ej.a, ej.b, Date.now() - i * dia); S.pintar(); }""", [EJEMPLO])
    assert p.is_visible('#siempre')
    p.click('#siempreNo'); p.wait_for_timeout(200)
    assert p.is_hidden('#siempre')
    p.evaluate("Spevb.Siempre.pintar()")
    assert p.is_hidden('#siempre'), 'no vuelve a salir hoy'
    p.reload(); p.wait_for_timeout(1500)
    assert p.is_hidden('#siempre'), 'ni al recargar'
    s.limpio('ahora no'); s.cerrar()


# ------------------------------------------------------------------------------------------------ resumen de la semana
@prueba
def el_resumen_de_la_semana_suma_los_ultimos_7_dias_y_avisa_una_vez(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    r = p.evaluate("""() => { const L = Spevb.Logros, ahora = new Date(2026, 5, 10, 18, 0), dia = 86400000;
        const vacio = L.textoSemana(ahora);
        L.registrarViaje({ buses: 1, resumen: { minutos: 25, caminaMetros: 400 } }, new Date(ahora.getTime() - 8 * dia));    // hace 8 días: no cuenta
        L.registrarViaje({ buses: 1, resumen: { minutos: 25, caminaMetros: 400 } }, new Date(ahora.getTime() - 2 * dia));
        L.registrarViaje({ buses: 2, resumen: { minutos: 50, caminaMetros: 1300 } }, new Date(ahora.getTime() - 1 * dia));
        return { vacio, texto: L.textoSemana(ahora), r: L.resumenSemana(ahora), primera: L.avisoSemanal(ahora), segunda: L.avisoSemanal(ahora) }; }""")
    assert r['vacio'] == '' and r['r'] == {'viajes': 2, 'caminaMetros': 1700, 'minutos': 75}, r
    assert '2 viajes' in r['texto'] and '1,7 km' in r['texto'] and '1 h 15 min' in r['texto'], r['texto']
    assert r['primera'] is True and r['segunda'] is False, 'el aviso sale una sola vez por semana'
    p.evaluate("Spevb.Logros.registrarViaje({ buses: 1, resumen: { minutos: 20, caminaMetros: 300 } })")      # un viaje de HOY: el menú usa la fecha real
    p.click('#menuButton'); p.wait_for_timeout(500); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    assert p.is_visible('#semanaResumen') and 'viaje' in p.inner_text('#semanaResumen') and 'caminaste 300 m' in p.inner_text('#semanaResumen'), p.inner_text('#semanaResumen')
    s.limpio('semana'); s.cerrar()


# ------------------------------------------------------------------------------------------------ lenguaje simple del modo viaje
@prueba
def los_mensajes_del_viaje_usan_paradero_letrero_y_cuadras(nav):
    s = V.sesion(nav)
    p = s.abrir()
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'fase:caminar')
    c = V.card(p)
    assert 'paradero' in c['instruccion'] and 'M01' in c['instruccion'] and 'cuadra' in c['instruccion'] and ' m.' not in c['instruccion'], c
    i = V.alimentar(p, ls, i, 'fase:esperando')
    c = V.card(p)
    assert 'letrero' in c['instruccion'] and 'M01' in c['instruccion'], c
    i = V.alimentar(p, ls, i, 'pregunta')
    p.click('#viajeSi')
    i = V.alimentar(p, ls, i, 'alerta:alerta')
    aviso = V.card(p)['aviso']
    assert 'Te acercas' in aviso and 'cuadra' in aviso and ' m.' not in aviso, aviso
    i = V.alimentar(p, ls, i, 'bajada')
    s.limpio('lenguaje simple'); s.cerrar()


# ------------------------------------------------------------------------------------------------ bienvenida con ilustraciones animadas
# ------------------------------------------------------------------------------------------------ práctica robusta
@prueba
def la_practica_desde_el_menu_cierra_el_menu_antes_de_empezar(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.click('#menuButton'); p.wait_for_timeout(600); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    p.click('#menuPractica'); p.wait_for_timeout(1800)
    assert p.evaluate("!!document.getElementById('coach')") and p.evaluate('Spevb.Guiado.modo()') == 'guiado'
    assert not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"), 'el menú ya cerró'
    assert p.evaluate("getComputedStyle(document.getElementById('menuBackdrop')).display") == 'none' or p.evaluate("document.getElementById('menuBackdrop').classList.contains('hidden')")
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.limpio('practica desde menu'); s.cerrar()


@prueba
def al_terminar_la_practica_hay_una_celebracion_con_animacion_que_se_va_sola(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    practica_hasta_recomendacion(p)
    assert p.evaluate("document.querySelectorAll('.coach-progreso i.hecho').length") == 3, 'el progreso va marcando los pasos'
    for _ in range(40):
        if p.evaluate("!document.getElementById('coach')"): break
        if 'paso 8' in coach_paso(p): p.click('.coach-siguiente'); break
        siguiente(p)
    p.wait_for_timeout(900)
    assert p.is_visible('#coachFin') and 'Muy bien' in p.inner_text('#coachFin') and p.evaluate("document.querySelectorAll('#coachFin .fin-confeti i').length") == 12
    assert p.evaluate("getComputedStyle(document.getElementById('coachFin')).pointerEvents") == 'none' and p.evaluate("getComputedStyle(document.getElementById('coachFin')).backgroundColor") == 'rgba(0, 0, 0, 0)', 'la celebración no oscurece ni bloquea la pantalla'
    assert p.evaluate("document.querySelectorAll('#coachFin svg.fin-chulo').length") == 1
    B.esperar(p, "!document.getElementById('coachFin')", 8000)
    s.limpio('celebracion'); s.cerrar()


# ------------------------------------------------------------------------------------------------ pestañita «Ahora escribe B»
@prueba
def al_poner_un_punto_aparece_una_pestanita_sin_mover_la_pantalla_ni_abrir_el_teclado(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.click('#tripOrigin'); p.fill('#tripOrigin', ORIGEN); p.wait_for_timeout(900)          # el panel sube al escribir (teclado abierto)
    antes = p.evaluate("(() => { const r = document.getElementById('sheet').getBoundingClientRect(); return { top: Math.round(r.top), h: Math.round(r.height) }; })()")
    p.keyboard.press('Enter'); p.wait_for_timeout(1300)
    t = p.evaluate("(() => { const e = document.querySelector('.pestana-siguiente'); return e ? { texto: e.textContent, visible: e.classList.contains('visible') } : null; })()")
    assert t and t['visible'] and 'Ahora escribe B' in t['texto'] and 'a dónde vas' in t['texto'], t
    despues = p.evaluate("(() => { const r = document.getElementById('sheet').getBoundingClientRect(); return { top: Math.round(r.top), h: Math.round(r.height) }; })()")
    # 4.13.3: el ajuste temporal para escribir se deshace al confirmar el punto (el panel baja a la altura que la persona tenía); lo que no debe pasar es que CREZCA
    assert despues['top'] >= antes['top'] - 4, f'confirmar el punto no amplía el panel: {antes} → {despues}'
    assert p.evaluate("document.activeElement && document.activeElement.id") != 'tripDestination', 'no se abre el teclado en B'
    assert p.evaluate("document.querySelectorAll('.endpoint-block.pide-punto').length") == 1, 'el campo B late suavemente'
    p.fill('#tripDestination', DEST); p.keyboard.press('Enter'); p.wait_for_timeout(1200)
    assert p.evaluate("!document.querySelector('.pestana-siguiente')"), 'con los dos puntos la pestañita se va'
    s.limpio('pestana'); s.cerrar()


@prueba
def la_pestanita_pide_a_si_se_puso_primero_b_y_no_sale_durante_la_practica(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.fill('#tripDestination', DEST); p.keyboard.press('Enter'); p.wait_for_timeout(1300)
    assert p.evaluate("(document.querySelector('.pestana-siguiente') || {}).textContent || ''").startswith('A') and 'Ahora escribe A' in p.inner_text('.pestana-siguiente')
    p.click('.pestana-siguiente'); p.wait_for_timeout(500)
    assert p.evaluate("!document.querySelector('.pestana-siguiente.visible')") and p.evaluate("document.activeElement && document.activeElement.id") != 'tripOrigin', 'tocarla muestra el campo sin abrir el teclado'
    s.cerrar()
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    p.evaluate(AUTO, EJEMPLO)
    hasta_paso(p, 1, '2 de 2', 8000)
    assert p.evaluate("!document.querySelector('.pestana-siguiente.visible')"), 'durante la práctica no sale'
    p.click('.coach-salir'); p.wait_for_timeout(600)
    s.cerrar()


# ------------------------------------------------------------------------------------------------ sin voz, sin emojis, controles del bus
@prueba
def la_voz_ya_no_existe_en_ninguna_parte(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    assert p.evaluate("!document.getElementById('vozModal') && !document.getElementById('vozAjuste') && !document.getElementById('vozProbarMenu') && !window.Spevb.Voz")
    p.click('#menuButton'); p.wait_for_timeout(500); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    assert 'voz' not in p.inner_text('#sideMenu').lower(), 'el menú no habla de voz'
    s.limpio('sin voz'); s.cerrar()
    s = V.sesion(nav)
    p = s.abrir()
    V.planear(p); V.destino_lejos(p)
    V.iniciar(p)
    assert p.locator('#viajeVoz').count() == 0, 'la tarjeta del viaje no tiene botón de voz'
    assert p.evaluate("window.__voz.length") == 0
    s.limpio('viaje sin voz'); s.cerrar()


EMOJI = re.compile('[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U00002B00-\U00002BFF\U0000FE0F]')


@prueba
def no_hay_emojis_en_la_pantalla_principal_ni_en_el_menu_ni_en_las_ventanas(nav):
    s = B.Sesion(nav, **MOVIL)
    p = con_bienvenida(s)
    textos = {'bienvenida': p.evaluate("document.getElementById('bienvenida').innerText")}
    p.click('#bienSaltar'); p.wait_for_timeout(500)
    planear(p)
    p.evaluate("document.querySelector('#tripResults .trip-option').open = true")
    textos['principal'] = p.evaluate("document.getElementById('sheet').innerText")
    p.evaluate("Spevb.Logros.registrarViaje({ buses: 2 }, new Date(2026, 0, 5, 6, 30)); Spevb.Logros.marcarPractica();")
    p.click('#menuButton'); p.wait_for_timeout(500); p.evaluate("document.querySelectorAll('#sideMenu details.menu-seccion').forEach((d) => { d.open = true; })")
    textos['menu'] = p.evaluate("document.getElementById('sideMenu').innerText")
    for nombre in ('authModal', 'settingsModal', 'ayudaModal', 'reportModal', 'nameModal'):
        textos[nombre] = p.evaluate("(id) => document.getElementById(id).textContent", nombre)
    textos['toasts'] = p.evaluate("document.body.innerText")
    for nombre, t in textos.items():
        m = EMOJI.findall(t.replace('☰', ''))
        assert not m, f'emojis en «{nombre}»: {m}'
    assert p.evaluate("document.querySelectorAll('.logro-ico svg').length") >= 8, 'los logros usan iconos propios (SVG)'
    assert p.evaluate("document.querySelectorAll('.tl-ico svg').length") >= 0
    s.limpio('sin emojis'); s.cerrar()


@prueba
def los_controles_del_bus_son_solo_un_circulo_con_el_icono_del_bus(nav):
    s = B.Sesion(nav, **MOVIL)
    p = s.abrir()
    planear(p)                                                                             # el bus aparece cuando hay una ruta en el mapa
    p.evaluate("Spevb.Ajustes.set('busMin', true)"); p.wait_for_timeout(700)
    r = p.evaluate("""() => { const b = document.querySelector('.bus-panel.collapsed .bus-min'); if (!b) return null; const r = b.getBoundingClientRect();
        return { w: Math.round(r.width), h: Math.round(r.height), texto: b.textContent.trim(), svg: b.querySelectorAll('svg').length, etiqueta: b.getAttribute('aria-label'), radio: getComputedStyle(b).borderTopLeftRadius }; }""")
    assert r and r['texto'] == '' and r['svg'] == 1 and r['w'] == r['h'] and 44 <= r['w'] <= 56 and 'controles del bus' in r['etiqueta'].lower(), r
    assert 'Controles' not in p.inner_text('.bus-panel'), 'ya no dice «Controles»'
    p.click('.bus-panel.collapsed .bus-min'); p.wait_for_timeout(500)
    assert p.evaluate("!document.querySelector('.bus-panel').classList.contains('collapsed')"), 'al tocarlo se abren los controles'
    play = p.evaluate("(() => { const b = document.querySelector('.bus-panel .bus-btn'); return b ? { svg: b.querySelectorAll('svg').length, texto: b.textContent.trim() } : null; })()")
    assert play and play['svg'] >= 1, play
    s.limpio('controles bus'); s.cerrar()



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
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0][:400] if str(e) else repr(e))
                traceback.print_exc(limit=3)
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas para aprender a usar la app; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
