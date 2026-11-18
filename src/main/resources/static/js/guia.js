'use strict';
/* Aprender a usar SEVB (4.15.1): bienvenida de 8 escenas con ilustraciones animadas que enseñan el FLUJO GUIADO real (destino primero → origen → buscar → recomendación → un solo viaje →
   marcador → avisos de bajada → terminar), ayuda en contexto (botón «?») con ayudas rápidas y una práctica de 8 pasos sobre el paso a paso real.
   · La bienvenida sale solo la primera vez y se puede ver otra vez desde el menú → Ayuda. Nadie está obligado a hacer la práctica. «Omitir» la cierra en cualquier escena.
   · Las «ayudas rápidas» reutilizan las mismas escenas (una sola ilustración, sin navegación) para consultar algo puntual. El planificador con A y B solo se explica ahí, como opción.
   · La práctica usa el planificador con A y B (el panel principal): #tripDestination, #useMyLocation, #planTrip, #startTrip…. NO usa el GPS ni inicia un viaje. Guarda lo que la persona tenía
     (puntos, resultados y el modo del planificador) y lo devuelve al terminar o salir. Si el servicio de rutas no responde, enseña con un ejemplo ilustrado marcado como simulación.
   · Solo se anima la escena que se ve; al cerrar se detienen animaciones, temporizadores y observadores. El coach se actualiza solo cuando algo cambia (eventos), no en cada cuadro.
   Sin emojis y sin voz: todo el dibujo es propio (SVG, ver iconos.js) y la guía es el chigüiro del proyecto, que solo aparece donde aporta. */
