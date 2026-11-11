'use strict';
/* Página pública «Viaje compartido» (4.15). Solo lectura: no hay formularios, cuenta, historial ni herramientas del planificador.
   · El token de lectura vive en el fragmento de la URL (#…) y viaja a la API en la cabecera X-Seguimiento (nunca en una URL de la API).
   · Consulta cada 12 s con ETag (si nada cambió, el servidor responde 304) y se detiene al llegar, al vencer el enlace o al revocarlo.
   · Un token inválido, vencido o revocado muestra siempre el mismo mensaje genérico.
   · «Esperando una nueva señal» si la última actualización tiene más de 90 s; al llegar no se muestran coordenadas. */
(() => {
    const $ = (id) => document.getElementById(id);
    const CADA_MS = 12000, VIEJO_S = 90;
    const token = decodeURIComponent((location.hash || '').replace(/^#/, '')).trim();
    let etag = null, ultimo = null, timer = null, relojTimer = null, detenido = false;

    const hace = (s) => { const m = Math.floor(s / 60); return s < 45 ? 'hace unos segundos' : m < 1 ? 'hace menos de un minuto' : m === 1 ? 'hace 1 min' : 'hace ' + m + ' min'; };
    const nombreRuta = (d) => { const e = d && d.ruta && d.ruta.etiquetas && d.ruta.etiquetas[d.leg || 0]; return e ? ' ' + e : ''; };
    const TEXTOS = {
        iniciando: ['Está por comenzar su viaje', 'Todavía no se ha movido.'],
        caminar: (d) => [d.leg > 0 ? 'Camina al transbordo' : 'Camina al punto donde toma el bus', 'Va a pie hacia el paradero.'],
        esperando: ['Está esperando el bus', 'Ya llegó al paradero.'],
        en_bus: (d) => ['Va en el bus' + nombreRuta(d), 'Se acerca a su destino.'],
        caminar_final: ['Camina hacia su destino', 'Ya bajó del bus.'],
        llegaste: ['Llegó a su destino', 'El viaje terminó. Ya no se comparte su ubicación.'],
    };
    function textos(d) { const t = TEXTOS[d.fase] || ['Viaje en curso', '']; return typeof t === 'function' ? t(d) : t; }

    function parar() { detenido = true; clearTimeout(timer); clearInterval(relojTimer); }
    function noDisponible() {
        parar();
        $('estado').textContent = 'Este enlace ya no está disponible';
        $('detalle').textContent = 'Puede haber terminado el viaje, haber vencido o que la persona haya dejado de compartirlo.';
        ['aviso', 'barra', 'mapaFigura'].forEach((i) => { $(i).hidden = true; });
        $('actualizado').textContent = '';
    }

    // ---------- esquema del recorrido (SVG propio: sin teselas ni terceros)
    function dibujar(d) {
        const svg = $('mapa'), tramos = d.ruta && d.ruta.tramos;
        if (!tramos || !tramos.length) { $('mapaFigura').hidden = true; return; }
        const pts = tramos.flat(), lat0 = pts.reduce((a, p) => a + p[1], 0) / pts.length, kx = Math.cos(lat0 * Math.PI / 180);
        const todos = pts.map((p) => [p[0] * kx, p[1]]).concat(d.posicion ? [[d.posicion.lng * kx, d.posicion.lat]] : []);
        const xs = todos.map((p) => p[0]), ys = todos.map((p) => p[1]);
        const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
        const W = 320, H = 240, M = 20, esc = Math.min((W - 2 * M) / Math.max(1e-9, x1 - x0), (H - 2 * M) / Math.max(1e-9, y1 - y0));
        const ox = (W - (x1 - x0) * esc) / 2, oy = (H - (y1 - y0) * esc) / 2;
        const P = (lng, lat) => [(ox + (lng * kx - x0) * esc).toFixed(1), (oy + (y1 - lat) * esc).toFixed(1)];
        const ns = 'http://www.w3.org/2000/svg';
        svg.replaceChildren();
        tramos.forEach((t, i) => {
            const l = document.createElementNS(ns, 'polyline');
            l.setAttribute('class', 'seg-ruta' + (i ? ' b2' : ''));
            l.setAttribute('points', t.map((p) => P(p[0], p[1]).join(',')).join(' '));
            svg.append(l);
        });
        if (d.posicion) {
            const [x, y] = P(d.posicion.lng, d.posicion.lat);
            const h = document.createElementNS(ns, 'circle'), c = document.createElementNS(ns, 'circle');
            h.setAttribute('class', 'seg-yo-halo'); h.setAttribute('cx', x); h.setAttribute('cy', y); h.setAttribute('r', '16');
            c.setAttribute('class', 'seg-yo'); c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', '8');
            svg.append(h, c);
        }
        $('mapaFigura').hidden = false;
    }

    function pintar(d) {
        ultimo = d;
        const [titulo, detalle] = textos(d);
        $('estado').textContent = titulo;
        $('detalle').textContent = detalle + (d.etaMin && d.estado === 'activo' ? ' Llegada aproximada en unos ' + d.etaMin + ' min.' : '');
        const pct = Math.round((d.estado === 'llego' ? 1 : d.progreso || 0) * 100);
        $('barra').hidden = false; $('barra').setAttribute('aria-valuenow', String(pct)); $('barra').firstElementChild.style.width = pct + '%';
        if (d.estado === 'llego') { $('mapaFigura').hidden = true; $('aviso').hidden = true; parar(); }
        else dibujar(d);
        reloj();
    }
    function reloj() {
        if (!ultimo) return;
        const s = Math.max(0, Math.round(Date.now() / 1000 - ultimo.actualizado));
        $('actualizado').textContent = 'Última actualización: ' + hace(s);
        const viejo = ultimo.estado === 'activo' && s > VIEJO_S;
        $('aviso').hidden = !viejo;
        if (viejo) $('aviso').textContent = 'Esperando una nueva señal. Puede que el teléfono no tenga internet; la última ubicación conocida es de ' + hace(s) + '.';
    }

    async function consultar() {
        clearTimeout(timer);
        if (detenido) return;
        try {
            const r = await fetch('/api/compartir', { headers: { 'X-Seguimiento': token, ...(etag ? { 'If-None-Match': etag } : {}) }, cache: 'no-store', referrerPolicy: 'no-referrer' });
            if (r.status === 304) { reloj(); }
            else if (r.status === 404) { return noDisponible(); }
            else if (r.status === 429) { /* se reintenta más tarde */ }
            else if (r.ok) { etag = r.headers.get('ETag'); pintar(await r.json()); }
        } catch { $('aviso').hidden = false; $('aviso').textContent = 'Sin conexión por ahora. Reintentando…'; }
        if (!detenido) timer = setTimeout(consultar, CADA_MS);
    }

    if (!/^[A-Za-z0-9_-]{43}$/.test(token)) noDisponible();
    else { relojTimer = setInterval(reloj, 15000); consultar(); }
})();
