"""Pruebas de navegador de la ruta consumible (4.15): lo recorrido desaparece del mapa y solo queda lo pendiente.

Frontend real, backend stub (e2e/stub_server.py), GPS SIMULADO (e2e/simulador_gps.js). Las unidades puras (dividirLinea, posicionMonotona) se prueban dentro del navegador
porque el proyecto no usa Node. NO prueba una calle real ni un teléfono físico.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/ruta_consumible_e2e.py [filtro]      (lo normal es e2e/run_e2e.py)
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


def prueba(f):
    PRUEBAS.append(f)
    return f


def estado(p):
    return p.evaluate('Spevb.Viaje.rutaEstado()')


def hay_pregunta(p):
    return p.evaluate("!document.getElementById('viajePregunta').hidden")


def lineas_en_mapa(p):
    """Polilíneas visibles por grosor: 7 y 11 = ruta consumible; 8 y 13 = copia estática del planificador (no debe quedar debajo)."""
    return p.evaluate("""() => { const r = { viaje: 0, planificador: 0 }; Spevb.maps.map.elementos().forEach((e) => { if (e.tipo !== 'linea') return;
        if (e.peso === 7 || e.peso === 11) r.viaje++; if (e.peso === 8 || e.peso === 13) r.planificador++; }); return r; }""")


def empezar(nav, escenario='multi', **opts):
    s = V.sesion(nav, **opts)
    p = s.abrir()
    V.planear(p, escenario)
    V.destino_lejos(p)
    ls = V.lecturas(p)
    V.iniciar(p)
    return s, p, ls


# ---------------------------------------------------------------------------------------------- unidades puras
@prueba
def dividir_linea_en_todos_los_casos_y_sin_modificar_la_original(nav):
    s = V.sesion(nav)
    p = s.abrir()
    r = p.evaluate("""() => { const N = Spevb.ViajeNucleo, L = N.prepararLinea([[-73.63, 4.15], [-73.63, 4.151], [-73.63, 4.151], [-73.629, 4.151], [-73.629, 4.1525]]);
      const copia = JSON.stringify(L), t = L.total, out = {};
      const f = (a) => { const d = N.dividirLinea(L, a); return { rec: d.recorrida.length, pen: d.pendiente.length, corte: d.corte }; };
      out.antes = f(-5); out.cero = f(0); out.nan = f(NaN); out.fin = f(t); out.despues = f(t + 50);
      const mitad = N.dividirLinea(L, L.acum[1] / 2); out.interp = { lat: mitad.corte[0], lng: mitad.corte[1], enAmbas: JSON.stringify(mitad.recorrida[mitad.recorrida.length - 1]) === JSON.stringify(mitad.pendiente[0]) };
      const vert = N.dividirLinea(L, L.acum[3]); out.vertice = { rec: vert.recorrida.length, pen: vert.pendiente.length };
      const suma = (pts) => { let s = 0; for (let i = 1; i < pts.length; i++) s += N.dist({ lat: pts[i - 1][0], lng: pts[i - 1][1] }, { lat: pts[i][0], lng: pts[i][1] }); return s; };
      const k = N.dividirLinea(L, 123.4); out.largos = { rec: suma(k.recorrida), pen: suma(k.pendiente), total: t };
      const vacia = N.dividirLinea(N.prepararLinea([]), 10), una = N.dividirLinea(N.prepararLinea([[-73.6, 4.1]]), 10);
      out.vacia = vacia.pendiente.length + vacia.recorrida.length; out.una = { rec: una.recorrida.length, pen: una.pendiente.length };
      out.intacta = JSON.stringify(L) === copia; return out; }""")
    assert r['antes']['rec'] == 0 and r['antes']['pen'] == 5 and r['cero']['rec'] == 0 and r['nan']['rec'] == 0, r
    assert r['fin']['pen'] == 0 and r['fin']['rec'] == 5 and r['despues']['pen'] == 0, r
    assert abs(r['interp']['lat'] - 4.1505) < 1e-6 and abs(r['interp']['lng'] + 73.63) < 1e-9 and r['interp']['enAmbas'], f'corte interpolado exacto: {r["interp"]}'
    assert r['vertice']['pen'] >= 2 and r['vertice']['rec'] >= 2, r
    assert abs(r['largos']['rec'] - 123.4) < 0.5 and abs(r['largos']['rec'] + r['largos']['pen'] - r['largos']['total']) < 0.5, f'recorrida + pendiente = total: {r["largos"]}'
    assert r['vacia'] == 0 and r['una']['pen'] == 1 and r['una']['rec'] == 0 or r['una']['pen'] <= 1, r
    assert r['intacta'], 'dividir no modifica la línea original'
    s.limpio('dividir')
    s.cerrar()


@prueba
def la_posicion_monotona_no_retrocede_con_ruido_y_un_salto_exige_confirmacion(nav):
    s = V.sesion(nav)
    p = s.abrir()
    r = p.evaluate("""() => { const N = Spevb.ViajeNucleo, c = N.CFG, L = N.prepararLinea(Array.from({ length: 41 }, (_, i) => [-73.63, 4.15 + i * 0.0005]));
      const st = { avanceMax: 0, avanceT: null, avanceSalto: null }, at = (m) => ({ lat: 4.15 + m / 110574, lng: -73.63 });
      let t = 0; const lee = (m, dt = 1) => { t += dt * 1000; const r = N.posicionMonotona(L, st, { ...at(m), t }, c); if (r.enRuta) st.avanceMax = Math.max(st.avanceMax, r.avance); return r; };
      [0, 10, 25, 22, 40, 33, 60, 52, 80].forEach((m) => lee(m));
      const tras = st.avanceMax;
      lee(30); lee(10);
      const despuesRetro = st.avanceMax;
      const s1 = lee(1500), n1 = st.avanceMax;
      const s2 = lee(1502), n2 = st.avanceMax;
      const s3 = lee(1504), n3 = st.avanceMax;
      return { tras, despuesRetro, s1: s1.enRuta, n1, s2: s2.enRuta, n2, s3: s3.enRuta, n3 }; }""")
    assert 70 <= r['tras'] <= 90 and r['despuesRetro'] == r['tras'], f'el avance no retrocede: {r}'
    assert not r['s1'] and r['n1'] == r['tras'] and not r['s2'] and r['n2'] == r['tras'], f'un salto aislado no es avance: {r}'
    assert r['s3'] and r['n3'] > 1400, f'tres lecturas coherentes confirman el avance: {r}'
    s.limpio('monotona')
    s.cerrar()


# ---------------------------------------------------------------------------------------------- viaje simulado
@prueba
def al_iniciar_el_planificador_suelta_su_copia_y_solo_queda_la_ruta_del_viaje(nav):
    s = V.sesion(nav)
    p = s.abrir()
    V.planear(p)
    V.destino_lejos(p)
    antes = lineas_en_mapa(p)
    assert antes['planificador'] > 0, f'antes de iniciar el planificador dibuja su copia: {antes}'
    V.iniciar(p)
    p.wait_for_timeout(500)
    despues = lineas_en_mapa(p)
    assert despues['planificador'] == 0, f'no debe quedar una ruta completa estática debajo: {despues}'
    assert despues['viaje'] >= 2, f'la ruta consumible dibuja borde y color del bus: {despues}'
    e = estado(p)
    assert e and [x['tipo'] for x in e['etapas']] in (['caminata', 'bus', 'caminata'], ['caminata', 'bus', 'caminata', 'bus', 'caminata']), e
    s.limpio('traspaso')
    s.cerrar()


@prueba
def la_caminata_el_bus_y_la_caminata_final_se_consumen_en_orden_sin_saltos(nav):
    s, p, ls = empezar(nav, 'multi')
    avances, activas = [], []
    i = 0
    for _ in range(80):
        h = min(len(ls), i + 12)
        V.alimentar(p, ls[:h], i, 'pregunta')
        i = h
        e = estado(p)
        if e:
            avances.append([x['objetivo'] for x in e['etapas']])
            activas.append(e['activa'])
        if hay_pregunta(p):
            p.click('#viajeSi')
        if p.evaluate("document.getElementById('viajeCard').dataset.fase") == 'llegaste' or i >= len(ls):
            break
    p.wait_for_timeout(2200)
    e = estado(p)
    for k in range(len(e['etapas'])):
        serie = [a[k] for a in avances]
        assert serie == sorted(serie), f'la etapa {k} nunca retrocede: {serie}'
    assert all(a <= b for a, b in zip(activas, activas[1:])), f'las etapas se activan en orden: {activas}'
    assert e['activa'] == len(e['etapas']) and all(x['consumida'] and x['lineas'] == 0 for x in e['etapas']), f'al llegar todo queda consumido: {e}'
    assert lineas_en_mapa(p)['viaje'] == 0, 'al llegar no queda ninguna polilínea del recorrido'
    s.limpio('consumo completo')
    s.cerrar()


@prueba
def a_mitad_del_bus_la_parte_recorrida_ya_no_se_dibuja(nav):
    s, p, ls = empezar(nav, 'multi')
    i = V.alimentar(p, ls, 0, 'pregunta')
    p.click('#viajeSi')
    antes = estado(p)['etapas'][1]
    i = V.alimentar(p, ls[:i + 60], i)
    p.wait_for_timeout(900)
    e = estado(p)
    bus = e['etapas'][1]
    assert bus['visual'] > antes['visual'] and 0 < bus['visual'] < bus['total'], f'el bus va a medias: {bus}'
    assert bus['pendientePts'] >= 2 and bus['lineas'] == 2 and not bus['consumida'], f'queda la parte pendiente (borde + color): {bus}'
    assert e['etapas'][0]['consumida'] and e['etapas'][0]['lineas'] == 0, f'la caminata inicial ya desapareció: {e["etapas"][0]}'
    s.limpio('mitad del bus')
    s.cerrar()


@prueba
def con_transbordo_desaparece_el_primer_bus_se_activa_la_caminata_y_luego_el_segundo(nav):
    s, p, ls = empezar(nav, 'transbordos')
    e = estado(p)
    assert len(e['etapas']) == 5, f'caminata, bus, caminata de cambio, bus, caminata: {e}'
    registro = []
    i = 0
    for _ in range(12):
        i = V.alimentar(p, ls, i, 'pregunta')
        if hay_pregunta(p):
            p.click('#viajeSi')
            p.wait_for_timeout(900)
            x = estado(p)
            registro.append(([t['consumida'] for t in x['etapas']], x['activa']))
        if i >= len(ls):
            break
    assert registro, 'hubo preguntas de subida y bajada'
    assert any(c[1] and a == 2 for c, a in registro), f'tras bajar del primer bus, ese bus está consumido y la caminata de cambio es la etapa activa: {registro}'
    s.limpio('transbordo')
    s.cerrar()


@prueba
def las_lecturas_rechazadas_no_cambian_la_geometria(nav):
    s, p, ls = empezar(nav, 'multi')
    V.alimentar(p, ls, 0, 'fase:caminar')
    p.wait_for_timeout(500)
    a = estado(p)
    # lecturas con precisión de 900 m: el filtro del núcleo las descarta antes de que lleguen a la ruta
    n = p.evaluate("""() => { const ls = Array.from({ length: 6 }, (_, k) => ({ lat: 4.2, lng: -73.5, precision: 900, t: Date.now() + 9e6 + k * 1000, velocidad: null }));
      const v = Spevb.Viaje.nucleo(); let ev = 0; ls.forEach((l) => v.procesar(l).forEach((e) => { if (e.tipo === 'descartada') ev++; })); return ev; }""")
    assert n == 6, 'el núcleo descarta las 6 lecturas imprecisas'
    b = estado(p)
    assert [x['objetivo'] for x in a['etapas']] == [x['objetivo'] for x in b['etapas']] and [x['lineas'] for x in a['etapas']] == [x['lineas'] for x in b['etapas']], f'sin cambios: {a} {b}'
    s.limpio('rechazadas')
    s.cerrar()


@prueba
def un_desvio_muestra_un_conector_ambar_sin_restaurar_lo_recorrido(nav):
    s = V.sesion(nav)
    p = s.abrir()
    V.planear(p)
    r = p.evaluate("""() => { const plan = JSON.parse(JSON.stringify(Spevb.Planner.seleccion.viaje)), N = Spevb.ViajeNucleo;
      const ruta = Spevb.ViajeRuta.crear({ mapa: Spevb.maps.map, plan, reducido: () => true });
      const bus = N.prepararLinea(plan.buses[0].tramo), info = { fase: 'en_bus', leg: 0 };
      const en = (m) => { const d = N.dividirLinea(bus, m).corte; return { lat: d[0], lng: d[1], precision: 5 }; };
      let t = 1e9; const lee = (L) => { t += 1000; ruta.actualizar({ ...L, t }, info); return ruta.estado().etapas[1]; };
      lee(en(50)); lee(en(120)); const sobre = lee(en(200));
      const c0 = ruta.estado().conector;
      const base = en(260); const fuera = lee({ lat: base.lat + 500 / 110574, lng: base.lng, precision: 5 });
      const ee = ruta.estado(); const c1 = ee.conector, desv = ee.desviada;
      const vuelta = lee(en(300)); const c2 = ruta.estado().conector;
      ruta.destruir(); return { sobre: sobre.objetivo, c0, fuera: fuera.objetivo, visualFuera: fuera.visual, c1, desv, vuelta: vuelta.objetivo, c2 }; }""")
    assert not r['c0'] and r['sobre'] >= 190, f'en ruta no hay conector: {r}'
    assert r['c1'] and r['desv'], f'fuera de la ruta aparece el conector ámbar: {r}'
    assert r['fuera'] == r['sobre'] and r['visualFuera'] >= r['sobre'] - 1, f'un desvío no restaura lo recorrido ni lo cambia: {r}'
    assert not r['c2'] and r['vuelta'] >= 290, f'al volver a la ruta el conector desaparece y el avance sigue: {r}'
    s.limpio('desvio')
    s.cerrar()


@prueba
def al_avanzar_aparece_una_estela_y_un_pulso_que_se_apagan_solos(nav):
    s, p, ls = empezar(nav, 'multi')
    V.alimentar(p, ls, 0, 'fase:esperando')
    vistos = p.evaluate("""async () => { const r = { estela: false, pulso: false }; const fin = performance.now() + 700;
      while (performance.now() < fin) { const e = Spevb.Viaje.rutaEstado(); if (e.estela) r.estela = true; if (e.pulso) r.pulso = true; await new Promise((ok) => setTimeout(ok, 30)); } return r; }""")
    assert vistos['estela'], f'tras avanzar se ve la estela de lo recién recorrido: {vistos}'
    p.wait_for_timeout(3500)
    e = estado(p)
    assert not e['estela'] and not e['pulso'] and not e['animando'] and e['raf'] == 0, f'los efectos se apagan solos y no queda ninguna animación corriendo: {e}'
    s.limpio('efectos')
    s.cerrar()


@prueba
def con_movimiento_reducido_no_hay_estela_ni_pulso(nav):
    s, p, ls = empezar(nav, 'multi')
    p.evaluate("document.documentElement.dataset.motion = 'reduce'")
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(400)
    e = estado(p)
    assert not e['estela'] and not e['pulso'] and not e['animando'], e
    s.limpio('efectos reducido')
    s.cerrar()


@prueba
def con_movimiento_reducido_el_corte_se_actualiza_al_instante(nav):
    s, p, ls = empezar(nav, 'multi')
    p.evaluate("document.documentElement.dataset.motion = 'reduce'")
    V.alimentar(p, ls, 0, 'fase:esperando')
    p.wait_for_timeout(150)
    e = estado(p)
    assert not e['animando'] and e['raf'] == 0, f'sin animación con movimiento reducido: {e}'
    assert e['etapas'][0]['visual'] == e['etapas'][0]['objetivo'], e
    s.limpio('reducido')
    s.cerrar()


@prueba
def terminar_libera_las_capas_y_la_animacion(nav):
    s, p, ls = empezar(nav, 'multi')
    V.alimentar(p, ls, 0, 'fase:caminar')
    assert lineas_en_mapa(p)['viaje'] > 0
    p.evaluate("Spevb.Viaje.detener()")
    p.wait_for_timeout(300)
    assert estado(p) is None, 'sin viaje no hay ruta'
    assert lineas_en_mapa(p)['viaje'] == 0, 'se liberan todas las polilíneas del viaje'
    s.limpio('terminar')
    s.cerrar()


@prueba
def el_progreso_se_guarda_con_el_viaje_para_reanudar(nav):
    s, p, ls = empezar(nav, 'multi')
    i = V.alimentar(p, ls, 0, 'pregunta')
    p.click('#viajeSi')
    V.alimentar(p, ls[:i + 40], i)
    p.wait_for_timeout(1000)
    antes = estado(p)['etapas']
    # la página se oculta de verdad (como al bloquear la pantalla): el viaje guarda su estado y el progreso de la ruta
    p.evaluate("() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); }")
    p.wait_for_timeout(200)
    p.evaluate("() => { delete document.hidden; }")
    guardado = p.evaluate("JSON.parse(localStorage.getItem('spevb-viaje-curso') || 'null')")
    assert guardado and guardado.get('ruta') and guardado['ruta']['avances'][1] > 0, f'el viaje guardado incluye el progreso de la ruta: {guardado and guardado.get("ruta")}'
    p.evaluate("Spevb.Viaje.detener()")
    # se vuelve a guardar el estado como lo dejaría la página al recargarse y se reanuda
    p.evaluate("(g) => localStorage.setItem('spevb-viaje-curso', JSON.stringify(g))", guardado)
    p.reload()
    p.wait_for_timeout(1500)
    if hay_pregunta(p):
        p.click('#viajeSi')
        p.wait_for_timeout(1500)
    despues = estado(p)
    assert despues, 'el viaje se reanudó'
    for a, b in zip(antes, despues['etapas']):
        assert b['visual'] >= a['visual'] - 5, f'se reconstruye desde el estado guardado, no desde cero: {a} {b}'
    s.limpio('reanudar')
    s.cerrar()


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
                print('FALLA ', f.__name__, '|', (str(e).splitlines()[0] if str(e) else repr(e))[:900])
                if os.environ.get('SEVB_E2E_TRAZA'):
                    traceback.print_exc()
        nav.close()
    print(f'\n{len([f for f in PRUEBAS if not filtro or filtro in f.__name__])} pruebas de la ruta consumible; fallos: {len(fallos)}', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(correr(sys.argv[1] if len(sys.argv) > 1 else None))
