// Genera src/main/resources/static/css/app.min.css: junta (en el orden de css/app.sources.txt) y minifica las hojas de index.html.
// Así la página principal pide 1 archivo de estilos en vez de 11 y no se bloquea el primer dibujo esperando muchas peticiones.
//
// Uso (desde la raíz del proyecto, con Node instalado):   node scripts/build-css.mjs
// Las hojas de origen siguen siendo la fuente de verdad: NUNCA edites app.min.css a mano. CssBundleTest falla si lo olvidas.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const carpeta = new URL('../src/main/resources/static/css/', import.meta.url);
const ESBUILD = 'esbuild@0.25.5'; // versión fija para que el resultado sea el mismo en cualquier equipo

const fuentes = readFileSync(new URL('app.sources.txt', carpeta), 'utf8')
    .split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith('#'));

// Se normalizan los saltos de línea para que la huella sea igual en Windows (CRLF) y Linux (LF). CssBundleTest hace lo mismo.
const textos = fuentes.map((f) => readFileSync(new URL(f, carpeta), 'utf8').replace(/\r\n/g, '\n'));
const unido = textos.join('\n');
const huella = createHash('sha256').update(unido, 'utf8').digest('hex');

const r = spawnSync(`npx --yes ${ESBUILD} --minify --loader=css --log-level=warning`,
    { input: unido, encoding: 'utf8', shell: true, maxBuffer: 64 * 1024 * 1024 });
if (r.status !== 0 || !r.stdout) {
    console.error(r.stderr || 'esbuild no devolvió resultado');
    process.exit(1);
}
if (r.stderr && r.stderr.trim()) console.warn(r.stderr.trim());

const cabecera = `/*! SEVB app.min.css - generado por scripts/build-css.mjs, no editar a mano - fuente-sha256: ${huella} */\n`;
writeFileSync(new URL('app.min.css', carpeta), cabecera + r.stdout.trimEnd() + '\n', 'utf8');

const origen = Buffer.byteLength(unido, 'utf8'), final = Buffer.byteLength(r.stdout, 'utf8');
console.log(`app.min.css: ${fuentes.length} hojas, ${(origen / 1024).toFixed(1)} KiB -> ${(final / 1024).toFixed(1)} KiB (${Math.round((1 - final / origen) * 100)}% menos)`);
