package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.CuentaService.Usuario;
import co.edu.usta.spevb.service.GoogleTokenVerifier;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

/**
 * Contrato HTTP de la cuenta en el modo público «solo Google» (Fase B): las vías locales están retiradas (410), la sesión solo nace de una credencial de Google verificada de verdad
 * (firma, audiencia, vigencia, un solo uso), el borrado exige una reautenticación reciente del MISMO «sub» y el vínculo de cuentas anteriores está apagado por defecto.
 * Los tokens se firman aquí con una clave propia (Google simulado): lo único que no cubre es el botón oficial de Google ni sus claves reales.
 */
class CuentaControllerTest {
    private static final String CLIENT = "123-abc.apps.googleusercontent.com";
    private static final ObjectMapper M = new ObjectMapper();
    private static KeyPair par, otro;
    private final CuentaService cuentas = mock(CuentaService.class);
    private final GoogleTokenVerifier google = new GoogleTokenVerifier(M, CLIENT, kid -> "k1".equals(kid) ? par.getPublic() : null);
    private static final String SESION = "S".repeat(43);
    private static final Usuario ANA = new Usuario(7, "Ana", "ana@gmail.com", false, true, false);

    @BeforeAll
    static void claves() throws Exception {
        var g = KeyPairGenerator.getInstance("RSA");
        g.initialize(2048);
        par = g.generateKeyPair();
        otro = g.generateKeyPair();
    }

    private static String b64(byte[] b) { return Base64.getUrlEncoder().withoutPadding().encodeToString(b); }

    /** Credencial de Google firmada con la clave indicada; {@code extra} pisa cualquier campo (valor null = quitarlo). */
    private static String token(KeyPair k, Map<String, Object> extra) {
        try { return firmar(k, extra); } catch (Exception e) { throw new IllegalStateException(e); }
    }

    private static String firmar(KeyPair k, Map<String, Object> extra) throws Exception {
        long ahora = System.currentTimeMillis() / 1000;
        var c = new LinkedHashMap<String, Object>(Map.of("iss", "https://accounts.google.com", "aud", CLIENT, "sub", "1098765", "email", "ana@gmail.com",
                "email_verified", true, "name", "Ana Pérez", "iat", ahora - 5, "exp", ahora + 3000));
        c.putAll(extra);
        c.values().removeIf(v -> v == null);
        String cuerpo = b64(M.writeValueAsBytes(Map.of("alg", "RS256", "kid", "k1"))) + "." + b64(M.writeValueAsBytes(c));
        Signature s = Signature.getInstance("SHA256withRSA");
        s.initSign(k.getPrivate());
        s.update(cuerpo.getBytes(StandardCharsets.US_ASCII));
        return cuerpo + "." + b64(s.sign());
    }

    private CuentaController controlador(boolean vinculo) {
        return new CuentaController(cuentas, new LimitadorSolicitudes(), google, "https://sevb.example.com", "ayuda@sevb.example.com", vinculo);
    }

    private static MockHttpServletRequest req() { var r = new MockHttpServletRequest(); r.setRemoteAddr("10.0.0.1"); return r; }
    private static MockHttpServletRequest conSesion() { var r = req(); r.setCookies(new Cookie(CuentaController.COOKIE, SESION)); return r; }
    private static int estado(Runnable accion) { return assertThrows(ResponseStatusException.class, accion::run).getStatusCode().value(); }

    private void sesionIniciada() {
        when(cuentas.usuarioDeSesion(SESION)).thenReturn(Optional.of(ANA));
        when(cuentas.googleSubDe(7)).thenReturn(Optional.of("1098765"));
    }

    // ------------------------------------------------------------------ vías locales retiradas
    @Test
    void registroEntradaYCambioDeClaveEstanRetiradosYNoEmitenSesionesNiTocanElServicio() {
        var c = controlador(false);
        for (Runnable via : new Runnable[]{c::registro, c::entrar, c::clave}) {
            var e = assertThrows(ResponseStatusException.class, via::run);
            assertEquals(410, e.getStatusCode().value());
            assertTrue(e.getReason().contains("Continuar con Google"), e.getReason());
        }
        verifyNoInteractions(cuentas);
    }

