'use strict';
/* Indicaciones paso a paso de una opción del resultado (planificador A/B y flujo guiado comparten ESTE modelo).
   · Se arma desde los datos de la opción recibida (no desde un párrafo del DOM): código y nombre popular de la ruta, puntos y paraderos de subida y bajada de ESA opción y las distancias de cada caminata.
   · Los pasos usan verbos simples: Camina, Toma la ruta, Bájate, Cambia de bus, Llega a tu destino. Nada depende del color.
   · Nada se inventa: sin nombre de paradero se usan los rótulos del mapa «Sube aquí» / «Baja aquí»; una caminata en línea recta se dice aproximada; no hay «gira a la derecha» ni número de paradas.
   · Una opción en sentido contrario NO recibe pasos de embarque. «Ver subida/bajada» solo centra el mapa: no inicia el viaje ni cambia de opción.
   · Cada tarjeta tiene su propio modelo: una caminata que llega tarde actualiza solo su paso, sin mover el foco (se cambia el texto, no la lista). */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const CORTA_M = 15;      // por debajo no se dice «camina»: ya estás ahí

    const num = (x) => (Number.isFinite(Number(x)) ? Number(x) : 0);
    /** «unos 30 m», «unos 130 m», «unos 1,2 km». */
    function distancia(m) {
        m = num(m);
        if (m < 1000) return 'unos ' + Math.max(10, Math.round(m / 10) * 10) + ' m';
        return 'unos ' + (m / 1000).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km';
    }
    /** Nombre útil de un punto elegido: nada de coordenadas ni de «Punto en mapa». Solo lo anterior a la primera coma. */
    function nombreUtil(p) {
        const n = p && p.nombre ? String(p.nombre).split(',')[0].trim() : '';
        if (!n || n.length > 70 || /^(punto en (el )?mapa|sitio de prueba)/i.test(n) || /^-?\d+[.,]\d+/.test(n)) return null;
        return n;
    }
    const ruta = (codigo) => {
        const pop = S.rutaPopular ? S.rutaPopular(codigo) : '';
        return pop && pop !== codigo ? pop + ' (' + codigo + ')' : String(codigo || '');
    };
    const comillas = (t) => '«' + t + '»';
    const punto = (g) => (g && Array.isArray(g.coordinates) && g.coordinates.length >= 2 ? { lat: g.coordinates[1], lng: g.coordinates[0] } : null);

    function ctxDe(origen, destino) {
        const o = nombreUtil(origen), d = nombreUtil(destino);
        return { origen: origen && origen.deGps ? 'tu ubicación' : o ? comillas(o) : 'tu punto de salida', destino: d ? comillas(d) : 'tu destino' };
    }
    /** El lugar de subida o bajada tal como se nombra: el paradero de ESA opción o el rótulo del marcador. */
    const lugarSube = (paradero, rotulo) => (paradero ? 'el paradero ' + comillas(paradero) : comillas(rotulo));
    const lugarBaja = (paradero, rotulo) => (paradero ? 'el paradero ' + comillas(paradero) : comillas(rotulo));

    /** Un paso de caminata (índice 0 = inicial, 1 = del cambio, 2 = final). */
    function caminar(i, m, calles, desde, hasta, extra = {}) {
        return { tipo: 'walk', verbo: 'Camina', caminata: i, metros: num(m), calles: !!calles, desde, hasta, ...extra };
    }
    function textoCaminata(p) {
        if (p.metros < CORTA_M) return p.sinCaminata;
        const d = distancia(p.metros) + (p.calles ? '' : ' (aprox., en línea recta)');
        return p.prefijo ? p.prefijo + ' camina ' + d + ' ' + p.hasta + '.' : 'Camina ' + d + (p.desde ? ' desde ' + p.desde : '') + ' ' + p.hasta + '.';
    }
    /** La frase completa de un paso (una caminata muy corta no se dice «camina 0 m»: se dice que ya estás ahí o que llegaste). */
    const frase = (p) => (p.tipo === 'walk' ? textoCaminata(p) : p.texto);

    // ---------------------------------------------------------------- modelos
    function deOpcion(o, origen, destino) {
        const c = ctxDe(origen, destino);
        const sube = punto(o.puntoSubida), baja = punto(o.puntoBajada);
        const contraria = o.sentidoPermitido === false;
        const nombre = ruta(o.codigo);
        const m = { tipo: contraria ? 'contraria' : 'directa', id: o.id || null, codigos: [o.codigo], titulo: 'Ruta ' + nombre, detalle: contraria ? 'Sentido contrario' : 'Sin transbordo', pasos: [], aviso: null, aproximada: false };
        if (o.variante === 'BAJAR_Y_CAMINAR') m.detalle = 'Baja y camina';
        else if (o.variante === 'SOLO_SEGUNDA_RUTA') m.detalle = 'Una sola ruta';
        else if (o.variante === 'MAS_RAPIDA' && !contraria) m.detalle = 'Sin transbordo · más rápida';
        if (contraria) {      // nunca instrucciones de embarque como si fuera viable
            m.aviso = o.advertencia || 'Este bus pasa por aquí en sentido contrario a tu viaje: no sirve para subirte en este punto.';
            return m;
        }
        const subeTxt = lugarSube(o.paraderoSubida, 'Sube aquí'), bajaTxt = lugarBaja(o.paraderoBajada, 'Baja aquí');
        const calles = !!o.caminataPorCalles;
        const ini = caminar(0, o.acercamientoInicioMetros, calles, c.origen, 'hasta ' + subeTxt, { sinCaminata: 'Ya estás en el punto de subida.' });
        const fin = caminar(2, o.acercamientoFinMetros, calles, null, 'hasta ' + c.destino, { prefijo: o.paraderoBajada ? 'Desde el paradero ' + comillas(o.paraderoBajada) + ',' : null, sinCaminata: 'Llegas a tu destino.' });
        m.pasos.push(
            { ...ini, foco: sube && { ...sube, etiqueta: 'Ver subida', clave: 'sube' } },
            { tipo: 'bus', verbo: 'Toma', texto: 'Toma la ruta ' + nombre + '.', detalle: o.recorridoKm ? 'Vas unos ' + num(o.recorridoKm).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km en el bus.' : null },
            { tipo: 'baja', verbo: 'Bájate', texto: 'Bájate en ' + bajaTxt + '.', foco: baja && { ...baja, etiqueta: 'Ver bajada', clave: 'baja' } },
            fin);
        m.aproximada = !calles;
        return m;
    }

    function deTransbordo(t, origen, destino) {
        const c = ctxDe(origen, destino);
        const a = t.primerBus, b = t.segundoBus;
        const sube1 = punto(a.puntoSubida), baja1 = punto(a.puntoBajada), sube2 = punto(b.puntoSubida), baja2 = punto(b.puntoBajada);
        const tx1 = lugarSube(a.paraderoSubida, 'Sube al primer bus'), bx1 = lugarBaja(a.paraderoBajada, 'Baja del primer bus');
        const tx2 = lugarSube(b.paraderoSubida, 'Sube al segundo bus'), bx2 = lugarBaja(b.paraderoBajada, 'Bajada final');
        const cambio = num(t.caminataCambio && t.caminataCambio.metros);
        const calles = (w) => !!(w && Array.isArray(w.coordinates) && w.coordinates.length > 1);
        const m = { tipo: 'transbordo', id: t.id || null, codigos: [a.codigo, b.codigo], titulo: 'Ruta ' + ruta(a.codigo) + ' + Ruta ' + ruta(b.codigo), detalle: '1 transbordo · 2 buses', pasos: [], aviso: null, aproximada: false };
        const ini = caminar(0, t.caminataInicio && t.caminataInicio.metros, calles(t.caminataInicio), c.origen, 'hasta ' + tx1, { sinCaminata: 'Ya estás en el punto de subida del primer bus.' });
        const camb = caminar(1, cambio, calles(t.caminataCambio), null, 'hasta ' + tx2, { sinCaminata: 'Cambia de bus: el segundo bus se toma donde te bajaste, sin caminar.' });
        const fin = caminar(2, t.caminataFin && t.caminataFin.metros, calles(t.caminataFin), null, 'hasta ' + c.destino, { prefijo: b.paraderoBajada ? 'Desde el paradero ' + comillas(b.paraderoBajada) + ',' : null, sinCaminata: 'Llegas a tu destino.' });
        m.pasos.push(
            { ...ini, foco: sube1 && { ...sube1, etiqueta: 'Ver subida', clave: 'sube1' } },
            { tipo: 'bus', verbo: 'Toma', texto: 'Toma el primer bus: la ruta ' + ruta(a.codigo) + '.', detalle: a.recorridoKm ? 'Vas unos ' + num(a.recorridoKm).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km en este bus.' : null },
            { tipo: 'baja', verbo: 'Bájate', texto: 'Bájate en ' + bx1 + '.', foco: baja1 && { ...baja1, etiqueta: 'Ver bajada', clave: 'baja1' } },
            { ...camb, verbo: cambio < CORTA_M ? 'Cambia de bus' : 'Camina', foco: sube2 && { ...sube2, etiqueta: 'Ver cambio', clave: 'sube2' } },
            { tipo: 'bus', verbo: 'Toma', texto: 'Toma el segundo bus: la ruta ' + ruta(b.codigo) + '.', detalle: b.recorridoKm ? 'Vas unos ' + num(b.recorridoKm).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km en este bus.' : null },
            { tipo: 'baja', verbo: 'Bájate', texto: 'Bájate en ' + bx2 + '.', foco: baja2 && { ...baja2, etiqueta: 'Ver bajada', clave: 'baja2' } },
            fin);
        m.aproximada = m.pasos.some((p) => p.tipo === 'walk' && p.metros >= CORTA_M && !p.calles);
        return m;
    }

    /** «Por qué la recomendamos» SOLO con datos estructurados del servidor (etiquetas de comparación y número de buses): nada se deduce del texto libre. */
    function porQue(item, modelo) {
        if (!item) return '';
        const et = new Set(item.etiquetas || []);
        const partes = [];
        if (modelo.tipo === 'transbordo') partes.push('Usa dos buses con un transbordo.');
        else if (item.buses === 1 || et.has('SIN_TRANSBORDO')) partes.push('Te lleva con un solo bus, sin transbordo.');
        if (et.has('PRIMER_BUS_MAS_CERCANO')) partes.push('Menos caminata hasta el primer bus.');
        if (et.has('MENOR_CAMINATA_TOTAL')) partes.push('Menos caminata en total.');
        if (et.has('MENOR_TIEMPO')) partes.push('Menor tiempo estimado.');
        return partes.join(' ');
    }

    // ---------------------------------------------------------------- vista
    function crear(modelo, { alVer = null } = {}) {
        const sec = document.createElement('section');
        sec.className = 'itinerario'; sec.setAttribute('aria-label', 'Indicaciones de esta opción'); sec.dataset.tipo = modelo.tipo;
        const enc = document.createElement('p'); enc.className = 'itin-encabezado';
        const etiqueta = document.createElement('span'); etiqueta.className = 'itin-etiqueta';
        const titulo = document.createElement('strong'); titulo.className = 'itin-titulo'; titulo.textContent = modelo.titulo;
        const det = document.createElement('span'); det.className = 'itin-detalle'; det.textContent = modelo.detalle;
        enc.append(etiqueta, titulo, document.createTextNode(' · '), det);
        const pq = document.createElement('p'); pq.className = 'itin-porque'; pq.hidden = true;
        sec.append(enc, pq);
        const filas = [];
        if (modelo.aviso) {
            const a = document.createElement('p'); a.className = 'itin-aviso'; a.setAttribute('role', 'note'); a.textContent = modelo.aviso; sec.append(a);
        } else {
            const ol = document.createElement('ol'); ol.className = 'itin-pasos';
            modelo.pasos.forEach((p, i) => {
                const li = document.createElement('li'); li.className = 'itin-paso ' + p.tipo; li.dataset.paso = String(i + 1);
                const texto = document.createElement('span'); texto.className = 'itin-texto';
                li.append(texto);
                if (p.detalle) { const d = document.createElement('small'); d.className = 'itin-nota-paso'; d.textContent = p.detalle; li.append(d); }
                if (p.foco && alVer) {
                    const b = document.createElement('button'); b.type = 'button'; b.className = 'secondary itin-ver'; b.textContent = p.foco.etiqueta; b.dataset.clave = p.foco.clave;
                    b.setAttribute('aria-label', p.foco.etiqueta + ' en el mapa');
                    b.addEventListener('click', () => alVer(p.foco));
                    li.append(b);
                }
                ol.append(li); filas.push({ li, texto, p });
            });
            sec.append(ol);
            const nota = document.createElement('p'); nota.className = 'itin-nota'; nota.hidden = true;
            nota.textContent = 'Las caminatas marcadas «aprox.» se midieron en línea recta: todavía no hay un trazado a pie por calles para esa parte.';
            sec.append(nota);
            const pintar = () => {
                filas.forEach(({ texto, p }) => { texto.textContent = frase(p); });
                nota.hidden = !modelo.pasos.some((p) => p.tipo === 'walk' && p.metros >= CORTA_M && !p.calles);
            };
            pintar();
            sec._pintar = pintar;
        }
        return {
            el: sec, modelo,
            /** La caminata por calles llegó: su paso pasa a ser exacto. Solo cambia el texto de ESE paso (el foco y la lista quedan como están). */
            actualizar(indice, datos) {
                const paso = modelo.pasos.find((p) => p.tipo === 'walk' && p.caminata === indice);
                if (!paso || !datos || !Number.isFinite(Number(datos.metros))) return;
                paso.metros = num(datos.metros); paso.calles = true;
                if (sec._pintar) sec._pintar();
                window.dispatchEvent(new CustomEvent('spevb-itinerario', { detail: { caminata: indice } }));
            },
            encabezado(esRecomendada) { etiqueta.textContent = esRecomendada ? 'Recomendada · ' : 'Opción seleccionada · '; },
            porQue(texto) { pq.textContent = texto ? 'Por qué la recomendamos: ' + texto : ''; pq.hidden = !texto; },
            /** Texto plano de los pasos (para anunciar o resumir en el flujo guiado). */
            pasos() { return modelo.pasos.map((p) => ({ tipo: p.tipo, texto: frase(p), foco: p.foco || null })); },
        };
    }

    S.Itinerario = { deOpcion, deTransbordo, porQue, crear, distancia, nombreUtil, ctxDe, CORTA_M };
})();
