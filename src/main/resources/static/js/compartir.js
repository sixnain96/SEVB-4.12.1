'use strict';
/* «Compartir mi viaje» (4.15), lado del teléfono que viaja. Ver docs/COMPARTIR-VIAJE.md.
   · Es opcional y nunca bloquea el viaje: si compartir o la red fallan, el viaje local sigue igual.
   · Crea un enlace con un token de lectura (va en el fragmento #… de /seguir.html, así no llega a registros ni al Referer) y guarda aquí el token de escritura.
   · Envía la ÚLTIMA posición, la fase y el progreso como máximo cada 12 s o al cambiar de fase (nunca cada lectura cruda ni una cola de historial). Sin internet espera
     y, al volver, manda solo el estado más reciente.
   · Se detiene al llegar (el servidor borra las coordenadas), al terminar el viaje, al tocar «Dejar de compartir», al vencer el enlace o si el servidor dice que ya no existe. */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const $ = (id) => document.getElementById(id);
    const tarjeta = $('viajeCard');
    if (!tarjeta || !S.Viaje) return;
    const CLAVE = 'spevb-compartir';
    const CADA_MS = 12000, TICK_MS = 4000, MAX_PUNTOS = 1500;
    let est = null;              // { lectura, escritura, expira } mientras se comparte
    let ultimoEnvio = 0, ultimaFase = null, pendiente = null, enviando = false, timer = null, fallos = 0, ultimaOk = 0;

    const leer = () => { try { return JSON.parse(localStorage.getItem(CLAVE)); } catch { return null; } };
    const guardar = () => { try { est ? localStorage.setItem(CLAVE, JSON.stringify(est)) : localStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ } };
    const enlace = () => location.origin + '/seguir.html#' + est.lectura;

    // ------------------------------------------------------------------ interfaz
    const ICONO = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M18 8a3 3 0 1 0-2.8-4M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm12-1a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM8.6 17.2l6.8 2.6M15.4 6.2L8.6 9.8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const boton = document.createElement('button');
    boton.type = 'button'; boton.id = 'viajeCompartir'; boton.className = 'viaje-compartir-boton';
    boton.innerHTML = ICONO + '<span>Compartir mi viaje</span>';
    const fila = document.createElement('div');
    fila.id = 'viajeCompartiendo'; fila.className = 'viaje-compartiendo'; fila.hidden = true;
    fila.innerHTML = '<span class="viaje-compartiendo-txt" role="status"><b>Compartiendo tu viaje</b><small id="viajeCompartirEstado"></small></span><button type="button" id="viajeDejarCompartir">Dejar de compartir</button>';
    const panel = $('viajeMasPanel');
    (panel || tarjeta).prepend(boton);
    const pie = tarjeta.querySelector('.viaje-pie');
    if (pie) pie.before(fila); else tarjeta.append(fila);

    const dlg = document.createElement('div');
    dlg.id = 'compartirModal'; dlg.className = 'modal-backdrop'; dlg.hidden = true;
    dlg.innerHTML = `
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="compTitulo">
            <h2 id="compTitulo">Compartir mi viaje</h2>
            <p id="compAviso">Las personas con el enlace podrán ver tu avance aproximado durante este viaje. El enlace dejará de funcionar cuando termines o dejes de compartir.</p>
            <div id="compConfirmar" hidden>
                <p id="compConfirmarTxt">¿Quieres dejar de compartir tu viaje? El enlace dejará de funcionar ahora mismo.</p>
            </div>
            <div id="compListo" hidden>
                <p class="comp-ok" id="compOk" role="status"><b>El enlace quedó listo</b></p>
                <p class="muted">Estás compartiendo tu viaje. Compártelo solo con alguien de confianza.</p>
                <label for="compEnlace">Enlace</label>
                <input id="compEnlace" type="text" readonly />
                <p class="muted" id="compEstado" role="status"></p>
                <div class="comp-botones">
                    <button type="button" id="compCompartir" class="primary-plan-button" hidden>Compartir de nuevo</button>
                    <button type="button" id="compCopiar" class="secondary">Copiar enlace</button>
                    <a id="compWhatsapp" class="secondary comp-enlace" target="_blank" rel="noopener noreferrer">Compartir por WhatsApp</a>
                </div>
            </div>
            <div class="modal-actions">
                <button type="button" id="compCancelar" class="secondary">Cancelar</button>
                <button type="button" id="compCrear" class="primary-plan-button">Crear enlace</button>
                <button type="button" id="compSiDejar" class="secondary comp-peligro" hidden>Sí, dejar de compartir</button>
                <button type="button" id="compNoDejar" class="primary-plan-button" hidden>No, seguir compartiendo</button>
                <button type="button" id="compDejar" class="secondary comp-peligro" hidden>Dejar de compartir</button>
                <button type="button" id="compCerrar" class="secondary" hidden>Cerrar</button>
            </div>
        </div>`;
    document.body.appendChild(dlg);

    let confirmando = false;
    function pintar() {
        const activo = !!est;
        if (!activo) confirmando = false;
        fila.hidden = !activo;
        boton.hidden = activo;
        $('compAviso').hidden = activo;
        $('compConfirmar').hidden = !confirmando;
        $('compListo').hidden = !activo || confirmando;
        $('compCrear').hidden = activo; $('compCancelar').hidden = activo;
        $('compDejar').hidden = !activo || confirmando; $('compCerrar').hidden = !activo || confirmando;
        $('compSiDejar').hidden = !confirmando; $('compNoDejar').hidden = !confirmando;
        if (!activo) return;
        $('compEnlace').value = enlace();
        $('compWhatsapp').href = 'https://wa.me/?text=' + encodeURIComponent('Sigue mi viaje en SEVB: ' + enlace());
        $('compCompartir').hidden = typeof navigator.share !== 'function' || confirmando;
        const txt = ultimaOk ? 'Última actualización: ' + hace(Date.now() - ultimaOk) + '.' : 'Esperando enviar la primera actualización…';
        $('compEstado').textContent = txt;
        $('viajeCompartirEstado').textContent = txt;
    }
    const hace = (ms) => { const s = Math.round(ms / 1000); return s < 45 ? 'hace unos segundos' : s < 90 ? 'hace 1 min' : 'hace ' + Math.round(s / 60) + ' min'; };
    const abrir = () => { confirmando = false; pintar(); S.Modal.abrir(dlg, { fondo: true, foco: est ? '#compCopiar' : '#compCrear' }); };
    const cerrar = () => { confirmando = false; S.Modal.cerrar(dlg); };

    // ------------------------------------------------------------------ servidor
    async function api(metodo, cuerpo, escritura) {
        return fetch('/api/compartir', { method: metodo, headers: { 'Content-Type': 'application/json', ...(escritura ? { 'X-Seguimiento-Escritura': escritura } : {}) },
            body: cuerpo ? JSON.stringify(cuerpo) : undefined, cache: 'no-store', credentials: 'same-origin' });
    }
    /** Recorrido a compartir: solo geometría y etiquetas, con a lo sumo MAX_PUNTOS (se conservan siempre el primero y el último de cada tramo). */
    function rutaDelViaje() {
        const plan = S.Viaje.plan && S.Viaje.plan();
        if (!plan || !plan.buses || !plan.buses.length) return null;
        const total = plan.buses.reduce((a, b) => a + b.tramo.length, 0), paso = Math.max(1, Math.ceil(total / MAX_PUNTOS));
        const reducir = (t) => { const o = t.filter((_, i) => i % paso === 0); if (o[o.length - 1] !== t[t.length - 1]) o.push(t[t.length - 1]); return o; };
        return { tramos: plan.buses.map((b) => reducir(b.tramo)), etiquetas: plan.buses.map((b) => b.etiqueta || b.codigo) };
    }
    async function crear() {
        if (est) return;
        if (!S.Viaje.activo()) { S.toast('Primero inicia un viaje para poder compartirlo.', { tipo: 'info', ms: 5000 }); return cerrar(); }
        const ruta = rutaDelViaje();
        $('compCrear').disabled = true;
        try {
            const r = await api('POST', { ruta });
            if (r.status === 429) throw new Error('Creaste varios enlaces seguidos. Inténtalo más tarde.');
            if (!r.ok) throw new Error('No pude crear el enlace ahora. Tu viaje sigue normal; inténtalo de nuevo.');
            const d = await r.json();
            est = { lectura: d.lectura, escritura: d.escritura, expira: d.expira * 1000 };
            guardar(); ultimoEnvio = 0; ultimaFase = null; ultimaOk = 0; fallos = 0;
            iniciarEnvios(); pintar(); enviar(true);
            const f = $('compCopiar'); if (f) f.focus();
        } catch (e) {
            S.toast(e && e.message && !/fetch|network/i.test(e.message) ? e.message : 'No pude crear el enlace: revisa tu internet. Tu viaje sigue normal.', { tipo: 'error', ms: 7000, clave: 'compartir' });
        } finally { $('compCrear').disabled = false; }
    }
    async function dejar({ aviso = true } = {}) {
        const e = est;
        est = null; pendiente = null; clearInterval(timer); timer = null; guardar();
        pintar();
        if (e) { try { await api('DELETE', null, e.escritura); } catch { /* sin internet: el enlace vence solo */ } }
        if (aviso && e) S.toast('Dejaste de compartir tu viaje. El enlace ya no funciona.', { tipo: 'info', ms: 5000, clave: 'compartir' });
        if (S.Modal.abierta(dlg)) cerrar();
    }
    async function enviar(forzar = false) {
        if (!est || enviando || !pendiente) return;
        if (Date.now() > est.expira) return dejar({ aviso: false });
        if (navigator.onLine === false) return;
        const cambioFase = pendiente.fase !== ultimaFase;
        if (!forzar && !cambioFase && Date.now() - ultimoEnvio < CADA_MS) return;
        const cuerpo = pendiente; pendiente = null; enviando = true;
        try {
            const r = await api('PUT', cuerpo, est.escritura);
            if (r.status === 404) { const e = est; est = null; guardar(); clearInterval(timer); pintar(); S.toast('El enlace de tu viaje dejó de estar disponible.', { tipo: 'info', ms: 6000, clave: 'compartir' }); void e; return; }
            if (!r.ok) throw new Error('http ' + r.status);
            ultimoEnvio = Date.now(); ultimaFase = cuerpo.fase; ultimaOk = Date.now(); fallos = 0;
            if (cuerpo.fase === 'llegaste') { est = null; guardar(); clearInterval(timer); }
            pintar();
        } catch { fallos++; if (!pendiente) pendiente = cuerpo; }      // se reintenta con el estado MÁS reciente, no con una cola
        finally { enviando = false; }
    }
    function iniciarEnvios() { clearInterval(timer); timer = setInterval(() => { enviar(); pintar(); }, TICK_MS); }

    // ------------------------------------------------------------------ eventos del viaje
    window.addEventListener('spevb-viaje-lectura', (e) => {
        if (!est) return;
        const d = e.detail, re = S.Viaje.rutaEstado && S.Viaje.rutaEstado();
        const tot = re ? re.etapas.reduce((a, x) => a + x.total, 0) : 0, hecho = re ? re.etapas.reduce((a, x) => a + Math.min(x.total, x.objetivo), 0) : 0;
        pendiente = { fase: d.fase, leg: d.leg || 0, progreso: tot ? Math.max(0, Math.min(1, hecho / tot)) : 0, lat: d.lat, lng: d.lng, precision: d.precision, etaMin: d.etaMin };
        enviar();
    });
    window.addEventListener('spevb-viaje-llegada', () => {
        if (!est) return;
        pendiente = { fase: 'llegaste', leg: 1, progreso: 1, lat: null, lng: null, precision: null, etaMin: 0 };
        enviar(true);
    });
    window.addEventListener('spevb-viaje-modo', (e) => {
        if (e.detail && e.detail.activo) {
            // Viaje reanudado tras recargar: si había un enlace vigente, se sigue compartiendo.
            const g = leer();
            if (!est && g && g.escritura && g.expira > Date.now()) { est = g; iniciarEnvios(); pintar(); }
        } else if (est) {
            dejar({ aviso: false }).then(() => S.toast('Dejaste de compartir porque el viaje terminó o cambió de recorrido. Puedes volver a compartirlo.', { tipo: 'info', ms: 6000, clave: 'compartir' }));
        }
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden && est) enviar(); });
    window.addEventListener('online', () => { if (est) enviar(true); });

    // ------------------------------------------------------------------ controles
    boton.addEventListener('click', abrir);
    $('compCancelar').addEventListener('click', cerrar);
    $('compCerrar').addEventListener('click', cerrar);
    $('compCrear').addEventListener('click', crear);
    // «Dejar de compartir» siempre pide confirmación (desde la tarjeta o desde el diálogo).
    const pedirConfirmacion = () => { confirmando = true; pintar(); if (!S.Modal.abierta(dlg)) S.Modal.abrir(dlg, { fondo: true, foco: '#compNoDejar' }); else $('compNoDejar').focus(); };
    $('compDejar').addEventListener('click', pedirConfirmacion);
    $('viajeDejarCompartir').addEventListener('click', pedirConfirmacion);
    $('compNoDejar').addEventListener('click', () => { confirmando = false; pintar(); $('compCopiar').focus(); });
    $('compSiDejar').addEventListener('click', () => dejar());
    $('compCompartir').addEventListener('click', async () => { try { await navigator.share({ title: 'Mi viaje en SEVB', text: 'Sigue mi viaje en SEVB:', url: enlace() }); } catch { /* cancelado */ } });
    $('compCopiar').addEventListener('click', async () => {
        const input = $('compEnlace');
        try { await navigator.clipboard.writeText(enlace()); $('compEstado').textContent = 'Enlace copiado.'; }
        catch { input.focus(); input.select(); $('compEstado').textContent = 'Selecciona y copia el enlace.'; }
    });
    S.Compartir = { activo: () => !!est, estado: () => (est ? { vence: est.expira, ultimaOk, fallos } : null) };
    const g0 = leer(); if (g0 && !(g0.expira > Date.now())) { try { localStorage.removeItem(CLAVE); } catch { /* nada */ } }
})();
