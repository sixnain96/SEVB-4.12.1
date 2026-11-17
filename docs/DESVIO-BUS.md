# Desvío del bus y «Tu parada quedó atrás» (Fase A)

> Estado: **sin publicar ni desplegar**, sobre 4.15.0. Código: `js/viaje-nucleo.js` (detector y referencia), `js/viaje.js` (tarjeta, aviso urgente, caminata real), `js/viaje-ruta.js` (mapa).
> Pruebas: `e2e/viaje_logica_e2e.py` (lógica, 14 casos nuevos), `e2e/desvio_bus_e2e.py` (interfaz, 14 casos), `e2e/simulador_gps.js` (escenario R006).

## 1. Diagnóstico: por qué la tarjeta decía «Todo va bien» con el conector naranja a la vista

En la prueba real con el bus **KIRPAS (R006)** la ruta pasaba por una calle en obras, el bus tomó otra y el mapa dibujó el conector naranja punteado, pero la tarjeta siguió con «Todo va bien». Había **tres mecanismos independientes**, sin relación entre sí:

| Mecanismo (antes) | Dónde | Qué decidía | Problema |
|---|---|---|---|
| Conector ámbar | `viaje-ruta.js` (`posicionMonotona` sobre la etapa) | Se dibujaba con **una sola lectura** a más de 150 m de la línea | No tenía tiempo, velocidad ni confirmación; nada de eso llegaba a la tarjeta. |
| `desvio_bus` | núcleo | Más de 150 m **y** velocidad de bus sostenida 20 s → un aviso de 15 s | `info()` no lo reflejaba: la instrucción seguía en «Todo va bien»; el aviso se apagaba solo. Además se activaba **falsamente** al pasar la bajada por la ruta normal (ver abajo). |
| `se_paso` y alerta «ahora» por distancia directa | núcleo | `dBmin ≤ 300 m` y alejarse 250 m (y 70 m en línea recta de la bajada) | Se podía disparar con el bus **desviado** pasando cerca de la parada por otra calle. |

Lo que **faltaba**: el dato `tramo` de cada bus (`planner.js → viajeDe`) es solo lo que el pasajero iba a recorrer, **de su subida a su bajada**: su geometría **termina en la bajada**. Una posición después de la parada se proyecta contra el final del tramo y parece «lejos de la ruta» (falso desvío tras pasar normalmente la parada) y, sobre todo, **no había con qué probar si el bus volvió a la ruta después de la parada**. Hace falta una **referencia** del recorrido que continúe después, en el sentido correcto.

## 2. La referencia del recorrido tras la bajada

`Spevb.ViajeNucleo.construirReferencia(tramo, recorrido, { sentidoRuta, sentidoViaje })` (pura, sin red) recibe el tramo del plan y la geometría completa de `/api/rutas/{id}` y devuelve la línea que lo contiene **en el sentido en que viaja el bus**, más los avances `a` (inicio del tramo) y `b` (la bajada) y `despues` (cuánta ruta queda tras la bajada). Comprueba que el tramo es **de verdad una parte contigua** del recorrido: extremos a ≤ 25 m, largo igual (±5 % o 40 m), todas las muestras (cada 50 m) a ≤ 20 m, **y en orden**.

| Caso | Resultado |
|---|---|
| Ruta normal (IDA/REGRESO) | referencia = recorrido. |
| Tramo en **sentido contrario** al dibujado (`sentidoViaje: SENTIDO_INVERSO`) | referencia = recorrido invertido. Si el plan dice «del trazado» pero el tramo va al revés: `no-coincide`. |
| Ruta **CIRCULAR** (el tramo puede cruzar el cierre del lazo, B antes que A) | referencia = la vuelta **duplicada**, para poder seguir después de cerrar el lazo. |
| Calle repetida en el mismo sentido, ramales, lazo que se cruza | el tramo cabe en más de un sitio → **`ambigua`**: nunca se elige una ocurrencia al azar; queda la incertidumbre. |
| El recorrido cambió desde que se planeó | `no-coincide`. |

