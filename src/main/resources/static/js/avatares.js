'use strict';
/* Avatares regionales de respaldo (Orinoquía).
   Orden de prioridad en «Mi cuenta» y «Ajustes»: 1) foto de Google si carga · 2) avatar regional estable · 3) chigüiro local.
   MANIFIESTO es la ÚNICA lista que hay que editar para agregar o retirar una imagen (la carpeta es /img/avatares/). Mientras esté vacía
   no se usa ninguna imagen regional y se ve el chigüiro de siempre. Requisitos de los archivos y nombres esperados: docs/AVATARES.md.
   La asignación es determinista: el mismo identificador de cuenta da siempre el mismo avatar, también en otro dispositivo. Si cambia la
   cantidad de imágenes, la asignación puede cambiar (documentado). El identificador nunca se envía a ningún servidor ni va en una URL. */
(() => {
    const S = window.Spevb || (window.Spevb = {});
    const CARPETA = '/img/avatares/';
    /** Cada elemento: { archivo: 'nombre.webp', nombre: 'Nombre visible', descripcion: 'texto breve' }. Vacío = solo chigüiro. */
    const MANIFIESTO = [];

    /** Hash FNV-1a de 32 bits: sencillo, determinista y sin dependencias. */
    function hash(texto) {
        let h = 0x811c9dc5;
        const t = String(texto ?? '');
        for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
        return h >>> 0;
    }
    const valido = (e) => !!e && typeof e.archivo === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]*\.(webp|png)$/.test(e.archivo);
    /** Entrada del manifiesto para un identificador de cuenta, o null si no hay imágenes (o no hay identificador). */
    function para(identificador, lista = MANIFIESTO) {
        const l = (lista || []).filter(valido);
        const id = identificador == null ? '' : String(identificador).trim().toLowerCase();
        if (!l.length || !id) return null;
        const e = l[hash(id) % l.length];
        return { archivo: e.archivo, nombre: e.nombre || '', descripcion: e.descripcion || '', url: CARPETA + e.archivo };
    }
    S.Avatares = { MANIFIESTO, CARPETA, hash, para };
})();
