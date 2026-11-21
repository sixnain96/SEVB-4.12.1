'use strict';
/* «Mis lugares» (Fase C): Casa, Trabajo y lugares con nombre, guardados en la CUENTA (no en el dispositivo) y usables como destino con un toque.
   Sustituye a atajos.js. Reglas:
   · Guardar exige una sesión comprobada con el servidor: si falta, se abre «Continuar con Google» y, tras entrar, se retoma lo que la persona quería; cancelar vuelve al menú.
   · Se marca el punto en un MODO DE MAPA PROPIO (pin fijo en el centro del mapa), con un punto temporal de este propósito: nunca toca A ni B ni sus eventos (spevb-point-selected no guarda nada).
     Si había un selector de A/B activo, cede mientras tanto y se restaura al terminar si sigue siendo pertinente; el panel que se ocultó vuelve; resultados, recomendación, mapa del viaje y fase no se tocan.
   · El pin confirmado son las coordenadas del centro del mapa EN EL MOMENTO de pulsar «Guardar este punto»: ninguna respuesta tardía (dirección, GPS) lo mueve.
   · Todo cambio lo confirma el servidor (Spevb.LugaresCuenta.mutar: lee lo último, aplica, escribe condicionado a lo leído). Sin conexión no se guarda nada y el mensaje lo dice.
   · Ids estables (editar y borrar no comparan texto ni coordenadas); Casa y Trabajo son únicos por cuenta; hasta 30 lugares en total; nombres de hasta 40 caracteres, siempre como texto. */