**Cómo se obtiene (`viaje.js`, `cargarReferencia`)**: **una vez por bus** (nunca con cada lectura del GPS), en segundo plano (el viaje **no** la espera), con tiempo máximo de 9 s y **3 intentos** espaciados 25 s, cancelable (terminar el viaje o perder la concesión entre pestañas la aborta; una respuesta tardía se ignora por identidad de sesión). El plan ahora trae `rutaId`, `sentidoRuta` y `sentidoViaje` (`planner.js → viajeDe`); un plan guardado por una versión anterior sin `rutaId` resuelve primero `/api/rutas/codigo/{codigo}` (que también entiende códigos anteriores). Se verifica por **id, código/alias, sentido y versión** cuando existen (`otra-ruta`, `sentido`, `version`) y, siempre, por geometría. Si no hay detalle (sin red, 5xx, lento) o no corresponde: **sin referencia**, y el caso queda sin confirmar. El tramo original **no se toca**: sigue siendo la referencia de la ruta consumible y de la reanudación.

## 3. El detector (estados comprobables en el núcleo)

`info().desvio = { estado, incierta, prolongado, sigo, referencia, paradaAtras, atrasEmitido, incidente }` y `info().estimacion` (`normal` | `incierta`). La **tarjeta y el mapa leen el mismo estado**: el conector sale de `info.desvio`, no de su propia medición.

```
normal ──(> 150 m de la línea)──▶ posible ──(3 lecturas fuera, ≥ 15 s, el bus se movió)──▶ confirmado ──(retorno probado)──▶ normal        (volvió ANTES de la bajada)
   ▲                                │                                                              └──(retorno probado después de la bajada + margen)──▶ atras
   └──(2 lecturas sobre la línea)───┘
```

* **normal**: alertas de bajada y «te pasaste» como siempre (la heurística de distancia sigue usándose **solo** aquí).
* **posible**: mensaje prudente en la tarjeta «El bus parece haberse apartado de la ruta. Estamos comprobando el recorrido.»; tiempo y distancia pasan a **estimación incierta** (sin cifras); se quita «Todo va bien». Si el bus vuelve enseguida (2 lecturas) el aviso se retira solo.
* **confirmado**: «El bus se desvió de la ruta habitual. Te aviso si retoma la ruta y ya pasó tu bajada.» Persistente pero discreto (sin sonido, sin vibración, sin recuadro urgente; filo ámbar). Tras 120 s se añade «Pregunta al conductor si pasa por tu parada.» Sigue en `en_bus` con «Ya me bajé» a mano. La línea punteada se explica en la tarjeta: une la posición con el recorrido registrado, no es el camino del bus ni indica una obra.
* **atras**: «Tu parada quedó atrás» (ver §4).
* Durante `posible`/`confirmado`/`atras` **no** salen alertas de bajada por distancia directa ni «te pasaste» (`normal` es condición): no hay dos avisos por el mismo hecho. Sin referencia, seguir de largo después del final del tramo **no** cuenta como desvío (no se sabe qué hay después).

### Umbrales (todos en `CFG`, sobrescribibles con `opciones.cfg` en pruebas)

| Parámetro | Valor | Qué controla |
|---|---|---|
| `DESVIO_BUS_M` (existente) | 150 m | **Salir**: a más de esto de la línea. |
| `DESVIO_VOLVER_M` | **60 m** | **Volver** (umbral distinto: histéresis). Entre 60 y 150 m sigue «fuera». |
| `DESVIO_CONFIRMA_N` / `_MS` / `_MOV_M` | 3 lecturas / 15 s / 40 m | De posible a confirmado; el bus tiene que haberse movido (o ir a velocidad de bus): uno detenido no es un desvío. |
| `DESVIO_PRECISION_MAX` | 60 m | Precisión máxima para confirmar el desvío. |
| `DESVIO_POSIBLE_FIN_N` | 2 lecturas | Cierra un «posible» que nunca se confirmó. |
| `DESVIO_LARGO_MS` | 120 s | Ofrece «Pregunta al conductor…». |
| `RETORNO_N` / `_MS` / `_GANA_M` | **4 lecturas / 12 s / 60 m** | Racha de retorno: seguidas, con duración y con **avance a lo largo de la RUTA** (no distancia recta): un cruce, una glorieta o un semáforo no avanzan. |
| `RETORNO_PRECISION_MAX` | 35 m | Una lectura más imprecisa no cuenta **y rompe la racha**. |
| `RETORNO_SEPARACION_M` / `_SEP_AVANCE_M` | 30 m / 100 m | La línea debe estar claramente más cerca que otro tramo **no contiguo** (calles repetidas, ramales). |
| `RETORNO_VEL_MAX` / `_ATRAS_M` | 18 m/s / 300 m | Plausibilidad frente a la última posición fiable: ni saltos hacia delante (18 m/s + 40 m) ni retrocesos mayores que el ruido; el retorno puede quedar hasta 300 m antes (un lazo corto). |
| **`RETORNO_AVANCE_MIN_M`** | **20 m** | **Margen mínimo configurable** de avance **por encima de la parada** para afirmar que quedó atrás. Nunca es un disparador por distancia recta ni prueba suficiente: es una condición **más** además de la racha. |
| `RETORNO_K_PREC` | 1,5 | El margen real es `max(20 m, 1,5 × la peor imprecisión de la racha)`: con incertidumbre mayor que 20 m se exige más avance (más evidencia). |
| `REF_DESPUES_MIN_M` | 120 m | Si la ruta termina antes de esto tras la bajada, «ya pasó la parada» no se puede probar. |

