# Celebración al llegar (Fase E) y pruebas de campo pendientes

Estado: implementada y probada con GPS y Google **simulados**. Sin publicar. Código: `js/viaje.js` (`celebrarLlegada`, `lanzarConfeti`, `limpiarLlegada`), `js/logros.js` (resultado), `css/viaje.css` (bloque «Fase E»).

## Qué hace

- Solo `llegada()` (la llegada **válida** del viaje real, que ya emitía `spevb-viaje-llegada`) muestra, **en el primer cuadro** y en la misma tarjeta, un bloque con el **sello de SEVB** (círculo y check que se dibujan), «¡Llegaste a tu destino!» y un **confeti breve** (14 partículas, cada una dura 1,9 s y salen escalonadas: ≤ 2,5 s en total) en la franja de ese bloque. «Cerrar» y el aviso/sonido/vibración de siempre funcionan de inmediato; el guardado de logros puede seguir pendiente.
- Cuando se conoce el resultado de los logros llega como **detalle secundario** en la misma tarjeta: «Ganaste: Primer viaje, …» y «Racha de N días» (si aumentó). Sin tarjeta de llegada a la vista queda el aviso breve de antes. No hay segunda celebración.
- La tarjeta conserva el resultado hasta «Cerrar» (o «Planear otro trayecto» en el modo guiado, que no se tocó); el ciclo sigue en `llegada` hasta entonces.
- **Idempotente por viaje lógico (`viajeId`)**: repetir el evento no repite el confeti ni suma. Un resultado guardado de una llegada que nadie llegó a ver (recarga o segundo plano) se avisa **una vez** con un aviso breve, sin confeti y sin sumar nada.
- **Segundo plano:** si el viaje termina con la página oculta, el estado se conserva y el confeti se reproduce **una sola vez** al volver (nunca varios atrasados).
- **Movimiento reducido** (`prefers-reduced-motion` o `html[data-motion=reduce]`): sello estático, sin confeti, mismo texto.
- **Ligero y limpio:** partículas locales con `transform` y `opacity`, sin canvas ni dependencias, `pointer-events: none` y `aria-hidden`; se quitan con `animationend`, con un temporizador de respaldo de 3,2 s y al cerrar/reemplazar el viaje (`limpiarLlegada` desde `finalizar`). No cambia el layout (franja con `overflow: hidden`) y no tapa controles.
- **Lectores de pantalla:** el bloque visual es `aria-hidden`; la llegada la anuncia una sola vez el aviso (`role="alert"`) y el detalle «Ganaste…» es una región `status`/`aria-live=polite`. El foco no se mueve.
- **La práctica sigue siendo distinta:** conserva `#coachFin` (guia.js) y el logro «Aprendiz»; su recorrido simulado no suma viajes ni racha.

## Qué NO produce confeti

«Ya me bajé» tras un desvío (solo inicia la recuperación peatonal), pasar cerca del destino aún `en_bus`, abrir/cerrar el menú, «Terminar viaje» antes de llegar, GPS ruidoso, reanudar, recalcular, «Sigo en el bus». El confeti llega al **terminar la caminata** en el destino.

## Pruebas

`e2e/llegada_e2e.py` (11 pruebas): llegada a pie con confeti único y limpieza, medalla nueva y racha, llegada con el guardado pendiente, ausencia de llegadas falsas (menú, cerca del destino en el bus, terminar antes), GPS ruidoso y reanudar, movimiento reducido, segundo plano, viajes repetidos sin acumular partículas ni temporizadores, **recorrido integrado** (desvío → «Ya me bajé» → caminata desde el punto real → llegada → confeti, total y racha → cerrar), «Sigo en el bus», 320×568 y horizontal. Capturas: `docs/capturas-viaje/llegada-*.png`.

## Pruebas de campo pendientes (teléfono real; NO hechas)

Todo lo anterior usa GPS simulado. Falta, con un teléfono real y **un compañero que observe la app** (nadie debe decidir dónde bajar por una sola alerta):

1. **Bus desviado que SÍ vuelve antes de la parada:** el conector y el aviso de desvío deben retirarse solos, sin «Tu parada quedó atrás» y sin perder el progreso; la llegada solo se celebra al caminar hasta el destino.
2. **Bus desviado que vuelve DESPUÉS de la parada:** debe aparecer una sola vez «Tu parada quedó atrás»; «Ya me bajé» calcula la caminata desde el punto real y conserva el destino; «Sigo en el bus» conserva la fase. Confirmar que no hay confeti hasta llegar a pie.
3. Llegada real a pie con y sin medalla nueva; con el teléfono bloqueado o la app en segundo plano al llegar (un solo confeti al volver).
4. Transbordo real (dos subidas confirmadas → «Con transbordo»), recalcular durante el viaje y reanudar tras cerrar la pestaña.
5. Sonido y vibración reales al llegar, pantalla de 320 px y modo horizontal en el teléfono, lector de pantalla real (TalkBack/VoiceOver).
6. Rendimiento y batería de la animación en un teléfono de gama baja.
7. «Continuar con Google» real con un Client ID real (la celebración no depende de ello, pero el registro en la cuenta sí).

Si se prueba en la calle: ir acompañado, registrar con el compañero las horas y lugares en que la app acierta o falla, y no usar la app como única guía para bajar.
