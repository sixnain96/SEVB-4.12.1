'use strict';
/* «Mis viajes y logros» (Fase D): viajes terminados de verdad, racha de días, medallas y recompensas visuales.

   · Un viaje cuenta SOLO al llegar de verdad con al menos una subida a un bus confirmada (el evento «spevb-viaje-llegada» trae un id lógico del viaje, la hora de llegada y cuántas subidas
     se confirmaron). Abandonar, «Cerrar» una llegada ya registrada, recargar, repetir el evento o practicar NO suman. Cada viaje cuenta una vez (idempotente por id).
   · Racha: días de calendario de BOGOTÁ (UTC-5 fijo, no la zona del teléfono). Un día cuenta una vez aunque tenga varios viajes (el total cuenta todos). Hay UN día vacío de gracia entre dos
     días con viaje; dos seguidos sin viajar la cortan. Sigue vigente mientras el último día con viaje no esté a más de 2 días de hoy. «3 días seguidos» y «Una semana» siguen pidiendo
     días consecutivos (racha estricta). El cálculo es espejo exacto de Racha.java (mismos vectores: src/test/resources/racha-vectores.json).
   · Con sesión, el progreso y la insignia destacada son de la CUENTA (servidor; cada viaje se envía con su id y no se suman contadores del dispositivo); sin sesión, de este dispositivo.
     El progreso antiguo de un dispositivo (spevb-logros) se conserva para quien lo usa como invitado y NUNCA se adjudica a la primera cuenta que entra.
   · El reloj es controlable (Spevb.Reloj) para probar medianoche, cambios de mes y de año sin esperar. No hay temporizadores frecuentes: el estado se deriva al abrir el menú, al volver
     de segundo plano y con UN solo temporizador a la próxima medianoche de Bogotá. */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const K_LEGADO = 'spevb-logros', K_LOCAL = 'spevb-logros-v2', K_CUENTA = 'spevb-logros-cuenta', K_COLA = 'spevb-logros-cola', K_RESUMEN = 'spevb-viajes-resumen';
    const $ = (id) => document.getElementById(id);
    const leerLS = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k)); return v === null || v === undefined ? d : v; } catch { return d; } };
    const escribirLS = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } };
    const quitarLS = (k) => { try { localStorage.removeItem(k); } catch { /* nada */ } };

    // ------------------------------------------------------------------ reloj controlable
    let desfase = 0, temporizador = null;
    const Reloj = {
        ahora: () => Date.now() + desfase,
        fijar(ms) { desfase = ms - Date.now(); replanificar(); pintar(); },
        avanzar(ms) { desfase += ms; replanificar(); pintar(); },
        restaurar() { desfase = 0; replanificar(); pintar(); },
    };

    // ------------------------------------------------------------------ días de Bogotá y racha (espejo de Racha.java)
    const BOGOTA_MS = -5 * 3600000;
    const diaDe = (ms) => new Date(ms + BOGOTA_MS).toISOString().slice(0, 10);
    const horaDe = (ms) => new Date(ms + BOGOTA_MS).getUTCHours();
    const numDia = (iso) => Math.round(Date.parse(iso + 'T00:00:00Z') / 86400000);
    const isoDe = (n) => new Date(n * 86400000).toISOString().slice(0, 10);
    const GRACIA = 1;
    function racha(dias, hoy) {
        const d = [...new Set(dias.map(numDia))].sort((a, b) => a - b);
        if (!d.length) return { actual: 0, mejor: 0, estricta: 0, dias: 0, ultimo: null };
        let cadena = 0, estricta = 0, mejor = 0, mejorE = 0, previo = null;
        for (const x of d) {
            const hueco = previo === null ? 0 : x - previo;
            cadena = previo === null || hueco > GRACIA + 1 ? 1 : cadena + 1;
            estricta = previo === null || hueco !== 1 ? 1 : estricta + 1;
            mejor = Math.max(mejor, cadena); mejorE = Math.max(mejorE, estricta); previo = x;
        }
        return { actual: numDia(hoy) - previo <= GRACIA + 1 ? cadena : 0, mejor, estricta: mejorE, dias: d.length, ultimo: isoDe(previo) };
    }
    /** Nivel de la llama: 0 sin racha, 1 (1–2 días), 2 (3–6), 3 (7–13), 4 (14 o más). */
    const nivelLlama = (n) => (n >= 14 ? 4 : n >= 7 ? 3 : n >= 3 ? 2 : n >= 1 ? 1 : 0);

    // ------------------------------------------------------------------ catálogo (espejo de LogrosService.desbloqueados)
    const pl = (n, uno, varios) => n + ' ' + (n === 1 ? uno : varios);
    const CATALOGO = [
        { id: 'primero', icono: 'brujula', titulo: 'Primer viaje', texto: 'Terminaste tu primer viaje en bus.', req: 'Termina un viaje yendo en bus.', prog: (m) => [m.viajes, 1], premio: 'Insignia «Mi primer viaje».', ok: (m) => m.viajes >= 1 },
        { id: 'cinco', icono: 'ruta', titulo: '5 viajes', texto: 'Ya llevas 5 viajes terminados.', req: 'Termina 5 viajes en bus.', prog: (m) => [m.viajes, 5], premio: 'Marco de ruta para tu foto de perfil.', ok: (m) => m.viajes >= 5 },
        { id: 'veinte', icono: 'medalla', titulo: '20 viajes', texto: '¡20 viajes! Ya conoces la ciudad.', req: 'Termina 20 viajes en bus.', prog: (m) => [m.viajes, 20], premio: 'Medalla «20 viajes».', ok: (m) => m.viajes >= 20 },
        { id: 'transbordo', icono: 'dosbuses', titulo: 'Con transbordo', texto: 'Hiciste un viaje cambiando de bus.', req: 'Termina un viaje cambiando de bus (con las dos subidas confirmadas).', prog: (m) => [m.transbordos, 1], premio: 'Medalla «Transbordo» con dos líneas de bus.', ok: (m) => m.transbordos >= 1 },
        { id: 'racha3', icono: 'llamaN2', titulo: '3 días seguidos', texto: 'Viajaste 3 días seguidos.', req: 'Viaja 3 días seguidos, sin saltarte ninguno.', prog: (m) => [m.mejorEstricta, 3], premio: 'Medalla de llama.', ok: (m) => m.mejorEstricta >= 3 },
        { id: 'racha7', icono: 'llamaN3', titulo: 'Una semana', texto: '¡7 días seguidos usando SEVB!', req: 'Viaja 7 días seguidos, sin saltarte ninguno.', prog: (m) => [m.mejorEstricta, 7], premio: 'Medalla de llama grande.', ok: (m) => m.mejorEstricta >= 7 },
        { id: 'madrugador', icono: 'sol', titulo: 'Madrugador', texto: 'Terminaste un viaje antes de las 7 a. m.', req: 'Termina un viaje antes de las 7 a. m.', prog: null, premio: 'Insignia «Madrugador».', ok: (m) => m.madrugador },
        { id: 'noche', icono: 'luna', titulo: 'De noche', texto: 'Terminaste un viaje después de las 7 p. m.', req: 'Termina un viaje después de las 7 p. m.', prog: null, premio: 'Insignia «De noche».', ok: (m) => m.nocturno },
        { id: 'practica', icono: 'birrete', titulo: 'Aprendiz', texto: 'Terminaste el viaje de práctica.', req: 'Haz el viaje de práctica (menú Ayuda). Practicar no suma viajes ni racha.', prog: null, premio: 'Insignia «Aprendiz».', ok: (m) => m.practica },
        { id: 'llano', icono: 'llano', titulo: 'Viajero del Llano', texto: '¡Eres Viajero del Llano!', req: 'Termina 30 viajes y consigue una racha de 7 días.', prog: (m) => [Math.min(m.viajes, 30), 30, Math.min(m.mejorRacha, 7), 7], premio: 'Borde ilustrado del Llano para tu foto y medalla «Viajero del Llano».', ok: (m) => m.viajes >= 30 && m.mejorRacha >= 7 },
    ];
    const porId = (id) => CATALOGO.find((l) => l.id === id);
    const desbloqueados = (m) => CATALOGO.filter((l) => l.ok(m)).map((l) => l.id);

    // ------------------------------------------------------------------ fuentes de datos: invitado (dispositivo) o cuenta (servidor)
    const uidActual = () => (S.Cuenta && S.Cuenta.uid ? S.Cuenta.uid() : null);
    const conCuenta = () => !!(S.LugaresCuenta && S.LugaresCuenta.deCuenta());
    const legado = () => { const v = leerLS(K_LEGADO, null); return v && typeof v === 'object' ? v : null; };
    const localGuest = () => { const v = leerLS(K_LOCAL, null); return { viajes: Array.isArray(v && v.viajes) ? v.viajes : [], practica: !!(v && v.practica) }; };
    const guardarLocal = (v) => escribirLS(K_LOCAL, { v: 2, viajes: v.viajes.slice(-400), practica: !!v.practica });
    const cacheCuenta = () => { const c = leerLS(K_CUENTA, null), uid = uidActual(); return c && uid !== null && String(c.uid) === String(uid) && c.estado ? c.estado : null; };

    /** Datos crudos de quien se muestra ahora → métricas con la racha calculada para HOY (Bogotá). */
    function vista() {
        const hoy = diaDe(Reloj.ahora());
        let f;
        if (conCuenta()) {
            const e = cacheCuenta() || { viajes: 0, transbordos: 0, madrugador: false, nocturno: false, practica: false, dias: [], mejorRacha: 0, mejorEstricta: 0, logros: [], insignia: null };
            f = { viajes: e.viajes || 0, transbordos: e.transbordos || 0, madrugador: !!e.madrugador, nocturno: !!e.nocturno, practica: !!e.practica, dias: e.dias || [], mejorRacha: e.mejorRacha || 0, mejorEstricta: e.mejorEstricta || 0, extra: e.logros || [], insignia: e.insignia || null, deCuenta: true };
        } else {
            const l = legado() || {}, g = localGuest(), dias = g.viajes.map((x) => diaDe(x.t));
            if (l.ultimoDia && l.racha > 0) for (let i = 0; i < Math.min(l.racha, 400); i++) dias.push(isoDe(numDia(l.ultimoDia) - i));      // la racha antigua del dispositivo (días seguidos de este teléfono)
            f = { viajes: (l.viajes || 0) + g.viajes.length, transbordos: (l.transbordos || 0) + g.viajes.filter((x) => x.b >= 2).length, madrugador: !!l.madrugador || g.viajes.some((x) => horaDe(x.t) < 7),
                nocturno: !!l.nocturno || g.viajes.some((x) => horaDe(x.t) >= 19), practica: !!l.practica || g.practica, dias, mejorRacha: l.mejorRacha || 0, mejorEstricta: l.mejorRacha || 0,
                extra: Array.isArray(l.hitos) ? l.hitos : [], insignia: null, deCuenta: false };
        }
        const r = racha(f.dias, hoy);
        const m = { viajes: f.viajes, transbordos: f.transbordos, madrugador: f.madrugador, nocturno: f.nocturno, practica: f.practica, rachaActual: r.actual, mejorRacha: Math.max(f.mejorRacha, r.mejor), mejorEstricta: Math.max(f.mejorEstricta, r.estricta), ultimoDia: r.ultimo, hoy };
        const ids = new Set(desbloqueados(m)); f.extra.forEach((id) => { if (porId(id)) ids.add(id); });
        return { m, ids, insignia: f.insignia && ids.has(f.insignia) ? f.insignia : null, deCuenta: f.deCuenta };
    }

    /** Compatibilidad con las pruebas y pantallas anteriores: los mismos nombres de siempre. */
    function leer() {
        const v = vista();
        return { viajes: v.m.viajes, transbordos: v.m.transbordos, racha: v.m.rachaActual, mejorRacha: v.m.mejorRacha, ultimoDia: v.m.ultimoDia || '', hitos: [...v.ids], madrugador: v.m.madrugador, nocturno: v.m.nocturno, practica: v.m.practica, insignia: v.insignia };
    }

    // ------------------------------------------------------------------ resumen de la semana (solo de este dispositivo, separado por quien lo usa)
    const alcance = () => (conCuenta() ? 'c' + uidActual() : 'g');
    function anotarResumen(t, resumen, buses) {
        const l = leerLS(K_RESUMEN, []).filter((x) => x && typeof x.t === 'number');
        l.push({ a: alcance(), t, min: resumen && resumen.minutos ? Math.round(resumen.minutos) : 0, camina: resumen && resumen.caminaMetros ? Math.round(resumen.caminaMetros) : 0, buses });
        escribirLS(K_RESUMEN, l.slice(-100));
    }
    function registroSemana() {
        const a = alcance(), propios = leerLS(K_RESUMEN, []).filter((x) => x && x.a === a);
        const viejo = a === 'g' && legado() && Array.isArray(legado().registro) ? legado().registro : [];
        return viejo.concat(propios);
    }
    function resumenSemana(ahora = new Date(Reloj.ahora())) {
        const desde = ahora.getTime() - 7 * 86400000;
        const r = registroSemana().filter((x) => x.t >= desde && x.t <= ahora.getTime() + 60000);
        return { viajes: r.length, caminaMetros: r.reduce((n, x) => n + (x.camina || 0), 0), minutos: r.reduce((n, x) => n + (x.min || 0), 0) };
    }
    const km = (m) => (m >= 1000 ? (m / 1000).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km' : Math.round(m / 10) * 10 + ' m');
    const duracion = (min) => (min >= 60 ? Math.floor(min / 60) + ' h ' + String(min % 60).padStart(2, '0') + ' min' : min + ' min');
    function textoSemana(ahora = new Date(Reloj.ahora())) {
        const r = resumenSemana(ahora);
        if (!r.viajes) return '';
        return 'En los últimos 7 días: ' + r.viajes + (r.viajes === 1 ? ' viaje' : ' viajes') + (r.caminaMetros ? ' · caminaste ' + km(r.caminaMetros) : '') + (r.minutos ? ' · unos ' + duracion(r.minutos) + ' en total' : '') + '.';
    }
    function avisoSemanal(ahora = new Date(Reloj.ahora())) {
        const texto = textoSemana(ahora);
        if (!texto) return false;
        const semana = ahora.getFullYear() + '-' + Math.floor((Date.UTC(ahora.getFullYear(), ahora.getMonth(), ahora.getDate()) - Date.UTC(ahora.getFullYear(), 0, 1)) / (7 * 86400000));
        try { if (localStorage.getItem('spevb-semana') === semana) return false; localStorage.setItem('spevb-semana', semana); } catch { return false; }
        if (S.toast) S.toast(texto + ' ¡Buen trabajo!', { tipo: 'success', ms: 9000, clave: 'semana' });
        return true;
    }

    // ------------------------------------------------------------------ registrar viajes
    const nuevoIdViaje = () => 'v' + Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
    const ahoraDe = (a) => (a instanceof Date ? a.getTime() : typeof a === 'number' ? a : Reloj.ahora());
    /** Un viaje cuenta con al menos una subida confirmada. Sin el dato (llamadas antiguas) se entiende que los buses del plan se tomaron. */
    const subidasDe = (d) => (Number.isFinite(d.subidas) ? d.subidas : d.busConfirmado === false ? 0 : Number.isFinite(d.buses) ? d.buses : 1);
    let chispaPendiente = false;

    /** Suma un viaje terminado EN ESTE DISPOSITIVO (invitado). Idempotente por id. Devuelve los logros nuevos. {@code ahora}: Date o ms (para poder probarlo). */
    function registrarViaje(det = {}, ahora) {
        const t = Number.isFinite(det.llegadaMs) ? det.llegadaMs : ahoraDe(ahora), b = subidasDe(det), id = String(det.viajeId || nuevoIdViaje());
        if (b < 1) return [];
        const g = localGuest();
        if (g.viajes.some((x) => x.id === id)) return [];
        const antes = vista();
        g.viajes.push({ id, t, b: Math.min(6, Math.round(b)) });
        guardarLocal(g);
        anotarResumen(t, det.resumen, b);
        const despues = vista();
        const nuevos = CATALOGO.filter((l) => despues.ids.has(l.id) && !antes.ids.has(l.id));
        if (nivelLlama(despues.m.rachaActual) > nivelLlama(antes.m.rachaActual)) chispaPendiente = true;
        pintar();
        return nuevos;
    }
    /** La práctica terminó: da «Aprendiz» (una vez) y NO suma viajes ni racha. */
    function marcarPractica() {
        if (conCuenta()) { const antes = vista(); if (antes.m.practica) return []; enviarPractica(); return CATALOGO.filter((l) => l.id === 'practica'); }
        const g = localGuest(), antes = vista();
        if (antes.m.practica) return [];
        g.practica = true; guardarLocal(g);
        const nuevos = CATALOGO.filter((l) => vista().ids.has(l.id) && !antes.ids.has(l.id));
        pintar();
        if (nuevos.length && S.toast) S.toast(nuevos.map((l) => l.texto).join('  '), { tipo: 'success', ms: 8000, clave: 'logro' });
        return nuevos;
    }

    // ---- cuenta: cola de envíos (reintentos sin conexión), un envío por viaje, con comprobación de identidad y de generación
    const cola = () => leerLS(K_COLA, []).filter((x) => x && x.uid !== undefined && x.viajeId);
    const guardarCola = (c) => escribirLS(K_COLA, c.slice(-50));
    let vaciando = false;
    const generacion = () => (S.Cuenta && S.Cuenta.generacion !== undefined ? S.Cuenta.generacion : 0);
    async function vaciarCola() {
        if (vaciando || !S.Cuenta || !S.Cuenta.sesionValida) return;
        vaciando = true;
        const uid = uidActual(), gen = generacion(), ganados = [], antes = vista(), ultimoViaje = cola().length ? cola()[cola().length - 1].viajeId : null;
        try {
            // Se toma siempre el siguiente envío pendiente de ESTA cuenta (los que se agregan mientras se vacía también se envían).
            for (let it = cola().find((x) => String(x.uid) === String(uid)); it; it = cola().find((x) => String(x.uid) === String(uid))) {
                if (uidActual() !== uid || generacion() !== gen) break;      // la sesión cambió: este envío ya no es de quien está aquí
                let r;
                try { r = await S.Cuenta.pedir('/api/cuenta/logros/viaje', { metodo: 'POST', cuerpo: { viajeId: it.viajeId, llegadaMs: it.llegadaMs, buses: it.buses } }); }
                catch (e) {
                    if (e && [400, 409, 429, 422].includes(e.status)) { guardarCola(cola().filter((x) => x.viajeId !== it.viajeId || String(x.uid) !== String(uid))); continue; }      // el servidor lo rechaza para siempre: se descarta
                    break;      // sin conexión, sesión vencida o fallo del servidor: se queda para reintentar
                }
                if (uidActual() !== uid || generacion() !== gen) break;
                guardarCola(cola().filter((x) => x.viajeId !== it.viajeId || String(x.uid) !== String(uid)));
                escribirLS(K_CUENTA, { uid, estado: r });
                (r.nuevos || []).forEach((id) => ganados.push(id));
            }
        } finally { vaciando = false; }
        if (uidActual() === uid) { const despues = vista(); celebrar(ganados, antes, despues, ultimoViaje); pintar(); }
    }
    async function enviarPractica() {
        if (!S.Cuenta.sesionValida) return;
        const uid = uidActual(), gen = generacion();
        try { const r = await S.Cuenta.pedir('/api/cuenta/logros/practica', { metodo: 'POST', cuerpo: {} }); if (uidActual() !== uid || generacion() !== gen) return; escribirLS(K_CUENTA, { uid, estado: r }); pintar(); if (S.toast) S.toast(porId('practica').texto, { tipo: 'success', ms: 8000, clave: 'logro' }); } catch { /* sin conexión: se verá al sincronizar */ }
    }
    /** Trae el estado de la cuenta (nunca pisa nada con una respuesta de otra cuenta o de otra sesión). */
    async function refrescarCuenta() {
        if (!S.Cuenta || !S.Cuenta.sesionValida) return;
        const uid = uidActual(), gen = generacion();
        try { const r = await S.Cuenta.pedir('/api/cuenta/logros'); if (uidActual() !== uid || generacion() !== gen) return; escribirLS(K_CUENTA, { uid, estado: r }); pintar(); } catch { /* sin conexión: queda la copia de esta cuenta */ }
    }
    async function sincronizar() { await vaciarCola(); await refrescarCuenta(); }

    /** UNA celebración breve y agrupada después de llegar: logros nuevos y subida de nivel de la llama (nada si no hay nada nuevo). */
    function celebrar(ganados, antes, despues, viajeId) {
        const nuevos = [...new Set(ganados)].map(porId).filter(Boolean), sube = nivelLlama(despues.m.rachaActual) > nivelLlama(antes.m.rachaActual);
        if (sube) chispaPendiente = true;
        const partes = [];
        if (despues.m.rachaActual > antes.m.rachaActual && despues.m.rachaActual >= 2) partes.push('Racha de ' + pl(despues.m.rachaActual, 'día', 'días') + '.');
        if (nuevos.length) partes.push((nuevos.length === 1 ? 'Logro nuevo: ' : 'Logros nuevos: ') + nuevos.map((l) => l.titulo).join(', ') + '.');
        if (partes.length) {
            // Con la tarjeta de llegada a la vista, el resultado va ahí como detalle secundario; sin ella (otra pantalla) queda el aviso breve.
            const r = { viajeId: viajeId || null, ganados: nuevos.map((l) => l.titulo), racha: despues.m.rachaActual > antes.m.rachaActual ? despues.m.rachaActual : 0, viajes: despues.m.viajes, manejado: false };
            window.dispatchEvent(new CustomEvent('spevb-logros-resultado', { detail: r }));
            if (!r.manejado && S.toast) S.toast('¡Llegaste! ' + partes.join(' '), { tipo: 'success', ms: 9000, clave: 'logro' });
        }
        if (chispaPendiente) chispa();
    }

    /** Evento de llegada del modo viaje. */
    function alLlegar(det) {
        det = det || {};
        if (!det.viajeId || !Number.isFinite(det.llegadaMs) || subidasDe(det) < 1 || det.busConfirmado === false) return;      // sin id, sin hora o sin subida confirmada no cuenta
        if (conCuenta()) {
            const uid = uidActual();
            if (uid === null) return;
            const c = cola();
            if (!c.some((x) => x.viajeId === det.viajeId && String(x.uid) === String(uid))) { c.push({ uid, viajeId: String(det.viajeId), llegadaMs: Math.round(det.llegadaMs), buses: Math.max(1, Math.min(6, Math.round(subidasDe(det)))) }); guardarCola(c); anotarResumenUnico(det); }
            vaciarCola();
        } else {
            const antes = vista(), nuevos = registrarViaje(det);
            celebrar(nuevos.map((l) => l.id), antes, vista(), det.viajeId);
        }
    }
    const vistos = new Set();
    function anotarResumenUnico(det) { if (vistos.has(det.viajeId)) return; vistos.add(det.viajeId); anotarResumen(det.llegadaMs, det.resumen, subidasDe(det)); }

    // ------------------------------------------------------------------ insignia destacada
    async function equipar(id) {
        if (!S.Cuenta || !S.Cuenta.sesionValida) { if (S.toast) S.toast('Para destacar una insignia necesitas continuar con Google, con conexión.', { tipo: 'info', ms: 5000, clave: 'logro' }); return false; }
        const uid = uidActual(), gen = generacion();
        try {
            const r = await S.Cuenta.pedir('/api/cuenta/logros/insignia', { metodo: 'POST', cuerpo: { id: id || null } });
            if (uidActual() !== uid || generacion() !== gen) return false;
            escribirLS(K_CUENTA, { uid, estado: r }); pintar(); return true;
        } catch (e) { if (S.toast) S.toast((e && e.message) || 'No pude cambiar la insignia. Inténtalo de nuevo.', { tipo: 'error', ms: 6000, clave: 'logro' }); return false; }
    }

    // ------------------------------------------------------------------ presentación
    function progresoTexto(l, m) {
        if (!l.prog) return '';
        const p = l.prog(m);
        return p.length === 4 ? 'Llevas ' + p[0] + ' de ' + p[1] + ' viajes y ' + p[2] + ' de ' + p[3] + ' días de racha.' : 'Llevas ' + Math.min(p[0], p[1]) + ' de ' + p[1] + '.';
    }
    let elegido = null;
    function detalle(id) {
        const caja = $('logroDetalle'), v = vista();
        if (!caja) return;
        const l = porId(id);
        elegido = l ? id : null;
        if (!l) { caja.hidden = true; caja.textContent = ''; return; }
        const ganado = v.ids.has(id);
        caja.replaceChildren();
        const t = document.createElement('strong'); t.textContent = l.titulo + ' · ' + (ganado ? 'Ganado' : 'Por conseguir');
        const r = document.createElement('span'); r.textContent = ganado ? l.texto : 'Cómo se consigue: ' + l.req;
        caja.append(t, r);
        const pr = progresoTexto(l, v.m);
        if (!ganado && pr) { const p = document.createElement('span'); p.textContent = pr; caja.append(p); }
        const g = document.createElement('span'); g.textContent = (ganado ? 'Tu recompensa: ' : 'Recompensa: ') + l.premio; caja.append(g);
        caja.hidden = false;
    }
    const textoRacha = (n) => (n >= 1 ? 'Racha de ' + pl(n, 'día', 'días') : 'Empieza tu racha con tu próximo viaje');
    function pintarRacha(v) {
        const n = v.m.rachaActual, nivel = nivelLlama(n);
        const chip = $('rachaChip'), ico = $('rachaIcono'), txt = $('rachaTexto'), det = $('rachaDetalle');
        if (txt) txt.textContent = textoRacha(n);
        if (chip) { chip.dataset.nivel = String(nivel); chip.classList.toggle('sin-racha', nivel === 0); }
        if (ico) { const nombre = nivel ? 'llamaN' + nivel : 'llama'; if (ico.dataset.icono !== nombre) { ico.replaceChildren(S.Iconos.el(nombre, { tam: 24 })); ico.dataset.icono = nombre; } }
        if (det) {
            const l = [];
            if (v.m.mejorRacha >= 1) l.push('Mejor racha: ' + pl(v.m.mejorRacha, 'día', 'días') + '.');
            if (n >= 1) l.push(diaDe(Reloj.ahora()) === v.m.ultimoDia ? 'Hoy ya sumaste un día.' : 'Hoy puedes seguir tu racha con un viaje.');
            l.push('Un día sin viajar no rompe tu racha; si pasan dos días seguidos sin viajar, vuelve a empezar.');
            det.textContent = l.join(' ');
        }
    }
    function pintarAvatar(v) {
        const id = v.deCuenta && v.insignia ? v.insignia : '';
        const marco = id === 'cinco' || id === 'llano' ? id : '', l = porId(id);
        let img = '';
        if (id && !marco && l) img = 'url("data:image/svg+xml,' + encodeURIComponent(S.Iconos.svg(l.icono, { tam: 16 }).replace(/currentColor/g, '#ffffff')) + '")';
        document.querySelectorAll('.account-avatar').forEach((a) => {
            if (id) a.dataset.insignia = id; else delete a.dataset.insignia;
            if (marco) a.dataset.marco = marco; else delete a.dataset.marco;
            if (img) a.style.setProperty('--insignia-img', img); else a.style.removeProperty('--insignia-img');
        });
    }
    function pintarPerfil(v) {
        const ul = $('setMedallasLista'), txt = $('setMedallasTxt');
        if (!ul) return;
        const ganadas = CATALOGO.filter((l) => v.ids.has(l.id));
        if (txt) txt.textContent = ganadas.length ? 'Elige una para destacarla junto a tu foto. Solo la ves tú y se guarda en tu cuenta.' : 'Todavía no has ganado medallas. Se ganan viajando: tu primer viaje te da una.';
        ul.replaceChildren(...ganadas.map((l) => {
            const li = document.createElement('li'), puesta = v.insignia === l.id;
            li.className = 'medalla-perfil' + (puesta ? ' puesta' : '');
            const ico = document.createElement('span'); ico.className = 'logro-ico'; ico.setAttribute('aria-hidden', 'true'); ico.append(S.Iconos.el(l.icono, { tam: 22 }));
            const t = document.createElement('span'); t.className = 'logro-txt'; t.textContent = l.titulo;
            const b = document.createElement('button'); b.type = 'button'; b.className = 'secondary medalla-boton'; b.textContent = puesta ? 'Quitar' : 'Destacar';
            b.setAttribute('aria-pressed', String(puesta)); b.setAttribute('aria-label', (puesta ? 'Quitar la insignia ' : 'Destacar la insignia ') + l.titulo);
            b.onclick = async () => { b.disabled = true; await equipar(puesta ? null : l.id); b.disabled = false; };
            li.append(ico, t, b);
            return li;
        }));
    }
    function pintar() {
        const v = vista(), lista = $('logrosLista'), resumen = $('logrosResumen'), sem = $('semanaResumen');
        if (sem) { const t = textoSemana(); sem.textContent = t; sem.hidden = !t; }
        pintarRacha(v); pintarAvatar(v); pintarPerfil(v);
        const pend = cola().filter((x) => String(x.uid) === String(uidActual())).length, nota = $('logrosPendiente');
        if (nota) { nota.hidden = !(v.deCuenta && pend); nota.textContent = pend ? (pend === 1 ? 'Un viaje por sincronizar: se enviará cuando haya conexión.' : pend + ' viajes por sincronizar: se enviarán cuando haya conexión.') : ''; }
        if (!lista || !resumen) return;
        resumen.textContent = v.m.viajes ? 'Has terminado ' + v.m.viajes + (v.m.viajes === 1 ? ' viaje' : ' viajes') + '.' : 'Aún no has terminado ningún viaje. ¡Tu primer viaje te da un logro!';
        lista.replaceChildren(...CATALOGO.map((l) => {
            const li = document.createElement('li'), ganado = v.ids.has(l.id);
            li.className = 'logro' + (ganado ? ' ganado' : '');
            const b = document.createElement('button'); b.type = 'button'; b.className = 'logro-boton'; b.dataset.logro = l.id;
            b.setAttribute('aria-label', l.titulo + ', ' + (ganado ? 'ganado' : 'por conseguir') + '. Toca para ver ' + (ganado ? 'tu recompensa.' : 'cómo se consigue.'));
            const ico = document.createElement('span'); ico.className = 'logro-ico'; ico.setAttribute('aria-hidden', 'true'); ico.append(S.Iconos.el(ganado ? l.icono : 'candado', { tam: 22 }));
            const t = document.createElement('span'); t.className = 'logro-txt'; t.textContent = l.titulo;
            const e = document.createElement('span'); e.className = 'logro-estado'; e.textContent = ganado ? 'Ganado' : 'Por conseguir';
            b.append(ico, t, e); b.title = ganado ? l.texto : 'Por conseguir';
            b.addEventListener('click', () => detalle(l.id));
            li.append(b);
            return li;
        }));
        if (elegido) detalle(elegido);
    }
    /** Destello breve cuando la llama sube de nivel; con «reducir movimiento» queda un aro fijo (lo decide el CSS). */
    function chispa() {
        const chip = $('rachaChip');
        if (!chip || !$('sideMenu') || !$('sideMenu').classList.contains('open')) return;      // el menú está cerrado: el destello queda pendiente y se ve la próxima vez que se abra
        chispaPendiente = false;
        chip.classList.remove('chispa'); void chip.offsetWidth; chip.classList.add('chispa');
        setTimeout(() => chip.classList.remove('chispa'), 2200);
    }

    // ------------------------------------------------------------------ cuándo se vuelve a derivar: abrir el menú, volver de segundo plano, medianoche, cambio de sesión
    function replanificar() {
        clearTimeout(temporizador);
        const ahora = Reloj.ahora(), sig = (Math.floor((ahora + BOGOTA_MS) / 86400000) + 1) * 86400000 - BOGOTA_MS;
        temporizador = setTimeout(() => { pintar(); replanificar(); }, Math.max(1000, sig - ahora + 1000));
    }
    function revisar() { pintar(); if (conCuenta()) sincronizar(); if (chispaPendiente && $('logros') && $('sideMenu') && $('sideMenu').classList.contains('open')) chispa(); }
    window.addEventListener('spevb-superficies', (ev) => { if (ev.detail && ev.detail.menu) revisar(); });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { replanificar(); revisar(); } });
    window.addEventListener('online', () => { if (conCuenta()) sincronizar(); });
    window.addEventListener('spevb-cuenta', () => { elegido = null; detalle(null); pintar(); if (conCuenta()) sincronizar(); });
    window.addEventListener('storage', (e) => { if (e.key === K_CUENTA || e.key === K_LOCAL || e.key === K_COLA) pintar(); });
    const ajustes = $('accountSettings');
    if (ajustes) ajustes.addEventListener('click', () => pintar());

    window.addEventListener('spevb-viaje-llegada', (ev) => alLlegar(ev.detail));
    S.Reloj = Reloj;
    S.Logros = { registrarViaje, marcarPractica, resumenSemana, textoSemana, avisoSemanal, leer, LOGROS: CATALOGO, vista, racha, diaDe, horaDe, nivelLlama, desbloqueados, sincronizar, equipar, revisar, alLlegar, cola, detalle };
    setTimeout(() => avisoSemanal(), 2500);
    replanificar();
    pintar();
})();