**Reincorporación antes de la bajada**: con la racha completa y `a₀ < b + margen` (la primera lectura de la racha quedó antes de la parada o dentro de su margen), el desvío se cierra (`desvio_fin: retomo_antes`) y las alertas ordinarias siguen (incluida «Tu bajada está aquí» si volvió en el entorno de la parada: el bus todavía puede servirla). **Después de la bajada**: `a₀ ≥ b + margen`, **con referencia**, sin ambigüedad de vuelta en rutas circulares y con ≥ 120 m de ruta tras la bajada → `parada_atras`.

**Qué NO confirma el retorno** (cada uno probado): un punto aislado, mala precisión, una vía paralela a 70–80 m, un cruce perpendicular, un bucle que cruza la ruta dos veces, ir por la ruta en sentido contrario, GPS perdido (tras un hueco se exigen lecturas **nuevas**: la racha se rompe), un semáforo en plena reincorporación (detenido no avanza), el bus lento (solo tarda más) y la referencia ausente o ambigua.

### El dato que demuestra que la parada quedó atrás (simulación R006)

Recorrido de 5 km; el pasajero sube en x = 600 m y baja en x = 3000 m (referencia: `a ≈ 599 m`, `b ≈ 2997 m`, `despues ≈ 1998 m`). El bus sale por una calle «en obras» en x = 1800, avanza 400 m al norte en paralelo y retoma la ruta en x = 3600. `parada_atras` se emite cuando **las 4 lecturas de la racha** (`≥ 12 s`, `≥ 60 m` de avance, `≤ 35 m` de imprecisión) están **sobre la referencia** y su **avance mínimo ≥ b + 20 m** (la prueba comprueba los avances de las cuatro lecturas con el que el núcleo mide), con el bus ya sobre la ruta (y ≈ 0, no sobre la calle paralela a y = 400). Sin referencia (`sinRef`), la misma simulación **se queda en `confirmado`**.

Números de la corrida (`e2e/simulador_gps.js`, 1 lectura por segundo, tiempos desde el primer apartarse): `desvio_posible` 0 s · `desvio_confirmado` +15 s · `desvio_largo` +120 s · **`parada_atras` +362 s**, con el bus en x ≈ 3 683 m (686 m después de la bajada, y ≈ 0 m, de nuevo sobre la ruta; el retorno ocurrió en x = 3 600). Los avances de las 4 lecturas de la racha sobre la referencia: **3 658 · 3 665 · 3 672 · 3 679 m**, frente a `b + 20 = 3 017 m`. Con ruido de 8 m: +365 s (avances 3 685–3 712 m). Sin referencia: termina en `confirmado`, sin `parada_atras`.

## 4. «Tu parada quedó atrás»

Una **sola** tarjeta prioritaria y persistente: **reutiliza el recuadro de bajada** (`#viajeBajada`, `role="alertdialog"`, su foco, su Escape, su compatibilidad con el menú abierto y con la tarjeta minimizada o cedida): solo cambian el título y el texto («Tu parada quedó atrás» / «El bus retomó la ruta después de tu bajada. Baja en la próxima parada, cuando el bus se detenga.»), sin nombre de parada. Acciones: **«Ya me bajé»** y **«Sigo en el bus»**; Escape y «Sigo en el bus» conservan `en_bus`, ocultan el recuadro y dejan la instrucción accesible en la tarjeta (`aria-live="polite"`), sin repetir la alerta con cada lectura.

