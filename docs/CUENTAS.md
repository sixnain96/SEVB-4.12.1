# Cuentas · «Continuar con Google» como única vía pública (Fase B)

> Estado: **sin publicar ni desplegar**, sobre 4.15.0. Código: `CuentaController`, `CuentaService`, `GoogleTokenVerifier`, migración `V14`, `js/cuenta.js`. Configuración de Google: `docs/GOOGLE.md`.
> Pruebas: `CuentaControllerTest`, `GoogleTokenVerifierTest`, `CuentaIdentidadPostgresTest` (PostgreSQL real) y `e2e/cuenta_google_e2e.py` (navegador, con Google simulado).

Funciona igual en computador, celular y tablet. **Sin cuenta todo sigue funcionando** en ese dispositivo (planear rutas, modo viaje, lugares, historial); con cuenta, los mismos datos aparecen en tus otros equipos.

## Modelo

* **Identidad = el `sub` de Google** (índice único `ux_usuarios_google`). **Propiedad de los datos = el id interno de SEVB** (`usuarios.id`): lugares, rutas favoritas, viajes guardados e historial (`usuario_datos`), sesiones y enlaces compartidos cuelgan de ese id.
* **El correo ya no identifica a nadie.** Un correo (aunque lo verifique Google) no demuestra que una persona sea la dueña de una cuenta ANTIGUA creada con contraseña: el correo de esas cuentas nunca se verificó y pudo escribirlo cualquiera. Por eso ya no se «vincula por correo» (V14 relaja la unicidad del correo: solo es único entre cuentas locales, sin Google).
* **Los permisos no se guardan ni se heredan.** Ser administrador se calcula con el correo que Google verificó en el inicio de sesión (`ADMIN_CORREOS`); una cuenta antigua con ese correo no es administradora (ni siquiera tiene sesión válida). Limitación conocida: en un dominio de Google Workspace que borre y vuelva a crear un correo, la nueva cuenta con ese correo sí sería administradora (la lista es por correo). Mantén `ADMIN_CORREOS` con correos que controlas.
* La **foto de perfil** (`picture` del token verificado) se acepta solo por HTTPS desde `*.googleusercontent.com` y se renueva en cada entrada; el avatar regional/chigüiro sigue de respaldo.

## Lo que ve la persona

* Menú → **un único botón «Continuar con Google»** (invitados) o «Ajustes de la cuenta / Cerrar sesión» (con sesión). Tocarlo abre un diálogo breve con **el control oficial de Google** (cargado solo en ese momento, nunca solo) y estos estados: «Preparando el acceso con Google…», listo, «Entrando con Google…» o un error **con «Reintentar» y «Seguir sin cuenta»** (Google no configurado, sin conexión, sin respuesta del servidor, Google bloqueado, dirección temporal sin autorizar —con la dirección oficial si está configurada—, credencial rechazada). Nunca queda vacío.
* La primera entrada y las siguientes empiezan en el mismo botón. Cerrar sesión borra los datos personales de ESE dispositivo (siguen en la cuenta).
* **Eliminar la cuenta**: Ajustes → «Eliminar mi cuenta…» → confirmar con Google (**reautenticación reciente de la MISMA cuenta de Google**) → confirmación final «Sí, eliminar para siempre» (el foco cae en «No, conservar mi cuenta»). No depende de ninguna contraseña (ni de un hash antiguo).
* Para cualquier función que necesite cuenta (el siguiente bloque: **lugares privados**): `Spevb.Cuenta.requiere(motivo)` devuelve el usuario (abre el mismo diálogo si hace falta, con el motivo escrito) o `null` si la persona decide seguir sin cuenta; `pedirEntrada({motivo})` es lo mismo sin atajos. Sirve de punto único: nadie abre sesión por su cuenta.

## Servidor: qué se retiró y qué se conserva

