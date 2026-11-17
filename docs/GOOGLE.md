# Inicio de sesión con Google (única vía pública de acceso)

Desde la Fase B, **«Continuar con Google» es la ÚNICA forma pública de entrar a una cuenta de SEVB** (no hay registro, correo ni contraseña). La planeación de rutas y el modo viaje siguen disponibles para invitados, sin cuenta. Sin `GOOGLE_CLIENT_ID` nadie puede abrir sesión (el diálogo dice que Google todavía no está configurado y deja «Reintentar» y «Seguir sin cuenta»). **No hace falta ningún secreto de Google**: solo el *Client ID*, que es público. Modelo de cuentas, transición de cuentas antiguas y seguridad: `docs/CUENTAS.md`.

> Separación de credenciales: esto es la **identidad** (`GOOGLE_CLIENT_ID`). La configuración de Google **Maps/Places** (`GOOGLE_MAPS_API_KEY`, `GOOGLE_MAPS_BROWSER_API_KEY`, `MAP_ID`) es otra cosa, con otras claves y otras restricciones (`docs/GOOGLE-MAPS.md`). Nunca uses una en lugar de la otra.

## 1. Obtener el Client ID (5–10 minutos, gratis)
> Los nombres de los menús de Google Cloud cambian de vez en cuando; si algo no coincide, busca «OAuth» en el buscador de la consola.

1. Entra a <https://console.cloud.google.com> con tu cuenta de Google y **crea un proyecto** (p. ej. «SPEVB»).
2. Menú **APIs y servicios → Pantalla de consentimiento de OAuth** (o «Google Auth Platform»):
   - Tipo de usuario: **Externo**.
   - Nombre de la app: *SPEVB Villavicencio*; correo de asistencia y de contacto: el tuyo.
   - Alcances: deja solo los básicos (`email`, `profile`, `openid`). No pidas nada más.
   - Estado de publicación: pásala a **«En producción»**. Mientras esté en «Pruebas» solo pueden entrar los correos que añadas como *usuarios de prueba* (máx. 100).
3. **Credenciales → Crear credenciales → ID de cliente de OAuth → Tipo: Aplicación web**.
   - **Orígenes de JavaScript autorizados** (uno por línea, sin `/` al final): `http://localhost:8080`, `http://localhost`, tu dominio real (`https://rutas.midominio.com`) y cada dirección de túnel con nombre fijo que uses para probar.
   - **URI de redireccionamiento: déjalo vacío** (se usa el modo emergente con token).
4. Copia el **ID de cliente** (`123456789-abcdef….apps.googleusercontent.com`).

## 2. Ponerlo en el sistema (`.env`)
```
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
# Opcionales (Fase B)
DIRECCION_OFICIAL=https://rutas.midominio.com     # https; se muestra si alguien intenta entrar desde una dirección temporal de túnel
SOPORTE_CORREO=ayuda@midominio.com                # a quién pedir la recuperación de una cuenta anterior con contraseña
ADMIN_CORREOS=tucorreo@gmail.com                  # administradores (correo verificado por Google)
# CUENTA_VINCULO_ANTERIOR=false                   # vínculo explícito de cuentas antiguas: apagado salvo decisión del proyecto (docs/CUENTAS.md §4)
```
Reinicia la aplicación (`.\start.ps1 -NoDatabase`, o `docker compose -f compose.prod.yml up -d`). Abre el menú → **Continuar con Google**: debe verse el botón de Google.

## 3. Qué ve la persona y qué pasa si algo falla
El diálogo carga Google **solo cuando se toca «Continuar con Google»** (nada se inicia solo) y siempre dice qué pasa, con una salida:

| Estado | Mensaje | Salida |
|---|---|---|
| cargando | «Preparando el acceso con Google…» | — |
| listo | «Toca el botón de Google para continuar.» + el botón oficial | «Seguir sin cuenta» |
| entrando | «Entrando con Google…» (no se puede cerrar mientras viaja al servidor) | — |
| no configurado | «El acceso con Google todavía no está configurado en este servidor.» | Reintentar · Seguir sin cuenta |
| sin conexión / sin servidor | «Sin conexión…» / «No pude comunicarme con SEVB…» | Reintentar · Seguir sin cuenta |
| bloqueado | «Google no cargó. Puede que un bloqueador de anuncios o de privacidad, o la red, lo esté impidiendo.» (tope de espera: 10 s) | Reintentar · Seguir sin cuenta |
| dirección temporal | «Entrar con Google no está disponible en esta dirección temporal…» + «Abrir …» si `DIRECCION_OFICIAL` existe | Seguir sin cuenta |
| rechazada | el mensaje del servidor (credencial vencida, ya usada, otra aplicación…) | Reintentar · Seguir sin cuenta |

