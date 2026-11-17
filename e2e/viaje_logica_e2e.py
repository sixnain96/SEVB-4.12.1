"""Pruebas de la LÓGICA del «Modo viaje» (viaje-nucleo.js) con recorridos GPS simulados, sin subirse a ningún bus.

El navegador real ejecuta el núcleo con lecturas generadas por e2e/simulador_gps.js (caminar → esperar → bus → bajar → caminar, con ruido,
saltos, lecturas malas, semáforos, túneles y transbordo). Todo es determinista: las lecturas llevan su propia marca de tiempo, así que un viaje
de 15 minutos se prueba en milisegundos. Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/viaje_logica_e2e.py [filtro]
"""
import math
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')      # la consola de Windows (cp1252) no admite todos los símbolos de los mensajes
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
PRUEBAS = []


def prueba(f):
    PRUEBAS.append(f)
    return f


def linea(n, lng0=-73.6500, lat0=4.1500, paso=0.0005, onda=0.0004):
    return [[lng0 + i * paso, lat0 + onda * math.sin(i / 6)] for i in range(n)]


def punto(c):
    return {'lat': c[1], 'lng': c[0]}


def plan_directo():
    t = linea(49)                                               # ≈ 2,6 km de recorrido del bus
    return {'origen': {'lat': 4.1478, 'lng': -73.6556}, 'destino': {'lat': 4.1524, 'lng': -73.6250},
            'buses': [{'codigo': 'M01', 'nombre': 'Ruta de prueba', 'color': '#176650', 'subida': punto(t[0]), 'bajada': punto(t[-1]), 'tramo': t}]}


def plan_transbordo():
    t1 = linea(30)
    t2 = [[-73.6330 + i * 0.0005, 4.1545 - 0.0003 * math.sin(i / 5)] for i in range(40)]
    return {'origen': {'lat': 4.1478, 'lng': -73.6556}, 'destino': {'lat': 4.1560, 'lng': -73.6100},
            'buses': [{'codigo': 'M01', 'nombre': 'Primera', 'color': '#176650', 'subida': punto(t1[0]), 'bajada': punto(t1[-1]), 'tramo': t1},
                      {'codigo': 'M02', 'nombre': 'Segunda', 'color': '#1e5fbf', 'subida': punto(t2[0]), 'bajada': punto(t2[-1]), 'tramo': t2}]}


JS = """([plan, op, ruido, resp, cfg]) => {
    const base = SimGps.viaje(plan, op || {});
    const l = ruido ? SimGps.ruido(base, ruido) : base;
    const r = SimGps.correr(plan, l, resp || {}, cfg);
    return { seq: SimGps.secuencia(r.eventos), eventos: r.eventos, fase: r.info.fase, n: l.length, tipos: base.map((x) => x.tipo) };
}"""


def sesion(nav):
    s = B.Sesion(nav)
    s.ctx.add_init_script(path=os.path.join(AQUI, 'simulador_gps.js'))
    return s, s.abrir()


def simular(p, plan, op=None, ruido=None, resp=None, cfg=None):
    return p.evaluate(JS, [plan, op, ruido, resp, cfg])


DIRECTO = ['fase:caminar', 'fase:esperando', 'pregunta:subida', 'fase:en_bus', 'alerta:cerca', 'alerta:preparate', 'alerta:ahora', 'pregunta:bajada', 'fase:caminar_final', 'fase:llegaste', 'llego']


def sin_ruido_de_fase(seq):
    """Quita los eventos de ida y vuelta caminar↔esperando (legítimos al acercarse al paradero) para comparar el flujo."""
    return [x for x in seq if x not in ('desvio',)]


# ---------------------------------------------------------------------------------------------- el recorrido completo
@prueba
def viaje_directo_ideal_recorre_todas_las_fases_en_orden(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo())
    assert r['seq'] == DIRECTO, r['seq']
    assert r['fase'] == 'llegaste'
    s.limpio('viaje ideal'); s.cerrar()


@prueba
def con_un_gps_ruidoso_el_flujo_es_el_mismo_y_no_hay_preguntas_de_mas(nav):
    s, p = sesion(nav)
    for semilla, sigma in ((1, 8), (2, 12), (3, 15)):
        n = p.evaluate("([plan]) => SimGps.viaje(plan, {}).length", [plan_directo()])
        r = simular(p, plan_directo(), ruido={'sigma': sigma, 'semilla': semilla, 'saltos': [40, 400, 900], 'malas': list(range(100, n, 23))})
        assert r['seq'] == DIRECTO, f'sigma {sigma}: {r["seq"]}'
    s.limpio('gps ruidoso'); s.cerrar()


@prueba
def la_aceleracion_y_el_frenado_del_bus_no_confunden_las_fases(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo(), op={'vBus': 4.5, 'vCamina': 1.1}, ruido={'sigma': 6, 'semilla': 5})        # bus lento (16 km/h) y peatón lento
    assert r['seq'] == DIRECTO, r['seq']
    r = simular(p, plan_directo(), op={'vBus': 12}, ruido={'sigma': 6, 'semilla': 6})                          # bus rápido (43 km/h)
    assert r['seq'] == DIRECTO, r['seq']
    s.cerrar()


# ---------------------------------------------------------------------------------------------- falsos positivos y silencios
@prueba
def un_dispositivo_que_informa_velocidad_cero_siempre_no_resta_velocidad_real(nav):
    """El emulador de Android entrega coords.speed = 0 aunque la posición se mueva (verificado con `dumpsys location`: vel=0.0)."""
    s, p = sesion(nav)
    r = p.evaluate("""([plan]) => {
        const salida = {};
        for (const [nombre, op] of [['normal', {}], ['bus lento', { vBus: 4.5 }], ['peaton lento', { vCamina: 0.9 }]]) {
            const l = SimGps.ruido(SimGps.viaje(plan, op), { sigma: 6, semilla: 3 }).map((x) => ({ ...x, velocidad: 0 }));
            salida[nombre] = SimGps.secuencia(SimGps.correr(plan, l, {}).eventos);
        }
        return salida; }""", [plan_directo()])
    for nombre, seq in r.items():
        assert seq == DIRECTO, f'{nombre} con velocidad informada = 0: {seq}'
    s.cerrar()


@prueba
def caminar_o_esperar_mucho_tiempo_nunca_pregunta_si_te_subiste(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo(), op={'esperaSeg': 420}, ruido={'sigma': 10, 'semilla': 9}, resp={'subida': False})
    previos = sum(1 for t in r['tipos'] if t in ('caminar', 'espera'))           # lecturas de caminar y esperar (7 minutos quieto incluidos)
    preguntas = [e for e in r['eventos'] if e['tipo'] == 'pregunta' and e['id'] == 'subida']
    assert preguntas and preguntas[0]['i'] >= previos, f'ninguna pregunta mientras camina o espera: primera en {preguntas[0]["i"]}, el bus arranca en {previos}'
    # aunque se conteste «no» siempre, las preguntas siguientes respetan el silencio de 90 s
    huecos = [b['i'] - a['i'] for a, b in zip(preguntas, preguntas[1:])]
    assert all(h >= 90 for h in huecos), huecos
    s.cerrar()