    // ------------------------------------------------------------------ acceso con Google
    @Test
    void unaCredencialValidaAbreUnaSesionConCookieHttpOnlyYSoloSirveUnaVez() throws Exception {
        when(cuentas.entrarConGoogle(any())).thenReturn(ANA);
        when(cuentas.abrirSesion(eq(7L), any())).thenReturn(SESION);
        var c = controlador(false);
        String t = token(par, Map.of());
        var resp = new MockHttpServletResponse();
        var cuerpo = c.conGoogle(new CuentaController.GoogleRequest(t), req(), resp);
        String cookie = resp.getHeader("Set-Cookie");
        assertTrue(cookie.contains("spevb_sesion=" + SESION) && cookie.contains("HttpOnly") && cookie.contains("SameSite=Lax") && cookie.contains("Max-Age="), cookie);
        assertFalse(cuerpo.toString().contains(SESION), "la sesión viaja solo en la cookie");
        assertEquals(7L, ((Map<?, ?>) cuerpo.get("usuario")).get("id"));
        verify(cuentas).entrarConGoogle(argThat(i -> "1098765".equals(i.sub()) && "ana@gmail.com".equals(i.correo())));
        // la MISMA credencial no abre otra sesión
        assertEquals(401, estado(() -> c.conGoogle(new CuentaController.GoogleRequest(t), req(), new MockHttpServletResponse())));
        verify(cuentas, times(1)).entrarConGoogle(any());
    }

    @Test
    void unaCredencialInvalidaNuncaAbreSesion() throws Exception {
        var c = controlador(false);
        long ahora = System.currentTimeMillis() / 1000;
        String[] malas = {
                token(otro, Map.of()),                                                         // firma de otra clave
                token(par, Map.of("aud", "otra-app.apps.googleusercontent.com")),               // audiencia distinta
                token(par, Map.of("iss", "https://evil.example")),                              // emisor falso
                token(par, Map.of("exp", ahora - 3600)),                                        // vencida
                token(par, Map.of("email_verified", false)),                                    // correo sin verificar
                token(par, Map.of("sub", "")),                                                  // sin sub
                "no-es-un-token", ""};
        for (String t : malas) {
            var e = assertThrows(ResponseStatusException.class, () -> c.conGoogle(new CuentaController.GoogleRequest(t), req(), new MockHttpServletResponse()), t);
            assertEquals(401, e.getStatusCode().value());
            assertFalse(String.valueOf(e.getReason()).contains("ana@gmail.com"), "el mensaje no repite el correo");
        }
        assertEquals(401, estado(() -> c.conGoogle(new CuentaController.GoogleRequest(null), req(), new MockHttpServletResponse())));
        verify(cuentas, never()).entrarConGoogle(any());
        verify(cuentas, never()).abrirSesion(anyLong(), any());
    }

    @Test
    void unaSolicitudDeOtroSitioNoAbreSesion() throws Exception {
        var c = controlador(false);
        var r = req(); r.addHeader("Sec-Fetch-Site", "cross-site");
        assertEquals(403, estado(() -> c.conGoogle(new CuentaController.GoogleRequest(token(par, Map.of())), r, new MockHttpServletResponse())));
        var o = req(); o.addHeader("Origin", "https://evil.example"); o.addHeader("Host", "sevb.example.com");
        assertEquals(403, estado(() -> c.conGoogle(new CuentaController.GoogleRequest(token(par, Map.of("iat", 1))), o, new MockHttpServletResponse())));
        verifyNoInteractions(cuentas);
    }

    @Test
    void elAvisoDeCuentaAnteriorSoloLlegaAQuienGoogleVerifico() throws Exception {
        when(cuentas.entrarConGoogle(any())).thenReturn(ANA);
        when(cuentas.abrirSesion(eq(7L), any())).thenReturn(SESION);
        when(cuentas.hayCuentaAnterior("ana@gmail.com")).thenReturn(true);
        var cuerpo = controlador(false).conGoogle(new CuentaController.GoogleRequest(token(par, Map.of())), req(), new MockHttpServletResponse());
        assertEquals(Boolean.TRUE, cuerpo.get("cuentaAnterior"));
        assertFalse(cuerpo.toString().contains("clave") || cuerpo.toString().contains("hash"));
    }