(() => {
    const S = window.Spevb;
    const caja = document.getElementById('atajos');
    if (!S || !caja) return;
    const $ = (id) => document.getElementById(id);
    const MAX = 30, NOMBRE_MAX = 40, DUP_M = 30, PIN_PASO = 60;
    const TIPOS = {
        casa: { clave: 'Casa', art: 'tu casa', guardar: 'Guardar mi casa', ir: 'Casa', hecho: 'Guardaste tu casa', titulo: 'Marca tu casa en el mapa', icono: 'casa' },
        trabajo: { clave: 'Trabajo', art: 'tu trabajo', guardar: 'Guardar mi trabajo', ir: 'Trabajo', hecho: 'Guardaste tu trabajo', titulo: 'Marca tu trabajo en el mapa', icono: 'maletin' },
    };
    const P = () => S.Planner;
    const norm = (t) => String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
    const limpiarNombre = (t) => String(t || '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
    const nuevoId = () => 'l' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    const lugares = () => S.LugaresCuenta.vivos();
    /** Casa y Trabajo pueden existir como favoritos antiguos por nombre (sin tipo): se interpretan así, sin migrar nada a la fuerza. */
    const tipoDe = (f) => (f.tipo === 'casa' || f.tipo === 'trabajo' || f.tipo === 'otro' ? f.tipo : norm(f.nombre) === 'casa' ? 'casa' : norm(f.nombre) === 'trabajo' ? 'trabajo' : 'otro');
    const reservado = (lista, tipo) => lista.find((f) => tipoDe(f) === tipo);
    const esReservado = (lista, f) => ['casa', 'trabajo'].some((t) => reservado(lista, t) === f);
    const personalizados = (lista) => lista.filter((f) => !esReservado(lista, f));
    const distM = (a, b) => (S.ViajeNucleo ? S.ViajeNucleo.dist(a, b) : Math.hypot((a.lat - b.lat) * 111000, (a.lng - b.lng) * 111000));
    const dentro = (lat, lng) => { const [[s, w], [n, e]] = S.cityBounds || [[-90, -180], [90, 180]]; return lat >= s && lat <= n && lng >= w && lng <= e; };
    const cerrarMenu = () => { if (S.Superficies) S.Superficies.menu.cerrar(); else { const c = $('closeMenu'); if (c) c.click(); } };
    const abrirMenu = () => { if (S.Superficies) S.Superficies.menu.abrir(); };
    const anunciar = (t) => { const r = $('lugarVoz'); if (r) { r.textContent = ''; setTimeout(() => { r.textContent = t; }, 30); } };
    const aviso = (t, tipo = 'info', ms = 5000) => S.toast(t, { tipo, ms, clave: 'lugar' });

    // ------------------------------------------------------------------ mensajes de error legibles
    function textoError(e) {
        if (!e) return 'No se pudo guardar.';
        if (e.offline) return 'Sin conexión: tu lugar NO se guardó. Esta versión necesita internet para confirmarlo; vuelve a intentarlo cuando tengas señal.';
        if (e.sinSesion) return e.message;
        if (e.sesionCambio) return 'La sesión cambió mientras se guardaba. No se guardó nada.';
        if (e.status === 401) return 'Tu sesión venció. Continúa con Google y vuelve a intentarlo: no se guardó nada.';
        if (e.status === 429) return 'Demasiados cambios seguidos. Espera unos segundos y vuelve a intentarlo.';
        return e.message || 'No se pudo guardar.';
    }

    // ------------------------------------------------------------------ sesión requerida
    /** true si hay una sesión comprobada. Si falta, abre «Continuar con Google» y espera el resultado; false = la persona decidió seguir sin cuenta (el menú vuelve). */
    async function conSesion(motivo) {
        if (S.Cuenta.sesionValida) return true;
        if (S.Cuenta.usuario) { aviso('Sin conexión no puedo confirmar tu sesión. Guardar un lugar necesita internet; inténtalo de nuevo con señal.', 'info', 6500); return false; }
        const u = await S.Cuenta.requiere(motivo);
        if (!u || !S.Cuenta.sesionValida) { abrirMenu(); return false; }      // cancelar vuelve al menú
        return true;
    }

    // ------------------------------------------------------------------ diálogo genérico (nombre y confirmar borrado)
    function dialogo({ titulo, texto, campo = null, aceptar, cancelar = 'Cancelar', peligro = false, validar = null }) {
        return new Promise((ok) => {
            const fondo = document.createElement('div');
            fondo.className = 'modal-backdrop'; fondo.hidden = true;
            fondo.innerHTML = '<div class="modal-card lugar-dialogo" role="alertdialog" aria-modal="true" aria-labelledby="lugDlgT" aria-describedby="lugDlgX"><h2 id="lugDlgT"></h2><p id="lugDlgX" class="muted"></p>'
                + (campo ? '<label for="lugDlgC"></label><input id="lugDlgC" maxlength="' + NOMBRE_MAX + '" autocomplete="off" enterkeyhint="done" />' : '')
                + '<p class="error-msg" id="lugDlgE" role="alert"></p><div class="modal-actions"><button type="button" class="secondary" id="lugDlgN"></button><button type="button" id="lugDlgS"></button></div></div>';
            document.body.appendChild(fondo);
            const q = (s) => fondo.querySelector(s);
            q('#lugDlgT').textContent = titulo; q('#lugDlgX').textContent = texto || ''; q('#lugDlgX').hidden = !texto;
            q('#lugDlgN').textContent = cancelar; q('#lugDlgS').textContent = aceptar; q('#lugDlgS').className = peligro ? 'secondary danger' : 'primary-plan-button';
            if (campo) { q('label').textContent = campo.etiqueta; q('#lugDlgC').value = campo.valor || ''; q('#lugDlgC').placeholder = campo.ejemplo || ''; }
            let fin = false;
            const cerrar = (valor) => { if (fin) return; fin = true; S.Modal.cerrar(fondo); setTimeout(() => fondo.remove(), 50); ok(valor); };
            const enviar = () => {
                if (!campo) return cerrar(true);
                const v = limpiarNombre(q('#lugDlgC').value), err = validar ? validar(v) : '';
                if (err) { q('#lugDlgE').textContent = err; q('#lugDlgC').focus(); return; }
                cerrar(v);
            };
            q('#lugDlgN').onclick = () => cerrar(null); q('#lugDlgS').onclick = enviar;
            if (campo) q('#lugDlgC').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); enviar(); } });
            S.Modal.abrir(fondo, { fondo: true, cerrar: () => cerrar(null), foco: campo ? '#lugDlgC' : (peligro ? '#lugDlgN' : '#lugDlgS'), seleccionar: !!campo });
        });
    }
    function validarNombre(nombre, lista, excepto) {
        if (nombre.length < 2) return 'Escribe un nombre de al menos 2 letras. Por ejemplo: Universidad o Casa de mamá.';
        if (nombre.length > NOMBRE_MAX) return 'El nombre puede tener hasta ' + NOMBRE_MAX + ' caracteres.';
        if (['casa', 'trabajo'].includes(norm(nombre))) return 'Casa y Trabajo se guardan con sus propios botones.';
        if (lista.some((f) => f.id !== excepto && norm(f.nombre) === norm(nombre))) return 'Ya tienes un lugar llamado «' + nombre + '». Elige otro nombre.';
        return '';
    }

    // ------------------------------------------------------------------ acciones sobre lugares guardados
    /** Usa el lugar como punto de salida (A) o de destino (B). El destino sigue siendo el valor de siempre. */
    function usar(f, modo = 'destination') {
        if (!P()) return;
        P().poner(modo === 'origin' ? 'origin' : 'destination', { id: null, lat: f.lat, lng: f.lng, nombre: f.nombre, direccion: null, fuente: 'Favorito', confirmado: true });      // el punto de entrada de siempre (también para el modo guiado)
        cerrarMenu();
    }
    // Al tocar un lugar guardado se pregunta, ahí mismo y sin ventanas, si SALES de ahí (A) o VAS para allá (B): casa → trabajo, trabajo → casa, universidad → casa…
    // Si ya hay un destino y falta la salida, se sugiere «Salgo de aquí» (y al revés).
    function cerrarUso(menos) {
        document.querySelectorAll('.lugar-uso').forEach((e) => { if (e !== menos) { const b = e.previousElementSibling; e.remove(); } });
        document.querySelectorAll('[data-uso-abierto]').forEach((b) => { if (!menos || !menos.contains(b)) { b.removeAttribute('data-uso-abierto'); b.setAttribute('aria-expanded', 'false'); } });
    }
    function elegirUso(f, fila, boton) {
        const ya = fila.querySelector(':scope > .lugar-uso');
        cerrarUso();
        if (ya) return;
        const pts = (P() && P().puntos && P().puntos()) || {};
        const sugerido = pts.destino && !pts.origen ? 'origin' : 'destination';
        const caja2 = document.createElement('div'); caja2.className = 'lugar-uso'; caja2.setAttribute('role', 'group'); caja2.setAttribute('aria-label', 'Usar ' + f.nombre + ' como salida o como destino');
        const mk = (modo, letra, titulo, sub) => {
            const b = document.createElement('button'); b.type = 'button'; b.className = 'lugar-uso-b ' + (modo === 'origin' ? 'sale' : 'va') + (modo === sugerido ? ' sugerido' : ''); b.dataset.uso = modo;
            const l = document.createElement('span'); l.className = 'lugar-uso-letra'; l.setAttribute('aria-hidden', 'true'); l.textContent = letra;
            const t = document.createElement('span'); t.className = 'lugar-uso-txt';
            const st = document.createElement('strong'); st.textContent = titulo; const sm = document.createElement('small'); sm.textContent = sub;
            t.append(st, sm); b.append(l, t);
            b.setAttribute('aria-label', titulo + ': ' + sub + ' ' + f.nombre);
            b.onclick = () => usar(f, modo);
            return b;
        };
        caja2.append(mk('origin', 'A', 'Salgo de aquí', 'Punto de salida'), mk('destination', 'B', 'Voy para aquí', 'Punto de llegada'));
        fila.append(caja2);
        boton.setAttribute('data-uso-abierto', ''); boton.setAttribute('aria-expanded', 'true');
        const foco = caja2.querySelector('.sugerido'); if (foco) { try { foco.focus({ preventScroll: true }); } catch { /* nada */ } }
        try { caja2.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch { /* nada */ }
    }
    async function renombrar(f) {
        const lista = lugares();
        const v = await dialogo({ titulo: 'Cambiar nombre', texto: 'Escribe el nombre nuevo de este lugar.', campo: { etiqueta: 'Nombre del lugar', valor: f.nombre, ejemplo: 'Universidad' }, aceptar: 'Guardar nombre', validar: (n) => validarNombre(n, lista, f.id) });
        if (v === null || v === f.nombre) return;
        try { await S.LugaresCuenta.mutar((vivos) => { const x = vivos.find((y) => y.id === f.id); if (!x) throw new Error('Ese lugar ya no existe (se borró en otro dispositivo).'); const err = validarNombre(v, vivos, f.id); if (err) throw new Error(err); x.nombre = v; if (x.tipo !== 'otro') x.tipo = 'otro'; return vivos; }); aviso('Cambiaste el nombre a «' + v + '».', 'success', 3500); }
        catch (e) { aviso(textoError(e), 'error', 8000); }
    }
    async function eliminar(f) {
        const ok = await dialogo({ titulo: '¿Eliminar «' + f.nombre + '»?', texto: 'Se borra de tu cuenta y de tus otros dispositivos. No se puede deshacer.', aceptar: 'Sí, eliminar', cancelar: 'No, conservar', peligro: true });
        if (!ok) return;
        try {
            if (S.LugaresCuenta.disponible()) await S.LugaresCuenta.mutar((vivos) => vivos.filter((x) => x.id !== f.id));
            else if (!S.Cuenta.usuario) S.Datos.escribir('lugares', lugares().filter((x) => x.id !== f.id));      // invitado: un favorito antiguo de ESTE dispositivo
            else throw Object.assign(new Error('Sin conexión no puedo confirmar el borrado. Inténtalo con señal.'), { sinSesion: true });
            aviso('Eliminaste «' + f.nombre + '».', 'success', 3500);
        } catch (e) { aviso(textoError(e), 'error', 8000); }
    }
    async function mover(f) {
        if (!(await conSesion('Para cambiar un lugar de tu cuenta necesitas continuar con Google.'))) return;
        abrirModo({ tipo: tipoDe(f) === 'otro' || !esReservado(lugares(), f) ? 'otro' : tipoDe(f), editar: f });
    }

    // ------------------------------------------------------------------ pintar el bloque
    const abiertas = new Set();
    function filaAcciones(f, lista) {
        const caja2 = document.createElement('div'); caja2.className = 'lugar-acciones'; caja2.id = 'lugAcc-' + f.id;
        const mk = (txt, fn) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'secondary lugar-accion'; b.textContent = txt; b.onclick = fn; return b; };
        const cuenta = !!S.Cuenta.usuario;
        if (cuenta) caja2.append(mk('Cambiar ubicación', () => mover(f)));
        if (cuenta && !esReservado(lista, f)) caja2.append(mk('Cambiar nombre', () => renombrar(f)));
        caja2.append(mk('Eliminar', () => eliminar(f)));
        return caja2;
    }
    function boton(f, lista, etiqueta) {
        const fila = document.createElement('li'); fila.className = 'lugar-fila'; fila.dataset.id = f.id;
        const cab = document.createElement('div'); cab.className = 'lugar-cab';
        const usarB = document.createElement('button'); usarB.type = 'button'; usarB.className = 'lugar-usar';
        usarB.append(S.Iconos.el('pin', { tam: 20 }));
        const t = document.createElement('span'); t.className = 'lugar-nombre'; t.textContent = etiqueta || f.nombre; usarB.append(t);       // texto, nunca HTML
        const ir = document.createElement('span'); ir.className = 'lugar-ir'; ir.setAttribute('aria-hidden', 'true'); ir.textContent = 'Usar'; usarB.append(ir);
        usarB.setAttribute('aria-label', 'Usar ' + f.nombre + ' como salida o destino'); usarB.setAttribute('aria-expanded', 'false'); usarB.onclick = () => elegirUso(f, fila, usarB);
        const mas = document.createElement('button'); mas.type = 'button'; mas.className = 'lugar-mas'; mas.textContent = '⋯';
        mas.setAttribute('aria-label', 'Más acciones de ' + f.nombre); mas.setAttribute('aria-expanded', String(abiertas.has(f.id))); mas.setAttribute('aria-controls', 'lugAcc-' + f.id);
        mas.onclick = () => { if (abiertas.has(f.id)) abiertas.delete(f.id); else abiertas.add(f.id); pintar(); const nuevo = document.querySelector('[data-id="' + f.id + '"] .lugar-mas'); if (nuevo) nuevo.focus({ preventScroll: true }); };
        cab.append(usarB, mas); fila.append(cab);
        if (abiertas.has(f.id)) fila.append(filaAcciones(f, lista));
        return fila;
    }
    function pintar() {
        const lista = lugares(), conCuenta = !!S.Cuenta.usuario;
        // Casa y Trabajo (siempre visibles)
        caja.querySelectorAll('.atajo-fila').forEach((fila) => {
            const tipo = fila.dataset.tipo, d = TIPOS[tipo], f = reservado(lista, tipo), b = fila.querySelector('.atajo'), mas = fila.querySelector('.atajo-mas'), acc = fila.querySelector('.atajo-acciones');
            const ico = b.querySelector('.atajo-ico'); if (ico && !ico.firstChild) ico.append(S.Iconos.el(d.icono, { tam: 26 }));
            b.classList.toggle('guardado', !!f);
            b.querySelector('.atajo-txt').textContent = f ? d.ir : d.guardar;
            b.setAttribute('aria-label', f ? 'Usar ' + d.art + ' como salida o destino' : d.guardar);
            if (f) b.setAttribute('aria-expanded', 'false'); else b.removeAttribute('aria-expanded');
            mas.hidden = !f; mas.setAttribute('aria-label', 'Más acciones de ' + d.clave); mas.setAttribute('aria-expanded', String(!!f && abiertas.has(f.id)));
            acc.replaceChildren(); acc.hidden = !(f && abiertas.has(f.id));
            if (f && abiertas.has(f.id)) { const ac = filaAcciones(f, lista); ac.id = 'lugAcc-' + f.id; acc.append(...ac.children); mas.setAttribute('aria-controls', ac.id); acc.id = ac.id; }
        });
        // lugares con nombre (los primeros 3; el resto en «Administrar»)
        const otros = personalizados(lista), ul = $('lugaresLista');
        if (ul) { ul.replaceChildren(...otros.slice(0, 3).map((f) => boton(f, lista))); ul.hidden = !otros.length; }
        const todos = $('favList');
        if (todos) {
            todos.replaceChildren();
            if (!lista.length) { const p = document.createElement('p'); p.className = 'fav-empty'; p.textContent = conCuenta ? 'Aún no guardas lugares. Toca «Agregar lugar» o guarda tu casa y tu trabajo.' : 'Aún no guardas lugares.'; todos.append(p); }
            else { const u = document.createElement('ul'); u.className = 'lugares-lista'; lista.forEach((f) => u.append(boton(f, lista, esReservado(lista, f) ? TIPOS[tipoDe(f)].clave + ' · ' + f.nombre : null))); todos.append(u); }
        }
        const n = $('favCount'); if (n) n.textContent = lista.length ? String(lista.length) : '';
        const agregar = $('lugarAgregar'); if (agregar) agregar.disabled = false;
        const hint = $('lugaresHint'); if (hint) hint.hidden = conCuenta;
    }
    caja.addEventListener('click', (e) => {
        const b = e.target.closest('.atajo'), mas = e.target.closest('.atajo-mas');
        const lista = lugares();
        if (mas) { const f = reservado(lista, mas.closest('.atajo-fila').dataset.tipo); if (f) { if (abiertas.has(f.id)) abiertas.delete(f.id); else abiertas.add(f.id); pintar(); const m = caja.querySelector('.atajo-fila[data-tipo="' + tipoDe(f) + '"] .atajo-mas'); if (m) m.focus({ preventScroll: true }); } return; }
        if (!b) return;
        const tipo = b.closest('.atajo-fila').dataset.tipo, f = reservado(lista, tipo);
        if (f) { elegirUso(f, caja, b); return; }      // la elección ocupa todo el ancho de «Casa y Trabajo» (cuelga de #atajos, no de la mitad de una fila)
        guardarPrimero(tipo);
    });
    async function guardarPrimero(tipo) {
        if (!(await conSesion('Para guardar ' + TIPOS[tipo].art + ' en tu cuenta necesitas continuar con Google.'))) return;
        abrirModo({ tipo });
    }
    async function agregar() {
        if (lugares().length >= MAX) { aviso('Ya tienes ' + MAX + ' lugares guardados. Elimina alguno para agregar otro.', 'info', 6000); return; }
        if (!(await conSesion('Para guardar un lugar en tu cuenta necesitas continuar con Google.'))) return;
        abrirModo({ tipo: 'otro' });
    }

    // ------------------------------------------------------------------ modo de mapa «Marca el lugar»
    const modo = { pt: null, activo: false, tipo: null, editar: null, turno: 0, guardando: false, panel: false, seleccion: null, cerca: null, ult: null, abridor: null, reverso: null };
    let barra = null, pin = null, ro = null;
    const mapa = () => (S.maps && S.maps.map) || (window.SpevbExplorer && window.SpevbExplorer.map);
    const estadoMsg = (t) => { const e = $('lugarEstado'); if (e) e.textContent = t; };
    function construir() {
        if (barra) return;
        barra = document.createElement('section');
        barra.id = 'lugarModo'; barra.className = 'lugar-modo'; barra.hidden = true; barra.setAttribute('role', 'region'); barra.setAttribute('aria-labelledby', 'lugarTitulo');
        barra.innerHTML = '<h2 id="lugarTitulo"></h2><p id="lugarAyuda" class="lugar-ayuda"></p>'
            + '<div id="lugarNombreFila" hidden><label for="lugarNombre">Nombre del lugar</label><input id="lugarNombre" maxlength="' + NOMBRE_MAX + '" autocomplete="off" enterkeyhint="done" placeholder="Por ejemplo: Universidad o Casa de mamá" /></div>'
            + '<p id="lugarCerca" class="lugar-cerca" aria-live="polite"></p><p id="lugarEstado" class="lugar-estado" role="status" aria-live="polite"></p>'
            + '<div class="lugar-botones"><button type="button" id="lugarGps" class="secondary" hidden>Usar mi ubicación</button><button type="button" id="lugarGuardar" class="primary-plan-button">Guardar este punto</button><button type="button" id="lugarCancelar" class="secondary">Cancelar</button></div>';
        document.body.appendChild(barra);
        const voz = document.createElement('p'); voz.id = 'lugarVoz'; voz.className = 'sr-only'; voz.setAttribute('role', 'status'); voz.setAttribute('aria-live', 'polite'); document.body.appendChild(voz);
        $('lugarGuardar').onclick = confirmar; $('lugarCancelar').onclick = () => cancelar(); $('lugarGps').onclick = miUbicacion;
        $('lugarNombre').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); confirmar(); } });
        $('lugarNombre').addEventListener('input', () => { modo.cerca = null; $('lugarGuardar').textContent = 'Guardar este punto'; estadoMsg(''); });
    }
    function ponerPin() {
        const m = mapa(); if (!m) return;
        if (!pin) {
            pin = document.createElement('div'); pin.id = 'lugarPin'; pin.className = 'lugar-pin'; pin.tabIndex = 0; pin.setAttribute('role', 'application');
            pin.setAttribute('aria-label', 'Pin en el centro del mapa. Flechas para mover el mapa, más y menos para acercar o alejar, Enter para guardar este punto.');
            pin.innerHTML = '<svg viewBox="0 0 24 32" width="40" height="53" aria-hidden="true" focusable="false"><path d="M12 31S2 19.5 2 11.5a10 10 0 0 1 20 0C22 19.5 12 31 12 31z" fill="#176650" stroke="#fff" stroke-width="2"/><circle cx="12" cy="11.5" r="4" fill="#fff"/></svg>';
            pin.addEventListener('keydown', alTeclado);
        }
        if (pin.parentElement !== m.el) m.el.append(pin);
        modo.pt = puntoLibre(m); pin.style.left = modo.pt.x + 'px'; pin.style.top = modo.pt.y + 'px';
    }
    /** El pin va en el centro del ÁREA LIBRE del mapa (la barra de este modo tapa una parte), y se fija al abrir o al cambiar el tamaño: no se mueve cuando la barra crece con un mensaje,
     *  así lo que se ve bajo la punta del pin es exactamente lo que se guarda. */
    function puntoLibre(m) {
        const t = m.getSize(), c = m.el.getBoundingClientRect(), r = barra && !barra.hidden ? barra.getBoundingClientRect() : null;
        if (!r) return { x: t.x / 2, y: t.y / 2 };
        if (window.matchMedia('(max-height: 480px) and (orientation: landscape)').matches) return { x: Math.max(40, (r.left - c.left) / 2), y: t.y / 2 + 26 };
        if (barra.dataset.viaje === '1') { const y0 = Math.max(0, r.bottom - c.top); return { x: t.x / 2, y: Math.min(t.y - 20, y0 + Math.max(60, (t.y - y0) / 2 + 26)) }; }
        const libre = Math.max(0, r.top - c.top); return { x: t.x / 2, y: Math.max(60, libre / 2 + 26) };
    }
    function alTeclado(e) {
        const m = mapa(); if (!m || !modo.activo) return;
        const paso = (e.shiftKey ? 3 : 1) * PIN_PASO, d = { ArrowLeft: [-paso, 0], ArrowRight: [paso, 0], ArrowUp: [0, -paso], ArrowDown: [0, paso] }[e.key];
        if (e.key === 'Enter') { e.preventDefault(); confirmar(); return; }
        if (e.key === '+' || e.key === '=') { e.preventDefault(); m.setView(m.getCenter(), Math.min(19, m.getZoom() + 1), { animate: false }); return; }
        if (e.key === '-' || e.key === '_') { e.preventDefault(); m.setView(m.getCenter(), Math.max(11, m.getZoom() - 1), { animate: false }); return; }
        if (!d) return;
        e.preventDefault();
        const [lat, lng] = m.getCenter(), z = m.getZoom(), g = 360 / (256 * 2 ** z);
        m.setView([lat - d[1] * g * Math.cos(lat * Math.PI / 180), lng + d[0] * g], z, { animate: false });
        pedirCerca();
    }
    function centro() { const m = mapa(); const [lat, lng] = (modo.pt && m.toLatLng(modo.pt)) || m.getCenter(); return { lat: Math.round(lat * 1e6) / 1e6, lng: Math.round(lng * 1e6) / 1e6 }; }
    /** Pista opcional «cerca de …»: solo informa. Nunca mueve el pin ni se guarda; una respuesta que llega con el mapa ya movido se descarta. */
    function pedirCerca() {
        clearTimeout(modo.reverso); const turno = modo.turno, c0 = centro();
        modo.reverso = setTimeout(async () => {
            if (!modo.activo || modo.turno !== turno) return;
            try {
                const r = await S.api('/api/lugares/reverso?lat=' + c0.lat + '&lng=' + c0.lng, { timeout: 6000 });
                const c1 = centro();
                if (!modo.activo || modo.turno !== turno || distM(c0, c1) > 5) return;      // el mapa se movió o el modo terminó: respuesta vieja
                const nombre = r && r.nombre && !/^Punto en mapa|^Sitio de prueba/.test(r.nombre) ? String(r.nombre).split(',')[0].slice(0, 60) : '';
                const el = $('lugarCerca'); if (el) el.textContent = nombre ? 'Cerca de: ' + nombre : '';
            } catch { /* sin dirección: se puede guardar igual */ }
        }, 700);
    }
    function miUbicacion() {
        if (!navigator.geolocation) { estadoMsg('Este dispositivo no ofrece ubicación. Mueve el mapa hasta dejar el pin en el lugar.'); return; }
        const turno = modo.turno; estadoMsg('Buscando tu ubicación…');
        navigator.geolocation.getCurrentPosition((p) => {
            if (!modo.activo || modo.turno !== turno || modo.guardando) return;      // llegó tarde: no mueve nada
            const lat = p.coords.latitude, lng = p.coords.longitude;
            if (!dentro(lat, lng)) { estadoMsg('Tu ubicación queda fuera de la zona donde funciona SEVB. Marca el punto en el mapa.'); return; }
            mapa().setView([lat, lng], Math.max(mapa().getZoom(), 17), { animate: false }); estadoMsg('Moví el mapa a tu ubicación. Ajusta el pin si hace falta y guarda.'); pedirCerca();
        }, () => { if (modo.activo && modo.turno === turno) estadoMsg('No pude obtener tu ubicación. Marca el punto moviendo el mapa.'); }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
    }
    function abrirModo({ tipo, editar = null }) {
        const m = mapa();
        if (!m || modo.activo) { if (!m) aviso('El mapa todavía no está listo. Inténtalo en un momento.', 'info', 4000); return; }
        construir();
        modo.activo = true; modo.tipo = tipo; modo.editar = editar; modo.turno++; modo.guardando = false; modo.cerca = null; modo.abridor = document.activeElement;
        // El selector de A/B (si lo había) cede mientras se marca este lugar; el panel se oculta para ver el mapa. Lo demás (A, B, resultados, viaje) no se toca.
        modo.seleccion = P() && P().cederSeleccion ? P().cederSeleccion() : null;
        modo.panel = !!(S.Panel && !S.Panel.oculto()); if (modo.panel) S.Panel.ocultar('lugar');
        cerrarMenu();
        const d = TIPOS[tipo];
        $('lugarTitulo').textContent = editar ? (d ? 'Cambia la ubicación de ' + d.art : 'Cambia la ubicación de «' + editar.nombre + '»') : (d ? d.titulo : 'Marca el lugar en el mapa');
        $('lugarAyuda').textContent = (editar ? 'Mueve el mapa para ajustar el punto. ' : 'Mueve el mapa hasta dejar el pin sobre el lugar. ') + 'Con teclado: flechas para mover, Enter para guardar.';
        $('lugarNombreFila').hidden = tipo !== 'otro' || !!editar;
        $('lugarNombre').value = ''; $('lugarCerca').textContent = ''; estadoMsg('');
        $('lugarGuardar').textContent = 'Guardar este punto'; $('lugarGuardar').disabled = false; $('lugarCancelar').disabled = false;
        $('lugarGps').hidden = !navigator.geolocation;
        barra.hidden = false; barra.dataset.viaje = document.body.classList.contains('viaje-activo') ? '1' : '';
        document.body.classList.add('modo-lugar');
        ponerPin();
        if (editar) {      // el punto guardado queda BAJO LA PUNTA del pin (que está en el centro del área libre, no del mapa)
            m.setView([editar.lat, editar.lng], Math.max(m.getZoom(), 16), { animate: false });
            const u = m.toLatLng(modo.pt), [cl, cg] = m.getCenter();
            if (u) m.setView([cl + (editar.lat - u[0]), cg + (editar.lng - u[1])], m.getZoom(), { animate: false });
        }
        setTimeout(() => { if (modo.activo) (tipo === 'otro' && !editar ? $('lugarNombre') : pin).focus({ preventScroll: true }); }, 120);
        window.addEventListener('resize', ponerPin);
        if (window.ResizeObserver) { ro = new ResizeObserver(ponerPin); ro.observe(m.el); }
        document.addEventListener('keydown', alEscape, true);
        anunciar(editar ? 'Cambia la ubicación. Mueve el mapa y guarda.' : $('lugarTitulo').textContent);
        pedirCerca();
    }
    function alEscape(e) { if (e.key === 'Escape' && modo.activo && !modo.guardando && !document.querySelector('.modal-backdrop:not([hidden])')) { e.preventDefault(); e.stopPropagation(); cancelar(); } }
    function salirModo({ restaurar = true } = {}) {
        if (!modo.activo) return;
        modo.activo = false; modo.guardando = false; modo.pt = null; modo.turno++; clearTimeout(modo.reverso);
        barra.hidden = true; if (pin) pin.remove(); document.body.classList.remove('modo-lugar');
        window.removeEventListener('resize', ponerPin); document.removeEventListener('keydown', alEscape, true); if (ro) { ro.disconnect(); ro = null; }
        if (modo.panel && S.Panel && S.Panel.ocultoPor() === 'lugar') S.Panel.mostrar('lugar');
        if (restaurar && modo.seleccion && P() && P().reanudarSeleccion) P().reanudarSeleccion(modo.seleccion);       // solo si sigue siendo pertinente
        modo.seleccion = null; modo.panel = false;
    }
    /** Cancelar: nada cambia (la versión anterior queda) y se vuelve al menú, con el foco en el botón que lo abrió. */
    function cancelar() {
        if (!modo.activo || modo.guardando) return;
        const tipo = modo.tipo, editar = modo.editar;
        salirModo(); abrirMenu(); anunciar('Cancelaste. No se guardó nada.');
        setTimeout(() => volverFoco(editar, tipo), 350);
    }
    function volverFoco(editar, tipo) {
        const lista = lugares(), t = editar ? (esReservado(lista, lista.find((f) => f.id === editar.id) || {}) ? tipoDe(editar) : 'otro') : tipo;
        const sel = t === 'casa' || t === 'trabajo' ? '.atajo-fila[data-tipo="' + t + '"] .atajo' : editar ? '[data-id="' + editar.id + '"] .lugar-usar' : '#lugarAgregar';
        const el = document.querySelector(sel) || document.querySelector('#lugarAgregar'); if (el) { try { el.focus({ preventScroll: true }); } catch { /* nada */ } }
    }
    async function confirmar() {
        if (!modo.activo || modo.guardando) return;      // un segundo toque no guarda dos veces
        const turno = modo.turno, c = centro(), tipo = modo.tipo, editar = modo.editar;
        if (!Number.isFinite(c.lat) || !Number.isFinite(c.lng) || Math.abs(c.lat) > 90 || Math.abs(c.lng) > 180) { estadoMsg('No pude leer el punto del mapa. Mueve el mapa e inténtalo de nuevo.'); return; }
        if (!dentro(c.lat, c.lng)) { estadoMsg('Ese punto queda fuera de la zona donde funciona SEVB (Villavicencio y sus alrededores). Mueve el mapa y el pin.'); anunciar('Ese punto queda fuera de la zona de servicio.'); return; }
        const lista = lugares();
        let nombre = null;
        if (tipo === 'otro' && !editar) {
            nombre = limpiarNombre($('lugarNombre').value);
            const err = validarNombre(nombre, lista, null);
            if (err) { estadoMsg(err); $('lugarNombre').focus(); return; }
            const cerca = lista.find((f) => distM(f, c) < DUP_M);
            if (cerca && modo.cerca !== cerca.id) { modo.cerca = cerca.id; estadoMsg('Ya tienes «' + cerca.nombre + '» a menos de ' + DUP_M + ' m. Si es otro lugar, pulsa «Guardar de todos modos».'); $('lugarGuardar').textContent = 'Guardar de todos modos'; return; }
        }
        if (!editar && lista.length >= MAX && !(tipo !== 'otro' && reservado(lista, tipo))) { estadoMsg('Llegaste al límite de ' + MAX + ' lugares. Elimina alguno para agregar otro.'); return; }
        modo.guardando = true; $('lugarGuardar').disabled = true; $('lugarCancelar').disabled = true; $('lugarGuardar').textContent = 'Guardando…'; estadoMsg('Guardando…');
        try {
            const resultado = await S.LugaresCuenta.mutar((vivos) => aplicar(vivos, { tipo, editar, nombre, c }));
            if (!modo.activo || modo.turno !== turno) return;
            const d = TIPOS[tipo], hecho = editar ? 'Cambiaste la ubicación de ' + (d ? d.art : '«' + editar.nombre + '»') : (d ? d.hecho : 'Guardaste «' + nombre + '»');
            salirModo(); aviso(hecho + '.', 'success', 5000); anunciar(hecho);
            abrirMenu(); setTimeout(() => volverFoco(editar || resultado.find((f) => f.nombre === nombre) || null, tipo), 400);
        } catch (e) {
            if (!modo.activo || modo.turno !== turno) return;
            estadoMsg(textoError(e)); anunciar(textoError(e));
        } finally {
            if (modo.activo && modo.turno === turno) { modo.guardando = false; $('lugarGuardar').disabled = false; $('lugarCancelar').disabled = false; $('lugarGuardar').textContent = modo.cerca ? 'Guardar de todos modos' : 'Guardar este punto'; }
        }
    }
    /** Aplica el cambio sobre la lista MÁS RECIENTE de la cuenta (la lee el servidor justo antes): reglas de unicidad, límite y duplicados se evalúan ahí, no sobre una copia vieja. */
    function aplicar(vivos, { tipo, editar, nombre, c }) {
        if (editar) {
            const f = vivos.find((x) => x.id === editar.id);
            if (!f) throw new Error('Ese lugar ya no existe (se borró en otro dispositivo). No se guardó el cambio.');
            f.lat = c.lat; f.lng = c.lng; if (!f.tipo) f.tipo = esReservado(vivos, f) ? tipoDe(f) : 'otro';
            return vivos;
        }
        if (tipo === 'casa' || tipo === 'trabajo') {
            const f = reservado(vivos, tipo);
            if (f) { f.lat = c.lat; f.lng = c.lng; f.tipo = tipo; return vivos; }
            if (vivos.length >= MAX) throw new Error('Llegaste al límite de ' + MAX + ' lugares. Elimina alguno para agregar otro.');
            vivos.unshift({ id: nuevoId(), nombre: TIPOS[tipo].clave, lat: c.lat, lng: c.lng, tipo });
            return vivos;
        }
        const err = validarNombre(nombre, vivos, null); if (err) throw new Error(err);
        if (vivos.length >= MAX) throw new Error('Llegaste al límite de ' + MAX + ' lugares. Elimina alguno para agregar otro.');
        vivos.unshift({ id: nuevoId(), nombre, lat: c.lat, lng: c.lng, tipo: 'otro' });
        return vivos;
    }
    // La sesión cambió con el modo abierto (otra pestaña cerró sesión o entró otra persona): se cierra sin guardar.
    window.addEventListener('spevb-cuenta', () => { if (modo.activo && !modo.guardando) { salirModo(); aviso('La sesión cambió, así que dejé de marcar el lugar. No se guardó nada.', 'info', 6000); } pintar(); });

    // ------------------------------------------------------------------ arranque
    if ($('lugarAgregar')) $('lugarAgregar').addEventListener('click', agregar);
    if ($('menuVolverViaje')) $('menuVolverViaje').addEventListener('click', () => { if (S.Viaje && S.Viaje.activo()) { cerrarMenu(); setTimeout(() => S.Viaje.volverAMiViaje(), 60); } });
    const viajeBoton = () => { const en = !!(S.Viaje && S.Viaje.activo()), b = $('menuVolverViaje'); if (b) b.hidden = !en; const c = $('menuEstadoViaje'), n = $('menuInicioNota'); if (c) c.hidden = !en; if (n) n.hidden = !en; };      // «Viaje en curso» y la nota de «Volver al inicio» solo con un viaje activo
    ['spevb-datos', 'spevb-cuenta', 'spevb-planner-listo'].forEach((n) => window.addEventListener(n, (e) => { if (n !== 'spevb-datos' || !e.detail || e.detail.clave === 'lugares') pintar(); }));
    window.addEventListener('spevb-viaje-modo', () => { viajeBoton(); pintar(); });
    window.addEventListener('spevb-superficies', viajeBoton);
    S.Lugares = { tipoDe, reservado, personalizados, abrirModo, estado: () => ({ activo: modo.activo, tipo: modo.tipo, guardando: modo.guardando }), cancelar, aplicar, validarNombre };
    pintar(); viajeBoton();
})();