| | |
|---|---|
| `POST /registro`, `POST /entrar`, `POST /clave` | **410 Gone** «El acceso con correo y contraseña ya no está disponible. Usa «Continuar con Google».» No emiten sesiones ni tocan la base. Siguen mapeados (el contrato público «ningún endpoint desaparece» se mantiene). |
| `POST /google` | Única vía para abrir sesión. Verifica **firma RS256 (JWKS), emisor, audiencia (+ `azp`), vigencia (`exp`, `iat`, `nbf`), correo verificado, `sub` y correo acotados** y que la credencial **no se haya usado antes** (huella SHA-256 en memoria hasta su vencimiento). Cookie `spevb_sesion`: HttpOnly, SameSite=Lax, `Secure` en HTTPS, 30 días. Límite 30/10 min por IP. |
| `POST /eliminar {credential}` | Credencial de Google emitida hace **menos de 5 minutos**, de un solo uso y con el **mismo `sub`** del perfil; 401/403 si no. 5 intentos / 10 min. |
| `GET /yo` | Siempre 200. Una cookie de sesión de una cuenta ANTIGUA responde `{autenticado:false, motivo:"cuenta-anterior"}` (ya no identifica a nadie). `cuentaAnterior:true` solo llega a quien Google acaba de verificarle ese correo. |
| `GET /config` | Client ID de Google (público), `modo:"google"`, `direccionOficial` y `soporte` (opcionales y saneados: solo `https` sin credenciales / correo válido), `vinculoAnterior` si está habilitado. **Nada de Maps/Places**: son otras claves (`GOOGLE_MAPS_*`). |
| `POST /salir`, `GET /datos`, `POST /datos/{clave}` | Sin cambios. CSRF: se rechaza `Sec-Fetch-Site: cross-site` y un `Origin` distinto del sitio. |
| `POST /vinculo-anterior` | Vínculo explícito de una cuenta antigua (apagado por defecto: **410**). Ver §4. |

Nunca se registran tokens, credenciales ni correos en mensajes de error (los mensajes son fijos y las pruebas lo comprueban).

## Inventario de cuentas (consultas agregadas, sin datos personales)

Antes de habilitar cualquier cosa sobre datos reales, en la base de producción (solo lectura, resultados agregados):

```sql
-- vinculadas a Google / solo con contraseña / vinculadas que aún conservan un hash antiguo
SELECT count(*) FILTER (WHERE google_sub IS NOT NULL)                       AS con_google,
       count(*) FILTER (WHERE google_sub IS NULL AND clave_hash IS NOT NULL) AS solo_contrasena,
       count(*) FILTER (WHERE google_sub IS NOT NULL AND clave_hash IS NOT NULL) AS vinculadas_con_hash_viejo,
       count(*) FILTER (WHERE google_sub IS NULL AND clave_hash IS NOT NULL AND EXISTS (SELECT 1 FROM usuario_datos d WHERE d.usuario_id = usuarios.id)) AS solo_contrasena_con_datos
FROM usuarios;
-- sesiones vigentes de cuentas antiguas (las que dejarán de valer)
SELECT count(*) FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id WHERE s.expira_en > NOW() AND u.google_sub IS NULL;
```

## Transición de cuentas antiguas (decisiones)

1. **Ya vinculada a Google** (`google_sub` no nulo, con o sin hash antiguo): entra con su `sub` y vuelve a **su mismo perfil, favoritos, lugares, historial y permisos**. El hash antiguo se ignora (no se usa para nada y el borrado no lo pide).
2. **Primera entrada con un `sub` nuevo**: se crea su perfil, de forma **idempotente** (índice único; varias solicitudes simultáneas dan el mismo perfil). **Nunca hereda nada por tener el mismo correo** de otra fila (cuenta antigua o de otro `sub`).
3. **Cuenta antigua solo con contraseña**: **se conserva intacta** (datos, contraseña, nombre). **Se eliminó** la rama que, al entrar con Google con ese correo, reemplazaba nombre y datos y borraba sesiones (era un «pre-secuestro» a la inversa: perdía datos reales). Hoy:
   * Sus **sesiones vigentes dejan de valer** (`usuarioDeSesion` exige `google_sub`); no se renuevan ni se invalidan en la base (los datos quedan). El navegador **no borra** los datos locales de ese dispositivo (pueden ser lo único a la mano): al entrar con Google se **unen al perfil nuevo** como cualquier dato del dispositivo.
   * Se avisa a quien Google acaba de verificar ese correo: «Tenías una cuenta anterior con contraseña. Sus datos siguen guardados, pero por seguridad no se unen solos a tu cuenta de Google. Para recuperarlos, escribe a …» (`SOPORTE_CORREO`; sin él, «pide la recuperación al equipo de SEVB»).