    // ------------------------------------------------------------------ configuración pública
    @Test
    void laConfiguracionPublicaNoTraeSecretosYSaneaLasDireccionesOpcionales() {
        when(cuentas.adminConfigurado()).thenReturn(true);
        var m = controlador(false).config();
        assertEquals(CLIENT, m.get("google"));
        assertEquals("google", m.get("modo"));
        assertEquals("https://sevb.example.com", m.get("direccionOficial"));
        assertEquals("ayuda@sevb.example.com", m.get("soporte"));
        assertFalse(m.containsKey("vinculoAnterior"));
        assertEquals(Boolean.TRUE, controlador(true).config().get("vinculoAnterior"));
        // direcciones peligrosas o mal formadas se ignoran: nunca se enlaza algo que no sea una página https
        for (String mala : new String[]{"http://sevb.example.com", "javascript:alert(1)", "https://user:pw@sevb.example.com", "https://sevb.example.com/#x", "https://sevb.example.com/?a=1", "no es url", ""}) {
            var c = new CuentaController(cuentas, new LimitadorSolicitudes(), google, mala, "mal correo <x>", false);
            assertFalse(c.config().containsKey("direccionOficial"), mala);
            assertFalse(c.config().containsKey("soporte"));
        }
        var sin = new CuentaController(cuentas, new LimitadorSolicitudes(), new GoogleTokenVerifier(M, "", kid -> null), "", "", false);
        assertFalse(sin.config().containsKey("google"), "sin Client ID no se anuncia Google");
    }

    // ------------------------------------------------------------------ quién soy
    @Test
    void unaSesionNacidaDeUnaContrasenaAntiguaYaNoIdentificaANadieYSeDiceSinBorrarNada() {
        when(cuentas.usuarioDeSesion(SESION)).thenReturn(Optional.empty());
        when(cuentas.sesionDeCuentaAnterior(SESION)).thenReturn(true);
        var m = controlador(false).yo(conSesion());
        assertEquals(false, m.get("autenticado"));
        assertEquals("cuenta-anterior", m.get("motivo"));
        var nadie = controlador(false).yo(req());
        assertEquals(false, nadie.get("autenticado"));
        assertFalse(nadie.containsKey("motivo"));
    }

    // ------------------------------------------------------------------ eliminar
    @Test
    void eliminarExigeUnaReautenticacionRecienteDeGoogleDelMismoSub() throws Exception {
        var c0 = controlador(false);
        sesionIniciada();
        long ahora = System.currentTimeMillis() / 1000;
        // sin sesión
        assertEquals(401, estado(() -> c0.eliminar(new CuentaController.EliminarRequest(null), req(), new MockHttpServletResponse())));
        // sin credencial, con basura, con la clave de una contraseña vieja (ya no existe el campo)
        assertEquals(401, estado(() -> c0.eliminar(new CuentaController.EliminarRequest(null), conSesion(), new MockHttpServletResponse())));
        assertEquals(401, estado(() -> c0.eliminar(new CuentaController.EliminarRequest("mi-clave-vieja"), conSesion(), new MockHttpServletResponse())));
        // credencial antigua (más de 5 minutos): la sesión no basta
        assertEquals(401, estado(() -> c0.eliminar(new CuentaController.EliminarRequest(token(par, Map.of("iat", ahora - 900))), conSesion(), new MockHttpServletResponse())));
        // credencial reciente pero de OTRA cuenta de Google
        assertEquals(403, estado(() -> c0.eliminar(new CuentaController.EliminarRequest(token(par, Map.of("sub", "999", "iat", ahora - 2))), conSesion(), new MockHttpServletResponse())));
        verify(cuentas, never()).eliminar(anyLong());
        // la correcta: borra y limpia la cookie (otro controlador: el límite de intentos del anterior ya se gastó con los rechazos)
        var c = controlador(false);
        String buena = token(par, Map.of("iat", ahora - 3));
        var resp = new MockHttpServletResponse();
        assertEquals(Boolean.TRUE, c.eliminar(new CuentaController.EliminarRequest(buena), conSesion(), resp).get("ok"));
        verify(cuentas).eliminar(7L);
        assertTrue(resp.getHeader("Set-Cookie").contains("Max-Age=0"), resp.getHeader("Set-Cookie"));
        // la misma credencial no sirve para borrar otra vez
        assertEquals(401, estado(() -> c.eliminar(new CuentaController.EliminarRequest(buena), conSesion(), new MockHttpServletResponse())));
        verify(cuentas, times(1)).eliminar(anyLong());
    }

