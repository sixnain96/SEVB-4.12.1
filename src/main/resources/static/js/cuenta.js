'use strict';
/* Cuentas y datos personales.
   · Spevb.Datos: lugares, rutas favoritas, viajes guardados e historial. Siempre funcionan en este dispositivo (sin cuenta);
     con una cuenta se sincronizan con el servidor y aparecen en el otro equipo (celular ↔ computador).
   · Spevb.Cuenta: SOLO «Continuar con Google» (Fase B). No hay registro, correo ni contraseña: la identidad es la cuenta de Google y SEVB guarda su perfil (id interno) con los datos.
     La sesión es una cookie HttpOnly del servidor. Al cerrar sesión se borran los datos personales de ESTE dispositivo (siguen en la cuenta), para no dejar rastro en equipos compartidos.
   · Spevb.Cuenta.pedirEntrada({ motivo }) / requiere(motivo): el punto de entrada para cualquier función que necesite cuenta (p. ej. «lugares privados»): abre el mismo diálogo y
     devuelve el usuario, o null si la persona decide seguir sin cuenta. Nada entra solo: el inicio de sesión siempre nace de una acción de la persona.
   · Ninguna respuesta asíncrona (callback de Google, respuesta del servidor, sincronización) puede aplicar una sesión o sus datos a otra cuenta: cada cambio de usuario sube `generacion`,
     las operaciones de sesión se serializan (`enOperacion`) y todo lo que llega tarde se compara con la generación con que empezó. */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const $ = (id) => document.getElementById(id);
    const LOCAL = { lugares: 'spevb-favoritos', rutas: 'spevb-rutas-fav', viajes: 'spevb-viajes-guardados', historial: 'spevb-historial' };
    const MAXIMO = { lugares: 30, rutas: 100, viajes: 50, historial: 50 };
    const K_PENDIENTES = 'spevb-datos-pendientes', K_USUARIO = 'spevb-usuario';
    // Fase C: los lugares de una CUENTA viven aparte de los de un invitado. Cache por cuenta: { uid, items (con lápidas), base (el «actualizadoEn» del servidor) }.
    const K_LUG = 'spevb-lugares-cuenta', K_MIG_LUG = 'spevb-lugares-v2';
    const leer = (k, v) => { try { return JSON.parse(localStorage.getItem(k)) ?? v; } catch { return v; } };
    const escribir = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } };
    const evento = (nombre, detalle) => window.dispatchEvent(new CustomEvent(nombre, { detail: detalle }));

    let usuario = null;          // { id, nombre, correo, ... } o null
    let verificado = false;      // ya se comprobó la sesión con el servidor al menos una vez en esta carga
    let sinVerificar = false;    // se muestra el último usuario conocido porque no hubo conexión para comprobar la sesión
    let cuentaAnterior = false;  // hay una cuenta antigua (con contraseña) con el correo de Google verificado, o este navegador tenía una sesión de una: se explica la recuperación
    let generacion = 0;          // sube cada vez que cambia QUIÉN está en sesión: lo que empezó con otra generación ya no se aplica
    let enOperacion = false;     // entrar, salir o eliminar: una sola a la vez
    const empujes = {};
    const pendientes = new Set(leer(K_PENDIENTES, []));
    const guardarPendientes = () => escribir(K_PENDIENTES, [...pendientes]);
    const idDeUsuario = (u) => (u && u.id !== undefined ? u.id : u ? u.correo : null);
    const fijarUsuario = (u) => { if (idDeUsuario(usuario) !== idDeUsuario(u)) generacion++; usuario = u; };

    // ------------------------------------------------------------------ pedidos
    async function pedir(url, { metodo = 'GET', cuerpo, espera = 15000 } = {}) {
        const control = new AbortController();
        const t = setTimeout(() => control.abort(), espera);
        try {
            const r = await fetch(url, {
                method: metodo, signal: control.signal, credentials: 'same-origin',
                headers: { Accept: 'application/json', ...(cuerpo !== undefined ? { 'Content-Type': 'application/json' } : {}) },
                body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
            });
            let datos = null;
            try { datos = await r.json(); } catch { /* sin cuerpo */ }
            if (!r.ok) { const e = new Error(datos?.message || 'No se pudo completar la operación (HTTP ' + r.status + ').'); e.status = r.status; throw e; }
            return datos;
        } catch (e) {
            if (e.status) throw e;
            const err = new Error('Sin conexión con el servidor.');
            err.offline = true;
            throw err;
        } finally { clearTimeout(t); }
    }

    // ------------------------------------------------------------------ datos (local primero, servidor si hay cuenta)
    // ---- lugares: invitado (este dispositivo) y cuenta (servidor) NUNCA se mezclan
    const esVivo = (x) => !!x && !x.borrado;
    /** Quién se muestra mientras la sesión aún no se comprobó: el último usuario conocido (como el resto de la interfaz). */
    const usuarioVisible = () => usuario || (!verificado ? leer(K_USUARIO, null) : null);
    function cacheLugares() {
        const u = usuarioVisible(), c = leer(K_LUG, null);
        return u && c && c.uid === idDeUsuario(u) && Array.isArray(c.items) ? c : null;
    }
    const guardarCacheLugares = (uid, items, base) => escribir(K_LUG, { uid, items, base: Number(base) || 0 });
    const errSesion = () => Object.assign(new Error('La sesión cambió mientras se guardaba. No se aplicó nada.'), { sesionCambio: true });
    const copiar = (x) => JSON.parse(JSON.stringify(x));
    /** Lista nueva de lugares vivos → documento con lápidas: lo que ya no está queda borrado (para que no reaparezca) y lo editado lleva un momento nuevo. */
    function reconciliar(prev, nuevos) {
        const ahora = Date.now(), previos = new Map(prev.map((x) => [x.id, x])), out = [];
        for (const n of nuevos) {
            const p = previos.get(n.id), igual = p && esVivo(p) && ['nombre', 'lat', 'lng', 'tipo'].every((k) => p[k] === n[k]);
            out.push({ ...n, v: igual ? (p.v || 0) : Math.max(ahora, ((p && p.v) || 0) + 1) });
        }
        const ids = new Set(nuevos.map((n) => n.id));
        for (const p of prev) if (!ids.has(p.id)) out.push(p.borrado ? p : { id: p.id, borrado: true, v: Math.max(ahora, (p.v || 0) + 1) });
        return out;
    }
    async function traerLugares(gen) {
        const r = await pedir('/api/cuenta/datos');
        if (gen !== generacion) throw errSesion();
        const e = r && r.lugares;
        return { doc: Array.isArray(e && e.valor) ? e.valor : [], base: e ? Number(e.actualizadoEn) || 0 : 0 };
    }
    /** Cambia los lugares de la cuenta CON CONFIRMACIÓN del servidor: lee lo último, aplica el cambio y lo escribe solo si nadie más lo cambió (si no, vuelve a leer y reaplica). Nada se confirma sin
     *  conexión (esta versión no guarda lugares sin internet) y nada se aplica si la sesión cambió mientras tanto. {@code f(vivos)} devuelve la lista nueva o lanza un Error con mensaje para la persona. */
    async function mutarLugares(f) {
        if (!usuario || sinVerificar) throw Object.assign(new Error('Necesitas iniciar sesión, con conexión, para guardar tus lugares.'), { sinSesion: true });
        const gen = generacion, uid = idDeUsuario(usuario);
        for (let intento = 0; intento < 3; intento++) {
            const { doc, base } = await traerLugares(gen);
            const nueva = f(doc.filter(esVivo).map(copiar)), nuevoDoc = reconciliar(doc, nueva);
            try {
                await pedir('/api/cuenta/datos/lugares', { metodo: 'POST', cuerpo: { valor: nuevoDoc, base } });
            } catch (e) { if (e.status === 409 && gen === generacion) continue; throw e; }
            if (gen !== generacion) throw errSesion();
            const fin = await traerLugares(gen);       // lo que quedó de verdad en el servidor (puede haber limpiado algo)
            guardarCacheLugares(uid, fin.doc, fin.base);
            evento('spevb-datos', { clave: 'lugares' });
            return fin.doc.filter(esVivo);
        }
        throw new Error('Tus lugares cambiaron en otro dispositivo varias veces seguidas. Inténtalo de nuevo.');
    }
    /** Trae los lugares de la cuenta (el servidor manda: aquí no hay escrituras pendientes). */
    async function refrescarLugares() {
        if (!usuario || sinVerificar) return;
        const gen = generacion, uid = idDeUsuario(usuario);
        try { const { doc, base } = await traerLugares(gen); if (gen !== generacion) return; guardarCacheLugares(uid, doc, base); evento('spevb-datos', { clave: 'lugares' }); } catch { /* sin conexión: queda la copia de esta cuenta */ }
    }
    // Una sola vez: si este navegador ya tenía una sesión cuando se instaló esta versión, lo que hubiera en «spevb-favoritos» era de ESA cuenta (antes se mezclaba al entrar y se borraba al salir).
    try {
        if (!leer(K_MIG_LUG, null)) {
            const u = leer(K_USUARIO, null), viejos = leer(LOCAL.lugares, []);
            if (u && Array.isArray(viejos) && viejos.length) { guardarCacheLugares(idDeUsuario(u), viejos.filter((x) => x && x.id && x.nombre).map((x) => ({ id: String(x.id), nombre: String(x.nombre), lat: x.lat, lng: x.lng })), 0); localStorage.removeItem(LOCAL.lugares); }
            escribir(K_MIG_LUG, 1);
        }
    } catch { /* sin almacenamiento */ }

    const Datos = {
        leer(clave) {
            if (clave === 'lugares') return usuarioVisible() ? (cacheLugares() ? cacheLugares().items.filter(esVivo) : []) : (() => { const v = leer(LOCAL.lugares, []); return Array.isArray(v) ? v : []; })();
            const v = leer(LOCAL[clave], []); return Array.isArray(v) ? v : [];
        },
        /** Guarda en este dispositivo y, con sesión, en la cuenta. Los lugares de una cuenta se guardan SOLO a través del servidor (mutarLugares). */
        escribir(clave, lista, { remoto = true } = {}) {
            if (clave === 'lugares' && usuario) { if (remoto) mutarLugares(() => lista.slice(0, MAXIMO.lugares)).catch(() => {}); return lista; }
            lista = lista.slice(0, MAXIMO[clave]);
            escribir(LOCAL[clave], lista);
            evento('spevb-datos', { clave });
            if (remoto && usuario) programar(clave);
            return lista;
        },
    };
    function programar(clave) {
        pendientes.add(clave); guardarPendientes();
        clearTimeout(empujes[clave]);
        const gen = generacion;
        empujes[clave] = setTimeout(() => { if (gen === generacion) empujar(clave); }, 700);
    }
    async function empujar(clave) {
        if (!usuario || sinVerificar || clave === 'lugares') return;
        const gen = generacion;
        try {
            await pedir('/api/cuenta/datos/' + clave, { metodo: 'POST', cuerpo: { valor: Datos.leer(clave) } });
            if (gen !== generacion) return;      // mientras tanto cambió la sesión: ese envío no es de la cuenta actual
            pendientes.delete(clave); guardarPendientes();
        } catch (e) {
            if (e.status === 401 && gen === generacion) { await verificar(); if (!usuario) S.toast('Tu sesión expiró. Continúa con Google para sincronizar.', { tipo: 'info', ms: 7000, clave: 'cuenta' }); }
            // sin conexión: queda pendiente y se reintenta al volver la señal
        }
    }
    window.addEventListener('online', () => { if (usuario) verificar().then(() => [...pendientes].forEach(empujar)); else if (!enOperacion) verificar(); });
    // Al volver a esta pestaña se comprueba quién tiene la sesión (otra pestaña pudo entrar o salir): lo que llegue se compara con la generación con que empezó.
    document.addEventListener('visibilitychange', () => { if (!document.hidden && !enOperacion) verificar(); });

    const idDe = (x) => x.id;
    function fusionar(clave, locales, remotos) {
        const mapa = new Map();
        const cerca = (a, b) => Math.abs(a.lat - b.lat) < 0.0002 && Math.abs(a.lng - b.lng) < 0.0002;
        [...remotos, ...locales].forEach((x) => {
            if (!x || mapa.has(idDe(x))) return;
            if (clave === 'lugares' && [...mapa.values()].some((y) => y.nombre.toLowerCase() === x.nombre.toLowerCase() && cerca(y, x))) return;
            mapa.set(idDe(x), x);
        });
        let lista = [...mapa.values()];
        if (clave === 'historial' || clave === 'viajes') lista.sort((a, b) => (b.t || 0) - (a.t || 0));
        return lista.slice(0, MAXIMO[clave]);
    }
    /**
     * Sincroniza con la cuenta. {@code alEntrar}: une lo de este dispositivo con lo de la cuenta (nada se pierde).
     * Al abrir la app: manda lo que haya pendiente de subir y, del resto, lo del servidor manda.
     * Cada espera comprueba que la sesión sigue siendo la misma: si cambió (cerró sesión, entró otra persona), lo que llegó NO se aplica.
     */
    async function sincronizar({ alEntrar = false } = {}) {
        if (!usuario || sinVerificar) return;
        const gen = generacion;
        let remoto;
        try { remoto = await pedir('/api/cuenta/datos'); } catch { return; }
        if (gen !== generacion || !usuario) return;
        await refrescarLugares();
        for (const clave of Object.keys(LOCAL)) {
            if (clave === 'lugares') continue;      // los lugares de la cuenta no se fusionan con los del invitado (Fase C)
            if (gen !== generacion || !usuario) return;
            const local = Datos.leer(clave), doc = remoto[clave]?.valor;
            if (alEntrar) {
                const unida = fusionar(clave, local, Array.isArray(doc) ? doc : []);
                Datos.escribir(clave, unida, { remoto: false });
                if (JSON.stringify(unida) !== JSON.stringify(doc)) await empujar(clave).catch(() => {});
                else { pendientes.delete(clave); guardarPendientes(); }
            } else if (pendientes.has(clave)) {
                await empujar(clave);
            } else if (Array.isArray(doc)) {
                if (JSON.stringify(doc) !== JSON.stringify(local)) Datos.escribir(clave, doc, { remoto: false });
            } else if (local.length) {
                await empujar(clave);
            }
        }
    }

    // ------------------------------------------------------------------ sesión
    /** Enlaces de administración (editor, pasos, lugares, reportes): nacen ocultos (atributo hidden en el HTML).
     *  Solo se muestran si la sesión verificada es de administrador.
     *  Estado desconocido, tiempo agotado o error: siguen ocultos. Solo se usa un valor anterior si en su momento lo confirmó el servidor.
     *  Esto es solo presentación: el servidor valida cada operación de administración. */
    async function aplicarAdmin() {
        const cfg = await cargarConfig();
        let hay = null;                                           // null = desconocido
        if (cfg && typeof cfg.adminConfigurado === 'boolean') { hay = cfg.adminConfigurado; escribir('spevb-admin-conf', hay); }
        else { const previo = leer('spevb-admin-conf', null); if (typeof previo === 'boolean') hay = previo; }
        const esAdmin = !!(usuario && usuario.admin) && !sinVerificar;
        const ver = esAdmin;      // solo una sesión VERIFICADA de administrador ve estos enlaces (sin administradores configurados ya no se muestran a nadie)
        document.querySelectorAll('.admin-only').forEach((el) => { el.hidden = !ver; });
    }
    function cambio() {
        evento('spevb-cuenta', { usuario });
        pintarMenu();
        aplicarAdmin();
    }
    /** Quita los datos personales de ESTE dispositivo (siguen en la cuenta) y cancela todo envío pendiente. */
    function limpiarLocalPersonal() {
        Object.values(empujes).forEach(clearTimeout);
        Object.keys(LOCAL).forEach((c) => { if (c !== 'lugares') { try { localStorage.removeItem(LOCAL[c]); } catch { /* nada */ } } evento('spevb-datos', { clave: c }); });
        try { localStorage.removeItem(K_LUG); } catch { /* nada */ }      // la copia de lugares de la cuenta se va; los lugares de un invitado (si los hay) no son de la cuenta y se quedan
        ['spevb-recientes', 'spevb-caminatas', K_PENDIENTES, 'spevb-logros-cuenta', 'spevb-logros-cola'].forEach((k) => { try { localStorage.removeItem(k); } catch { /* nada */ } });
        quitarResumenesDeCuenta();
        pendientes.clear();
        evento('spevb-recientes');
    }
    function cerrarLocal() {
        fijarUsuario(null); sinVerificar = false; cuentaAnterior = false;
        try { localStorage.removeItem(K_USUARIO); } catch { /* nada */ }
        limpiarLocalPersonal();
        cambio();
    }
    /** La cookie de este navegador era de una cuenta ANTIGUA con contraseña: ya no vale como sesión, pero esos datos no se borran de este dispositivo (pueden ser lo único que hay a la mano). */
    /** Fase D: los resúmenes de la semana y los envíos pendientes de logros de una cuenta se van con ella; lo del invitado («g») se queda. */
    function quitarResumenesDeCuenta() {
        try { const l = JSON.parse(localStorage.getItem('spevb-viajes-resumen') || '[]'); localStorage.setItem('spevb-viajes-resumen', JSON.stringify(l.filter((x) => x && x.a === 'g'))); } catch { /* nada */ }
    }
    function dejarSesionAnterior() {
        fijarUsuario(null); sinVerificar = false; cuentaAnterior = true;
        try { localStorage.removeItem(K_USUARIO); localStorage.removeItem(K_LUG); localStorage.removeItem('spevb-logros-cuenta'); localStorage.removeItem('spevb-logros-cola'); } catch { /* nada */ }
        quitarResumenesDeCuenta();
        Object.values(empujes).forEach(clearTimeout);
        pendientes.clear(); guardarPendientes();
        cambio();
    }
    async function verificar() {
        const gen = generacion;
        try {
            const r = await pedir('/api/cuenta/yo', { espera: 8000 });
            if (gen !== generacion || enOperacion) return;      // la sesión cambió mientras se comprobaba: esa respuesta ya no vale
            sinVerificar = false; verificado = true;
            if (r.autenticado) { fijarUsuario(r.usuario); cuentaAnterior = !!r.cuentaAnterior; escribir(K_USUARIO, usuario); }
            else if (r.motivo === 'cuenta-anterior') dejarSesionAnterior();
            else if (usuario || leer(K_USUARIO, null)) cerrarLocal();
            else cuentaAnterior = false;
        } catch {
            if (gen !== generacion) return;
            const cache = leer(K_USUARIO, null);
            if (cache && !usuario) { fijarUsuario(cache); sinVerificar = true; }
        }
        cambio();
    }
    /** Pasa por el servidor una operación que cambia la sesión. Una a la vez: ninguna respuesta puede pisar a otra. */
    async function conBloqueo(f) {
        if (enOperacion) { const e = new Error('Hay otro cambio de sesión en curso. Espera un momento.'); e.ocupado = true; throw e; }
        enOperacion = true;
        try { return await f(); } finally { enOperacion = false; }
    }
    async function entrada(ruta, cuerpo, mensaje) {
        await conBloqueo(async () => {
            const previo = usuario;
            const r = await pedir('/api/cuenta/' + ruta, { metodo: 'POST', cuerpo });
            // Si había OTRA persona en sesión, lo de este dispositivo es suyo: no se mezcla con la cuenta que entra.
            if (previo && idDeUsuario(previo) !== idDeUsuario(r.usuario)) limpiarLocalPersonal();
            fijarUsuario(r.usuario); sinVerificar = false; cuentaAnterior = !!r.cuentaAnterior;
            escribir(K_USUARIO, usuario);
            cambio();
        });
        // La sesión ya está abierta: el diálogo se cierra y la sincronización sigue en segundo plano (una red lenta no deja a la persona esperando ni la app bloqueada).
        sincronizar({ alEntrar: true }).catch(() => {});
        S.toast(mensaje(usuario), { tipo: 'success', ms: 4500, clave: 'cuenta' });
        return usuario;
    }
    const Cuenta = {
        get usuario() { return usuario; },
        get sinVerificar() { return sinVerificar; },
        get cuentaAnterior() { return cuentaAnterior; },
        /** Entra con la credencial que entrega el botón OFICIAL de Google (la verifica el servidor). Es lo único que abre una sesión. */
        google: (credential) => entrada('google', { credential }, (u) => '¡Hola, ' + u.nombre + '! Entraste con Google.'),
        async salir(todas = false) {
            try {
                await conBloqueo(async () => {
                    try { await pedir('/api/cuenta/salir', { metodo: 'POST', cuerpo: { todas } }); } catch { /* la cookie vence sola */ }
                    cerrarLocal();
                });
            } catch (e) { if (e.ocupado) return; throw e; }
            S.toast('Sesión cerrada. Tus datos siguen en tu cuenta.', { tipo: 'info', ms: 4000, clave: 'cuenta' });
        },
        /** Borra la cuenta. {@code credential}: credencial RECIENTE de Google de la misma cuenta (el servidor la exige y solo sirve una vez). */
        async eliminar(credential) { await conBloqueo(async () => { await pedir('/api/cuenta/eliminar', { metodo: 'POST', cuerpo: { credential } }); cerrarLocal(); }); },
        /** Vínculo explícito de una cuenta ANTERIOR con contraseña (apagado en el servidor salvo que el proyecto lo habilite; sin pantalla pública). Comprueba las dos cuentas. */
        vincularAnterior: (credential, correo, clave) => entrada('vinculo-anterior', { credential, correo, clave }, (u) => 'Tu cuenta anterior quedó vinculada a Google, ' + u.nombre + '.'),
        pedirEntrada: (o) => pedirEntrada(o),
        /** ¿Hay una sesión comprobada con el servidor (no solo el último usuario recordado)? Guardar un lugar exige esto. */
        get sesionValida() { return !!usuario && !sinVerificar; },
        /** Fase D: identidad y generación de la sesión actuales (para descartar respuestas de otra cuenta o de una sesión anterior) y el pedido autenticado. */
        get generacion() { return generacion; },
        uid: () => idDeUsuario(usuarioVisible()),
        pedir: (ruta, opciones) => pedir(ruta, opciones),
        /** Para funciones que necesitan cuenta (p. ej. lugares privados): devuelve el usuario, abriendo «Continuar con Google» solo si hace falta, o null si decide seguir sin cuenta. */
        requiere: (motivo) => (usuario ? Promise.resolve(usuario) : pedirEntrada({ motivo })),
        sincronizar,
    };
    S.Datos = Datos;
    S.Cuenta = Cuenta;
    /** Lugares de la CUENTA (Fase C): lectura de la copia de esta cuenta y escritura confirmada por el servidor. Con invitado, {@code disponible()} es false y {@code vivos()} da los de este dispositivo. */
    S.LugaresCuenta = { vivos: () => Datos.leer('lugares'), mutar: mutarLugares, refrescar: refrescarLugares, disponible: () => !!usuario && !sinVerificar, deCuenta: () => !!usuarioVisible() };
    window.addEventListener('storage', (e) => {      // otra pestaña del mismo navegador cambió de sesión o de lugares: esta lo comprueba, nunca supone
        if (e.key === K_USUARIO && !enOperacion) verificar();
        else if (e.key === K_LUG) evento('spevb-datos', { clave: 'lugares' });
    });

    // ------------------------------------------------------------------ avatar (foto de Google con respaldo local)
    /** Mismo criterio que el servidor: HTTPS y un subdominio de googleusercontent.com. Cualquier otra cosa se ignora (queda el avatar local). */
    function fotoValida(url) {
        if (typeof url !== 'string' || url.length > 512) return null;
        try { const u = new URL(url); return u.protocol === 'https:' && !u.username && !u.port && /(^|\.)googleusercontent\.com$/i.test(u.hostname) ? u.href : null; } catch { return null; }
    }
    /** Pone (o quita) la foto sobre el avatar local. Cada llamada invalida las cargas anteriores de ese círculo: al cerrar sesión o cambiar de cuenta, una foto
     *  que llega tarde nunca se muestra en lugar de la actual. La foto se pide solo cuando el perfil se va a ver (menú o ajustes abiertos). */
    const fotosFallidas = new Set();        // fotos de Google que ya fallaron en esta vista: no se vuelven a pedir
    const regionalesRotos = new Set();      // imágenes regionales que no cargaron (caso excepcional): queda el chigüiro local
    function pintarAvatar(el, u) {
        if (!el) return;
        let url = u ? fotoValida(u.foto) : null;
        if (url && fotosFallidas.has(url)) url = null;
        // Avatar regional estable (si hay imágenes en el manifiesto): se pinta de inmediato, antes de intentar la foto de Google.
        let reg = u && S.Avatares ? S.Avatares.para(u.id != null ? 'id:' + u.id : u.correo) : null;
        if (reg && regionalesRotos.has(reg.archivo)) reg = null;
        const clave = (url ? u.correo + '|' + url : '') + (reg ? '#' + reg.archivo : '');
        if (el.dataset.clave === clave && (url ? el.querySelector('img') : !el.firstChild)) return;       // ya está así: no se vuelve a pedir
        el.dataset.clave = clave;
        const turno = (el._turno = (el._turno || 0) + 1);
        el.classList.remove('con-foto');
        el.replaceChildren();
        el.classList.toggle('con-regional', !!reg);
        if (reg) el.style.setProperty('--avatar-regional', 'url("' + reg.url + '")'); else el.style.removeProperty('--avatar-regional');
        el.dataset.avatar = reg ? reg.archivo : '';
        if (reg) {      // si el regional no carga (caso excepcional), vuelve el chigüiro local; nunca una imagen rota
            const prueba = new Image();
            prueba.onerror = () => { regionalesRotos.add(reg.archivo); if (el._turno === turno) { el.classList.remove('con-regional'); el.style.removeProperty('--avatar-regional'); el.dataset.avatar = ''; } };
            prueba.src = reg.url;
        }
        if (!url || navigator.onLine === false) return;
        const img = new Image();
        img.alt = ''; img.width = 40; img.height = 40; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
        img.onload = () => { if (el._turno === turno && el.contains(img)) el.classList.add('con-foto'); };
        img.onerror = () => { fotosFallidas.add(url); if (el._turno === turno) { img.remove(); el.classList.remove('con-foto'); el.dataset.clave = (reg ? '#' + reg.archivo : ''); } };      // sin foto: se queda el avatar regional (o el chigüiro)
        el.append(img);
        img.src = url;
    }
    const perfilVisible = () => !!document.getElementById('sideMenu')?.classList.contains('open') || !$('settingsModal')?.hidden;
    function pintarAvatares() {
        const u = usuario;
        const visibleMenu = !!document.getElementById('sideMenu')?.classList.contains('open'), visibleAjustes = !!$('settingsModal') && !$('settingsModal').hidden;
        if (!u) { pintarAvatar($('accountAvatar'), null); pintarAvatar($('setAvatar'), null); return; }
        if (visibleMenu) pintarAvatar($('accountAvatar'), u); else if ($('accountAvatar')?.dataset.clave && !$('accountAvatar').dataset.clave.startsWith(u.correo + '|')) pintarAvatar($('accountAvatar'), null);
        if (visibleAjustes) pintarAvatar($('setAvatar'), u); else if ($('setAvatar')?.dataset.clave && !$('setAvatar').dataset.clave.startsWith(u.correo + '|')) pintarAvatar($('setAvatar'), null);
    }
    window.addEventListener('spevb-superficies', () => { if (usuario && perfilVisible()) pintarAvatares(); });
    function pintarMenu() {
        if (!$('accountGuest')) return;
        $('accountGuest').hidden = !!usuario;
        $('accountUser').hidden = !usuario;
        if (usuario) {
            $('accountName').textContent = usuario.nombre;
            $('accountEmail').textContent = usuario.correo + ' · Google' + (sinVerificar ? ' · sin conexión' : '');
        }
        pintarAvisoAnterior();
        pintarAvatares();
    }
    /** Aviso de «cuenta anterior»: sus datos NO se unen solos a la cuenta de Google (un correo no demuestra propiedad); se dice cómo pedir la recuperación. Solo texto: nada de contraseñas aquí. */
    function pintarAvisoAnterior() {
        const p = $('accountAnterior'); if (!p) return;
        p.hidden = !cuentaAnterior;
        if (!cuentaAnterior) return;
        const soporte = config && config.soporte;
        p.replaceChildren(document.createTextNode('Tenías una cuenta anterior con contraseña. Sus datos siguen guardados, pero por seguridad no se unen solos a tu cuenta de Google. Para recuperarlos, '));
        if (soporte) { const a = document.createElement('a'); a.href = 'mailto:' + soporte; a.textContent = 'escribe a ' + soporte; p.append(a, document.createTextNode('.')); }
        else p.append(document.createTextNode('pide la recuperación al equipo de SEVB.'));
        if (!config) cargarConfig().then((c) => { if (c && c.soporte && cuentaAnterior) pintarAvisoAnterior(); });
    }
    // Apertura, foco, Escape, fondo inerte y regreso del foco: controlador único (modales.js).
    const abrir = (el, opciones) => S.Modal.abrir(el, { fondo: true, ...opciones });
    const cerrar = (el) => S.Modal.cerrar(el);
    const cerrarMenu = () => { try { $('closeMenu')?.click(); } catch { /* nada */ } };

    // ------------------------------------------------------------------ Google (el control OFICIAL; solo se carga cuando la persona lo pide)
    let config = null, googleListo = null, googleIniciado = null, proposito = 'entrar';
    /** Datos públicos de /api/cuenta/config. Si falla no se guarda nada: el próximo intento (Reintentar) vuelve a preguntar. */
    async function cargarConfig(forzar = false) {
        if (config && !forzar) return config;
        try { config = await pedir('/api/cuenta/config', { espera: 6000 }); } catch { config = null; }
        return config;
    }
    function cargarScriptGoogle(forzar = false) {
        if (window.google?.accounts?.id) return Promise.resolve();
        if (googleListo && !forzar) return googleListo;
        document.querySelectorAll('script[data-gsi]').forEach((s) => s.remove());
        googleListo = new Promise((ok, fallo) => {
            const el = document.createElement('script');
            el.src = 'https://accounts.google.com/gsi/client'; el.async = true; el.dataset.gsi = '1';
            const t = setTimeout(() => { googleListo = null; fallo(new Error('tiempo')); }, 10000);      // un bloqueo silencioso no deja el diálogo esperando para siempre
            el.onload = () => { clearTimeout(t); if (window.google?.accounts?.id) ok(); else { googleListo = null; fallo(new Error('sin api')); } };
            el.onerror = () => { clearTimeout(t); googleListo = null; fallo(new Error('Sin Google')); };
            document.head.append(el);
        });
        return googleListo;
    }
    const enDireccionTemporal = () => /\.(trycloudflare\.com|loca\.lt|lhr\.life|serveo\.net)$/i.test((window.__spevbPruebas && window.__spevbPruebas.hostname) || location.hostname);      // __spevbPruebas.hostname: solo para pruebas de navegador
    /** Prepara el botón oficial de Google dentro de {@code contenedor}. {@code estado(tipo, texto, { reintentar, oficial })} informa cada paso (cargando, listo o un error con salida);
     *  {@code vigente()} dice si lo que se está preparando sigue siendo lo que la persona tiene abierto (si no, se abandona sin tocar nada). */
    async function montarGoogle({ contenedor, ancho, vigente, estado, forzar = false }) {
        estado('cargando', 'Preparando el acceso con Google…');
        const cfg = await cargarConfig(forzar);
        if (!vigente()) return false;
        if (enDireccionTemporal()) {
            estado('origen', 'Entrar con Google no está disponible en esta dirección temporal: Google solo acepta la dirección oficial de SEVB.' + (cfg && cfg.direccionOficial ? '' : ' Pide a quien te compartió el enlace la dirección oficial.'), { reintentar: false, oficial: cfg && cfg.direccionOficial });
            return false;
        }
        if (!cfg) { estado(navigator.onLine === false ? 'sin-conexion' : 'sin-servidor', navigator.onLine === false ? 'Sin conexión: necesitas internet para entrar con Google.' : 'No pude comunicarme con SEVB para preparar el acceso. Revisa tu conexión e inténtalo de nuevo.', { reintentar: true }); return false; }
        if (!cfg.google) { estado('no-configurado', 'El acceso con Google todavía no está configurado en este servidor.', { reintentar: true }); return false; }
        if (navigator.onLine === false) { estado('sin-conexion', 'Sin conexión: necesitas internet para entrar con Google.', { reintentar: true }); return false; }
        try { await cargarScriptGoogle(forzar); }
        catch { if (vigente()) estado('bloqueado', 'Google no cargó. Puede que un bloqueador de anuncios o de privacidad, o la red, lo esté impidiendo.', { reintentar: true }); return false; }
        if (!vigente()) return false;
        try {
            if (googleIniciado !== cfg.google) {
                window.google.accounts.id.initialize({
                    client_id: cfg.google, ux_mode: 'popup', auto_select: false, cancel_on_tap_outside: true, itp_support: true,
                    callback: (resp) => alCredencial(resp && resp.credential),
                });
                googleIniciado = cfg.google;
            }
            contenedor.replaceChildren();
            window.google.accounts.id.renderButton(contenedor, { type: 'standard', theme: 'outline', size: 'large', text: 'continue_with', shape: 'pill', locale: 'es', logo_alignment: 'left', width: ancho() });
        } catch { if (vigente()) estado('bloqueado', 'No pude mostrar el botón de Google. Inténtalo de nuevo.', { reintentar: true }); return false; }
        estado('listo', 'Toca el botón de Google para continuar.');
        return true;
    }
    /** Credencial que entrega Google. Un único callback (Google no permite quitarlo): reparte según lo que la persona esté haciendo y descarta lo que llegue fuera de lugar. */
    function alCredencial(credential) {
        if (!credential || typeof credential !== 'string') return;
        if (proposito === 'borrar') return alCredencialBorrar(credential);
        return alCredencialEntrar(credential);
    }

    // ------------------------------------------------------------------ diálogo «Continuar con Google»
    const auth = { abierto: false, turno: 0, usuarioId0: null, enCurso: false };
    const esperas = [];       // quienes esperan el resultado de pedirEntrada()
    const vigenteAuth = (t) => auth.abierto && auth.turno === t;
    function resolverEntrada(u) { while (esperas.length) esperas.shift()(u || null); }
    function estadoAuth(tipo, texto, { reintentar = false, oficial = null } = {}) {
        const caja = $('authEstado');
        caja.dataset.estado = tipo; caja.textContent = texto;
        caja.setAttribute('aria-busy', String(tipo === 'cargando' || tipo === 'entrando'));
        $('googleBox').hidden = tipo !== 'listo';
        $('authReintentar').hidden = !reintentar;
        $('authCancel').disabled = tipo === 'entrando';
        const ayuda = $('authAyuda');
        ayuda.replaceChildren(); ayuda.hidden = true;
        if (oficial) {
            try {
                const u = new URL(oficial);
                const a = document.createElement('a'); a.href = u.href; a.rel = 'noopener noreferrer'; a.textContent = 'Abrir ' + u.host;
                ayuda.append(document.createTextNode('Dirección oficial: '), a); ayuda.hidden = false;
            } catch { /* una dirección ilegible no se muestra */ }
        }
    }
    function motivoAuth(motivo) {
        const p = $('authMotivo');
        p.textContent = typeof motivo === 'string' ? motivo.slice(0, 160) : '';
        p.hidden = !p.textContent;
    }
    function prepararAuth() {
        const turno = ++auth.turno;
        montarGoogle({ contenedor: $('googleBtn'), ancho: () => Math.max(200, Math.min(340, ($('authCard').clientWidth || 340) - 48)), vigente: () => vigenteAuth(turno), estado: estadoAuth, forzar: false });
    }
    /** Abre «Continuar con Google». Devuelve una promesa con el usuario (o null si la persona sigue sin cuenta): ver Spevb.Cuenta.pedirEntrada. */
    function pedirEntrada({ motivo } = {}) {
        if (usuario) return Promise.resolve(usuario);
        const promesa = new Promise((r) => { esperas.push(r); });
        abrirAuth({ motivo });
        return promesa;
    }
    function abrirAuth({ motivo } = {}) {
        if (!$('authModal') || usuario) return;
        if (auth.abierto) { motivoAuth(motivo); try { $('authCard').focus({ preventScroll: true }); } catch { /* nada */ } return; }
        cerrarMenu();
        auth.abierto = true; auth.enCurso = false; auth.usuarioId0 = idDeUsuario(usuario); proposito = 'entrar';
        motivoAuth(motivo);
        abrir($('authModal'), { foco: () => $('authCard'), cerrar: cancelarAuth, alCerrar: finAuth });
        prepararAuth();
    }
    /** «Seguir sin cuenta», Escape o el fondo: cierra sin entrar (la app sigue disponible como invitado). Mientras un inicio de sesión viaja al servidor no se puede cerrar. */
    function cancelarAuth() { if (auth.enCurso) return; cerrar($('authModal')); }
    /** Se llama SIEMPRE que el diálogo se cierra (por la vía que sea): invalida todo lo pendiente de ESTE diálogo. */
    function finAuth() {
        auth.abierto = false; auth.turno++; auth.enCurso = false;
        $('googleBtn').replaceChildren();
        resolverEntrada(usuario);
    }
    async function alCredencialEntrar(credential) {
        // Llegó después de cerrar el diálogo, mientras otra entrada viaja al servidor, o con otra persona ya en sesión: se ignora (nada se aplica a otra cuenta).
        if (!auth.abierto || auth.enCurso || auth.usuarioId0 !== idDeUsuario(usuario)) return;
        const turno = auth.turno;
        auth.enCurso = true; estadoAuth('entrando', 'Entrando con Google…');
        try {
            await Cuenta.google(credential);
            auth.enCurso = false;
            if (auth.turno === turno) cerrar($('authModal'));
        } catch (err) {
            auth.enCurso = false;
            if (!vigenteAuth(turno)) return;
            estadoAuth('error', err.offline ? 'Sin conexión: necesitas internet para entrar con Google.' : (err.message || 'No pudimos entrar con Google.'), { reintentar: true });
        }
    }
    // Un cambio de quién está en sesión con el diálogo abierto (otra pestaña, una comprobación tardía): se cierra, nunca queda una sesión a medias.
    window.addEventListener('spevb-cuenta', () => { if (auth.abierto && !auth.enCurso && auth.usuarioId0 !== idDeUsuario(usuario)) cerrar($('authModal')); });

    // ------------------------------------------------------------------ eliminar la cuenta: reautenticación reciente con Google (misma cuenta) y una confirmación final
    const borrado = { activo: false, turno: 0, usuarioId0: null, credencial: null, t: 0, enCurso: false };
    const VIGENCIA_CONFIRMACION_MS = 4 * 60 * 1000;       // el servidor acepta credenciales de hasta 5 minutos
    const msgBorrado = (t, clase = 'muted') => { $('setMsg').textContent = t; $('setMsg').className = clase; };
    function estadoBorrado(tipo, texto, { reintentar = false } = {}) {
        $('setDelTexto').textContent = texto;
        $('setDelTexto').dataset.estado = tipo;
        $('delGoogleBox').hidden = tipo !== 'listo';
        $('setDelReintentar').hidden = !reintentar;
        $('setDelConfirmar').hidden = tipo !== 'confirmar';
    }
    function pedirReautenticacion(forzar = false) {
        const turno = ++borrado.turno;
        montarGoogle({
            contenedor: $('delGoogleBtn'), ancho: () => Math.max(200, Math.min(320, ($('setDelPaso').clientWidth || 320) - 8)),
            vigente: () => borrado.activo && borrado.turno === turno, estado: (t, x, o) => estadoBorrado(t, t === 'listo' ? 'Para borrar tu cuenta, confirma que eres tú con Google. Se borrarán tus lugares, viajes guardados, rutas favoritas e historial. No se puede deshacer.' : x, o), forzar,
        });
    }
    function abrirBorrado() {
        if (borrado.activo) return;
        borrado.activo = true; borrado.usuarioId0 = idDeUsuario(usuario); borrado.credencial = null; proposito = 'borrar';
        $('setDelPaso').hidden = false; $('setDelete').hidden = true; msgBorrado('');
        pedirReautenticacion();
    }
    /** Cancela el borrado (o termina el flujo): descarta la credencial y vuelve el propósito normal. */
    function cerrarBorrado() {
        borrado.activo = false; borrado.turno++; borrado.credencial = null; borrado.enCurso = false;
        if (proposito === 'borrar') proposito = 'entrar';
        if ($('setDelPaso')) { $('setDelPaso').hidden = true; $('setDelete').hidden = false; $('delGoogleBtn').replaceChildren(); }
    }
    function alCredencialBorrar(credential) {
        if (!borrado.activo || borrado.enCurso || borrado.usuarioId0 !== idDeUsuario(usuario)) return;       // tarde, repetida o de otra sesión: nada
        borrado.credencial = credential; borrado.t = Date.now();
        estadoBorrado('confirmar', 'Google confirmó tu identidad. ¿Eliminar tu cuenta para siempre? No se puede deshacer.');
        msgBorrado('Identidad confirmada con Google.');
        try { $('setDelCancelar').focus({ preventScroll: true }); } catch { /* nada */ }      // la opción segura recibe el foco
    }
    async function confirmarBorrado() {
        if (!borrado.activo || !borrado.credencial || borrado.enCurso) return;
        if (Date.now() - borrado.t > VIGENCIA_CONFIRMACION_MS) { borrado.credencial = null; msgBorrado('La confirmación venció. Confirma de nuevo con Google.', 'error-msg'); pedirReautenticacion(); return; }
        const credencial = borrado.credencial, turno = borrado.turno;
        borrado.enCurso = true; borrado.credencial = null; $('setDelConfirmar').disabled = true; msgBorrado('Eliminando tu cuenta…');
        try {
            await Cuenta.eliminar(credencial);
            cerrarBorrado(); cerrar($('settingsModal'));
            S.toast('Cuenta eliminada.', { tipo: 'info', ms: 5000, clave: 'cuenta' });
        } catch (err) {
            borrado.enCurso = false;
            if (!borrado.activo || borrado.turno !== turno) return;
            msgBorrado(err.offline ? 'Sin conexión: tu cuenta NO se borró. Inténtalo de nuevo.' : (err.message || 'No se pudo eliminar la cuenta.'), 'error-msg');
            pedirReautenticacion();
        } finally { $('setDelConfirmar').disabled = false; }
    }

    // ------------------------------------------------------------------ menú, ajustes y arranque
    function iniciarUI() {
        if (!$('authModal')) return;
        $('accountLogin').onclick = () => { pedirEntrada({}); };
        document.querySelectorAll('[data-abrir-cuenta]').forEach((b) => { b.onclick = () => { pedirEntrada({}); }; });
        $('authCancel').onclick = cancelarAuth;
        $('authReintentar').onclick = () => { if (auth.enCurso || !auth.abierto) return; auth.turno++; prepararReintento(); };
        $('accountLogout').onclick = () => { cerrarMenu(); Cuenta.salir(false); };
        $('accountSettings').onclick = () => {
            cerrarMenu();
            $('setName').textContent = usuario?.nombre || ''; $('setEmail').textContent = usuario?.correo || '';
            msgBorrado('');
            cerrarBorrado();
            abrir($('settingsModal'), { foco: () => $('setAll'), alCerrar: cerrarBorrado });
            pintarAvatares();
        };
        $('settingsClose').onclick = () => cerrar($('settingsModal'));
        $('setAll').onclick = async () => { cerrar($('settingsModal')); await Cuenta.salir(true); };
        $('setDelete').onclick = abrirBorrado;
        $('setDelCancelar').onclick = () => { cerrarBorrado(); msgBorrado('Tu cuenta sigue como estaba.'); try { $('setDelete').focus({ preventScroll: true }); } catch { /* nada */ } };
        $('setDelReintentar').onclick = () => { if (borrado.activo && !borrado.enCurso) pedirReautenticacion(true); };
        $('setDelConfirmar').onclick = confirmarBorrado;
        pintarMenu();
    }
    /** «Reintentar»: vuelve a preguntar la configuración y a cargar el script (sin recargar la página). */
    function prepararReintento() {
        const turno = auth.turno;
        montarGoogle({ contenedor: $('googleBtn'), ancho: () => Math.max(200, Math.min(340, ($('authCard').clientWidth || 340) - 48)), vigente: () => vigenteAuth(turno), estado: estadoAuth, forzar: true });
    }
    iniciarUI();

    // Al abrir la app: se comprueba la sesión y, si hay, se sincroniza. Los datos locales ya están disponibles desde el principio.
    S.Cuenta.listo = verificar().then(() => sincronizar());
})();