(() => {
    const S = window.Spevb;
    const $ = (id) => document.getElementById(id);
    if (!S || !S.Modal || !$('bienvenida')) return;
    const K = 'spevb-bienvenida', VERSION = '2';
    const visto = () => { try { return localStorage.getItem(K) === VERSION; } catch { return true; } };
    const marcarVisto = () => { try { localStorage.setItem(K, VERSION); } catch { /* sin almacenamiento */ } };
    const hayModalAbierto = () => [...document.querySelectorAll('.modal-backdrop')].some((m) => !m.hidden);
    const reducido = () => document.documentElement.dataset.motion === 'reduce' || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    const icono = (n, tam = 20) => (S.Iconos ? S.Iconos.svg(n, { tam }) : '');
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const visible = (el) => !!el && !el.hidden && el.getClientRects().length > 0;
    const FOCO = S.Modal.FOCO;

    // ------------------------------------------------------------------ foco de las ventanas
    // La trampa de Tab, Escape, el fondo inerte y el regreso del foco son del controlador común (modales.js). Aquí solo se conserva QUIÉN abrió la cadena
    // (ayuda → bienvenida → práctica), para devolverle el foco una sola vez al final.
    let abridor = null;
    const recordarAbridor = () => { abridor = S.Modal.recordarAbridor(); };
    const devolverFoco = () => { const a = abridor; abridor = null; S.Modal.devolverFoco(a); };

    // ------------------------------------------------------------------ ilustraciones animadas (SVG propio, mismo trazo y paleta que el resto de SEVB)
    const V = '#176650', ROJO = '#e53935', NARANJA = '#d9822b', AZUL = '#1a73e8';
    const CALLES = '<path class="calle" d="M-10 150C50 128 105 170 165 138S270 122 330 144"/><path class="calle" d="M-10 62 330 96"/><path class="calle" d="M118-10 150 210"/><path class="calle" d="M232-10 214 210"/>';
    const MANZANAS = [[14, 100, 62, 30], [100, 98, 52, 24], [172, 104, 48, 22], [250, 100, 56, 26], [14, 156, 64, 28], [128, 156, 70, 26], [224, 156, 82, 28]]
        .map((m) => '<rect class="manzana" x="' + m[0] + '" y="' + m[1] + '" width="' + m[2] + '" height="' + m[3] + '" rx="7"/>').join('');
    const FONDO = '<rect width="320" height="200" rx="22" class="fondo"/>';
    const ABRE = (n) => '<svg viewBox="0 0 320 200" class="escena-svg e' + n + '" aria-hidden="true" focusable="false">';
    const ic = (nombre, x, y, tam = 22) => '<g class="ico" transform="translate(' + (x - tam / 2) + ' ' + (y - tam / 2) + ')">' + icono(nombre, tam) + '</g>';
    const BUS_ILUS = '<g transform="translate(-17 -11)"><rect width="34" height="20" rx="6" fill="' + ROJO + '" stroke="#fff" stroke-width="2.4"/>'
        + '<rect x="5" y="5" width="7" height="6" rx="1.6" fill="#fff"/><rect x="14" y="5" width="7" height="6" rx="1.6" fill="#fff"/><rect x="23" y="5" width="6" height="6" rx="1.6" fill="#fff"/>'
        + '<circle cx="9" cy="20" r="3.4" fill="#14281f" stroke="#fff" stroke-width="1.6"/><circle cx="25" cy="20" r="3.4" fill="#14281f" stroke="#fff" stroke-width="1.6"/></g>';
    const MASCOTA = (id, cx, cy, r) => '<circle class="medallon" cx="' + cx + '" cy="' + cy + '" r="' + (r + 3) + '"/><clipPath id="' + id + '"><circle cx="' + cx + '" cy="' + cy + '" r="' + r + '"/></clipPath>'
        + '<g clip-path="url(#' + id + ')"><image class="mascota" href="/img/marca/sevb-chiguiro-96.png" x="' + (cx - r) + '" y="' + (cy - r) + '" width="' + 2 * r + '" height="' + 2 * r + '"/></g>';
    /** Botón de las escenas (mismo verde del botón principal) o botón secundario (borde verde, fondo blanco). */
    const BOTON = (x, y, w, h, texto, clase = '') => '<g class="boton ' + clase + '"><rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="' + h / 2 + '"/><text x="' + (x + w / 2) + '" y="' + (y + h / 2 + 4.6) + '" text-anchor="middle">' + texto + '</text></g>';
    /** El círculo azul de tu ubicación (el mismo que se ve en el mapa mientras caminas). */
    const PUNTO_AZUL = (x, y, r = 11) => '<g class="azul" transform="translate(' + x + ' ' + y + ')"><circle class="halo" r="' + Math.round(r * 1.9) + '"/><circle class="disco" r="' + r + '"/></g>';
    /** El marcador del bus con el código de la ruta, que reemplaza al círculo azul mientras vas en el bus. */
    const BUS_MARCA = (x, y, codigo) => '<g class="bus-marca" transform="translate(' + x + ' ' + y + ')"><circle r="24" fill="' + ROJO + '" stroke="#fff" stroke-width="3"/><g class="ico" transform="translate(-11 -19)">' + icono('bus', 22) + '</g>'
        + '<rect x="-19" y="6" width="38" height="16" rx="8" fill="#fff" stroke="' + ROJO + '" stroke-width="1.6"/><text x="0" y="18" text-anchor="middle" class="codigo">' + codigo + '</text></g>';

    const ESCENAS = [
        {
            clave: 'destino', titulo: 'Primero, dime a dónde vas',
            texto: 'Escribe el lugar al que quieres ir. Google te muestra sugerencias: toca la correcta y confirma.',
            svg: ABRE(1) + FONDO + MANZANAS + CALLES
                + '<g class="burbuja"><rect x="14" y="8" width="204" height="30" rx="15"/><text x="116" y="27.6" text-anchor="middle">¿A dónde quieres ir?</text></g>'
                + '<g class="campo"><rect class="caja" x="14" y="46" width="292" height="34" rx="17"/><text class="valor" x="32" y="68">Terminal de transportes</text><rect class="tapa" x="30" y="52" width="260" height="22"/></g>'
                + '<text class="rotulo" x="16" y="98">Sugerencias de Google</text>'
                + '<g class="sug s1"><rect x="14" y="104" width="292" height="30" rx="10"/><text x="30" y="123.4">Terminal de transportes, Villavicencio</text><g class="visto"><circle cx="286" cy="119" r="9"/><path d="M281.5 119.4 285 123 291 115.4"/></g></g>'
                + '<g class="sug s2"><rect x="14" y="138" width="292" height="26" rx="10"/><text x="30" y="155.4">Terminal de buses, otra ciudad</text></g>'
                + BOTON(78, 168, 164, 28, 'Sí, continuar', 'b-si')
                + '<g class="saludo">' + MASCOTA('recorteE1', 292, 20, 15) + '</g></svg>',
        },
        {
            clave: 'origen', titulo: 'Ahora, dónde estás',
            texto: 'Toca «Usar mi ubicación actual». Si prefieres, escribe una dirección o elígela en el mapa.',
            svg: ABRE(2) + FONDO
                + '<g class="boton b-gps"><rect x="14" y="12" width="292" height="46" rx="23"/><g class="ico" transform="translate(30 23)">' + icono('gps', 24) + '</g><text x="172" y="40.6" text-anchor="middle">Usar mi ubicación actual</text></g>'
                + BOTON(14, 66, 142, 34, 'Escribir una dirección', 'sec b-esc') + BOTON(164, 66, 142, 34, 'Elegir en el mapa', 'sec b-map')
                + '<rect class="mapita" x="14" y="110" width="292" height="80" rx="14"/><path class="calle" d="M14 168C80 140 150 176 220 146S280 140 306 150"/><path class="calle" d="M70 110 100 190"/><path class="calle" d="M210 110 196 190"/>'
                + PUNTO_AZUL(160, 150, 10)
                + '<g class="etiqueta et-aqui"><rect x="190" y="124" width="104" height="20" rx="10"/><text x="242" y="138" text-anchor="middle">Aquí estás tú</text></g></svg>',
        },
        {
            clave: 'revisar', titulo: 'Revisa y busca',
            texto: 'Mira desde dónde sales y a dónde vas. Si todo está bien, toca «Buscar cómo llegar».',
            svg: ABRE(3) + FONDO
                + '<g class="lugar l1"><rect x="14" y="12" width="292" height="48" rx="14"/><text x="30" y="31" class="peq">Vas desde</text><text x="30" y="50" class="gran">Tu ubicación actual</text><g class="ico" transform="translate(268 22)">' + icono('gps', 24) + '</g></g>'
                + '<path class="union" d="M160 62V80" /><circle class="punto-u" cx="160" cy="66" r="2.6"/><circle class="punto-u" cx="160" cy="72" r="2.6"/><circle class="punto-u" cx="160" cy="78" r="2.6"/>'
                + '<g class="lugar l2"><rect x="14" y="82" width="292" height="48" rx="14"/><text x="30" y="101" class="peq">Hasta</text><text x="30" y="120" class="gran">Terminal de transportes</text><g class="ico" transform="translate(268 92)">' + icono('pin', 24) + '</g></g>'
                + BOTON(40, 146, 240, 44, 'Buscar cómo llegar', 'b-buscar') + '</svg>',
        },
        {
            clave: 'recomendacion', titulo: 'Esta es la recomendación',
            texto: 'Verás los minutos, cuánto caminas y qué bus tomar. Si hay que cambiar de bus, dice «2 buses».',
            svg: ABRE(4) + FONDO
                + '<g class="reco r1"><rect class="t-fondo" x="12" y="10" width="296" height="92" rx="16"/><rect x="24" y="22" width="40" height="26" rx="8" fill="' + ROJO + '"/><text x="44" y="39.6" text-anchor="middle" class="t-chip">R12</text>'
                + '<text x="74" y="40" class="t-nombre">Ruta Catama</text><text x="296" y="42" text-anchor="end" class="t-min">21 min</text>'
                + '<g class="dato d1"><g class="ico" transform="translate(24 58)">' + icono('caminar', 20) + '</g><text x="50" y="73" class="t-dato">Caminas 300 m</text></g>'
                + '<g class="dato d2"><g class="ico" transform="translate(170 58)">' + icono('bus', 20) + '</g><text x="196" y="73" class="t-dato">1 bus</text></g>'
                + '<g class="insignia"><rect x="24" y="80" width="104" height="16" rx="8"/><text x="76" y="91.6" text-anchor="middle">Recomendada</text></g></g>'
                + '<g class="reco r2"><rect class="t-fondo" x="12" y="112" width="296" height="78" rx="16"/><rect x="24" y="124" width="40" height="26" rx="8" fill="' + ROJO + '"/><text x="44" y="141.6" text-anchor="middle" class="t-chip">R12</text>'
                + '<g class="ico" transform="translate(70 126)">' + icono('flecha', 22) + '</g><rect x="98" y="124" width="40" height="26" rx="8" fill="#7b1fa2"/><text x="118" y="141.6" text-anchor="middle" class="t-chip">R08</text>'
                + '<text x="296" y="142" text-anchor="end" class="t-min">2 buses</text><text x="24" y="172" class="t-dato">Transbordo: bajas del primero y subes al segundo</text></g></svg>',
        },
        {
            clave: 'empezar', titulo: 'Empieza un solo viaje',
            texto: 'Cuando estés en el paradero, toca «Empezar este viaje». Solo puede haber un viaje a la vez: termina este antes de empezar otro.',
            svg: ABRE(5) + FONDO + MANZANAS
                + '<g class="paradero-ilu">' + ic('paradero', 160, 30, 30) + '</g>'
                + BOTON(30, 56, 260, 52, 'Empezar este viaje', 'b-empezar')
                + '<g class="uno"><rect x="52" y="124" width="216" height="32" rx="16"/><g class="ico" transform="translate(64 130)">' + icono('candado', 20) + '</g><text x="172" y="144.4" text-anchor="middle">Un solo viaje a la vez</text></g>'
                + '<text class="nota" x="160" y="178" text-anchor="middle">Para empezar otro, primero termina este.</text></svg>',
        },
        {
            clave: 'marcador', titulo: 'Sigue tu marcador',
            texto: 'Caminando eres un círculo azul. En el bus, te vuelves un bus con el código de la ruta. Al bajar, otra vez un círculo.',
            svg: ABRE(6) + FONDO
                + '<g class="paso p1">' + PUNTO_AZUL(58, 74, 13) + '<text x="58" y="124" text-anchor="middle" class="rot">Caminas</text></g>'
                + '<g class="flecha f1">' + ic('flecha', 108, 74, 26) + '</g>'
                + '<g class="paso p2">' + BUS_MARCA(160, 74, 'R12') + '<text x="160" y="124" text-anchor="middle" class="rot">Vas en el bus</text></g>'
                + '<g class="flecha f2">' + ic('flecha', 212, 74, 26) + '</g>'
                + '<g class="paso p3">' + PUNTO_AZUL(262, 74, 13) + '<text x="262" y="124" text-anchor="middle" class="rot">Bajas y caminas</text></g>'
                + '<g class="leyenda"><circle cx="40" cy="168" r="7" fill="' + AZUL + '" stroke="#fff" stroke-width="2.4"/><text x="54" y="172" class="rot2">Círculo azul: eres tú</text>'
                + '<circle cx="186" cy="168" r="7" fill="' + ROJO + '" stroke="#fff" stroke-width="2.4"/><text x="200" y="172" class="rot2">Bus con su código</text></g></svg>',
        },
        {
            clave: 'bajada', titulo: 'Te aviso antes de bajar',
            texto: 'Te aviso cuando estés cerca, cuando debas prepararte y cuando sea ahora. Con «Tu bajada está aquí», baja cuando el bus se detenga.',
            svg: ABRE(7) + FONDO
                + '<g class="nivel n1"><text x="16" y="29" class="rot">Cerca</text><rect class="pista" x="104" y="16" width="200" height="16" rx="8"/><rect class="barra" x="104" y="16" width="70" height="16" rx="8" fill="#6fa58f"/></g>'
                + '<g class="nivel n2"><text x="16" y="59" class="rot">Prepárate</text><rect class="pista" x="104" y="46" width="200" height="16" rx="8"/><rect class="barra" x="104" y="46" width="136" height="16" rx="8" fill="' + NARANJA + '"/></g>'
                + '<g class="nivel n3"><text x="16" y="89" class="rot">Ahora</text><rect class="pista" x="104" y="76" width="200" height="16" rx="8"/><rect class="barra" x="104" y="76" width="200" height="16" rx="8" fill="' + ROJO + '"/></g>'
                + '<text class="nota" x="160" y="114" text-anchor="middle">Si tu teléfono lo permite, también vibra o te avisa.</text>'
                + '<g class="tarjeta-baja"><rect x="14" y="124" width="292" height="64" rx="16"/><g class="ico" transform="translate(28 138)">' + icono('bajar', 28) + '</g><text x="68" y="148" class="t-nombre">Tu bajada está aquí</text><text x="68" y="168" class="t-dato">Baja cuando el bus se detenga</text></g></svg>',
        },
        {
            clave: 'terminar', titulo: 'Termina tu viaje',
            texto: 'Toca «Ya me bajé» y camina el último tramo. Al llegar, toca «Terminar viaje». Puedes practicar o empezar a explorar.',
            svg: ABRE(8) + FONDO + MANZANAS
                + BOTON(14, 16, 150, 40, 'Ya me bajé', 'sec b-baje')
                + '<g class="flecha f1">' + ic('flecha', 188, 36, 24) + '</g>' + PUNTO_AZUL(246, 36, 11)
                + '<path class="camino" pathLength="1" d="M246 50C240 84 200 96 170 120"/><g class="ico pin-fin" transform="translate(158 118)">' + icono('pin', 24) + '</g>'
                + BOTON(50, 150, 220, 40, 'Terminar viaje', 'b-terminar')
                + '<g class="saludo">' + MASCOTA('recorteE8', 36, 112, 22) + '</g></svg>',
        },
    ];
    // Ayudas rápidas: cada tema reutiliza una escena (no hay una ilustración nueva por tema). La primera ayuda que se abre desde el planificador con A y B muestra la escena 0.
    const TEMAS = [
        { t: 'Cómo elegir el destino', escena: 0, practicaMapa: true, titulo: 'Cómo elegir el destino', texto: 'Escribe el lugar al que quieres ir y toca «Buscar destino». Google te muestra sugerencias: toca la correcta y confirma con «Sí, continuar». Si no la encuentras, toca «Elegir en el mapa».' },
        { t: 'Cómo decir dónde estás', escena: 1, titulo: 'Cómo decir dónde estás', texto: 'Toca «Usar mi ubicación actual» si ya estás donde empiezas. También puedes tocar «Escribir una dirección» o «Elegir en el mapa» y marcar el punto con el dedo.' },
        { t: 'Cómo buscar cómo llegar', escena: 2, titulo: 'Cómo buscar cómo llegar', texto: 'Revisa desde dónde sales y a dónde vas. Si algo no es correcto, toca «Cambiar origen» o «Cambiar destino»: no pierdes el otro lugar. Después toca «Buscar cómo llegar».' },
        { t: 'Cómo leer la recomendación', escena: 3, titulo: 'Cómo leer la recomendación', texto: 'Mira el tiempo aproximado, cuánto caminas y qué bus tomar. El tiempo no incluye la espera del bus. «Ver otras opciones» muestra las demás rutas.' },
        { t: 'Cómo funcionan los transbordos', escena: 3, titulo: 'Cómo funcionan los transbordos', texto: 'Si no hay un bus directo, verás «2 buses»: bajas del primero en el punto marcado y subes al segundo. El tiempo ya incluye ese cambio.' },
        { t: 'Cómo empezar un viaje', escena: 4, titulo: 'Cómo empezar un viaje', texto: 'Toca «Empezar este viaje» cuando estés en el paradero. Solo puede haber un viaje a la vez: para empezar otro, primero termina este.' },
        { t: 'Qué significa tu marcador', escena: 5, titulo: 'Qué significa tu marcador', texto: 'Eres un círculo azul mientras caminas. Cuando confirmas que subiste, te vuelves un bus con el código de la ruta. Al bajarte vuelves a ser un círculo azul.' },
        { t: 'Cómo funcionan los avisos de bajada', escena: 6, titulo: 'Cómo funcionan los avisos de bajada', texto: 'Te aviso en tres momentos: cerca, prepárate y ahora. Aparece «Tu bajada está aquí» hasta que toques «Ya me bajé». La vibración y la notificación son opcionales y dependen de tu teléfono.' },
        { t: 'Cómo terminar el viaje', escena: 7, titulo: 'Cómo terminar el viaje', texto: 'Toca «Ya me bajé» cuando bajes del bus y camina el último tramo. Al llegar, toca «Terminar viaje». También puedes terminarlo antes desde la tarjeta del viaje.' },
        { t: 'Si no aparece una ruta', escena: null, titulo: 'Si no aparece una ruta', accion: '#tripDestination',
            tips: ['Prueba con otro lugar cercano o más conocido.', 'Toca «Elegir en el mapa» y marca el punto con el dedo para ver dónde quedó.', 'Hay zonas con pocas rutas registradas: acércate a una calle grande.'] },
    ];

    // ------------------------------------------------------------------ bienvenida y lecciones
    const bien = $('bienvenida'), tarjetaBien = bien.querySelector('.bienvenida-card');
    let paso = 0, anterior = -1, modo = 'bienvenida', leccionActual = null;
    function montarEscenas() {
        const cont = $('bienIlustracion');
        if (cont.childElementCount) return;
        ESCENAS.forEach((e, i) => { const d = document.createElement('div'); d.className = 'bien-escena'; d.dataset.i = String(i); d.dataset.clave = e.clave; d.innerHTML = e.svg; cont.append(d); });
    }
    /** Detiene lo que se mueve en las escenas que no se ven (las animaciones SMIL no se pausan solas) y reanuda la activa. */
    function animarSoloLaActiva(activa) {
        document.querySelectorAll('#bienIlustracion .bien-escena').forEach((d, i) => {
            const svg = d.querySelector('svg');
            if (svg && svg.pauseAnimations) { if (i === activa && !reducido()) { if (svg.dataset.vista !== '1') { svg.setCurrentTime(0); svg.dataset.vista = '1'; } svg.unpauseAnimations(); } else { svg.pauseAnimations(); if (i !== activa) delete svg.dataset.vista; } }
        });
    }
    function pintarBienvenida() {
        montarEscenas();
        const leccion = modo === 'leccion', p = leccion ? leccionActual : ESCENAS[paso], ultimo = !leccion && paso === ESCENAS.length - 1;
        tarjetaBien.dataset.modo = modo; tarjetaBien.dataset.escena = String(paso);
        document.querySelectorAll('#bienIlustracion .bien-escena').forEach((d, i) => {
            d.classList.toggle('activa', i === paso); d.classList.toggle('pasada', i < paso); d.classList.toggle('futura', i > paso);
        });
        animarSoloLaActiva(paso);
        const texto = $('bienTextos');
        texto.classList.remove('cambia'); void texto.offsetWidth; texto.classList.add('cambia');          // reinicia la animación de entrada del texto
        texto.dataset.dir = anterior > paso ? 'atras' : 'adelante';
        $('bienTitulo').textContent = p.titulo;
        $('bienTexto').textContent = p.texto;
        $('bienPuntos').replaceChildren(...ESCENAS.map((_, i) => { const d = document.createElement('i'); if (i === paso) d.className = 'activo'; else if (i < paso) d.className = 'hecho'; return d; }));
        $('bienAtras').hidden = leccion || paso === 0;
        $('bienSiguiente').textContent = leccion ? 'Entendido' : ultimo ? 'Empezar a explorar' : 'Siguiente';
        $('bienSiguiente').className = ultimo ? 'secondary' : 'primary-plan-button';
        $('bienPractica').hidden = !ultimo;
        $('bienPracticaMapa').hidden = !(leccion && leccionActual && leccionActual.practicaMapa);
        $('bienSaltar').hidden = leccion || ultimo;
        $('bienPasoTexto').textContent = leccion ? 'Ayuda rápida' : 'Paso ' + (paso + 1) + ' de ' + ESCENAS.length;
        anterior = paso;
    }
    function abrirVentanaBien(foco) {
        if (!abridor) recordarAbridor();
        bien.classList.remove('cerrando'); pintarBienvenida();
        S.Modal.abrir(bien, { foco: () => $(foco), retardo: 60, abridor, cerrar: () => { if (!bien.classList.contains('cerrando')) cerrarBienvenida(); } });
    }
    function abrirBienvenida() { modo = 'bienvenida'; leccionActual = null; paso = 0; anterior = -1; abrirVentanaBien('bienSiguiente'); }
    /** Una sola escena con su explicación (ayudas rápidas): no cuenta como «bienvenida vista». */
    function abrirLeccion(tema) { modo = 'leccion'; leccionActual = tema; paso = tema.escena; anterior = -1; abrirVentanaBien('bienSiguiente'); }
    function cerrarBienvenida({ marcar = true } = {}) {
        if (marcar && modo === 'bienvenida') marcarVisto();
        bien.classList.add('cerrando');
        setTimeout(() => {
            S.Modal.cerrar(bien, { devolver: false }); bien.classList.remove('cerrando'); animarSoloLaActiva(-1);
            devolverFoco();
        }, reducido() ? 0 : 260);
    }
    const irA = (n) => { if (n < 0 || n > ESCENAS.length - 1 || modo === 'leccion') return; paso = n; pintarBienvenida(); };
    $('bienSiguiente').onclick = () => { if (modo === 'bienvenida' && paso < ESCENAS.length - 1) irA(paso + 1); else cerrarBienvenida(); };
    $('bienAtras').onclick = () => irA(paso - 1);
    $('bienSaltar').onclick = () => cerrarBienvenida();
    $('bienPractica').onclick = () => { abridor = null; cerrarBienvenida(); setTimeout(() => practica(), 450); };
    document.addEventListener('keydown', (e) => {
        if (bien.hidden) return;
        if (e.key === 'ArrowRight') irA(paso + 1);
        else if (e.key === 'ArrowLeft') irA(paso - 1);
    });
    // Deslizar con el dedo entre las escenas de la bienvenida.
    let x0 = null;
    bien.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    bien.addEventListener('touchend', (e) => {
        if (x0 === null) return;
        const dx = e.changedTouches[0].clientX - x0; x0 = null;
        if (dx < -50) irA(paso + 1); else if (dx > 50) irA(paso - 1);
    }, { passive: true });

    // ------------------------------------------------------------------ ayuda en contexto (9 estados)
    const puntosAhora = () => (S.Planner && S.Planner.puntos ? S.Planner.puntos() : {});
    const DEMO_BUSCAR = { texto: 'Ver cómo se busca', tema: 0 }, DEMO_ELEGIR = { texto: 'Ver cómo se elige', tema: 3 }, DEMO_VIAJE = { texto: 'Ver cómo es el viaje', tema: 5 };
    const AYUDAS = {
        inicio: { titulo: 'Para empezar', tips: ['Escribe dónde estás en «¿De dónde sales?», o toca «Mi ubicación».', 'Escribe a dónde vas en «¿A dónde vas?».',
            'Si no encuentras la dirección, toca «En el mapa» y marca el punto con el dedo.', 'Después toca el botón verde «Buscar rutas».'], accion: '#tripOrigin', demo: DEMO_BUSCAR },
        uno: { titulo: 'Te falta un punto', tips: ['Ya tienes uno de los dos puntos. Falta el otro: escríbelo, o toca «En el mapa» para marcarlo.', 'Cuando estén los dos, toca «Buscar rutas».'],
            accion: () => (puntosAhora().origen ? '#tripDestination' : '#tripOrigin'), demo: DEMO_BUSCAR },
        listos: { titulo: 'Ya casi', tips: ['Ya están tus dos puntos. Toca el botón verde «Buscar rutas» para ver qué bus tomar.'], accion: '#planTrip', demo: DEMO_BUSCAR },
        buscando: { titulo: 'Buscando tus rutas', tips: ['Estoy comparando tu salida y tu llegada con todas las rutas. Son unos segundos.', 'No cierres la página: las opciones aparecen solas.'], accion: null, demo: null },
        resultados: { titulo: 'Tus opciones', tips: ['Cada opción dice qué ruta tomar, cuánto caminas y cuánto tardas, más o menos.', 'Toca una opción para verla en el mapa.',
            'El tiempo es aproximado y no incluye la espera del bus.'], accion: '#tripResults .trip-option summary', demo: DEMO_ELEGIR },
        ruta: { titulo: 'Ya elegiste una ruta', tips: ['La línea roja es el bus y la punteada es lo que caminas.', 'Sube en «Sube aquí» y bájate en «Bájate aquí».',
            'Si quieres cambiar un lugar, toca «Editar A y B»: la ruta elegida se conserva hasta que cambies un punto.',
            'Cuando estés en el paradero, toca «Iniciar viaje» y te acompaño paso a paso.'], accion: '#startTrip', demo: DEMO_VIAJE },
        sinrutas: { titulo: 'No apareció una ruta', tips: ['Mueve A o B hacia una calle grande, cerca de donde pasan los buses.', 'Toca «En el mapa» y marca el punto con el dedo para ver dónde quedó.',
            'Prueba con otro lugar cercano: hay zonas con pocas rutas registradas.'], accion: '#tripOrigin', demo: null },
        error: { titulo: 'Algo no salió bien', tips: ['Revisa tu conexión a internet.', 'Los viajes que ya consultaste están en «Recientes», en el menú ☰.', 'Vuelve a tocar «Buscar rutas».'], accion: '#planTrip', demo: null },
        viaje: { titulo: 'Durante tu viaje', tips: ['Sigue la tarjeta del mapa: te dice qué hacer ahora.', 'Tú eres un círculo azul; cuando subes al bus te conviertes en un bus con el código de la ruta.',
            'Si te pregunta «¿Vas en la ruta…?», toca «Sí» o «No».',
            'Al acercarte a tu bajada te aviso; cuando veas «Tu bajada está aquí», baja cuando el bus se detenga y toca «Ya me bajé» (o «Sigo en el bus»).',
            'Solo puede haber un viaje a la vez: para empezar otro, termina este.',
            'Si te pierdes, toca «Más» y luego «Recalcular desde aquí». Ahí también eliges las «Alertas de bajada».', 'Para terminar antes, toca «Terminar viaje».'], accion: null, demo: null },
    };
    // Ayuda del FLUJO GUIADO («Planear paso a paso»): habla de los botones reales de cada pantalla (no de «¿De dónde sales?» ni «Buscar rutas», que ahí no existen).
    const AYUDAS_GUIADO = {
        destino: { titulo: 'Para empezar', tips: ['Escribe el lugar al que quieres ir y toca «Buscar destino». Las sugerencias vienen de Google: toca la que corresponda.',
            'Si no lo encuentras, toca «Elegir en el mapa» y marca el punto con el dedo.'], accion: '#gBuscarDestino', practicaMapa: true },
        confirmar_destino: { titulo: 'Confirma el destino', tips: ['Mira el punto en el mapa.', 'Si es el lugar correcto toca «Sí, continuar»; si no, «Cambiar destino».'], accion: '#gSiDestino' },
        origen: { titulo: 'Ahora, desde dónde sales', tips: ['Toca «Usar mi ubicación actual» si ya estás donde empiezas.', 'O toca «Escribir una dirección», o «Elegir en el mapa».',
            '«Volver al destino» te deja corregir el lugar al que vas.'], accion: '#gUsarGps' },
        confirmar_origen: { titulo: 'Confirma tu salida', tips: ['Si es el lugar correcto toca «Sí, continuar».', '«Cambiar lugar» te deja elegir otro.'], accion: '#gSiOrigen' },
        resumen: { titulo: 'Revisa tu viaje', tips: ['Comprueba tu salida y tu destino.', 'Toca «Buscar cómo llegar».', '«Cambiar origen» o «Cambiar destino» corrigen uno sin perder el otro.'], accion: '#gBuscar' },
        calculando: { titulo: 'Buscando tu ruta', tips: ['Estoy comparando tu salida y tu llegada con todas las rutas. Son unos segundos.', 'Puedes tocar «Cancelar» y tus lugares no se pierden.'], accion: null },
        recomendacion: { titulo: 'Esta es la recomendación', tips: ['Te digo qué bus tomar, dónde subirte, dónde bajarte y cuánto caminas.',
            'Cuando estés en el paradero toca «Empezar este viaje» y te acompaño paso a paso.', '«Ver otras opciones» muestra las demás rutas; «Cambiar desde o hasta» vuelve a la revisión.'], accion: '#gEmpezar' },
    };
    function estadoActual() {
        if (S.Viaje && S.Viaje.activo()) return 'viaje';
        const estado = $('tripStatus'), msg = estado ? estado.textContent.trim() : '';
        const p = puntosAhora(), hayOpciones = !!document.querySelector('#tripResults .trip-option');
        if (navigator.onLine === false) return 'error';
        if (!hayOpciones && /^Comparando/.test(msg)) return 'buscando';
        if (document.querySelector('.trip-option.selected')) return 'ruta';
        if (hayOpciones) return 'resultados';
        if (/Todavía no hay una ruta/.test(($('tripResults') || {}).textContent || '')) return 'sinrutas';
        if ((estado && estado.classList.contains('error') && !/^Primero selecciona/.test(msg) && p.origen && p.destino) || navigator.onLine === false) return 'error';
        if (p.origen && p.destino) return 'listos';
        if (p.origen || p.destino) return 'uno';
        return 'inicio';
    }
    const ayuda = $('ayudaModal');
    let accionPendiente = null, demoPendiente = null, temporizadorResalte = 0;
    function llenarLista(tips) { $('ayudaLista').replaceChildren(...tips.map((t) => { const li = document.createElement('li'); li.textContent = t; return li; })); }
    function montarTemas() {
        const cont = $('ayudaTemas');
        if (cont.childElementCount) return;
        TEMAS.forEach((t, i) => {
            const b = document.createElement('button'); b.type = 'button'; b.className = 'tema-chip'; b.dataset.tema = String(i);
            b.textContent = t.t;
            b.onclick = () => {
                if (t.escena === null) { $('ayudaTitulo').textContent = t.titulo; llenarLista(t.tips); accionPendiente = t.accion || null; demoPendiente = null; $('ayudaDemo').hidden = true; $('ayudaMapa').hidden = true; return; }
                cerrarAyuda({ devolver: false }); setTimeout(() => abrirLeccion(t), 200);
            };
            cont.append(b);
        });
    }
    /** Resalta unos segundos la acción recomendada (con poco movimiento: solo un borde fijo). */
    function resaltar(selector) {
        const el = selector ? document.querySelector(selector) : null;
        if (!el || !visible(el)) return;
        document.querySelectorAll('.ayuda-resalta').forEach((x) => x.classList.remove('ayuda-resalta'));
        el.classList.add('ayuda-resalta');
        const r = el.getBoundingClientRect();
        if (r.top < 0 || r.bottom > innerHeight) el.scrollIntoView({ block: 'center', behavior: reducido() ? 'auto' : 'smooth' });
        clearTimeout(temporizadorResalte);
        temporizadorResalte = setTimeout(() => el.classList.remove('ayuda-resalta'), 3600);
    }
    function abrirAyuda() {
        const guiado = !!(S.Guiado && S.Guiado.esGuiado && S.Guiado.esGuiado()) && !(S.Viaje && S.Viaje.activo()) && navigator.onLine !== false;
        const a = (guiado && AYUDAS_GUIADO[S.Guiado.paso()]) || AYUDAS[estadoActual()];
        $('ayudaTitulo').textContent = a.titulo;
        llenarLista(a.tips);
        accionPendiente = typeof a.accion === 'function' ? a.accion() : a.accion;
        demoPendiente = a.demo ? TEMAS[a.demo.tema] : null;      // (la ayuda del flujo guiado no ofrece la demostración del flujo avanzado)
        $('ayudaDemo').hidden = !demoPendiente;
        $('ayudaMapa').hidden = !a.practicaMapa;
        if (demoPendiente) $('ayudaDemo').textContent = a.demo.texto;
        montarTemas();
        const det = ayuda.querySelector('.ayuda-temas'); if (det) det.open = false;
        recordarAbridor();
        S.Modal.abrir(ayuda, { foco: $('ayudaCerrar'), retardo: 50, fondo: true, abridor, cerrar: () => cerrarAyuda() });
    }
    function cerrarAyuda({ devolver = true, resaltarAccion = false } = {}) {
        S.Modal.cerrar(ayuda, { devolver: false });
        if (devolver) devolverFoco();
        if (resaltarAccion && accionPendiente) setTimeout(() => resaltar(accionPendiente), 120);
    }
    $('helpButton').addEventListener('click', abrirAyuda);
    $('ayudaCerrar').onclick = () => cerrarAyuda({ resaltarAccion: true });
    $('ayudaDemo').onclick = () => { const t = demoPendiente; if (!t) return; cerrarAyuda({ devolver: false }); setTimeout(() => abrirLeccion(t), 200); };
    $('ayudaBien').onclick = () => { cerrarAyuda({ devolver: false }); abrirBienvenida(); };
    $('ayudaPractica').onclick = () => { cerrarAyuda({ devolver: false }); setTimeout(() => practica(), 250); };
    const menuAbierto = () => { const m = $('sideMenu'); return !!m && m.classList.contains('open'); };
    async function cerrarMenu() { if (!menuAbierto()) return; const c = $('closeMenu'); if (c) c.click(); for (let i = 0; i < 20 && menuAbierto(); i++) await sleep(50); await sleep(reducido() ? 0 : 380); }
    $('menuBienvenida').addEventListener('click', async () => { await cerrarMenu(); abrirBienvenida(); });
    $('menuPractica').addEventListener('click', async () => { await cerrarMenu(); practica(); });

    // ------------------------------------------------------------------ práctica breve: «No encontramos esa dirección» → «Elegir en el mapa»
    // Es una pantalla de EJEMPLO dibujada aquí (botones con el mismo nombre y aspecto que los del flujo real). No usa el buscador, ni Google, ni el selector del mapa, ni A/B, la cuenta,
    // el historial o un viaje: no publica ninguna dirección y no guarda nada. Se abre ENCIMA de la ayuda o la lección (pila de ventanas); al salir, el foco vuelve a quien la abrió.
    const pm = { el: null, paso: 1, punto: null };
    const PM_TEXTOS = {
        1: ['Paso 1 de 3', 'Toca Elegir en el mapa'], 2: ['Paso 2 de 3', 'Marca el punto'], 3: ['Paso 3 de 3', 'Confírmalo'], 4: ['Listo', 'Así puedes elegir el destino cuando no aparece en la lista'],
    };
    function construirPracticaMapa() {
        if (pm.el) return pm.el;
        const f = document.createElement('div'); f.id = 'practicaMapa'; f.className = 'modal-backdrop'; f.hidden = true;
        f.innerHTML = '<div class="modal-card pm-card" role="dialog" aria-modal="true" aria-labelledby="pmTitulo">'
            + '<p class="pm-sello">Práctica</p><p id="pmPaso" class="pm-paso"></p><h2 id="pmTitulo">Cuando no aparece la dirección</h2>'
            + '<div class="pm-pantalla" role="group" aria-label="Pantalla de ejemplo: no se guarda nada">'
            + '<p class="pm-etiqueta">Ejemplo de destino</p><div class="pm-campo" id="pmCampo">Calle 99 # 99-99, Villavicencio</div>'
            + '<p id="pmNoHay" class="pm-error" role="status">No encontramos esa dirección</p>'
            + '<div id="pmAcciones" class="pm-acciones"><button type="button" class="guiado-boton secundario" id="pmElegir">Elegir en el mapa</button></div>'
            + '<button type="button" id="pmMapa" class="pm-mapa" hidden aria-label="Mapa de práctica. Toca el lugar para marcar el punto, o pulsa Enter para marcar el centro.">'
            + '<svg viewBox="0 0 300 150" aria-hidden="true" focusable="false"><rect width="300" height="150" rx="14" class="pm-fondo"/><path class="pm-calle" d="M-5 100 305 66M70-5 96 155M200-5 184 155"/><rect class="pm-manzana" x="110" y="22" width="60" height="26" rx="6"/><rect class="pm-manzana" x="212" y="104" width="64" height="28" rx="6"/>'
            + '<g id="pmPin" hidden><path d="M0 0S-9-10-9-17a9 9 0 0 1 18 0C9-10 0 0 0 0z" fill="#176650" stroke="#fff" stroke-width="2"/><circle cy="-17" r="3.4" fill="#fff"/></g></svg></button>'
            + '<div id="pmConfirma" class="pm-acciones" hidden><button type="button" class="guiado-boton primario" id="pmSi">Sí, continuar</button></div>'
            + '<p id="pmHecho" class="pm-hecho" role="status" hidden></p></div>'
            + '<p id="pmInstruccion" class="pm-instruccion" aria-live="polite"></p>'
            + '<div class="pm-botones"><button id="pmAtras" class="secondary" type="button">Atrás</button><button id="pmOtra" class="secondary" type="button" hidden>Repetir la práctica</button><button id="pmListo" class="primary-plan-button" type="button" hidden>Entendido</button></div>'
            + '<button id="pmOmitir" class="text-button" type="button">Omitir</button></div>';
        document.body.appendChild(f); pm.el = f;
        const q = (id) => f.querySelector('#' + id);
        q('pmElegir').onclick = () => irPM(2, true);
        q('pmMapa').addEventListener('click', (e) => {
            const r = q('pmMapa').getBoundingClientRect(), teclado = e.detail === 0 || !r.width;
            pm.punto = teclado ? { x: 150, y: 80 } : { x: Math.max(12, Math.min(288, (e.clientX - r.left) / r.width * 300)), y: Math.max(22, Math.min(148, (e.clientY - r.top) / r.height * 150)) };
            irPM(3, true);
        });
        q('pmSi').onclick = () => irPM(4, true);
        q('pmAtras').onclick = () => irPM(pm.paso - 1, true);
        q('pmOtra').onclick = () => { pm.punto = null; irPM(1, true); };
        q('pmListo').onclick = () => cerrarPM(); q('pmOmitir').onclick = () => cerrarPM();
        return f;
    }
    function irPM(n, mover = false) {
        const f = pm.el; if (!f) return;
        if (n < 1) return cerrarPM();
        const antes = pm.punto; pm.paso = n; if (n < 3) pm.punto = null; else if (!pm.punto) pm.punto = antes;
        const q = (id) => f.querySelector('#' + id), [sub, instr] = PM_TEXTOS[n];
        q('pmPaso').textContent = sub; q('pmInstruccion').textContent = n === 4 ? '' : instr;
        q('pmNoHay').hidden = n === 4; q('pmCampo').hidden = n === 4; q('pmAcciones').hidden = n > 1; q('pmMapa').hidden = n < 2 || n === 4; q('pmConfirma').hidden = n !== 3; q('pmHecho').hidden = n !== 4;
        q('pmHecho').textContent = n === 4 ? instr : '';
        const pin = q('pmPin');      // (un <g> de SVG no tiene la propiedad `hidden`: se usa el atributo)
        pin.toggleAttribute('hidden', !(n === 3 && pm.punto)); if (pm.punto) pin.setAttribute('transform', 'translate(' + pm.punto.x.toFixed(1) + ' ' + pm.punto.y.toFixed(1) + ')');
        q('pmAtras').hidden = n === 1; q('pmOtra').hidden = n !== 4; q('pmListo').hidden = n !== 4; q('pmOmitir').hidden = n === 4;
        f.querySelectorAll('.ayuda-resalta').forEach((x) => x.classList.remove('ayuda-resalta'));
        const objetivo = n === 1 ? q('pmElegir') : n === 2 ? q('pmMapa') : n === 3 ? q('pmSi') : q('pmListo');
        if (n < 4) objetivo.classList.add('ayuda-resalta');      // el mismo resaltado de las ayudas, fijo mientras dure ese momento
        if (mover) setTimeout(() => { try { objetivo.focus({ preventScroll: true }); } catch { /* nada */ } }, 30);
    }
    function abrirPracticaMapa() {
        construirPracticaMapa(); pm.punto = null; irPM(1);
        S.Modal.abrir(pm.el, { foco: () => pm.el.querySelector('#pmElegir'), retardo: 60, fondo: true, abridor: document.activeElement, cerrar: () => cerrarPM() });
    }
    function cerrarPM() { if (pm.el && !pm.el.hidden) S.Modal.cerrar(pm.el); }
    $('bienPracticaMapa').onclick = abrirPracticaMapa;
    $('ayudaMapa').onclick = abrirPracticaMapa;

    // ------------------------------------------------------------------ práctica guiada (8 pasos sobre el FLUJO GUIADO real)
    // Dos puntos de ejemplo con ruta registrada. Si en la ciudad no hay ruta entre ellos (o el servicio no responde), la práctica sigue con un ejemplo ilustrado.
    const EJEMPLO = {
        a: { id: null, lat: 4.1165, lng: -73.6505, nombre: 'Serramonte (ejemplo)', direccion: null, fuente: 'Práctica', confirmado: true },
        b: { id: null, lat: 4.1330, lng: -73.6065, nombre: 'Cerca de la Terminal (ejemplo)', direccion: null, fuente: 'Práctica', confirmado: true },
    };
    const TOTAL = 8;
    let coach = null;
    const MINI_MARCADOR = '<div class="coach-mini" aria-label="Demostración de tu marcador"><p class="mini-rotulo">Así cambia tu marcador (demostración)</p><ol class="mini-marc">'
        + '<li><span class="m-azul" aria-hidden="true"></span><span class="mv-txt">Caminas: círculo azul</span></li>'
        + '<li><span class="m-bus" aria-hidden="true">R12</span><span class="mv-txt">En el bus: bus con su código</span></li>'
        + '<li><span class="m-azul" aria-hidden="true"></span><span class="mv-txt">Bajas: otra vez círculo azul</span></li></ol></div>';
    const MINI_AVISOS = '<div class="coach-mini" aria-label="Demostración de los avisos de bajada"><p class="mini-rotulo">Tres avisos (demostración)</p><ol class="mini-niveles">'
        + '<li class="n1"><b>Cerca:</b> ya casi llegas a tu bajada.</li><li class="n2"><b>Prepárate:</b> ve hacia la puerta.</li><li class="n3"><b>Ahora:</b> baja cuando el bus se detenga.</li></ol>'
        + '<p class="mini-tarjeta"><b>Tu bajada está aquí</b><span>Se queda en pantalla hasta que toques «Ya me bajé».</span></p>'
        + '<p class="mini-nota">La vibración y la notificación son opcionales: dependen de tu teléfono y de los permisos que des. Si no las tienes, el aviso en pantalla siempre sale.</p></div>';
    const MINI_TRANSBORDO = '<div class="coach-mini"><p class="mini-rotulo">Transbordo: dos buses</p><div class="mini-tb"><span class="chip c1">R12</span><span class="flecha">' + icono('flecha', 18) + '</span><span class="chip c2">R08</span><span class="mini-nota">Bajas del primero y subes al segundo</span></div></div>';

    function crearCoach() {
        const c = document.createElement('div');
        c.id = 'coach'; c.className = 'coach';
        c.innerHTML = '<div class="coach-bloqueo b-arriba"></div><div class="coach-bloqueo b-abajo"></div><div class="coach-bloqueo b-izq"></div><div class="coach-bloqueo b-der"></div><div class="coach-bloqueo coach-escudo" hidden></div>'
            + '<div class="coach-hueco" aria-hidden="true"><i class="onda"></i><i class="onda o2"></i></div>'
            + '<div class="coach-dedo" aria-hidden="true">' + icono('mano', 34) + '<i class="toque"></i></div>'
            + '<div class="coach-tarjeta" role="dialog" aria-modal="false" aria-label="Práctica guiada" tabindex="-1" data-pos="abajo"><div class="coach-cab"><img class="coach-guia" src="/img/marca/sevb-chiguiro-96.png" width="44" height="44" alt="" decoding="async">'
            + '<div class="coach-cab-txt"><p class="coach-paso"></p><div class="coach-progreso" aria-hidden="true">' + '<i></i>'.repeat(TOTAL) + '</div></div></div>'
            + '<p class="coach-simulacion" hidden><b>Ejemplo ilustrado:</b> es una simulación, no un recorrido real.</p>'
            + '<p class="coach-texto" aria-live="polite"></p><div class="coach-extra"></div>'
            + '<p class="coach-ok" role="status" hidden><span class="ok-chulo">' + icono('check', 18) + '</span><span class="ok-txt"></span></p>'
            + '<div class="coach-botones"><button type="button" class="secondary coach-salir">Salir</button><button type="button" class="secondary coach-atras" hidden>Atrás</button>'
            + '<button type="button" class="secondary coach-alt" hidden></button><button type="button" class="primary-plan-button coach-siguiente">Siguiente</button></div></div>';
        document.body.append(c);
        return c;
    }
    /**
     * El coach sigue al elemento señalado SOLO cuando algo cambia: tamaño de la ventana, desplazamiento, teclado virtual, cambios en la página,
     * el elemento que cambia de tamaño o transiciones/animaciones que lo mueven (se sigue unos instantes por cuadros y se vuelve a dormir).
     * Antes se medía en cada cuadro de pantalla durante toda la práctica.
     */
    function seguir(c) {
        let vivo = true, raf = 0, hasta = 0, ultimo = '', objetivo = null, desplazado = false; let ultimoDesp = 0;
        const hueco = c.querySelector('.coach-hueco'), dedo = c.querySelector('.coach-dedo'), tarjeta = c.querySelector('.coach-tarjeta'), escudo = c.querySelector('.coach-escudo');
        const bl = { arriba: c.querySelector('.b-arriba'), abajo: c.querySelector('.b-abajo'), izq: c.querySelector('.b-izq'), der: c.querySelector('.b-der') };
        const vv = window.visualViewport;
        const W = () => window.innerWidth, H = () => window.innerHeight;
        function bloquear(x, y, w, h) {
            Object.assign(bl.arriba.style, { left: '0px', top: '0px', width: W() + 'px', height: Math.max(0, y) + 'px' });
            Object.assign(bl.abajo.style, { left: '0px', top: (y + h) + 'px', width: W() + 'px', height: Math.max(0, H() - y - h) + 'px' });
            Object.assign(bl.izq.style, { left: '0px', top: y + 'px', width: Math.max(0, x) + 'px', height: h + 'px' });
            Object.assign(bl.der.style, { left: (x + w) + 'px', top: y + 'px', width: Math.max(0, W() - x - w) + 'px', height: h + 'px' });
        }
        /** La tarjeta va del lado donde quepa sin tapar lo señalado (usa el área realmente visible: teclado, barras y zonas seguras). */
        function colocar(r) {
            const vTop = vv ? vv.offsetTop : 0, vAlto = vv ? vv.height : H(), margen = 10;
            // Teclado abierto sobre el campo señalado (poca altura visible): la tarjeta pasa a una versión mínima para dejar a la vista el campo y sus sugerencias.
            const enCampo = !!(objetivo && document.activeElement && (document.activeElement === objetivo || objetivo.contains(document.activeElement)) && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName));
            tarjeta.dataset.teclado = enCampo && vAlto < 460 ? '1' : '0';
            const tope = vTop + margen, fondo = vTop + vAlto - margen;
            tarjeta.style.maxHeight = Math.max(160, fondo - tope) + 'px';
            let alto = Math.min(tarjeta.offsetHeight, fondo - tope);
            let pos = 'abajo';
            if (r) {
                const libreArriba = r.top - tope, libreAbajo = fondo - r.bottom, quepeArriba = libreArriba >= alto + 8, quepeAbajo = libreAbajo >= alto + 8;
                const prefiereArriba = (r.top + r.height / 2) > vTop + vAlto * 0.5;
                if (prefiereArriba ? quepeArriba : !quepeAbajo && quepeArriba) pos = 'arriba';
                else if (quepeAbajo) pos = 'abajo';
                else pos = libreArriba > libreAbajo ? 'arriba' : 'abajo';
            }
            // Celular girado (pantalla ancha y baja): si no cabe ni arriba ni abajo, la tarjeta se coloca al LADO de lo señalado, donde hay más espacio libre.
            let lado = null;
            if (r && W() >= 560) {
                const libreArriba = r.top - tope, libreAbajo = fondo - r.bottom;
                if (libreArriba < alto + 8 && libreAbajo < alto + 8) {
                    const libreIzq = r.left - margen, libreDer = W() - r.right - margen, room = Math.max(libreIzq, libreDer);
                    if (room >= 300) lado = { der: libreDer >= libreIzq, ancho: Math.min(460, room - 8) };
                }
            }
            // Ni arriba ni abajo cabe la tarjeta completa (el panel A y B ocupa mucho): se usa su versión mínima, con desplazamiento interno, SOLO en el espacio libre del lado elegido: nunca tapa lo señalado.
            if (r && !lado) {
                const libre = pos === 'arriba' ? r.top - tope : fondo - r.bottom;
                if (libre < alto + 8) {
                    tarjeta.dataset.teclado = '1';
                    const tope2 = Math.max(72, libre - 8);
                    tarjeta.style.maxHeight = tope2 + 'px';
                    alto = Math.min(tarjeta.offsetHeight, tope2);
                }
            }
            if (lado) {
                tarjeta.dataset.pos = 'lado';
                Object.assign(tarjeta.style, { bottom: 'auto', right: 'auto', width: lado.ancho + 'px', marginInline: '0', left: Math.round(lado.der ? W() - margen - lado.ancho : margen) + 'px' });
                tarjeta.style.top = Math.round(Math.max(tope, Math.min(r.top, fondo - alto))) + 'px';
                return;
            }
            Object.assign(tarjeta.style, { right: '', width: '', marginInline: '', left: '' });
            tarjeta.dataset.pos = pos;
            tarjeta.style.bottom = 'auto';
            tarjeta.style.top = Math.round(pos === 'arriba' ? tope : fondo - alto) + 'px';
        }
        function actualizar() {
            if (!vivo) return;
            const sel = c.dataset.sel, el = sel ? document.querySelector(sel) : null;
            if (el !== objetivo) { objetivo = el; if (ro) { ro.disconnect(); if (el) ro.observe(el); } desplazado = false; }
            // Con el teclado abierto (poca altura) y el cursor dentro del bloque señalado, se señala SOLO el campo (con su lista): el bloque entero ya no deja sitio a la tarjeta.
            const vv0 = window.visualViewport, bajo = (vv0 ? vv0.height : H()) < 460, a0 = document.activeElement;
            const ef = el && bajo && a0 && a0 !== el && el.contains(a0) && /^(INPUT|TEXTAREA)$/.test(a0.tagName) ? a0 : el;
            let r = ef && visible(ef) ? ef.getBoundingClientRect() : null;
            if (r && ef.getAttribute && ef.getAttribute('aria-controls')) {      // sugerencias abiertas bajo el campo: también deben quedar libres
                const lista = document.getElementById(ef.getAttribute('aria-controls'));
                if (lista && !lista.hidden && lista.getClientRects().length) { const l = lista.getBoundingClientRect(); r = { top: Math.min(r.top, l.top), bottom: Math.max(r.bottom, l.bottom), left: Math.min(r.left, l.left), right: Math.max(r.right, l.right), width: Math.max(r.right, l.right) - Math.min(r.left, l.left), height: Math.max(r.bottom, l.bottom) - Math.min(r.top, l.top) }; }
            }
            if (r && (r.width > 0 || r.height > 0)) {
                const m = 6, x = Math.max(-m, r.left - m), y = Math.max(-m, r.top - m), w = Math.min(W() + 2 * m, r.width + 2 * m), h = Math.min(H() + 2 * m, r.height + 2 * m);
                const clave = [x, y, w, h].map(Math.round).join(',') + c.dataset.dedo + c.dataset.escudo;
                if (clave !== ultimo) {
                    ultimo = clave;
                    Object.assign(hueco.style, { display: 'block', left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' });
                    bloquear(x, y, w, h);
                    escudo.hidden = c.dataset.escudo !== '1';
                    if (!escudo.hidden) Object.assign(escudo.style, { left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' });
                    dedo.style.display = c.dataset.dedo === '1' ? 'block' : 'none';
                    dedo.style.left = (x + w * 0.62) + 'px'; dedo.style.top = (y + h * 0.55) + 'px';
                }
                colocar(r);
                if ((r.top < 0 || r.bottom > H()) && (!desplazado || performance.now() - ultimoDesp > 1500)) { desplazado = true; ultimoDesp = performance.now(); if (el.closest && el.closest('#sheet')) { window.dispatchEvent(new CustomEvent('spevb-panel-completo')); setTimeout(() => { if (vivo) { desplazado = false; ultimoDesp = 0; rafla(900); } }, 1100); }      // si el panel aún se está acomodando (cambio de tamaño), se vuelve a comprobar
                el.scrollIntoView({ block: 'center', behavior: reducido() ? 'auto' : 'smooth' }); rafla(900); }
            } else {
                ultimo = ''; hueco.style.display = 'none'; dedo.style.display = 'none'; escudo.hidden = true;       // sin nada señalado: todo bloqueado menos la tarjeta
                bloquear(0, 0, 0, 0); Object.assign(bl.arriba.style, { height: H() + 'px' });
                colocar(null);
            }
        }
        const pedir = () => { if (!raf && vivo) raf = requestAnimationFrame(() => { raf = 0; actualizar(); if (performance.now() < hasta) pedir(); }); };
        function rafla(ms = 700) { hasta = Math.max(hasta, performance.now() + ms); pedir(); }
        const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => rafla(250)) : null;
        const dentro = (n) => n && n.nodeType === 1 && c.contains(n);
        // Los cambios dentro del mapa (el bus que anima, los marcadores que se mueven) ocurren en cada cuadro y no mueven lo que se señala: no cuentan.
        const delMapa = (n) => n && n.nodeType === 1 && !!n.closest('#map');
        const mo = new MutationObserver((lista) => { if (lista.some((m) => !dentro(m.target) && !delMapa(m.target))) rafla(450); });
        mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'hidden', 'open'] });
        const alMover = (e) => { if (!dentro(e.target) && !delMapa(e.target)) rafla(750); };
        const alCambiar = () => rafla(300);
        window.addEventListener('resize', alCambiar); window.addEventListener('orientationchange', alCambiar);
        window.addEventListener('scroll', pedir, { capture: true, passive: true });
        if (vv) { vv.addEventListener('resize', alCambiar); vv.addEventListener('scroll', pedir); }
        ['transitionrun', 'transitionend', 'animationend'].forEach((n) => document.addEventListener(n, alMover, true));
        const reposo = setInterval(pedir, 900);               // por si algo se mueve sin avisar (una imagen que carga): una vez cada casi segundo, no cada cuadro
        pedir();
        return {
            rafla,
            detener() {
                vivo = false; cancelAnimationFrame(raf); clearInterval(reposo); mo.disconnect(); if (ro) ro.disconnect();
                window.removeEventListener('resize', alCambiar); window.removeEventListener('orientationchange', alCambiar); window.removeEventListener('scroll', pedir, true);
                if (vv) { vv.removeEventListener('resize', alCambiar); vv.removeEventListener('scroll', pedir); }
                ['transitionrun', 'transitionend', 'animationend'].forEach((n) => document.removeEventListener(n, alMover, true));
            },
        };
    }
    function celebrar() {
        document.getElementById('coachFin')?.remove();
        const f = document.createElement('div');
        f.id = 'coachFin'; f.className = 'coach-fin'; f.setAttribute('role', 'status');
        const confeti = Array.from({ length: 12 }, (_, i) => '<i style="--i:' + i + '"></i>').join('');
        f.innerHTML = '<div class="fin-confeti" aria-hidden="true">' + confeti + '</div><div class="fin-tarjeta"><svg class="fin-chulo" viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="23"/><path d="M15 27.5 22.5 35 37.5 18"/></svg>'
            + '<h2>¡Muy bien!</h2><p>Ya sabes usar SEVB. Cuando quieras, busca tu viaje de verdad.</p><span class="fin-logro">' + icono('birrete', 20) + 'Logro: Aprendiz</span></div>';
        document.body.append(f);
        const quitar = () => { f.classList.add('saliendo'); setTimeout(() => f.remove(), 320); };
        f.addEventListener('click', quitar);
        setTimeout(quitar, 3400);
    }
    /** Ejemplo ilustrado (solo si el servicio de rutas no responde): todo está marcado como simulación y nada de esto es un recorrido real. */
    function panelDemo() {
        const d = document.createElement('div');
        d.id = 'coachDemo'; d.className = 'coach-demo'; d.setAttribute('aria-label', 'Ejemplo ilustrado (simulación)');
        d.innerHTML = '<p class="demo-sello">Ejemplo ilustrado · simulación</p>'
            + '<div class="demo-tarjeta"><span class="demo-chip">R12</span><span class="demo-main"><strong>Serramonte → Terminal</strong><small class="demo-camina">caminas unas 4 cuadras · bus 6,4 km</small></span><span class="demo-eta"><b>21</b><small>min</small></span></div>'
            + '<ol class="demo-pasos"><li>Camina unas 3 cuadras hasta el paradero.</li><li>Sube a la ruta R12.</li><li>Bájate en «Terminal».</li><li>Camina una cuadra hasta tu destino.</li></ol>'
            + '<div class="demo-transbordo"><span class="demo-chip dos">2 buses</span><small>Si hay que cambiar de bus, se ve así.</small></div>'
            + '<svg class="demo-mapa" viewBox="0 0 300 110" aria-hidden="true" focusable="false"><rect width="300" height="110" rx="14" fill="#e6efe8"/><path d="M-5 70 305 40M60-5 90 115M190-5 170 115" stroke="#fff" stroke-width="9" fill="none"/>'
            + '<path d="M30 92 55 92C100 92 110 52 160 52S238 30 270 22" stroke="#2f3640" stroke-width="4" stroke-dasharray="1 8" stroke-linecap="round" fill="none" opacity="0"/>'
            + '<path d="M52 88C96 86 112 50 160 50S236 34 270 24" stroke="' + ROJO + '" stroke-width="8" stroke-linecap="round" fill="none"/>'
            + '<path d="M22 100 52 88" stroke="#2f3640" stroke-width="4" stroke-dasharray="1 8" stroke-linecap="round" fill="none"/>'
            + '<circle cx="52" cy="88" r="6" fill="' + V + '" stroke="#fff" stroke-width="2.5"/><circle cx="270" cy="24" r="6" fill="#8e1b17" stroke="#fff" stroke-width="2.5"/>'
            + '<circle cx="22" cy="100" r="8" fill="' + AZUL + '" stroke="#fff" stroke-width="2.5"/><g transform="translate(278 4)"><path d="M8 0a8 8 0 0 0-8 8c0 6 8 14 8 14s8-8 8-14a8 8 0 0 0-8-8z" fill="' + NARANJA + '" stroke="#fff" stroke-width="1.5"/><circle cx="8" cy="8" r="3" fill="#fff"/></g></svg>'
            + '<div class="demo-iniciar" aria-hidden="true">Empezar este viaje</div>';
        return d;
    }

    /** opciones.ejemplo: otros puntos de ejemplo. opciones.pausa: milisegundos entre pasos automáticos; con 200 o menos (o con opciones.auto) la práctica se hace sola (pruebas).
     *  La práctica usa el FLUJO GUIADO real (mismos botones y mismos pasos): si la persona estaba en el planificador con A y B, pasa al paso a paso mientras practica y lo devuelve al salir. */
    async function practica(opciones = {}) {
        if (coach) return;
        if (S.Viaje && S.Viaje.activo()) return S.toast('Ya tienes un viaje en curso: termínalo antes de practicar.', { tipo: 'info', ms: 4000 });
        if (!S.Planner) return S.toast('La práctica no está disponible en este momento.', { tipo: 'info', ms: 4000 });
        await cerrarMenu();
        for (const id of ['ayudaModal', 'bienvenida']) { const m = $(id); if (m && !m.hidden) S.Modal.cerrar(m, { devolver: false }); }
        const ej = opciones.ejemplo || EJEMPLO, P = S.Planner, pausa = opciones.pausa ?? 700;
        const auto = opciones.auto === true || pausa <= 200, tecleo = !auto && !reducido() ? 38 : 0;
        // Lo que la persona tenía antes: se devuelve al terminar o al salir (puntos, resultados y el modo del planificador).
        const previo = { puntos: P.puntos(), resultados: !!document.querySelector('#tripResults .trip-option') };
        recordarAbridor();
        document.body.dataset.sinRegistro = '1';                // la búsqueda de práctica no cuenta como historial ni como hábito
        coach = crearCoach();
        document.body.classList.add('practicando');
        const seg = seguir(coach);
        const q = (s) => coach.querySelector(s);
        const botonSig = q('.coach-siguiente'), botonAtras = q('.coach-atras'), botonAlt = q('.coach-alt'), tarjeta = q('.coach-tarjeta');
        let salir = false, despertar = null, demo = false;
        const esperas = new Map();           // temporizadores pendientes: todos se cancelan al salir
        const dormir = (ms) => new Promise((res) => { if (salir || ms <= 0) return res(); const t = setTimeout(() => { esperas.delete(t); res(); }, ms); esperas.set(t, res); });
        const fin = () => { salir = true; esperas.forEach((res, t) => { clearTimeout(t); res(); }); esperas.clear(); if (despertar) despertar('salir'); };
        q('.coach-salir').onclick = fin;
        const onEsc = (e) => { if (e.key === 'Escape') { e.stopPropagation(); fin(); } };
        /** Con Tab solo se puede ir a lo señalado y a los botones de la tarjeta (todo lo demás está bloqueado también para teclado y lectores). */
        const onTab = (e) => {
            if (e.key !== 'Tab') return;
            const sel = coach.dataset.sel, el = sel && coach.dataset.escudo !== '1' ? document.querySelector(sel) : null;
            const lista = [...(el ? (el.matches(FOCO) ? [el] : [...el.querySelectorAll(FOCO)]) : []), ...tarjeta.querySelectorAll(FOCO)].filter(visible);
            if (!lista.length) return;
            const i = lista.indexOf(document.activeElement);
            const sig = e.shiftKey ? (i <= 0 ? lista.length - 1 : i - 1) : (i === lista.length - 1 ? 0 : i + 1);
            e.preventDefault(); lista[sig].focus({ preventScroll: true });
        };
        document.addEventListener('keydown', onEsc, true); document.addEventListener('keydown', onTab, true);
        const verPanel = () => window.dispatchEvent(new CustomEvent('spevb-panel-medio'));      // el panel a media altura (no usa «spevb-ir-inicio»: ese evento reinicia el flujo guiado)
        const verPanelCompleto = () => window.dispatchEvent(new CustomEvent('spevb-panel-completo'));
        const verMapa = () => window.dispatchEvent(new CustomEvent('spevb-focus-map'));
        const hayOpciones = () => !!document.querySelector('#tripResults .trip-option');
        const tocar = (id) => { const b = $(id); if (b && !b.disabled) b.click(); };
        let okTimer = 0;
        const confirmar = (texto) => {
            const ok = q('.coach-ok'); ok.hidden = false; q('.ok-txt').textContent = texto;
            ok.classList.remove('entra'); void ok.offsetWidth; ok.classList.add('entra');
            clearTimeout(okTimer); okTimer = setTimeout(() => { ok.hidden = true; }, 1400); esperas.set(okTimer, () => {});
        };
        /** Muestra un paso y espera: el botón principal, «Atrás», el botón extra o que se cumpla la condición. Devuelve 'sig', 'atras', 'alt', 'cond' o 'salir'. */
        function mostrar({ n, texto, sel = null, boton = null, atras = true, dedo = false, escudo = false, extra = '', alt = null, cond = null, foco = true, sub = '' }) {
            coach.dataset.sel = sel || ''; coach.dataset.dedo = dedo ? '1' : '0'; coach.dataset.escudo = escudo ? '1' : '0';
            const pd = sel && /demo-(\w+)/.exec(sel); coach.dataset.demo = pd ? ({ chip: 'tarjeta', eta: 'tarjeta', camina: 'tarjeta' }[pd[1]] || pd[1]) : '';
            tarjeta.classList.remove('cambia'); void tarjeta.offsetWidth; tarjeta.classList.add('cambia');
            q('.coach-paso').textContent = 'Práctica · paso ' + n + ' de ' + TOTAL + (sub ? ' · ' + sub : '');
            coach.querySelectorAll('.coach-progreso i').forEach((i, k) => { i.className = k + 1 < n ? 'hecho' : k + 1 === n ? 'actual' : ''; });
            q('.coach-texto').textContent = texto;
            q('.coach-extra').innerHTML = extra;
            q('.coach-simulacion').hidden = !demo;
            botonSig.hidden = !boton; if (boton) botonSig.textContent = boton;
            botonAtras.hidden = !atras;
            botonAlt.hidden = !alt; if (alt) botonAlt.textContent = alt;
            seg.rafla(900);
            if (foco) setTimeout(() => { if (!salir && coach) { const b = [botonSig, botonAlt].find(visible); (b || tarjeta).focus({ preventScroll: true }); } }, 80);
            return new Promise((resolver) => {
                let id = 0;
                const r = (v) => { clearInterval(id); despertar = null; resolver(v); };
                despertar = r;
                botonSig.onclick = () => r('sig'); botonAtras.onclick = () => r('atras'); botonAlt.onclick = () => r('alt');
                if (cond) id = setInterval(() => { if (!salir && cond()) r('cond'); }, 200);
            });
        }
        const escribir = async (campo, punto, modoPunto) => {
            const input = $(campo);
            if (input && tecleo > 0) { input.classList.add('coach-escribiendo'); for (let i = 1; i <= punto.nombre.length && !salir; i++) { input.value = punto.nombre.slice(0, i); await dormir(tecleo); } input.classList.remove('coach-escribiendo'); }
            if (!salir) P.poner(modoPunto, punto);      // elegir el punto avanza el flujo guiado real (igual que tocar una sugerencia)
        };

        // La práctica se hace SOBRE el planificador con A y B (el panel principal de siempre): se señalan sus campos y botones reales.
        const BLOQUE_B = '#formAB .endpoint-block:has(#tripDestination)', BLOQUE_A = '#formAB .endpoint-block:has(#tripOrigin)';      // (el botón de intercambiar está entre los dos bloques: nth-child no sirve)
        // ---- Paso 1 · Destino primero (1 de 2: escribir y elegir una sugerencia · 2 de 2: mirar el pin B en el mapa)
        async function paso1(desdeAtras) {
            let sub = P.puntos().destino && desdeAtras ? 2 : 1;
            while (!salir) {
                if (sub === 1) {
                    verPanel(); await dormir(reducido() || auto ? 0 : 380);
                    const hecho = () => !!P.puntos().destino;
                    if (auto && !hecho()) { coach.dataset.sel = BLOQUE_B; await dormir(Math.min(pausa, 300)); await escribir('tripDestination', ej.b, 'destination'); await dormir(Math.min(pausa, 300)); sub = 2; continue; }
                    const r = await mostrar({ n: 1, sub: '1 de 2', atras: false, sel: BLOQUE_B,
                        texto: hecho() ? 'Ya tienes tu destino. Sigue con el paso siguiente.' : 'Primero, a dónde vas. Escribe aquí el lugar y toca «Buscar» (o pulsa Enter). Google te muestra sugerencias: toca la correcta. Para seguir sin escribir, toca «Poner un ejemplo».',
                        boton: hecho() ? 'Siguiente' : 'Poner un ejemplo', cond: hecho, foco: !hecho() });
                    if (r === 'salir') return r;
                    if (r === 'sig' && !hecho()) { botonSig.hidden = true; await escribir('tripDestination', ej.b, 'destination'); }
                    if (salir) return 'salir';
                    if (hecho()) { confirmar('Destino puesto'); await dormir(auto ? 150 : 900); }
                    sub = 2;
                } else {
                    verPanel(); await dormir(reducido() || auto ? 0 : 200);
                    const r = await mostrar({ n: 1, sub: '2 de 2', sel: null, boton: 'Siguiente', atras: true,
                        texto: 'Mira el mapa: el pin B marca tu destino. Si no es el lugar correcto, escríbelo otra vez. Cuando esté bien, sigue.' });
                    if (r === 'salir') return r;
                    if (r === 'atras') { sub = 1; continue; }
                    return 'sig';
                }
            }
            return 'salir';
        }
        // ---- Paso 2 · Ahora, dónde estás (1: usar mi ubicación · 2: buscar una dirección · 3: elegir en el mapa · 4: poner un ejemplo · 5: mirar el pin A)
        async function paso2(desdeAtras) {
            let sub = P.puntos().origen && desdeAtras ? 5 : 1;
            while (!salir) {
                if (sub === 1) {
                    verPanel(); await dormir(reducido() || auto ? 0 : 300);
                    const r = await mostrar({ n: 2, sub: '1 de 5', sel: '#useMyLocation', escudo: true, boton: 'Siguiente',
                        texto: 'Ahora, desde dónde sales. Lo normal es tocar «Mi ubicación». En esta práctica no la vamos a usar, así que no la toques.' });
                    if (r === 'atras' || r === 'salir') return r;
                    sub = 2;
                } else if (sub === 2) {
                    const r = await mostrar({ n: 2, sub: '2 de 5', sel: '#searchOrigin', escudo: true, boton: 'Siguiente', texto: 'Otra manera: escribir una dirección en «¿De dónde sales?» y tocar «Buscar». Google te muestra sugerencias, igual que con el destino.' });
                    if (r === 'salir') return r;
                    sub = r === 'atras' ? 1 : 3;
                } else if (sub === 3) {
                    const r = await mostrar({ n: 2, sub: '3 de 5', sel: '#pickOrigin', escudo: true, boton: 'Siguiente', texto: 'Y otra más: «En el mapa». Tocas el mapa con el dedo en el lugar desde el que sales.' });
                    if (r === 'salir') return r;
                    sub = r === 'atras' ? 2 : 4;
                } else if (sub === 4) {
                    const hecho = () => !!P.puntos().origen;
                    if (hecho()) { sub = 5; continue; }
                    if (auto) { coach.dataset.sel = BLOQUE_A; await dormir(Math.min(pausa, 300)); await escribir('tripOrigin', ej.a, 'origin'); await dormir(Math.min(pausa, 300)); sub = 5; continue; }
                    const r = await mostrar({ n: 2, sub: '4 de 5', sel: BLOQUE_A, escudo: true, boton: 'Poner un ejemplo', texto: 'Para seguir, usaremos un lugar de ejemplo como punto de salida. Toca «Poner un ejemplo».' });
                    if (r === 'salir') return r;
                    if (r === 'atras') { sub = 3; continue; }
                    botonSig.hidden = true; await escribir('tripOrigin', ej.a, 'origin');
                    if (salir) return 'salir';
                    confirmar('Salida puesta'); await dormir(900); sub = 5;
                } else {
                    verPanel(); await dormir(reducido() || auto ? 0 : 200);
                    const r = await mostrar({ n: 2, sub: '5 de 5', sel: null, boton: 'Siguiente', texto: 'Mira el mapa: el pin A marca tu salida. Si no es el lugar correcto, cámbialo. Cuando esté bien, sigue.' });
                    if (r === 'salir') return r;
                    if (r === 'atras') { sub = P.puntos().origen ? 3 : 4; continue; }
                    return 'sig';
                }
            }
            return 'salir';
        }
        // ---- Paso 3 · Revisa y busca (1: revisar A y B · 2: buscar rutas)
        async function paso3(desdeAtras) {
            verPanel(); await dormir(reducido() || auto ? 0 : 300);
            let sub = hayOpciones() && !desdeAtras ? 2 : 1;
            if (sub === 1) {
                const r = await mostrar({ n: 3, sub: '1 de 2', sel: null, boton: 'Siguiente', texto: 'Revisa tu viaje: aquí ves desde dónde sales (A) y a dónde vas (B). Si algo está mal, puedes cambiarlo sin perder el otro lugar.' });
                if (r !== 'sig') return r;
            }
            verPanelCompleto(); await dormir(reducido() || auto ? 0 : 350);
            if (hayOpciones()) { demo = false; return mostrar({ n: 3, sub: '2 de 2', sel: '#tripResults', boton: 'Siguiente', foco: false, texto: 'Ya buscaste y SEVB encontró una recomendación. Sigue para aprender a leerla.' }); }
            const inicio = { t: 0 };
            const estado = () => {
                if (hayOpciones()) return 'ok';
                const st = $('tripStatus'), msg = st ? st.textContent.trim() : '';
                if (/Todavía no hay una ruta/.test(($('tripResults') || {}).textContent || '')) return 'vacio';
                if (st && st.classList.contains('error') && !/^Primero selecciona/.test(msg)) return 'fallo';
                if (/^Comparando/.test(msg)) { if (!inicio.t) inicio.t = Date.now(); if (Date.now() - inicio.t > 14000) return 'lento'; return 'buscando'; }
                return 'espera';
            };
            let ultimo = '';
            if (auto && !hayOpciones()) { coach.dataset.sel = '#planTrip'; await dormir(Math.min(pausa, 200)); }
            const r = await mostrar({ n: 3, sub: '2 de 2', sel: '#planTrip', dedo: true, foco: false, texto: 'Ahora toca «Buscar rutas». Tócalo tú.',
                cond: () => {
                    const e = estado();
                    if (e !== ultimo) {
                        ultimo = e;
                        if (e === 'buscando') { q('.coach-texto').textContent = 'Buscando tu ruta… un momento.'; coach.dataset.dedo = '0'; botonAlt.hidden = true; }
                        if (e === 'lento' || e === 'fallo' || e === 'vacio') { q('.coach-texto').textContent = e === 'vacio' ? 'Para este ejemplo no hay una ruta registrada.' : 'Ahora no pude traer rutas reales.'; botonAlt.hidden = false; botonAlt.textContent = 'Ver un ejemplo ilustrado'; }
                    }
                    return e === 'ok';
                } });
            if (r === 'alt') { demo = true; return 'sig'; }
            if (r === 'cond') { demo = false; confirmar('Ya hay una recomendación'); await dormir(auto ? 300 : 900); return 'sig'; }
            return r;
        }
        /** Paso 4 · Elige la recomendación: se explica una cosa por vez (razón, tiempo, caminata, buses y transbordo, ruta, otras opciones). */
        async function paso4(desdeAtras) {
            let subs;
            if (demo) {
                document.getElementById('coachDemo')?.remove();
                const d = panelDemo(); coach.append(d);
                subs = [['Este es el nombre de la ruta. Es el que ves escrito en el letrero del bus.', '#coachDemo .demo-chip'], ['Aquí está el tiempo aproximado, en minutos. No incluye la espera del bus.', '#coachDemo .demo-eta'],
                    ['Y aquí, cuánto caminas y cuánto vas en el bus.', '#coachDemo .demo-camina'], ['Aquí ves dónde subir, dónde bajar y cuánto caminas en cada tramo.', '#coachDemo .demo-pasos'], ['Si no hay un bus directo, verás «2 buses»: es un transbordo.', '#coachDemo .demo-transbordo']];
            } else {
                verPanelCompleto(); await dormir(reducido() || auto ? 0 : 350);
                const hay = (x) => { const e = document.querySelector(x); return !!e && visible(e); };
                subs = [];
                if (hay('#tripItinerario .itin-encabezado')) subs.push(['Este es el nombre de la ruta: el que ves escrito en el letrero del bus.', '#tripItinerario .itin-encabezado']);
                if (hay('#tripItinerario .itin-porque')) subs.push(['Aquí SEVB te dice por qué recomienda esta opción.', '#tripItinerario .itin-porque']);
                if (hay('#tripResults .trip-option.selected')) subs.push(['Aquí ves el tiempo aproximado, en minutos (no incluye la espera del bus), cuánto caminas y los buses que vas a usar. Si dice «2 buses», es un transbordo: bajas del primero y subes al segundo.', '#tripResults .trip-option.selected', MINI_TRANSBORDO]);
                if (hay('#tripItinerario .itin-pasos')) subs.push(['Estos son los pasos: dónde caminar, qué bus tomar y dónde bajarte. «Ver subida» y «Ver bajada» te muestran esos puntos en el mapa.', '#tripItinerario .itin-pasos']);
                if (hay('#tripResults .trip-option')) subs.push(['Si hay más opciones, toca otra tarjeta para verla en el mapa.', '#tripResults']);
                if (!subs.length) subs.push(['Si no hay un bus directo, verás «2 buses»: es un transbordo.', null, MINI_TRANSBORDO]);
            }
            let j = desdeAtras ? subs.length - 1 : 0, r = 'sig';
            while (!salir && j >= 0 && j < subs.length) {
                const [texto, sel, extra] = subs[j];
                r = await mostrar({ n: 4, sub: (j + 1) + ' de ' + subs.length, texto, sel, escudo: true, boton: j === subs.length - 1 ? 'Siguiente paso' : 'Siguiente', extra: extra || '', atras: true, foco: true });
                if (r === 'atras') { if (j === 0) return 'atras'; j--; } else if (r === 'sig' || r === 'cond') j++; else return r;
            }
            return r === 'salir' ? 'salir' : 'sig';
        }
        /** Paso 5 · Empieza un solo viaje: se señala el botón real pero NO se puede tocar (la práctica no inicia ningún viaje). */
        async function paso5() {
            if (!demo) { verPanelCompleto(); await dormir(reducido() || auto ? 0 : 300); }
            const real = !demo && visible($('startTrip'));
            return mostrar({ n: 5, sel: real ? '#startTrip' : '#coachDemo .demo-iniciar', escudo: true, boton: 'Siguiente',
                texto: 'Cuando estés en el paradero, toca «Iniciar viaje». Solo puede haber un viaje a la vez: para empezar otro, primero termina este. Ahora no lo toques: la práctica no inicia ningún viaje ni usa tu ubicación.' });
        }
        /** Paso 6 · Sigue tu marcador (solo explicación: no hay viaje real). */
        async function paso6() {
            document.getElementById('coachDemo')?.remove();
            verMapa(); await dormir(reducido() || auto ? 0 : 300);
            return mostrar({ n: 6, boton: 'Siguiente', extra: MINI_MARCADOR,
                texto: 'Durante el viaje, tú eres un círculo azul mientras caminas. Cuando confirmas que subiste al bus, el círculo se cambia por un bus con el código de la ruta. Al bajarte, vuelves a ser un círculo azul.' });
        }
        /** Paso 7 · Prepárate para bajar. */
        async function paso7() {
            return mostrar({ n: 7, boton: 'Siguiente', extra: MINI_AVISOS,
                texto: 'Antes de tu bajada te aviso tres veces: cerca, prepárate y ahora. Cuando aparece «Tu bajada está aquí», baja cuando el bus se detenga y toca «Ya me bajé».' });
        }
        /** Paso 8 · Termina el viaje. */
        async function paso8() {
            return mostrar({ n: 8, boton: 'Terminar práctica', alt: 'Hacer mi viaje real', foco: true,
                texto: 'Después de bajar, camina el último tramo. Cuando llegues, toca «Terminar viaje». ¡Listo! Ya sabes elegir tu destino, tu salida, buscar, leer la recomendación y seguir tu viaje. ¿Hacemos uno de verdad?' });
        }
        let completo = false, viajeReal = false;
        const restaurar = () => {
            try {
                P.limpiar();
                const { origen, destino } = previo.puntos;
                if (origen) P.poner('origin', origen);
                if (destino) P.poner('destination', destino);
                if (previo.resultados && origen && destino) setTimeout(() => { const b = $('planTrip'); if (b && !document.body.classList.contains('practicando')) b.click(); }, 300);
            } catch { /* sin planificador */ }
            setTimeout(() => { delete document.body.dataset.sinRegistro; }, previo.resultados ? 9000 : 400);
        };
        try {
            P.limpiar();      // la práctica usa el planificador con A y B (el panel principal): parte de campos vacíos y los devuelve al salir
            await dormir(180);
            let i = 1, volver = false;
            const pasos = [null, () => paso1(volver), () => paso2(volver), () => paso3(volver), () => paso4(volver), paso5, paso6, paso7, paso8];
            while (!salir && i <= TOTAL) {
                const r = await pasos[i]();
                if (salir || r === 'salir') break;
                volver = r === 'atras';
                if (r === 'alt' && i === TOTAL) { viajeReal = true; completo = true; break; }
                if (r === 'atras') i = Math.max(1, i - 1); else { if (i === TOTAL) { completo = true; break; } i++; }
            }
        } finally {
            const cancelado = salir && !completo;
            fin(); seg.detener(); clearTimeout(okTimer);
            document.removeEventListener('keydown', onEsc, true); document.removeEventListener('keydown', onTab, true);
            document.getElementById('coachDemo')?.remove();
            coach.remove(); coach = null; document.body.classList.remove('practicando');
            restaurar();
            if (completo) { if (S.Logros && S.Logros.marcarPractica) S.Logros.marcarPractica(); celebrar(); }
            else S.toast(cancelado ? 'Saliste de la práctica. Tus puntos siguen como estaban.' : 'Cuando quieras, busca tu viaje de verdad.', { tipo: 'info', ms: 5000, clave: 'practica' });
            if (viajeReal) { abridor = null; setTimeout(() => { verPanel(); const c = $('tripDestination'); if (c) c.focus({ preventScroll: true }); }, 400); } else devolverFoco();
        }
    }

    window.Spevb.Guia = { abrirPracticaMapa, abrirBienvenida, abrirAyuda, abrirLeccion, practica, estadoActual, visto, EJEMPLO, ESCENAS, TEMAS };

    // La primera vez, la bienvenida sale sola (no si se abrió un enlace compartido ni si ya hay un viaje en curso).
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            const compartido = /[?&]a=/.test(location.search) && /[?&]b=/.test(location.search);
            if (!visto() && !compartido && !hayModalAbierto() && !(S.Viaje && S.Viaje.activo())) abrirBienvenida();
        }, 900);
    });
})();
