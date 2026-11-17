'use strict';
/* Ruta «consumible» del modo viaje (4.15): lo ya recorrido desaparece suavemente del mapa y solo queda lo que falta.
   · Es SOLO una representación: el plan (geometría íntegra) no se toca; se conserva para reanudar, recalcular y reconstruir el mapa.
   · Es la ÚNICA dueña del dibujo del recorrido mientras dura el viaje: viaje.js le pide a Spevb.Planner que suelte su copia estática y esta capa dibuja las etapas
     (caminata, bus, [caminata de transbordo, bus,] caminata final), los puntos de subida/bajada y el destino. Al terminar, destruir() libera todo (capas, animación).
   · El avance de cada etapa sale de ViajeNucleo.posicionMonotona (mismo algoritmo que el núcleo): nunca retrocede por ruido y los saltos exigen confirmación. Solo recibe
     lecturas YA filtradas por el núcleo: una lectura rechazada nunca llega aquí, así que no puede recortar la ruta.
   · El conector de desvío y la parada que quedó atrás salen del MISMO estado que cuenta la tarjeta (info.desvio del núcleo): el mapa y el texto no pueden contradecirse. El conector es solo la unión de la
     posición con el recorrido registrado; nunca se presenta como el camino del bus. Si la parada quedó atrás, el tramo hasta ella se da por consumido, su punto se atenúa y la caminata del plan (que parte de
     esa parada) se oculta: el mapa nunca lleva a la persona a la parada original. La caminata nueva desde la bajada real llega con caminataReal().
   · Con movimiento reducido el corte se actualiza al instante. Sin movimiento reducido el extremo pendiente se acerca a la persona en 350–800 ms (una sola animación
     para todas las etapas; actualiza las polilíneas existentes con setPath, no crea capas nuevas por cuadro). Solo hay dos polilíneas por etapa de bus (borde y color) y una por caminata. */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const N = S.ViajeNucleo;
    if (!N || !N.dividirLinea) return;

    const COLORES = { bus: ['#e53935', '#1e5fbf'], borde: '#fff', caminata: '#1b2a33', desvio: '#f59e0b' };
    const MIN_MS = 350, MAX_MS = 800;
    const EPS = 0.5;                      // m: por debajo no se anima ni se repinta

    /** @param {{ mapa, plan, reducido?:()=>boolean, estado?:object }} o
     *  Estado serializable: { v: 1, avances: [m, …] } (un avance por etapa). */
    let vivas = 0;      // rutas consumibles sin destruir (diagnóstico: nunca debe haber más de una)
    function crear(o) {
        vivas++;
        const m = o.mapa, plan = o.plan, reducido = o.reducido || (() => false);
        const cfgCamina = { ...N.CFG, DESVIO_BUS_M: N.CFG.DESVIO_CAMINA_M };
        const nb = plan.buses.length;

        // ---------- etapas: caminata, bus, [caminata, bus,] caminata
        const geo = (p) => [p.lng, p.lat];
        const caminata = (clave, de, a) => {
            const c = plan.caminatas && plan.caminatas[clave];
            const coords = c && Array.isArray(c.coordinates) && c.coordinates.length > 1 ? [geo(de)].concat(c.coordinates, [geo(a)]) : [geo(de), geo(a)];
            return { tipo: 'caminata', coords, linea: N.prepararLinea(coords), cfg: cfgCamina };
        };
        const etapas = [caminata(0, plan.origen || plan.buses[0].subida, plan.buses[0].subida)];
        plan.buses.forEach((b, i) => {
            etapas.push({ tipo: 'bus', color: COLORES.bus[i % 2], coords: b.tramo, linea: N.prepararLinea(b.tramo), cfg: N.CFG });
            const sig = plan.buses[i + 1];
            etapas.push(sig ? caminata(1, b.bajada, sig.subida) : caminata(2, b.bajada, plan.destino));
        });
        etapas.forEach((e) => { e.st = { avanceMax: 0, avanceT: null, avanceSalto: null }; e.objetivo = 0; e.visual = 0; e.anim = null; e.lineas = []; e.consumida = false; e.oculta = false; });

        const grupo = m.group().addTo(m);
        const puntos = [], puntosBajada = [];
        let conector = null, activa = 0, raf = 0, destruida = false, ultimaPos = null, desviada = false;

        // ---------- dibujo
        const trazo = (e, path) => {
            if (e.tipo === 'bus') return [m.polyline(path, { color: COLORES.borde, weight: 11, opacity: 0.95, interactive: false }), m.polyline(path, { color: e.color, weight: 7, opacity: 1, interactive: false })];
            return [m.polyline(path, { color: COLORES.caminata, weight: 5, opacity: 0.9, dashArray: '1 10', lineCap: 'round', interactive: false })];
        };
        function pintar(e) {
            if (destruida) return;
            if (e.oculta) { quitarLineas(e); return; }      // etapa que no debe verse (la caminata que parte de una parada que quedó atrás)
            const pend = N.dividirLinea(e.linea, e.visual).pendiente;
            if (pend.length < 2) { quitarLineas(e); e.consumida = true; return; }
            e.consumida = false;
            if (!e.lineas.length) e.lineas = trazo(e, pend).map((l) => l.addTo(grupo));
            else e.lineas.forEach((l) => l.setPath(pend));
        }
        function quitarLineas(e) { e.lineas.forEach((l) => { try { l.remove(); } catch { /* ya liberada */ } }); e.lineas = []; }
        etapas.forEach(pintar);
        plan.buses.forEach((b) => {
            puntos.push(m.dot([b.subida.lat, b.subida.lng], { radius: 7, color: '#fff', weight: 3, fillColor: '#176650', fillOpacity: 1, tooltip: 'Subes a la ruta ' + (b.etiqueta || b.codigo) }).addTo(grupo));
            const pb = m.dot([b.bajada.lat, b.bajada.lng], { radius: 7, color: '#fff', weight: 3, fillColor: '#c62828', fillOpacity: 1, tooltip: 'Bajas de la ruta ' + (b.etiqueta || b.codigo) }).addTo(grupo);
            puntos.push(pb); puntosBajada.push(pb);
        });
        puntos.push(m.dot([plan.destino.lat, plan.destino.lng], { radius: 8, color: '#fff', weight: 3, fillColor: '#1e5fbf', fillOpacity: 1, tooltip: 'Tu destino' }).addTo(grupo));

        // ---------- efectos: estela que se desvanece y pulso en el punto de corte (solo opacidad y radio: igual en Leaflet y en Google)
        const COLA_M = 70, COLA_MS = 1100, PULSO_MS = 1100, PULSO_ENTRE_MS = 2400;
        let colaIdx = -1, colaT0 = 0, pulsoIdx = -1, pulsoT0 = -1e9, estela = null, pulso = null;
        const colorDe = (e) => (e.tipo === 'bus' ? e.color : COLORES.caminata);
        const corteDe = (e) => { const c = N.dividirLinea(e.linea, e.visual).corte; return c || null; };
        /** Tramo de la línea entre los avances a y b (para la estela): puntos [lat, lng] con los extremos interpolados. */
        function subLinea(l, a, b) {
            const A = N.dividirLinea(l, a).corte, B = N.dividirLinea(l, b).corte;
            if (!A || !B) return [];
            const out = [A];
            for (let i = 0; i < l.pts.length; i++) if (l.acum[i] > a && l.acum[i] < b) out.push([l.pts[i].lat, l.pts[i].lng]);
            out.push(B);
            return out;
        }
        function quitarEstela() { if (estela) { try { estela.remove(); } catch { /* nada */ } estela = null; } colaIdx = -1; }
        function quitarPulso() { if (pulso) { try { pulso.remove(); } catch { /* nada */ } pulso = null; } pulsoIdx = -1; }
        /** Devuelve true mientras siga habiendo algo animándose. */
        function efectos(ahora) {
            if (reducido()) { quitarEstela(); quitarPulso(); return false; }
            let vivo = false;
            if (colaIdx >= 0) {
                const e = etapas[colaIdx], f = 1 - (ahora - colaT0) / COLA_MS;
                if (f > 0) {
                    const path = subLinea(e.linea, Math.max(0, e.visual - COLA_M), e.visual), op = 0.6 * f * f, estilo = { color: colorDe(e), opacity: op, weight: e.tipo === 'bus' ? 7 : 5 };
                    if (e.visual > 1 && path.length > 1) {
                        if (!estela) estela = m.polyline(path, { ...estilo, lineCap: 'round', interactive: false }).addTo(grupo); else { estela.setPath(path); estela.setStyle(estilo); }
                    }
                    vivo = true;
                } else quitarEstela();
            }
            if (pulsoIdx >= 0) {
                const e = etapas[pulsoIdx], p = (ahora - pulsoT0) / PULSO_MS, c = corteDe(e);
                if (p >= 0 && p < 1 && c) {
                    const estilo = { radius: 8 + 16 * p, opacity: 0.8 * (1 - p), fillOpacity: 0.3 * (1 - p), color: colorDe(e), fillColor: colorDe(e) };
                    if (!pulso) pulso = m.dot(c, { ...estilo, weight: 2, interactive: false }).addTo(grupo); else { pulso.setPosition(c); pulso.setStyle(estilo); }
                    vivo = true;
                } else quitarPulso();
            }
            return vivo;
        }
        function dispararEfectos(idx) {
            if (reducido()) return;
            const ahora = performance.now();
            colaIdx = idx; colaT0 = ahora;
            if (ahora - pulsoT0 > PULSO_ENTRE_MS) { pulsoIdx = idx; pulsoT0 = ahora; }       // un pulso cada tanto, no uno por lectura
        }

        // ---------- animación (una sola, cancelable)
        function paso(ahora) {
            raf = 0;
            if (destruida) return;
            let sigue = false;
            etapas.forEach((e) => {
                if (!e.anim) return;
                const k = Math.min(1, (ahora - e.anim.t0) / e.anim.dur), f = 1 - Math.pow(1 - k, 3);
                e.visual = e.anim.desde + (e.anim.hasta - e.anim.desde) * f;
                if (k >= 1) { e.visual = e.anim.hasta; e.anim = null; } else sigue = true;
                pintar(e);
            });
            if (efectos(ahora)) sigue = true;
            if (sigue) raf = requestAnimationFrame(paso);
        }
        /** {@code completa}: la etapa terminó (cambio de fase): se consume hasta el último metro aunque falte menos de EPS. */
        function mover(e, hasta, completa = false) {
            if (completa ? (e.visual >= e.linea.total && e.objetivo >= e.linea.total) : hasta <= e.objetivo + EPS) return;      // el objetivo nunca retrocede
            e.objetivo = Math.max(e.objetivo, hasta);
            if (reducido() || typeof requestAnimationFrame !== 'function') { e.anim = null; e.visual = e.objetivo; pintar(e); return; }
            const salto = e.objetivo - e.visual;
            e.anim = { desde: e.visual, hasta: e.objetivo, t0: performance.now(), dur: Math.max(MIN_MS, Math.min(MAX_MS, MIN_MS + salto * 4)) };
            dispararEfectos(etapas.indexOf(e));
            if (!raf) raf = requestAnimationFrame(paso);
        }

        // ---------- conector de desvío (ámbar, discontinuo): de la persona al punto de reincorporación; nunca restaura lo recorrido
        function ponerConector(desde, hasta) {
            if (!desde || !hasta) { quitarConector(); return; }
            if (!conector) conector = m.polyline([desde, hasta], { color: COLORES.desvio, weight: 4, opacity: 0.95, dashArray: '8 8', lineCap: 'round', interactive: false }).addTo(grupo);
            else conector.setPath([desde, hasta]);
        }
        function quitarConector() { if (conector) { try { conector.remove(); } catch { /* nada */ } conector = null; } }

        /** Etapa que corresponde a la fase del núcleo (info.fase / info.leg). */
        function etapaDe(info) {
            switch (info && info.fase) {
                case 'en_bus': return 2 * Math.min(info.leg || 0, nb - 1) + 1;
                case 'caminar': case 'esperando': return 2 * Math.min(info.leg || 0, nb - 1);
                case 'caminar_final': return 2 * nb;
                case 'llegaste': case 'terminado': return etapas.length;
                default: return 0;
            }
        }

        /** L: lectura ya filtrada ({lat,lng,precision,t}) o null (solo cambio de fase); info: la del núcleo. */
        function actualizar(L, info) {
            if (destruida) return;
            activa = etapaDe(info);
            for (let i = 0; i < Math.min(activa, etapas.length); i++) mover(etapas[i], etapas[i].linea.total, true);       // lo anterior se consume por completo
            if (activa >= etapas.length) { quitarConector(); return; }
            const e = etapas[activa], dv = e.tipo === 'bus' && info && info.desvio ? info.desvio : null;
            if (dv && dv.estado === 'atras') {      // la parada quedó atrás: nada que consumir ni conector; el tramo hasta ella se da por recorrido y la caminata del plan (que sale de ella) se oculta
                desviada = false; quitarConector(); mover(e, e.linea.total, true);
                const pb = puntosBajada[Math.min(info.leg || 0, puntosBajada.length - 1)]; if (pb) { try { pb.setStyle({ fillColor: '#9aa5ab' }); } catch { /* sin estilo */ } }
                const sig = etapas[activa + 1]; if (sig && sig.tipo === 'caminata' && !sig.propia) { sig.oculta = true; quitarLineas(sig); }
                return;
            }
            if (e.oculta) { quitarConector(); return; }
            if (!L || !Number.isFinite(L.lat) || !Number.isFinite(L.lng)) return;
            ultimaPos = [L.lat, L.lng];
            if (dv && (dv.estado === 'posible' || dv.estado === 'confirmado')) {      // el núcleo dice que el bus se apartó: el conector sale de ESE estado (la misma historia que la tarjeta)
                desviada = true; ponerConector(ultimaPos, N.dividirLinea(e.linea, Math.max(e.visual, e.objetivo)).corte); return;
            }
            const r = N.posicionMonotona(e.linea, e.st, L, e.cfg);
            if (r.enRuta) { e.st.avanceMax = Math.max(e.st.avanceMax, r.avance); mover(e, e.st.avanceMax); desviada = false; quitarConector(); return; }
            if (dv) { desviada = false; quitarConector(); return; }      // el núcleo no ve desvío (p. ej. el bus siguió después de la bajada): no hay conector que contradiga a la tarjeta
            // Sin información del núcleo (uso directo): fuera de la línea lo recorrido no se restaura; si hay desvío claro se muestra el conector hacia el punto de reincorporación (el corte actual).
            desviada = r.dist > e.cfg.DESVIO_BUS_M;
            if (desviada && !r.saltoPendiente) ponerConector(ultimaPos, N.dividirLinea(e.linea, Math.max(e.visual, e.objetivo)).corte); else if (!desviada) quitarConector();
        }
        /** Caminata NUEVA desde donde la persona se bajó de verdad (la etapa de caminata que corresponde a {@code info}). estado: 'calculando' | 'error' (no se dibuja nada: ni la parada vieja ni una recta)
         *  o 'lista' con {@code coords} (GeoJSON [lng, lat] del servicio) y los extremos reales. La geometría del plan no se toca: es la referencia para reanudar. */
        function caminataReal(info, o) {
            if (destruida) return false;
            const idx = etapaDe(info), e = etapas[idx];
            if (!e || e.tipo !== 'caminata') return false;
            if (o && o.estado === 'lista' && Array.isArray(o.coords) && o.coords.length > 1 && o.desde && o.hasta) {
                const coords = [geo(o.desde)].concat(o.coords, [geo(o.hasta)]);
                e.coords = coords; e.linea = N.prepararLinea(coords); e.st = { avanceMax: 0, avanceT: null, avanceSalto: null }; e.objetivo = e.visual = 0; e.anim = null; e.oculta = false; e.propia = true;
                quitarLineas(e); pintar(e);
            } else { e.oculta = true; e.propia = false; e.anim = null; quitarLineas(e); }
            return true;
        }

        function serializar() { return { v: 1, avances: etapas.map((e) => Math.round(Math.max(e.objetivo, e.st.avanceMax))) }; }
        function restaurar(x) {
            if (!x || x.v !== 1 || !Array.isArray(x.avances)) return;
            etapas.forEach((e, i) => {
                const a = Number(x.avances[i]);
                if (!Number.isFinite(a) || a <= 0) return;
                e.st.avanceMax = Math.min(a, e.linea.total); e.objetivo = e.visual = e.st.avanceMax; e.anim = null; pintar(e);
            });
        }
        /** Diagnóstico para pruebas y soporte (sin coordenadas privadas más allá del recorrido del propio plan). */
        function estado() {
            return { activa, desviada, conector: !!conector, ocultas: etapas.map((e) => !!e.oculta), propias: etapas.map((e) => !!e.propia), estela: !!estela, pulso: !!pulso, animando: !!raf || etapas.some((e) => !!e.anim), raf,
                etapas: etapas.map((e) => ({ tipo: e.tipo, total: Math.round(e.linea.total), objetivo: Math.round(e.objetivo), visual: Math.round(e.visual), lineas: e.lineas.length, consumida: e.consumida,
                    pendientePts: N.dividirLinea(e.linea, e.visual).pendiente.length })) };
        }
        function destruir() {
            if (destruida) return;
            destruida = true; vivas--;
            if (raf) { try { cancelAnimationFrame(raf); } catch { /* nada */ } raf = 0; }
            etapas.forEach((e) => { e.anim = null; e.lineas = []; });
            conector = null; estela = null; pulso = null;
            try { grupo.remove(); } catch { /* el mapa ya no existe */ }
        }

        if (o.estado) restaurar(o.estado);
        return { actualizar, caminataReal, serializar, restaurar, estado, destruir, grupo };
    }

    S.ViajeRuta = { crear, vivas: () => vivas };
})();
