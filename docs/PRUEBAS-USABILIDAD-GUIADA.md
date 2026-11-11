# Prueba de usabilidad del flujo guiado · SEVB 4.15.0

**Estado: protocolo y plantillas listos. NO hay resultados.** Las pruebas automáticas (`e2e/guiado_e2e.py`) demuestran que los botones existen, se ven y funcionan; **no** demuestran que una persona los entienda. Esa comprobación física está **pendiente** y la hace el equipo con este guion.

## Quién participa (sin recopilar datos sensibles)
Mínimo 5 personas que **no hayan visto SEVB**: una persona mayor con poca experiencia con mapas; un adulto con experiencia digital baja; un joven; alguien que use letra grande o tenga dificultad de precisión al tocar; y una persona con experiencia (para comprobar que el flujo no la frena demasiado). Solo se anota un código (P1, P2…), nunca nombre, teléfono ni correo.

## Preparación
- Un celular real con GPS (Android y, si se puede, iPhone), con datos móviles, la aplicación recién abierta (borrar los datos del sitio para simular «primera vez»).
- Un sitio de partida y un destino **conocidos por la persona** dentro de Villavicencio. Para la prueba en casa se puede usar «Elegir en el mapa» o escribir una dirección.
- Una persona que observa en silencio y un cronómetro. Opcional: grabar solo la pantalla con permiso.
- Una segunda persona de confianza con otro celular para la parte de «Compartir mi viaje».

## Guion (se lee tal cual; **no se explica dónde tocar**)
> «Estás en [lugar conocido] y quieres llegar a [destino conocido]. Usa SEVB para encontrar cómo ir e iniciar el acompañamiento del viaje. Yo no puedo ayudarte; piensa en voz alta si quieres.»

Si la persona se queda quieta más de 30 segundos, solo se pregunta: «¿Qué esperas que pase ahora?» (se anota como duda). Se interviene únicamente por seguridad.

Parte 2 (cuando ya inició el viaje): «Quieres que [persona de confianza] pueda ver cómo vas.» Se observa si encuentra «Compartir mi viaje». Después: «Ahora ya no quieres compartir.» Se observa si encuentra «Dejar de compartir».

Parte 3 (corregir un error): «Te equivocaste de destino: era [otro lugar].» Se observa si logra volver y corregirlo sin empezar de cero.

## Qué se registra (una hoja por persona)
| Campo | Anotar |
|---|---|
| Código / perfil | P1 · mayor, baja experiencia… |
| ¿Completó el trayecto hasta iniciar el viaje sin ayuda? | Sí / No / Con ayuda (cuál) |
| Tiempo hasta identificar la primera acción | segundos |
| ¿Dónde dudó? (paso) | destino · confirmar destino · origen · confirmar origen · resumen · recomendación · viaje |
| ¿Qué texto no entendió? | cita breve |
| Toques equivocados (graves / leves) | número |
| Retrocesos | número |
| Veces que preguntó «¿ahora qué hago?» | número |
| ¿Entendió el permiso de ubicación? | Sí / No / Dudó |
| ¿Sabe cuál fue la ruta recomendada? | Sí / No |
| ¿Pudo corregir un error (Parte 3)? | Sí / No / Con ayuda |
| ¿Entendió que estaba compartiendo su ubicación? | Sí / No / Dudó |
| ¿Pudo dejar de compartir? | Sí / No / Con ayuda |
| Tiempo total | minutos |
| Confianza percibida (1 a 5) | número |
| Pregunta final: «¿Qué fue lo más confuso?» | respuesta textual |

## Criterios de aceptación para pasar a una segunda ronda
- Al menos **4 de 5** completan el flujo sin intervención.
- **Todas** identifican la primera acción en menos de 10 segundos.
- **Ninguna** necesita entender «A» y «B» para completar el trayecto.
- No más de **2** toques erróneos graves por participante.
- **Todas** pueden volver y corregir un lugar sin reiniciar.
- Quien lo pida debe poder **dejar de compartir** sin ayuda.

## Después de la ronda
Resumir (sin nombres) dónde se dudó, qué textos se cambiaron y qué se repitió; corregir y repetir con otras 5 personas. Los resultados reales **no** van en este documento hasta que existan.

## Cómo repetir lo automático antes de salir a la calle
```powershell
mvn clean verify "-Dsevb.sinDocker=true"
python e2e/js_syntax.py
python e2e/run_e2e.py        # una sola ejecución a la vez: no en paralelo sobre el mismo puerto
```
