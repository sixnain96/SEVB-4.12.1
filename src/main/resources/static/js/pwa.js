"use strict";
// Registra el service worker (sólo con HTTPS o localhost). Si falla, la aplicación sigue funcionando igual.
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    window.addEventListener("load", () => {
        const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1500));
        idle(() => navigator.serviceWorker.register("/sw.js").catch(() => { /* sin soporte */ }));
    });
}

// La instalación (botón «Instalar ahora» y el paso a paso por navegador) vive en instalar.js, dentro del menú ☰ → «Instalar en tu celular».
