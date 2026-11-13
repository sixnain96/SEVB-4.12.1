"""Capturas representativas del TUTORIAL (4.15.1) para docs/capturas-tutorial/: las 8 escenas de la bienvenida en 320 × 568 y pasos clave de la práctica en 320 × 568, 360 × 640 y 390 × 844.

No es una prueba (no afirma nada): solo guarda imágenes con datos de ejemplo (frontend real, API simulada, sin cuenta ni datos personales).
Uso: SEVB_E2E_URL=http://127.0.0.1:18080/ python e2e/capturas_tutorial.py
"""
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sevb_e2e as B  # noqa: E402
import aprender_e2e as A  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'capturas-tutorial')


def main():
    os.makedirs(SALIDA, exist_ok=True)
    with sync_playwright() as pw:
        nav = B.navegador(pw)
        # 1) Bienvenida: 8 escenas en 320 × 568
        s = B.Sesion(nav, viewport={'width': 320, 'height': 568}, is_mobile=True, has_touch=True, device_scale_factor=2)
        p = A.con_bienvenida(s)
        for i in range(8):
            p.wait_for_timeout(4200)
            p.screenshot(path=os.path.join(SALIDA, f'bienvenida-{i + 1}-320x568.png'))
            if i < 7:
                p.click('#bienSiguiente'); p.wait_for_timeout(300)
        s.cerrar()
        # 2) Práctica: pasos clave en tres tamaños
        for ancho, alto in ((320, 568), (360, 640), (390, 844)):
            s = B.Sesion(nav, viewport={'width': ancho, 'height': alto}, is_mobile=True, has_touch=True, device_scale_factor=2)
            p = s.abrir()
            p.evaluate(A.AUTO, A.EJEMPLO)
            A.hasta_paso(p, 1, '2 de 2', 8000); p.wait_for_timeout(900)
            p.screenshot(path=os.path.join(SALIDA, f'practica-1-confirmar-destino-{ancho}x{alto}.png')); A.siguiente(p)
            A.hasta_paso(p, 2, '1 de 5'); p.wait_for_timeout(900)
            p.screenshot(path=os.path.join(SALIDA, f'practica-2-usar-ubicacion-{ancho}x{alto}.png')); A.siguiente(p)
            A.hasta_paso(p, 2, '2 de 5'); A.siguiente(p)
            A.hasta_paso(p, 2, '3 de 5'); A.siguiente(p)
            A.hasta_paso(p, 2, '5 de 5'); A.siguiente(p)
            A.hasta_paso(p, 3, '1 de 2'); A.siguiente(p)
            A.hasta_paso(p, 3, '2 de 2'); p.wait_for_timeout(900)
            p.screenshot(path=os.path.join(SALIDA, f'practica-3-buscar-{ancho}x{alto}.png'))
            p.evaluate("document.getElementById('gBuscar').click()"); A.hasta_paso(p, 4, None, 20000); p.wait_for_timeout(1200)
            p.screenshot(path=os.path.join(SALIDA, f'practica-4-recomendacion-{ancho}x{alto}.png'))
            for _ in range(12):
                import re
                if not re.search(r'paso 4( |$)', A.coach_paso(p)):
                    break
                A.siguiente(p)
            A.hasta_paso(p, 5, None, 4000); p.wait_for_timeout(700)
            p.screenshot(path=os.path.join(SALIDA, f'practica-5-empezar-{ancho}x{alto}.png'))
            for n in (6, 7):
                A.siguiente(p); A.hasta_paso(p, n, None, 4000); p.wait_for_timeout(700)
                p.screenshot(path=os.path.join(SALIDA, f'practica-{n}-{"marcador" if n == 6 else "bajada"}-{ancho}x{alto}.png'))
            p.click('.coach-salir'); p.wait_for_timeout(500)
            s.cerrar()
        nav.close()
    print('Capturas guardadas en', SALIDA, '·', len(os.listdir(SALIDA)), 'archivos')


if __name__ == '__main__':
    main()
