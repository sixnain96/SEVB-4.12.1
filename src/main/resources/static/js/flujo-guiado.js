'use strict';
/* Flujo guiado de planificación (4.15): UNA decisión por pantalla, sobre el planificador REAL.
   · No es un planificador paralelo: usa los mismos campos, la misma búsqueda, el mismo GPS, el mismo mapa y el mismo modo viaje (Spevb.Planner, #tripOrigin, #tripDestination…).
     Los puntos elegidos siguen viviendo en planner.js (una sola fuente de verdad): este módulo solo decide qué se muestra y qué se pregunta en cada momento.
   · Máquina de estados explícita (PASOS / TRANSICIONES): destino → confirmar_destino → origen → confirmar_origen → resumen → calculando → recomendacion → viaje.
     Una transición inválida se ignora (y se registra en la consola de desarrollo); retroceder conserva los datos del otro extremo.
   · Modo avanzado: «Modo avanzado» muestra el planificador completo de siempre; «Modo guiado» vuelve. La preferencia se guarda en este dispositivo ('spevb-modo-planificador').
   · Al recargar no se guarda ninguna dirección ni coordenada: el paso se DEDUCE del estado real (viaje en curso, opción elegida, puntos cargados desde un enlace…). */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const $ = (id) => document.getElementById(id);
    const panel = document.querySelector('.trip-panel');
    if (!panel || !$('tripDestination') || !$('tripOrigin') || !S.Planner) return;

    const CLAVE_MODO = 'spevb-modo-planificador';
    const PASOS = ['destino', 'confirmar_destino', 'origen', 'confirmar_origen', 'resumen', 'calculando', 'recomendacion', 'viaje'];
    const TRANSICIONES = {
        destino: ['confirmar_destino', 'resumen', 'recomendacion', 'viaje'],
        confirmar_destino: ['destino', 'origen', 'resumen'],
        origen: ['destino', 'confirmar_origen', 'resumen'],
        confirmar_origen: ['origen', 'resumen'],
        resumen: ['destino', 'origen', 'calculando', 'recomendacion', 'viaje'],
        calculando: ['resumen', 'recomendacion', 'viaje', 'destino'],
        recomendacion: ['resumen', 'calculando', 'viaje', 'destino', 'origen'],
        viaje: ['destino', 'resumen', 'recomendacion'],
    };
    const INDICADOR = { destino: 0, confirmar_destino: 0, origen: 1, confirmar_origen: 1, resumen: 2, calculando: 2, recomendacion: 2, viaje: 2 };
    const MUY_CERCA_M = 60;

    // El planificador con A y B es el ÚNICO que ve la persona: el paso a paso ya no se ofrece ni se recuerda entre visitas. Solo la práctica del tutorial lo usa de forma temporal
    // (su botón del menú queda oculto) y las pruebas pueden activarlo con la bandera de desarrollo 'spevb-guiado-habilitado' (nunca la pone la interfaz).
    const habilitado = () => { try { return localStorage.getItem('spevb-guiado-habilitado') === '1'; } catch { return false; } };
    const leerModo = () => { try { return habilitado() && localStorage.getItem(CLAVE_MODO) === 'guiado' ? 'guiado' : 'avanzado'; } catch { return 'avanzado'; } };
    const guardarModo = (m) => { try { if (habilitado()) localStorage.setItem(CLAVE_MODO, m); } catch { /* sin almacenamiento */ } };
    let modo = leerModo(), paso = 'destino', escribiendoOrigen = false, montado = false, interaccion = false;

    const puntos = () => S.Planner.puntos();
    const distancia = (a, b) => (S.Geo && S.Geo.distancia ? S.Geo.distancia([a.lat, a.lng], [b.lat, b.lng]) : Math.hypot((a.lat - b.lat) * 111000, (a.lng - b.lng) * 111000));
    const referencia = (p) => { const d = (p && (p.direccion || p.barrio || p.sector || '')) || ''; return d && d !== p.nombre ? d : ''; };
    const nombreRuta = (c) => (S.rutaNombre ? S.rutaNombre(c) : c);

    // ------------------------------------------------------------------ estructura
    const bloqueOrigen = $('tripOrigin').closest('.endpoint-block'), bloqueDestino = $('tripDestination').closest('.endpoint-block');
    if (bloqueOrigen) bloqueOrigen.classList.add('g-bloque-origen');
    if (bloqueDestino) bloqueDestino.classList.add('g-bloque-destino');

    const raiz = document.createElement('section');
    raiz.id = 'guiado'; raiz.className = 'guiado'; raiz.setAttribute('aria-labelledby', 'guiadoTitulo');
    raiz.innerHTML = `
        <ol class="guiado-pasos" id="guiadoPasos" aria-label="Pasos para planear tu viaje">
            <li data-i="0"><span>1</span> Destino</li><li data-i="1"><span>2</span> Origen</li><li data-i="2"><span>3</span> Confirmar</li>
        </ol>
        <h2 id="guiadoTitulo" class="guiado-titulo" tabindex="-1"></h2>
        <p id="guiadoAyuda" class="guiado-ayuda"></p>`;
    panel.prepend(raiz);
    // La parte de acciones va DESPUÉS del campo real del planificador (#formAB): pregunta → campo → botones.
    const acciones = document.createElement('section');
    acciones.id = 'guiadoAcciones'; acciones.className = 'guiado guiado-acciones'; acciones.setAttribute('aria-label', 'Acciones de este paso');
    acciones.innerHTML = `
        <div id="guiadoCuerpo" class="guiado-cuerpo"></div>
        <div id="guiadoMensaje" class="guiado-mensaje" role="status" aria-live="polite" hidden></div>
        <div class="guiado-pie">
            <button type="button" id="guiadoAyudaBtn" class="guiado-enlace">Necesito ayuda</button>
            <button type="button" id="guiadoVoz" class="guiado-enlace" hidden>Leer instrucciones en voz alta</button>
            <button type="button" id="guiadoAvanzado" class="guiado-enlace">Usar el planificador con A y B</button>
        </div>`;
    $('formAB').after(acciones);
    const ocultarTodo = (v) => { raiz.hidden = v; acciones.hidden = v; };

    // Entrada APARTE en el menú lateral: «Planear paso a paso» (modo guiado) / «Usar el planificador con A y B» (el de siempre).
    const entrada = document.createElement('button');
    entrada.type = 'button'; entrada.id = 'menuPasoAPaso'; entrada.className = 'secondary menu-inicio';
    entrada.hidden = true;      // sin entrada visible: el paso a paso ya no se ofrece (la práctica del tutorial pulsa este botón por código)
    if ($('menuInicio')) $('menuInicio').after(entrada);
    function pintarEntrada() {
        const guiado = modo === 'guiado';
        entrada.textContent = guiado ? 'Usar el planificador con A y B' : 'Planear paso a paso';
        entrada.setAttribute('aria-label', guiado ? 'Volver al planificador con origen A y destino B' : 'Planear tu viaje paso a paso, con una pregunta por pantalla');
    }
    const volver = { hidden: true, focus() {} };       // compatibilidad: ya no hay botón dentro del panel

    const el = { titulo: $('guiadoTitulo'), ayuda: $('guiadoAyuda'), cuerpo: $('guiadoCuerpo'), mensaje: $('guiadoMensaje'), pasos: $('guiadoPasos') };

    // ------------------------------------------------------------------ utilidades de interfaz
    const boton = (txt, clase, fn, extra = {}) => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'guiado-boton ' + clase; b.textContent = txt;
        if (extra.id) b.id = extra.id;
        b.addEventListener('click', () => { if (b.disabled) return; fn(); });
        return b;
    };
    const parrafo = (txt, clase = '') => { const p = document.createElement('p'); p.className = clase; p.textContent = txt; return p; };
    const lugar = (etiqueta, p) => {
        const d = document.createElement('div'); d.className = 'guiado-lugar';
        const e = document.createElement('small'); e.textContent = etiqueta;
        const n = document.createElement('strong'); n.textContent = p ? p.nombre : '—';
        d.append(e, n);
        const r = referencia(p); if (r) { const s = document.createElement('span'); s.textContent = r; d.append(s); }
        return d;
    };
    const tocar = (id) => { const b = $(id); if (b) b.click(); };

    // ------------------------------------------------------------------ máquina de estados
    function ir(nuevo, { enfocar = true } = {}) {
        if (!PASOS.includes(nuevo)) return false;
        if (nuevo === paso) { render(); return true; }
        if (!TRANSICIONES[paso].includes(nuevo)) { try { console.debug('[guiado] transición no permitida:', paso, '→', nuevo); } catch { /* nada */ } return false; }
        paso = nuevo;
        if (paso !== 'origen') escribiendoOrigen = false;
        render();
        if (enfocar && interaccion) { try { el.titulo.focus({ preventScroll: true }); } catch { /* sin foco */ } }
        return true;
    }
    /** Paso que corresponde al estado REAL del planificador y del viaje (tras recargar, enlaces compartidos, etc.). */
    function derivar() {
        if (S.Viaje && S.Viaje.activo()) return 'viaje';
        if (S.Planner.buscando && S.Planner.buscando()) return 'calculando';
        if (S.Planner.seleccion && S.Planner.seleccion.viaje) return 'recomendacion';
        const p = puntos();
        if (p.origen && p.destino) return 'resumen';
        return 'destino';
    }
    function sincronizar({ enfocar = false } = {}) {
        const d = derivar();
        const edicion = ['destino', 'confirmar_destino', 'origen', 'confirmar_origen', 'resumen'];
        if (edicion.includes(paso) && edicion.includes(d)) {
            // Mientras se arma el viaje, el paso lo decide la persona: solo se corrige si faltan los datos que ese paso necesita.
            const p = puntos();
            const ok = paso === 'destino' || (paso === 'confirmar_destino' && p.destino) || (paso === 'origen' && p.destino) || (paso === 'confirmar_origen' && p.origen && p.destino) || (paso === 'resumen' && p.origen && p.destino);
            if (ok) return render();
        }
        if (d === paso) return render();
        paso = d; if (paso !== 'origen') escribiendoOrigen = false;
        render();
        if (enfocar && interaccion) { try { el.titulo.focus({ preventScroll: true }); } catch { /* nada */ } }
    }

    // ------------------------------------------------------------------ contenido de cada paso
    let ultimaFirma = null;
    const pt = (x) => (x ? [x.nombre, x.lat, x.lng, x.direccion, x.barrio].join('~') : '');
    /** Resume TODO lo que cambia el contenido del paso actual: si la firma es igual, los botones actuales siguen siendo correctos. */
    function firmaVista(p) {
        const sel = S.Planner.seleccion, opts = document.querySelectorAll('#tripResults .trip-option');
        const it = S.Planner.itinerario && S.Planner.itinerario(), real = it ? [it.el.querySelector('.itin-porque').textContent, it.pasos().map((x) => x.texto)] : null;
        return JSON.stringify([paso, escribiendoOrigen, !!($('useMyLocation') && $('useMyLocation').disabled), pt(p.origen), pt(p.destino), sel && sel.viaje ? [sel.codigos, sel.resumen] : null,
            opts.length, document.body.classList.contains('g-todas'), navigator.onLine !== false, real]);
    }
    function render() {
        if (modo !== 'guiado') return;
        document.body.dataset.paso = paso;
        document.body.classList.toggle('g-escribiendo-origen', paso === 'origen' && escribiendoOrigen);
        const idx = INDICADOR[paso];
        el.pasos.hidden = paso === 'viaje';
        el.pasos.querySelectorAll('li').forEach((li) => {
            const i = Number(li.dataset.i);
            li.classList.toggle('hecho', i < idx); li.classList.toggle('actual', i === idx);
            if (i === idx) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
        });
        const p = puntos();
        // Si lo que se ve no cambió, NO se reconstruyen los botones: render() lo llaman muchos eventos (puntos elegidos, resultados, temporizadores del panel) y reemplazar el botón
        // entre el «toque» y el «soltar» de un dedo hace que ese toque se pierda (4.15.x: causa del fallo intermitente de «retroceder entre pasos»).
        const firma = firmaVista(p);
        if (firma === ultimaFirma && el.cuerpo.firstChild) { ocultarTodo(paso === 'viaje'); if (paso !== 'viaje') panelMedio(); return; }
        ultimaFirma = firma;
        const activo = document.activeElement && el.cuerpo.contains(document.activeElement) ? (document.activeElement.id ? '#' + document.activeElement.id : document.activeElement.dataset.clave ? '[data-clave="' + document.activeElement.dataset.clave + '"]' : null) : null;
        el.cuerpo.replaceChildren();
        if (activo) setTimeout(() => { const b = el.cuerpo.querySelector(activo); if (b && !el.cuerpo.contains(document.activeElement)) { try { b.focus({ preventScroll: true }); } catch { /* nada */ } } }, 0);
        const c = el.cuerpo;
        el.ayuda.hidden = false;
        ocultarTodo(paso === 'viaje');
        switch (paso) {
            case 'destino': {
                el.titulo.textContent = '¿A dónde quieres ir?';
                el.ayuda.textContent = 'Escribe un lugar, una dirección o el nombre de un sitio.';
                const f = document.createElement('div'); f.className = 'guiado-botones';
                f.append(boton('Buscar destino', 'primario', buscarDestino, { id: 'gBuscarDestino' }), boton('Elegir en el mapa', 'secundario', () => { tocar('pickDestination'); anunciar('Toca el mapa en el lugar al que quieres ir.'); }, { id: 'gMapaDestino' }));
                c.append(f);
                break;
            }
            case 'confirmar_destino': {
                el.titulo.textContent = '¿Este es el lugar al que quieres ir?';
                el.ayuda.textContent = 'Mira el punto marcado en el mapa.';
                c.append(lugar('Destino', p.destino));
                const f = document.createElement('div'); f.className = 'guiado-botones';
                f.append(boton('Sí, continuar', 'primario', () => ir(p.origen ? 'resumen' : 'origen'), { id: 'gSiDestino' }), boton('Cambiar destino', 'secundario', cambiarDestino, { id: 'gCambiarDestino' }));
                c.append(f);
                break;
            }
            case 'origen': {
                el.titulo.textContent = '¿Desde dónde vas a salir?';
                const busy = $('useMyLocation') && $('useMyLocation').disabled;
                el.ayuda.textContent = busy ? 'Buscando tu ubicación… Puede tardar unos segundos. Si prefieres, puedes cancelar.' : 'Elige cómo quieres decirnos dónde estás.';
                c.append(lugarResumen('Vas a', p.destino));
                const f = document.createElement('div'); f.className = 'guiado-botones';
                if (busy) {
                    f.append(boton('Cancelar', 'secundario', () => { tocar('clearOrigin'); render(); }, { id: 'gCancelarGps' }));
                } else {
                    f.append(boton('Usar mi ubicación actual', escribiendoOrigen ? 'secundario' : 'primario', () => { tocar('useMyLocation'); render(); }, { id: 'gUsarGps' }),
                        boton('Escribir una dirección', 'secundario', escribirOrigen, { id: 'gEscribirOrigen' }),
                        boton('Elegir en el mapa', 'secundario', () => { tocar('pickOrigin'); anunciar('Toca el mapa en el lugar desde el que sales.'); }, { id: 'gMapaOrigen' }));
                    if (escribiendoOrigen) f.insertBefore(boton('Buscar dirección', 'primario', buscarOrigen, { id: 'gBuscarOrigen' }), f.firstChild);
                }
                f.append(boton('Volver al destino', 'texto', cambiarDestino, { id: 'gVolverDestino' }));
                c.append(f);
                if (!busy && !escribiendoOrigen) c.append(parrafo('SEVB necesita tu ubicación para encontrar dónde tomar el bus. Se usa durante el viaje y no se guarda en el servidor.', 'guiado-nota'));
                break;
            }
            case 'confirmar_origen': {
                el.titulo.textContent = '¿Estás saliendo desde aquí?';
                el.ayuda.textContent = 'Mira el punto marcado en el mapa.';
                c.append(lugar('Origen', p.origen));
                const f = document.createElement('div'); f.className = 'guiado-botones';
                f.append(boton('Sí, continuar', 'primario', () => ir('resumen'), { id: 'gSiOrigen' }), boton('Cambiar lugar', 'secundario', cambiarOrigen, { id: 'gCambiarOrigen' }));
                c.append(f);
                break;
            }
            case 'resumen': {
                el.titulo.textContent = 'Revisa tu viaje';
                el.ayuda.textContent = '';
                el.ayuda.hidden = true;
                const par = document.createElement('div'); par.className = 'guiado-par';
                par.append(lugar('Vas desde', p.origen), lugar('Hasta', p.destino));
                c.append(par);
                const cerca = p.origen && p.destino && distancia(p.origen, p.destino) < MUY_CERCA_M;
                if (cerca) c.append(parrafo('El origen y el destino están muy cerca: puedes llegar caminando. Cambia uno de los dos lugares para buscar un bus.', 'guiado-aviso'));
                else if (navigator.onLine === false) c.append(parrafo('Sin internet: si ya consultaste este viaje antes, lo mostraremos guardado.', 'guiado-nota'));
                const f = document.createElement('div'); f.className = 'guiado-botones';
                const b = boton('Buscar cómo llegar', 'primario', buscar, { id: 'gBuscar' });
                if (cerca) b.disabled = true;
                f.append(b, boton('Cambiar origen', 'secundario', cambiarOrigen, { id: 'gCambiarOrigen2' }), boton('Cambiar destino', 'secundario', cambiarDestino, { id: 'gCambiarDestino2' }));
                c.append(f);
                break;
            }
            case 'calculando': {
                el.titulo.textContent = 'Estamos buscando la mejor forma de llegar.';
                el.ayuda.textContent = 'Puede tardar unos segundos. Tus lugares no se pierden.';
                const f = document.createElement('div'); f.className = 'guiado-botones';
                f.append(boton('Cancelar', 'secundario', () => { if (S.Planner.cancelarBusqueda) S.Planner.cancelarBusqueda(); sincronizarTras(); }, { id: 'gCancelarBusqueda' }));
                c.append(f);
                break;
            }
            case 'recomendacion': {
                const sel = S.Planner.seleccion, r = sel && sel.resumen;
                el.titulo.textContent = 'Esta es nuestra recomendación';
                el.ayuda.textContent = motivo();
                { const pasosRec = pasosRecomendacion(); if (pasosRec) c.append(pasosRec); }
                if (sel) c.append(datosRecomendacion(sel, r));
                const f = document.createElement('div'); f.className = 'guiado-botones';
                f.append(boton('Empezar este viaje', 'primario', () => tocar('startTrip'), { id: 'gEmpezar' }));
                const otras = document.querySelectorAll('#tripResults .trip-option').length - 1;
                if (otras > 0) f.append(boton(document.body.classList.contains('g-todas') ? 'Ocultar otras opciones' : 'Ver otras opciones', 'secundario', alternarOtras, { id: 'gOtras' }));
                f.append(boton('Cambiar desde o hasta', 'texto', () => ir('resumen'), { id: 'gCambiarPuntos' }));
                c.append(f);
                break;
            }
            default: break;
        }
        const voz = $('guiadoVoz'); voz.hidden = !('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined';
        if (paso !== 'viaje') panelMedio();
    }
    /** La pregunta del paso siempre queda a la vista (el mapa se sigue viendo arriba). Se repite poco después porque el panel también reacciona a los resultados y a los puntos. */
    function panelMedio() {
        const pedir = () => window.dispatchEvent(new CustomEvent('spevb-panel-medio'));
        pedir();
        const quien = paso;
        clearTimeout(panelMedio._t);
        panelMedio._t = setTimeout(() => { if (modo === 'guiado' && paso === quien && quien !== 'viaje') pedir(); }, 600);
    }
    function lugarResumen(etiqueta, p) {
        const d = document.createElement('p'); d.className = 'guiado-chip';
        d.append(etiqueta + ': ');
        const b = document.createElement('b'); b.textContent = p ? p.nombre : '—'; d.append(b);
        return d;
    }
    /** «Por qué la recomendamos»: la frase armada con los datos ESTRUCTURADOS del servidor (etiquetas de comparación y buses). Sin ella no se inventa un criterio. */
    function motivo() {
        const c = document.querySelector('#tripResults .trip-option.selected');
        const q = c && c.dataset.porque ? c.dataset.porque.trim() : '';
        return q ? 'Por qué la recomendamos: ' + q : '';
    }
    /** Los pasos de la opción seleccionada (el MISMO modelo que la tarjeta del planificador), con «Ver subida / Ver bajada» que solo centran el mapa. */
    function pasosRecomendacion() {
        const it = S.Planner.itinerario && S.Planner.itinerario();
        if (!it) return null;
        const caja = document.createElement('div'); caja.className = 'guiado-itinerario';
        const enc = document.createElement('p'); enc.className = 'guiado-itin-titulo';
        enc.textContent = it.modelo.titulo + ' · ' + it.modelo.detalle;
        caja.append(enc);
        if (it.modelo.aviso) { const a = document.createElement('p'); a.className = 'itin-aviso'; a.textContent = it.modelo.aviso; caja.append(a); return caja; }
        const ol = document.createElement('ol'); ol.className = 'guiado-pasos-ruta';
        it.pasos().forEach((p) => {
            const li = document.createElement('li');
            const t = document.createElement('span'); t.textContent = p.texto; li.append(t);
            if (p.foco) {
                const b = document.createElement('button'); b.type = 'button'; b.className = 'guiado-ver'; b.textContent = p.foco.etiqueta; b.dataset.clave = p.foco.clave;
                b.setAttribute('aria-label', p.foco.etiqueta + ' en el mapa');
                b.addEventListener('click', () => S.Planner.verPunto(p.foco.clave));      // centra el mapa: no empieza el viaje ni cambia de opción
                li.append(b);
            }
            ol.append(li);
        });
        caja.append(ol);
        return caja;
    }
    function datosRecomendacion(sel, r) {
        const ul = document.createElement('ul'); ul.className = 'guiado-datos';
        const li = (t) => { const x = document.createElement('li'); x.textContent = t; ul.append(x); };
        if (r) {
            li('Tiempo aproximado: ' + r.minutos + ' min');
            li('Caminas: ' + (r.caminaMetros < 1000 ? r.caminaMetros + ' m' : (r.caminaMetros / 1000).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' km'));
            li('Buses: ' + r.pasajes);
        }
        if (sel.codigos && sel.codigos.length) li('Ruta: ' + sel.codigos.map(nombreRuta).join(' y luego '));
        return ul;
    }

    // ------------------------------------------------------------------ acciones
    function anunciar(txt) { mostrarMensaje(txt, 'info'); }
    function mostrarMensaje(txt, tipo = 'info') {
        if (!txt) { el.mensaje.hidden = true; el.mensaje.textContent = ''; return; }
        if (el.mensaje.textContent !== txt) el.mensaje.textContent = txt;
        el.mensaje.dataset.tipo = tipo; el.mensaje.hidden = false;
    }
    function buscarDestino() {
        interaccion = true;
        const campo = $('tripDestination');
        if (!campo.value.trim()) { mostrarMensaje('Escribe primero el lugar al que quieres ir.', 'error'); campo.focus({ preventScroll: true }); return; }
        const d = puntos().destino;
        if (d && campo.value.trim() === String(d.nombre || '').trim()) { ir('confirmar_destino'); return; }      // el mismo lugar de antes: no hace falta buscarlo otra vez
        tocar('searchDestination');
    }
    function buscarOrigen() {
        interaccion = true;
        const campo = $('tripOrigin');
        if (!campo.value.trim()) { mostrarMensaje('Escribe primero la dirección desde donde sales.', 'error'); campo.focus({ preventScroll: true }); return; }
        const o = puntos().origen;
        if (o && campo.value.trim() === String(o.nombre || '').trim()) { ir('confirmar_origen'); return; }
        tocar('searchOrigin');
    }
    function escribirOrigen() { interaccion = true; escribiendoOrigen = true; render(); try { $('tripOrigin').focus({ preventScroll: true }); } catch { /* nada */ } }
    function cambiarDestino() { interaccion = true; mostrarMensaje(''); if (paso !== 'destino') ir('destino'); try { $('tripDestination').focus({ preventScroll: true }); $('tripDestination').select(); } catch { /* nada */ } }
    function cambiarOrigen() { interaccion = true; mostrarMensaje(''); escribiendoOrigen = false; ir('origen'); }
    function buscar() {
        interaccion = true;
        if (S.Planner.buscando && S.Planner.buscando()) return;       // varios toques seguidos: una sola búsqueda
        mostrarMensaje('');
        if (ir('calculando')) tocar('planTrip');
    }
    function alternarOtras() { document.body.classList.toggle('g-todas'); render(); }
    function sincronizarTras() { setTimeout(() => sincronizar(), 0); }

    // ------------------------------------------------------------------ reacciones al planificador y al viaje
    window.addEventListener('spevb-point-selected', () => {
        if (modo !== 'guiado') return;
        const p = puntos();
        if (paso === 'destino' && p.destino) { ir('confirmar_destino'); mostrarMensaje(''); }
        else if (paso === 'origen' && p.origen) { ir('confirmar_origen'); mostrarMensaje(''); }
        else sincronizar();
    });
    window.addEventListener('spevb-seleccion', () => {
        if (modo !== 'guiado') return;
        const sel = S.Planner.seleccion;
        // Una opción elegida solo existe si se calculó para los puntos ACTUALES (elegir un punto la borra): la recomendación es el paso correcto, también para enlaces compartidos.
        if (sel && sel.viaje) { if (paso !== 'viaje') { paso = 'recomendacion'; escribiendoOrigen = false; render(); } }
        else if (paso === 'recomendacion') { paso = 'resumen'; render(); }      // cambiaron los lugares: esa recomendación ya no vale
        else if (paso === 'calculando') render();
    });
    window.addEventListener('spevb-viaje-modo', (e) => {
        if (modo !== 'guiado') return;
        if (e.detail && e.detail.activo) { paso = 'viaje'; document.body.classList.remove('g-todas'); render(); }
        else { paso = 'viaje'; sincronizar(); }
    });
    window.addEventListener('spevb-ir-inicio', () => { paso = 'destino'; escribiendoOrigen = false; document.body.classList.remove('g-todas'); render(); });
    window.addEventListener('spevb-editar-ab', () => { if (modo === 'guiado' && paso === 'recomendacion') ir('resumen'); });
    window.addEventListener('spevb-ver-opciones', () => { if (modo === 'guiado') { document.body.classList.add('g-todas'); render(); } });

    // Mensajes del planificador (errores, GPS, búsqueda) → región en vivo del paso actual, sin repetirlos.
    const estado = $('tripStatus');
    const OMITIR = /^Marca A y B|^Primero selecciona el punto A|^Punto seleccionado\.|^Origen y destino listos|^Comparando /i;      // avisos de rutina del planificador: el paso ya dice qué sigue
    const alEstado = () => {
        if (modo !== 'guiado' || !estado) return;
        const txt = (estado.textContent || '').trim();
        if (!txt || OMITIR.test(txt)) { if (!txt) mostrarMensaje(''); return; }
        const tipo = /error/.test(estado.className) ? 'error' : /success/.test(estado.className) ? 'ok' : 'info';
        mostrarMensaje(simple(txt), tipo);
        // Sin GPS o con mala precisión: nunca un callejón sin salida → se ofrecen ya las otras dos maneras.
        if (tipo === 'error' && paso === 'origen' && !escribiendoOrigen) { escribiendoOrigen = true; render(); }
    };
    /** Los mensajes del planificador hablan de «A» y «B»: en el modo guiado se dicen con palabras. */
    const simple = (t) => t.replace(/\bel punto A y el punto B\b/gi, 'el origen y el destino').replace(/\bpunto A\b/gi, 'origen').replace(/\bpunto B\b/gi, 'destino').replace(/\bA y B\b/g, 'origen y destino');
    if (estado) new MutationObserver(alEstado).observe(estado, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    // Cambios de estado del GPS y de la búsqueda (botones que el planificador activa o desactiva).
    const observar = (id) => { const n = $(id); if (n) new MutationObserver(() => { if (modo !== 'guiado') return; if (paso === 'origen') render(); if (id === 'planTrip') { if (n.disabled && !['calculando', 'viaje', 'recomendacion'].includes(paso)) { paso = 'calculando'; render(); } else if (!n.disabled && paso === 'calculando') sincronizarTras(); } }).observe(n, { attributes: true, attributeFilter: ['disabled'] }); };
    ['useMyLocation', 'planTrip'].forEach(observar);
    // Resultados de la búsqueda: cuando terminan de dibujarse, el paso se corrige (recomendación o vuelta al resumen con el error visible).
    const resultados = $('tripResults');
    if (resultados) new MutationObserver(() => { if (modo === 'guiado' && (paso === 'recomendacion' || paso === 'calculando')) { clearTimeout(resultados._t); resultados._t = setTimeout(() => { if (paso === 'calculando' && !(S.Planner.buscando && S.Planner.buscando())) sincronizar(); else if (paso === 'recomendacion') render(); }, 60); } }).observe(resultados, { childList: true });

    // ------------------------------------------------------------------ modo guiado / avanzado
    function aplicarModo() {
        const guiado = modo === 'guiado';
        document.body.classList.toggle('guiado', guiado);
        ocultarTodo(!guiado); pintarEntrada();
        if (!guiado) { delete document.body.dataset.paso; document.body.classList.remove('g-escribiendo-origen', 'g-todas'); }
        // Etiquetas visibles en el modo guiado (en el avanzado vuelven a ser solo para lectores de pantalla).
        const lo = document.querySelector('label[for="tripOrigin"]'), ld = document.querySelector('label[for="tripDestination"]');
        if (lo) { lo.textContent = guiado ? 'Dirección desde donde sales' : 'Origen'; lo.classList.toggle('sr-only', !guiado); lo.classList.toggle('guiado-etiqueta', guiado); }
        if (ld) { ld.textContent = guiado ? 'Lugar al que quieres ir' : 'Destino'; ld.classList.toggle('sr-only', !guiado); ld.classList.toggle('guiado-etiqueta', guiado); }
        if (guiado) { paso = derivar(); render(); }
        window.dispatchEvent(new CustomEvent('spevb-modo-planificador', { detail: { modo } }));
    }
    function cambiarModo(nuevo) {
        if (modo === nuevo) return;
        modo = nuevo; guardarModo(modo); interaccion = true; ultimaFirma = null;
        aplicarModo();
        if (modo === 'guiado') { try { el.titulo.focus({ preventScroll: true }); } catch { /* nada */ } }
    }
    $('guiadoAvanzado').addEventListener('click', () => cambiarModo('avanzado'));
    entrada.addEventListener('click', () => { const c = $('closeMenu'); if (c) c.click(); cambiarModo(modo === 'guiado' ? 'avanzado' : 'guiado'); });
    $('guiadoAyudaBtn').addEventListener('click', () => tocar('helpButton'));

    // Leer en voz alta: opcional, solo con capacidades nativas, nunca automático; el texto completo siempre está en pantalla.
    $('guiadoVoz').addEventListener('click', () => {
        try {
            const sy = window.speechSynthesis;
            if (sy.speaking) { sy.cancel(); return; }
            const partes = [el.titulo.textContent, el.ayuda.hidden ? '' : el.ayuda.textContent, ...[...el.cuerpo.querySelectorAll('p, strong, li, small, span')].map((n) => n.textContent), el.mensaje.hidden ? '' : el.mensaje.textContent].filter(Boolean);
            const u = new SpeechSynthesisUtterance(partes.join('. ')); u.lang = 'es-CO';
            sy.cancel(); sy.speak(u);
        } catch { /* sin voz: el texto sigue visible */ }
    });

    // La llegada: acción opcional para planear otro trayecto.
    window.addEventListener('spevb-itinerario', () => { if (modo === 'guiado' && paso === 'recomendacion') render(); });
    window.addEventListener('spevb-viaje-llegada', () => {
        const tarjeta = $('viajeCard'); if (!tarjeta || $('viajeOtro')) return;
        const b = document.createElement('button');
        b.type = 'button'; b.id = 'viajeOtro'; b.className = 'viaje-otro'; b.textContent = 'Planear otro trayecto';
        b.addEventListener('click', () => { try { if (!S.Viaje.cerrarLlegada()) return; S.Planner.limpiar(); } catch { /* nada */ } b.remove(); paso = 'destino'; escribiendoOrigen = false; interaccion = true; render(); });
        const pie = tarjeta.querySelector('.viaje-pie'); (pie || tarjeta).before(b);
    });
    window.addEventListener('spevb-viaje-modo', (e) => { if (!(e.detail && e.detail.activo)) { const o = $('viajeOtro'); if (o) o.remove(); } });

    S.Guiado = { paso: () => paso, modo: () => modo, ir, derivar, PASOS, TRANSICIONES, esGuiado: () => modo === 'guiado' };
    function iniciar() { if (montado) return; montado = true; aplicarModo(); window.addEventListener('pageshow', (e) => { if (e.persisted) sincronizar(); }); }
    // El planificador termina de montarse cuando el mapa está listo (evento «spevb-planner-listo»): hasta entonces solo se aplica la clase y el bloque queda oculto.
    if (typeof S.Planner.puntos === 'function') iniciar();
    else { ocultarTodo(true); document.body.classList.toggle('guiado', modo === 'guiado'); window.addEventListener('spevb-planner-listo', iniciar, { once: true }); }
})();
