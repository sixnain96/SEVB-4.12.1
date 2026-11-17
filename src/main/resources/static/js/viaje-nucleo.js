'use strict';
/* Núcleo del «Modo viaje» (sin DOM, sin mapa, sin red): depura las lecturas del GPS y decide en qué fase va la persona.

   Fases:  caminar → esperando → [¿te subiste?] → en_bus → [¿ya te bajaste?] → caminar (transbordo) o caminar_final → llegaste
   Reglas de oro:
   · Todo el tiempo sale de la marca de tiempo de cada lectura (nunca del reloj): el mismo recorrido da el mismo resultado, en vivo o simulado.
   · La aplicación NUNCA asume que subiste o bajaste: detecta una señal (velocidad sostenida de bus cerca de la ruta; velocidad de caminata
     después del bus cerca de la parada) y PREGUNTA. Una respuesta «no» silencia esa pregunta un rato.
   · El GPS ruidoso se filtra antes de decidir nada: lecturas imprecisas, repetidas, saltos imposibles y quietud (el punto no «tiembla»).
   Las coordenadas de las rutas llegan como GeoJSON ([lng, lat]); las posiciones del usuario como { lat, lng }. */
(() => {
    const S = window.Spevb || (window.Spevb = {});

    const CFG = {
        // ---- filtro del GPS
        PRECISION_MAX: 100,          // m: una lectura con peor precisión se descarta
        VEL_SALTO: 40,               // m/s (144 km/h): un desplazamiento más rápido que esto en un bus urbano es ruido
        SALTO_MIN: 80,               // m: por debajo de esto un «salto» no se considera salto
        SALTO_CONFIRMAN: 3,          // lecturas seguidas que coinciden entre sí para aceptar un salto como real (la anterior era la errónea)
        HUECO_MS: 25000,             // sin lecturas más de esto: se reancla el filtro y se avisa que la señal volvió
        VENTANA_VEL_MS: 8000,        // la velocidad se mide sobre las últimas posiciones de esta ventana
        // ---- detección de fases
        V_BUS: 3.6,                  // m/s (≈ 13 km/h): más rápido de lo que camina o trota una persona
        T_BUS_MS: 6000, D_BUS_MIN: 30,
        D_LINEA_SUBIR: 80,           // m: para sospechar que subió al bus tiene que estar sobre la ruta de ese bus
        V_CAMINA_MIN: 0.7, V_CAMINA_MAX: 2.4,
        T_BAJAR_MS: 10000, D_BAJAR_MIN: 12, D_PARADA_CERCA: 350, BUS_RECIENTE_MS: 180000,
        QUIETO_MS: 45000, D_QUIETO_PARADA: 100,
        R_PARADERO: 45, R_PARADERO_SALIR: 90, R_LLEGADA: 35,
        COOL_SUBIDA_MS: 90000, COOL_BAJADA_MS: 60000, PREGUNTA_VENCE_MS: 25000,
        ALERTA_CERCA: 500, ALERTA_PREPARATE: 200, ALERTA_AHORA: 70,
        AVANCE_VENTANA_M: 200, AVANCE_VEL_MAX: 25,   // la posición sobre la ruta no puede adelantarse más que esto (+ velocidad × tiempo) entre lecturas: un salto no es avance
        AVANCE_CONFIRMAN: 3,         // lecturas seguidas coherentes que confirman un avance grande (p. ej. tras perder la señal un rato)
        SIN_RUTA_ALERTA_M: 1500,     // fuera de la ruta solo se avisa por distancia directa si ya se recorrió casi todo el tramo
        SE_PASO_M: 250, DESVIO_CAMINA_M: 120, DESVIO_BUS_M: 150, DESVIO_MSG_MS: 90000, DESVIO_BUS_SOST_MS: 20000,
        V_CAMINA_ETA: 1.25, V_BUS_ETA: 5,
        SENAL_DEBIL_N: 8,
        R_DESTINO_EN_BUS: 50, T_DESTINO_MS: 8000,   // última parada pegada al destino: si ya estás ahí y vas despacio, se pregunta si bajaste
        // ---- desvío del bus y «tu parada quedó atrás» (Fase A). Todo configurable y comprobable: las pruebas lo cambian con opciones.cfg.
        // Salir y volver usan umbrales DISTINTOS (histéresis): se sale a más de DESVIO_BUS_M (150 m) de la línea y solo se vuelve a menos de DESVIO_VOLVER_M.
        DESVIO_VOLVER_M: 60,         // m: una lectura a menos de esto de la línea puede ser parte de la reincorporación; entre 60 y 150 m sigue «fuera»
        DESVIO_PRECISION_MAX: 60,    // m: una lectura peor que esto no cuenta como prueba de desvío confirmado
        DESVIO_CONFIRMA_N: 3,        // lecturas seguidas fuera de la ruta (y coherentes: el bus se movió) para pasar de «posible» a «confirmado»
        DESVIO_CONFIRMA_MS: 15000,   // y como mínimo este tiempo desde la primera
        DESVIO_MOV_M: 40,            // m: un bus detenido a 160 m de su ruta no es un desvío: tiene que haberse movido (o ir a velocidad de bus)
        DESVIO_POSIBLE_FIN_N: 2,     // lecturas seguidas sobre la línea que cierran un «posible» que nunca se confirmó (el aviso se retira solo)
        DESVIO_LARGO_MS: 120000,     // un desvío confirmado que dura más que esto ofrece «Pregunta al conductor si pasa por tu parada»
        // Retorno: cuántas lecturas, qué tan seguidas y cuánto avance a lo largo de la RUTA (no en línea recta) prueban que el bus volvió a ella.
        RETORNO_N: 4,                // lecturas seguidas compatibles con el recorrido y su sentido
        RETORNO_MS: 12000,           // tiempo mínimo entre la primera y la última de esas lecturas
        RETORNO_GANA_M: 60,          // m de avance a lo largo de la ruta entre la primera y la última (un cruce o una glorieta no avanzan)
        RETORNO_PRECISION_MAX: 35,   // m: una lectura más imprecisa no cuenta (y rompe la racha)
        RETORNO_VEL_MAX: 18,         // m/s (65 km/h): el avance a lo largo de la ruta entre dos lecturas no puede superar esto (+ 40 m de margen): un salto no es avance
        RETORNO_SEPARACION_M: 30,    // m: la línea debe estar claramente más cerca que cualquier otro tramo de la ruta que no sea contiguo
        RETORNO_SEP_AVANCE_M: 100,   // m: dos puntos de la ruta separados menos que esto sobre el recorrido son «el mismo sitio» (vecinos)
        RETORNO_ATRAS_M: 300,        // m: cuánto se admite que el retorno quede antes del último punto fiable (un lazo corto)
        RETORNO_AVANCE_MIN_M: 20,    // m: MARGEN MÍNIMO de avance por encima de la parada para afirmar que quedó atrás; con peor precisión el margen crece: max(20, 1.5 × precisión)
        RETORNO_K_PREC: 1.5,         // veces la imprecisión que debe superar el avance sobre la parada
        REF_TOL_EXTREMO_M: 25,       // m: el tramo del pasajero empieza y termina a menos de esto de la referencia
        REF_TOL_MUESTRA_M: 20,       // m: cada muestra del tramo está a menos de esto de la referencia
        REF_TOL_LARGO: 0.05,         // fracción: el largo del tramo debe coincidir con el de la referencia entre sus extremos (±5 % o 40 m)
        REF_DESPUES_MIN_M: 120,      // m: si la referencia termina antes de esto tras la bajada, «ya pasó la parada» no se puede probar
        CAMINATA_FINAL_MAX_M: 2000, CAMINATA_FINAL_MAX_MIN: 30,      // más que esto a pie hasta el destino ya no es razonable: se ofrece recalcular con el planificador
        CAMINATA_TRANSBORDO_MAX_M: 1000, CAMINATA_TRANSBORDO_MAX_MIN: 15,      // el siguiente bus solo se conserva si su subida queda a esta caminata desde la bajada real
        UBICACION_VIGENTE_MS: 30000, UBICACION_PRECISION_MAX: 60,      // la bajada real exige una lectura de hace menos de 30 s y de ±60 m o mejor
    };

    // ------------------------------------------------------------------ geometría
    const RAD = Math.PI / 180;
    function dist(a, b) {
        const dLat = (b.lat - a.lat) * RAD, dLng = (b.lng - a.lng) * RAD;
        const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * RAD) * Math.cos(b.lat * RAD) * Math.sin(dLng / 2) ** 2;
        return 2 * 6371000 * Math.asin(Math.sqrt(h));
    }

    /** Línea GeoJSON → puntos con la distancia acumulada (m) desde el inicio. */
    function prepararLinea(coords) {
        const pts = (coords || []).map((c) => ({ lat: c[1], lng: c[0] }));
        const acum = [0];
        for (let i = 1; i < pts.length; i++) acum.push(acum[i - 1] + dist(pts[i - 1], pts[i]));
        return { pts, acum, total: acum.length ? acum[acum.length - 1] : 0 };
    }

    /** Punto más cercano de la línea: { dist (m hasta la línea), avance (m desde el inicio de la línea) }. {@code desde}: ignora lo anterior. */
    function proyectar(linea, p, desde = 0, hasta = Infinity) {
        const { pts, acum } = linea;
        if (pts.length < 2) return { dist: pts.length ? dist(p, pts[0]) : Infinity, avance: 0 };
        const kx = 111320 * Math.cos(p.lat * RAD), ky = 110574;
        const buscar = (minimo) => {
            let mejor = { dist: Infinity, avance: 0 };
            for (let i = 0; i < pts.length - 1; i++) {
                if (acum[i + 1] < minimo || acum[i] > hasta) continue;
                const a = pts[i], b = pts[i + 1];
                const bx = (b.lng - a.lng) * kx, by = (b.lat - a.lat) * ky, px = (p.lng - a.lng) * kx, py = (p.lat - a.lat) * ky;
                const l2 = bx * bx + by * by;
                const t = l2 > 0 ? Math.max(0, Math.min(1, (px * bx + py * by) / l2)) : 0;
                const d = Math.hypot(px - bx * t, py - by * t);
                if (d < mejor.dist) mejor = { dist: d, avance: acum[i] + t * (acum[i + 1] - acum[i]) };
            }
            return mejor;
        };
        const r = buscar(desde);
        return r.dist === Infinity ? buscar(0) : r;      // sin tope hasta no hay nada que ocultar: la búsqueda de reserva es completa
    }

    /** Divide la línea en un avance (m desde su inicio): { recorrida, pendiente } como listas de [lat, lng], con el punto de corte INTERPOLADO exacto en ambas
     *  y { corte }. Antes del inicio todo queda pendiente; después del final, todo recorrido. Tolera puntos repetidos y segmentos de longitud cero. No modifica la línea. */
    function dividirLinea(linea, avance) {
        const { pts, acum, total } = linea;
        const ll = (p) => [p.lat, p.lng];
        if (!pts.length) return { recorrida: [], pendiente: [], corte: null };
        const a = Math.max(0, Math.min(Number.isFinite(avance) ? avance : 0, total));
        if (a <= 0) return { recorrida: [], pendiente: pts.map(ll), corte: ll(pts[0]) };
        if (a >= total) return { recorrida: pts.map(ll), pendiente: [], corte: ll(pts[pts.length - 1]) };
        let i = 0;
        while (i < pts.length - 2 && acum[i + 1] <= a) i++;
        const seg = acum[i + 1] - acum[i], t = seg > 0 ? (a - acum[i]) / seg : 0;
        const c = [pts[i].lat + (pts[i + 1].lat - pts[i].lat) * t, pts[i].lng + (pts[i + 1].lng - pts[i].lng) * t];
        return { recorrida: pts.slice(0, i + 1).map(ll).concat([c]), pendiente: [c].concat(pts.slice(i + 1).map(ll)), corte: c };
    }

    /** Candidatos de proyección sobre una línea: {@code mejor} = el punto más cercano DENTRO de la ventana de avance [desde, hasta] y {@code segundo} = el más cercano de OTRA parte de la
     *  línea (a más de {@code sep} m de avance del mejor), buscado en toda la línea: si una calle repetida o un ramal queda casi igual de cerca, el retorno es ambiguo. */
    function proyectarCandidatos(linea, p, desde = 0, hasta = Infinity, sep = 100, periodo = 0) {
        const { pts, acum } = linea;
        if (pts.length < 2) return { mejor: null, segundo: null };
        const kx = 111320 * Math.cos(p.lat * RAD), ky = 110574, todos = [];
        let mejor = null;
        for (let i = 0; i < pts.length - 1; i++) {
            const a = pts[i], b = pts[i + 1];
            const bx = (b.lng - a.lng) * kx, by = (b.lat - a.lat) * ky, px = (p.lng - a.lng) * kx, py = (p.lat - a.lat) * ky;
            const l2 = bx * bx + by * by, t = l2 > 0 ? Math.max(0, Math.min(1, (px * bx + py * by) / l2)) : 0;
            const k = { dist: Math.hypot(px - bx * t, py - by * t), avance: acum[i] + t * (acum[i + 1] - acum[i]) };
            todos.push(k);
            if (acum[i + 1] >= desde && acum[i] <= hasta && (!mejor || k.dist < mejor.dist)) mejor = k;
        }
        if (!mejor) return { mejor: null, segundo: null };
        let segundo = null;
        // {@code periodo} > 0 (ruta circular con la vuelta duplicada): el mismo sitio de la vuelta siguiente es el MISMO lugar, no un competidor.
        const lejos = (k) => { const d = Math.abs(k.avance - mejor.avance); if (d <= sep) return false; if (!periodo) return true; const r = d % periodo; return r > sep && periodo - r > sep; };
        for (const k of todos) if (lejos(k) && (!segundo || k.dist < segundo.dist)) segundo = k;
        return { mejor, segundo };
    }

    /** Dónde cabe el tramo {@code tr} (línea preparada de {@code tramo}) dentro de la línea {@code lin}: lista de { a, b } (avances de su inicio y su fin) donde el tramo es de verdad una parte
     *  contigua de ella (extremos cerca, largo igual y TODAS las muestras sobre la línea y en orden). En una ruta con calles repetidas puede haber más de una. */
    function colocaciones(tr, tramo, lin, c, aMax) {
        const kx0 = 111320 * Math.cos(tramo[0][1] * RAD), ky = 110574;
        const candidatos = (P) => {
            const out = [];
            for (let i = 0; i < lin.pts.length - 1; i++) {
                const a = lin.pts[i], b = lin.pts[i + 1];
                const bx = (b.lng - a.lng) * kx0, by = (b.lat - a.lat) * ky, px = (P[0] - a.lng) * kx0, py = (P[1] - a.lat) * ky;
                const l2 = bx * bx + by * by, t = l2 > 0 ? Math.max(0, Math.min(1, (px * bx + py * by) / l2)) : 0;
                const d = Math.hypot(px - bx * t, py - by * t);
                if (d <= c.REF_TOL_EXTREMO_M) out.push({ d, avance: lin.acum[i] + t * (lin.acum[i + 1] - lin.acum[i]) });
            }
            const g = [];
            for (const k of out) { const u = g[g.length - 1]; if (u && k.avance - u.avance <= 50) { if (k.d < u.d) g[g.length - 1] = k; } else g.push(k); }
            return g.map((k) => k.avance);
        };
        const as = candidatos(tramo[0]).filter((a) => a < aMax), bs = candidatos(tramo[tramo.length - 1]);
        const L = tr.total, tol = Math.max(c.REF_TOL_LARGO * L, 40), n = Math.max(2, Math.ceil(L / 50)), res = [];
        for (const a of as) for (const b of bs) {
            if (b <= a || Math.abs((b - a) - L) > tol) continue;
            let max = 0, suma = 0, previo = a - 30, ok = true;
            for (let k = 0; k <= n && ok; k++) {
                const m = dividirLinea(tr, L * k / n).corte, r = proyectar(lin, { lat: m[0], lng: m[1] }, Math.max(0, a - 30), b + 30);
                if (!(r.dist < Infinity) || r.avance < previo - 30) { ok = false; break; }
                max = Math.max(max, r.dist); suma += r.dist; previo = Math.max(previo, r.avance);
            }
            if (ok && max <= c.REF_TOL_MUESTRA_M && suma / (n + 1) <= c.REF_TOL_MUESTRA_M * 0.6) res.push({ a, b });
        }
        return res;
    }

    /** REFERENCIA del recorrido que continúa DESPUÉS de la bajada. {@code tramo}: el tramo del pasajero (GeoJSON [lng, lat], termina en la bajada); {@code recorrido}: la geometría completa de la ruta
     *  (la de /api/rutas/{id}). Comprueba que el tramo es de verdad una parte contigua del recorrido y devuelve la línea que lo contiene, en el sentido en que viaja el bus: la del trazado, la invertida
     *  (tramo en sentido contrario al dibujado) o, en una ruta circular, la vuelta duplicada para poder seguir después de cerrar el lazo.
     *  {@code o}: { sentidoRuta: 'IDA'|'REGRESO'|'CIRCULAR', sentidoViaje: 'SENTIDO_DEL_TRAZADO'|'SENTIDO_INVERSO' (opcionales), cfg }.
     *  Resultado: { ok: true, coords, a, b, total, despues, circular, invertida } con a/b = avance (m) del inicio y del fin del tramo sobre {@code coords}; o { ok: false, motivo }, con motivo
     *  'sin-datos' | 'tramo-corto' | 'no-coincide' | 'ambigua'. Si el tramo cabe en más de un sitio (calles repetidas, ramales, lazo que se cruza a sí mismo) es 'ambigua': nunca se elige uno al azar. */
    function construirReferencia(tramo, recorrido, o = {}) {
        const c = { ...CFG, ...(o.cfg || {}) };
        const valida = (l) => Array.isArray(l) && l.length >= 2 && l.every((p) => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]));
        if (!valida(tramo) || !valida(recorrido)) return { ok: false, motivo: 'sin-datos' };
        const tr = prepararLinea(tramo);
        if (tr.total < 20) return { ok: false, motivo: 'tramo-corto' };
        const circular = o.sentidoRuta === 'CIRCULAR';
        const intentos = o.sentidoViaje === 'SENTIDO_INVERSO' ? [true] : o.sentidoViaje === 'SENTIDO_DEL_TRAZADO' ? [false] : [false, true];
        const hallados = [];
        for (const inv of intentos) {
            if (inv && circular) continue;      // una ruta circular no se recorre al revés
            const base = inv ? recorrido.slice().reverse() : recorrido;
            const coords = circular ? base.concat(base.slice(1)) : base;
            const lin = prepararLinea(coords), vuelta = circular ? prepararLinea(base).total : lin.total;
            for (const col of colocaciones(tr, tramo, lin, c, circular ? vuelta : Infinity)) hallados.push({ ...col, inv, coords, total: lin.total, vuelta });
        }
        if (!hallados.length) return { ok: false, motivo: 'no-coincide' };
        const h = hallados[0];
        if (hallados.some((x) => x.inv !== h.inv || Math.abs(x.a - h.a) > c.RETORNO_SEP_AVANCE_M)) return { ok: false, motivo: 'ambigua' };
        return { ok: true, coords: h.coords, a: h.a, b: h.b, total: h.total, despues: h.total - h.b, circular, invertida: h.inv, vuelta: circular ? h.vuelta : 0 };
    }

    /** Posición MONÓTONA sobre una línea: el avance máximo nunca retrocede, no salta a un tramo vecino por una lectura mala y un avance grande solo se acepta si varias
     *  lecturas seguidas lo confirman. {@code st} = { avanceMax, avanceT, avanceSalto } (se modifica); {@code c} = CFG (usa AVANCE_*, DESVIO_BUS_M como distancia máxima a la línea).
     *  Devuelve { dist, avance, enRuta, saltoPendiente? }. El núcleo la usa para el tramo del bus y la ruta consumible (viaje-ruta.js) para cada etapa. */
    function posicionMonotona(linea, st, L, c) {
        const dtS = st.avanceT === null || st.avanceT === undefined ? 0 : Math.max(0, (L.t - st.avanceT) / 1000);
        const tope = st.avanceMax + c.AVANCE_VENTANA_M + c.AVANCE_VEL_MAX * dtS;
        const acotada = proyectar(linea, L, Math.max(0, st.avanceMax - 100), tope);
        if (acotada.dist <= c.DESVIO_BUS_M) { st.avanceSalto = null; st.avanceT = L.t; return { ...acotada, enRuta: true }; }
        // No está cerca de la línea dentro de lo plausible: ¿está más adelante? Solo se acepta si varias lecturas seguidas lo confirman.
        const libre = proyectar(linea, L, Math.max(0, st.avanceMax - 100));
        if (libre.dist <= c.DESVIO_BUS_M && libre.avance > tope) {
            const s0 = st.avanceSalto;
            st.avanceSalto = s0 && Math.abs(libre.avance - s0.avance) <= 250 ? { avance: libre.avance, n: s0.n + 1 } : { avance: libre.avance, n: 1 };
            if (st.avanceSalto.n >= c.AVANCE_CONFIRMAN) { st.avanceSalto = null; st.avanceT = L.t; return { ...libre, enRuta: true }; }
            return { ...acotada, enRuta: false, saltoPendiente: true };
        }
        st.avanceSalto = null;
        return { ...acotada, enRuta: false };
    }

    // ------------------------------------------------------------------ filtro de lecturas
    class FiltroLecturas {
        constructor(cfg = CFG) { this.cfg = cfg; this.reiniciar(); }

        reiniciar() {
            this.ultimaT = null; this.cruda = null; this.lat = null; this.lng = null; this.varianza = -1;
            this.hist = []; this.vel = 0; this.saltos = []; this.malasSeguidas = 0;
        }

        /** @returns {{ok:boolean, motivo?:string, lectura?:{lat,lng,precision,t,vel,hueco,quieto}}} */
        procesar(l) {
            const c = this.cfg;
            if (!l || !Number.isFinite(l.lat) || !Number.isFinite(l.lng) || !Number.isFinite(l.t)) return { ok: false, motivo: 'invalida' };
            const acc = Number.isFinite(l.precision) ? Math.max(1, l.precision) : 9999;
            if (acc > c.PRECISION_MAX) { this.malasSeguidas++; return { ok: false, motivo: 'imprecisa' }; }
            let hueco = false;
            if (this.ultimaT !== null) {
                const dt = (l.t - this.ultimaT) / 1000;
                if (dt <= 0) return { ok: false, motivo: 'repetida' };
                if (dt * 1000 > c.HUECO_MS) {
                    hueco = true;                                   // tras un hueco largo no se compara con lo anterior: se reancla
                    this.varianza = -1; this.hist = []; this.vel = 0; this.saltos = [];
                } else {
                    const salto = dist(this.cruda, l);
                    if (salto > c.SALTO_MIN && salto / dt > c.VEL_SALTO) {
                        // Un salto aislado es ruido; si varias lecturas seguidas coinciden en el nuevo lugar, el que estaba mal era el anterior.
                        this.saltos.push(l);
                        const base = this.saltos[0];
                        const coinciden = this.saltos.every((s) => dist(s, base) <= 60);
                        if (!coinciden) this.saltos = [l];
                        if (this.saltos.length < c.SALTO_CONFIRMAN) return { ok: false, motivo: 'salto' };
                        this.varianza = -1; this.hist = []; this.vel = 0; this.saltos = [];
                    } else this.saltos = [];
                }
            }
            this.malasSeguidas = 0;
            const dtS = this.ultimaT === null ? 0 : Math.max(0, (l.t - this.ultimaT) / 1000);
            // Suavizado tipo Kalman: el ruido de proceso crece con la velocidad (a 10 m/s no puede quedarse atrás) y las lecturas precisas pesan más.
            const q = this.vel < 1.0 ? 2.0 : 3 + 0.9 * this.vel;
            if (this.varianza < 0) { this.lat = l.lat; this.lng = l.lng; this.varianza = acc * acc; }
            else {
                this.varianza += dtS * q * q;
                const k = this.varianza / (this.varianza + acc * acc);
                this.lat += k * (l.lat - this.lat);
                this.lng += k * (l.lng - this.lng);
                this.varianza = (1 - k) * this.varianza;
            }
            this.cruda = { lat: l.lat, lng: l.lng };
            this.ultimaT = l.t;
            this.hist.push({ t: l.t, lat: this.lat, lng: this.lng });
            while (this.hist.length > 2 && l.t - this.hist[0].t > c.VENTANA_VEL_MS) this.hist.shift();
            // Velocidad: desplazamiento de las posiciones suavizadas en la ventana (con ≥ 3 s de historia), mezclada con la del dispositivo si es fiable.
            let v = 0;
            const ini = this.hist[0], span = (l.t - ini.t) / 1000;
            if (span >= 3) v = Math.max(0, dist(ini, { lat: this.lat, lng: this.lng }) - 0.3 * acc) / span;      // se descuenta el ruido típico de la posición
            // La velocidad que informa el dispositivo solo se usa si es positiva: el emulador de Android (y algunos teléfonos) informan 0 siempre,
            // y mezclar ese 0 restaría un 40 % a la velocidad real calculada con las posiciones.
            if (Number.isFinite(l.velocidad) && l.velocidad > 0.3 && acc <= 30 && span >= 3) v = 0.6 * v + 0.4 * l.velocidad;
            this.vel = hueco || span < 3 ? 0 : 0.5 * this.vel + 0.5 * v;
            if (this.vel < 0.35) this.vel = 0;                       // por debajo del ruido: quieto
            return { ok: true, lectura: { lat: this.lat, lng: this.lng, precision: Math.min(acc, Math.sqrt(this.varianza)), t: l.t, vel: this.vel, hueco, quieto: this.vel === 0 } };
        }
    }

    // ------------------------------------------------------------------ fases del viaje
    /**
     * @param plan { origen, destino, buses: [{ codigo, nombre, color, subida:{lat,lng}, bajada:{lat,lng}, tramo:[[lng,lat],...] }] }
     * @returns {{ procesar(lectura):Evento[], responder(id, si):Evento[], sinSenal(ms):Evento[], terminar():Evento[], info(), serializar(), restaurar(x) }}
     */
    function crearViaje(plan, opciones = {}) {
        const c = { ...CFG, ...(opciones.cfg || {}) };
        if (!plan || !plan.destino || !Array.isArray(plan.buses) || !plan.buses.length) throw new Error('El viaje no tiene recorrido.');
        // {@code ref}: referencia del recorrido que continúa después de la bajada (ver construirReferencia); la pone la interfaz cuando llega el detalle de la ruta. {@code refMotivo}: por qué no hay.
        const buses = plan.buses.map((b) => ({ ...b, linea: prepararLinea(b.tramo), ref: null, refMotivo: null }));
        const filtro = new FiltroLecturas(c);
        const e = nuevoEstado();
        let ultima = null;

        function nuevoEstado() {
            return {
                fase: 'iniciando', leg: 0, subidas: [], pregunta: null, ultimaT: null, sinSenal: false,
                cdSubida: 0, cdBajada: 0, rapidoDesde: null, rapidoPos: null, lentoDesde: null, lentoPos: null, quietoDesde: null, busRapidoT: 0,
                alertas: { cerca: false, preparate: false, ahora: false }, avanceMax: 0, avanceT: null, avanceSalto: null, dBmin: Infinity, sePaso: false, mejorDist: Infinity,
                desvioT: -Infinity, destinoDesde: null, d0: 0, tFase: 0, velBus: 0, condicionPerdidaDesde: null, dv: dvVacio(),
            };
        }
        /** Estado del DESVÍO del bus (solo cuenta en la fase en_bus). estado: normal → posible → confirmado → atras (la parada quedó atrás); de posible/confirmado se vuelve a normal si el bus
         *  retoma el recorrido ANTES de la bajada. Los avances están en coordenadas de la línea de evaluación: la referencia si la hay (off = avance donde empieza el tramo) y si no, el tramo. */
        function dvVacio(off = 0) {
            return { estado: 'normal', incidente: 0, off, st: { avanceMax: off, avanceT: null, avanceSalto: null }, ult: off, ultT: null, inicioT: null, fueraN: 0, enLineaN: 0, movio: false, pos0: null, ret: null,
                     largo: false, atrasEmitido: false, sigo: false };
        }
        const bus = () => buses[Math.min(e.leg, buses.length - 1)];
        const objetivo = () => (e.fase === 'caminar_final' ? plan.destino : bus().subida);

        function cambiarFase(fase, L, extra = {}) {
            e.fase = fase;
            e.tFase = L ? L.t : e.tFase;
            e.rapidoDesde = e.lentoDesde = e.quietoDesde = null;
            e.mejorDist = Infinity;
            e.pregunta = null;
            e.condicionPerdidaDesde = null;
            e.dv = dvVacio(fase === 'en_bus' && bus().ref ? bus().ref.a : 0);      // cambiar de fase o de bus reinicia el desvío: cada bus parte de cero
            if (L) e.d0 = fase === 'en_bus' ? Math.max(1, bus().linea.total) : Math.max(1, dist(L, objetivo()));
            return { tipo: 'fase', fase, leg: e.leg, ...extra, info: info() };
        }
        function preguntar(id, L, texto) {
            e.pregunta = { id, texto, t: L.t };
            e.condicionPerdidaDesde = null;
            return { tipo: 'pregunta', id, texto, leg: e.leg, info: info() };
        }

        // ---------- fase: caminar / esperando
        function alSubir(L, ev) {
            const b = bus();
            const dSub = dist(L, b.subida);
            e.mejorDist = Math.min(e.mejorDist, dSub);
            // Mientras hay una pregunta abierta no se cambia de fase (la pregunta se retira sola si la situación cambia).
            // En «esperando», alejarse a velocidad de bus no es «volver a caminar»: es el bus arrancando.
            if (!e.pregunta) {
                if (e.fase === 'caminar' && dSub <= c.R_PARADERO && L.vel < c.V_BUS * 0.6) {
                    ev.push(cambiarFase('esperando', L, { texto: 'Llegaste al paradero. Espera el bus que dice «' + letrero(b) + '» en el letrero.' }));
                } else if (e.fase === 'esperando' && dSub > c.R_PARADERO_SALIR && L.vel < c.V_BUS * 0.6) {
                    ev.push(cambiarFase('caminar', L));
                }
            }
            if (e.pregunta) return;
            if (L.vel >= c.V_BUS) { if (e.rapidoDesde === null) { e.rapidoDesde = L.t; e.rapidoPos = L; } } else e.rapidoDesde = null;
            const sostenido = e.rapidoDesde !== null && L.t - e.rapidoDesde >= c.T_BUS_MS && dist(e.rapidoPos, L) >= c.D_BUS_MIN;
            if (sostenido && proyectar(b.linea, L).dist <= c.D_LINEA_SUBIR && L.t >= e.cdSubida) {
                ev.push(preguntar('subida', L, 'Parece que te subiste al bus. ¿Vas en la ruta ' + (b.etiqueta || b.codigo) + '?'));
                return;
            }
            if (dSub - e.mejorDist > c.DESVIO_CAMINA_M && L.t - e.desvioT > c.DESVIO_MSG_MS && e.fase === 'caminar') {
                e.desvioT = L.t; e.mejorDist = dSub;
                ev.push({ tipo: 'desvio', texto: 'Te estás alejando del paradero. Si quieres, toca «Recalcular desde aquí» para buscar otro camino.', info: info() });
            }
        }

        // ---------- fase: en el bus
        /** Metros que faltan para bajar: por el tramo si la persona va sobre él; si no, la distancia directa (y solo si ya se recorrió casi todo, ver enBus). */
        function restante(b, p, dB) {
            if (p.enRuta) return Math.max(0, b.linea.total - p.avance);
            return e.avanceMax >= b.linea.total - c.SIN_RUTA_ALERTA_M ? dB : Math.max(dB, b.linea.total - e.avanceMax);
        }

        /** Posición sobre el tramo del bus: continua (no salta a una parte posterior de la ruta por una lectura mala ni por un tramo vecino). */
        function posicionEnTramo(b, L) { return posicionMonotona(b.linea, e, L, c); }

        function enBus(L, ev) {
            const b = bus();
            const p = posicionEnTramo(b, L);
            if (p.enRuta) e.avanceMax = Math.max(e.avanceMax, p.avance);
            const dB = dist(L, b.bajada);
            // La distancia mínima solo cuenta cerca del final del tramo: pasar a 60 m en línea recta de la bajada por otra calle no es «haber llegado».
            if (e.avanceMax >= b.linea.total - 400) e.dBmin = Math.min(e.dBmin, dB);
            const resta = restante(b, p, dB);
            if (L.vel >= c.V_BUS) { e.busRapidoT = L.t; e.velBus = e.velBus ? 0.8 * e.velBus + 0.2 * L.vel : L.vel; }
            evaluarDesvio(L, b, ev);
            // Mientras el bus está fuera de su recorrido (posible, confirmado o ya con la parada atrás) NINGÚN atajo por distancia directa puede decidir una alerta de bajada ni un «te pasaste»:
            // el mapa y la tarjeta cuentan una sola historia (la del desvío).
            const normal = e.dv.estado === 'normal';
            // Alertas de bajada (una vez cada una). Sobre la ruta manda la distancia RECORRIDA por el tramo: un bus puede pasar a 50 m en línea
            // recta del punto de bajada y faltarle todavía un kilómetro de calles. Una distancia directa pequeña solo cuenta si ya se avanzó casi todo.
            const casiTodo = e.avanceMax >= b.linea.total - c.SIN_RUTA_ALERTA_M;
            const directoValido = !p.enRuta && !p.saltoPendiente && casiTodo;
            const nivel = (resta <= c.ALERTA_AHORA || (directoValido && dB <= c.ALERTA_AHORA)) ? 'ahora' : (resta <= c.ALERTA_PREPARATE ? 'preparate' : (resta <= c.ALERTA_CERCA ? 'cerca' : null));
            const orden = ['cerca', 'preparate', 'ahora'];
            if (nivel && normal) {
                for (const n of orden.slice(0, orden.indexOf(nivel) + 1)) {
                    if (!e.alertas[n]) {
                        e.alertas[n] = true;
                        if (n === nivel) ev.push({ tipo: 'alerta', nivel: n, distancia: Math.round(resta), texto: textoAlerta(n, b, resta), info: info() });
                    }
                }
            }
            // se pasó de la parada
            if (normal && !e.sePaso && e.dBmin <= 300 && dB - e.dBmin >= c.SE_PASO_M && L.vel >= c.V_BUS && e.avanceMax >= b.linea.total - 400) {       // solo si ya recorrió casi todo el tramo (pasar cerca antes de llegar no es pasarse)
                e.sePaso = true;
                ev.push({ tipo: 'se_paso', texto: 'Parece que te pasaste de tu parada. Tranquilo: bájate en la siguiente parada y toca «Recalcular desde aquí» para buscar el camino desde donde estés.', info: info() });
            }
            if (e.pregunta) return;
            // ¿ya se bajó?  (a) camina después del bus, cerca de la parada;  (b) lleva un buen rato quieto en la parada
            const camina = L.vel >= c.V_CAMINA_MIN && L.vel <= c.V_CAMINA_MAX;
            if (camina) { if (e.lentoDesde === null) { e.lentoDesde = L.t; e.lentoPos = L; } } else if (L.vel > c.V_CAMINA_MAX || L.vel < c.V_CAMINA_MIN * 0.5) e.lentoDesde = null;
            const cerca = dB <= c.D_PARADA_CERCA || e.sePaso || e.alertas.ahora;
            const caminaTrasBus = e.lentoDesde !== null && L.t - e.lentoDesde >= c.T_BAJAR_MS && dist(e.lentoPos, L) >= c.D_BAJAR_MIN && L.t - e.busRapidoT <= c.BUS_RECIENTE_MS;
            if (L.vel < 0.5) { if (e.quietoDesde === null) e.quietoDesde = L.t; } else e.quietoDesde = null;
            const quietoEnParada = e.quietoDesde !== null && L.t - e.quietoDesde >= c.QUIETO_MS && dB <= c.D_QUIETO_PARADA;
            // última parada pegada al destino (a veces no hay nada que caminar): estar ya en B y despacio vale como «se bajó»
            const dDest = dist(L, plan.destino);
            if (e.leg === buses.length - 1 && dDest <= c.R_DESTINO_EN_BUS && L.vel <= c.V_CAMINA_MAX) { if (e.destinoDesde === null) e.destinoDesde = L.t; } else e.destinoDesde = null;
            const yaEnDestino = e.destinoDesde !== null && L.t - e.destinoDesde >= c.T_DESTINO_MS;
            if ((caminaTrasBus && cerca || quietoEnParada || yaEnDestino) && L.t >= e.cdBajada) {
                ev.push(preguntar('bajada', L, 'Parece que te bajaste del bus. ¿Ya te bajaste?'));
            }
        }

        // ---------- desvío del bus y «tu parada quedó atrás»
        const TXT_POSIBLE = 'El bus parece haberse apartado de la ruta. Estamos comprobando el recorrido.';
        const TXT_CONFIRMADO = 'El bus se desvió de la ruta habitual. Te aviso si retoma la ruta y ya pasó tu bajada.';
        const TXT_LARGO = 'Pregunta al conductor si pasa por tu parada.';
        const TXT_ATRAS_TITULO = 'Tu parada quedó atrás';
        const TXT_ATRAS = 'El bus retomó la ruta después de tu bajada. Baja en la próxima parada, cuando el bus se detenga.';

        /** Se llama con cada lectura ya filtrada mientras se va en el bus. SALIR: a más de DESVIO_BUS_M de la línea de evaluación (la referencia si hay; si no, el tramo). VOLVER: a menos de
         *  DESVIO_VOLVER_M, con varias lecturas coherentes, avance real a lo largo de la ruta y separación frente a otros tramos (ver «retorno»). «Parada atrás» solo con referencia posterior a la bajada. */
        function evaluarDesvio(L, b, ev) {
            const dv = e.dv, ref = b.ref, linea = ref ? ref.linea : b.linea, sig = L.precision;
            if (dv.estado === 'atras') return;      // incidente ya confirmado: no se reevalúa ni se repite
            if (dv.estado === 'normal') {
                const q = posicionMonotona(linea, dv.st, L, c);
                if (q.enRuta) { dv.st.avanceMax = Math.max(dv.st.avanceMax, q.avance); dv.ult = dv.st.avanceMax; dv.ultT = L.t; return; }
                if (q.saltoPendiente) return;      // un salto de avance sin confirmar no es un desvío
                if (!ref && q.avance >= linea.total - 5) return;      // sin referencia no se sabe qué hay después del final del tramo: seguir de largo no es prueba de desvío
                if (sig > c.DESVIO_PRECISION_MAX) return;      // una lectura muy imprecisa no basta ni para sospechar
                dv.estado = 'posible'; dv.incidente++; dv.inicioT = L.t; dv.fueraN = 1; dv.enLineaN = 0; dv.movio = L.vel >= c.V_BUS * 0.7; dv.pos0 = { lat: L.lat, lng: L.lng }; dv.ret = null; dv.largo = false;
                ev.push({ tipo: 'desvio_posible', texto: TXT_POSIBLE, info: info() });
                return;
            }
            // posible o confirmado
            if (dv.inicioT === null) dv.inicioT = L.t;      // un viaje reanudado empieza a contar con su primera lectura NUEVA
            if (!dv.pos0) dv.pos0 = { lat: L.lat, lng: L.lng };
            const dt = dv.ultT === null ? 600 : Math.max(0, (L.t - dv.ultT) / 1000);
            const periodo = ref && ref.circular ? ref.vuelta : 0;
            const hasta = dv.ult + c.AVANCE_VENTANA_M + c.RETORNO_VEL_MAX * dt, desde = Math.max(0, dv.ult - c.RETORNO_ATRAS_M);
            const { mejor, segundo } = proyectarCandidatos(linea, L, desde, hasta, c.RETORNO_SEP_AVANCE_M, periodo);
            const d = mejor ? mejor.dist : Infinity;
            const sinRef = !ref && !!mejor && mejor.avance >= linea.total - 5;
            if (dv.estado === 'posible') {
                if (d <= c.DESVIO_VOLVER_M && sig <= c.RETORNO_PRECISION_MAX && !sinRef) {
                    dv.enLineaN++;
                    if (dv.enLineaN >= c.DESVIO_POSIBLE_FIN_N) cerrarDesvio(L, mejor, ev, 'regreso');
                    return;
                }
                dv.enLineaN = 0;
                if (d > c.DESVIO_VOLVER_M) {      // entre 60 y 150 m sigue «fuera»: la histéresis evita que una lectura de borde apague y encienda el aviso
                    dv.fueraN++;
                    if (L.vel >= c.V_BUS * 0.7 || (dv.pos0 && dist(dv.pos0, L) >= c.DESVIO_MOV_M)) dv.movio = true;
                    if (dv.fueraN >= c.DESVIO_CONFIRMA_N && L.t - dv.inicioT >= c.DESVIO_CONFIRMA_MS && dv.movio && sig <= c.DESVIO_PRECISION_MAX) {
                        dv.estado = 'confirmado';
                        ev.push({ tipo: 'desvio_confirmado', texto: TXT_CONFIRMADO, info: info() });
                    }
                }
                return;
            }
            if (!dv.largo && L.t - dv.inicioT >= c.DESVIO_LARGO_MS) { dv.largo = true; ev.push({ tipo: 'desvio_largo', texto: TXT_LARGO, info: info() }); }
            retorno(L, b, mejor, segundo, d, sig, sinRef, hasta - desde, periodo, ev);
        }

        /** Cierra un desvío (el bus retomó el recorrido ANTES de la bajada, o un «posible» que nunca se confirmó): vuelve la circulación normal y las alertas ordinarias. */
        function cerrarDesvio(L, mejor, ev, motivo) {
            const dv = e.dv;
            dv.estado = 'normal'; dv.fueraN = 0; dv.enLineaN = 0; dv.ret = null; dv.largo = false; dv.inicioT = null; dv.pos0 = null; dv.movio = false;
            if (mejor) { dv.ult = Math.max(dv.ult, mejor.avance); dv.st.avanceMax = Math.max(dv.st.avanceMax, mejor.avance); }
            dv.st.avanceT = L.t; dv.st.avanceSalto = null; dv.ultT = L.t;
            ev.push({ tipo: 'desvio_fin', motivo, info: info() });
        }

        /** Racha de lecturas que prueban que el bus volvió: cada una cerca de la línea, precisas, con la línea claramente más cerca que otro tramo no contiguo y con un avance coherente (nunca
         *  hacia atrás más que el ruido, ni a saltos). Se confirma con RETORNO_N lecturas, RETORNO_MS de duración y RETORNO_GANA_M de avance a lo largo de la RUTA; un cruce, una glorieta, un semáforo,
         *  una vía paralela o el sentido contrario no cumplen alguna. Una lectura mala o un hueco de GPS rompen la racha. */
        function retorno(L, b, mejor, segundo, d, sig, sinRef, ventana, periodo, ev) {
            const dv = e.dv, ref = b.ref;
            // En una ruta circular con la vuelta duplicada, si la ventana de búsqueda abarca (casi) una vuelta entera el mismo punto aparece dos veces: no se puede decidir cuál es.
            const ambiguaVuelta = periodo > 0 && ventana >= periodo - 2 * c.RETORNO_SEP_AVANCE_M;
            const aceptable = !!mejor && !sinRef && !ambiguaVuelta && sig <= c.RETORNO_PRECISION_MAX && d <= c.DESVIO_VOLVER_M && (!segundo || segundo.dist - mejor.dist >= c.RETORNO_SEPARACION_M);
            if (!aceptable) { dv.ret = null; return; }
            const pos = { lat: L.lat, lng: L.lng };
            const nueva = () => ({ n: 1, t0: L.t, tU: L.t, a0: mejor.avance, aU: mejor.avance, p0: pos, pU: pos, sig, sigU: sig });
            const r = dv.ret;
            if (!r) { dv.ret = nueva(); return; }
            const da = mejor.avance - r.aU, dtc = Math.max(0, (L.t - r.tU) / 1000);
            if (da < -(sig + r.sigU) || da > c.RETORNO_VEL_MAX * dtc + 40) { dv.ret = nueva(); return; }
            r.n++; r.tU = L.t; r.aU = Math.max(r.aU, mejor.avance); r.pU = pos; r.sig = Math.max(r.sig, sig); r.sigU = sig;
            const gana = r.aU - r.a0, desp = dist(r.p0, r.pU);
            if (desp > 2 * r.sig && gana < 0.6 * desp) { dv.ret = nueva(); return; }      // se mueve, pero no a lo largo de la ruta
            if (r.n < c.RETORNO_N || L.t - r.t0 < c.RETORNO_MS || gana < c.RETORNO_GANA_M) return;
            // Hay evidencia de que volvió al recorrido. ¿Antes de la parada (o dentro de su margen) o claramente después?
            const margen = Math.max(c.RETORNO_AVANCE_MIN_M, c.RETORNO_K_PREC * r.sig);
            if (ref) {
                if (r.a0 >= ref.b + margen) {
                    if (ref.despues < c.REF_DESPUES_MIN_M) { dv.ret = null; return; }      // la ruta termina justo después de la bajada: no hay con qué probarlo
                    marcarAtras(L, ev);
                } else cerrarDesvio(L, mejor, ev, 'retomo_antes');
            } else if (r.aU <= b.linea.total - Math.max(margen, c.RETORNO_GANA_M)) cerrarDesvio(L, mejor, ev, 'retomo_antes');      // sin referencia solo se puede afirmar «todavía no llega a la bajada»
            else dv.ret = null;
        }

        /** La parada quedó atrás. UNA sola vez por incidente. Cierra de paso el «te pasaste» y las alertas ordinarias para que no salgan dos avisos por el mismo hecho. */
        function marcarAtras(L, ev) {
            const dv = e.dv;
            dv.estado = 'atras'; dv.atrasEmitido = true; dv.ret = null;
            e.sePaso = true; e.alertas = { cerca: true, preparate: true, ahora: true };
            ev.push({ tipo: 'parada_atras', incidente: dv.incidente, titulo: TXT_ATRAS_TITULO, texto: TXT_ATRAS, info: info() });
        }

        /** La interfaz entrega la referencia del recorrido (resultado de construirReferencia) o el motivo por el que no hay. Se puede llamar en cualquier momento, también con el viaje en marcha. */
        function ponerReferencia(leg, r) {
            const b = buses[leg]; if (!b) return false;
            if (!r || !r.ok || !Array.isArray(r.coords)) { b.ref = null; b.refMotivo = (r && r.motivo) || 'sin-datos'; return false; }
            b.ref = { linea: prepararLinea(r.coords), a: r.a, b: r.b, despues: r.despues, circular: !!r.circular, invertida: !!r.invertida, vuelta: r.vuelta || 0 };
            b.refMotivo = null;
            if (leg === Math.min(e.leg, buses.length - 1)) {      // el avance ya medido sobre el tramo pasa a coordenadas de la referencia
                const dv = e.dv, delta = r.a - dv.off;
                if (delta) { dv.st.avanceMax += delta; dv.ult += delta; dv.off = r.a; dv.st.avanceSalto = null; dv.ret = null; }
            }
            return true;
        }
        function marcarReferencia(leg, motivo) { const b = buses[leg]; if (b && !b.ref) b.refMotivo = motivo; }
        const refEstado = (b) => (b.ref ? 'lista' : b.refMotivo || 'pendiente');

        // ---------- fase: caminar (final)
        function caminarFinal(L, ev) {
            const d = dist(L, plan.destino);
            e.mejorDist = Math.min(e.mejorDist, d);
            if (d <= c.R_LLEGADA) {
                ev.push(cambiarFase('llegaste', L, { texto: 'Llegaste a tu destino.' }));
                ev.push({ tipo: 'llego', info: info() });
                return;
            }
            if (d - e.mejorDist > c.DESVIO_CAMINA_M && L.t - e.desvioT > c.DESVIO_MSG_MS) {
                e.desvioT = L.t; e.mejorDist = d;
                ev.push({ tipo: 'desvio', texto: 'Te estás alejando de tu destino. Si quieres, toca «Recalcular desde aquí» para buscar otro camino.', info: info() });
            }
        }

        /** «Unas 3 cuadras»: una cuadra mide ≈ 100 m; más fácil de imaginar que los metros. */
        const cuadras = (m) => { if (m < 60) return 'menos de una cuadra'; const c = Math.max(1, Math.round(m / 100)); return c === 1 ? 'una cuadra' : 'unas ' + c + ' cuadras'; };
        const letrero = (b) => { const t = b.etiqueta || b.codigo; return t; };
        /** «Falta una cuadra» / «faltan unas 3 cuadras» / «falta menos de una cuadra». */
        const faltan = (m) => (m < 150 ? 'falta ' : 'faltan ') + cuadras(m);
        function textoAlerta(n, b, resta) {
            if (n === 'cerca') return 'Te acercas a tu punto de bajada' + (b.paraderoBajada ? ' (paradero «' + b.paraderoBajada + '»)' : '') + ': ' + faltan(resta) + '.';
            if (n === 'preparate') return 'Prepárate para bajar: ' + faltan(resta) + '.';
            return 'Tu punto de bajada está aquí cerca. Baja cuando el bus se detenga.' + (b.paraderoBajada ? ' Paradero «' + b.paraderoBajada + '».' : '');
        }

        // ---------- API
        function procesar(raw) {
            const ev = [];
            if (e.fase === 'llegaste' || e.fase === 'terminado') return ev;
            const r = filtro.procesar(raw);
            if (!r.ok) {
                ev.push({ tipo: 'descartada', motivo: r.motivo });
                if (filtro.malasSeguidas === c.SENAL_DEBIL_N) ev.push({ tipo: 'senal_debil', texto: 'La señal del GPS está débil. Si puedes, ponte en un lugar abierto, sin techo, para encontrarte mejor.' });
                return ev;
            }
            const L = r.lectura;
            const volvio = e.sinSenal || L.hueco;
            if (volvio && e.fase !== 'iniciando') {
                e.sinSenal = false;
                e.rapidoDesde = e.lentoDesde = e.quietoDesde = null;     // los cronómetros de «sostenido» no cruzan un hueco
                // Tras un hueco de GPS el desvío exige lecturas NUEVAS: la racha de retorno se rompe y un «posible» sin confirmar vuelve a contar desde la primera lectura posterior.
                e.dv.ret = null; if (e.dv.estado === 'posible') { e.dv.fueraN = 0; e.dv.enLineaN = 0; e.dv.inicioT = null; e.dv.movio = false; e.dv.pos0 = null; }
                ev.push({ tipo: 'senal_recuperada', texto: 'Recuperé tu ubicación.' });
            }
            e.sinSenal = false;
            ultima = L;
            if (e.fase === 'iniciando') {
                const d = dist(L, bus().subida);
                e.d0 = Math.max(1, d);
                ev.push(cambiarFase(d <= c.R_PARADERO ? 'esperando' : 'caminar', L, { inicial: true, distanciaAOrigen: Math.round(dist(L, plan.origen || bus().subida)) }));
            }
            if (e.pregunta) {
                // Una pregunta sin respuesta se retira sola si la condición que la causó dejó de cumplirse un buen rato.
                const sigue = e.pregunta.id === 'subida' ? L.vel >= c.V_BUS * 0.7 : (L.vel <= c.V_CAMINA_MAX || e.quietoDesde !== null);
                if (sigue) e.condicionPerdidaDesde = null;
                else {
                    if (e.condicionPerdidaDesde === null) e.condicionPerdidaDesde = L.t;
                    if (L.t - e.condicionPerdidaDesde >= c.PREGUNTA_VENCE_MS) {
                        const id = e.pregunta.id;
                        e.pregunta = null; e.condicionPerdidaDesde = null; e.rapidoDesde = e.lentoDesde = null;
                        ev.push({ tipo: 'pregunta_retirada', id, info: info() });
                    }
                }
            }
            if (e.fase === 'caminar' || e.fase === 'esperando') alSubir(L, ev);
            else if (e.fase === 'en_bus') enBus(L, ev);
            else if (e.fase === 'caminar_final') caminarFinal(L, ev);
            ev.push({ tipo: 'progreso', lectura: L, info: info() });
            return ev;
        }

        function responder(id, si) {
            const ev = [];
            if (!e.pregunta || e.pregunta.id !== id) return ev;
            const L = ultima || { t: e.tFase };
            if (id === 'subida') {
                if (si) { if (!e.subidas.includes(e.leg)) e.subidas.push(e.leg); ev.push(cambiarFase('en_bus', L, { texto: 'Vas en la ruta ' + (bus().etiqueta || bus().codigo) + '.' })); e.alertas = { cerca: false, preparate: false, ahora: false }; e.avanceMax = 0; e.avanceT = null; e.avanceSalto = null; e.dBmin = Infinity; e.sePaso = false; e.busRapidoT = L.t; }
                else { e.pregunta = null; e.cdSubida = L.t + c.COOL_SUBIDA_MS; e.rapidoDesde = null; ev.push({ tipo: 'pregunta_respondida', id, si, info: info() }); }
            } else if (id === 'bajada') {
                if (si) {
                    // Si el bus iba fuera de su recorrido (o la parada quedó atrás), la persona NO se bajó donde el plan decía: se entrega su posición real para calcular la caminata desde ahí.
                    const real = e.dv.estado !== 'normal' ? { desviada: true, estadoDesvio: e.dv.estado, bajadaReal: ultima ? { lat: ultima.lat, lng: ultima.lng, precision: Math.round(ultima.precision), t: ultima.t } : null } : {};
                    if (e.leg < buses.length - 1) { e.leg++; ev.push(cambiarFase('caminar', L, { transbordo: true, texto: 'Camina hasta el paradero para tomar la ruta ' + (bus().etiqueta || bus().codigo) + '.', ...real })); }
                    else ev.push(cambiarFase('caminar_final', L, { texto: 'Ya casi: camina hasta tu destino.', ...real }));
                } else { e.pregunta = null; e.cdBajada = L.t + c.COOL_BAJADA_MS; e.lentoDesde = e.quietoDesde = null; ev.push({ tipo: 'pregunta_respondida', id, si, info: info() }); }
            }
            return ev;
        }

        /** «Ya me subí» / «Ya me bajé» tocados por la persona (el bus puede ir lento y no alcanzar el umbral automático). Usa las mismas transiciones que la pregunta. */
        function confirmarManual(id) {
            const fase = id === 'subida' ? (e.fase === 'caminar' || e.fase === 'esperando') : e.fase === 'en_bus';
            if (!fase) return [];
            if (!ultima) return [];                       // sin una lectura válida no se sabe dónde está: se espera la primera
            if (!e.pregunta || e.pregunta.id !== id) e.pregunta = { id, texto: '', t: ultima.t };
            return responder(id, true);
        }

        /** «Sigo en el bus» (recuadro «Tu bajada está aquí»): la persona dice que NO se bajó. Se conserva la fase y el bus y se enfría la pregunta automática «¿ya te bajaste?» (como un «no»). */
        function sigoEnBus() {
            if (e.fase !== 'en_bus') return [];
            const t = ultima ? ultima.t : Date.now();
            e.cdBajada = t + c.COOL_BAJADA_MS; e.lentoDesde = e.quietoDesde = null;
            if (e.dv.estado === 'atras') e.dv.sigo = true;      // la instrucción «tu parada quedó atrás» sigue en la tarjeta, pero el recuadro urgente no vuelve a salir por sí solo
            return [{ tipo: 'bajada_aplazada', info: info() }];
        }

        function sinSenal(ms) {
            if (e.fase === 'iniciando' || e.fase === 'llegaste' || e.fase === 'terminado') return [];
            if (ms >= 20000 && !e.sinSenal) { e.sinSenal = true; return [{ tipo: 'sin_senal', texto: 'Perdí tu ubicación. Sigo buscándola; cuando vuelva, continúo desde donde ibas.', info: info() }]; }
            return [];
        }

        function terminar() { e.fase = 'terminado'; e.pregunta = null; e.dv = dvVacio(); return [{ tipo: 'fase', fase: 'terminado', info: info() }]; }

        function info() {
            const b = bus();
            const L = ultima;
            let distancia = null, etaS = null, titulo, instruccion, progreso = 0;
            if (e.fase === 'caminar' || e.fase === 'esperando' || e.fase === 'caminar_final') {
                const d = L ? dist(L, objetivo()) : null;
                distancia = d === null ? null : Math.round(d);
                etaS = d === null ? null : d / c.V_CAMINA_ETA;
                progreso = d === null ? 0 : Math.max(0, Math.min(1, 1 - d / e.d0));
            }
            // Con el bus fuera de su recorrido (o con la parada atrás) el cálculo ordinario de «cuánto falta» ya no aplica: tiempo y distancia pasan a ser una estimación INCIERTA (sin cifras).
            const dv = e.dv, fueraDeRuta = e.fase === 'en_bus' && dv.estado !== 'normal';
            if (e.fase === 'en_bus' && L) {
                const dB = dist(L, b.bajada);
                const p = proyectar(b.linea, L, Math.max(0, e.avanceMax - 100), e.avanceMax + c.AVANCE_VENTANA_M + c.AVANCE_VEL_MAX * 10);
                const resta = restante(b, { ...p, enRuta: p.dist <= c.DESVIO_BUS_M }, dB);
                if (fueraDeRuta) progreso = Math.max(0, Math.min(1, e.avanceMax / Math.max(1, b.linea.total)));      // lo avanzado por la ruta, sin deshacerlo
                else { distancia = Math.round(resta); etaS = resta / Math.max(2.5, e.velBus || c.V_BUS_ETA); progreso = Math.max(0, Math.min(1, 1 - resta / e.d0)); }
            }
            const trans = e.leg > 0 && e.fase === 'caminar';
            switch (e.fase) {
                case 'iniciando': titulo = 'Buscando tu ubicación'; instruccion = 'Un momento: espero una lectura buena del GPS.'; break;
                case 'caminar': titulo = trans ? 'Camina al transbordo' : 'Camina al punto de subida'; instruccion = 'Camina hasta el paradero de la ruta ' + letrero(b) + (b.paraderoSubida ? ' (paradero «' + b.paraderoSubida + '»)' : '') + (distancia ? '. Te faltan ' + cuadras(distancia) : '') + '.'; break;
                case 'esperando': titulo = 'Espera el bus'; instruccion = 'Estás en el paradero. Busca el bus que dice «' + letrero(b) + '» en el letrero y súbete. Yo te aviso cuando arranques.'; break;
                case 'en_bus': titulo = 'Vas en el bus ' + (b.etiqueta || b.codigo); instruccion = dv.estado === 'atras' ? TXT_ATRAS_TITULO + '. ' + TXT_ATRAS : dv.estado === 'confirmado' ? TXT_CONFIRMADO + (dv.largo ? ' ' + TXT_LARGO : '') : dv.estado === 'posible' ? TXT_POSIBLE : e.alertas.ahora ? 'Tu punto de bajada está aquí cerca. Baja cuando el bus se detenga.' : e.alertas.preparate ? 'Prepárate para bajar.' : e.alertas.cerca ? 'Te acercas a tu punto de bajada.' : e.sinSenal ? 'No tengo tu ubicación en este momento y sigo buscándola. Te aviso antes de tu parada en cuanto la recupere.' : 'Todo va bien. Te aviso antes de tu parada: no tienes que mirar el celular.'; break;
                case 'caminar_final': titulo = 'Camina a tu destino'; instruccion = 'Sigue caminando hasta tu destino' + (distancia ? '. Te faltan ' + cuadras(distancia) : '') + '.'; break;
                case 'llegaste': titulo = '¡Llegaste!'; instruccion = 'Terminó tu viaje.'; break;
                default: titulo = 'Viaje terminado'; instruccion = '';
            }
            return {
                fase: e.fase, leg: e.leg, buses: buses.length, codigo: b.codigo, etiqueta: b.etiqueta || b.codigo, nombre: b.nombre, color: b.color, titulo, instruccion,
                distancia, etaMin: etaS === null ? null : Math.max(1, Math.round(etaS / 60)), progreso, pregunta: e.pregunta ? { ...e.pregunta } : null,
                precision: L ? Math.round(L.precision) : null, velKmh: L ? Math.round(L.vel * 3.6) : null, sinSenal: e.sinSenal,
                alertas: { ...e.alertas }, sePaso: e.sePaso,
                // Contrato del desvío para la interfaz (y para el mapa: ambos cuentan la misma historia). estado: normal | posible | confirmado | atras. {@code incierta}: tiempo y distancia ya no son fiables.
                estimacion: fueraDeRuta ? 'incierta' : 'normal',
                desvio: { estado: e.fase === 'en_bus' ? dv.estado : 'normal', incidente: dv.incidente, incierta: fueraDeRuta, prolongado: e.fase === 'en_bus' && dv.largo, sigo: e.fase === 'en_bus' && dv.sigo,
                          referencia: refEstado(b), paradaAtras: e.fase === 'en_bus' && dv.estado === 'atras', atrasEmitido: dv.atrasEmitido },
            };
        }

        /** Solo lo MÍNIMO para reanudar: la fase, el avance, las alertas ya dadas y, si hay un desvío en curso, su estado (sin lecturas ni geometría). */
        function serializar() {
            const dv = e.dv, activo = e.fase === 'en_bus' && (dv.estado !== 'normal' || dv.atrasEmitido);
            return JSON.parse(JSON.stringify({ fase: e.fase, leg: e.leg, subidas: e.subidas, alertas: e.alertas, avanceMax: e.avanceMax, sePaso: e.sePaso, velBus: e.velBus,
                ...(activo ? { dv: { estado: dv.estado, incidente: dv.incidente, atrasEmitido: dv.atrasEmitido, largo: dv.largo, sigo: dv.sigo, ult: Math.round(dv.ult - dv.off) } } : {}) }));
        }
        function restaurar(x) {
            if (!x || !x.fase || x.fase === 'llegaste' || x.fase === 'terminado') return;
            Object.assign(e, { fase: x.fase === 'iniciando' ? 'iniciando' : x.fase, leg: Math.min(x.leg || 0, buses.length - 1), alertas: x.alertas || e.alertas, avanceMax: x.avanceMax || 0, sePaso: !!x.sePaso, velBus: x.velBus || 0 });
            // Subidas CONFIRMADAS (la evidencia de que se viajó en bus): un estado guardado de una versión anterior no las traía, y se deducen de la fase (en un bus o después de bajar de uno se subió a ese tramo).
            e.subidas = Array.isArray(x.subidas) ? x.subidas.filter((n) => Number.isInteger(n) && n >= 0 && n < buses.length) : [];
            if (!Array.isArray(x.subidas)) { const hasta = e.fase === 'en_bus' || e.fase === 'caminar_final' ? e.leg : e.leg - 1; for (let i = 0; i <= hasta; i++) e.subidas.push(i); }
            e.pregunta = null;
            // Estado guardado de una versión anterior: sin «dv» queda en circulación normal. Con «dv» se conserva el estado, pero SIN contadores ni lecturas: un caso incierto espera lecturas nuevas.
            const g = x.dv;
            e.dv = dvVacio(e.fase === 'en_bus' && bus().ref ? bus().ref.a : 0);
            if (e.fase === 'en_bus' && g && ['posible', 'confirmado', 'atras'].includes(g.estado)) {
                const dv = e.dv;
                dv.estado = g.estado; dv.incidente = Math.max(1, Number(g.incidente) || 1); dv.atrasEmitido = !!g.atrasEmitido || g.estado === 'atras'; dv.largo = !!g.largo; dv.sigo = !!g.sigo;
                dv.ult = dv.off + Math.max(0, Number(g.ult) || 0); dv.st.avanceMax = dv.ult; dv.ultT = null; dv.inicioT = null;
            }
        }

        return { procesar, responder, subidas: () => e.subidas.length, confirmarSubida: () => confirmarManual('subida'), confirmarBajada: () => confirmarManual('bajada'), sigoEnBus, sinSenal, terminar, info, serializar, restaurar, filtro, cfg: c, ponerReferencia, marcarReferencia, referencia: (leg) => { const b = buses[Math.max(0, Math.min(leg === undefined ? e.leg : leg, buses.length - 1))]; return { estado: refEstado(b), a: b.ref ? b.ref.a : null, b: b.ref ? b.ref.b : null, despues: b.ref ? b.ref.despues : null }; } };
    }

    S.ViajeNucleo = { CFG, dist, prepararLinea, proyectar, proyectarCandidatos, construirReferencia, dividirLinea, posicionMonotona, FiltroLecturas, crearViaje };
})();