4. **Vínculo explícito** (`POST /vinculo-anterior`, `CUENTA_VINCULO_ANTERIOR=true`; **apagado por defecto**, sin pantalla pública, sujeto a la estrategia de transición que decida el proyecto): comprueba **las dos cosas**: acceso a la cuenta anterior (correo + contraseña, con tiempo uniforme y límites 10/IP, 5/perfil y 5/correo cada 10 min, mismo mensaje en cualquier fallo) y acceso a Google (credencial reciente del mismo `sub` de la sesión). Si todo cuadra, en una transacción: **la cuenta anterior conserva su id** y toma el `sub`; el perfil nuevo de Google cede los datos que la anterior no tenga (**si la clave está en las dos, manda la anterior**) y desaparece; se **anula la contraseña** y se **cierran todas las sesiones** de la cuenta anterior; se abre una sesión nueva. Si algo no se prueba: **no cambia nada** (registro intacto) y se muestra cómo pedir la recuperación.
   * Colisiones: un `sub` ya vinculado a otro perfil no se reasigna (índice único); una credencial de otro `sub` que el de la sesión → 403; una cuenta que ya tiene Google no es «anterior».
5. **No se migran datos reales en esta fase.** V14 solo cambia un índice y agrega `vinculado_en`; no toca filas. Hacerla efectiva en producción es un despliegue aparte (con las consultas del inventario antes y después).

## Seguridad (qué se conserva)

* Sesión: token de 256 bits en cookie HttpOnly; en la base solo su hash SHA-256; máx. 10 por persona; cerrar sesión borra también los enlaces de «Compartir mi viaje» de esa persona.
* Los datos subidos se validan y limpian en el servidor (campos esperados, rangos, largos, tope por tipo) y se muestran siempre con `textContent`.
* Administración (`/api/editor/**`): `X-Editor-Token` o sesión de administrador (correo verificado por Google); sin cambios.
* Residuales: la credencial de Google viaja una vez por HTTPS; el un-solo-uso vive en memoria del proceso (con varias réplicas, cada una recuerda lo suyo); sin `nonce` de Google (el origen se verifica con `Sec-Fetch-Site`/`Origin`).

## Qué NO hay (a propósito)
Recuperar contraseña por correo, verificar correos o cualquier otro proveedor: sin contraseñas no hacen falta. La recuperación de una cuenta antigua es manual (soporte) o por el vínculo explícito cuando el proyecto lo habilite.

## Privacidad
El historial guarda dónde sales y a dónde vas. Cada persona solo ve lo suyo, puede borrarlo y eliminar la cuenta lo borra del servidor en cascada (perfil, datos, sesiones y enlaces compartidos).

## Pruebas
* `CuentaControllerTest`: 410 de las vías locales, cookie HttpOnly, credencial inválida / audiencia distinta / vencida / sin verificar / repetida, otro sitio, configuración saneada, borrado con credencial antigua o de otro `sub`, vínculo apagado/habilitado y límites.
* `GoogleTokenVerifierTest`: firma, `alg:none`, emisor, audiencia/`azp`, vigencia, `nbf`, correo, un solo uso, reautenticación reciente, mensajes sin datos.
* `CuentaIdentidadPostgresTest` (**PostgreSQL real**; Testcontainers o `SEVB_TEST_PG_URL` a una base `*_test`): `sub` nuevo idempotente (8 hilos), mismo correo sin herencia, otro `sub` con el mismo correo, cuenta vinculada con hash viejo, vínculo explícito (id conservado, datos, sesiones, contraseña), vínculo fallido sin cambios, eliminación en cascada, administrador, V14 idempotente.
* `e2e/cuenta_google_e2e.py` (navegador; Google **simulado**): una sola vía, 410, entrada, rechazo con Reintentar/Seguir, no configurado/bloqueado/sin conexión/sin servidor/dirección temporal, apertura y cierre repetidos con foco, Escape, teclado y 320 px, callbacks tardíos, respuestas que llegan tarde, cambio de usuario, cuenta anterior, `requiere` y borrado.
* Lo que NO se probó: el botón oficial de Google, su ventana emergente, los Orígenes autorizados y las claves reales de Google (ver `docs/GOOGLE.md` §6).
