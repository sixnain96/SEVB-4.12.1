'use strict';
/* «Modo viaje»: sigue a la persona en tiempo real, como una app de navegación, pero para tomar el bus.
   Camina al punto de subida → detecta que va en el bus (y pregunta) → avisa antes de bajar → detecta que bajó (y pregunta) → guía hasta B.
   La lógica (filtrar el GPS y decidir la fase) vive en viaje-nucleo.js y se prueba sin salir a la calle; este archivo es solo la interfaz:
   tarjeta del viaje, punto de la persona en el mapa, preguntas, avisos (pantalla, vibración y sonido), pantalla encendida y reanudación. */
(() => {
    const S = window.Spevb;
    const N = S && S.ViajeNucleo;
    const $ = (id) => document.getElementById(id);
    if (!S || !N || !S.Gps || !$('startTrip')) return;
    const CLAVE = 'spevb-viaje-curso';
    const MAX_EDAD_MS = 3 * 3600 * 1000;
    let sesion = null;

    // ------------------------------------------------------------------ CICLO DE VIDA ÚNICO (4.15.1)
    // UNA sola fuente de verdad para «¿hay un viaje?»: `ciclo`. Valores: libre · preparando (el inicio está en marcha: bloqueo contra el doble toque) · activo · llegada (llegó pero la persona
    // todavía no pulsó «Cerrar») · pendiente (hay un viaje guardado esperando «Reanudar viaje»). Además, un bloqueo compartido entre pestañas (localStorage + BroadcastChannel) impide que otra
    // pestaña de este navegador empiece uno. TODOS los puntos de entrada pasan por `iniciar()`; TODA la limpieza por `finalizar()` (idempotente).
    // ---- CONCESIÓN (lease) ENTRE PESTAÑAS · protocolo (4.15.1) -------------------------------------------------------------------------------------------------------------------
    // Una sola pestaña de este navegador puede ser propietaria del viaje. La propiedad es una CONCESIÓN en localStorage: { tab, instancia, nonce, id, estado, t, vida }. Vale mientras
    // Date.now() - t < vida; la pestaña propietaria la renueva con un latido. Reglas (invariantes):
    //  1. Una concesión AJENA VIGENTE nunca se borra ni se sobrescribe, aunque esa pestaña tarde en responder: no responder NO significa que murió (puede estar congelada, en segundo
    //     plano o suspendida por el sistema). Solo se toma el control si el propietario CONFIRMA que terminó (soltó la concesión) o si la concesión de verdad VENCIÓ.
    //  2. Para tomar una vencida: se lee, se espera una verificación breve, se vuelve a leer (sigue vencida y sin cambios), se escribe un nonce propio y se vuelve a leer para comprobar
    //     que la ganó esta pestaña. Con Web Locks (navigator.locks) esa lectura-escritura es además atómica entre pestañas; sin ellos, la verificación posterior cubre la carrera.
    //  3. Quien pierda la concesión (porque estuvo suspendida y otra pestaña la tomó al vencer) lo descubre al reanudarse (latido, evento «storage», pageshow, visibilidad, resume): detiene sus
    //     efectos SIN borrar el estado guardado ni la concesión de la pestaña nueva, y no la recupera.
    //  4. Pedir terminar a otra pestaña usa BroadcastChannel Y un mensaje por localStorage (evento «storage»): sin BroadcastChannel sigue funcionando. Sin confirmación explícita no se actúa.
    // Duraciones configurables SOLO para pruebas de navegador (window.__spevbPruebas, definido por un script de inicio de la prueba): vidaBloqueoMs, latidoMs, esperaTerminarMs, verificacionMs.
    const CLAVE_BLOQUEO = 'spevb-viaje-bloqueo', CLAVE_ORDEN = 'spevb-viaje-orden', SECCION_ADQUIRIR = 'spevb-viaje-adquirir';
    const PRUEBAS = (window.__spevbPruebas && typeof window.__spevbPruebas === 'object') ? window.__spevbPruebas : {};
    const duracion = (v, def, min) => (Number.isFinite(Number(v)) && Number(v) >= min ? Number(v) : def);
    const VIDA_BLOQUEO_MS = duracion(PRUEBAS.vidaBloqueoMs, 20000, 300), LATIDO_MS = duracion(PRUEBAS.latidoMs, 5000, 100);
    const ESPERA_TERMINAR_MS = duracion(PRUEBAS.esperaTerminarMs, 2500, 200), VERIFICACION_MS = duracion(PRUEBAS.verificacionMs, 80, 10);
    let ciclo = 'libre', intento = 0, latido = null, nonce = null, venceTimer = null, ultimoOrden = null;
    const contadores = { creadas: 0, liberadas: 0, concesionesPerdidas: 0 };
    const nuevoId = () => 'v' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
    const pausa = (ms) => new Promise((r) => setTimeout(r, ms));
    const miTab = (() => {
        try { let t = sessionStorage.getItem('spevb-tab'); if (!t) { t = nuevoId(); sessionStorage.setItem('spevb-tab', t); } return t; } catch { return nuevoId(); }
    })();
    const instancia = nuevoId();      // identifica ESTA carga de la página (una recarga de la misma pestaña es otra instancia)
    let canal = null;
    try { if ('BroadcastChannel' in window) canal = new BroadcastChannel('spevb-viaje'); } catch { canal = null; }
    const leerBloqueo = () => { try { const b = JSON.parse(localStorage.getItem(CLAVE_BLOQUEO)); return b && typeof b.tab === 'string' && typeof b.t === 'number' ? b : null; } catch { return null; } };
    /** ¿La concesión sigue vigente? Se mide con el reloj y la vida que escribió su propietario (una hora absurda en el futuro no la hace eterna). */
    const vigente = (b) => { if (!b) return false; const edad = Date.now() - b.t, vida = Number(b.vida) > 0 ? Number(b.vida) : VIDA_BLOQUEO_MS; return edad > -vida && edad < vida; };
    /** Concesión vigente de OTRA pestaña/instancia. Una vencida no cuenta. Nunca se borra desde aquí. */
    const bloqueoAjeno = () => { const b = leerBloqueo(); if (!b || (nonce && b.nonce === nonce)) return null; return vigente(b) ? b : null; };
    /** ¿Esta página es hoy la propietaria? (lee la concesión: no se fía de una variable que pudo quedar vieja durante una suspensión) */
    const poseo = () => { if (!nonce) return false; const b = leerBloqueo(); return !!b && b.nonce === nonce; };
    function escribirBloqueo() { if (!nonce) return; try { localStorage.setItem(CLAVE_BLOQUEO, JSON.stringify({ tab: miTab, instancia, nonce, id: sesion ? sesion.id : null, estado: ciclo, t: Date.now(), vida: VIDA_BLOQUEO_MS })); } catch { /* sin almacenamiento */ } }
    function iniciarLatido() { if (!latido) latido = setInterval(latidoTick, LATIDO_MS); }
    function latidoTick() { if (!nonce) return; if (!verificarPosesion()) return; escribirBloqueo(); }
    /** Latido extra desde el GPS: si el navegador estrangula los temporizadores de una pestaña en segundo plano, cada lectura de posición también renueva la concesión (como máximo cada 2 s). */
    let ultimoLatido = 0;
    function renovarSiToca() { if (!nonce || Date.now() - ultimoLatido < 2000) return; ultimoLatido = Date.now(); latidoTick(); }
    /** Toma la concesión (o la renueva si ya es nuestra). Devuelve { ok } o { ok: false, b } con la concesión ajena que lo impide. Es lo ÚNICO que escribe una concesión nueva. */
    async function adquirir() {
        if (nonce) { if (poseo()) { escribirBloqueo(); iniciarLatido(); return { ok: true }; } nonce = null; }      // la nuestra se perdió mientras tanto
        const seccion = async () => {
            const b = leerBloqueo();
            if (b && vigente(b)) return { ok: false, b };      // vigente y ajena: ni se borra ni se sobrescribe
            if (b) {      // venció: se comprueba que SIGUE vencida y sin cambios antes de tomarla
                const firma = JSON.stringify(b);
                await pausa(VERIFICACION_MS);
                const b2 = leerBloqueo();
                if (b2 && (JSON.stringify(b2) !== firma || vigente(b2))) return { ok: false, b: b2 };
            }
            nonce = nuevoId(); escribirBloqueo();
            return { ok: true };
        };
        let r;
        try { r = (navigator.locks && navigator.locks.request) ? await navigator.locks.request(SECCION_ADQUIRIR, seccion) : await seccion(); } catch { r = await seccion(); }
        if (!r.ok) return r;
        await pausa(VERIFICACION_MS);      // verificación posterior: se vuelve a leer para confirmar que la ganó ESTA pestaña
        if (!poseo()) { const b = leerBloqueo(); nonce = null; return { ok: false, b, perdida: true }; }
        iniciarLatido();
        return { ok: true };
    }
    /** Suelta la concesión SOLO si es nuestra (nunca la de otra pestaña). */
    function soltarBloqueo() {
        clearInterval(latido); latido = null;
        const b = leerBloqueo();
        if (nonce && b && b.nonce === nonce) { try { localStorage.removeItem(CLAVE_BLOQUEO); } catch { /* nada */ } }
        nonce = null;
    }
    /** Al reanudarse (o ante cualquier señal), comprueba que sigue siendo propietaria. Si otra pestaña tomó la concesión al vencer, detiene los efectos y NO la recupera. */
    function verificarPosesion() {
        if (!nonce) return true;
        const b = leerBloqueo();
        if (b && b.nonce !== nonce) { perderConcesion(); return false; }
        if (!b) escribirBloqueo();      // alguien limpió el almacenamiento: nadie más la tiene, se reafirma
        return true;
    }
    function perderConcesion() {
        contadores.concesionesPerdidas++;
        clearInterval(latido); latido = null; nonce = null;
        if (sesion) {
            finalizar({ borrarEstado: false, perdido: true });
            S.toast('Tu viaje se abrió en otra pestaña, así que esta dejó de seguirlo. Sigue en esa pestaña.', { tipo: 'info', ms: 9000, clave: 'viaje' });
        } else if (ciclo === 'pendiente') {
            descartarReanudar({ conservarGuardado: true }); ciclo = 'libre';
        } else if (ciclo === 'preparando') { intento++; ciclo = 'libre'; }
        pintarBotonInicio();
    }
    /** Cuando una concesión ajena vence, esta pestaña lo nota sola: el botón se actualiza y, si quedó un viaje guardado, se ofrece reanudarlo. */
    function vigilarVencimiento() {
        clearTimeout(venceTimer); venceTimer = null;
        const b = bloqueoAjeno(); if (!b) return;
        venceTimer = setTimeout(() => {
            venceTimer = null; pintarBotonInicio();
            if (bloqueoAjeno()) return vigilarVencimiento();
            if (ciclo === 'libre' && !sesion && !reanudarAbierta) ofrecerReanudar();
        }, Math.max(250, (Number(b.vida) || VIDA_BLOQUEO_MS) - (Date.now() - b.t) + 150));
    }
    /** Pide a OTRA pestaña que termine su viaje (por BroadcastChannel y por localStorage). Devuelve true SOLO si confirma soltando la concesión; sin respuesta devuelve false y no toca nada. */
    async function pedirTerminarAjeno(b) {
        const orden = { tipo: 'terminar', para: b.nonce || null, id: nuevoId(), de: miTab, t: Date.now() };
        try { canal && canal.postMessage(orden); } catch { /* sin canal */ }
        try { localStorage.setItem(CLAVE_ORDEN, JSON.stringify(orden)); } catch { /* sin almacenamiento */ }
        const fin = Date.now() + ESPERA_TERMINAR_MS;
        while (Date.now() < fin) {
            const l = leerBloqueo();
            if (!l || !vigente(l)) { try { localStorage.removeItem(CLAVE_ORDEN); } catch { /* nada */ } return true; }      // soltó la concesión (o ya había vencido)
            if (l.nonce !== b.nonce) return false;      // otra pestaña la tomó: no era la que se pidió
            await pausa(60);
        }
        try { localStorage.removeItem(CLAVE_ORDEN); } catch { /* nada */ }
        return false;      // sin confirmación: la concesión vigente se respeta
    }
    /** Esta pestaña recibió la orden de terminar. Solo la obedece si va dirigida a su concesión actual. */
    function atenderOrden(o) {
        if (!o || o.tipo !== 'terminar' || o.id === ultimoOrden || !nonce || o.para !== nonce || !poseo()) return;
        if (!(Date.now() - o.t <= ESPERA_TERMINAR_MS + 500)) return;      // una orden tardía (la pestaña estaba congelada y la otra ya dejó de esperar) NO se ejecuta: nadie la espera
        ultimoOrden = o.id;
        if (sesion) finalizar();
        else if (ciclo === 'pendiente') descartarReanudar();
        else return;
        try { canal && canal.postMessage({ tipo: 'terminado', nonce: o.para, id: o.id }); } catch { /* sin canal */ }
    }
    /** El botón «Iniciar viaje» comunica su estado sin dejar de recibir toques (el toque abre la explicación): ocupado, en curso o abierto en otra pestaña. */
    function pintarBotonInicio() {
        const b = $('startTrip'); if (!b) return;
        const span = b.querySelector('span'), ajeno = ciclo === 'libre' && !!bloqueoAjeno();
        b.setAttribute('aria-busy', String(ciclo === 'preparando'));
        b.setAttribute('aria-disabled', String(ciclo !== 'libre' || ajeno));
        b.dataset.ciclo = ajeno ? 'ajeno' : ciclo;
        if (span) span.textContent = ciclo === 'preparando' ? 'Preparando tu viaje…' : ciclo === 'libre' ? (ajeno ? 'Viaje abierto en otra pestaña' : 'Iniciar viaje') : 'Viaje en curso';
    }
    const liberarCompartir = () => { try { return S.Compartir && S.Compartir.liberar ? S.Compartir.liberar() : null; } catch { return null; } };

    // ---- «Ya tienes un viaje en curso»: la única respuesta a un segundo intento. Nada se reemplaza en un toque.
    let dlgC = null, confirmandoFin = false;
    function situacion() { return ciclo === 'llegada' ? 'llegada' : ciclo === 'pendiente' ? 'pendiente' : (ciclo === 'libre' && bloqueoAjeno()) ? 'ajeno' : 'activo'; }
    function pintarConflicto() {
        const v = situacion(), t = $('conflTexto'), volver = $('conflVolver'), fin = $('conflTerminar'), canc = $('conflCancelar');
        if (confirmandoFin) {
            t.textContent = v === 'pendiente' ? '¿Descartar el viaje guardado? Se borra su progreso y no se puede deshacer.' : '¿Terminar el viaje actual? Se detiene el seguimiento y se borra su progreso. No se puede deshacer.';
            volver.textContent = 'No, seguir con mi viaje'; fin.textContent = v === 'pendiente' ? 'Sí, descartar viaje' : 'Sí, terminar viaje'; canc.hidden = true;
            return;
        }
        canc.hidden = false;
        t.textContent = v === 'llegada' ? 'Cierra la llegada antes de empezar otro viaje.' : v === 'pendiente' ? 'Tienes un viaje guardado sin terminar. Reanúdalo o descártalo antes de empezar otro.'
            : v === 'ajeno' ? 'Ya hay un viaje activo en otra pestaña de este navegador. Termina ese viaje antes de empezar otro.' : 'Termina el viaje actual antes de empezar otro.';
        volver.textContent = v === 'pendiente' ? 'Reanudar viaje' : 'Volver a mi viaje';
        fin.textContent = v === 'llegada' ? 'Cerrar llegada' : v === 'pendiente' ? 'Descartar viaje guardado' : 'Terminar viaje actual';
    }
    function cerrarConflicto() { confirmandoFin = false; if (dlgC && !dlgC.hidden) S.Modal.cerrar(dlgC); }
    function crearDialogoConflicto() {
        if (dlgC) return dlgC;
        dlgC = document.createElement('div');
        dlgC.id = 'viajeConflicto'; dlgC.className = 'modal-backdrop'; dlgC.hidden = true;
        dlgC.innerHTML = `
            <div class="modal-card inicio-card" role="alertdialog" aria-modal="true" aria-labelledby="conflTitulo" aria-describedby="conflTexto">
                <h2 id="conflTitulo">Ya tienes un viaje en curso</h2>
                <p id="conflTexto" class="muted"></p>
                <div class="modal-actions inicio-acciones">
                    <button id="conflVolver" class="primary-plan-button" type="button">Volver a mi viaje</button>
                    <button id="conflTerminar" class="secondary danger" type="button">Terminar viaje actual</button>
                    <button id="conflCancelar" class="secondary" type="button">Cancelar</button>
                </div>
            </div>`;
        document.body.appendChild(dlgC);
        $('conflCancelar').addEventListener('click', cerrarConflicto);
        $('conflVolver').addEventListener('click', () => { const pend = situacion() === 'pendiente' && !confirmandoFin; cerrarConflicto(); if (pend) { const si = q('viajeSi'); if (si) si.click(); } else volverAMiViaje(); });
        $('conflTerminar').addEventListener('click', async () => {
            const v = situacion();
            if (v === 'llegada') { cerrarConflicto(); finalizar(); return S.toast('Cerraste la llegada. Ya puedes empezar otro viaje.', { tipo: 'info', ms: 4500, clave: 'viaje' }); }
            if (!confirmandoFin) { confirmandoFin = true; pintarConflicto(); $('conflVolver').focus({ preventScroll: true }); return; }      // la opción segura recibe el foco
            cerrarConflicto();
            if (await terminarActual()) return S.toast('Viaje terminado. Ya puedes empezar otro.', { tipo: 'info', ms: 4500, clave: 'viaje' });
            const b = bloqueoAjeno(), seg = b ? Math.max(1, Math.ceil(((Number(b.vida) || VIDA_BLOQUEO_MS) - (Date.now() - b.t)) / 1000)) : 0;
            S.toast('Ya hay un viaje activo en otra pestaña y no respondió. Por seguridad no lo borro: ' + (seg ? 'podrás empezar otro cuando esa pestaña deje de responder (en unos ' + seg + ' s) o al terminarlo allí.' : 'vuelve a intentarlo.'), { tipo: 'alerta', ms: 12000, clave: 'viaje' });
        });
        dlgC.addEventListener('click', (e) => { if (e.target === dlgC) cerrarConflicto(); });
        return dlgC;
    }
    function mostrarConflicto() {
        crearDialogoConflicto();
        if (!dlgC.hidden) return;
        confirmandoFin = false; pintarConflicto();
        S.Modal.abrir(dlgC, { fondo: true, escape: true, foco: '#conflVolver', cerrar: cerrarConflicto });
    }
    /** Termina de verdad el viaje actual (esta pestaña, uno guardado o el de otra pestaña) y deja todo libre. Solo se llama tras una confirmación explícita. */
    async function terminarActual() {
        if (sesion) finalizar();
        else if (ciclo === 'pendiente') descartarReanudar();
        else if (bloqueoAjeno()) {
            // La otra pestaña debe CONFIRMAR que terminó (soltando la concesión). Si no responde, su concesión vigente se respeta: nada se borra ni se sobrescribe.
            const b = bloqueoAjeno();
            if (b && !(await pedirTerminarAjeno(b))) { pintarBotonInicio(); vigilarVencimiento(); return false; }
        }
        ciclo = 'libre'; pintarBotonInicio();
        return true;
    }
    /** «Volver a mi viaje»: la tarjeta a la vista y el mapa en tu posición; el planificador cede. En otra pestaña, le pide que se muestre. */
    function volverAMiViaje() {
        if (sesion) {
            if (S.Panel && !S.Panel.oculto()) S.Panel.ocultar('viaje');
            if (ui.modo !== 'completa') ponerModo('completa', { recordar: false });
            const l = sesion.marcador && sesion.marcador.getPosition();
            if (l && mapa()) { sesion.seguir = true; q('viajeSeguir').setAttribute('aria-pressed', 'true'); try { S.centrarEn(mapa(), l, Math.max(mapa().getZoom(), 16)); } catch { /* mapa no listo */ } sesion.zoomSeguimiento = true; }
            const t = q('viajeTitulo'); t.setAttribute('tabindex', '-1'); try { t.focus({ preventScroll: true }); } catch { /* nada */ }
        } else if (ciclo === 'pendiente') { tarjeta.hidden = false; try { q('viajeSi').focus({ preventScroll: true }); } catch { /* nada */ } }
        else if (bloqueoAjeno()) {
            try { canal && canal.postMessage({ tipo: 'enfocar' }); } catch { /* sin canal */ }
            S.toast('Tu viaje está abierto en otra pestaña de este navegador. Cambia a esa pestaña para seguirlo.', { tipo: 'info', ms: 7000, clave: 'viaje' });
        }
    }
    if (canal) canal.onmessage = (e) => {
        const m = e && e.data; if (!m) return;
        if (m.tipo === 'enfocar' && (sesion || ciclo === 'pendiente')) { try { window.focus(); } catch { /* nada */ } volverAMiViaje(); }
        else if (m.tipo === 'terminar') atenderOrden(m);
    };
    window.addEventListener('storage', (e) => {
        if (e.key === CLAVE_ORDEN) { try { atenderOrden(JSON.parse(e.newValue)); } catch { /* orden ilegible */ } return; }      // respaldo sin BroadcastChannel
        if (e.key !== CLAVE_BLOQUEO) return;
        if (nonce && !verificarPosesion()) return;      // otra pestaña tomó la concesión: esta detiene sus efectos
        pintarBotonInicio();
        if (ciclo === 'libre' && !sesion && !bloqueoAjeno() && !reanudarAbierta) ofrecerReanudar();      // la otra pestaña soltó el bloqueo: si quedó un viaje guardado, se ofrece reanudarlo
        else if (ciclo === 'libre' && bloqueoAjeno()) vigilarVencimiento();
    });

    const mapa = () => (S.maps && S.maps.map) || (window.SpevbExplorer && window.SpevbExplorer.map);
    const leer = () => { try { return JSON.parse(localStorage.getItem(CLAVE)); } catch { return null; } };
    const borrar = () => { try { localStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ } };
    /** Estado reanudable (4.14): el plan (con las caminatas cuando ya llegaron), el estado del núcleo, la hora ORIGINAL de inicio y solo la ÚLTIMA posición válida
     *  (nunca un historial de ubicaciones). `t` es cuándo se guardó: al reanudar, esa posición se presenta como antigua hasta recibir una lectura nueva. */
    const guardar = () => {
        if (!sesion || !poseo()) return;      // solo la pestaña propietaria escribe el avance: una pestaña suspendida que despierta no pisa el estado de la que tomó el viaje
        try {
            const sel = S.Planner && S.Planner.seleccion && S.Planner.seleccion.viaje;
            if (sel && sel.caminatas && !sesion.plan.caminatas && sel.destino && sel.destino.lat === sesion.plan.destino.lat && sel.destino.lng === sesion.plan.destino.lng) sesion.plan.caminatas = redondear(sel.caminatas);
            localStorage.setItem(CLAVE, JSON.stringify({ v: 2, id: sesion.id, vid: sesion.viajeId, previas: sesion.previas || 0, bajada: !!sesion.bajadaAbierta, plan: sesion.plan, estado: sesion.nucleo.serializar(), t: Date.now(), inicio: sesion.inicio, ultima: sesion.ultima || null, ruta: sesion.ruta ? sesion.ruta.serializar() : (sesion.rutaGuardada || null), cam: camGuardable() }));
        } catch { /* sin almacenamiento */ }
    };
    const redondear = (plan) => JSON.parse(JSON.stringify(plan, (k, v) => (typeof v === 'number' && !Number.isInteger(v) ? Math.round(v * 1e6) / 1e6 : v)));

    // ------------------------------------------------------------------ tarjeta
    const tarjeta = document.createElement('section');
    tarjeta.id = 'viajeCard'; tarjeta.className = 'viaje-card'; tarjeta.hidden = true;
    tarjeta.setAttribute('role', 'region'); tarjeta.setAttribute('aria-label', 'Modo viaje');
    tarjeta.innerHTML = `
        <div class="viaje-tope">
            <div class="viaje-asa" id="viajeAsa" tabindex="0" role="group"
                 aria-label="Mover la tarjeta del viaje: arrástrala o usa las flechas del teclado; doble toque para devolverla a su sitio"><span class="viaje-agarre" aria-hidden="true"></span></div>
            <div class="viaje-ventana">
                <button type="button" id="viajeInicio" class="viaje-icono-boton" aria-label="Volver al inicio" title="Volver al inicio"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 11l8-7 8 7M6 10v10h4v-6h4v6h4V10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
                <button type="button" id="viajeMinimizar" class="viaje-icono-boton" aria-label="Minimizar la tarjeta del viaje" aria-expanded="true" title="Minimizar"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M6 10l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
                <button type="button" id="viajeOcultar" class="viaje-icono-boton" aria-label="Ocultar la tarjeta del viaje (el viaje sigue; toca «Viaje» para volver a verla)" title="Ocultar"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg></button>
            </div>
        </div>
        <div class="viaje-cab">
            <span class="viaje-icono" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 3l7 17-7-4-7 4z" fill="currentColor"/></svg></span>
            <h2 class="viaje-titulo" id="viajeTitulo">Modo viaje</h2>
        </div>
        <div class="viaje-llegada" id="viajeLlegada" hidden>
            <span class="viaje-sello" aria-hidden="true"><svg viewBox="0 0 52 52" width="44" height="44"><circle cx="26" cy="26" r="23"/><path d="M15 27l8 8 14-16"/></svg></span>
            <div class="viaje-llegada-texto"><p class="viaje-llegada-titulo" aria-hidden="true">¡Llegaste a tu destino!</p><p class="viaje-llegada-detalle" id="viajeLlegadaDetalle" role="status" aria-live="polite" hidden></p></div>
            <div class="viaje-confeti" id="viajeConfeti" aria-hidden="true"></div>
        </div>
        <div class="viaje-ruta">
            <span class="viaje-bus" id="viajeBus" hidden></span>
            <p class="viaje-mini" id="viajeMini" aria-hidden="true"></p>
        </div>
        <p class="viaje-instruccion" id="viajeInstruccion" aria-live="polite"></p>
        <p class="viaje-desvio-nota" id="viajeDesvioNota" hidden></p>
        <div class="estados-viaje" id="viajeEstados" role="status" aria-live="polite" hidden></div>
        <div class="viaje-caminata" id="viajeCaminata" role="status" aria-live="polite" hidden>
            <p class="viaje-caminata-titulo" id="viajeCaminataTitulo"></p>
            <p id="viajeCaminataTexto"></p>
            <div class="viaje-caminata-botones">
                <button type="button" id="viajeCaminataReintentar" hidden>Reintentar</button>
                <button type="button" id="viajeCaminataRecalcular" hidden>Recalcular desde aquí</button>
            </div>
        </div>
        <div class="viaje-barra" id="viajeBarra" role="progressbar" aria-label="Avance de esta parte del viaje" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i></div>
        <div class="viaje-aviso" id="viajeAviso" role="alert" hidden></div>
        <div class="viaje-pregunta" id="viajePregunta" role="alertdialog" aria-labelledby="viajePreguntaTexto" hidden>
            <p id="viajePreguntaTexto"></p>
            <div class="viaje-botones">
                <button type="button" class="viaje-si" id="viajeSi">Sí</button>
                <button type="button" class="viaje-no" id="viajeNo">No</button>
            </div>
        </div>
        <div class="viaje-bajada" id="viajeBajada" role="alertdialog" aria-labelledby="viajeBajadaTitulo" aria-describedby="viajeBajadaTexto" hidden>
            <p class="viaje-bajada-titulo" id="viajeBajadaTitulo">Tu bajada está aquí</p>
            <p class="viaje-bajada-texto" id="viajeBajadaTexto">Baja cuando el bus se detenga.</p>
            <p class="viaje-bajada-parada" id="viajeBajadaParada" hidden></p>
            <div class="viaje-bajada-botones">
                <button type="button" class="viaje-bajada-ya" id="viajeBajadaYa">Ya me bajé</button>
                <button type="button" class="viaje-bajada-sigo" id="viajeBajadaSigo">Sigo en el bus</button>
            </div>
        </div>
        <div class="viaje-manual" id="viajeManual" hidden>
            <button type="button" id="viajeYaSubi" class="viaje-manual-boton" hidden>Ya me subí</button>
            <button type="button" id="viajeYaBaje" class="viaje-manual-boton" hidden>Ya me bajé</button>
        </div>
        <div class="viaje-pie">
            <button type="button" id="viajeSeguir" aria-pressed="true">Seguirme</button>
            <button type="button" id="viajeMas" aria-expanded="false" aria-controls="viajeMasPanel">Más</button>
            <button type="button" id="viajeTerminar" class="viaje-terminar">Terminar viaje</button>
        </div>
        <div class="viaje-mas" id="viajeMasPanel" hidden>
            <span class="viaje-lecturas"><b id="viajeDist">—</b><small>falta</small></span>
            <span class="viaje-lecturas"><b id="viajeEta">—</b><small>aprox.</small></span>
            <span class="viaje-lecturas"><b id="viajeVel">—</b><small>velocidad</small></span>
            <span class="viaje-lecturas"><b id="viajePrec">—</b><small>precisión</small></span>
            <button type="button" id="viajeRecuperarMapa">Recuperar mapa</button>
            <button type="button" id="viajeRecalcular">Recalcular desde aquí</button>
            <div class="viaje-alertas" id="viajeAlertasFila">
                <button type="button" id="viajeAlertas" aria-pressed="true">Alertas de bajada: activadas</button>
                <small id="viajeAlertasEstado" role="status"></small>
                <button type="button" id="viajeActivarAlertas" hidden>Activar alertas</button>
            </div>
        </div>`;
    // La tarjeta y su pastilla viven en <body>: dentro de .app (position: fixed = su propia pila) nunca podrían verse sobre el menú, ni siquiera un aviso urgente.
    document.body.appendChild(tarjeta);
    const q = (id) => $(id);
    // Pastilla que queda cuando la tarjeta se oculta: el viaje sigue y un toque la devuelve.
    const pastilla = document.createElement('button');
    pastilla.type = 'button'; pastilla.id = 'viajePastilla'; pastilla.className = 'viaje-pastilla'; pastilla.hidden = true;
    pastilla.setAttribute('aria-label', 'Mostrar la tarjeta del viaje');
    pastilla.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 3l7 17-7-4-7 4z" fill="currentColor"/></svg><span>Viaje</span><b id="viajePastillaDato"></b>';
    document.body.appendChild(pastilla);


    // ------------------------------------------------------------------ tarjeta: arrastrar, minimizar y ocultar
    // La tarjeta NO debe quedar fija tapando el mapa: se mueve con el dedo, el ratón o el teclado, se minimiza a una barra y se oculta a una pastilla.
    // Las preguntas y los avisos importantes la vuelven a abrir solos (no se puede perder el aviso de bajada por tenerla escondida).
    const CLAVE_UI = 'spevb-viaje-ui';
    const ui = { modo: 'completa', x: 0, y: 0 };
    try { Object.assign(ui, JSON.parse(localStorage.getItem(CLAVE_UI)) || {}); } catch { /* valores por defecto */ }
    if (!['completa', 'compacta', 'oculta'].includes(ui.modo)) ui.modo = 'completa';
    ui.x = Number.isFinite(ui.x) ? ui.x : 0; ui.y = Number.isFinite(ui.y) ? ui.y : 0;
    const guardarUi = () => { try { localStorage.setItem(CLAVE_UI, JSON.stringify(ui)); } catch { /* sin almacenamiento */ } };
    function aplicarPosicion() { tarjeta.style.transform = ui.x || ui.y ? 'translate(' + ui.x + 'px, ' + ui.y + 'px)' : ''; }
    /** Deja la tarjeta entera dentro de la pantalla (también tras girar el teléfono o cambiar el tamaño de la ventana). */
    function limitarPosicion() {
        if (tarjeta.hidden) return;
        if (tarjeta.dataset.cede === 'overlay' && !tarjeta.dataset.urgente) return;      // cedida (desplazada 18 px por la animación): medirla ahora movería la posición guardada
        if (tarjeta.dataset.urgente && (tarjeta.dataset.cede === 'overlay' || tarjeta.dataset.cede === 'planificador')) return;      // aviso arriba y reducido: el CSS ignora la posición de la persona; no se toca ni se guarda
        const r = tarjeta.getBoundingClientRect();
        if (!r.width) return;
        const margen = 4, arriba = 56;      // arriba se respeta la barra de la aplicación
        let dx = 0, dy = 0;
        if (r.left < margen) dx = margen - r.left; else if (r.right > innerWidth - margen) dx = innerWidth - margen - r.right;
        if (r.top < arriba) dy = arriba - r.top; else if (r.bottom > innerHeight - margen) dy = innerHeight - margen - r.bottom;
        if (dx || dy) { ui.x += dx; ui.y += dy; aplicarPosicion(); }
    }
    function datoCorto() { const i = sesion && sesion.nucleo.info(); return i && i.distancia !== null ? fmtDist(i.distancia) : ''; }
    function ponerModo(modo, { recordar = true } = {}) {
        ui.modo = modo;
        tarjeta.dataset.modo = modo;
        const visible = !!sesion || tarjeta.dataset.fase === 'reanudar';
        tarjeta.hidden = !visible || modo === 'oculta';
        pastilla.hidden = !sesion || modo !== 'oculta';
        q('viajeMinimizar').setAttribute('aria-expanded', String(modo === 'completa'));
        q('viajeMinimizar').setAttribute('aria-label', modo === 'completa' ? 'Minimizar la tarjeta del viaje' : 'Expandir la tarjeta del viaje');
        q('viajeMinimizar').title = modo === 'completa' ? 'Minimizar' : 'Expandir';
        q('viajeMinimizar').firstElementChild.style.transform = modo === 'completa' ? '' : 'rotate(180deg)';
        if (recordar) guardarUi();
        requestAnimationFrame(limitarPosicion);
    }
    /** Una pregunta o un aviso urgente siempre se ven: abre la tarjeta aunque estuviera minimizada u oculta. */
    // Si un menú o diálogo está encima, la tarjeta NO se reabre a pantalla completa: el aviso importante sale en su propia presentación (ver sincronizarUrgente).
    // «Cedida»: hay un menú/diálogo encima o la persona trajo el planificador durante el viaje. En ambos casos un aviso importante sale reducido y arriba, sin maximizar la tarjeta.
    const cedida = () => tarjeta.dataset.cede === 'overlay' || tarjeta.dataset.cede === 'planificador';
    function mostrarCompleta() { if (cedida()) return sincronizarUrgente(); if (ui.modo !== 'completa') ponerModo('completa', { recordar: false }); }
    /** Un aviso importante (pregunta de subida/bajada, aviso próximo o urgente, error que pide acción) tiene que verse aunque la tarjeta haya cedido el sitio
     *  al menú o esté oculta: la misma tarjeta se muestra SOLO con esa pregunta/aviso, arriba de todo. Es UNA pila, no otra: nunca hay dos preguntas a la vez. */
    // Una pregunta que pide respuesta, con un menú o diálogo abierto, pasa a ser LA ventana de arriba del controlador común (modales.js): ahí se coordinan el foco
    // (entra en «Sí»), Tab (se queda en la pregunta), Escape (= la respuesta prudente), el fondo inerte y el regreso del foco al terminar. Sin menú ni diálogo no se usa:
    // el mapa y el planificador siguen siendo operables junto a la tarjeta.
    let ventanaPregunta = null;
    const preguntaPideRespuesta = () => !!sesion && ((!q('viajePregunta').hidden && ['subida', 'bajada', 'recalculo'].includes(q('viajePregunta').dataset.id || '')) || !q('viajeBajada').hidden);
    function escaparPregunta() { if (!q('viajeBajada').hidden) return q('viajeBajadaSigo').click(); if (preguntaPideRespuesta()) q('viajeNo').click(); }      // «Todavía no» / «No, sigo en el bus» / «No, seguir con el actual»: nunca descarta ni cambia nada por sí sola
    function sincronizarVentanaPregunta() {
        if (!S.Modal || !S.Superficies) return;
        const encima = !!S.Superficies.estado().overlay && preguntaPideRespuesta();
        if (encima && !ventanaPregunta) {
            ventanaPregunta = S.Modal.abrir(tarjeta, { mostrar: () => {}, ocultar: () => {}, tarjeta, escape: true, cerrar: escaparPregunta, foco: () => (!q('viajeBajada').hidden ? q('viajeBajadaYa') : q('viajeSi')) });
        } else if (!encima && ventanaPregunta) {
            ventanaPregunta = null;
            S.Modal.cerrar(tarjeta);
        }
    }
    function sincronizarUrgente() {
        const aviso = q('viajeAviso'), preg = q('viajePregunta');
        const urgente = !!sesion && (!preg.hidden || !q('viajeBajada').hidden || (!aviso.hidden && (aviso.dataset.nivel === 'urgente' || aviso.dataset.nivel === 'alerta')));
        const antes = tarjeta.dataset.urgente;
        if (urgente) tarjeta.dataset.urgente = '1'; else delete tarjeta.dataset.urgente;
        if (antes !== tarjeta.dataset.urgente && S.Superficies) S.Superficies.aplicar();      // el coordinador exime a la tarjeta del `inert` del menú mientras haya un aviso importante
        pastilla.classList.toggle('con-aviso', urgente);
        if (urgente && cedida() && tarjeta.hidden) { tarjeta.hidden = false; tarjeta.dataset.forzada = '1'; }
        else if (tarjeta.dataset.forzada && !(urgente && cedida())) { delete tarjeta.dataset.forzada; ponerModo(ui.modo, { recordar: false }); }
        sincronizarVentanaPregunta();
    }
    window.addEventListener('spevb-superficies', () => { sincronizarUrgente(); requestAnimationFrame(limitarPosicion); });
    q('viajeMinimizar').addEventListener('click', () => ponerModo(ui.modo === 'completa' ? 'compacta' : 'completa'));
    q('viajeOcultar').addEventListener('click', () => { ponerModo('oculta'); pastilla.focus({ preventScroll: true }); });
    pastilla.addEventListener('click', () => { ponerModo('compacta'); q('viajeMinimizar').focus({ preventScroll: true }); });
    q('viajeMas').addEventListener('click', () => {
        const abierto = q('viajeMasPanel').hidden;
        q('viajeMasPanel').hidden = !abierto; q('viajeMas').setAttribute('aria-expanded', String(abierto));
        q('viajeMas').textContent = abierto ? 'Menos' : 'Más';
        requestAnimationFrame(limitarPosicion);
    });

    const asa = q('viajeAsa');
    let arrastre = null;
    asa.addEventListener('pointerdown', (e) => {
        if (e.button !== undefined && e.button > 0) return;
        arrastre = { id: e.pointerId, sx: e.clientX, sy: e.clientY, x: ui.x, y: ui.y };
        try { asa.setPointerCapture(e.pointerId); } catch { /* sin captura */ }
        tarjeta.classList.add('arrastrando');
        e.preventDefault();
    });
    asa.addEventListener('pointermove', (e) => {
        if (!arrastre || e.pointerId !== arrastre.id) return;
        ui.x = arrastre.x + (e.clientX - arrastre.sx); ui.y = arrastre.y + (e.clientY - arrastre.sy);
        aplicarPosicion();
    });
    const soltar = (e) => {
        if (!arrastre || (e && e.pointerId !== arrastre.id)) return;
        arrastre = null; tarjeta.classList.remove('arrastrando');
        limitarPosicion(); guardarUi();
    };
    asa.addEventListener('pointerup', soltar); asa.addEventListener('pointercancel', soltar);
    // El gesto termina SIEMPRE: al perder la captura del puntero, al perder el foco la ventana o al ocultarse la página (nunca queda «arrastrando» pegado).
    asa.addEventListener('lostpointercapture', soltar);
    window.addEventListener('blur', () => soltar());
    document.addEventListener('visibilitychange', () => { if (document.hidden) soltar(); });
    asa.addEventListener('dblclick', () => { ui.x = 0; ui.y = 0; aplicarPosicion(); guardarUi(); });
    asa.addEventListener('keydown', (e) => {
        const paso = e.shiftKey ? 60 : 20, mueve = { ArrowLeft: [-paso, 0], ArrowRight: [paso, 0], ArrowUp: [0, -paso], ArrowDown: [0, paso] }[e.key];
        if (e.key === 'Home') { ui.x = 0; ui.y = 0; } else if (mueve) { ui.x += mueve[0]; ui.y += mueve[1]; } else return;
        e.preventDefault(); aplicarPosicion(); limitarPosicion(); guardarUi();
    });
    window.addEventListener('resize', limitarPosicion);
    aplicarPosicion(); tarjeta.dataset.modo = ui.modo;

    // ------------------------------------------------------------------ sonido, vibración y voz
    let audio = null;
    const prepararAudio = () => { try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); if (audio.state === 'suspended') audio.resume(); } catch { audio = null; } };
    function pitido(veces) {
        if (!audio || audio.state !== 'running') return;      // el sonido solo suena si una interacción de la persona ya habilitó el audio (si no, queda suspendido y no se fuerza)
        try {
            for (let i = 0; i < veces; i++) {
                const o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime + i * 0.28;
                o.type = 'sine'; o.frequency.value = 880; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
                o.connect(g).connect(audio.destination); o.start(t); o.stop(t + 0.22);
            }
        } catch { /* sin audio */ }
    }
    const vibrar = (patron) => { try { navigator.vibrate && navigator.vibrate(patron); } catch { /* sin vibración */ } };
    const avisarPersona = (texto, { vibra, pitidos } = {}) => { if (vibra) vibrar(vibra); if (pitidos) pitido(pitidos); };
    // ---- Alertas de bajada (4.15.2): vibración, sonido y notificación opcionales; la pantalla SIEMPRE avisa. Nada depende de que existan.
    const soportaVibracion = () => typeof navigator.vibrate === 'function';
    const alertasOn = () => !(S.Ajustes && S.Ajustes.get('alertasBajada') === false);
    const notifSoportada = () => typeof Notification !== 'undefined' && typeof Notification.requestPermission === 'function';
    const permisoNotif = () => (notifSoportada() ? Notification.permission : 'no-soportado');
    const unir = (l) => (l.length < 2 ? l.join('') : l.slice(0, -1).join(', ') + ' y ' + l[l.length - 1]);
    function pintarAlertas() {
        const b = q('viajeAlertas'); if (!b) return;
        const on = alertasOn(), canales = ['pantalla'];
        if (soportaVibracion()) canales.push('vibración');
        if (audio && audio.state === 'running') canales.push('sonido');
        if (permisoNotif() === 'granted') canales.push('notificaciones');
        b.setAttribute('aria-pressed', String(on));
        b.textContent = on ? 'Alertas de bajada: activadas' : 'Alertas de bajada: solo en pantalla';
        let t = on ? 'Te aviso con: ' + unir(canales) + '.' : 'Solo verás el aviso en la pantalla.';
        if (on && permisoNotif() === 'denied') t += ' Las notificaciones están bloqueadas en este navegador.';
        q('viajeAlertasEstado').textContent = t;
        q('viajeActivarAlertas').hidden = !(on && notifSoportada() && Notification.permission === 'default');      // solo se ofrece; el permiso se pide al tocarlo
    }
    /** Vibración, sonido y notificación de una alerta de bajada, solo si la persona no las apagó. Una notificación solo sale con la página oculta y el permiso ya concedido. */
    function avisarBajada({ vibra, pitidos, nivel } = {}) {
        if (!alertasOn() || !sesion) return;
        if (vibra && soportaVibracion()) vibrar(vibra);
        if (pitidos) pitido(pitidos);
        if (nivel && document.hidden && permisoNotif() === 'granted') notificarBajada(nivel);
    }
    function notificarBajada(nivel) {
        const info = sesion.nucleo.info(), parada = nivel === 'atras' ? '' : paradaBajada(info);
        const titulo = nivel === 'atras' ? 'Tu parada quedó atrás' : nivel === 'preparate' ? 'Prepárate para bajar' : 'Tu bajada está aquí';
        // La notificación del desvío NO lleva nombres de lugares, paraderos ni coordenadas: solo qué hacer.
        const cuerpo = nivel === 'atras' ? 'Baja en la próxima parada, cuando el bus se detenga.' : 'Ruta ' + (info.etiqueta || info.codigo) + (parada ? ' · Paradero «' + parada + '»' : '');
        const opciones = { body: cuerpo, tag: 'spevb-bajada-' + nivel + '-' + sesion.id + '-' + info.leg, icon: '/img/marca/sevb-icono-app-128.png', data: { url: '/' } };
        const mostrar = (reg) => { try { if (reg && reg.showNotification) return reg.showNotification(titulo, opciones); const n = new Notification(titulo, opciones); (sesion.notifs = sesion.notifs || []).push(n); } catch { /* sin notificación: la pantalla ya avisó */ } };
        try { if (navigator.serviceWorker && navigator.serviceWorker.getRegistration) navigator.serviceWorker.getRegistration().then(mostrar, () => mostrar(null)); else mostrar(null); } catch { mostrar(null); }
    }
    function cerrarNotificaciones() {
        try { (sesion && sesion.notifs || []).forEach((n) => n.close()); } catch { /* nada */ }
        try { if (navigator.serviceWorker && navigator.serviceWorker.getRegistration) navigator.serviceWorker.getRegistration().then((r) => r && r.getNotifications && r.getNotifications().then((l) => l.filter((n) => (n.tag || '').startsWith('spevb-bajada-')).forEach((n) => n.close()))).catch(() => {}); } catch { /* nada */ }
    }
    const paradaBajada = (info) => { const b = sesion && sesion.plan.buses[Math.min(info.leg || 0, sesion.plan.buses.length - 1)]; return b && b.paraderoBajada ? String(b.paraderoBajada).slice(0, 60) : ''; };
    /** Libera el audio y corta cualquier vibración pendiente (el siguiente viaje crea el suyo). */
    function cerrarAudio() { try { if (audio && audio.close) audio.close(); } catch { /* nada */ } audio = null; try { navigator.vibrate && navigator.vibrate(0); } catch { /* nada */ } cerrarNotificaciones(); }

    // ------------------------------------------------------------------ pantalla encendida
    async function pedirPantalla(forzar = false) {
        const mia = sesion;
        try {
            if (!navigator.wakeLock || !mia) return;
            if (mia.wake) {
                if (!forzar) return;
                try { mia.wake.release(); } catch { /* nada */ }      // al volver a la app se pide uno nuevo (el navegador suele haber soltado el anterior; soltarlo dos veces es inofensivo)
                mia.wake = null;
            }
            const w = await navigator.wakeLock.request('screen');
            if (sesion !== mia) { try { w.release(); } catch { /* nada */ } return; }      // llegó tarde: ese viaje ya terminó (o es otro): no queda ningún candado de pantalla suelto
            mia.wake = w;
            if (w.addEventListener) w.addEventListener('release', () => { if (mia.wake === w) mia.wake = null; });
        } catch { /* opcional */ }
    }
    function soltarPantalla() { try { sesion && sesion.wake && sesion.wake.release(); } catch { /* nada */ } if (sesion) sesion.wake = null; }

    // ------------------------------------------------------------------ mapa
    /** El viaje NO depende del mapa: la capa de dibujo (posición, recorrido) se crea cuando el mapa está disponible y se reintenta sola mientras tanto. */
    function asegurarCapa() {
        if (!sesion || sesion.capa) return !!(sesion && sesion.capa);
        const m = mapa();
        if (!m || typeof m.group !== 'function') return false;
        try { sesion.capa = m.group().addTo(m); } catch { sesion.capa = null; return false; }
        sesion.mapaListo = true;
        asegurarRecorrido();
        if (sesion.ultima && !sesion.marcador) pintarPosicion({ lat: sesion.ultima.lat, lng: sesion.ultima.lng, precision: sesion.ultima.precision || 30 }, { sinSeguir: true });
        return true;
    }
    function crearMarcador(l) {
        const m = mapa(); if (!m || !sesion.capa || sesion.marcador) return;
        sesion.circulo = m.circle([l.lat, l.lng], l.precision, { color: '#1a73e8', weight: 1, fillColor: '#1a73e8', fillOpacity: 0.12, interactive: false }).addTo(sesion.capa);
        sesion.marcador = m.marker([l.lat, l.lng], {
            className: 'viaje-yo-wrapper', size: [50, 36], anchor: [25, 18], z: 1200, keyboard: false, interactive: false,
            // UN solo elemento con las dos formas (se crea una vez): el círculo azul de siempre y un bus de SVG propio; el cambio es solo `data-modo` (transform y opacity).
            html: '<div class="viaje-yo-caja" data-modo="persona"><div class="viaje-yo"></div><div class="viaje-bus-marca" aria-hidden="true"><svg viewBox="0 0 44 30" width="44" height="30" focusable="false"><rect class="bus-cuerpo" x="2" y="2" width="40" height="22" rx="6"/><rect class="bus-ventanas" x="6" y="6" width="32" height="10" rx="3"/><rect class="bus-franja" x="2" y="18" width="40" height="3"/><circle class="bus-rueda" cx="12" cy="25" r="3.6"/><circle class="bus-rueda" cx="32" cy="25" r="3.6"/></svg><b class="viaje-bus-cod" hidden></b></div></div>',
        }).addTo(sesion.capa);
        sesion.marcadorClave = null; sesion.pintada = null;
        pintarMarcadorYo(sesion.nucleo.info());
    }
    /** Círculo azul mientras caminas o esperas; bus (con el código corto de la ruta, si cabe) mientras vas en él. Solo toca el DOM si cambió la fase, el código o el color. */
    function pintarMarcadorYo(info) {
        if (!sesion || !sesion.marcador || !info) return;
        const modo = info.fase === 'en_bus' ? 'bus' : 'persona';
        const cod = modo === 'bus' && info.codigo && String(info.codigo).length <= 5 ? String(info.codigo) : '';
        const color = modo === 'bus' && /^#[0-9a-f]{6}$/i.test(info.color || '') ? info.color : '';
        const clave = modo + '|' + cod + '|' + color;
        if (sesion.marcadorClave === clave) return;
        const el = sesion.marcador.getElement && sesion.marcador.getElement(), caja = el && el.querySelector('.viaje-yo-caja');
        if (!caja) return;      // el elemento aún no existe (el mapa lo monta después): se reintenta con la próxima lectura
        sesion.marcadorClave = clave;
        caja.dataset.modo = modo;
        caja.style.setProperty('--bus-c', color || '#176650');
        const b = caja.querySelector('.viaje-bus-cod'); b.textContent = cod; b.hidden = !cod;
    }
    function pintarPosicion(l, { sinSeguir = false } = {}) {
        if (!asegurarCapa()) return;      // sin mapa: la posición y las indicaciones de la tarjeta siguen; se dibujará cuando el mapa esté listo
        crearMarcador(l);
        if (!sesion.marcador) return;
        const k = l.lat + ',' + l.lng + ',' + Math.round(l.precision);
        if (sesion.pintada !== k) { sesion.pintada = k; sesion.marcador.setPosition([l.lat, l.lng]); sesion.circulo.setPosition([l.lat, l.lng]).setRadius(Math.max(5, l.precision)); }      // sin cambios no se repinta nada
        const m = mapa();
        if (m && m.priorizarCaminata) m.priorizarCaminata([l.lat, l.lng]);      // con un viaje en curso solo se anima la caminata más cercana a la persona
        if (sesion.seguir && m && !sinSeguir) {
            // El zoom mínimo de 16 se impone UNA vez al empezar a seguir (o al reactivar «Seguirme»): después se respeta el zoom que la persona elija con el pellizco.
            const zoom = sesion.zoomSeguimiento ? m.getZoom() : Math.max(m.getZoom(), 16);
            sesion.zoomSeguimiento = true;
            sesion.moviendo = true;
            S.centrarEn(m, [l.lat, l.lng], zoom, { animate: !(S.Motion && S.Motion.reduced) });      // al centro del área LIBRE: nunca debajo de la tarjeta ni del panel
            setTimeout(() => { if (sesion) sesion.moviendo = false; }, 400);
        }
    }
    /** Traspaso de propiedad (4.15): al empezar el viaje el planificador suelta su copia estática del recorrido y la ruta consumible (viaje-ruta.js) dibuja las etapas, los puntos
     *  de subida/bajada y el destino. Sin mapa no se hace nada (el viaje sigue); cuando el mapa aparezca, se dibuja el estado actual (con el progreso ya guardado). */
    function asegurarRecorrido() {
        const m = mapa(); if (!sesion || !m || sesion.ruta || !S.ViajeRuta) return;
        if (typeof m.group !== 'function') return;
        try { if (S.Planner && S.Planner.liberarRecorrido) S.Planner.liberarRecorrido(); } catch { /* sin planificador */ }
        try { sesion.ruta = S.ViajeRuta.crear({ mapa: m, plan: sesion.plan, reducido: () => !!(S.Motion && S.Motion.reduced), estado: sesion.rutaGuardada || null }); } catch { sesion.ruta = null; return; }
        sesion.rutaGuardada = null;
        const i = sesion.nucleo.info(); sesion.ruta.actualizar(sesion.ultima && !sesion.antigua ? sesion.ultima : null, i);
        aplicarCaminataARuta();
    }

    // ------------------------------------------------------------------ pintar la tarjeta
    const fmtDist = (m) => (m === null || m === undefined ? '—' : m < 1000 ? m + ' m' : (m / 1000).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km');
    function pintarInfo(info) {
        const prepararse = info.fase === 'en_bus' && info.alertas && info.alertas.preparate && !info.alertas.ahora;
        q('viajeTitulo').textContent = prepararse ? 'Prepárate para bajar' : info.titulo;
        q('viajeInstruccion').textContent = info.instruccion + (prepararse && paradaBajada(info) ? ' Paradero «' + paradaBajada(info) + '».' : '');
        pintarMarcadorYo(info);
        const incierta = info.estimacion === 'incierta';      // el bus va fuera de su recorrido: ni distancia ni tiempo son fiables
        q('viajeDist').textContent = incierta ? 'Incierta' : fmtDist(info.distancia);
        q('viajeEta').textContent = incierta ? 'Incierta' : info.etaMin === null ? '—' : info.etaMin + ' min';
        q('viajeVel').textContent = info.velKmh === null ? '—' : info.velKmh + ' km/h';
        q('viajePrec').textContent = info.precision === null ? '—' : '±' + info.precision + ' m';
        const pct = Math.round(info.progreso * 100);
        q('viajeBarra').setAttribute('aria-valuenow', String(pct));
        q('viajeBarra').firstElementChild.style.width = pct + '%';
        const chip = q('viajeBus');
        chip.hidden = !info.codigo || info.fase === 'iniciando' || info.fase === 'caminar_final' || info.fase === 'llegaste';
        chip.textContent = info.etiqueta || info.codigo || ''; if (/^#[0-9a-f]{6}$/i.test(info.color || '')) chip.style.setProperty('--viaje-bus', info.color);
        tarjeta.dataset.fase = info.fase;
        tarjeta.classList.toggle('sin-senal', !!info.sinSenal);
        // Confirmación manual (el bus puede ir lento y no alcanzar el umbral del detector): solo en la fase que corresponde y sin pregunta abierta.
        const sinPregunta = !info.pregunta && tarjeta.dataset.fase !== 'reanudar';
        q('viajeYaSubi').hidden = !(sinPregunta && (info.fase === 'caminar' || info.fase === 'esperando') && info.precision !== null);
        q('viajeYaBaje').hidden = !(sinPregunta && info.fase === 'en_bus');
        q('viajeManual').hidden = q('viajeYaSubi').hidden && q('viajeYaBaje').hidden;
        const dato = incierta ? 'Estimación incierta' : info.distancia === null ? '' : fmtDist(info.distancia) + (info.etaMin === null ? '' : ' · ' + info.etaMin + ' min');
        q('viajeMini').textContent = dato; q('viajePastillaDato').textContent = incierta || info.distancia === null ? '' : fmtDist(info.distancia);
        pintarDesvio(info);
    }
    /** El estado del desvío en la tarjeta: la MISMA historia que cuenta el mapa (el conector ámbar sale del mismo estado del núcleo). La línea punteada se explica: une la posición con el
     *  recorrido registrado; no es el camino del bus ni prueba de una obra. */
    function pintarDesvio(info) {
        const d = info.desvio, estado = info.fase === 'en_bus' && d ? d.estado : 'normal', nota = q('viajeDesvioNota');
        if (estado === 'normal') delete tarjeta.dataset.desvio; else tarjeta.dataset.desvio = estado;
        const hayConector = estado === 'posible' || estado === 'confirmado';
        nota.hidden = !hayConector;
        if (hayConector) nota.textContent = 'La línea naranja punteada solo une tu posición con el recorrido registrado: no es el camino que seguirá el bus ni indica una obra.';
    }
    let temporizadorAviso = null;
    function mostrarAviso(texto, { nivel = 'info', ms = 12000 } = {}) {
        const a = q('viajeAviso');
        a.textContent = texto; a.dataset.nivel = nivel; a.hidden = false;
        clearTimeout(temporizadorAviso);
        if (ms) temporizadorAviso = setTimeout(() => { a.hidden = true; sincronizarUrgente(); }, ms);
        sincronizarUrgente();
    }
    const ocultarAviso = () => { clearTimeout(temporizadorAviso); q('viajeAviso').hidden = true; sincronizarUrgente(); };
    // ------------------------------------------------------------------ nivel 3: «Tu bajada está aquí» (recuadro persistente y prioritario; no se oculta por tiempo)
    function mostrarBajada(tipo = 'ahora') {
        if (!sesion) return;
        // UN solo recuadro para los dos avisos (reutiliza su accesibilidad, su foco y el sistema de avisos): solo cambian los textos. Si ya está abierto se actualiza, sin duplicarlo.
        const caja = q('viajeBajada'), info = sesion.nucleo.info(), atras = tipo === 'atras', parada = atras ? '' : paradaBajada(info);
        q('viajeBajadaTitulo').textContent = atras ? 'Tu parada quedó atrás' : 'Tu bajada está aquí';
        q('viajeBajadaTexto').textContent = atras ? 'El bus retomó la ruta después de tu bajada. Baja en la próxima parada, cuando el bus se detenga.' : 'Baja cuando el bus se detenga.';
        q('viajeBajadaParada').textContent = parada ? 'Paradero «' + parada + '»' : ''; q('viajeBajadaParada').hidden = !parada;
        caja.dataset.tipo = tipo;
        if (!caja.hidden) return;
        const previo = document.activeElement;
        sesion.focoPrevio = previo && previo !== document.body && !tarjeta.contains(previo) ? previo : null;      // a dónde devolver el foco al resolver
        caja.hidden = false; tarjeta.dataset.bajada = '1'; sesion.bajadaAbierta = true;
        mostrarCompleta();
        sincronizarUrgente();
        if (!(S.Superficies && S.Superficies.estado().overlay)) { try { q('viajeBajadaYa').focus({ preventScroll: true }); } catch { /* sin foco */ } }      // con un menú o diálogo abierto, la pila de modales.js lo hace
    }
    function ocultarBajada({ devolverFoco = true } = {}) {
        const caja = q('viajeBajada'); if (caja.hidden) return;
        const tenia = tarjeta.contains(document.activeElement), enPila = !!ventanaPregunta;
        caja.hidden = true; delete tarjeta.dataset.bajada; delete caja.dataset.tipo;
        const previo = sesion && sesion.focoPrevio;
        if (sesion) { sesion.bajadaAbierta = false; sesion.focoPrevio = null; }
        sincronizarUrgente();
        if (devolverFoco && tenia && !enPila) {
            if (previo && previo.isConnected && previo.getClientRects().length && !previo.closest('[inert]')) { try { previo.focus({ preventScroll: true }); } catch { /* nada */ } }
            else { const t = q('viajeTitulo'); t.setAttribute('tabindex', '-1'); try { t.focus({ preventScroll: true }); } catch { /* nada */ } }
        }
    }
    /** Las tres alertas de bajada vienen del núcleo (una vez cada una por tramo); aquí solo se PRESENTAN. */
    function alertaBajada(ev) {
        const info = ev.info || sesion.nucleo.info(), clave = info.leg + ':' + ev.nivel;
        if (sesion.avisadas.has(clave)) return;      // cada umbral se notifica una vez por tramo
        sesion.avisadas.add(clave);
        const parada = paradaBajada(info), fiable = info.precision !== null && info.precision <= 60;
        if (ev.nivel === 'cerca') {
            const base = 'Te acercas a tu punto de bajada';
            mostrarAviso(base + (fiable && ev.texto.startsWith(base) ? ev.texto.slice(base.length) : (parada ? ' (paradero «' + parada + '»).' : '.')), { nivel: 'alerta', ms: 20000 });
            avisarBajada({ vibra: [200] });
        } else if (ev.nivel === 'preparate') {
            mostrarCompleta();      // una sola vez: el núcleo emite este nivel una vez por tramo
            mostrarAviso((fiable ? ev.texto : 'Prepárate para bajar.') + (parada ? ' Paradero «' + parada + '».' : ''), { nivel: 'alerta', ms: 20000 });
            avisarBajada({ vibra: [450, 150, 450], pitidos: 2, nivel: 'preparate' });
        } else {
            if (info.desvio && info.desvio.estado === 'atras') return;      // la parada ya quedó atrás: la alerta ordinaria no puede salir por el mismo hecho
            ocultarAviso(); mostrarBajada('ahora');
            avisarBajada({ vibra: [700, 200, 700, 200, 700], pitidos: 3, nivel: 'ahora' });
        }
    }
    /** «Tu parada quedó atrás»: una sola tarjeta prioritaria y persistente (el recuadro de bajada) y UNA alerta urgente por incidente confirmado, con las preferencias de vibración, sonido y
     *  notificación de siempre. Las lecturas siguientes solo actualizan la tarjeta: nunca repiten el aviso. */
    function alertaAtras(ev) {
        const info = ev.info || sesion.nucleo.info(), clave = 'atras:' + info.leg + ':' + (ev.incidente || 0);
        pintarInfo(info);
        if (sesion.avisadas.has(clave)) return;
        sesion.avisadas.add(clave);
        ocultarAviso();
        mostrarBajada('atras');
        avisarBajada({ vibra: [700, 200, 700, 200, 700], pitidos: 3, nivel: 'atras' });
        guardar();
    }
    function mostrarPregunta(id, texto) {
        q('viajePreguntaTexto').textContent = texto;
        q('viajePregunta').dataset.id = id; q('viajePregunta').hidden = false;
        q('viajeSi').textContent = id === 'subida' ? 'Sí, me subí' : 'Sí, ya me bajé';
        q('viajeNo').textContent = id === 'subida' ? 'Todavía no' : 'No, sigo en el bus';
        sincronizarUrgente();
    }
    const ocultarPregunta = () => { q('viajePregunta').hidden = true; delete q('viajePregunta').dataset.id; sincronizarUrgente(); };

    // ------------------------------------------------------------------ eventos del núcleo
    function manejar(eventos) {
        for (const ev of eventos) {
            if (!sesion) return;
            switch (ev.tipo) {
                case 'progreso': pintarPosicion(ev.lectura); pintarInfo(ev.info); if (sesion.ruta) sesion.ruta.actualizar(ev.lectura, ev.info);
                    if (sesion.cam && sesion.cam.estado === 'sin-ubicacion') calcularCaminataReal(sesion.cam);      // llegó una lectura nueva: se reintenta sola, una vez por lectura
                    try { window.dispatchEvent(new CustomEvent('spevb-viaje-lectura', { detail: { fase: ev.info.fase, leg: ev.info.leg, etaMin: ev.info.etaMin, lat: ev.lectura.lat, lng: ev.lectura.lng, precision: ev.lectura.precision } })); } catch { /* sin compartir */ }
                    break;
                case 'fase':
                    pintarInfo(ev.info); ocultarPregunta(); ocultarBajada(); if (sesion.ruta) sesion.ruta.actualizar(null, ev.info);
                    if (ev.desviada) iniciarCaminataReal(ev); else liberarCaminataReal();      // bajó con el bus desviado: la caminata sale de DONDE se bajó, no de la parada del plan
                    if (ev.fase !== 'llegaste' && ev.fase !== 'terminado') { ocultarAviso(); guardar(); }
                    if (ev.texto && !ev.inicial) { mostrarAviso(ev.texto, { nivel: 'ok', ms: 9000 }); }
                    if (ev.inicial && ev.distanciaAOrigen > 1500) {
                        mostrarAviso('Estás a ' + fmtDist(ev.distanciaAOrigen) + ' del punto A. Puedes seguir, o usar «Recalcular desde aquí» para un viaje que parta de donde estás.', { nivel: 'alerta', ms: 20000 });
                    }
                    break;
                case 'pregunta':
                    if (ev.id === 'bajada') ocultarBajada();      // la pregunta de bajada toma el relevo del recuadro
                    mostrarCompleta(); pintarInfo(ev.info); mostrarPregunta(ev.id, ev.texto); avisarPersona(ev.texto, { vibra: [200, 100, 200], pitidos: 1 });
                    break;
                case 'pregunta_retirada': ocultarPregunta(); break;
                case 'alerta': alertaBajada(ev); pintarInfo(ev.info); guardar(); break;
                case 'se_paso': ocultarBajada(); mostrarCompleta(); mostrarAviso(ev.texto, { nivel: 'urgente', ms: 0 }); avisarPersona(ev.texto, { vibra: [500, 200, 500], pitidos: 2 }); break;
                case 'desvio': mostrarAviso(ev.texto, { nivel: 'alerta', ms: 15000 }); avisarPersona(ev.texto, { vibra: [250] }); break;
                // Desvío del bus: la tarjeta cuenta lo mismo que el mapa. Sin sonido ni vibración hasta que la parada quede atrás (único aviso urgente).
                case 'desvio_posible': case 'desvio_confirmado': case 'desvio_largo': pintarInfo(ev.info); if (ev.tipo === 'desvio_confirmado') guardar(); break;
                case 'desvio_fin': pintarInfo(ev.info); if (ev.motivo === 'retomo_antes') mostrarAviso('El bus volvió a su ruta. Seguimos con tu viaje.', { nivel: 'ok', ms: 6000 }); guardar(); break;      // un «posible» que nunca se confirmó se retira sin ruido
                case 'parada_atras': alertaAtras(ev); break;
                case 'senal_debil': mostrarAviso(ev.texto, { nivel: 'info', ms: 15000 }); break;
                // Aviso de señal: informa en la tarjeta (en su modo actual, también la compacta) pero NO la maximiza ni reorganiza la pantalla.
                case 'sin_senal': mostrarAviso(ev.texto, { nivel: 'alerta', ms: 0 }); pintarInfo(ev.info); estadoUbicacion(); break;
                case 'senal_recuperada': mostrarAviso(ev.texto, { nivel: 'ok', ms: 5000 }); break;
                case 'llego': ocultarBajada(); llegada(); break;
                default: break;
            }
        }
    }

    // ------------------------------------------------------------------ celebración de la llegada REAL (Fase E): sello + confeti breve, una sola vez por viaje lógico
    const celebradas = new Set();
    let confetiTimer = null, confetiPendiente = null;
    const movimientoReducido = () => !!(S.Motion && S.Motion.reduced);
    function limpiarConfeti() {
        clearTimeout(confetiTimer); confetiTimer = null;
        const c = q('viajeConfeti'); if (c) c.replaceChildren();
    }
    /** Pocas partículas (transform y opacity), dentro de la franja del encabezado, que se quitan solas al terminar (animationend) o con un temporizador de respaldo. */
    function lanzarConfeti() {
        const c = q('viajeConfeti'); if (!c) return;
        limpiarConfeti();
        let vivas = 14;
        const baja = () => { if (--vivas <= 0) limpiarConfeti(); };
        for (let i = 0; i < 14; i++) { const e = document.createElement('i'); e.style.setProperty('--i', String(i)); e.addEventListener('animationend', baja, { once: true }); c.append(e); }
        confetiTimer = setTimeout(limpiarConfeti, 3200);
    }
    function limpiarLlegada() {
        limpiarConfeti(); confetiPendiente = null;
        const l = q('viajeLlegada'); if (l) { l.hidden = true; delete l.dataset.viaje; }
        const d = q('viajeLlegadaDetalle'); if (d) { d.hidden = true; d.textContent = ''; }
        try { localStorage.removeItem('spevb-llegada'); } catch { /* nada */ }
    }
    function celebrarLlegada(vid) {
        const l = q('viajeLlegada'); l.hidden = false; l.dataset.viaje = vid || '';
        if (vid && celebradas.has(vid)) return;      // el mismo viaje no repite el confeti
        if (vid) { celebradas.add(vid); if (celebradas.size > 30) celebradas.delete(celebradas.values().next().value); }
        try { localStorage.setItem('spevb-llegada', JSON.stringify({ vid: vid || null, t: Date.now() })); } catch { /* nada */ }
        if (movimientoReducido()) return;      // queda el sello estático y el mismo texto
        if (document.visibilityState !== 'visible') { confetiPendiente = vid; return; }      // con la página en segundo plano no se reproduce nada atrasado: se ve UNA vez al volver
        lanzarConfeti();
    }
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState !== 'visible' || !confetiPendiente) return;
        const vid = confetiPendiente; confetiPendiente = null;
        if (sesion && sesion.viajeId === vid && q('viajeTerminar').dataset.llego && !movimientoReducido()) lanzarConfeti();
    });
    /** Detalle secundario cuando se conoce el resultado de los logros («Ganaste: …», racha); no bloquea nada: la llegada y «Cerrar» ya funcionan. */
    window.addEventListener('spevb-logros-resultado', (ev) => {
        const d = ev.detail, el = q('viajeLlegadaDetalle');
        if (!d || !el || !sesion || !q('viajeTerminar').dataset.llego || d.viajeId !== sesion.viajeId) return;
        const partes = [];
        if (d.ganados && d.ganados.length) partes.push('Ganaste: ' + d.ganados.join(', ') + '.');
        if (d.racha) partes.push('Racha de ' + d.racha + (d.racha === 1 ? ' día.' : ' días.'));
        if (!partes.length) return;
        el.textContent = partes.join(' '); el.hidden = false; d.manejado = true;
    });
    // Un resultado guardado de una llegada que no se llegó a ver (página recargada o en segundo plano): se avisa UNA vez, sin confeti y sin sumar nada.
    setTimeout(() => {
        try {
            const g = JSON.parse(localStorage.getItem('spevb-llegada') || 'null'); localStorage.removeItem('spevb-llegada');
            if (g && Date.now() - g.t < 3 * 3600000 && !sesion && S.toast) S.toast('Llegaste a tu destino. Gracias por viajar con SEVB.', { tipo: 'success', ms: 7000, clave: 'llegada' });
        } catch { /* nada */ }
    }, 1500);

    function llegada() {
        ciclo = 'llegada'; escribirBloqueo();      // sigue siendo ESTE viaje hasta que la persona pulse «Cerrar»: no se puede empezar otro
        pintarBotonInicio();
        mostrarCompleta(); if (sesion && sesion.ruta) sesion.ruta.actualizar(null, { fase: 'llegaste' });
        avisarPersona('¡Llegaste a tu destino!', { vibra: [300, 120, 300, 120, 600], pitidos: 3 });
        mostrarAviso('¡Llegaste a tu destino! Gracias por viajar con SEVB.', { nivel: 'ok', ms: 0 });
        q('viajeTerminar').textContent = 'Cerrar';
        q('viajeTerminar').dataset.llego = '1';
        celebrarLlegada(sesion ? sesion.viajeId : null);
        try { window.dispatchEvent(new CustomEvent('spevb-viaje-llegada', { detail: { viajeId: sesion ? sesion.viajeId : null, llegadaMs: Date.now(), subidas: sesion ? (sesion.previas || 0) + sesion.nucleo.subidas() : 0, busConfirmado: !!sesion && ((sesion.previas || 0) + sesion.nucleo.subidas()) > 0, buses: sesion && sesion.plan && sesion.plan.buses ? sesion.plan.buses.length : 1, inicio: sesion ? sesion.inicio : Date.now(), resumen: S.Planner && S.Planner.seleccion ? S.Planner.seleccion.resumen || null : null } })); } catch { /* sin logros */ }
        detenerEscucha();
        borrar();
    }

    // ------------------------------------------------------------------ ubicación: estado visible, vigilancia (señal) y visibilidad
    const hace = (ms) => { const m = Math.max(0, Math.round(ms / 60000)); return m < 1 ? 'hace unos segundos' : m === 1 ? 'hace 1 min' : 'hace ' + m + ' min'; };
    /** Aviso «sin ubicación actual» (distinto de «sin internet» y «mapa incompleto»): dice desde cuándo es la última posición conocida; nunca se presenta como actual. */
    function estadoUbicacion() {
        if (!sesion || !S.MapaSalud) return;
        const sinLectura = sesion.antigua || (performance.now() - sesion.ultimaRecepcion > 20000);
        if (!sinLectura) return S.MapaSalud.poner('ubicacion', null);
        const t = sesion.ultima && sesion.ultima.t;
        S.MapaSalud.poner('ubicacion', { texto: 'Sin ubicación actual.' + (t ? ' Última posición conocida ' + hace(Date.now() - t) + '.' : ' Todavía no tengo una lectura.') });
    }
    function vigilar() {
        if (!sesion) return;
        const ms = performance.now() - sesion.ultimaRecepcion;
        if (!sesion.nucleo.info().precision && sesion.fase0 && ms > 25000 && !sesion.avisoInicial) {
            sesion.avisoInicial = true;
            mostrarAviso('Todavía no consigo tu ubicación. Sal a cielo abierto y revisa que el GPS del teléfono esté activado.', { nivel: 'alerta', ms: 0 });
        }
        manejar(sesion.nucleo.sinSenal(ms));
        estadoUbicacion();
        if (!sesion.capa) asegurarCapa();      // el mapa pudo llegar después: se dibuja ahora (sin tocar el viaje)
    }
    /** Suscribe UNA escucha de GPS. Cada suscripción tiene un número de generación: los callbacks de una escucha vieja (renovada al volver de la pantalla bloqueada) se ignoran. */
    function escucharGps() {
        if (!sesion) return;
        const gen = (sesion.genGps = (sesion.genGps || 0) + 1);
        try { sesion.gps && sesion.gps.detener(); } catch { /* nada */ }
        sesion.gps = null;
        const mia = sesion;
        const vigente = () => !!sesion && sesion === mia && sesion.genGps === gen;      // ni de una escucha vieja ni de OTRO viaje
        sesion.gps = S.Gps.seguir({
            crudas: true, segundoPlano: true,
            onLectura: (l) => {
                if (!vigente()) return;
                const eventos = sesion.nucleo.procesar({ lat: l.lat, lng: l.lng, precision: l.precision, t: l.marcaTiempo, velocidad: l.velocidad });
                // «Recibí un evento del GPS» no es «tengo una posición válida»: las lecturas descartadas (imprecisas, repetidas, saltos) no
                // reinician el reloj de ausencia de señal, para que el seguimiento no parezca sano mientras solo llega ruido.
                if (!eventos.some((e) => e.tipo === 'descartada')) {
                    sesion.ultimaRecepcion = performance.now();
                    sesion.ultima = { lat: l.lat, lng: l.lng, precision: l.precision, t: Date.now() };      // solo la ÚLTIMA posición válida
                    if (sesion.antigua) { sesion.antigua = false; estadoUbicacion(); }      // llegó una lectura actual: la posición guardada deja de ser «antigua»
                }
                renovarSiToca();      // cada lectura de GPS también renueva la concesión entre pestañas (por si el navegador estrangula los temporizadores)
                manejar(eventos);
            },
            onAviso: () => { if (vigente()) mostrarAviso('El GPS no responde por ahora; sigo intentando.', { nivel: 'info', ms: 6000 }); },
            onError: (e) => { if (vigente()) mostrarAviso(e.message + (e.ayuda ? ' ' + e.ayuda : ''), { nivel: 'urgente', ms: 0 }); },
        });
    }
    /** Volver a la app (pantalla bloqueada, otra app, página restaurada): el navegador puede haber pausado el GPS sin avisar. Se renueva la escucha UNA vez (sin duplicarla),
     *  se vuelve a pedir la pantalla encendida y se marca la última posición como antigua hasta recibir una lectura nueva. */
    function alVolver(motivo) {
        if (!sesion) return;
        const fuera = sesion.oculto ? performance.now() - sesion.oculto : 0;
        sesion.oculto = null;
        pedirPantalla(true);
        if (motivo === 'pageshow' || fuera > 15000) {
            sesion.ultimaRecepcion = performance.now();      // margen antes de declarar «sin señal»: el GPS pudo pausarse
            sesion.antigua = true; estadoUbicacion();
            escucharGps();                                   // renueva la escucha (la anterior queda invalidada por su generación)
            if (fuera > 15000) mostrarAviso('Volviste a la app. Estoy verificando tu posición: si el teléfono se bloqueó, el GPS pudo pausarse.', { nivel: 'info', ms: 10000 });
        }
        asegurarCapa();
    }
    function alVisibilidad() {
        if (!sesion) return;
        if (document.hidden) { sesion.oculto = performance.now(); guardar(); return; }      // al ocultar la página se guarda el avance
        if (!verificarPosesion()) return;      // mientras estuvo oculta, otra pestaña pudo tomar la concesión
        alVolver('visible');
    }
    const alOcultarPagina = (e) => {
        if (sesion) guardar();
        // Una descarga REAL de la página (cerrar o recargar; no bfcache) suelta la concesión: el avance ya quedó guardado y otra pestaña (o esta misma al recargar) puede ofrecer reanudarlo.
        // Si la página va a la memoria (persisted) o el evento no es real, la concesión se conserva y vence sola si no vuelve.
        if (e && e.isTrusted && !e.persisted && nonce) { if (poseo()) soltarBloqueo(); else nonce = null; }
    };
    const alMostrarPagina = (e) => { if (e.persisted) { if (!verificarPosesion()) return; alVolver('pageshow'); } };      // página restaurada desde la memoria (bfcache): ¿sigue siendo la propietaria?
    window.addEventListener('pagehide', alOcultarPagina);
    window.addEventListener('pageshow', alMostrarPagina);
    document.addEventListener('resume', () => { verificarPosesion(); });      // una pestaña congelada que se reanuda comprueba de inmediato si perdió la concesión
    window.addEventListener('focus', () => { verificarPosesion(); });

    // ------------------------------------------------------------------ iniciar / terminar
    function detenerEscucha() {
        if (!sesion) return;
        try { sesion.gps && sesion.gps.detener(); } catch { /* nada */ }
        sesion.gps = null;
        clearInterval(sesion.timer); clearInterval(sesion.timerGuardado);
        soltarPantalla();
        document.removeEventListener('visibilitychange', alVisibilidad);
        sesion.genGps = (sesion.genGps || 0) + 1;      // invalida cualquier callback pendiente de la escucha anterior
    }

    async function iniciar(planGuardado, estado, opciones = {}) {
        // ÚNICA puerta de entrada (botón del planificador, flujo guiado, atajos): nada empieza si ya hay un viaje, una llegada sin cerrar, uno guardado esperando «Reanudar viaje» o uno abierto
        // en otra pestaña. «Reanudar» y el recálculo pasan con `interno`: la persona ya lo decidió con una pregunta explícita.
        if (!opciones.interno) {
            if (ciclo === 'preparando') return false;      // doble toque: ya se está preparando UN viaje; no se crea otra sesión
            if (ciclo !== 'libre' || bloqueoAjeno()) { mostrarConflicto(); return false; }
        }
        const volverA = opciones.volverA || 'libre', mio = ++intento;
        ciclo = 'preparando'; pintarBotonInicio();      // el doble toque queda bloqueado de inmediato (síncrono); la concesión entre pestañas se toma justo después, ANTES de cualquier otra espera
        const abortar = () => { if (mio === intento) { ciclo = volverA; if (volverA === 'libre') soltarBloqueo(); pintarBotonInicio(); } return false; };
        const concesion = await adquirir();
        if (mio !== intento || ciclo !== 'preparando') { if (concesion.ok && !sesion && ciclo === 'libre') soltarBloqueo(); return false; }      // se canceló mientras se tomaba la concesión
        if (!concesion.ok) { abortar(); mostrarConflicto(); vigilarVencimiento(); return false; }      // otra pestaña es propietaria (vigente): no se empieza nada
        const sel = S.Planner && S.Planner.seleccion;
        const plan = planGuardado || (sel && sel.viaje ? redondear(sel.viaje) : null);
        if (!plan) { S.toast('Primero calcula un viaje y elige una opción.', { tipo: 'info', ms: 4000 }); return abortar(); }
        const prob = S.Gps.problema();
        if (prob) { S.toast(prob.message + (prob.ayuda ? ' ' + prob.ayuda : ''), { tipo: 'error', ms: 12000, clave: 'viaje' }); return abortar(); }
        if ((await S.Gps.permiso()) === 'denied') { const e = S.Gps.errorGps({ code: 1 }); S.toast(e.message + ' ' + e.ayuda, { tipo: 'error', ms: 14000, clave: 'viaje' }); return abortar(); }
        if (mio !== intento || ciclo !== 'preparando') return false;      // se canceló (terminar, volver al inicio) mientras se pedía el permiso: la promesa tardía no crea nada
        if (!poseo()) { abortar(); mostrarConflicto(); return false; }      // la concesión se perdió durante la espera (otra pestaña la tomó al vencer): no se crea nada
        let nucleo;
        try { nucleo = N.crearViaje(plan); } catch (e) { S.toast(e.message, { tipo: 'error', ms: 6000, clave: 'viaje' }); return abortar(); }
        if (estado) nucleo.restaurar(estado);
        // El viaje NO depende del mapa (Google puede tardar o fallar): arranca igual y la capa de dibujo se crea cuando el mapa está disponible.
        // Un viaje reanudado conserva la hora ORIGINAL de inicio y su última posición, que se marca como antigua hasta recibir una lectura nueva.
        const reanudado = !!opciones.reanudado;
        sesion = { id: opciones.id || nuevoId(), viajeId: opciones.viajeId || opciones.id || nuevoId(), previas: opciones.previas || 0, plan, nucleo, capa: null, seguir: true, inicio: opciones.inicio || Date.now(), ultimaRecepcion: performance.now(), fase0: true, wake: null,
                   ultima: opciones.ultima || null, antigua: reanudado, genGps: 0, rutaGuardada: opciones.ruta || null, ruta: null, avisadas: new Set(), marcadorClave: null, pintada: null,
                   refs: {}, cam: null, camSeq: 0, camGuardada: opciones.cam || null };
        ciclo = 'activo'; contadores.creadas++; escribirBloqueo(); iniciarLatido(); pintarBotonInicio();
        asegurarCapa();
        prepararAudio();
        try { window.SpevbExplorer.bus.suspender(true); } catch { /* sin explorador */ }      // el bus de demostración se pausa: compite con tu posición real y gasta batería
        document.body.classList.add('viaje-activo');
        if (S.Superficies) S.Superficies.viajeIniciado();      // la tarjeta pasa a ser la superficie principal; el planificador cede (sin perder A/B)
        const alerta = $('alightAlert');
        if (alerta) { if (alerta.getAttribute('aria-pressed') === 'true') alerta.click(); alerta.disabled = true; alerta.title = 'El modo viaje ya te avisa antes de bajar.'; }
        tarjeta.dataset.fase = 'iniciando';
        ponerModo(ui.modo === 'oculta' ? 'compacta' : ui.modo, { recordar: false });      // un viaje nuevo siempre empieza con la tarjeta a la vista
        q('viajeMasPanel').hidden = true; q('viajeMas').setAttribute('aria-expanded', 'false'); q('viajeMas').textContent = 'Más';
        q('viajeTerminar').textContent = 'Terminar viaje'; delete q('viajeTerminar').dataset.llego;
        q('viajeSeguir').setAttribute('aria-pressed', 'true');
        ocultarAviso(); ocultarPregunta(); ocultarBajada({ devolverFoco: false }); pintarInfo(nucleo.info()); pintarAlertas();
        if (opciones.bajada && nucleo.info().fase === 'en_bus') mostrarBajada(nucleo.info().desvio.estado === 'atras' ? 'atras' : 'ahora');      // viaje reanudado con el recuadro abierto: vuelve a mostrarse (sin repetir vibración ni sonido)
        window.dispatchEvent(new CustomEvent('spevb-focus-map'));          // el panel baja para dejar ver el mapa
        asegurarRecorrido();
        restaurarCaminataReal();
        cargarReferencias();      // en segundo plano: el viaje ya empezó y NO espera al detalle de la ruta
        escucharGps();
        sesion.timer = setInterval(vigilar, 3000);
        sesion.timerGuardado = setInterval(guardar, 15000);      // el avance se guarda cada 15 s (y al ocultar la página): una recarga o un cierre del navegador no lo pierden
        document.addEventListener('visibilitychange', alVisibilidad);
        pedirPantalla();
        guardar();
        estadoUbicacion();
        window.dispatchEvent(new CustomEvent('spevb-viaje-modo', { detail: { activo: true } }));
        return true;
    }

    /** ÚNICO procedimiento de cierre (terminar, cerrar la llegada, volver al inicio, recálculo): idempotente. Libera el GPS, intervalos y temporizadores, Wake Lock, audio y vibración,
     *  capas y marcadores, la ruta consumible, lo compartido (y su token de escritura), las clases de modo viaje, lo guardado y el bloqueo entre pestañas. Cancela también un inicio en preparación. */
    function finalizar({ borrarEstado = true, conservarBloqueo = false, perdido = false } = {}) {
        intento++;      // cualquier inicio que esté esperando (permiso de GPS, etc.) queda cancelado: su promesa tardía no crea nada
        if (recalculo) { try { recalculo.cancelado = true; recalculo.abort.abort(); } catch { /* nada */ } reposoRecalculo(); }
        clearTimeout(confirmarFin); confirmarFin = null;
        if (!sesion) {
            if (ciclo === 'preparando' || ciclo === 'llegada') { ciclo = conservarBloqueo ? 'preparando' : 'libre'; if (!conservarBloqueo) soltarBloqueo(); }
            pintarBotonInicio();
            return;
        }
        detenerEscucha();
        clearTimeout(temporizadorAviso);
        liberarReferencias(); liberarCaminataReal();
        ocultarBajada({ devolverFoco: false });
        cerrarAudio();      // audio, vibración pendiente y notificaciones de este viaje
        try { sesion.capa && sesion.capa.remove(); } catch { /* nada */ }
        if (S.MapaSalud) { S.MapaSalud.poner('ubicacion', null); }
        try { sesion.ruta && sesion.ruta.destruir(); } catch { /* nada */ }
        { const mm = mapa(); if (mm && mm.priorizarCaminata) mm.priorizarCaminata(null); }
        if (perdido) { try { S.Compartir && S.Compartir.soltarLocal && S.Compartir.soltarLocal(); } catch { /* nada */ } }      // el enlace compartido y su token pertenecen ahora a la pestaña propietaria: aquí solo se detiene
        else liberarCompartir();      // enlace compartido, temporizador de envíos y token de escritura guardado
        sesion = null;
        limpiarLlegada();
        contadores.liberadas++;
        if (borrarEstado) borrar();
        document.body.classList.remove('viaje-activo');
        try { window.SpevbExplorer.bus.suspender(false); } catch { /* sin explorador */ }
        tarjeta.hidden = true; pastilla.hidden = true; delete tarjeta.dataset.urgente; delete tarjeta.dataset.forzada; pastilla.classList.remove('con-aviso');
        q('viajeTerminar').textContent = 'Terminar viaje'; delete q('viajeTerminar').dataset.llego;
        ocultarAviso(); ocultarPregunta();
        sincronizarVentanaPregunta();
        if (S.Superficies) S.Superficies.viajeTerminado();
        const alerta = $('alightAlert'); if (alerta) { alerta.disabled = false; alerta.title = ''; }
        ciclo = conservarBloqueo ? 'preparando' : 'libre';
        if (!conservarBloqueo) soltarBloqueo();
        pintarBotonInicio();
        window.dispatchEvent(new CustomEvent('spevb-viaje-modo', { detail: { activo: false } }));
    }

    // ------------------------------------------------------------------ referencia del recorrido DESPUÉS de la bajada (Fase A)
    // El plan trae solo el tramo del pasajero (termina en la bajada). Para saber si el bus retomó la ruta DESPUÉS de la parada hace falta la geometría completa del recorrido, en el sentido correcto.
    // Se pide UNA vez por bus (no con cada lectura del GPS), de forma acotada (tiempo máximo y 3 intentos espaciados) y cancelable (terminar el viaje o cambiar de pestaña la aborta), y el viaje NO la espera.
    // Se verifica por id, código, sentido y versión cuando existen, y por geometría: el tramo debe ser una parte contigua del recorrido. Si no coincide o es ambigua, queda sin referencia (incertidumbre).
    const REF_TIEMPO_MS = 9000, REF_REINTENTO_MS = 25000, REF_INTENTOS_MAX = 3;
    function cargarReferencias() { if (sesion) sesion.plan.buses.forEach((_, leg) => cargarReferencia(leg)); }
    async function cargarReferencia(leg) {
        const s = sesion, bus = s && s.plan.buses[leg];
        if (!s || !bus || !N.construirReferencia) return;
        const r = s.refs[leg] || (s.refs[leg] = { estado: 'pendiente', intentos: 0, abort: null, timer: null });
        if (r.estado === 'cargando' || r.estado === 'lista' || r.estado === 'definitiva') return;
        r.estado = 'cargando'; r.intentos++; r.abort = new AbortController();
        s.nucleo.marcarReferencia(leg, 'cargando');
        const vivo = () => sesion === s && s.refs[leg] === r && !!r.abort && !r.abort.signal.aborted;
        let veredicto = null;
        try {
            let id = bus.rutaId;
            if (!id) {      // plan guardado por una versión anterior: se resuelve el código (también un código anterior, alias)
                const c = await S.api('/api/rutas/codigo/' + encodeURIComponent(bus.codigo), { signal: r.abort.signal, timeout: REF_TIEMPO_MS });
                if (!vivo()) return;
                if (!c || !c.id) throw Object.assign(new Error('sin id'), { definitivo: 'sin-ruta' });
                id = c.id;
            }
            const d = await S.api('/api/rutas/' + encodeURIComponent(id), { signal: r.abort.signal, timeout: REF_TIEMPO_MS });
            if (!vivo()) return;
            veredicto = verificarDetalle(bus, id, d);
        } catch (err) {
            if (!vivo()) return;      // cancelada o de otro viaje: no toca nada
            if (err && err.definitivo) veredicto = { ok: false, motivo: err.definitivo };
            else if (err && err.status === 404) veredicto = { ok: false, motivo: 'sin-ruta' };
            else {
                r.estado = 'error'; s.nucleo.marcarReferencia(leg, err && err.offline ? 'sin-red' : 'sin-detalle');
                if (r.intentos < REF_INTENTOS_MAX) r.timer = setTimeout(() => { if (sesion === s && s.refs[leg] === r) { r.estado = 'pendiente'; cargarReferencia(leg); } }, REF_REINTENTO_MS);
                return;
            }
        }
        r.abort = null;
        s.nucleo.ponerReferencia(leg, veredicto);
        r.estado = veredicto.ok ? 'lista' : 'definitiva'; r.motivo = veredicto.ok ? null : veredicto.motivo;
        if (!veredicto.ok) s.nucleo.marcarReferencia(leg, veredicto.motivo);
        if (s.ruta) s.ruta.actualizar(null, s.nucleo.info());
    }
    /** El detalle de la ruta corresponde a ESTE bus y a ESTE tramo: mismo id, mismo código (o un código anterior de la misma ruta), mismo sentido y misma versión, y el tramo está contenido en el recorrido. */
    function verificarDetalle(bus, id, d) {
        if (!d || typeof d !== 'object') return { ok: false, motivo: 'sin-datos' };
        if (bus.rutaId && Number(d.id) !== Number(bus.rutaId)) return { ok: false, motivo: 'otra-ruta' };
        if (!bus.rutaId && Number(d.id) !== Number(id)) return { ok: false, motivo: 'otra-ruta' };
        if (bus.sentidoRuta && d.sentido && d.sentido !== bus.sentidoRuta) return { ok: false, motivo: 'sentido' };
        if (bus.rutaVersion !== undefined && bus.rutaVersion !== null && d.version !== undefined && Number(d.version) !== Number(bus.rutaVersion)) return { ok: false, motivo: 'version' };
        const rec = d.recorrido && d.recorrido.type === 'LineString' ? d.recorrido.coordinates : null;
        if (!rec) return { ok: false, motivo: 'sin-datos' };
        return N.construirReferencia(bus.tramo, rec, { sentidoRuta: d.sentido || bus.sentidoRuta, sentidoViaje: bus.sentidoViaje || undefined });
    }
    function liberarReferencias() {
        if (!sesion) return;
        Object.values(sesion.refs || {}).forEach((r) => { clearTimeout(r.timer); try { r.abort && r.abort.abort(); } catch { /* nada */ } r.abort = null; r.timer = null; });
    }

    // ------------------------------------------------------------------ caminata desde la bajada REAL (Fase A)
    // Si la persona confirma «Ya me bajé» con el bus desviado (o con la parada atrás), NO se bajó donde decía el plan: la caminata sale de su ubicación real, vigente y de calidad suficiente, y conserva el
    // destino original. Mientras no haya un camino peatonal válido el mapa NO dibuja nada que lleve a la parada vieja ni una recta como si se pudiera cruzar. Usa /api/caminata (la misma de siempre).
    const camClave = (cam) => (cam.tipo === 'final' ? 'final' : 'subida');
    const camHasta = (s, cam) => (cam.tipo === 'final' ? s.plan.destino : s.plan.buses[Math.min(cam.leg, s.plan.buses.length - 1)].subida);
    const redondeaCoords = (c) => (Array.isArray(c) ? c.map((p) => [Math.round(p[0] * 1e6) / 1e6, Math.round(p[1] * 1e6) / 1e6]) : null);
    function camGuardable() {
        const cam = sesion && sesion.cam;
        if (!cam) return null;
        return { tipo: cam.tipo, leg: cam.leg, estado: cam.estado === 'lista' ? 'lista' : 'pendiente', desde: cam.desde || null, hasta: cam.hasta || null, coords: cam.estado === 'lista' ? redondeaCoords(cam.coords) : null, metros: cam.metros || null, minutos: cam.minutos || null };
    }
    function iniciarCaminataReal(ev) {
        const s = sesion; if (!s) return;
        liberarCaminataReal();
        const tipo = ev.transbordo ? 'subida' : 'final', cam = s.cam = { id: ++s.camSeq, tipo, leg: ev.leg, estado: 'pendiente', intentos: 0, abort: null, coords: null, metros: null, minutos: null, desde: null, hasta: null, recalculando: false };
        cam.hasta = { lat: camHasta(s, cam).lat, lng: camHasta(s, cam).lng };
        aplicarCaminataARuta();      // la caminata del plan sale de la parada ORIGINAL: se oculta hasta tener la nueva
        calcularCaminataReal(cam);
    }
    /** Una ubicación REAL: de esta sesión, de hace menos de UBICACION_VIGENTE_MS, con precisión suficiente y no la «antigua» de un viaje reanudado. */
    function ubicacionVigente() {
        const s = sesion, f = s && s.nucleo.filtro; if (!s || !f || f.lat === null || s.antigua) return null;
        if (performance.now() - s.ultimaRecepcion > N.CFG.UBICACION_VIGENTE_MS) return null;
        const i = s.nucleo.info(); if (i.precision === null || i.precision > N.CFG.UBICACION_PRECISION_MAX) return null;
        return { lat: f.lat, lng: f.lng };
    }
    async function calcularCaminataReal(cam) {
        const s = sesion; if (!s || s.cam !== cam || cam.estado === 'calculando' || cam.estado === 'lista') return;
        const yo = ubicacionVigente();
        if (!yo) { cam.estado = 'sin-ubicacion'; pintarCaminata(cam); return; }
        cam.estado = 'calculando'; cam.intentos++; cam.desde = yo; cam.abort = new AbortController(); pintarCaminata(cam);
        const q2 = new URLSearchParams({ olat: yo.lat, olng: yo.lng, dlat: cam.hasta.lat, dlng: cam.hasta.lng });
        let data = null, fallo = 'error';
        try { data = await S.api('/api/caminata?' + q2, { signal: cam.abort.signal, timeout: 12000 }); }
        catch (err) { fallo = err && err.name === 'AbortError' ? 'cancelado' : err && err.offline ? 'sin-internet' : err && err.timeout ? 'lento' : 'error'; }
        if (sesion !== s || s.cam !== cam || (cam.abort && cam.abort.signal.aborted)) return;      // respuesta tardía: este cálculo ya no es el vigente (otro viaje, otra bajada, o terminó)
        cam.abort = null;
        const ok = data && Array.isArray(data.coordinates) && data.coordinates.length > 1 && Number.isFinite(Number(data.metros)) && Number(data.metros) >= 0;
        if (!ok) { cam.estado = 'error'; cam.fallo = fallo; pintarCaminata(cam); return; }
        const metros = Math.round(Number(data.metros)), minutos = Math.max(1, Math.round(Number(data.minutos) || metros / 80));
        const maxM = cam.tipo === 'final' ? N.CFG.CAMINATA_FINAL_MAX_M : N.CFG.CAMINATA_TRANSBORDO_MAX_M, maxMin = cam.tipo === 'final' ? N.CFG.CAMINATA_FINAL_MAX_MIN : N.CFG.CAMINATA_TRANSBORDO_MAX_MIN;
        cam.metros = metros; cam.minutos = minutos; cam.minDato = Number.isFinite(Number(data.minutos)) && Number(data.minutos) > 0;      // los minutos se muestran solo si el cálculo los devolvió
        if (metros > maxM || minutos > maxMin) {
            cam.estado = cam.tipo === 'final' ? 'larga' : 'no-alcanzable'; pintarCaminata(cam);
            if (cam.tipo === 'subida' && !cam.recalculando) { cam.recalculando = true; recalcular(); }      // el transbordo ya no sirve: se busca otra recomendación hasta el destino original (con la confirmación de siempre)
            return;
        }
        cam.coords = data.coordinates; cam.estado = 'lista';
        aplicarCaminataARuta();
        pintarCaminata(cam); guardar();
    }
    // Tarjeta de recuperación tras «Ya me bajé»: una instrucción principal (título) y una línea de apoyo. El destino es el del VIAJE activo (sesion.plan), no el de A/B.
    // El plan solo guarda las coordenadas del destino (no su nombre): se dice «tu destino». Sin coordenadas crudas y sin consultas extra para nombrar el punto.
    const busSiguiente = (cam) => { const s = sesion, b = s && s.plan && s.plan.buses && s.plan.buses[Math.min(cam.leg, s.plan.buses.length - 1)]; return b ? { ruta: b.etiqueta || b.codigo || null, paradero: b.paraderoSubida || null } : null; };
    const hasta = (cam) => (cam.tipo === 'final' ? 'hasta tu destino' : 'hasta donde tomas el siguiente bus');
    const TEXTOS_CAMINATA = {
        'sin-ubicacion': () => ['Esperando tu ubicación actual', 'Tu destino se conserva. Cuando tengamos una ubicación reciente, podemos calcular desde donde te bajaste.'],
        calculando: (cam) => ['Buscando cómo seguir', 'Desde donde te bajaste ' + hasta(cam) + '.'],
        error: (cam) => ['Tu destino se mantiene', (cam.fallo === 'sin-internet' ? 'Sin internet: no pude calcular la caminata.' : cam.fallo === 'lento' ? 'La conexión está muy lenta: no pude calcular la caminata.' : 'No pude calcular un camino a pie desde donde te bajaste.') + ' Puedes reintentar o recalcular el viaje desde aquí.'],
        larga: (cam) => ['El destino queda lejos a pie', 'Desde donde te bajaste son ' + fmtDist(cam.metros) + ' a pie hasta tu destino. Puedes recalcular desde aquí para buscar otra forma de llegar.'],
        'no-alcanzable': (cam) => ['El siguiente bus queda lejos a pie', fmtDist(cam.metros) + ' a pie hasta ese bus. Busco otra forma de llegar a tu destino.'],
        lista: (cam) => {
            const min = cam.minDato && cam.minutos ? ' · ' + cam.minutos + ' min' : '';
            if (cam.tipo === 'final') return ['Sigue a pie', 'Camina unos ' + fmtDist(cam.metros) + ' hasta tu destino' + min + '.'];
            const b = busSiguiente(cam);
            return ['Camina hasta el siguiente bus', 'Camina unos ' + fmtDist(cam.metros) + (b && b.paradero ? ' hasta ' + b.paradero : ' hasta donde tomas el siguiente bus') + min + (b && b.ruta ? '. Ahí tomas la ruta ' + b.ruta + '.' : '.')];
        },
    };
    let firmaCaminata = '';
    function pintarCaminata(cam) {
        const caja = q('viajeCaminata'); if (!caja) return;
        if (!cam || !sesion) { caja.hidden = true; delete caja.dataset.estado; firmaCaminata = ''; return; }
        const [titulo, detalle] = (TEXTOS_CAMINATA[cam.estado] || TEXTOS_CAMINATA.error)(cam);
        const firma = cam.estado + '|' + titulo + '|' + detalle;
        caja.hidden = false; caja.dataset.estado = cam.estado;
        if (firma !== firmaCaminata) {      // el texto solo se toca (y se anuncia) cuando de verdad cambió: una lectura GPS más no repite el aviso ni mueve el foco
            firmaCaminata = firma;
            q('viajeCaminataTitulo').textContent = titulo; q('viajeCaminataTexto').textContent = detalle;
        }
        q('viajeCaminataReintentar').hidden = !(cam.estado === 'error' || cam.estado === 'sin-ubicacion');
        q('viajeCaminataRecalcular').hidden = !(cam.estado === 'error' || cam.estado === 'larga');
    }
    /** Cancela el cálculo en curso (una respuesta tardía ya no cambia nada) y limpia el bloque. */
    function liberarCaminataReal() {
        const s = sesion;
        if (s && s.cam) { try { s.cam.abort && s.cam.abort.abort(); } catch { /* nada */ } s.cam = null; }
        if (s) s.camGuardada = null;
        const caja = q('viajeCaminata'); if (caja) { caja.hidden = true; delete caja.dataset.estado; }
        firmaCaminata = '';
    }
    /** Pone en el mapa lo que corresponde al estado de la caminata: nada mientras se calcula (o falla) y el camino peatonal nuevo cuando está listo. */
    function aplicarCaminataARuta() {
        const s = sesion, cam = s && s.cam; if (!s || !s.ruta || !cam) return;
        const i = s.nucleo.info();
        if (cam.estado === 'lista' && cam.coords) s.ruta.caminataReal(i, { estado: 'lista', coords: cam.coords, desde: cam.desde, hasta: cam.hasta });
        else s.ruta.caminataReal(i, { estado: 'calculando' });
    }
    /** Al reanudar: una caminata nueva ya calculada se vuelve a dibujar; una que quedó a medias se reintenta cuando llegue una lectura actual (la ubicación guardada es antigua). */
    function restaurarCaminataReal() {
        const s = sesion, g = s && s.camGuardada; if (!s || !g) return;
        s.camGuardada = null;
        const i = s.nucleo.info();
        if (!['caminar_final', 'caminar'].includes(i.fase) || !g.hasta || (g.tipo === 'final') !== (i.fase === 'caminar_final')) return;
        s.cam = { id: ++s.camSeq, tipo: g.tipo, leg: g.leg, estado: 'pendiente', intentos: 0, abort: null, coords: null, metros: g.metros, minutos: g.minutos, desde: g.desde, hasta: g.hasta, recalculando: false };
        if (g.estado === 'lista' && Array.isArray(g.coords) && g.coords.length > 1 && g.desde) {
            s.cam.estado = 'lista'; s.cam.coords = g.coords;
            aplicarCaminataARuta(); pintarCaminata(s.cam);
        } else { aplicarCaminataARuta(); calcularCaminataReal(s.cam); }
    }

    // ------------------------------------------------------------------ recálculo SEGURO
    // «Recalcular desde aquí» NUNCA borra el viaje actual antes de tener otro recorrido utilizable. Con el servidor caído, sin internet, con la búsqueda cancelada o sin opciones,
    // el viaje sigue exactamente como estaba. Usa el destino GUARDADO del viaje (no los campos del planificador, que pueden estar vacíos tras una reanudación).
    let recalculo = null;
    const MENSAJES_RECALCULO = {
        'sin-internet': 'Sin internet: no pude calcular un recorrido nuevo.', lento: 'La conexión está muy lenta: no pude calcular un recorrido nuevo.',
        error: 'El servidor no pudo calcular un recorrido ahora.', 'sin-opciones': 'No encontré otro recorrido utilizable desde donde estás.',
    };
    async function recorridoNuevo(origen, destino, signal) {
        if (!S.Planner || !S.Planner.viajeDe) throw new Error('El planificador todavía no está listo.');
        const data = await S.api('/api/viajes/planificar', { method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ origen, destino, soloValidadas: false }) });
        const A = { lat: origen.lat, lng: origen.lng }, B = { lat: destino.lat, lng: destino.lng };
        const op = (data.opciones || [])[0] || (data.alternativas || [])[0];
        if (op && op.puntoSubida && op.puntoBajada && op.tramo) return redondear(S.Planner.viajeDe(A, B, [op]));
        const t = (data.transbordos || [])[0];
        if (t && t.primerBus && t.segundoBus) return redondear(S.Planner.viajeDe(A, B, [t.primerBus, t.segundoBus]));
        return null;
    }
    function reposoRecalculo() { recalculo = null; q('viajeRecalcular').textContent = 'Recalcular desde aquí'; }
    async function recalcular() {
        if (!sesion) return;
        if (recalculo) {      // segundo toque = cancelar el cálculo; el viaje no cambió nada
            recalculo.cancelado = true; recalculo.abort.abort(); reposoRecalculo();
            return mostrarAviso('Cálculo cancelado. Tu viaje sigue como estaba.', { nivel: 'info', ms: 6000 });
        }
        const f = sesion.nucleo.filtro;
        const actual = f && f.lat !== null && !sesion.antigua && performance.now() - sesion.ultimaRecepcion < 30000;
        if (!actual) return mostrarAviso('Todavía no tengo tu ubicación actual para recalcular. Tu viaje sigue como estaba.', { nivel: 'info', ms: 7000 });
        const origen = { lat: f.lat, lng: f.lng }, destino = { lat: sesion.plan.destino.lat, lng: sesion.plan.destino.lng };
        const yo = recalculo = { abort: new AbortController(), cancelado: false };
        q('viajeRecalcular').textContent = 'Cancelar el cálculo';
        mostrarAviso('Calculando un recorrido nuevo desde donde estás… tu viaje actual sigue activo.', { nivel: 'info', ms: 0 });
        let nuevo = null, motivo = 'sin-opciones';
        try { nuevo = await recorridoNuevo(origen, destino, yo.abort.signal); }
        catch (err) { motivo = err && err.name === 'AbortError' ? 'cancelado' : err && err.offline ? 'sin-internet' : err && err.timeout ? 'lento' : 'error'; }
        if (recalculo !== yo || yo.cancelado || !sesion) return;      // otra cosa lo superó (cancelación, fin del viaje)
        reposoRecalculo();
        if (!nuevo) return mostrarAviso((MENSAJES_RECALCULO[motivo] || MENSAJES_RECALCULO['sin-opciones']) + ' Tu viaje sigue como estaba.', { nivel: 'alerta', ms: 12000 });
        // Hay un recorrido utilizable: se ofrece cambiar con UNA pregunta. Nada se borra hasta que la persona acepta.
        sesion.propuesta = nuevo;
        ocultarAviso();
        const bus = nuevo.buses && nuevo.buses[0];
        const rutas = (nuevo.buses || []).map((b) => b.etiqueta || b.codigo).filter(Boolean);
        mostrarPregunta('recalculo', 'Encontré otra forma de llegar' + (rutas.length ? ': ' + (rutas.length > 1 ? 'rutas ' + rutas.join(' y luego ') : 'ruta ' + rutas[0]) : '') + '. ¿Quieres cambiar a ella?');
        q('viajeSi').textContent = 'Sí, cambiar'; q('viajeNo').textContent = 'No, seguir con el actual';
        mostrarCompleta();
    }
    async function aceptarRecalculo() {
        if (!sesion || !sesion.propuesta) return;
        const nuevo = sesion.propuesta;
        const respaldo = { viajeId: sesion.viajeId, previas: sesion.previas || 0, plan: sesion.plan, estado: sesion.nucleo.serializar(), inicio: sesion.inicio, ultima: sesion.ultima, ruta: sesion.ruta ? sesion.ruta.serializar() : (sesion.rutaGuardada || null) };
        ocultarPregunta();
        finalizar({ borrarEstado: false, conservarBloqueo: true });      // suelta GPS, capa y temporizadores del viaje viejo SIN borrar su estado guardado ni soltar el bloqueo
        // El viaje sigue siendo EL MISMO para los logros: conserva su identificador lógico y las subidas ya confirmadas (con el recorrido nuevo se confirmarán las que falten).
        const ok = await iniciar(nuevo, undefined, { interno: true, viajeId: respaldo.viajeId, previas: respaldo.previas + (JSON.parse(JSON.stringify(respaldo.estado)).subidas || []).length });
        if (ok) return;
        // El viaje nuevo no pudo arrancar: se recupera el anterior tal como estaba (misma fase, misma hora de inicio).
        await iniciar(respaldo.plan, respaldo.estado, { interno: true, reanudado: true, viajeId: respaldo.viajeId, previas: respaldo.previas, inicio: respaldo.inicio, ultima: respaldo.ultima, ruta: respaldo.ruta });
        mostrarAviso('No pude cambiar de recorrido. Sigues con el anterior.', { nivel: 'alerta', ms: 10000 });
    }
    function rechazarRecalculo() { if (sesion) delete sesion.propuesta; ocultarPregunta(); mostrarAviso('Sigues con tu recorrido actual.', { nivel: 'info', ms: 5000 }); }

    // ------------------------------------------------------------------ controles de la tarjeta
    $('startTrip').addEventListener('click', () => iniciar());
    q('viajeSi').addEventListener('click', () => { if (!sesion) return; if (q('viajePregunta').dataset.id === 'recalculo') return aceptarRecalculo(); manejar(sesion.nucleo.responder(q('viajePregunta').dataset.id, true)); });
    q('viajeNo').addEventListener('click', () => { if (!sesion) return; const id = q('viajePregunta').dataset.id; if (id === 'recalculo') return rechazarRecalculo(); manejar(sesion.nucleo.responder(id, false)); ocultarPregunta(); });
    q('viajeBajadaYa').addEventListener('click', () => { if (!sesion) return; manejar(sesion.nucleo.confirmarBajada()); pintarInfo(sesion.nucleo.info()); ocultarBajada(); });
    q('viajeBajadaSigo').addEventListener('click', () => {
        if (!sesion) return;
        const atras = q('viajeBajada').dataset.tipo === 'atras';
        manejar(sesion.nucleo.sigoEnBus());      // la fase y el bus se conservan; la pregunta automática se enfría
        ocultarBajada();
        mostrarAviso(atras ? 'Sigues en el bus. Baja en la próxima parada, cuando el bus se detenga.' : 'Seguimos con tu viaje. Te avisaré si hace falta.', { nivel: 'info', ms: 5000 });
        guardar();
    });
    q('viajeAlertas').addEventListener('click', () => { if (S.Ajustes) S.Ajustes.set('alertasBajada', !alertasOn()); pintarAlertas(); });
    q('viajeActivarAlertas').addEventListener('click', async () => { try { await Notification.requestPermission(); } catch { /* sin permiso: la pantalla sigue avisando */ } pintarAlertas(); });      // ÚNICO sitio que pide el permiso: un toque de la persona
    window.addEventListener('spevb-ajustes', pintarAlertas);
    q('viajeYaSubi').addEventListener('click', () => { if (sesion) { manejar(sesion.nucleo.confirmarSubida()); pintarInfo(sesion.nucleo.info()); } });
    q('viajeYaBaje').addEventListener('click', () => { if (sesion) { manejar(sesion.nucleo.confirmarBajada()); pintarInfo(sesion.nucleo.info()); } });
    q('viajeSeguir').addEventListener('click', () => {
        if (!sesion) return;
        sesion.seguir = !sesion.seguir; q('viajeSeguir').setAttribute('aria-pressed', String(sesion.seguir));
        const l = sesion.marcador && sesion.marcador.getPosition(); if (sesion.seguir && l && mapa()) { S.centrarEn(mapa(), l, Math.max(mapa().getZoom(), 16)); sesion.zoomSeguimiento = true; }
    });
    q('viajeRecalcular').addEventListener('click', recalcular);
    q('viajeCaminataReintentar').addEventListener('click', () => { const cam = sesion && sesion.cam; if (!cam || !['error', 'sin-ubicacion'].includes(cam.estado)) return; cam.estado = 'pendiente'; calcularCaminataReal(cam); });
    q('viajeCaminataRecalcular').addEventListener('click', () => { if (sesion) recalcular(); });
    q('viajeRecuperarMapa').addEventListener('click', () => { if (S.MapaSalud) S.MapaSalud.recuperar({ manual: true }); else mostrarAviso('La recuperación del mapa no está disponible.', { nivel: 'info', ms: 5000 }); });
    let confirmarFin = null;
    // «Volver al inicio»: la casita pide una confirmación comprensible (diálogo de inicio.js) cuando hay un viaje activo; ya llegado, sale de una vez.
    // El trabajo de limpiar vive en inicio.js (un solo camino para planificación, resultados, viaje y menú).
    function volverAlInicio() {
        finalizar();
        try { S.Planner.limpiar && S.Planner.limpiar(); } catch { /* sin planificador */ }
        const m = mapa(); if (m) m.setView(S.center, 13, { animate: !(S.Motion && S.Motion.reduced) });
        window.dispatchEvent(new CustomEvent('spevb-ir-inicio'));
    }
    q('viajeInicio').addEventListener('click', () => { if (S.Inicio) S.Inicio.pedir('viaje'); else volverAlInicio(); });
    q('viajeTerminar').addEventListener('click', () => {
        if (!sesion) return;
        if (q('viajeTerminar').dataset.llego) return finalizar();
        if (confirmarFin) { clearTimeout(confirmarFin); confirmarFin = null; q('viajeTerminar').textContent = 'Terminar viaje'; return finalizar(); }
        q('viajeTerminar').textContent = '¿Seguro? Toca otra vez';
        confirmarFin = setTimeout(() => { confirmarFin = null; if (sesion) q('viajeTerminar').textContent = 'Terminar viaje'; }, 4000);
    });
    // El primer arrastre manual del mapa deja de seguirte (como en cualquier app de navegación); «Seguirme» lo vuelve a activar.
    // El mapa es asíncrono (Google): se espera al hito «explorador». dragstart solo lo provoca la persona, nunca setView/panTo.
    S.esperar('explorador').then((explorador) => {
        const m0 = (explorador && explorador.map) || mapa();
        if (m0) m0.on('dragstart', () => { if (sesion && sesion.seguir) { sesion.seguir = false; q('viajeSeguir').setAttribute('aria-pressed', 'false'); } });
    });
    // Si la persona cambia o borra el plan mientras viaja, el viaje sigue con su propia copia y se dibuja aparte.
    window.addEventListener('spevb-seleccion', () => { if (sesion) asegurarRecorrido(); });
    document.addEventListener('keydown', (e) => { if (e.defaultPrevented) return; if (e.key === 'Escape' && sesion && tarjeta.contains(document.activeElement)) { if (!q('viajeBajada').hidden) q('viajeBajadaSigo').click(); else if (!q('viajePregunta').hidden) q('viajeNo').click(); } });

    // ------------------------------------------------------------------ reanudar un viaje interrumpido (recarga, cierre del navegador)
    let reanudarAbierta = false, descartarReanudar = () => {};
    /** Un viaje guardado solo se ofrece si es COHERENTE: forma completa, no vencido, no terminado y con un recorrido que el núcleo acepta. Cualquier otra cosa se borra y deja empezar uno nuevo. */
    function guardadoValido(g) {
        try {
            const num = (x) => typeof x === 'number' && Number.isFinite(x);
            if (!g || typeof g !== 'object' || !num(g.t) || g.t > Date.now() + 60000 || Date.now() - g.t > MAX_EDAD_MS) return false;
            if (!g.estado || typeof g.estado !== 'object' || ['llegaste', 'terminado'].includes(g.estado.fase)) return false;
            const p = g.plan;
            if (!p || !Array.isArray(p.buses) || !p.buses.length || !p.destino || !num(p.destino.lat) || !num(p.destino.lng)) return false;
            if (!p.buses.every((b) => b && Array.isArray(b.tramo) && b.tramo.length > 1 && b.subida && num(b.subida.lat) && b.bajada && num(b.bajada.lat))) return false;
            N.crearViaje(p);
            return true;
        } catch { return false; }
    }
    function ofrecerReanudar() {
        let crudo = null; try { crudo = localStorage.getItem(CLAVE); } catch { /* sin almacenamiento */ }
        if (crudo === null || crudo === undefined) { if (ciclo === 'pendiente') { ciclo = 'libre'; pintarBotonInicio(); } return; }
        const g = leer();
        if (!guardadoValido(g)) { borrar(); liberarCompartir(); return; }      // corrupto, incompleto, vencido o terminado: se limpia de forma segura
        if (bloqueoAjeno()) { pintarBotonInicio(); vigilarVencimiento(); return; }      // otra pestaña lo tiene abierto: aquí no se ofrece (se avisa al intentar empezar otro); al vencer su concesión se ofrece solo
        if (ofreciendo) return; ofreciendo = true;
        adquirir().then((r) => {
            ofreciendo = false;
            if (!r.ok) { pintarBotonInicio(); vigilarVencimiento(); return; }      // otra pestaña la tomó en ese instante
            if (ciclo !== 'libre' || sesion || reanudarAbierta) { if (!sesion && ciclo === 'libre') soltarBloqueo(); return; }      // mientras tanto cambió el ciclo
            mostrarReanudar(g);
        }).catch(() => { ofreciendo = false; });
    }
    let ofreciendo = false;
    function mostrarReanudar(g) {
        reanudarAbierta = true; ciclo = 'pendiente'; escribirBloqueo(); pintarBotonInicio();
        tarjeta.dataset.fase = 'reanudar'; ponerModo('completa', { recordar: false });
        q('viajeTitulo').textContent = 'Tienes un viaje en curso';
        const bus = g.plan.buses[Math.min(g.estado.leg || 0, g.plan.buses.length - 1)];
        q('viajeInstruccion').textContent = 'Ruta ' + (bus.etiqueta || bus.codigo) + ' · iniciado hace ' + Math.max(1, Math.round((Date.now() - (g.inicio || g.t)) / 60000)) + ' min.'
            + (g.ultima ? ' Última posición guardada ' + hace(Date.now() - (g.ultima.t || g.t)) + ' (antigua hasta recibir una lectura nueva).' : '');
        q('viajeBarra').hidden = true; q('viajeMini').hidden = true;
        q('viajePreguntaTexto').textContent = '¿Quieres continuarlo?';
        q('viajePregunta').dataset.id = 'reanudar'; q('viajePregunta').hidden = false;
        q('viajeSi').textContent = 'Reanudar viaje'; q('viajeNo').textContent = 'Descartar';
        q('viajeTerminar').hidden = true; q('viajeMas').hidden = true; q('viajeSeguir').hidden = true;
        const restaurar = () => { q('viajeBarra').hidden = false; q('viajeMini').hidden = false; ['viajeTerminar', 'viajeMas', 'viajeSeguir'].forEach((i) => { q(i).hidden = false; }); };
        const si = q('viajeSi'), no = q('viajeNo');
        // Reanudar NO depende de Google Maps: el viaje arranca aunque el mapa tarde o haya fallado (la capa se dibuja cuando esté disponible). La tarjeta de la pregunta solo se cierra
        // cuando el viaje de verdad arrancó; si no (p. ej. GPS sin permiso), se queda con el motivo y el viaje guardado se conserva.
        const alSi = (e) => {
            if (q('viajePregunta').dataset.id !== 'reanudar') return;
            e.stopImmediatePropagation();
            if (si.disabled) return;
            si.disabled = true;
            iniciar(g.plan, g.estado, { interno: true, volverA: 'pendiente', id: g.id, viajeId: g.vid || g.id, previas: g.previas || 0, bajada: !!g.bajada, reanudado: true, inicio: g.inicio, ultima: g.ultima || null, ruta: g.ruta || null }).then((ok) => {
                si.disabled = false;
                if (ok) { reanudarAbierta = false; restaurar(); }
                else mostrarAviso('No pude reanudar todavía. Revisa que el GPS esté activado y vuelve a tocar «Reanudar»: tu viaje sigue guardado.', { nivel: 'alerta', ms: 0 });
            }).catch(() => { si.disabled = false; mostrarAviso('No pude reanudar el viaje. Sigue guardado: vuelve a intentarlo.', { nivel: 'alerta', ms: 0 }); });
        };
        const alNo = (e) => { if (q('viajePregunta').dataset.id !== 'reanudar') return; e.stopImmediatePropagation(); descartarReanudar(); };
        // «Volver al inicio» con la pregunta de reanudar abierta: se descarta el viaje pendiente (y su estado guardado) como si se hubiera contestado «Descartar».
        descartarReanudar = ({ conservarGuardado = false } = {}) => {
            if (!reanudarAbierta) return;
            reanudarAbierta = false; restaurar(); tarjeta.hidden = true; ocultarPregunta(); delete tarjeta.dataset.fase;
            if (!conservarGuardado) { borrar(); liberarCompartir(); }      // un enlace compartido que quedó guardado con ese viaje también se retira (no si la concesión pasó a otra pestaña: ese viaje es de ella)
            if (ciclo === 'pendiente') { ciclo = 'libre'; soltarBloqueo(); pintarBotonInicio(); }
        };
        si.addEventListener('click', alSi, true); no.addEventListener('click', alNo, true);
    }

    // «Iniciar viaje» es la acción principal tras buscar: aparece justo bajo «Buscar rutas» en cuanto hay una opción elegida, con su resumen.
    const barraInicio = $('startTripBar');
    const fmtM = (m) => (m < 1000 ? m + ' m' : (m / 1000).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km');
    function mostrarBarraInicio() {
        const sel = S.Planner && S.Planner.seleccion;
        barraInicio.hidden = !(sel && sel.viaje) && !sesion;
        $('editarAB').hidden = barraInicio.hidden;      // «Editar A y B» acompaña a «Iniciar viaje» mientras haya una opción elegida (o un viaje en curso)
        const otras = document.querySelectorAll('#tripResults .trip-option').length - 1;
        $('verOpciones').hidden = !!sesion || !(sel && sel.viaje) || otras < 1;
        $('verOpciones').textContent = 'Ver otras opciones · ' + otras;
        if (sesion) { $('startTripInfo').textContent = 'Sigue las indicaciones de la tarjeta del mapa'; return; }
        if (!(sel && sel.viaje)) return;
        const r = sel.resumen;
        $('startTripInfo').textContent = 'Ruta ' + sel.codigos.map((c) => Spevb.rutaNombre(c)).join(' → ') + (r ? ' · ' + r.minutos + ' min · caminas ' + fmtM(r.caminaMetros) + (r.pasajes > 1 ? ' · 2 pasajes' : '') : '');
        // Si ir caminando directo tardaría lo mismo o menos, se dice aquí también (antes de tocar «Iniciar viaje»).
        if (r && r.caminarMejor) $('startTripInfo').textContent += ' · caminar directo ≈ ' + r.directoMin + ' min';
        $('startTripInfo').classList.toggle('walk-better', !!(r && r.caminarMejor));
    }
    window.addEventListener('spevb-seleccion', mostrarBarraInicio);
    window.addEventListener('spevb-viaje-modo', mostrarBarraInicio);
    $('verOpciones').addEventListener('click', () => window.dispatchEvent(new CustomEvent('spevb-ver-opciones')));
    $('editarAB').addEventListener('click', () => window.dispatchEvent(new CustomEvent('spevb-editar-ab')));

    const cerrarLlegada = () => { if (sesion && q('viajeTerminar').dataset.llego) { finalizar(); return true; } return false; };
    S.Viaje = { iniciar, detener: finalizar, cerrarLlegada, volverAMiViaje, mostrarConflicto, estadoCiclo: () => ciclo, bloqueado: () => ciclo !== 'libre' || !!bloqueoAjeno(), id: () => (sesion ? sesion.id : null),
        viajeId: () => (sesion ? sesion.viajeId : null), evidencia: () => (sesion ? { viajeId: sesion.viajeId, previas: sesion.previas || 0, subidas: sesion.nucleo.subidas() } : null),
        alertas: () => ({ activadas: alertasOn(), vibracion: soportaVibracion(), sonido: !!(audio && audio.state === 'running'), notificaciones: permisoNotif(), bajadaAbierta: !q('viajeBajada').hidden, avisadas: sesion ? [...sesion.avisadas] : [] }),
        diagnostico: () => ({ ciclo, id: sesion ? sesion.id : null, creadas: contadores.creadas, liberadas: contadores.liberadas, gps: !!(sesion && sesion.gps), timers: sesion ? [sesion.timer, sesion.timerGuardado].filter(Boolean).length : 0,
            capa: !!(sesion && sesion.capa), ruta: !!(sesion && sesion.ruta), wake: !!(sesion && sesion.wake), latido: !!latido, bloqueo: leerBloqueo(), poseo: poseo(), concesionesPerdidas: contadores.concesionesPerdidas, instancia, canal: !!canal }), pendiente: () => !sesion && reanudarAbierta, descartarPendiente: () => descartarReanudar(),
        llego: () => !!(sesion && q('viajeTerminar').dataset.llego), activo: () => !!sesion, info: () => (sesion ? sesion.nucleo.info() : null), nucleo: () => (sesion ? sesion.nucleo : null),
        rutaEstado: () => (sesion && sesion.ruta ? sesion.ruta.estado() : null),
        referencia: () => (sesion ? { ...sesion.nucleo.referencia(), cargas: Object.fromEntries(Object.entries(sesion.refs).map(([k, r]) => [k, { estado: r.estado, intentos: r.intentos }])) } : null),
        caminataReal: () => (sesion && sesion.cam ? { tipo: sesion.cam.tipo, leg: sesion.cam.leg, estado: sesion.cam.estado, intentos: sesion.cam.intentos, metros: sesion.cam.metros, minutos: sesion.cam.minutos, desde: sesion.cam.desde, hasta: sesion.cam.hasta, puntos: sesion.cam.coords ? sesion.cam.coords.length : 0 } : null),
        plan: () => (sesion ? sesion.plan : null) };      // diagnóstico de la ruta consumible (pruebas y soporte)
    pintarBotonInicio(); pintarAlertas();
    ofrecerReanudar();
})();
