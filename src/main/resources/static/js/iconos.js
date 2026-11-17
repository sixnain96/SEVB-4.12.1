'use strict';
/* Iconos propios de SEVB (4.14): dibujos sencillos en SVG, de trazo redondeado, que usan el color del texto (currentColor).
   Reemplazan a los emojis, que el proyecto no usa. Cada icono se dibuja en una cuadrícula de 24 × 24.
   Uso:  Spevb.Iconos.el('bus', { tam: 20 })  → elemento <svg>        ·        Spevb.Iconos.svg('casa')  → texto <svg>…</svg> para innerHTML. */
(() => {
    const NS = 'http://www.w3.org/2000/svg';
    // Cada entrada: contenido del SVG (trazos) y, si hace falta, que el relleno sea sólido.
    const D = {
        caminar: '<circle cx="13" cy="4.6" r="1.9"/><path d="M11.2 8.6 9 12.4l2.6 2-1.6 5.6M11.2 8.6l3.2 2.6 2.6.5M11.6 14.4l3.3 2.2.7 3.8"/>',
        bus: '<rect x="4" y="3.5" width="16" height="14" rx="3"/><path d="M4 11h16M8 17.5V20M16 17.5V20"/><circle cx="8" cy="14.2" r=".9" fill="currentColor"/><circle cx="16" cy="14.2" r=".9" fill="currentColor"/>',
        casa: '<path d="M3.5 11 12 4l8.5 7M6 9.5V20h12V9.5M10 20v-5.5h4V20"/>',
        maletin: '<rect x="3.5" y="7.5" width="17" height="12" rx="2.2"/><path d="M9 7.5V5.8A1.3 1.3 0 0 1 10.3 4.5h3.4A1.3 1.3 0 0 1 15 5.8v1.7M3.5 13h17M11 13v1.6h2V13"/>',
        pin: '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.4" fill="currentColor"/>',
        brujula: '<path d="M12 3l7 17-7-4-7 4z"/>',
        medalla: '<circle cx="12" cy="9.5" r="5.5"/><path d="M8.7 14 7 20.5l5-2.4 5 2.4-1.7-6.5M12 7l.9 1.9 2 .3-1.5 1.4.4 2L12 11.6 10.2 12.6l.4-2L9.1 9.2l2-.3z"/>',
        llama: '<path d="M12 21a6 6 0 0 0 6-6c0-3.6-2.5-5.6-3.5-9-2 1.2-2.6 3-2.6 3S9.5 7 11 3C7.8 5.5 6 9.5 6 15a6 6 0 0 0 6 6z"/>',
        estrella: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.8 6.8 19.6l1-5.8L3.5 9.7l5.9-.9z"/>',
        sol: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5V5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8"/>',
        luna: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
        candado: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
        birrete: '<path d="M2.5 9.5 12 5l9.5 4.5L12 14z"/><path d="M6.5 11.8V16c1.5 1.6 3.4 2.5 5.5 2.5s4-.9 5.5-2.5v-4.2M21.5 9.5V15"/>',
        check: '<path d="M4.5 12.8 9.5 18 19.5 6.5"/>',
        cruz: '<path d="M6 6l12 12M18 6 6 18"/>',
        giro: '<path d="M7 7h11l-3-3M17 17H6l3 3"/>',
        mano: '<path d="M9 11V5.5a1.6 1.6 0 0 1 3.2 0V11M12.2 10.2V9a1.6 1.6 0 0 1 3.2 0v2M15.4 10.8a1.6 1.6 0 0 1 3.2.3v4.2c0 3-2 5.2-5 5.2h-1.8c-1.6 0-2.6-.7-3.5-1.8L5 14.5a1.6 1.6 0 0 1 2.4-2L9 14"/>',
        play: '<path d="M8 5.5v13L19 12z" fill="currentColor"/>',
        pausa: '<path d="M8.5 5.5v13M15.5 5.5v13" stroke-width="3"/>',
        flecha: '<path d="M5 12h14M13 6l6 6-6 6"/>',
        ayuda: '<path d="M9.2 9.3a2.9 2.9 0 1 1 4.2 2.6c-.9.5-1.4 1.1-1.4 2.1M12 17.6v.1"/>',
        lupa: '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5 5"/>',
        gps: '<circle cx="12" cy="12" r="4"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
        paradero: '<path d="M8 3.5h8A1.5 1.5 0 0 1 17.5 5v6a1.5 1.5 0 0 1-1.5 1.5H8A1.5 1.5 0 0 1 6.5 11V5A1.5 1.5 0 0 1 8 3.5zM12 12.5V21M9 21h6M9.5 8h5"/>',
        transbordo: '<rect x="3" y="4" width="9" height="8" rx="2"/><rect x="12" y="12" width="9" height="8" rx="2"/><path d="M7.5 12v2.5A1.5 1.5 0 0 0 9 16h3M16.5 12V9.5A1.5 1.5 0 0 0 15 8h-3"/>',
        mapa: '<path d="M3.5 6.5 9 4l6 2.5 5.5-2.5v13.5L15 20.5 9 18l-5.5 2.5zM9 4v14M15 6.5v14"/>',
        reloj: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
        bajar: '<path d="M12 4v13M6.5 12l5.5 5.5 5.5-5.5M5 20.5h14"/>',
        // Fase D · llama de racha en cuatro tamaños (1–2, 3–6, 7–13 y 14+ días): misma cuadrícula, así caben en la misma fila. El número y el texto dicen la racha; el dibujo solo acompaña.
        llamaN1: '<path d="M12 20.5a4.4 4.4 0 0 0 4.4-4.4c0-2.7-1.9-4.2-2.6-6.8-1.5.9-2 2.2-2 2.2s-1.5-.6-.7-3.2C8.6 9.1 7.6 12 7.6 16.1a4.4 4.4 0 0 0 4.4 4.4z"/>',
        llamaN2: '<path d="M12 21a6 6 0 0 0 6-6c0-3.6-2.5-5.6-3.5-9-2 1.2-2.6 3-2.6 3S9.5 7 11 3C7.8 5.5 6 9.5 6 15a6 6 0 0 0 6 6z"/><path d="M12 20a2.4 2.4 0 0 0 2.4-2.4c0-1.6-1.2-2.4-1.8-3.8-.9.7-1 1.6-1 1.6s-1.3-.6-.9-2.2c-1.4 1.2-1.1 3.2-1.1 4.4A2.4 2.4 0 0 0 12 20z"/>',
        llamaN3: '<path d="M12 21a6 6 0 0 0 6-6c0-3.6-2.5-5.6-3.5-9-2 1.2-2.6 3-2.6 3S9.5 7 11 3C7.8 5.5 6 9.5 6 15a6 6 0 0 0 6 6z"/><path d="M12 20a2.4 2.4 0 0 0 2.4-2.4c0-1.6-1.2-2.4-1.8-3.8-.9.7-1 1.6-1 1.6s-1.3-.6-.9-2.2c-1.4 1.2-1.1 3.2-1.1 4.4A2.4 2.4 0 0 0 12 20z"/><path d="M3.5 12.5l1.6 1.2M3 17h2M20.5 12.5l-1.6 1.2M21 17h-2"/>',
        llamaN4: '<path d="M12 21.2a6 6 0 0 0 6-6c0-3.6-2.5-5.6-3.5-9-2 1.2-2.6 3-2.6 3S9.5 7.2 11 3.2C7.8 5.7 6 9.7 6 15.2a6 6 0 0 0 6 6z"/><path d="M12 20.2a2.4 2.4 0 0 0 2.4-2.4c0-1.6-1.2-2.4-1.8-3.8-.9.7-1 1.6-1 1.6s-1.3-.6-.9-2.2c-1.4 1.2-1.1 3.2-1.1 4.4a2.4 2.4 0 0 0 2.4 2.4z"/><path d="M3.5 12.5l1.6 1.2M3 17.5h2M20.5 12.5l-1.6 1.2M21 17.5h-2M4.5 7.5l1.4 1M19.5 7.5l-1.4 1M12 1.2v1.4"/>',
        // Medallas (Fase D): cada una con su propio dibujo
        ruta: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h5.5a3 3 0 0 0 0-6h-3a3 3 0 0 1 0-6H16"/>',
        dosbuses: '<rect x="2.5" y="4.5" width="10" height="9" rx="2"/><rect x="11.5" y="10.5" width="10" height="9" rx="2"/><path d="M2.5 9h10M11.5 15h10M5.5 13.5v1.6M18.5 10.5V9"/>',
        llano: '<circle cx="16.5" cy="7.5" r="2.6"/><path d="M2.5 17.5h19M4 17.5c2.2-3.2 4.7-4.3 7.2-4.3 2.2 0 3.6 1 5 2.2M5 20.5c2.5-1 5-1 7.5 0s5 1 7.5 0M8 13.4c-.2-1.6-.9-2.8-2-3.6M11 12.9c0-1.8.8-3.2 2-4"/>',
        chispa: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
    };
    const marco = (nombre, tam, clase) => '<svg xmlns="' + NS + '" viewBox="0 0 24 24" width="' + tam + '" height="' + tam + '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"'
        + (clase ? ' class="' + clase + '"' : '') + ' data-icono="' + nombre + '">' + (D[nombre] || '') + '</svg>';
    /** Texto <svg>…</svg> (para plantillas o innerHTML). Un nombre desconocido da un cuadro vacío, nunca un error. */
    function svg(nombre, { tam = 20, clase = '' } = {}) { return marco(nombre, tam, clase); }
    /** Elemento <svg> listo para insertar. */
    function el(nombre, { tam = 20, clase = '' } = {}) {
        const t = document.createElement('template');
        t.innerHTML = marco(nombre, tam, clase);
        return t.content.firstElementChild;
    }
    window.Spevb = window.Spevb || {};
    window.Spevb.Iconos = { svg, el, nombres: () => Object.keys(D) };
})();
