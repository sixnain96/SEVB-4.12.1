'use strict';
/* SEVB · Tarjeta «Mejor opción» (PROPUESTA, fuera del proyecto).
   Muestra, tras buscar, QUÉ BUS tomar de forma grande y clara, y qué otros buses sirven, sin esconderlo bajo la lista.
   No depende del planificador: recibe una lista de «opciones» ya normalizadas (ver abajo) y avisa con callbacks. Así se puede enchufar después con un adaptador pequeño.

   opcion = { id, buses: [{ nombre, color }], minutos, caminaM, busKm?, subeM?, transbordo?: bool, sentidoContrario?: bool,
              caminarMejor?: bool, directoMin?, recomendada?: bool, etiquetas?: [texto] }

   Reglas de producto que aplica:
   · Los nombres de los buses se escriben bien («Terminal», «Galán», «Porfía»), no en mayúsculas ni sin tilde.
   · «También puedes tomar» muestra máximo 3 buses DISTINTOS al principal, los más rápidos, sin repetir el mismo bus y sin «sentido contrario» ni «mejor caminando».
   · Nada se dibuja con innerHTML con datos de fuera: todo el texto entra con textContent. */
(function (raiz) {
    const ACENTOS = { PORFIA: 'Porfía', GALAN: 'Galán', COVISAN: 'Covisán', ALAMOS: 'Álamos', APIAY: 'Apiay', CATAMA: 'Catama', KIRPAS: 'Kirpas', TERMINAL: 'Terminal', HOSPITAL: 'Hospital', JORDAN: 'Jordán', MANANTIAL: 'Manantial' };
    const MINUSCULAS = new Set(['de', 'del', 'la', 'las', 'el', 'los', 'y']);

    /** «PORFIA» → «Porfía»; «la nohora» → «La Nohora»; «876» → «876». */
    function nombreBus(crudo) {
        const t = String(crudo == null ? '' : crudo).trim().replace(/\s+/g, ' ');
        if (!t) return 'sin nombre';
        return t.split(' ').map((p, i) => {
            const k = p.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
            if (ACENTOS[k]) return ACENTOS[k];
            const baja = p.toLowerCase();
            if (i > 0 && MINUSCULAS.has(baja)) return baja;
            return baja.charAt(0).toUpperCase() + baja.slice(1);
        }).join(' ');
    }
    const esNumero = (n) => /^\d+$/.test(String(n).trim());
    const dicho = (n) => (esNumero(n) ? 'la ruta ' + n : 'el bus ' + nombreBus(n));      // «el bus Terminal» / «la ruta 876»
    const fmtM = (m) => (m < 1000 ? Math.round(m) + ' m' : (m / 1000).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km');
    const nombresDe = (o) => o.buses.map((b) => nombreBus(b.nombre));
    const clave = (o) => nombresDe(o).join('+').toLowerCase();

    /** Los buses «de segunda»: los más rápidos que no son el principal, sin repetir y sin los poco útiles. */
    function alternativas(opciones, principal, max) {
        const vistos = new Set([clave(principal)]);
        return opciones
            .filter((o) => o !== principal && !o.sentidoContrario && !o.caminarMejor)
            .slice().sort((a, b) => a.minutos - b.minutos || a.caminaM - b.caminaM)
            .filter((o) => { const k = clave(o); if (vistos.has(k)) return false; vistos.add(k); return true; })
            .slice(0, max == null ? 3 : max);
    }

    // ------------------------------------------------------------------ pequeños dibujos (SVG fijo, sin datos)
    const SVG = {
        estrella: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.4l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.8l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="currentColor"/></svg>',
        bus: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="3.5" width="16" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M4 11h16M8 20.5v-3M16 20.5v-3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="8.5" cy="14.2" r="1" fill="currentColor"/><circle cx="15.5" cy="14.2" r="1" fill="currentColor"/></svg>',
        check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.2 4.2L19 7" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        flecha: '<svg class="mo-flecha" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m0 0l-5-5m5 5l-5 5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        volver: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m0 0l5-5m-5 5l5 5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        caminar: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="13" cy="4.5" r="2" fill="currentColor"/><path d="M9 21l2.2-6-2.7-2.4 1.8-4.6 3.4 1.6 2.3 3M11.2 15l3.3 2.2L15 21" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    };
    const MARCAS = { 'Primer bus más cercano': 'Bus muy cerca', 'Menor caminata total': 'Camina poco', 'Menor caminata hasta el primer bus': 'Bus muy cerca', 'Menor tiempo estimado': 'Llegas antes' };

    function el(tag, clase, texto) { const e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; }
    function conSvg(e, svg) { e.insertAdjacentHTML('afterbegin', svg); return e; }      // SVG constante del propio archivo: ningún dato entra por aquí
    function punto(color) { const p = el('span', 'mo-punto'); p.style.setProperty('--c', /^#[0-9a-f]{3,8}$/i.test(color || '') ? color : '#176650'); p.setAttribute('aria-hidden', 'true'); return p; }

    function montar(contenedor, config) {
        const estado = { opciones: [], seleccion: null };
        const cfg = Object.assign({ alElegir() {}, alVerTodas() {}, maxAlternativas: 3 }, config);
        const raizMo = el('section', 'mo'); raizMo.setAttribute('aria-label', 'Mejor opción para tu viaje');
        const aviso = el('div', 'mo-sr'); aviso.setAttribute('role', 'status'); aviso.setAttribute('aria-live', 'polite');
        contenedor.replaceChildren(raizMo);

        const mejor = () => estado.opciones.find((o) => o.recomendada) || estado.opciones[0];
        const actual = () => estado.opciones.find((o) => o.id === estado.seleccion) || mejor();

        function tarjeta(o, esMejor) {
            const card = el('article', 'mo-card');
            const fila = el('div', 'mo-fila');
            const et = conSvg(el('span', 'mo-etiqueta', esMejor ? 'Mejor opción' : 'Otra opción'), esMejor ? SVG.estrella : SVG.bus);
            const hora = el('div', 'mo-hora'); hora.title = 'Tiempo estimado sin contar la espera del bus';
            const t = el('div', 'mo-tiempo'); t.append(el('b', null, String(o.minutos)), el('small', null, 'min'));
            hora.append(t, el('span', 'mo-sinespera', 'sin la espera'));
            fila.append(et, hora);

            const titulo = el('h3');
            const cab = el('div', 'mo-titulo'); const pts = el('span', 'mo-puntos');
            o.buses.forEach((b, i) => { if (i) pts.insertAdjacentHTML('beforeend', SVG.flecha); pts.append(punto(b.color)); });
            cab.append(pts, titulo);
            // «Toma el bus <em>Terminal</em>» / «Toma el bus <em>Galán</em> y luego el bus <em>Porfía</em>»: solo el nombre va resaltado
            titulo.append('Toma ');
            o.buses.forEach((b, i) => {
                if (i) titulo.append(' y luego ');
                const partes = dicho(b.nombre).split(' '), nombre = partes.slice(2).join(' ');
                titulo.append(partes.slice(0, 2).join(' ') + ' ', el('em', null, nombre));
            });

            const datos = el('p', 'mo-datos'); const trozos = [];
            const add = (pre, fuerte, post) => { const s = document.createElement('span'); s.append(pre || '', el('strong', null, fuerte), post || ''); trozos.push(s); };
            if (o.subeM != null) add('Subes a ', fmtM(o.subeM), '');
            add(trozos.length ? 'caminas ' : 'Caminas ', fmtM(o.caminaM), '');
            trozos.forEach((s, i) => { if (i) datos.append(' · '); datos.append(s); });
            datos.title = (o.subeM != null ? 'Subes al bus a ' + fmtM(o.subeM) + ' de ti. ' : '') + 'Caminas ' + fmtM(o.caminaM) + ' en total' + (o.busKm ? ' y vas ' + o.busKm.toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km en bus.' : '.');

            const marcas = el('ul', 'mo-marcas');
            const m1 = conSvg(el('li', null, o.transbordo ? '1 transbordo' : 'Sin transbordo'), SVG.check); marcas.append(m1);
            (o.etiquetas || []).filter((x) => x !== 'Sin transbordo').map((x) => MARCAS[x] || x).filter((x, i, a) => a.indexOf(x) === i).slice(0, 1).forEach((x) => marcas.append(conSvg(el('li', null, x), SVG.check)));

            card.append(fila, cab, datos, marcas);
            if (o.caminarMejor && o.directoMin) {
                const av = conSvg(el('p', 'mo-aviso', 'Ir caminando directo tarda ≈ ' + o.directoMin + ' min: casi lo mismo, o menos, que este bus.'), SVG.caminar);
                card.append(av);
            }
            return card;
        }

        function pintar(conAnimacion) {
            const principal = mejor(); if (!principal) { raizMo.replaceChildren(el('p', 'mo-vacio', 'Busca rutas para ver la mejor opción.')); return; }
            const o = actual(), esMejor = o === principal;
            raizMo.className = 'mo' + (esMejor ? '' : ' mo--otra') + (conAnimacion === 'entra' ? ' mo--entra' : conAnimacion === 'cambia' ? ' mo--cambia' : '');
            const card = tarjeta(o, esMejor);

            if (!esMejor) {
                const v = conSvg(el('button', 'mo-volver', 'Volver a la mejor opción'), SVG.volver); v.type = 'button';
                v.addEventListener('click', () => elegir(principal.id)); card.append(v);
            }
            const otros = estado.opciones.filter((x) => x !== principal);
            const rapidas = otros.filter((x) => !x.sentidoContrario && !x.caminarMejor && clave(x) !== clave(principal));
            const masRapida = rapidas.length ? Math.min.apply(null, rapidas.map((x) => x.minutos)) : null;
            const contexto = el('p', 'mo-contexto');
            if (esMejor && masRapida != null && masRapida - principal.minutos >= 8) { contexto.textContent = 'Las otras opciones tardan al menos ' + (masRapida - principal.minutos) + ' min más.'; card.append(contexto); }

            const partes = [card];
            const alt = alternativas(estado.opciones, principal, cfg.maxAlternativas);
            if (alt.length) {
                const caja = el('div', 'mo-otras'); caja.append(el('p', 'mo-otras-titulo', 'También puedes tomar'));
                const chips = el('div', 'mo-chips'); chips.setAttribute('role', 'group'); chips.setAttribute('aria-label', 'Otros buses que sirven');
                const lista = [principal].concat(alt).filter((x) => x !== o);       // el que se está mirando no se repite como botón
                lista.forEach((x, i) => {
                    const b = el('button', 'mo-chip'); b.type = 'button'; b.style.setProperty('--i', String(i));
                    b.setAttribute('aria-label', (x === principal ? 'Volver a la mejor opción: ' : 'Ver la opción ') + nombresDe(x).join(' y luego ') + ', ' + x.minutos + ' minutos');
                    x.buses.forEach((bus) => b.append(punto(bus.color)));
                    b.append(nombresDe(x).join(' → ')); b.append(el('small', null, x.minutos + ' min'));
                    b.addEventListener('click', () => elegir(x.id));
                    chips.append(b);
                });
                const total = otros.length;
                if (total > alt.length) {      // la lista completa, al final de la misma fila (no ocupa otra línea)
                    const t = el('button', 'mo-chip mo-chip--todas', 'Ver las ' + (total + 1)); t.type = 'button'; t.style.setProperty('--i', String(lista.length));
                    t.setAttribute('aria-label', 'Ver las ' + (total + 1) + ' opciones');
                    t.insertAdjacentHTML('beforeend', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>');
                    t.addEventListener('click', () => cfg.alVerTodas()); chips.append(t);
                }
                caja.append(chips);
                partes.push(caja);
            }
            partes.push(aviso);
            raizMo.replaceChildren.apply(raizMo, partes);
            aviso.textContent = (esMejor ? 'Mejor opción: ' : 'Opción elegida: ') + nombresDe(o).join(' y luego ') + ', ' + o.minutos + ' minutos.';
        }

        function elegir(id) {
            const o = estado.opciones.find((x) => x.id === id); if (!o) return;
            estado.seleccion = id; pintar('cambia'); cfg.alElegir(o);
        }
        function actualizar(opciones) { estado.opciones = (opciones || []).slice(); estado.seleccion = null; pintar('entra'); }
        /** Muestra una opción SIN avisar con alElegir (la persona ya la eligió en otro lado, p. ej. tocando una tarjeta de la lista). */
        function mostrar(id) { if (!estado.opciones.some((x) => x.id === id) || (estado.seleccion || mejor().id) === id) return; estado.seleccion = id; pintar('cambia'); }
        actualizar(cfg.opciones);
        return { elegir, mostrar, actualizar, actual, destruir() { contenedor.replaceChildren(); } };
    }

    raiz.MejorOpcion = { montar, nombreBus, alternativas, fmtM };
})(typeof window !== 'undefined' ? window : globalThis);

/* ---------------------------------------------------------------------------------------------------------------------------------------------------
   ENGANCHE CON SEVB (solo si la página tiene #mejorOpcion). No toca la lógica del planificador: lee los datos que planner.js deja en cada tarjeta de resultado
   (card._mejor, ver datosMejor en planner.js) y, al tocar un bus, abre esa tarjeta igual que si la persona la tocara en la lista.
   Solo se muestra si el servidor marcó una opción como RECOMENDADA; si no (p. ej. solo hay sentido contrario) todo queda como antes. */
(function () {
    const cont = typeof document !== 'undefined' && document.getElementById('mejorOpcion');
    if (!cont || !window.MejorOpcion) return;
    let ctl = null, firma = '';
    const tarjetas = () => [...document.querySelectorAll('#tripResults .trip-option')].filter((c) => c._mejor);
    const tarjetaDe = (id) => tarjetas().find((c) => c._mejor.id === id);
    const ocultar = () => { cont.hidden = true; cont.classList.remove('mo-activa'); if (ctl) ctl.destruir(); ctl = null; firma = ''; avisarBarra(false); };
    function avisarBarra(on) { const b = document.getElementById('startTripBar'); if (b) b.classList.toggle('con-mejor', !!on); }
    function sincronizar() {
        const S = window.Spevb, sel = S && S.Planner && S.Planner.seleccion;
        if (!sel || !sel.viaje || (S.Viaje && S.Viaje.activo && S.Viaje.activo())) { ocultar(); return; }
        const cartas = tarjetas();
        const opciones = cartas.map((c) => Object.assign({}, c._mejor, { recomendada: c.dataset.recomendada === 'true' }));
        if (!opciones.some((o) => o.recomendada)) { ocultar(); return; }          // sin recomendación del servidor no se afirma «la mejor»
        const f = opciones.map((o) => o.id).join('|');
        const elegida = document.querySelector('#tripResults .trip-option.selected');
        if (!ctl || f !== firma) {
            firma = f; cont.hidden = false; cont.classList.add('mo-activa'); avisarBarra(true);
            ctl = window.MejorOpcion.montar(cont, {
                opciones,
                alElegir: (o) => { const c = tarjetaDe(o.id); if (c && !c.open) c.open = true; },      // abre la tarjeta: el planificador la dibuja en el mapa como siempre
                alVerTodas: () => window.dispatchEvent(new CustomEvent('spevb-ver-opciones')),
            });
        }
        if (elegida && elegida._mejor) ctl.mostrar(elegida._mejor.id);
    }
    window.addEventListener('spevb-seleccion', sincronizar);
    window.addEventListener('spevb-viaje-modo', sincronizar);
})();