@prueba
def ir_rapido_pero_lejos_de_la_ruta_no_dispara_la_pregunta(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    lejos = p.evaluate("""([plan]) => { const kx = 111320 * Math.cos(4.15 * Math.PI / 180), ky = 110574;
        const pts = plan.buses[0].tramo.map((c) => ({ lat: c[1] - 600 / ky, lng: c[0] }));
        return SimGps.recorrer(pts, () => 7, 1, { t: 1700000000000 }, 'carro'); }""", [plan])
    r = p.evaluate("""([plan, l]) => { const r = SimGps.correr(plan, l, {}); return { seq: SimGps.secuencia(r.eventos), fase: r.info.fase }; }""", [plan, lejos])
    assert 'pregunta:subida' not in r['seq'] and r['fase'] in ('caminar', 'esperando'), r
    s.cerrar()


@prueba
def responder_que_no_silencia_la_pregunta_un_tiempo_y_vuelve_a_preguntar(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo(), resp={'subida': [False, True]})
    preguntas = [e for e in r['eventos'] if e['tipo'] == 'pregunta' and e['id'] == 'subida']
    assert len(preguntas) == 2, f'pregunta, se responde «no» y, pasado el silencio de 90 s, vuelve a preguntar: {len(preguntas)}'
    assert preguntas[1]['i'] > preguntas[0]['i'] + 80, 'no repite la pregunta de inmediato'
    assert r['fase'] == 'llegaste'
    s.cerrar()


@prueba
def un_semaforo_o_un_atasco_dentro_del_bus_no_se_toma_por_haberse_bajado(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo(), op={'semaforos': [{'avance': 700, 'seg': 40}, {'avance': 1500, 'seg': 25}, {'avance': 2250, 'seg': 90}]}, ruido={'sigma': 8, 'semilla': 11})
    assert r['seq'].count('pregunta:bajada') == 1 and r['seq'] == DIRECTO, r['seq']
    s.cerrar()


@prueba
def una_pregunta_sin_respuesta_se_retira_sola_cuando_la_situacion_cambia(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    # arranca como un bus (pregunta) pero se detiene y camina de vuelta: nadie contesta
    r = p.evaluate("""([plan]) => {
        const t = plan.buses[0].tramo, st = { t: 1700000000000 };
        const sub = { lat: t[0][1], lng: t[0][0] };
        const l = [...SimGps.quieto(sub, 30, 1, st, 'espera'),
                   ...SimGps.recorrer([sub, { lat: t[2][1], lng: t[2][0] }], (m) => Math.min(7, 1 + m / 6), 1, st, 'bus'),
                   ...SimGps.quieto({ lat: t[2][1], lng: t[2][0] }, 60, 1, st, 'espera')];
        const r = SimGps.correr(plan, l, { ignorar: true });
        return { seq: SimGps.secuencia(r.eventos), fase: r.info.fase, pregunta: r.info.pregunta }; }""", [plan])
    assert 'pregunta:subida' in r['seq'] and 'pregunta_retirada' in r['seq'], r
    assert r['pregunta'] is None
    s.cerrar()


# ---------------------------------------------------------------------------------------------- alertas, pasarse, señal
@prueba
def las_alertas_de_bajada_llegan_una_sola_vez_y_en_orden_con_distancias_decrecientes(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo(), ruido={'sigma': 7, 'semilla': 3})
    alertas = [e for e in r['eventos'] if e['tipo'] == 'alerta']
    assert [a['nivel'] for a in alertas] == ['cerca', 'preparate', 'ahora'], alertas
    d = [a['distancia'] for a in alertas]
    assert d[0] > d[1] > d[2] and 250 < d[0] <= 520 and 90 < d[1] <= 220 and d[2] <= 80, d
    s.cerrar()


@prueba
def si_el_bus_se_pasa_de_la_parada_avisa_y_no_asume_que_bajaste(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    # el bus sigue 600 m más allá de la bajada prevista
    r = p.evaluate("""([plan]) => {
        const t = plan.buses[0].tramo, st = { t: 1700000000000 };
        const ext = [...t, ...Array.from({ length: 12 }, (_, i) => [t[t.length - 1][0] + (i + 1) * 0.0005, t[t.length - 1][1]])];
        const larga = { ...plan, buses: [{ ...plan.buses[0], tramo: ext }] };
        const l = SimGps.viaje(larga, {});
        const r = SimGps.correr(plan, l, {});
        return { seq: SimGps.secuencia(r.eventos), fase: r.info.fase }; }""", [plan])
    assert 'se_paso' in r['seq'], r
    assert r['seq'].index('se_paso') > r['seq'].index('alerta:ahora')
    s.cerrar()


@prueba
def un_tunel_sin_senal_no_rompe_el_viaje_y_se_avisa_al_volver(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    tipos = simular(p, plan)['tipos']
    ini = tipos.index('bus') + 100                              # a los 100 s de ir en el bus
    r = simular(p, plan, ruido={'sigma': 6, 'semilla': 4, 'huecos': [[ini, ini + 70]]})
    assert 'senal_recuperada' in r['seq'], r['seq']
    assert [x for x in r['seq'] if x != 'senal_recuperada'] == DIRECTO, r['seq']
    s.cerrar()


@prueba
def solo_lecturas_malas_avisan_senal_debil_y_no_cambian_de_fase(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    r = p.evaluate("""([plan]) => {
        const st = { t: 1700000000000 }, v = SimGps.quieto(plan.origen, 3, 1, st, 'x');
        const malas = SimGps.quieto(plan.origen, 20, 1, st, 'x').map((l) => ({ ...l, precision: 300 }));
        const c = SimGps.correr(plan, [...v, ...malas], {});
        return { tipos: c.eventos.map((e) => e.tipo + (e.motivo ? ':' + e.motivo : '')), fase: c.info.fase }; }""", [plan])
    assert 'senal_debil' in r['tipos'] and r['fase'] in ('caminar', 'iniciando'), r
    s.cerrar()


@prueba
def si_la_parada_de_bajada_es_el_destino_pregunta_y_al_confirmar_llega(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    plan['destino'] = dict(plan['buses'][0]['bajada'])                      # no hay nada que caminar después del bus
    r = simular(p, plan, op={'paradaSeg': 40}, ruido={'sigma': 7, 'semilla': 12})
    assert r['seq'] == DIRECTO, r['seq']
    s.cerrar()


# ---------------------------------------------------------------------------------------------- transbordo y casos de borde
@prueba
def con_transbordo_repite_el_flujo_para_el_segundo_bus(nav):
    s, p = sesion(nav)
    r = simular(p, plan_transbordo(), ruido={'sigma': 7, 'semilla': 8})
    esperado = ['fase:caminar', 'fase:esperando', 'pregunta:subida', 'fase:en_bus', 'alerta:cerca', 'alerta:preparate', 'alerta:ahora', 'pregunta:bajada',
                'fase:caminar', 'fase:esperando', 'pregunta:subida', 'fase:en_bus', 'alerta:cerca', 'alerta:preparate', 'alerta:ahora', 'pregunta:bajada',
                'fase:caminar_final', 'fase:llegaste', 'llego']
    assert [x for x in r['seq'] if x != 'desvio'] == esperado, r['seq']
    cambios = [e for e in r['eventos'] if e['tipo'] == 'fase' and e['fase'] == 'caminar' and e.get('transbordo')]
    assert len(cambios) == 1
    s.cerrar()


@prueba
def empezar_ya_en_el_paradero_pasa_directo_a_esperar(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    r = simular(p, plan, op={'empezarEn': plan['buses'][0]['subida']})
    assert r['seq'][0] == 'fase:esperando' and r['seq'][-1] == 'llego', r['seq']
    s.cerrar()


@prueba
def lecturas_invalidas_repetidas_o_desordenadas_no_rompen_el_viaje(nav):
    s, p = sesion(nav)
    plan = plan_directo()
    r = p.evaluate("""([plan]) => {
        const l = SimGps.viaje(plan, {});
        const sucias = [];
        l.forEach((x, i) => { sucias.push(x); if (i % 17 === 0) sucias.push(x); if (i % 29 === 0) sucias.push({ ...x, t: x.t - 5000 });
                              if (i % 41 === 0) sucias.push({ lat: NaN, lng: x.lng, precision: 5, t: x.t + 1 }); if (i % 53 === 0) sucias.push({ ...x, precision: undefined, t: x.t + 2 }); });
        const c = SimGps.correr(plan, sucias, {});
        return { seq: SimGps.secuencia(c.eventos), motivos: [...new Set(c.eventos.filter((e) => e.tipo === 'descartada').map((e) => e.motivo))] }; }""", [plan])
    assert r['seq'] == DIRECTO, r['seq']
    assert set(r['motivos']) >= {'repetida', 'invalida', 'imprecisa'}, r['motivos']
    s.cerrar()


@prueba
def el_estado_se_guarda_y_se_restaura_en_la_misma_fase(nav):
    s, p = sesion(nav)
    plan = plan_transbordo()
    r = p.evaluate("""([plan]) => {
        const l = SimGps.viaje(plan, {});
        const media = l.findIndex((x) => x.tipo === 'camina_cambio') + 60;
        const c = SimGps.correr(plan, l.slice(0, media), {});
        const x = JSON.parse(JSON.stringify(c.v.serializar()));
        const v2 = Spevb.ViajeNucleo.crearViaje(plan); v2.restaurar(x);
        return { x, info: v2.info() }; }""", [plan])
    assert r['x']['fase'] == 'caminar' and r['x']['leg'] == 1 and r['info']['leg'] == 1 and r['info']['codigo'] == 'M02', r
    s.cerrar()


# ---------------------------------------------------------------------------------------------- 4.15.1: alertas por recorrido y confirmación manual
def plan_con_retorno():
    """Tramo en «U»: 1200 m al este, sube 60 m y regresa 600 m al oeste. El punto de bajada queda a 60 m EN LÍNEA RECTA de la mitad de la ida,
    pero a más de 1,2 km por el recorrido. Es el caso de un bus que pasa cerca de la bajada mucho antes de llegar a ella."""
    kx, ky, lng0, lat0 = 111040.0, 110574.0, -73.6500, 4.1500
    pts = [(0, 0), (1200, 0), (1200, 60), (600, 60)]
    t = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 25))
        for i in range(n):
            t.append([lng0 + (x0 + (x1 - x0) * i / n) / kx, lat0 + (y0 + (y1 - y0) * i / n) / ky])
    t.append([lng0 + 600 / kx, lat0 + 60 / ky])
    return {'origen': {'lat': lat0, 'lng': lng0}, 'destino': {'lat': lat0 + 60 / ky, 'lng': lng0 + 500 / kx},
            'buses': [{'codigo': 'M09', 'nombre': 'Ruta con retorno', 'color': '#176650', 'subida': punto(t[0]), 'bajada': punto(t[-1]), 'tramo': t}]}


@prueba
def un_bus_que_pasa_cerca_de_la_bajada_antes_de_llegar_no_dispara_avisos_urgentes(nav):
    s, p = sesion(nav)
    plan = plan_con_retorno()
    r = p.evaluate("""([plan]) => {
        const base = SimGps.viaje(plan, {}), l = SimGps.ruido(base, { sigma: 5, semilla: 11 });
        const res = SimGps.correr(plan, l, {});
        return { seq: SimGps.secuencia(res.eventos), eventos: res.eventos, lat: l.map((x) => x.lat) }; }""", [plan])
    alertas = [e for e in r['eventos'] if e['tipo'] == 'alerta']
    assert [a['nivel'] for a in alertas] == ['cerca', 'preparate', 'ahora'], alertas
    assert 'se_paso' not in r['seq'], r['seq']
    # El primer aviso llega en el tramo de regreso (a 60 m al norte), no al pasar a 60 m en línea recta por la ida.
    primera = alertas[0]
    assert (r['lat'][primera['i']] - 4.15) * 110574.0 > 30, f"primer aviso demasiado pronto: lectura {primera['i']}"
    assert 250 < primera['distancia'] <= 520, primera


@prueba
def el_texto_de_bajada_no_manda_bajar_con_el_bus_en_movimiento(nav):
    s, p = sesion(nav)
    r = simular(p, plan_directo(), ruido={'sigma': 6, 'semilla': 5})
    textos = [e.get('texto', '') for e in r['eventos'] if e['tipo'] == 'alerta']
    assert len(textos) == 3, textos
    assert 'Te acercas a tu punto de bajada' in textos[0], textos
    assert 'Prepárate para bajar' in textos[1], textos
    assert 'Baja cuando el bus se detenga' in textos[2] and 'Bájate ahora' not in ' '.join(textos), textos
    s.cerrar()


@prueba
def la_confirmacion_manual_usa_las_transiciones_del_nucleo_y_no_duplica_estados(nav):
    s, p = sesion(nav)
    r = p.evaluate("""([plan]) => {
        const v = Spevb.ViajeNucleo.crearViaje(plan), base = SimGps.viaje(plan, {}), out = {};
        out.sinLectura = v.confirmarSubida().length;
        for (const l of base) { v.procesar(l); if (v.info().fase === 'esperando') break; }
        out.faseAntes = v.info().fase;
        out.bajadaAntes = v.confirmarBajada().length;
        const a = v.confirmarSubida(); out.fase1 = v.info().fase; out.ev1 = a.map((e) => e.tipo + ':' + (e.fase || ''));
        out.otraVez = v.confirmarSubida().length;
        out.pregunta = v.info().pregunta;
        const b = v.confirmarBajada(); out.fase2 = v.info().fase; out.ev2 = b.map((e) => e.tipo + ':' + (e.fase || ''));
        out.bajadaOtraVez = v.confirmarBajada().length;
        return out; }""", [plan_directo()])
    assert r['sinLectura'] == 0 and r['faseAntes'] == 'esperando' and r['bajadaAntes'] == 0, r
    assert r['fase1'] == 'en_bus' and r['ev1'] == ['fase:en_bus'] and r['otraVez'] == 0 and r['pregunta'] is None, r
    assert r['fase2'] == 'caminar_final' and r['ev2'] == ['fase:caminar_final'] and r['bajadaOtraVez'] == 0, r
    s.cerrar()


@prueba
def con_transbordo_la_confirmacion_manual_pasa_al_segundo_bus_y_reinicia_sus_avisos(nav):
    s, p = sesion(nav)
    r = p.evaluate("""([plan]) => {
        const v = Spevb.ViajeNucleo.crearViaje(plan), base = SimGps.viaje(plan, {});
        for (const l of base) { v.procesar(l); if (v.info().fase === 'esperando') break; }
        v.confirmarSubida(); v.confirmarBajada();
        const i = v.info();
        return { fase: i.fase, leg: i.leg, etiqueta: i.etiqueta, alertas: i.alertas }; }""", [plan_transbordo()])
    assert r['fase'] == 'caminar' and r['leg'] == 1 and r['etiqueta'] == 'M02', r
    assert r['alertas'] == {'cerca': False, 'preparate': False, 'ahora': False}, r
    s.cerrar()


# ---------------------------------------------------------------------------------------------- el filtro de lecturas
@prueba
def el_filtro_descarta_lo_imprecio_los_saltos_aislados_y_acepta_un_salto_confirmado(nav):
    s, p = sesion(nav)
    r = p.evaluate("""() => {
        const F = new Spevb.ViajeNucleo.FiltroLecturas(); const t0 = 1700000000000;
        const lec = (i, lat, lng, acc = 8) => ({ lat, lng, precision: acc, t: t0 + i * 1000 });
        const res = {};
        for (let i = 0; i < 6; i++) F.procesar(lec(i, 4.15, -73.65));
        res.mala = F.procesar(lec(6, 4.15, -73.65, 400)).motivo;
        res.salto = F.procesar(lec(7, 4.1560, -73.6440)).motivo;                       // ≈ 800 m en 1 s
        res.vuelve = F.procesar(lec(8, 4.15, -73.65)).ok;                               // la lectura siguiente es normal: el salto fue ruido
        const G = new Spevb.ViajeNucleo.FiltroLecturas();
        for (let i = 0; i < 6; i++) G.procesar(lec(i, 4.15, -73.65));
        const tres = [7, 8, 9].map((i) => G.procesar(lec(i, 4.16, -73.64)));            // tres lecturas seguidas en otro sitio: el cambio es real
        res.confirmado = tres.map((x) => x.ok);
        return res; }""")
    assert r['mala'] == 'imprecisa' and r['salto'] == 'salto' and r['vuelve'] is True, r
    assert r['confirmado'] == [False, False, True], r
    s.cerrar()


@prueba
def el_filtro_estabiliza_un_punto_quieto_y_mide_bien_la_velocidad(nav):
    s, p = sesion(nav)
    r = p.evaluate("""() => {
        const sim = SimGps.ruido(SimGps.quieto({ lat: 4.15, lng: -73.65 }, 120, 1, { t: 1700000000000 }, 'q'), { sigma: 8, semilla: 7 });
        const F = new Spevb.ViajeNucleo.FiltroLecturas(); const out = sim.map((l) => F.procesar(l)).filter((x) => x.ok).map((x) => x.lectura);
        const dist = Spevb.ViajeNucleo.dist, c = { lat: 4.15, lng: -73.65 };
        const quieto = out.slice(20);
        const crudo = sim.slice(20).map((l) => dist(c, l));
        // movimiento a 7 m/s
        const st = { t: 1700000000000 }, pts = [{ lat: 4.15, lng: -73.65 }, { lat: 4.15, lng: -73.62 }];
        const mov = SimGps.ruido(SimGps.recorrer(pts, () => 7, 1, st, 'b'), { sigma: 6, semilla: 8 });
        const G = new Spevb.ViajeNucleo.FiltroLecturas(); const v = mov.map((l) => G.procesar(l)).filter((x) => x.ok).map((x) => x.lectura.vel);
        return { maxQuieto: Math.max(...quieto.map((l) => dist(c, l))), maxCrudo: Math.max(...crudo), velQuieto: Math.max(...quieto.map((l) => l.vel)), vMov: v.slice(30, 300) }; }""")
    assert r['maxQuieto'] < r['maxCrudo'] * 0.6, f'el punto filtrado tiembla bastante menos que el crudo: {r}'
    assert r['velQuieto'] < 0.7, 'parado no marca velocidad'
    media = sum(r['vMov']) / len(r['vMov'])
    assert 6.0 <= media <= 7.8, f'velocidad media a 7 m/s: {media}'
    s.cerrar()


@prueba
def la_proyeccion_sobre_la_ruta_da_avance_y_distancia(nav):
    s, p = sesion(nav)
    r = p.evaluate("""() => {
        const N = Spevb.ViajeNucleo, l = N.prepararLinea([[-73.65, 4.15], [-73.64, 4.15], [-73.64, 4.16]]);
        const a = N.proyectar(l, { lat: 4.1503, lng: -73.645 }), b = N.proyectar(l, { lat: 4.155, lng: -73.6395 });
        return { total: l.total, a, b }; }""")
    assert 2150 < r['total'] < 2300, r
    assert 20 < r['a']['dist'] < 45 and 540 < r['a']['avance'] < 580, r
    assert r['b']['dist'] < 60 and r['b']['avance'] > r['total'] * 0.7, r
    s.cerrar()


# ---------------------------------------------------------------------------------------------- Fase A: desvío del bus y «tu parada quedó atrás» (caso R006 / KIRPAS)
# Plano local en metros (SimGps.R006): la ruta corre 5 km al este con una ondulación de ±8 m; el pasajero sube en x = 600 y baja en x = 3000 (la parada). Umbrales por defecto (CFG):
# sale a > 150 m de la línea, vuelve a < 60 m; confirma el desvío con 3 lecturas / 15 s y se mueve; confirma el retorno con 4 lecturas / 12 s / 60 m de avance por la ruta, precisión ≤ 35 m,
# separación ≥ 30 m frente a otros tramos y un margen mínimo de 20 m (o 1,5 × la imprecisión) por encima de la parada. Sin referencia posterior a la bajada NO se afirma que la parada quedó atrás.
RUN_JS = """([caso, op]) => {
    const R = SimGps.R006, N = Spevb.ViajeNucleo, o = op || {}, plan = o.plan || R.plan();
    const xOf = (p) => (p.lng + 73.65) * R.KX;
    // Trayecto del bus: ruta hasta `salida`, sube `alto` m al norte, avanza en paralelo hasta `retorno` y baja a la ruta; sigue hasta `hasta`.
    const desvio = (salida, retorno, hasta, alto = 400) => R.unir(R.ruta(600, salida), R.recta([salida, 0], [salida, alto]), R.recta([salida, alto], [retorno, alto]), R.recta([retorno, alto], [retorno, R.yRuta(retorno)]), R.ruta(retorno, hasta));
    const salida = (x = 1800, alto = 400) => [R.ruta(600, x), R.recta([x, R.yRuta(x)], [x, alto])];
    const T = {
        normal: () => R.ruta(600, 3000),
        pasaDeLargo: () => R.ruta(600, 3700),
        antes: () => desvio(1000, 1600, 3000),
        r006: () => desvio(1800, 3600, 5000),
        r006Corto: () => desvio(1800, 3600, 4200),
        zona: () => desvio(1800, o.retorno || 2975, o.hasta || 3400),
        breve: () => R.unir(R.ruta(600, 1800), R.recta([1800, 0], [1800, 158]), R.recta([1800, 158], [1800, 0]), R.ruta(1800, 3000)),
        paralela: () => R.unir(...salida(), R.recta([1800, 400], [2400, 400]), R.recta([2400, 400], [2600, 80]), R.recta([2600, 80], [5000, 80])),
        paralela70: () => R.unir(...salida(), R.recta([1800, 400], [2400, 400]), R.recta([2400, 400], [2600, 70]), R.recta([2600, 70], [5000, 70])),
        cruce: () => R.unir(...salida(), R.recta([1800, 400], [3300, 400]), R.recta([3300, 400], [3300, -400]), R.recta([3300, -400], [5000, -400])),
        bucle: () => R.unir(...salida(), R.recta([1800, 400], [3100, 400]), R.recta([3100, 400], [3100, -100]), R.recta([3100, -100], [3300, -100]), R.recta([3300, -100], [3300, 400]), R.recta([3300, 400], [5000, 400])),
        contrario: () => R.unir(...salida(), R.recta([1800, 400], [3800, 400]), R.recta([3800, 400], [3800, R.yRuta(3800)]), R.ruta(3800, 3300), R.recta([3300, R.yRuta(3300)], [3300, 400]), R.recta([3300, 400], [5000, 400])),
        pasaCerca: () => desvio(2700, 4300, 5000, 200),
        dosDesvios: () => R.unir(desvio(1800, 3600, 4200), R.recta([4200, R.yRuta(4200)], [4200, 400]), R.recta([4200, 400], [4800, 400]), R.recta([4800, 400], [4800, R.yRuta(4800)]), R.ruta(4800, 5000)),
    };
    const tray = T[caso](), refOpts = o.refOpts || {};
    let l = SimGps.viajeLibre(plan, tray, { sinCaminarFinal: o.sinCaminarFinal !== false, vBus: o.vBus, paradas: o.semaforo ? [{ i: tray.findIndex((q, k) => k > 60 && xOf(q) >= o.semaforo.x && Math.abs((q.lat - 4.15) * R.KY) < 20), seg: o.semaforo.seg }] : undefined, precision: o.precision, esperaSeg: 40 });
    if (o.aislado) { const k = l.findIndex((x) => x.tipo === 'bus' && xOf(x) >= o.aislado); l[k] = { ...l[k], lat: l[k].lat - 50 / R.KY }; }
    if (o.ruido) l = SimGps.ruido(l, o.ruido);
    const ref = o.sinRef ? null : R.referencia(plan, refOpts);
    const capturas = {};
    const alLeer = (i, v) => { const inf = v.info(); if (inf.fase !== 'en_bus') return; const e = inf.desvio.estado; if (!capturas[e]) capturas[e] = { i, instruccion: inf.instruccion, distancia: inf.distancia, etaMin: inf.etaMin, estimacion: inf.estimacion, desvio: inf.desvio }; };
    const r = SimGps.correr(plan, l, { alLeer, bajada: o.bajada }, o.cfg, ref ? [ref] : undefined);
    const idx = (tipo) => r.eventos.findIndex((e) => e.tipo === tipo);
    const out = { seq: SimGps.secuencia(r.eventos), eventos: r.eventos.filter((e) => !['progreso', 'descartada'].includes(e.tipo)).map((e) => ({ tipo: e.tipo, i: e.i, t: e.t, nivel: e.nivel, motivo: e.motivo, texto: e.texto, estado: e.estadoDesvio, incidente: e.incidente })),
        traza: r.traza, n: l.length, estadoFinal: r.info.desvio.estado, infoFinal: r.info.desvio, capturas, ref: ref && { ok: ref.ok, motivo: ref.motivo, a: ref.a, b: ref.b, despues: ref.despues },
        t: l.map((x) => x.t), x: l.map(xOf), y: l.map((x) => (x.lat - 4.15) * R.KY) };
    const ia = idx('parada_atras');
    if (ia >= 0 && ref && ref.ok) {
        const lin = N.prepararLinea(ref.coords), i = r.eventos[ia].i;
        out.avancesAtras = [i - 3, i - 2, i - 1, i].map((k) => N.proyectar(lin, l[k]).avance);
    }
    return out;
}"""


def correr_desvio(p, caso, **op):
    return p.evaluate(RUN_JS, [caso, op])


def sin(seq, *quitar):
    return [x for x in seq if x not in quitar]


@prueba
def la_referencia_del_recorrido_se_construye_y_se_rechaza_cuando_no_corresponde(nav):
    s, p = sesion(nav)
    r = p.evaluate("""() => {
        const R = SimGps.R006, N = Spevb.ViajeNucleo, plan = R.plan(), rec = R.recorrido(), tr = plan.buses[0].tramo, out = {};
        out.normal = N.construirReferencia(tr, rec, { sentidoRuta: 'IDA', sentidoViaje: 'SENTIDO_DEL_TRAZADO' });
        out.sinSentido = N.construirReferencia(tr, rec, {});                                       // sin dato de sentido se prueban los dos y solo cabe uno
        // el tramo va al revés del dibujo (sentido inverso): la referencia es la ruta invertida y el bus sigue hacia donde el dibujo empieza
        out.inverso = N.construirReferencia(tr.slice().reverse(), rec, { sentidoRuta: 'IDA', sentidoViaje: 'SENTIDO_INVERSO' });
        out.inversoMalDicho = N.construirReferencia(tr.slice().reverse(), rec, { sentidoRuta: 'IDA', sentidoViaje: 'SENTIDO_DEL_TRAZADO' });
        // la ruta cambió (o es otra): el tramo ya no está dentro de ella
        out.otra = N.construirReferencia(tr.map(([x, y]) => [x, y + 60 / R.KY]), rec, { sentidoRuta: 'IDA' });
        out.sinDatos = N.construirReferencia([], rec, {}); out.sinRecorrido = N.construirReferencia(tr, null, {}); out.corto = N.construirReferencia([tr[0], [tr[0][0] + 5 / R.KX, tr[0][1]]], rec, {});
        // ruta circular (un cuadrado de 2 km): el tramo cruza el cierre del lazo (B antes que A) y la referencia sigue más allá, con la vuelta duplicada
        const cuadro = [[0, 0], [500, 0], [500, 500], [0, 500], [0, 0]].flatMap(([x, y], k, a) => (k ? R.recta(a[k - 1], [x, y], 25).slice(1) : [R.local(x, y)])).map((q) => [q.lng, q.lat]);
        const tramoCierre = cuadro.slice(70).concat(cuadro.slice(1, 15));
        out.circular = N.construirReferencia(tramoCierre, cuadro, { sentidoRuta: 'CIRCULAR' });
        out.circularComoIda = N.construirReferencia(tramoCierre, cuadro, { sentidoRuta: 'IDA' });
        // calle repetida en el mismo sentido (el recorrido pasa dos veces por ella): no se elige una al azar
        const pts = [[0, 0], [1000, 0], [1000, 300], [0, 300], [0, 0], [1000, 0], [2000, 0]];
        const doble = pts.flatMap(([x, y], k, a) => (k ? R.recta(a[k - 1], [x, y], 25).slice(1) : [R.local(x, y)])).map((q) => [q.lng, q.lat]);
        const ida = R.recta([200, 0], [800, 0], 25).map((q) => [q.lng, q.lat]);
        out.repetida = N.construirReferencia(ida, doble, { sentidoRuta: 'IDA', sentidoViaje: 'SENTIDO_DEL_TRAZADO' });
        const unica = R.recta([1200, 0], [1900, 0], 25).map((q) => [q.lng, q.lat]);
        out.noRepetida = N.construirReferencia(unica, doble, { sentidoRuta: 'IDA', sentidoViaje: 'SENTIDO_DEL_TRAZADO' });
        return out; }""")
    n = r['normal']
    assert n['ok'] and abs(n['a'] - 600) < 5 and abs(n['b'] - 3000) < 5 and n['despues'] > 1900, r['normal'] and {k: n.get(k) for k in ('ok', 'motivo', 'a', 'b', 'despues')}
    assert r['sinSentido']['ok'] and abs(r['sinSentido']['a'] - 600) < 5, 'sin dato de sentido se prueban los dos y solo uno encaja'
    inv = r['inverso']
    assert inv['ok'] and inv['invertida'] and abs(inv['a'] - (inv['total'] - 3000)) < 5 and abs(inv['b'] - (inv['total'] - 600)) < 5, {k: inv.get(k) for k in ('ok', 'motivo', 'a', 'b', 'total', 'invertida')}
    assert not r['inversoMalDicho']['ok'] and r['inversoMalDicho']['motivo'] == 'no-coincide', 'el sentido informado por el plan se respeta: un tramo al revés de lo dicho no encaja'
    assert not r['otra']['ok'] and r['otra']['motivo'] == 'no-coincide', r['otra']
    assert (r['sinDatos']['motivo'], r['sinRecorrido']['motivo'], r['corto']['motivo']) == ('sin-datos', 'sin-datos', 'tramo-corto'), (r['sinDatos'], r['sinRecorrido'], r['corto'])
    c = r['circular']
    assert c['ok'] and c['circular'] and c['b'] > c['a'] and c['despues'] > 100 and c['total'] > 3000, {k: c.get(k) for k in ('ok', 'motivo', 'a', 'b', 'total', 'circular', 'despues')}
    assert not r['circularComoIda']['ok'], 'un tramo que cruza el cierre del lazo solo existe en una ruta circular'
    assert not r['repetida']['ok'] and r['repetida']['motivo'] == 'ambigua', f"calle repetida en el mismo sentido: ambigua, no se elige una: {r['repetida']}"
    assert r['noRepetida']['ok'] and r['noRepetida']['a'] > 2000, 'la parte que no se repite sí se identifica'
    s.limpio('referencia'); s.cerrar()


@prueba
def sale_y_vuelve_antes_de_la_bajada_el_aviso_se_retira_y_las_alertas_son_las_normales(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'antes', sinCaminarFinal=False)
    seq = sin(r['seq'], 'desvio')
    esperado = ['fase:caminar', 'fase:esperando', 'pregunta:subida', 'fase:en_bus', 'desvio_posible', 'desvio_confirmado', 'desvio_largo', 'desvio_fin:retomo_antes', 'alerta:cerca', 'alerta:preparate', 'alerta:ahora', 'pregunta:bajada', 'fase:caminar_final', 'fase:llegaste', 'llego']
    assert seq == esperado, seq
    assert 'parada_atras' not in seq and 'se_paso' not in seq, seq
    pos, conf = r['capturas']['posible'], r['capturas']['confirmado']
    assert 'apartado de la ruta' in pos['instruccion'] and 'Todo va bien' not in pos['instruccion'], pos
    assert 'se desvió de la ruta habitual' in conf['instruccion'] and 'Te aviso si retoma la ruta y ya pasó tu bajada' in conf['instruccion'], conf
    assert r['estadoFinal'] == 'normal' and r['traza'].count('confirmado') > 20, 'el desvío duró un buen rato y terminó'
    # durante el desvío no hay alertas de bajada: las normales salen después, con la ruta recuperada
    i_fin = next(e['i'] for e in r['eventos'] if e['tipo'] == 'desvio_fin')
    assert all(e['i'] > i_fin for e in r['eventos'] if e['tipo'] == 'alerta'), r['eventos']
    s.limpio('antes'); s.cerrar()


@prueba
def r006_sale_por_la_calle_en_obras_y_retoma_la_ruta_despues_de_la_bajada(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'r006')
    assert r['ref']['ok'], r['ref']
    seq = sin(r['seq'], 'desvio')
    assert seq == ['fase:caminar', 'fase:esperando', 'pregunta:subida', 'fase:en_bus', 'desvio_posible', 'desvio_confirmado', 'desvio_largo', 'parada_atras'], seq
    assert r['seq'].count('parada_atras') == 1 and 'se_paso' not in seq and 'alerta:ahora' not in seq, 'una sola alerta, y ninguna «Tu bajada está aquí» ni «te pasaste» por el mismo hecho'
    ev = {e['tipo']: e for e in r['eventos'] if e['tipo'].startswith('desvio') or e['tipo'] == 'parada_atras'}
    # tiempos: «posible» en cuanto se aparta; «confirmado» ≥ 15 s después con 3 lecturas fuera; «parada atrás» solo tras el retorno real (4 lecturas, ≥ 12 s)
    assert ev['desvio_confirmado']['t'] - ev['desvio_posible']['t'] >= 15000, ev
    assert ev['desvio_largo']['t'] - ev['desvio_posible']['t'] >= 120000, ev
    # el dato que demuestra que la parada quedó atrás: las 4 lecturas que lo confirman están SOBRE la referencia y más allá de la bajada + margen (20 m)
    b = r['ref']['b']
    assert min(r['avancesAtras']) >= b + 20, f"avances {r['avancesAtras']} frente a la bajada en {b}"
    assert r['avancesAtras'] == sorted(r['avancesAtras']), 'y avanzan en el sentido de la ruta'
    # en el momento de la parada atrás el bus ya está de vuelta sobre la ruta (y ≈ 0), no sobre la calle paralela (y = 400)
    i_atras = ev['parada_atras']['i']
    assert abs(r['y'][i_atras]) < 30 and r['x'][i_atras] > 3600, (r['x'][i_atras], r['y'][i_atras])
    assert r['estadoFinal'] == 'atras' and r['infoFinal']['paradaAtras'] and r['infoFinal']['estado'] == 'atras'
    assert ev['parada_atras']['texto'] == 'El bus retomó la ruta después de tu bajada. Baja en la próxima parada, cuando el bus se detenga.'
    s.limpio('r006'); s.cerrar()


@prueba
def mientras_hay_incertidumbre_la_tarjeta_no_dice_todo_va_bien_y_la_estimacion_es_incierta(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'r006')
    for estado in ('posible', 'confirmado', 'atras'):
        c = r['capturas'][estado]
        assert 'Todo va bien' not in c['instruccion'], (estado, c['instruccion'])
        assert c['estimacion'] == 'incierta' and c['distancia'] is None and c['etaMin'] is None and c['desvio']['incierta'], (estado, c)
    assert 'Estamos comprobando el recorrido' in r['capturas']['posible']['instruccion']
    assert r['capturas']['confirmado']['desvio']['referencia'] == 'lista'
    assert 'Todo va bien' in correr_desvio(p, 'normal')['capturas']['normal']['instruccion'], 'sin desvío sigue diciendo lo de siempre'
    s.cerrar()


@prueba
def un_desvio_largo_ofrece_preguntar_al_conductor_y_uno_breve_no_se_confirma(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'r006')
    largo = next(e for e in r['eventos'] if e['tipo'] == 'desvio_largo')
    assert largo['texto'] == 'Pregunta al conductor si pasa por tu parada.', largo
    b = correr_desvio(p, 'breve', vBus=10)      # se aparta apenas 158 m y vuelve enseguida: menos de 15 s «fuera»
    assert 'desvio_confirmado' not in b['seq'] and 'desvio_largo' not in b['seq'], b['seq']
    assert 'desvio_posible' in b['seq'] and 'desvio_fin:regreso' in b['seq'], f"una salida breve queda en «posible» y el aviso se retira solo: {b['seq']}"
    assert b['estadoFinal'] == 'normal'
    s.cerrar()


@prueba
def vuelve_dentro_de_la_zona_de_bajada_y_se_mantiene_la_alerta_ordinaria(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'zona', retorno=2975, hasta=3400)
    assert 'parada_atras' not in r['seq'], f"volvió a 25 m ANTES de la parada: no se afirma que quedó atrás: {r['seq']}"
    assert 'desvio_fin:retomo_antes' in r['seq'] and 'alerta:ahora' in r['seq'], r['seq']
    assert r['seq'].index('desvio_fin:retomo_antes') < r['seq'].index('alerta:ahora'), 'la alerta ordinaria sale con el recorrido ya recuperado'
    assert 'Todo va bien' not in r['capturas']['confirmado']['instruccion']
    # volver claramente después (a 300 m) sí es «atrás»
    d = correr_desvio(p, 'zona', retorno=3300, hasta=3900)
    assert 'parada_atras' in d['seq'] and 'alerta:ahora' not in d['seq'], d['seq']
    s.limpio('zona'); s.cerrar()


@prueba
def sin_la_referencia_del_recorrido_el_caso_se_mantiene_sin_confirmar(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'r006', sinRef=True)
    assert 'desvio_confirmado' in r['seq'], 'el desvío mismo se detecta con el tramo'
    assert 'parada_atras' not in r['seq'] and r['estadoFinal'] == 'confirmado', f"sin recorrido posterior a la bajada no se concluye nada: {r['seq']}"
    assert r['infoFinal']['referencia'] == 'pendiente', r['infoFinal']
    # volver ANTES del final del tramo sí se puede afirmar con el tramo solo
    a = correr_desvio(p, 'antes', sinRef=True)
    assert 'desvio_fin:retomo_antes' in a['seq'] and 'parada_atras' not in a['seq'], a['seq']
    s.cerrar()


@prueba
def una_referencia_que_no_coincide_o_es_ambigua_deja_la_incertidumbre(nav):
    s, p = sesion(nav)
    for motivo, opciones in (('no-coincide', {'sentidoViaje': 'SENTIDO_INVERSO'}),):
        r = p.evaluate("""([opciones]) => { const R = SimGps.R006, plan = R.plan(); const ref = R.referencia(plan, opciones);
            const v = Spevb.ViajeNucleo.crearViaje(plan); const ok = v.ponerReferencia(0, ref); return { ok, ref: v.referencia(0), motivo: ref.motivo }; }""", [opciones])
        assert not r['ok'] and r['ref']['estado'] == motivo and r['motivo'] == motivo, r
    s.cerrar()


@prueba
def un_punto_aislado_mala_precision_via_paralela_cruce_bucle_o_sentido_contrario_no_confirman_el_retorno(nav):
    s, p = sesion(nav)
    casos = {
        'paralela a 80 m': dict(caso='paralela'),
        'paralela a 70 m con un punto aislado sobre la ruta': dict(caso='paralela70', aislado=4000),
        'cruce perpendicular de la ruta': dict(caso='cruce'),
        'bucle que cruza la ruta dos veces': dict(caso='bucle'),
        'sentido contrario sobre la propia ruta': dict(caso='contrario'),
    }
    for nombre, op in casos.items():
        caso = op.pop('caso')
        r = correr_desvio(p, caso, **op)
        assert 'desvio_confirmado' in r['seq'], (nombre, r['seq'])
        assert 'parada_atras' not in r['seq'] and 'desvio_fin:retomo_antes' not in r['seq'] and r['estadoFinal'] == 'confirmado', (nombre, r['seq'], r['estadoFinal'])
    # mala precisión: el mismo retorno que SÍ se confirma con precisión normal, no se confirma si la imprecisión supera el umbral configurado
    buena = correr_desvio(p, 'r006')
    mala = correr_desvio(p, 'r006', precision=45, cfg={'RETORNO_PRECISION_MAX': 12})
    assert 'parada_atras' in buena['seq'], buena['seq']
    assert 'desvio_confirmado' in mala['seq'] and 'parada_atras' not in mala['seq'] and mala['estadoFinal'] == 'confirmado', mala['seq']
    s.limpio('falsos positivos'); s.cerrar()


@prueba
def gps_perdido_y_recuperado_semaforo_y_bus_lento_exigen_evidencia_nueva_y_terminan_confirmando(nav):
    s, p = sesion(nav)
    base = correr_desvio(p, 'r006')
    i_atras = next(e['i'] for e in base['eventos'] if e['tipo'] == 'parada_atras')
    # hueco de GPS de 35 s justo antes de confirmar: la racha se rompe; hacen falta lecturas NUEVAS después del hueco (≥ 4, ≥ 12 s, ≥ 60 m)
    ini = i_atras - 6
    con_hueco = correr_desvio(p, 'r006', ruido={'sigma': 0.01, 'semilla': 1, 'huecos': [[ini, ini + 35]]})
    ia = next(e for e in con_hueco['eventos'] if e['tipo'] == 'parada_atras')
    assert 'senal_recuperada' in con_hueco['seq'], con_hueco['seq']
    primera_nueva = ini  # el índice de la primera lectura posterior al hueco en la lista con huecos
    assert ia['t'] - con_hueco['t'][primera_nueva] >= 12000, f"la confirmación usa solo lecturas posteriores al hueco: {ia['t'] - con_hueco['t'][primera_nueva]} ms"
    assert con_hueco['seq'].count('parada_atras') == 1
    # semáforo de 90 s EN la zona de reincorporación (justo después de volver a la ruta): detenido no avanza, no confirma; al arrancar sí
    sem = correr_desvio(p, 'r006', semaforo={'x': 3640, 'seg': 90})
    ev = {e['tipo']: e for e in sem['eventos']}
    assert 'parada_atras' in ev, sem['seq']
    quietas = [k for k in range(len(sem['x'])) if 3630 <= sem['x'][k] <= 3660 and abs(sem['y'][k]) < 20]
    assert ev['parada_atras']['i'] > quietas[-1] - 5, 'no confirma mientras el semáforo lo tiene detenido'
    # bus lento (4,2 m/s ≈ 15 km/h, apenas por encima del umbral de «va en un bus»): tarda más pero confirma
    lento = correr_desvio(p, 'r006', vBus=4.2)
    assert 'desvio_confirmado' in lento['seq'] and 'parada_atras' in lento['seq'] and lento['seq'].count('parada_atras') == 1, lento['seq']
    s.limpio('hueco semaforo lento'); s.cerrar()


@prueba
def la_alerta_urgente_sale_una_sola_vez_por_incidente_aunque_el_bus_siga_o_se_desvie_otra_vez(nav):
    s, p = sesion(nav)
    r = correr_desvio(p, 'dosDesvios')
    assert r['seq'].count('parada_atras') == 1 and r['seq'].count('desvio_posible') == 1, r['seq']
    assert r['estadoFinal'] == 'atras' and r['infoFinal']['atrasEmitido']
    s.cerrar()


@prueba
def el_aviso_de_te_pasaste_de_un_viaje_normal_se_mantiene_y_no_se_toma_por_un_desvio(nav):
    s, p = sesion(nav)
    for sin_ref in (False, True):
        r = correr_desvio(p, 'pasaDeLargo', sinRef=sin_ref)
        assert 'se_paso' in r['seq'] and 'alerta:ahora' in r['seq'], (sin_ref, r['seq'])
        assert not any(x.startswith('desvio') or x == 'parada_atras' for x in r['seq']), f"seguir por su recorrido habitual (con o sin referencia) no es un desvío: {r['seq']}"
    # pasar cerca de la parada por una calle del desvío NO dispara «te pasaste» por distancia directa
    c = correr_desvio(p, 'pasaCerca', sinRef=True)
    assert 'desvio_confirmado' in c['seq'] and 'se_paso' not in c['seq'] and 'alerta:ahora' not in c['seq'], c['seq']
    s.limpio('te pasaste'); s.cerrar()


@prueba
def el_estado_del_desvio_se_guarda_minimo_y_al_reanudar_espera_lecturas_nuevas(nav):
    s, p = sesion(nav)
    r = p.evaluate("""() => {
        const R = SimGps.R006, N = Spevb.ViajeNucleo, plan = R.plan(), ref = R.referencia(plan), out = {};
        const tray = R.unir(R.ruta(600, 1800), R.recta([1800, 0], [1800, 400]), R.recta([1800, 400], [3600, 400]), R.recta([3600, 400], [3600, 0]), R.ruta(3600, 5000));
        const l = SimGps.viajeLibre(plan, tray, { sinCaminarFinal: true });
        const v = N.crearViaje(plan); v.ponerReferencia(0, ref);
        let iConf = -1, iAtras = -1;
        l.forEach((x, i) => { v.procesar(x).forEach((e) => { if (e.tipo === 'pregunta' && e.id === 'subida') v.responder('subida', true); if (e.tipo === 'desvio_confirmado') iConf = i; if (e.tipo === 'parada_atras') iAtras = i; }); if (i === iConf + 25 && iConf >= 0 && !out.guardadoConfirmado) out.guardadoConfirmado = JSON.parse(JSON.stringify(v.serializar())); });
        out.guardadoAtras = JSON.parse(JSON.stringify(v.serializar()));
        out.claves = Object.keys(out.guardadoAtras.dv || {});
        out.tamano = JSON.stringify(out.guardadoAtras).length;
        // estado de una versión anterior (sin «dv»): circulación normal
        const viejo = N.crearViaje(plan); viejo.restaurar({ fase: 'en_bus', leg: 0, alertas: { cerca: false, preparate: false, ahora: false }, avanceMax: 900, sePaso: false, velBus: 6 }); out.viejo = viejo.info().desvio.estado;
        // reanudar un desvío CONFIRMADO: conserva el estado, pero una lectura vieja o aislada no lo cierra; hacen falta lecturas nuevas y coherentes
        const w = N.crearViaje(plan); w.ponerReferencia(0, ref); w.restaurar(out.guardadoConfirmado);
        out.restConf = w.info().desvio.estado;
        const evs = []; const sobre = (x) => ({ lat: R.local(x, R.yRuta(x)).lat, lng: R.local(x, R.yRuta(x)).lng, precision: 6, t: 1800000000000 });
        let t = 1800000000000; for (let k = 0; k < 3; k++) { t += 1000; const q = sobre(3700 + k * 7); q.t = t; w.procesar(q).forEach((e) => evs.push(e.tipo)); }
        out.tras3 = { estado: w.info().desvio.estado, eventos: evs.filter((e) => e !== 'progreso') };
        // reanudar con la parada atrás: sigue «atrás» y NO repite la alerta urgente
        const z = N.crearViaje(plan); z.ponerReferencia(0, ref); z.restaurar(out.guardadoAtras);
        out.restAtras = z.info().desvio; const ev2 = []; t = 1800000100000; for (let k = 0; k < 8; k++) { t += 1000; const q = sobre(4200 + k * 7); q.t = t; z.procesar(q).forEach((e) => ev2.push(e.tipo)); }
        out.repiteAlerta = ev2.includes('parada_atras');
        return out; }""")
    assert r['guardadoConfirmado']['dv']['estado'] == 'confirmado' and r['guardadoAtras']['dv']['estado'] == 'atras', r
    assert set(r['claves']) <= {'estado', 'incidente', 'atrasEmitido', 'largo', 'sigo', 'ult'} and r['tamano'] < 400, f"solo el estado mínimo: {r['claves']} ({r['tamano']} bytes)"
    assert r['viejo'] == 'normal', 'un estado guardado por una versión anterior se acepta'
    assert r['restConf'] == 'confirmado' and r['tras3']['estado'] == 'confirmado' and 'parada_atras' not in r['tras3']['eventos'], f"una racha incompleta tras reanudar no concluye nada: {r['tras3']}"
    assert r['restAtras']['estado'] == 'atras' and r['restAtras']['atrasEmitido'] and not r['repiteAlerta'], r
    s.cerrar()


@prueba
def ya_me_baje_con_el_bus_desviado_entrega_la_posicion_real_y_el_siguiente_bus_reinicia_el_desvio(nav):
    s, p = sesion(nav)
    r = p.evaluate("""() => {
        const R = SimGps.R006, N = Spevb.ViajeNucleo, plan = R.plan();
        const t2 = R.tramo(3400, 4800), ll = (c) => ({ lat: c[1], lng: c[0] });
        plan.buses.push({ codigo: 'R007', etiqueta: 'R007', nombre: 'Segunda', color: '#1e5fbf', subida: ll(t2[0]), bajada: ll(t2[t2.length - 1]), tramo: t2 });
        plan.destino = R.local(5100, 100);
        const ref = R.referencia(plan);
        const tray = R.unir(R.ruta(600, 1800), R.recta([1800, 0], [1800, 400]), R.recta([1800, 400], [3600, 400]), R.recta([3600, 400], [3600, 0]), R.ruta(3600, 4200));
        const l = SimGps.viajeLibre(plan, tray, { sinCaminarFinal: true });
        const v = N.crearViaje(plan); v.ponerReferencia(0, ref);
        let ultima = null; l.forEach((x) => { v.procesar(x).forEach((e) => { if (e.tipo === 'pregunta' && e.id === 'subida') v.responder('subida', true); }); ultima = x; });
        const antes = v.info().desvio;
        const ev = v.confirmarBajada(), f = ev.find((e) => e.tipo === 'fase');
        const dm = N.dist({ lat: f.bajadaReal.lat, lng: f.bajadaReal.lng }, ultima);
        return { antes, fase: f.fase, leg: f.leg, transbordo: f.transbordo, desviada: f.desviada, estadoDesvio: f.estadoDesvio, distReal: dm, despues: v.info().desvio, infoLeg: v.info().leg }; }""")
    assert r['antes']['estado'] == 'atras', r
    assert r['fase'] == 'caminar' and r['transbordo'] and r['leg'] == 1 and r['desviada'] and r['estadoDesvio'] == 'atras', r
    assert r['distReal'] < 15, f"la bajada real es la última posición filtrada: {r['distReal']} m"
    assert r['despues']['estado'] == 'normal' and r['despues']['incidente'] == 0, 'cambiar de bus reinicia el desvío'
    # y una bajada normal NO marca «desviada» (las caminatas del plan siguen siendo las de siempre)
    n = p.evaluate("""() => { const R = SimGps.R006, N = Spevb.ViajeNucleo, plan = R.plan(), v = N.crearViaje(plan); v.ponerReferencia(0, R.referencia(plan));
        const l = SimGps.viajeLibre(plan, R.ruta(600, 3000), { sinCaminarFinal: true }); l.forEach((x) => v.procesar(x).forEach((e) => { if (e.tipo === 'pregunta' && e.id === 'subida') v.responder('subida', true); })); const f = v.confirmarBajada().find((e) => e.tipo === 'fase'); return { desviada: f.desviada, bajadaReal: f.bajadaReal }; }""")
    assert n['desviada'] is None and n['bajadaReal'] is None, n
    s.cerrar()


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
                print('FALLA ', f.__name__, '|', str(e).splitlines()[0][:600] if str(e) else repr(e))
                traceback.print_exc(limit=3)
        nav.close()
    print(f'\n{len(PRUEBAS) if not filtro else "?"} pruebas de la lógica del modo viaje; fallos: {len(fallos)} {fallos}')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
