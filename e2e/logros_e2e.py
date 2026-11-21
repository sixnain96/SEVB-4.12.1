"""Pruebas de navegador de logros, medallas y racha de viajes (Fase D).

Frontend real y backend stub (e2e/stub_server.py: mismas reglas que LogrosService/Racha.java), Google simulado como en cuenta_google_e2e.py y GPS simulado como en viaje_e2e.py.
Los vectores de la racha son LOS MISMOS que usa la prueba Java (src/test/resources/racha-vectores.json). El reloj de la aplicación es controlable (Spevb.Reloj).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/logros_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
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
import cuenta_google_e2e as G  # noqa: E402
import viaje_e2e as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PRUEBAS = []
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURAS = os.path.join(RAIZ, 'docs', 'capturas-viaje')
VECTORES = json.load(open(os.path.join(RAIZ, 'src', 'test', 'resources', 'racha-vectores.json'), encoding='utf-8'))
MOVIL = G.MOVIL


def prueba(f):
    PRUEBAS.append(f)
    return f


def bog(y, m, d, h=12, mi=0):
    """Milisegundos de un momento a la hora de Bogotá (UTC-5)."""
    import calendar
    return (calendar.timegm((y, m, d, h + 5, mi, 0)) * 1000)


def llegada(p, n, ms, subidas=1, extra=None):
    detalle = {'viajeId': 'viaje-%s' % n, 'llegadaMs': ms, 'subidas': subidas, 'busConfirmado': subidas > 0, 'buses': max(1, subidas), **(extra or {})}
    p.evaluate("(d) => window.dispatchEvent(new CustomEvent('spevb-viaje-llegada', { detail: d }))", detalle)


def fijar(p, ms):
    p.evaluate("(ms) => Spevb.Reloj.fijar(ms)", ms)


def estado(p):
    return p.evaluate("Spevb.Logros.leer()")


def invitado(nav, **opts):
    s = G.sesion(nav, **{**MOVIL, **opts})
    return s, s.abrir()


def con_ana(nav, sub='111', correo='ana@example.com', nombre='Ana Pérez', reiniciar=True, **opts):
    """Una sesión con Google simulado y la cuenta ya abierta. {@code reiniciar=False}: un SEGUNDO dispositivo de la misma cuenta (no borra lo que el servidor simulado ya guarda)."""
    s = G.sesion(nav, **{**MOVIL, **opts}) if reiniciar else B.Sesion(nav, **{**MOVIL, **opts})
    if not reiniciar:
        s.ctx.add_init_script(G.GSI_FALSO)
    p = s.abrir()
    G.entrar(p, sub, correo, nombre)
    return s, p


def hace_dias(n, hora=12):
    """Un mediodía de Bogotá de hace n días (dentro de la ventana que acepta el servidor y sin depender de la hora a la que se corra la prueba)."""
    import calendar
    hoy = time.gmtime(time.time() - 5 * 3600)
    base = calendar.timegm((hoy.tm_year, hoy.tm_mon, hoy.tm_mday, 0, 0, 0)) * 1000 - n * 86400000
    return base + (hora + 5) * 3600000


def foto(p, nombre):
    """Captura del menú con «Mis viajes y logros» a la vista y sin los avisos que se cruzan en la imagen."""
    p.evaluate("(() => { const t = document.getElementById('spevbToasts'); if (t) t.style.display = 'none'; document.getElementById('logros').scrollIntoView({ block: 'start' }); })()")
    p.wait_for_timeout(300)
    p.screenshot(path=os.path.join(CAPTURAS, nombre))
    p.evaluate("(() => { const t = document.getElementById('spevbToasts'); if (t) t.style.display = ''; })()")


def menu(p):
    if not p.evaluate("document.getElementById('sideMenu').classList.contains('open')"):
        p.click('#menuButton')
    p.wait_for_timeout(450)
    p.evaluate("document.getElementById('menuMas').open = true; document.getElementById('logros').open = true")


# ------------------------------------------------------------------------------------------------------------------------------------------- racha
@prueba
def los_vectores_compartidos_dan_lo_mismo_en_javascript_que_en_java(nav):
    s, p = invitado(nav)
    for v in VECTORES['rachas']:
        r = p.evaluate("([d, h]) => Spevb.Logros.racha(d, h)", [v['dias'], v['hoy']])
        assert (r['actual'], r['mejor'], r['estricta']) == (v['actual'], v['mejor'], v['estricta']), f"{v['nombre']}: {r}"
    for v in VECTORES['dias']:
        assert p.evaluate("(ms) => Spevb.Logros.diaDe(ms)", v['ms']) == v['dia'] and p.evaluate("(ms) => Spevb.Logros.horaDe(ms)", v['ms']) == v['hora'], v
    s.limpio('vectores'); s.cerrar()


@prueba
def la_racha_usa_dias_de_bogota_aunque_el_telefono_este_en_otra_zona(nav):
    resultados = []
    for zona in ('Asia/Tokyo', 'America/Los_Angeles', 'America/Bogota'):
        s, p = invitado(nav, timezone_id=zona)
        fijar(p, bog(2026, 3, 3, 23, 50))
        llegada(p, 'a', bog(2026, 3, 3, 23, 50))                 # martes 11:50 p. m. en Bogotá (miércoles por la mañana en Tokio)
        fijar(p, bog(2026, 3, 4, 0, 10))
        llegada(p, 'b', bog(2026, 3, 4, 0, 10))                  # pasó la medianoche de Bogotá: otro día
        e = estado(p)
        resultados.append((e['viajes'], e['racha'], e['ultimoDia']))
        s.limpio('zona ' + zona); s.cerrar()
    assert len(set(resultados)) == 1 and resultados[0] == (2, 2, '2026-03-04'), resultados


@prueba
def la_racha_sigue_con_un_dia_de_gracia_y_despues_baja_un_dia_por_dia(nav):
    s, p = invitado(nav)
    fijar(p, bog(2026, 3, 2)); llegada(p, 1, bog(2026, 3, 2))                    # lunes
    assert estado(p)['racha'] == 1
    fijar(p, bog(2026, 3, 4)); assert estado(p)['racha'] == 1, 'el miércoles aún se puede continuar'
    llegada(p, 2, bog(2026, 3, 4))                                               # miércoles
    assert estado(p)['racha'] == 2, 'lunes y miércoles: continúa'
    fijar(p, bog(2026, 3, 7)); assert estado(p)['racha'] == 1 and estado(p)['mejorRacha'] == 2, '4.17: pasado el margen la racha baja un día por día (2 → 1) y se conserva la mejor'
    llegada(p, 3, bog(2026, 3, 7)); llegada(p, 4, bog(2026, 3, 7, 13))
    e = estado(p)
    assert e['racha'] == 2 and e['viajes'] == 4, 'viajar de nuevo continúa desde lo que quedaba (1 + 1) y todos los viajes cuentan en el total'
    s.limpio('gracia'); s.cerrar()


@prueba
def cambio_de_mes_de_anio_y_bisiesto_no_rompen_la_racha(nav):
    s, p = invitado(nav)
    for i, (y, m, d) in enumerate([(2025, 12, 30), (2025, 12, 31), (2026, 1, 1), (2028, 2, 28), (2028, 2, 29), (2028, 3, 1)]):
        pass
    for n, (y, m, d) in enumerate([(2025, 12, 31), (2026, 1, 1), (2026, 1, 2)]):
        fijar(p, bog(y, m, d)); llegada(p, 'f%d' % n, bog(y, m, d))
    assert estado(p)['racha'] == 3
    s.cerrar()
    s2, p2 = invitado(nav)
    for n, (y, m, d) in enumerate([(2028, 2, 28), (2028, 2, 29), (2028, 3, 1)]):
        fijar(p2, bog(y, m, d)); llegada(p2, 'b%d' % n, bog(y, m, d))
    assert estado(p2)['racha'] == 3, 'febrero bisiesto'
    s2.limpio('mes y anio'); s2.cerrar()


@prueba
def un_viaje_tardio_o_fuera_de_orden_ordena_la_racha_sin_duplicar(nav):
    s, p = invitado(nav)
    fijar(p, bog(2026, 3, 10, 18))
    llegada(p, 'x10', bog(2026, 3, 10)); llegada(p, 'x08', bog(2026, 3, 8)); llegada(p, 'x09', bog(2026, 3, 9)); llegada(p, 'x09', bog(2026, 3, 9))
    e = estado(p)
    assert e['viajes'] == 3 and e['racha'] == 3 and 'racha3' in e['hitos'], e
    s.limpio('fuera de orden'); s.cerrar()


@prueba
def el_menu_se_actualiza_al_cruzar_la_medianoche_sin_recargar(nav):
    s, p = invitado(nav)
    fijar(p, bog(2026, 3, 2, 22)); llegada(p, 'm1', bog(2026, 3, 2, 22))
    menu(p)
    assert p.inner_text('#rachaTexto') == 'Racha de 1 día'
    p.evaluate("Spevb.Reloj.avanzar(3 * 86400000)")                                # pasan tres días: la racha vigente vuelve a 0
    p.evaluate("Spevb.Logros.revisar()")
    assert p.inner_text('#rachaTexto') == 'Empieza tu racha con tu próximo viaje', p.inner_text('#rachaTexto')
    assert 'Mejor racha: 1 día' in p.inner_text('#rachaDetalle')
    s.limpio('medianoche'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- qué cuenta como viaje
@prueba
def solo_una_llegada_real_con_subida_confirmada_suma_y_repetirla_no(nav):
    s, p = invitado(nav)
    llegada(p, 'ok1', int(time.time() * 1000), subidas=1)
    assert estado(p)['viajes'] == 1
    llegada(p, 'ok1', int(time.time() * 1000), subidas=1); llegada(p, 'ok1', int(time.time() * 1000), subidas=1)
    assert estado(p)['viajes'] == 1, 'el mismo id no cuenta dos veces (toques, pestañas, eventos repetidos)'
    llegada(p, 'sin-bus', int(time.time() * 1000), subidas=0)
    assert estado(p)['viajes'] == 1, 'sin subida confirmada no cuenta'
    p.evaluate("window.dispatchEvent(new CustomEvent('spevb-viaje-llegada', { detail: { buses: 1 } }))")
    assert estado(p)['viajes'] == 1, 'un evento sin id ni hora no cuenta'
    s.limpio('solo llegadas'); s.cerrar()


@prueba
def el_viaje_real_cuenta_una_vez_al_llegar_y_cerrar_recargar_o_abandonar_no_suman(nav):
    s = V.sesion(nav, **V.MOVIL)
    s.ctx.add_init_script(G.GSI_FALSO)
    p = s.abrir()
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p)
    vid = p.evaluate("Spevb.Viaje.viajeId()")
    assert vid and p.evaluate("Spevb.Viaje.evidencia().subidas") == 0
    V.viaje_completo(p, ls)
    assert V.card(p)['fase'] == 'llegaste'
    e = estado(p)
    assert e['viajes'] == 1 and 'primero' in e['hitos'], e
    p.click('#viajeTerminar'); p.wait_for_timeout(600)                         # «Cerrar» sobre una llegada ya registrada
    assert estado(p)['viajes'] == 1, '«Cerrar» no suma otro viaje'
    p.reload(wait_until='domcontentloaded'); B.esperar(p, "!!(window.Spevb && Spevb.maps && Spevb.maps.map)", 20000); p.wait_for_timeout(1200)
    assert estado(p)['viajes'] == 1, 'recargar no suma'
    # un viaje abandonado (terminado antes de llegar) no cuenta
    V.planear(p); V.destino_lejos(p)
    ls2 = V.lecturas(p, ruido={'sigma': 6, 'semilla': 4})
    V.iniciar(p); V.alimentar(p, ls2, 0, 'fase:esperando')
    p.evaluate("Spevb.Viaje.detener()"); p.wait_for_timeout(500)
    assert estado(p)['viajes'] == 1, 'abandonar no suma'
    s.limpio('viaje real'); s.cerrar()


@prueba
def el_transbordo_cuenta_un_solo_viaje_y_el_logro_se_gana_por_las_subidas_confirmadas(nav):
    s = V.sesion(nav, **V.MOVIL)
    p = s.abrir()
    V.planear(p, 'transbordos')
    p.evaluate("Spevb.Planner.seleccion.viaje.destino.lat += 0.003")
    ls = p.evaluate("""() => { const v = Spevb.Planner.seleccion.viaje, b = v.buses[0]; return SimGps.viaje(v, { empezarEn: { lat: b.subida.lat - 0.0022, lng: b.subida.lng } }); }""")
    V.iniciar(p)
    V.viaje_completo(p, ls)
    e = estado(p)
    assert e['viajes'] == 1 and e['transbordos'] == 1 and 'transbordo' in e['hitos'], e
    s.limpio('transbordo'); s.cerrar()


@prueba
def la_evidencia_de_subida_se_conserva_al_reanudar_y_al_recalcular_con_el_mismo_viaje(nav):
    s = V.sesion(nav, **V.MOVIL)
    p = s.abrir()
    V.planear(p); V.destino_lejos(p)
    ls = V.lecturas(p, ruido={'sigma': 6, 'semilla': 3})
    V.iniciar(p)
    i = V.alimentar(p, ls, 0, 'pregunta')
    assert V.card(p)['pregunta'], 'llegó la pregunta «¿te subiste?»'
    p.click('#viajeSi'); p.wait_for_timeout(300)
    ev = p.evaluate("Spevb.Viaje.evidencia()")
    assert ev['subidas'] == 1, ev
    id_antes = p.evaluate("Spevb.Viaje.id()")
    # reanudar: el estado guardado trae las subidas y el id lógico
    guardado = p.evaluate("JSON.parse(localStorage.getItem('spevb-viaje-activo') || localStorage.getItem(Object.keys(localStorage).find(k => /viaje/.test(k) && /activo|curso/.test(k)) || '') || 'null')")
    assert guardado is None or guardado.get('vid') == ev['viajeId'], guardado
    # recalcular: el viaje nuevo es otro recorrido pero el MISMO viaje para los logros
    V.abrir_mas(p)
    p.click('#viajeRecalcular')
    B.esperar(p, "document.getElementById('viajePregunta').dataset.id === 'recalculo'", 12000)
    p.click('#viajeSi'); p.wait_for_timeout(1200)
    despues = p.evaluate("Spevb.Viaje.evidencia()")
    assert despues['viajeId'] == ev['viajeId'] and despues['previas'] == 1, despues
    assert p.evaluate("Spevb.Viaje.id()") != id_antes, 'el recorrido nuevo tiene su propio id interno (compartir lo necesita)'
    s.limpio('evidencia'); s.cerrar()


@prueba
def el_estado_guardado_de_una_version_anterior_deduce_las_subidas_de_la_fase(nav):
    s, p = invitado(nav)
    V_plan = None
    r = p.evaluate("""() => {
        const bus = (n) => ({ codigo: 'R00' + n, nombre: 'Ruta ' + n, color: '#176650', subida: { lat: 4.14 + n * 0.01, lng: -73.64 }, bajada: { lat: 4.145 + n * 0.01, lng: -73.62 }, tramo: [[-73.64, 4.14 + n * 0.01], [-73.62, 4.145 + n * 0.01]] });
        const plan = { origen: { lat: 4.139, lng: -73.641 }, destino: { lat: 4.17, lng: -73.61 }, buses: [bus(1), bus(2)] };
        const sal = [];
        for (const [fase, leg] of [['en_bus', 0], ['caminar', 1], ['en_bus', 1], ['caminar_final', 1], ['caminar', 0]]) {
            const v = Spevb.ViajeNucleo.crearViaje(plan); v.restaurar({ fase, leg }); sal.push(v.subidas());
        }
        const v = Spevb.ViajeNucleo.crearViaje(plan); v.restaurar({ fase: 'en_bus', leg: 0, subidas: [0] });
        sal.push(JSON.stringify(v.serializar().subidas));
        return sal; }""")
    assert r == [1, 1, 2, 2, 0, '[0]'], r
    s.limpio('estado antiguo'); s.cerrar()


@prueba
def la_practica_da_aprendiz_pero_no_suma_viajes_ni_racha(nav):
    s, p = invitado(nav)
    p.evaluate("Spevb.Logros.marcarPractica()")
    e = estado(p)
    assert 'practica' in e['hitos'] and e['viajes'] == 0 and e['racha'] == 0, e
    menu(p)
    assert p.inner_text('#rachaTexto') == 'Empieza tu racha con tu próximo viaje' and p.get_attribute('#rachaChip', 'data-nivel') == '0'
    s.limpio('practica'); s.cerrar()


@prueba
def el_progreso_antiguo_del_dispositivo_se_conserva_para_el_invitado_y_no_pasa_a_la_cuenta(nav):
    s = G.sesion(nav, **MOVIL)
    hoy = time.strftime('%Y-%m-%d')
    s.ctx.add_init_script("try { if (!localStorage.getItem('__lg')) { localStorage.setItem('__lg', '1'); localStorage.setItem('spevb-logros', JSON.stringify({ viajes: 3, transbordos: 1, racha: 3, mejorRacha: 3, ultimoDia: '%s', hitos: ['primero', 'transbordo', 'racha3'], madrugador: false, nocturno: false, practica: false, registro: [] })); } } catch (e) {}" % hoy)
    p = s.abrir()
    e = estado(p)
    assert e['viajes'] == 3 and {'primero', 'transbordo', 'racha3'} <= set(e['hitos']), e
    G.entrar(p, '111', 'ana@example.com', 'Ana')
    p.wait_for_timeout(1200)
    assert estado(p)['viajes'] == 0 and estado(p)['hitos'] == [], 'la primera cuenta NO hereda el progreso del dispositivo'
    assert p.evaluate("!!localStorage.getItem('spevb-logros')"), 'el progreso antiguo sigue guardado en el dispositivo'
    p.click('#menuButton'); p.wait_for_timeout(400); p.click('#accountLogout'); p.wait_for_timeout(900)
    assert estado(p)['viajes'] == 3, 'al volver a invitado, vuelve lo suyo'
    s.limpio('legado'); s.cerrar()


@prueba
def los_logros_antiguos_de_racha_siguen_pidiendo_dias_consecutivos(nav):
    s, p = invitado(nav)
    for n, d in enumerate((1, 3, 5, 7)):                      # cuatro días ALTERNOS: racha con gracia de 4, pero ninguna «3 días seguidos»
        fijar(p, bog(2026, 3, d)); llegada(p, 'alt%d' % n, bog(2026, 3, d))
    e = estado(p)
    assert e['racha'] == 4 and 'racha3' not in e['hitos'], e
    for n, d in enumerate((8, 9)):
        fijar(p, bog(2026, 3, d)); llegada(p, 'seg%d' % n, bog(2026, 3, d))
    assert 'racha3' in estado(p)['hitos'], 'tres días seguidos de verdad'
    s.limpio('estricta'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- cuenta
@prueba
def con_sesion_el_progreso_es_de_la_cuenta_y_se_ve_igual_en_otro_dispositivo(nav):
    s1, p1 = con_ana(nav)
    ahora = int(time.time() * 1000)
    llegada(p1, 'cta1', ahora - 60000); p1.wait_for_timeout(1200)
    assert estado(p1)['viajes'] == 1 and 'primero' in estado(p1)['hitos']
    llegada(p1, 'cta1', ahora - 60000); p1.wait_for_timeout(800)
    assert estado(p1)['viajes'] == 1, 'reenviar el mismo viaje no lo duplica'
    s2, p2 = con_ana(nav, reiniciar=False)
    B.esperar(p2, "Spevb.Logros.leer().viajes === 1", 6000)
    llegada(p2, 'cta2', ahora - 30000); p2.wait_for_timeout(1200)
    p1.evaluate("Spevb.Logros.sincronizar()"); p1.wait_for_timeout(1000)
    assert estado(p1)['viajes'] == 2 and estado(p2)['viajes'] == 2, 'dos dispositivos, una cuenta: no se suman contadores, se suman viajes'
    s1.limpio('cuenta 1'); s2.limpio('cuenta 2'); s1.cerrar(); s2.cerrar()


@prueba
def dos_pestanas_con_la_misma_cuenta_reportan_el_mismo_viaje_y_cuenta_una_vez(nav):
    s, p = con_ana(nav)
    q = s.ctx.new_page(); q.goto(B.URL, wait_until='domcontentloaded'); B.esperar(q, "!!(window.Spevb && Spevb.maps && Spevb.maps.map && Spevb.Cuenta.usuario)", 20000); q.wait_for_timeout(800)
    ahora = int(time.time() * 1000)
    llegada(p, 'dos-pestanas', ahora - 5000); llegada(q, 'dos-pestanas', ahora - 5000)
    p.wait_for_timeout(1500)
    p.evaluate("Spevb.Logros.sincronizar()"); p.wait_for_timeout(800)
    assert estado(p)['viajes'] == 1, estado(p)
    s.limpio('pestanas'); s.cerrar()


@prueba
def sin_conexion_el_envio_queda_en_cola_y_se_reintenta_una_sola_vez(nav):
    s, p = con_ana(nav)
    posts = []
    p.on('request', lambda r: posts.append(r.url) if r.method == 'POST' and r.url.endswith('/api/cuenta/logros/viaje') else None)
    s.ctx.route('**/api/cuenta/logros/viaje', lambda r: r.abort())
    llegada(p, 'offline1', int(time.time() * 1000) - 1000); p.wait_for_timeout(1200)
    assert p.evaluate("Spevb.Logros.cola().length") == 1 and estado(p)['viajes'] == 0, 'sin conexión se encola y no se inventa nada'
    assert 'por sincronizar' in p.evaluate("document.getElementById('logrosPendiente').textContent")
    s.ctx.unroute('**/api/cuenta/logros/viaje')
    p.evaluate("window.dispatchEvent(new Event('online'))"); p.wait_for_timeout(1500)
    assert p.evaluate("Spevb.Logros.cola().length") == 0 and estado(p)['viajes'] == 1
    p.evaluate("Spevb.Logros.sincronizar()"); p.wait_for_timeout(600)
    assert estado(p)['viajes'] == 1
    s.errores = [e for e in s.errores if 'ERR_FAILED' not in e and 'Failed to load' not in e and 'net::' not in e]
    s.limpio('cola'); s.cerrar()


@prueba
def un_viaje_que_el_servidor_rechaza_se_descarta_sin_reintentar_para_siempre(nav):
    s, p = con_ana(nav)
    llegada(p, 'viejo1', int(time.time() * 1000) - 45 * 86400000)       # más de 30 días: el servidor dice que no
    p.wait_for_timeout(1500)
    assert p.evaluate("Spevb.Logros.cola().length") == 0 and estado(p)['viajes'] == 0
    s.errores = [e for e in s.errores if '400' not in e]
    s.limpio('rechazo'); s.cerrar()


@prueba
def al_cambiar_de_cuenta_se_limpia_la_vista_y_una_respuesta_vieja_no_aparece(nav):
    s, p = con_ana(nav)
    llegada(p, 'ana1', int(time.time() * 1000) - 2000); p.wait_for_timeout(1200)
    assert estado(p)['viajes'] == 1
    retenida = []
    s.ctx.route('**/api/cuenta/logros', lambda r: retenida.append(r))
    p.evaluate("Spevb.Logros.sincronizar()"); p.wait_for_timeout(600)
    s.ctx.unroute('**/api/cuenta/logros')
    p.click('#menuButton'); p.wait_for_timeout(400); p.click('#accountLogout'); p.wait_for_timeout(900)
    assert p.evaluate("localStorage.getItem('spevb-logros-cuenta')") is None and p.evaluate("localStorage.getItem('spevb-logros-cola')") is None, 'al salir no queda progreso de la cuenta en el navegador'
    G.entrar(p, '222', 'beto@example.com', 'Beto')
    for r in retenida:
        r.fulfill(status=200, content_type='application/json', body=json.dumps({'viajes': 9, 'transbordos': 0, 'rachaActual': 9, 'mejorRacha': 9, 'mejorEstricta': 9, 'madrugador': False, 'nocturno': False, 'practica': False, 'logros': ['primero'], 'insignia': None, 'hoy': '2026-03-01', 'ultimoDia': None, 'dias': [], 'nuevo': False, 'nuevos': []}))
    p.wait_for_timeout(900)
    assert estado(p)['viajes'] == 0, 'lo que llegó tarde de Ana no se le muestra a Beto'
    s.limpio('cambio de cuenta'); s.cerrar()


@prueba
def la_racha_baja_un_dia_por_cada_dia_sin_viajar_y_continua_desde_lo_que_quedaba(nav):
    s, p = invitado(nav)
    menu(p)
    for d in (1, 2, 3):
        fijar(p, bog(2026, 4, d)); llegada(p, 'g%d' % d, bog(2026, 4, d))
    assert p.inner_text('#rachaTexto') == 'Racha de 3 días'
    # lunes–miércoles de gracia: entera; después baja un día por día hasta 0 (no cae a 0 de golpe)
    for dia, texto in ((4, 'Racha de 3 días'), (5, 'Racha de 3 días'), (6, 'Racha de 2 días'), (7, 'Racha de 1 día'), (8, 'Empieza tu racha con tu próximo viaje')):
        fijar(p, bog(2026, 4, dia)); p.wait_for_timeout(80)
        assert p.inner_text('#rachaTexto') == texto, (dia, p.inner_text('#rachaTexto'))
    # volver antes de llegar a 0 continúa desde lo que quedaba: el día 7 valía 1 y al viajar suma 1 → 2 (no vuelve a 1)
    fijar(p, bog(2026, 4, 7)); llegada(p, 'g7', bog(2026, 4, 7)); p.wait_for_timeout(80)
    assert p.inner_text('#rachaTexto') == 'Racha de 2 días', p.inner_text('#rachaTexto')
    assert p.inner_text('#rachaChip .racha-num') == '2', 'el número grande acompaña al texto'
    s.limpio('racha gradual'); s.cerrar()


@prueba
def la_cuenta_de_demostracion_muestra_una_racha_estatica_que_baja_sola_y_se_puede_simular_en_la_presentacion(nav):
    import datetime
    s, p = con_ana(nav, sub='985', correo='demo@example.com', nombre='Cuenta Demo')
    menu(p)
    hoy = (datetime.datetime.utcnow() - datetime.timedelta(hours=5)).date()
    esperada = max(0, 30 - max(0, (hoy - datetime.date(2026, 11, 19)).days))
    p.evaluate("document.getElementById('logros').open = true"); p.wait_for_timeout(500)
    B.esperar(p, "!!Spevb.Logros.leer() && Spevb.Logros.leer().hitos.length >= 10", 6000)      # todos los logros desbloqueados
    txt = p.inner_text('#rachaTexto')
    assert txt == ('Racha de %d días' % esperada if esperada != 1 else 'Racha de 1 día') or esperada == 0, (txt, esperada)
    assert p.is_visible('#rachaSimular') and p.is_visible('#rachaSimMas'), 'el simulador de la presentación aparece solo en la cuenta de demostración'
    if esperada >= 3:
        p.click('#rachaSimMas'); p.wait_for_timeout(300)
        assert p.inner_text('#rachaTexto') == 'Racha de %d días' % (esperada - 1), p.inner_text('#rachaTexto')
        assert 'pasó 1 día' in p.inner_text('#rachaSimularTxt')
        p.click('#rachaSimMas'); p.click('#rachaSimMas'); p.wait_for_timeout(300)
        assert p.inner_text('#rachaTexto') == 'Racha de %d días' % (esperada - 3), 'cada día simulado quita uno'
        p.click('#rachaSimHoy'); p.wait_for_timeout(300)
        assert p.inner_text('#rachaTexto') == txt, 'volver a hoy'
    s.limpio('racha demo'); s.cerrar()
    # otra cuenta: sin simulador y con su racha normal
    s2, p2 = con_ana(nav)
    menu(p2)
    p2.evaluate("document.getElementById('logros').open = true"); p2.wait_for_timeout(300)
    assert not p2.is_visible('#rachaSimular'), 'las demás cuentas no ven el simulador'
    assert p2.inner_text('#rachaTexto') == 'Empieza tu racha con tu próximo viaje'
    s2.limpio('racha otra cuenta'); s2.cerrar()


@prueba
def la_cuenta_del_proyecto_muestra_31_dias_y_todos_los_logros_siempre_y_el_simulador_enseña_como_baja(nav):
    s, p = con_ana(nav, sub='777', correo='SebvAdmin@gmail.com', nombre='Admin SEVB')
    menu(p)
    p.evaluate("document.getElementById('logros').open = true"); p.wait_for_timeout(500)
    B.esperar(p, "Spevb.Logros.leer().hitos.length >= 10", 6000)
    assert p.inner_text('#rachaTexto') == 'Racha de 31 días', p.inner_text('#rachaTexto')
    assert p.inner_text('#rachaChip .racha-num') == '31'
    assert p.locator('#logrosLista .logro.ganado').count() == 10, 'todos los logros desbloqueados'
    p.click('#rachaSimMas'); p.wait_for_timeout(300)
    assert p.inner_text('#rachaTexto') == 'Racha de 30 días', 'el simulador enseña cómo baja'
    p.click('#rachaSimHoy'); p.wait_for_timeout(300)
    assert p.inner_text('#rachaTexto') == 'Racha de 31 días'
    s.limpio('cuenta del proyecto'); s.cerrar()


# ------------------------------------------------------------------------------------------------------------------------------------------- presentación y recompensas
@prueba
def el_menu_muestra_racha_llama_por_nivel_y_detalle_con_la_explicacion_del_dia_de_gracia(nav):
    s, p = invitado(nav)
    menu(p)
    assert p.inner_text('#rachaTexto') == 'Empieza tu racha con tu próximo viaje' and p.is_visible('#rachaChip')
    esperado = {1: ('llamaN1', 'Racha de 1 día'), 2: ('llamaN1', 'Racha de 2 días'), 3: ('llamaN2', 'Racha de 3 días'), 6: ('llamaN2', 'Racha de 6 días'), 7: ('llamaN3', 'Racha de 7 días'), 13: ('llamaN3', 'Racha de 13 días'), 14: ('llamaN4', 'Racha de 14 días')}
    dia = 0
    for n in range(1, 15):
        dia += 1
        fijar(p, bog(2026, 4, dia)); llegada(p, 'r%d' % n, bog(2026, 4, dia))
        if n in esperado:
            p.wait_for_timeout(60)
            assert p.inner_text('#rachaTexto') == esperado[n][1] and p.get_attribute('#rachaIcono', 'data-icono') == esperado[n][0], (n, p.inner_text('#rachaTexto'), p.get_attribute('#rachaIcono', 'data-icono'))
    assert 'Mejor racha: 14 días' in p.inner_text('#rachaDetalle') and 'Un día sin viajar no rompe tu racha' in p.inner_text('#rachaDetalle')
    ancho = p.evaluate("(() => { const c = document.getElementById('rachaChip').getBoundingClientRect(), i = document.getElementById('rachaIcono').getBoundingClientRect(); return { chip: c.height, icono: document.getElementById('rachaIcono').offsetHeight, mismaFila: Math.abs((i.top + i.height / 2) - (c.top + c.height / 2)) < 14 }; })()")
    assert ancho['mismaFila'] and ancho['icono'] <= 44, f'el icono cabe en la misma fila que el texto en todos los niveles (4.17: la llama es más grande): {ancho}'
    foto(p, 'logros-racha-menu-320.png')
    s.limpio('racha menu'); s.cerrar()


@prueba
def las_medallas_se_exploran_con_teclado_y_dicen_requisito_progreso_y_recompensa(nav):
    s, p = invitado(nav)
    fijar(p, bog(2026, 3, 2)); llegada(p, 'k1', bog(2026, 3, 2)); llegada(p, 'k2', bog(2026, 3, 2, 13))
    menu(p)
    botones = p.evaluate("[...document.querySelectorAll('#logrosLista .logro-boton')].map(b => ({ id: b.dataset.logro, aria: b.getAttribute('aria-label'), estado: b.querySelector('.logro-estado').textContent, icono: b.querySelector('svg').dataset.icono }))")
    assert [b['id'] for b in botones] == ['primero', 'cinco', 'veinte', 'transbordo', 'racha3', 'racha7', 'madrugador', 'noche', 'practica', 'llano'], botones
    por = {b['id']: b for b in botones}
    assert por['primero']['estado'] == 'Ganado' and por['cinco']['estado'] == 'Por conseguir' and por['cinco']['icono'] == 'candado'
    assert 'por conseguir' in por['cinco']['aria'] and 'ganado' in por['primero']['aria'], 'el estado se dice en texto, no solo con color'
    iconos = p.evaluate("[...document.querySelectorAll('.logro')].map(l => l.classList.contains('ganado'))")
    p.focus('#logrosLista .logro-boton[data-logro="cinco"]'); p.keyboard.press('Enter'); p.wait_for_timeout(200)
    d = p.inner_text('#logroDetalle')
    assert 'Por conseguir' in d and 'Termina 5 viajes' in d and 'Llevas 2 de 5' in d and 'Marco de ruta' in d, d
    p.focus('#logrosLista .logro-boton[data-logro="primero"]'); p.keyboard.press('Space'); p.wait_for_timeout(200)
    d = p.inner_text('#logroDetalle')
    assert 'Ganado' in d and 'Mi primer viaje' in d, d
    p.click('#logrosLista .logro-boton[data-logro="llano"]'); p.wait_for_timeout(200)
    assert 'Llevas 2 de 30 viajes y 1 de 7 días de racha' in p.inner_text('#logroDetalle'), p.inner_text('#logroDetalle')
    assert p.evaluate("document.getElementById('logroDetalle').getAttribute('aria-live')") == 'polite'
    nombres = p.evaluate("[...new Set([...document.querySelectorAll('#logrosLista svg')].map(s => s.dataset.icono))].length")
    assert nombres >= 2
    foto(p, 'logros-medallas-menu-320.png')
    s.limpio('medallas'); s.cerrar()


@prueba
def las_medallas_ganadas_se_destacan_en_el_perfil_y_solo_se_equipan_las_ganadas(nav):
    s, p = con_ana(nav)
    for n in range(5):
        llegada(p, 'eq%d' % n, hace_dias(n + 1))      # mediodías: sin «Madrugador» ni «De noche»
    p.wait_for_timeout(2500)
    assert estado(p)['viajes'] == 5 and {'primero', 'cinco'} <= set(estado(p)['hitos'])
    p.click('#menuButton'); p.wait_for_timeout(400); p.click('#accountSettings'); p.wait_for_timeout(500)
    filas = p.evaluate("[...document.querySelectorAll('#setMedallasLista .medalla-perfil')].map(l => l.querySelector('.logro-txt').textContent)")
    assert filas == ['Primer viaje', '5 viajes', '3 días seguidos'], filas      # cinco días seguidos también dan «3 días seguidos»
    p.click('#setMedallasLista .medalla-perfil:nth-child(2) button'); p.wait_for_timeout(900)
    assert p.get_attribute('#setAvatar', 'data-marco') == 'cinco' and p.get_attribute('#accountAvatar', 'data-insignia') == 'cinco', 'el marco de ruta se ve en la foto'
    assert p.get_attribute('#setMedallasLista .medalla-perfil:nth-child(2) button', 'aria-pressed') == 'true'
    p.screenshot(path=os.path.join(CAPTURAS, 'logros-perfil-marco-ruta.png'))
    p.click('#setMedallasLista .medalla-perfil:nth-child(1) button'); p.wait_for_timeout(900)
    assert p.get_attribute('#setAvatar', 'data-insignia') == 'primero' and p.get_attribute('#setAvatar', 'data-marco') is None, 'una sola insignia destacada a la vez'
    p.click('#setMedallasLista .medalla-perfil:nth-child(1) button'); p.wait_for_timeout(900)
    assert p.get_attribute('#setAvatar', 'data-insignia') is None, 'se puede quitar'
    # una insignia que no se ganó la rechaza el servidor
    assert p.evaluate("Spevb.Logros.equipar('llano')") is False
    assert p.get_attribute('#setAvatar', 'data-insignia') is None
    s.errores = [e for e in s.errores if '409' not in e]
    # y la insignia es de la cuenta: otro dispositivo la ve
    p.evaluate("Spevb.Logros.equipar('cinco')"); p.wait_for_timeout(800)
    s2, p2 = con_ana(nav, reiniciar=False)
    p2.wait_for_timeout(1200)
    assert p2.get_attribute('#accountAvatar', 'data-insignia') == 'cinco'
    s.limpio('perfil'); s2.limpio('perfil 2'); s.cerrar(); s2.cerrar()


@prueba
def una_llegada_con_logro_nuevo_da_una_sola_celebracion_agrupada(nav):
    s, p = con_ana(nav)
    llegada(p, 'cel1', int(time.time() * 1000) - 1000, subidas=2); p.wait_for_timeout(1500)
    textos = p.evaluate("[...document.querySelectorAll('#spevbToasts > *')].map(e => e.textContent).filter(t => /Llegaste/.test(t))")
    assert len(textos) == 1 and 'Primer viaje' in textos[0] and 'Con transbordo' in textos[0], textos
    llegada(p, 'cel2', int(time.time() * 1000) - 500)
    p.wait_for_timeout(1200)
    nuevos = p.evaluate("[...document.querySelectorAll('#spevbToasts > *')].map(e => e.textContent).filter(t => /Llegaste/.test(t))")
    assert len(nuevos) <= 1, 'sin nada nuevo no hay otra celebración'
    s.limpio('celebracion'); s.cerrar()


@prueba
def el_destello_de_nivel_tiene_version_fija_con_reducir_movimiento_y_la_racha_se_lee_con_el_sistema_en_modo_oscuro(nav):
    s, p = invitado(nav, reduced_motion='reduce', color_scheme='dark')
    fijar(p, bog(2026, 5, 1)); llegada(p, 'q1', bog(2026, 5, 1))
    fijar(p, bog(2026, 5, 2)); llegada(p, 'q2', bog(2026, 5, 2)); fijar(p, bog(2026, 5, 3)); llegada(p, 'q3', bog(2026, 5, 3))      # sube a nivel 2
    menu(p)
    p.evaluate("Spevb.Logros.revisar()"); p.wait_for_timeout(300)
    anim = p.evaluate("getComputedStyle(document.getElementById('rachaIcono'), '::after').animationName")
    assert anim == 'none', f'con reducir movimiento no hay animación: {anim}'
    assert p.evaluate("getComputedStyle(document.getElementById('rachaIcono'), '::after').opacity") == '1', 'queda un aro fijo como versión estática'
    # el menú de SEVB es siempre claro (solo las superficies sobre el mapa siguen el modo oscuro): la racha debe leerse sobre fondo claro
    color = p.evaluate("getComputedStyle(document.getElementById('rachaTexto')).color")
    fondo = p.evaluate("getComputedStyle(document.getElementById('sideMenu')).backgroundColor")
    assert color == 'rgb(138, 59, 0)' and fondo == 'rgb(255, 255, 255)', f'la racha se lee con el menú claro aunque el sistema esté en modo oscuro: {color} sobre {fondo}'
    foto(p, 'logros-racha-oscuro-320.png')
    s.limpio('movimiento'); s.cerrar()


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
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de logros, medallas y racha; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