## 4. Problemas típicos
| Síntoma | Causa |
|---|---|
| «No configurado» | `GOOGLE_CLIENT_ID` vacío o la app no se reinició |
| «Google no cargó» | bloqueador de anuncios/privacidad que bloquea `accounts.google.com`, red corporativa, sin internet |
| «Error 400: origin_mismatch» | La dirección desde la que abres la app no está en *Orígenes de JavaScript autorizados*. Los túneles gratuitos cambian de dirección y Google **no permite registrarlas**: usa un dominio fijo (ngrok con dominio gratuito, o tu dominio) y regístralo |
| «Acceso bloqueado: esta app no ha sido verificada» / solo entran algunos | La pantalla de consentimiento sigue en «Pruebas»: publícala o añade usuarios de prueba |
| Falla dentro de Instagram/Facebook/WhatsApp | Esos navegadores integrados bloquean a Google: abrir el enlace en Chrome o Safari |
| «La credencial no es para esta aplicación» | El `GOOGLE_CLIENT_ID` del servidor no es el del proyecto/botón |
| «Esa credencial de Google ya se usó» | Cada credencial sirve una sola vez; basta con volver a tocar el botón |

## 5. Qué comprueba el servidor (seguridad)
1. El botón oficial de Google (script `accounts.google.com/gsi/client`) devuelve un **ID token** firmado por Google.
2. El servidor lo verifica **él mismo** (no se lo envía a nadie): firma RS256 con las claves públicas de Google (JWKS en caché), emisor `accounts.google.com`, destinatario = tu Client ID (y `azp` si viene), vigencia (`exp`, `iat`, `nbf`), **correo verificado**, `sub` y correo con tamaño razonable y **un solo uso** por credencial.
3. La identidad es el **`sub`**; el correo no demuestra propiedad de ninguna cuenta antigua (`docs/CUENTAS.md`).
4. Se abre una sesión propia (cookie HttpOnly). Eliminar la cuenta pide una credencial **de menos de 5 minutos del mismo `sub`**.
5. La política de seguridad de contenido (CSP) solo permite `accounts.google.com/gsi/*` para el botón.
6. Nunca se registran tokens ni correos en mensajes de diagnóstico.

## 6. Pruebas y qué se validó (y qué no)
* **Con Google simulado** (sin cuenta ni red de Google): `GoogleTokenVerifierTest` y `CuentaControllerTest` firman sus propios tokens con una clave propia; `CuentaIdentidadPostgresTest` prueba la identidad en PostgreSQL real; `e2e/cuenta_google_e2e.py` usa un `window.google.accounts.id` de mentira y el stub del servidor (`e2e/stub_server.py`, que acepta credenciales `fake.<json en base64url>` con las mismas reglas: audiencia, vigencia, un solo uso, borrado reciente del mismo `sub`).
* **Con Google real: nada.** No se probó el botón oficial, su ventana emergente, los *Orígenes autorizados*, la pantalla de consentimiento ni las claves reales. Hazlo tú una vez con tu Client ID: entrar, cerrar sesión, volver a entrar (mismo perfil), eliminar la cuenta de prueba y abrir desde una dirección temporal (debe mostrar el aviso, no el error 400 de Google).
* Los scripts antiguos `docs/pruebas/cuentas_e2e.py` y `docs/pruebas/google_e2e.py` probaban contraseñas y el vínculo por correo: están **obsoletos** y salen con un aviso.

## 7. Administradores
Si pones `ADMIN_CORREOS=tucorreo@gmail.com` en el `.env`, quien entre con Google con ese correo (verificado por Google) es administrador: ve el editor, los pasos, los lugares y los reportes sin escribir la clave. Una cuenta antigua con contraseña y ese correo **no** lo es. Ver `docs/ADMIN-Y-PARADEROS.md`.
