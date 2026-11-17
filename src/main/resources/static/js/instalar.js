'use strict';
/* «Instalar en tu celular» (menú ☰): detecta el navegador y el sistema y explica, paso a paso, cómo instalar SEVB como app (PWA).
   · No es un APK ni va a ninguna tienda: el propio navegador instala la página como una app (icono, pantalla completa, arranque rápido).
   · Detecta Chrome, Edge, Brave, Firefox, Safari, Samsung Internet y Opera en Android, iPhone/iPad y computador; si se equivoca, la persona elige el suyo en la lista.
   · Donde el navegador lo permite (beforeinstallprompt) hay un botón «Instalar ahora»; si ya está instalada lo dice; sin HTTPS explica por qué no se puede.
   · No guarda nada ni envía nada: todo ocurre en el dispositivo. */
(() => {
    const $ = (id) => document.getElementById(id);
    const caja = $('menuInstalar');
    if (!caja) return;

    const NAVEGADORES = {
        chrome: 'Chrome', edge: 'Edge', brave: 'Brave', firefox: 'Firefox', safari: 'Safari', samsung: 'Samsung Internet', opera: 'Opera', otro: 'otro navegador',
    };
    const SISTEMAS = { android: 'Android', ios: 'iPhone o iPad', desktop: 'computador' };

    // ------------------------------------------------------------------ detección (pura: se puede probar con cualquier User-Agent)
    function detectar(ua, plataforma, toques, brave) {
        ua = String(ua || ''); plataforma = String(plataforma || '');
        const ios = /iPhone|iPad|iPod/i.test(ua) || (plataforma === 'MacIntel' && toques > 1);
        const android = /Android/i.test(ua);
        const sistema = ios ? 'ios' : android ? 'android' : 'desktop';
        let nav = 'otro';
        if (/EdgA|EdgiOS|Edg\//.test(ua)) nav = 'edge';
        else if (/OPR\/|OPiOS|Opera/.test(ua)) nav = 'opera';
        else if (/SamsungBrowser/.test(ua)) nav = 'samsung';
        else if (/FxiOS|Firefox\//.test(ua)) nav = 'firefox';
        else if (brave) nav = 'brave';
        else if (/CriOS|Chrome\//.test(ua)) nav = 'chrome';
        else if (/Safari\//.test(ua) && /Version\//.test(ua)) nav = 'safari';
        else if (/Safari\//.test(ua)) nav = 'safari';
        return { sistema, nav };
    }

    // ------------------------------------------------------------------ pasos (texto simple; los símbolos entre {} se dibujan como iconos)
    const FIN = 'Busca el icono de SEVB en tu pantalla de inicio (o en tu lista de aplicaciones) y ábrelo: se abre como una app, sin barra del navegador.';
    const PASOS = {
        'android-chrome': ['Toca el menú {puntos} (tres puntos), arriba a la derecha.', 'Elige «Instalar aplicación» (en algunas versiones dice «Añadir a la pantalla de inicio»).', 'Confirma con «Instalar».', FIN],
        'android-brave': ['Toca el menú {puntos} (tres puntos) de Brave.', 'Elige «Instalar aplicación» o «Añadir a la pantalla de inicio».', 'Confirma con «Instalar» o «Añadir».', FIN],
        'android-edge': ['Toca el menú {puntos} (tres puntos) de Edge, abajo en el centro.', 'Elige «Añadir al teléfono» (o «Instalar»).', 'Confirma con «Instalar» o «Añadir».', FIN],
        'android-firefox': ['Toca el menú {puntos} (tres puntos) de Firefox.', 'Elige «Instalar» (o «Añadir a la pantalla de inicio»).', 'Confirma con «Añadir».', FIN],
        'android-samsung': ['Toca el menú {menu} (tres rayas), abajo a la derecha.', 'Elige «Añadir página a» y luego «Pantalla de inicio».', 'Confirma con «Añadir».', FIN],
        'android-opera': ['Toca el menú {puntos} (tres puntos) de Opera.', 'Elige «Añadir a» y luego «Pantalla de inicio».', 'Confirma con «Añadir».', FIN],
        'android-safari': ['Safari no existe en Android: abre este mismo enlace en Chrome y sigue los pasos de Chrome.'],
        'android-otro': ['Abre el menú de tu navegador (suele ser {puntos} o {menu}).', 'Busca «Instalar aplicación» o «Añadir a la pantalla de inicio».', 'Confirma y busca el icono de SEVB en tu pantalla de inicio.'],
        'ios-safari': ['Toca el botón Compartir {compartir} (un cuadrado con una flecha hacia arriba), abajo en el centro de Safari.', 'Desliza hacia abajo en el menú y elige «Añadir a pantalla de inicio».', 'Toca «Añadir», arriba a la derecha.', FIN],
        'ios-chrome': ['Toca el botón Compartir {compartir} (un cuadrado con una flecha), junto a la barra de direcciones.', 'Elige «Añadir a pantalla de inicio».', 'Toca «Añadir».', 'Si no ves esa opción, abre este enlace en Safari y sigue los pasos de Safari (Chrome en iPhone necesita iOS 16.4 o más reciente).'],
        'ios-edge': ['Toca el menú {puntos} (tres puntos) de Edge y luego «Compartir».', 'Elige «Añadir a pantalla de inicio».', 'Toca «Añadir».', 'Si no ves esa opción, abre este enlace en Safari y sigue los pasos de Safari.'],
        'ios-firefox': ['Toca el menú {menu} de Firefox y luego «Compartir».', 'Elige «Añadir a pantalla de inicio».', 'Toca «Añadir».', 'Si no ves esa opción, abre este enlace en Safari y sigue los pasos de Safari.'],
        'ios-otro': ['En iPhone y iPad la instalación es más segura desde Safari: abre este mismo enlace en Safari.', 'Toca Compartir {compartir} y elige «Añadir a pantalla de inicio».', 'Toca «Añadir».', FIN],
        'desktop-chrome': ['Mira a la derecha de la barra de direcciones: aparece un icono de instalar {instalar} (un monitor con una flecha). Tócalo.', 'Si no lo ves: menú {puntos} → «Transmitir, guardar y compartir» → «Instalar SEVB…».', 'Confirma con «Instalar». SEVB se abre en su propia ventana y queda en tu escritorio o menú de inicio.'],
        'desktop-edge': ['Mira a la derecha de la barra de direcciones: aparece un icono de instalar {instalar}. Tócalo.', 'Si no lo ves: menú {puntos} (tres puntos) → «Aplicaciones» → «Instalar este sitio como una aplicación».', 'Confirma con «Instalar».'],
        'desktop-brave': ['Mira a la derecha de la barra de direcciones: aparece un icono de instalar {instalar}. Tócalo.', 'Si no lo ves: menú {menu} → «Instalar SEVB…».', 'Confirma con «Instalar».'],
        'desktop-firefox': ['Firefox de escritorio normalmente no instala aplicaciones web.', 'Para instalar SEVB abre este enlace en Chrome o Edge.', 'Mientras tanto puedes guardar la página en marcadores con Ctrl + D.'],
        'desktop-safari': ['En el menú superior elige «Archivo».', 'Toca «Añadir al Dock…».', 'Confirma con «Añadir».'],
        'desktop-opera': ['Busca el icono de instalar {instalar} a la derecha de la barra de direcciones y tócalo.', 'Si no lo ves, abre este enlace en Chrome o Edge.'],
        'desktop-samsung': ['Abre este enlace en Chrome o Edge para instalar SEVB.'],
        'desktop-otro': ['Busca en el menú de tu navegador «Instalar aplicación» o un icono de instalar {instalar} junto a la barra de direcciones.', 'Si no aparece, abre este enlace en Chrome o Edge.'],
    };
    const NOTAS = {
        'android-firefox': 'En Firefox la opción puede llamarse «Instalar» o «Añadir a la pantalla de inicio» según tu versión.',
        'ios-chrome': 'En iPhone todos los navegadores usan el motor de Safari; el botón Compartir es el que instala.',
    };
    const ICONOS = {
        puntos: '<circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/>',
        menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
        compartir: '<path d="M12 15V3M8 7l4-4 4 4M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1"/>',
        instalar: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4M12 7v5M9.5 10 12 12.5 14.5 10"/>',
    };
    const icono = (nombre) => {
        const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('width', '18'); s.setAttribute('height', '18'); s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false'); s.setAttribute('class', 'instalar-ico');
        s.setAttribute('fill', nombre === 'puntos' ? 'currentColor' : 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '2'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
        s.innerHTML = ICONOS[nombre] || '';
        return s;
    };
    /** Un paso como texto con los {símbolos} dibujados (nunca HTML recibido de fuera: todo sale de las tablas de arriba). */
    function paso(texto) {
        const li = document.createElement('li');
        texto.split(/(\{[a-z]+\})/).forEach((trozo) => {
            const m = /^\{([a-z]+)\}$/.exec(trozo);
            if (m && ICONOS[m[1]]) li.append(icono(m[1])); else if (trozo) li.append(document.createTextNode(trozo));
        });
        return li;
    }

    // ------------------------------------------------------------------ estado
    let evento = null, actual = null, brave = false;
    const instalada = () => (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
    const seguro = () => window.isSecureContext !== false;

    function pintar() {
        const lista = $('instalarPasos'), det = $('instalarDetectado'), nota = $('instalarNota'), ahora = $('instalarAhoraCaja'), sel = $('instalarOtro');
        const clave = actual.sistema + '-' + actual.nav;
        if (sel && sel.value !== clave) sel.value = PASOS[clave] ? clave : actual.sistema + '-otro';
        det.textContent = instalada() ? 'Ya tienes SEVB instalada en este dispositivo.' : 'Estás usando ' + NAVEGADORES[actual.nav] + ' en ' + SISTEMAS[actual.sistema] + '.';
        lista.replaceChildren();
        nota.textContent = '';
        ahora.hidden = true;
        if (instalada()) { lista.hidden = true; return; }
        lista.hidden = false;
        if (!seguro()) {
            nota.textContent = 'Esta página se abrió sin conexión segura (http://). Los navegadores solo ofrecen instalar desde una dirección https:// (o localhost). Abre SEVB con su dirección https:// para poder instalarla.';
            lista.hidden = true;
            return;
        }
        (PASOS[clave] || PASOS[actual.sistema + '-otro']).forEach((t, i) => { const li = paso(t); li.dataset.n = String(i + 1); lista.append(li); });
        nota.textContent = NOTAS[clave] || '';
        ahora.hidden = !evento;      // el navegador avisó que puede instalar con un toque
    }

    function iniciar() {
        actual = detectar(navigator.userAgent, navigator.platform, navigator.maxTouchPoints || 0, brave);
        const sel = $('instalarOtro');
        if (sel && !sel.options.length) {
            [['android-chrome', 'Chrome · Android'], ['android-brave', 'Brave · Android'], ['android-edge', 'Edge · Android'], ['android-firefox', 'Firefox · Android'], ['android-samsung', 'Samsung Internet · Android'], ['android-opera', 'Opera · Android'],
                ['ios-safari', 'Safari · iPhone/iPad'], ['ios-chrome', 'Chrome · iPhone/iPad'], ['ios-edge', 'Edge · iPhone/iPad'], ['ios-firefox', 'Firefox · iPhone/iPad'],
                ['desktop-chrome', 'Chrome · computador'], ['desktop-edge', 'Edge · computador'], ['desktop-brave', 'Brave · computador'], ['desktop-firefox', 'Firefox · computador'], ['desktop-safari', 'Safari · Mac'], ['android-otro', 'Otro navegador']]
                .forEach(([v, t]) => { const o = document.createElement('option'); o.value = v; o.textContent = t; sel.append(o); });
            sel.addEventListener('change', () => { const [sis, nav] = sel.value.split('-'); actual = { sistema: sis, nav }; pintar(); });
        }
        pintar();
    }

    window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); evento = e; if (actual) pintar(); });
    window.addEventListener('appinstalled', () => { evento = null; if (actual) pintar(); });
    const boton = $('instalarAhora');
    if (boton) boton.addEventListener('click', async () => {
        if (!evento) return;
        const e = evento; evento = null; pintar();
        try { e.prompt(); await e.userChoice; } catch { /* sin respuesta: se vuelve a ofrecer la guía */ }
    });
    if (window.matchMedia) { try { window.matchMedia('(display-mode: standalone)').addEventListener('change', () => { if (actual) pintar(); }); } catch { /* navegador antiguo */ } }

    window.Spevb = window.Spevb || {};
    window.Spevb.Instalar = { detectar, pasos: (clave) => (PASOS[clave] || []).slice(), claves: () => Object.keys(PASOS), actual: () => actual && { ...actual } };
    // Brave se reconoce con una pregunta propia (no aparece en el User-Agent).
    const listo = () => { try { return navigator.brave && navigator.brave.isBrave ? navigator.brave.isBrave() : Promise.resolve(false); } catch { return Promise.resolve(false); } };
    listo().then((b) => { brave = !!b; }).catch(() => { brave = false; }).then(iniciar);
})();
