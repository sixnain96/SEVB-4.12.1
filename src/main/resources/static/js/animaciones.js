'use strict';
/* Animaciones de los campos A y B (Fase P). Este archivo SOLO pone y quita clases; todo el movimiento (y su versión «reducir movimiento») está en css/motion.css.
   · Al abrir la app: A y B «caen», el conector punteado se dibuja y un punto baja de A a B (clase ab-intro, una sola vez y solo con los campos vacíos).
   · Al elegir una dirección (la 1.ª y la 2.ª): la letra late, un aro sale de ella, el borde del campo destella y un punto baja por el conector
     (punto-fijado / ab-viaja). Con las dos listas, el punto baja tres veces y las dos letras hacen la ola (ab-completo).
   · Si la persona se queda un buen rato sin tocar nada y falta una dirección, ese campo titila tres veces (pide). Es discreto: como mucho tres avisos seguidos,
     nada mientras haya un diálogo, el menú o el tutorial abiertos, ni con la pestaña oculta, ni si la persona ya está escribiendo.
   No toca la lógica del planificador: se entera de que una dirección quedó elegida por el atributo data-campo-estado de cada campo. */
(() => {
    const $ = (id) => document.getElementById(id);
    const form = $('formAB'), origen = $('tripOrigin'), destino = $('tripDestination');
    if (!form || !origen || !destino) return;
    const campos = { origin: origen, destination: destino };
    const bloque = (modo) => campos[modo].closest('.endpoint-block');
    const sinMovimiento = () => document.documentElement.dataset.motion === 'reduce' || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);

    /** Pone la clase (reiniciando la animación si ya estaba) y la quita pasado un tiempo. */
    function encender(el, clase, ms) {
        if (!el) return;
        el.classList.remove(clase); void el.offsetWidth; el.classList.add(clase);
        clearTimeout(el['_anim_' + clase]);
        el['_anim_' + clase] = setTimeout(() => el.classList.remove(clase), ms);
    }
    const apagar = (el, clase) => { if (el) { clearTimeout(el['_anim_' + clase]); el.classList.remove(clase); } };
    const confirmado = (modo) => campos[modo].dataset.campoEstado === 'confirmado';
    const vacio = (modo) => !campos[modo].value.trim();

    // ---------------------------------------------------------------- entrada de A y B al abrir la app
    let introHecha = false;
    function intro() {
        if (introHecha || sinMovimiento() || document.body.classList.contains('guiado')) return;
        const bien = $('bienvenida');
        if (bien && !bien.hidden) return;                       // con la bienvenida encima no se ve: espera a que se cierre
        if (!vacio('origin') || !vacio('destination')) return;  // si ya hay algo (viaje restaurado), no se anima
        introHecha = true;
        encender(form, 'ab-intro', 3400);
    }

    // ---------------------------------------------------------------- una dirección quedó elegida
    function fijado(modo) {
        if (sinMovimiento()) return;
        apagar(form, 'ab-intro');
        const ambos = confirmado('origin') && confirmado('destination');
        if (ambos) {
            apagar(form, 'ab-viaja');
            encender(bloque('origin'), 'punto-fijado', 1500); encender(bloque('destination'), 'punto-fijado', 1500);
            encender(form, 'ab-completo', 2400);
        } else {
            encender(bloque(modo), 'punto-fijado', 1200);
            encender(form, 'ab-viaja', 2300);
        }
        reiniciarEspera();
    }
    const observador = new MutationObserver((cambios) => cambios.forEach((c) => {
        if (c.target.dataset.campoEstado === 'confirmado' && c.oldValue !== 'confirmado') fijado(c.target === origen ? 'origin' : 'destination');
    }));
    [origen, destino].forEach((el) => observador.observe(el, { attributes: true, attributeFilter: ['data-campo-estado'], attributeOldValue: true }));

    // ---------------------------------------------------------------- «aquí falta algo»: el campo vacío titila tras un rato sin actividad
    const ESPERA_MS = 14000, REPITE_MS = 22000, MAX_AVISOS = 3;
    let reloj = null, avisos = 0;
    const pendiente = () => (vacio('origin') && !confirmado('origin') ? 'origin' : vacio('destination') && !confirmado('destination') ? 'destination' : null);
    /** El campo que falta se ve entero en pantalla (el panel puede estar a medio subir: solo importa ese campo, no todo el formulario). */
    function visible(modo) {
        const r = bloque(modo).getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.top >= 0 && r.bottom <= window.innerHeight && getComputedStyle(form).visibility !== 'hidden';
    }
    function ocupado(modo) {
        const menu = $('sideMenu');
        return document.hidden || document.body.classList.contains('guiado') || document.body.classList.contains('viaje-activo')
            || !!(menu && menu.classList.contains('open')) || !!document.querySelector('.modal-backdrop:not([hidden])')
            || form.contains(document.activeElement) || !visible(modo);
    }
    function programar(ms) { clearTimeout(reloj); reloj = setTimeout(avisar, ms); }
    function avisar() {
        const modo = pendiente();
        if (!modo) return;                                      // ya no falta nada: no hace falta insistir
        if (ocupado(modo)) { programar(REPITE_MS); return; }    // algo está en pantalla: se vuelve a intentar más tarde, sin gastar un aviso
        encender(bloque(modo), 'pide', 4400);
        if (++avisos < MAX_AVISOS) programar(REPITE_MS);
    }
    function reiniciarEspera() {
        avisos = 0;
        apagar(bloque('origin'), 'pide'); apagar(bloque('destination'), 'pide');
        programar(ESPERA_MS);
    }
    // cualquier toque, tecla o foco cuenta como actividad (la captura evita que otro código lo frene)
    ['pointerdown', 'keydown', 'focusin', 'input'].forEach((ev) => window.addEventListener(ev, reiniciarEspera, { passive: true, capture: true }));
    document.addEventListener('visibilitychange', () => { if (!document.hidden) reiniciarEspera(); });
    window.addEventListener('spevb-point-cleared', reiniciarEspera);

    // ---------------------------------------------------------------- arranque
    function arrancar() {
        intro();
        const bien = $('bienvenida');
        if (bien && !introHecha) new MutationObserver(() => { if (!bien.hidden) return; setTimeout(intro, 350); }).observe(bien, { attributes: true, attributeFilter: ['hidden'] });
        programar(ESPERA_MS);
    }
    if (document.readyState === 'complete') setTimeout(arrancar, 300);
    else window.addEventListener('load', () => setTimeout(arrancar, 300), { once: true });

    // para probar desde la consola o los e2e: Spevb.Animaciones.fijado('origin'), .avisar(), .intro()
    (window.Spevb || (window.Spevb = {})).Animaciones = { fijado, avisar, intro, reiniciarEspera, ESPERA_MS };
})();