* **Una alerta urgente por incidente**: clave `atras:<tramo>:<incidente>` en `sesion.avisadas`; vibración (patrón de «ahora»), sonido y notificación respetan «Alertas de bajada». **La notificación no lleva nombres de lugares ni coordenadas** (solo «Baja en la próxima parada, cuando el bus se detenga.»).
* No salen a la vez «Tu bajada está aquí» y «Tu parada quedó atrás» por el mismo hecho: al confirmar la parada atrás el núcleo da por emitidas las alertas ordinarias y cierra `se_paso`; si el recuadro «ahora» ya estaba abierto se **actualiza** el mismo recuadro.
* **Mapa**: el tramo hasta la parada vieja se da por recorrido, su punto se atenúa y la caminata del plan (que parte de esa parada) se **oculta**: nunca se lleva visualmente al pasajero a la parada original.

## 5. «Ya me bajé» tras el desvío: caminata desde la bajada real

Si se confirma «Ya me bajé» con el bus en `posible`/`confirmado`/`atras`, el evento `fase` trae `desviada: true`, `estadoDesvio` y `bajadaReal`. `viaje.js → iniciarCaminataReal`:

1. **Ubicación**: se usa la lectura **actual** (de menos de 30 s, ±60 m o mejor, no la «antigua» de un viaje reanudado). Si no hay: «Todavía no tengo tu ubicación actual para calcular la caminata. Tu destino se mantiene…» y se reintenta sola con la próxima lectura buena, o con «Reintentar».
2. **Cálculo explícito** («Calculando tu caminata desde donde te bajaste…») con `/api/caminata`. Mientras tanto el mapa **no dibuja nada**: ni la parada vieja ni una recta como si se pudiera cruzar. Vuelve el círculo azul.
3. **Último bus**: destino original. Si a pie es poco razonable (> 2 000 m o > 30 min) o la red peatonal falla: «Reintentar» (si falló) y **«Recalcular desde aquí»** (planificador existente, con su confirmación de recálculo y el bloqueo de un único viaje).
4. **Con transbordo**: se conserva el siguiente bus solo si su subida queda a ≤ 1 000 m / 15 min a pie desde la bajada real; se dibuja la caminata nueva. Si no, «ya no te sirve» y se pide **otra recomendación hasta el destino original** (el mismo `recalcular()`: nada se reemplaza sin «Sí, cambiar»).
5. Respuestas tardías (otro viaje, otra bajada, el viaje terminó): se ignoran por identidad (`cam`) y por `AbortController`.

## 6. Robustez

* **Estado guardado mínimo** (`serializar()`): `dv: { estado, incidente, atrasEmitido, largo, sigo, ult }` (< 400 bytes con todo el estado del núcleo) solo si hay un desvío; un estado guardado por una versión anterior (sin `dv`) se acepta como `normal`. La caminata real nueva solo se guarda ya calculada (`cam`).
* **Reanudar con ubicación vieja**: se conserva el estado, pero **sin contadores ni lecturas**: el caso incierto espera lecturas nuevas (3 lecturas sobre la ruta no cierran un `confirmado`); con la parada atrás el recuadro vuelve **sin repetir vibración ni sonido**. La referencia se vuelve a pedir una vez.
* **Reinicio**: cambiar de bus (transbordo), terminar o cerrar el viaje reinician el desvío (`cambiarFase`/`terminar`).
* **Callbacks viejos y pestañas**: referencias, caminata real y GPS comprueban la identidad de la sesión; cambiar de pestaña u ocultar la página no reactiva el aviso.

## 7. Qué falta probar físicamente en un bus (no sustituible por simulación)

* **Geometría real de KIRPAS R006**: la repo no trae ese recorrido; las pruebas usan un recorrido sintético equivalente (5 km, ondulación de ±8 m). Hay que correr `construirReferencia` con el `recorrido` real de `/api/rutas/{id}` y comprobar que no sale `ambigua`/`no-coincide` por calles repetidas reales.
* **Ruido real del GPS urbano** (cañones de edificios, rebotes) frente a `RETORNO_PRECISION_MAX` (35 m) y al margen `max(20 m, 1,5 × imprecisión)`: puede tardar más de lo simulado en confirmar. Los umbrales están pensados para ajustarse con datos de campo.
* **Velocidades y paradas reales** (semáforos largos, filas, paradas de pasajeros sobre la reincorporación) y la distancia entre lecturas con el teléfono en segundo plano.
* **Vibración, sonido y notificaciones en un teléfono** (en las pruebas son dobles) y el aspecto del recuadro con la pantalla bloqueada.
* **Una glorieta real** en el punto de reincorporación y **dos ramales paralelos** de la ruta a menos de 100 m (la separación de 30 m puede ser insuficiente allí).
* Rutas **circulares** con un lazo corto (la ventana de búsqueda puede abarcar una vuelta entera y, por prudencia, no se decide: queda `confirmado`).
