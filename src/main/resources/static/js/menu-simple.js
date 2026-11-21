'use strict';
/* Menú principal simplificado (4.17). Solo presentación y plegado: no cambia ids, lógica de rutas, viaje, cuenta ni lugares.
   · Menú ☰: lo diario queda a la vista (Planear un viaje, cuenta, Mis lugares, Recientes) y lo demás vive dentro de «Más» (#menuMas).
     «Recientes» se muestra ya abierto cuando hay viajes recientes y la persona aún no lo plegó.
   · Panel de abajo: «Más» de las acciones del resultado (Google Maps, WhatsApp, Reportar) y el aviso largo del resultado recortado a dos líneas (toque para leerlo entero).
   · Instrucción por defecto («Marca A y B…») oculta: el título «¿A dónde vamos?» ya dice lo mismo (el texto sigue en el DOM por si otro aviso lo necesita). */
(() => {
    const $ = (id) => document.getElementById(id);

    // ------------------------------------------------------------------ acciones del resultado: «Más»
    const mas = $('tripToolsMas'), extra = $('tripToolsExtra'), barra = $('tripTools');
    function plegarAcciones() {
        if (!mas || !extra) return;
        extra.hidden = true; mas.setAttribute('aria-expanded', 'false');
        const t = mas.querySelector('span'); if (t) t.textContent = 'Más';
    }
    if (mas && extra && barra) {
        mas.addEventListener('click', () => {
            const abre = extra.hidden;
            extra.hidden = !abre; mas.setAttribute('aria-expanded', String(abre));
            const t = mas.querySelector('span'); if (t) t.textContent = abre ? 'Menos' : 'Más';
        });
        new MutationObserver(() => { if (barra.hidden) plegarAcciones(); }).observe(barra, { attributes: true, attributeFilter: ['hidden'] });
    }

    // ------------------------------------------------------------------ aviso del resultado: dos líneas y «toca para leer todo»
    const estado = $('tripStatus');
    const GUIA = /^Marca A y B en el mapa o escribe una dirección\.?$/;
    // Ojo: este observador mira el atributo «class»; solo se toca la clase cuando de verdad cambia (si no, cada escritura vuelve a dispararlo).
    const poner = (el, clase, on) => { if (el.classList.contains(clase) !== on) el.classList.toggle(clase, on); };
    function revisarEstado() {
        if (!estado) return;
        const t = estado.textContent.trim();
        poner(estado, 'es-guia', GUIA.test(t));
        const largo = t.length > 110 && estado.classList.contains('success');
        poner(estado, 'es-largo', largo);
        if (largo) { if (estado.tabIndex !== 0) estado.tabIndex = 0; estado.setAttribute('aria-expanded', String(estado.classList.contains('abierto'))); }
        else { poner(estado, 'abierto', false); if (estado.hasAttribute('tabindex')) estado.removeAttribute('tabindex'); if (estado.hasAttribute('aria-expanded')) estado.removeAttribute('aria-expanded'); }
    }
    if (estado) {
        new MutationObserver(revisarEstado).observe(estado, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['class'] });
        const alternar = () => { if (!estado.classList.contains('es-largo')) return; estado.classList.toggle('abierto'); estado.setAttribute('aria-expanded', String(estado.classList.contains('abierto'))); };
        estado.addEventListener('click', alternar);
        estado.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); alternar(); } });
        revisarEstado();
    }

    // ------------------------------------------------------------------ «Recientes» abierto si hay viajes recientes (y la persona no lo plegó)
    const espacio = $('menuEspacio'), recientes = $('recentTrips');
    let tocadoEspacio = false;
    if (espacio) {
        const sum = espacio.querySelector(':scope > summary');
        if (sum) sum.addEventListener('click', () => { tocadoEspacio = true; });
        const antesDeAbrir = () => {
            if (tocadoEspacio || document.body.classList.contains('viaje-activo')) return;
            if (recientes && !recientes.hidden && recientes.children.length) espacio.open = true;
        };
        ['menuButton', 'menuFlotante'].forEach((id) => { const b = $(id); if (b) b.addEventListener('click', antesDeAbrir, true); });
        document.addEventListener('click', (e) => { if (e.target.closest && e.target.closest('#menuFlotante')) antesDeAbrir(); }, true);
    }
})();