    @Test
    void sinGoogleConfiguradoNoSePuedeConfirmarUnBorradoYNoSeBorraNada() {
        var sin = new CuentaController(cuentas, new LimitadorSolicitudes(), new GoogleTokenVerifier(M, "", kid -> null), "", "", false);
        sesionIniciada();
        assertEquals(503, estado(() -> sin.eliminar(new CuentaController.EliminarRequest("x"), conSesion(), new MockHttpServletResponse())));
        verify(cuentas, never()).eliminar(anyLong());
    }

    // ------------------------------------------------------------------ vínculo explícito de una cuenta anterior
    @Test
    void elVinculoDeCuentasAnterioresEstaApagadoPorDefecto() {
        sesionIniciada();
        var e = assertThrows(ResponseStatusException.class, () -> controlador(false).vincularAnterior(new CuentaController.VincularRequest("x", "a@b.co", "clave"), conSesion(), new MockHttpServletResponse()));
        assertEquals(410, e.getStatusCode().value());
        verify(cuentas, never()).vincularCuentaAnterior(anyLong(), any(), any(), any());
    }

    @Test
    void elVinculoPideLasDosPruebasConservaElIdYAbreUnaSesionNueva() throws Exception {
        sesionIniciada();
        var c = controlador(true);
        long ahora = System.currentTimeMillis() / 1000;
        var vinculada = new Usuario(3, "Beto antiguo", "ana@gmail.com", false, true, false);
        when(cuentas.vincularCuentaAnterior(eq(7L), any(), eq("beto@correo.co"), eq("clave-vieja-1"))).thenReturn(vinculada);
        when(cuentas.abrirSesion(eq(3L), any())).thenReturn("N".repeat(43));
        // sin sesión o sin credencial reciente de Google: nada
        assertEquals(401, estado(() -> c.vincularAnterior(new CuentaController.VincularRequest("x", "beto@correo.co", "clave-vieja-1"), req(), new MockHttpServletResponse())));
        assertEquals(401, estado(() -> c.vincularAnterior(new CuentaController.VincularRequest("basura", "beto@correo.co", "clave-vieja-1"), conSesion(), new MockHttpServletResponse())));
        verify(cuentas, never()).vincularCuentaAnterior(anyLong(), any(), any(), any());
        var resp = new MockHttpServletResponse();
        var m = c.vincularAnterior(new CuentaController.VincularRequest(token(par, Map.of("iat", ahora - 2)), " Beto@Correo.co ", "clave-vieja-1"), conSesion(), resp);
        assertEquals(Boolean.TRUE, m.get("vinculada"));
        assertEquals(3L, ((Map<?, ?>) m.get("usuario")).get("id"), "conserva el id interno de la cuenta anterior");
        assertTrue(resp.getHeader("Set-Cookie").contains("N".repeat(43)) && resp.getHeader("Set-Cookie").contains("HttpOnly"));
    }

    @Test
    void elVinculoLimitaLosIntentosPorCorreoParaNoAdivinarContrasenas() throws Exception {
        sesionIniciada();
        var c = controlador(true);
        when(cuentas.vincularCuentaAnterior(anyLong(), any(), any(), any())).thenThrow(new IllegalArgumentException(CuentaService.MSG_ANTERIOR_NO_COMPROBADA));
        long ahora = System.currentTimeMillis() / 1000;
        int rechazos = 0, limitados = 0;
        for (int i = 0; i < 8; i++) {
            try {
                c.vincularAnterior(new CuentaController.VincularRequest(token(par, Map.of("iat", ahora - i - 1)), "beto@correo.co", "intento" + i), conSesion(), new MockHttpServletResponse());
            } catch (IllegalArgumentException e) { rechazos++; }
            catch (ResponseStatusException e) { if (e.getStatusCode().value() == 429) limitados++; }
        }
        assertEquals(5, rechazos, "cinco intentos por correo y por perfil");
        assertEquals(3, limitados);
    }
}
