"""Genera las capturas REALES del flujo guiado, del viaje, de compartir y de la página pública en tamaños de celular (docs/capturas/guiado/).

Frontend real + stub + GPS simulado, como las pruebas. No son maquetas: cada imagen sale de la aplicación funcionando.
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/capturas_guiado.py [ancho alto ...]      (ver también e2e/run_e2e.py)
"""
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import sevb_e2e as B  # noqa: E402
import viaje_e2e as V  # noqa: E402
import guiado_e2e as G  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

SALIDA = os.path.join(os.path.dirname(AQUI), 'docs', 'capturas', 'guiado')


def tomar(p, tam, n, nombre):
    os.makedirs(SALIDA, exist_ok=True)
    ruta = os.path.join(SALIDA, f'{tam}-{n:02d}-{nombre}.png')
    p.screenshot(path=ruta)
    print('captura', os.path.basename(ruta))


def recorrer(nav, ancho, alto):
    tam = f'{ancho}x{alto}'
    s = V.sesion(nav, guiado=True, viewport={'width': ancho, 'height': alto}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = s.abrir()
    B.esperar(p, "!!(Spevb.Guiado && Spevb.Planner.puntos)", 20000)
    p.wait_for_timeout(800)
    tomar(p, tam, 1, 'primera-pregunta')
    p.fill('#tripDestination', V.DEST)
    G.pulsar(p, '#gBuscarDestino')
    G.esperar_paso(p, 'confirmar_destino')
    p.wait_for_timeout(500)
    tomar(p, tam, 2, 'destino-confirmado')
    G.pulsar(p, '#gSiDestino')
    G.esperar_paso(p, 'origen')
    p.wait_for_timeout(300)
    tomar(p, tam, 3, 'eleccion-del-origen')
    G.elegir_origen_escribiendo(p, V.ESC['multi'])
    G.pulsar(p, '#gSiOrigen')
    G.esperar_paso(p, 'resumen')
    p.wait_for_timeout(400)
    tomar(p, tam, 4, 'resumen')
    G.pulsar(p, '#gBuscar')
    G.esperar_paso(p, 'recomendacion', 20000)
    p.wait_for_timeout(900)
    tomar(p, tam, 5, 'recomendacion')
    V.destino_lejos(p)
    ls = V.lecturas(p)
    G.pulsar(p, '#gEmpezar')
    B.esperar(p, "Spevb.Viaje.activo() && window.__geo.escuchas === 1", 8000)
    V.alimentar(p, ls, 0, 'fase:caminar')
    p.wait_for_timeout(900)
    tomar(p, tam, 6, 'viaje-en-curso')
    i = V.alimentar(p, ls, 0, 'pregunta')
    p.click('#viajeSi')
    p.wait_for_timeout(500)
    V.alimentar(p, ls[:i + 90], i)
    p.wait_for_timeout(300)
    tomar(p, tam, 7, 'ruta-parcialmente-consumida')
    p.wait_for_timeout(2500)
    # compartir: diálogo y enlace listo
    if p.get_attribute('#viajeMas', 'aria-expanded') != 'true':
        p.click('#viajeMas')
    p.click('#viajeCompartir')
    p.wait_for_timeout(500)
    tomar(p, tam, 8, 'compartir-explicacion')
    p.click('#compCrear')
    B.esperar(p, "!!JSON.parse(localStorage.getItem('spevb-compartir') || 'null')", 6000)
    p.wait_for_timeout(500)
    tomar(p, tam, 9, 'compartir-enlace-listo')
    t = p.evaluate("JSON.parse(localStorage.getItem('spevb-compartir'))")
    p.click('#compCerrar')
    V.alimentar(p, ls[:i + 120], i + 90)
    p.wait_for_timeout(800)
    pub = s.ctx.new_page()
    pub.set_viewport_size({'width': ancho, 'height': alto})
    pub.goto(B.URL.rstrip('/') + '/seguir.html#' + t['lectura'])
    B.esperar(pub, "!/Buscando/.test(document.getElementById('estado').textContent)", 8000)
    pub.wait_for_timeout(600)
    tomar(pub, tam, 10, 'pagina-publica-de-seguimiento')
    pub.close()
    V.viaje_completo(p, ls)
    B.esperar(p, "!!document.getElementById('viajeOtro')", 8000)
    p.wait_for_timeout(800)
    tomar(p, tam, 11, 'llegada')
    pub = s.ctx.new_page()
    pub.set_viewport_size({'width': ancho, 'height': alto})
    pub.goto(B.URL.rstrip('/') + '/seguir.html#' + t['lectura'])
    B.esperar(pub, "!/Buscando/.test(document.getElementById('estado').textContent)", 8000)
    pub.wait_for_timeout(500)
    tomar(pub, tam, 12, 'pagina-publica-llego')
    pub.close()
    s.cerrar()


if __name__ == '__main__':
    args = [int(x) for x in sys.argv[1:]]
    tamanos = list(zip(args[0::2], args[1::2])) or [(360, 640), (390, 844)]
    with sync_playwright() as pw:
        nav = B.navegador(pw)
        for ancho, alto in tamanos:
            recorrer(nav, ancho, alto)
        nav.close()
