package co.edu.usta.spevb.service;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.util.Base64;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class GoogleTokenVerifierTest {
    private static final String CLIENT = "123-abc.apps.googleusercontent.com";
    private static final long AHORA = 1_800_000_000L;
    private static final ObjectMapper M = new ObjectMapper();
    private static KeyPair par, otro;

    @BeforeAll
    static void claves() throws Exception {
        var g = KeyPairGenerator.getInstance("RSA");
        g.initialize(2048);
        par = g.generateKeyPair();
        otro = g.generateKeyPair();
    }

    private static String b64(byte[] b) { return Base64.getUrlEncoder().withoutPadding().encodeToString(b); }

    private static String token(KeyPair k, Map<String, Object> extra) throws Exception {
        var c = new java.util.LinkedHashMap<String, Object>(Map.of("iss", "https://accounts.google.com", "aud", CLIENT, "sub", "1098765",
                "email", "Ana@Gmail.com", "email_verified", true, "name", "Ana Pérez", "iat", AHORA - 10, "exp", AHORA + 3000));
        c.putAll(extra);
        c.values().removeIf(v -> v == null);
        String cuerpo = b64(M.writeValueAsBytes(Map.of("alg", "RS256", "kid", "k1"))) + "." + b64(M.writeValueAsBytes(c));
        Signature s = Signature.getInstance("SHA256withRSA");
        s.initSign(k.getPrivate());
        s.update(cuerpo.getBytes(StandardCharsets.US_ASCII));
        return cuerpo + "." + b64(s.sign());
    }

    private GoogleTokenVerifier verificador() {
        return new GoogleTokenVerifier(M, CLIENT, kid -> "k1".equals(kid) ? par.getPublic() : null);
    }

    private void rechaza(String token, String contiene) {
        var e = assertThrows(GoogleTokenVerifier.TokenInvalido.class, () -> verificador().verificar(token, AHORA));
        assertTrue(e.getMessage().toLowerCase().contains(contiene.toLowerCase()), e.getMessage());
    }

    @Test
    void aceptaUnTokenValido() throws Exception {
        var id = verificador().verificar(token(par, Map.of()), AHORA);
        assertEquals("1098765", id.sub());
        assertEquals("ana@gmail.com", id.correo());
        assertEquals("Ana Pérez", id.nombre());
    }

    @Test
    void rechazaFirmaAjenaAlteradaYAlgoritmoNone() throws Exception {
        rechaza(token(otro, Map.of()), "firma");
        String t = token(par, Map.of());
        String[] p = t.split("\\.");
        String alterado = p[0] + "." + b64(M.writeValueAsBytes(Map.of("iss", "https://accounts.google.com", "aud", CLIENT, "sub", "999", "email", "otro@x.com",
                "email_verified", true, "iat", AHORA, "exp", AHORA + 3000))) + "." + p[2];
        rechaza(alterado, "firma");
        String none = b64(M.writeValueAsBytes(Map.of("alg", "none"))) + "." + p[1] + ".";
        rechaza(none, "no válida");
        rechaza("basura", "no válida");
        rechaza(null, "no válida");
    }

    @Test
    void rechazaEmisorAudienciaVencidoYCorreoSinVerificar() throws Exception {
        rechaza(token(par, Map.of("iss", "https://evil.com")), "Google");
        rechaza(token(par, Map.of("aud", "otra-app.apps.googleusercontent.com")), "esta aplicación");
        rechaza(token(par, Map.of("exp", AHORA - 3600)), "venció");
        rechaza(token(par, Map.of("email_verified", false)), "verificado");
        rechaza(token(par, Map.of("sub", "")), "incompleta");
    }

    @Test
    void aceptaAudienciaEnListaYNombreVacioUsaElCorreo() throws Exception {
        var id = verificador().verificar(token(par, Map.of("aud", java.util.List.of("x", CLIENT), "name", "")), AHORA);
        assertEquals("ana", id.nombre());
    }

    @Test
    void laFotoDeGoogleSoloSeAceptaSiEsHttpsDeUnHostDeImagenesDeGoogle() throws Exception {
        String buena = "https://lh3.googleusercontent.com/a/ACg8ocK=s96-c";
        assertEquals(buena, verificador().verificar(token(par, Map.of("picture", buena)), AHORA).foto());
        assertNull(verificador().verificar(token(par, Map.of()), AHORA).foto(), "sin picture: sin foto (avatar local)");
        for (String mala : new String[] {
                "http://lh3.googleusercontent.com/a/x", "https://evil.com/foto.png", "https://googleusercontent.com.evil.com/a",
                "https://evil.com/.googleusercontent.com", "https://user:pw@lh3.googleusercontent.com/a", "https://lh3.googleusercontent.com:8443/a",
                "javascript:alert(1)", "data:image/png;base64,AAAA", "//lh3.googleusercontent.com/a", "https://lh3.googleusercontent.com/" + "a".repeat(600), "no es una url" }) {
            var id = verificador().verificar(token(par, Map.of("picture", mala)), AHORA);
            assertNull(id.foto(), "debe ignorarse: " + mala);
            assertEquals("ana@gmail.com", id.correo(), "una foto inválida nunca impide entrar");
        }
    }

    @Test
    void sinClientIdConfiguradoNadaEntra() throws Exception {
        var v = new GoogleTokenVerifier(M, "", kid -> par.getPublic());
        assertFalse(v.activo());
        assertThrows(GoogleTokenVerifier.TokenInvalido.class, () -> v.verificar(token(par, Map.of()), AHORA));
    }

    // ------------------------------------------------------------------ Fase B: controles adicionales
    @Test
    void rechazaDestinatarioAutorizadoAjenoCorreoDemasiadoLargoYTokenAunNoValido() throws Exception {
        rechaza(token(par, Map.of("azp", "otra-app.apps.googleusercontent.com")), "esta aplicación");
        rechaza(token(par, Map.of("aud", java.util.List.of(CLIENT, "otra"), "azp", "otra")), "esta aplicación");
        assertEquals("1098765", verificador().verificar(token(par, Map.of("aud", java.util.List.of(CLIENT, "otra"), "azp", CLIENT)), AHORA).sub());
        rechaza(token(par, Map.of("email", "a".repeat(115) + "@x.com")), "incompleta");
        rechaza(token(par, Map.of("email", "sin-arroba")), "incompleta");
        rechaza(token(par, Map.of("nbf", AHORA + 3600)), "no válida");
        rechaza(token(par, Map.of("iat", AHORA + 3600)), "no válida");
    }

    @Test
    void unaCredencialDeGoogleSoloSirveUnaVez() throws Exception {
        var v = verificador();
        String t = token(par, Map.of());
        var id = v.verificar(t, AHORA);
        assertNotNull(id.huella());
        assertFalse(id.huella().contains("."), "la huella es un hash, no el token");
        assertDoesNotThrow(() -> v.consumir(id, AHORA));
        var e = assertThrows(GoogleTokenVerifier.TokenInvalido.class, () -> v.consumir(v.verificar(t, AHORA), AHORA));
        assertTrue(e.getMessage().contains("ya se usó"), e.getMessage());
        // otra credencial (otro iat) sí sirve
        assertDoesNotThrow(() -> v.consumir(v.verificar(token(par, Map.of("iat", AHORA - 5)), AHORA), AHORA));
    }

    @Test
    void laReautenticacionRecienteExigeUnaCredencialDeHaceMenosDeCincoMinutos() throws Exception {
        var v = verificador();
        assertEquals("1098765", v.verificarReciente(token(par, Map.of("iat", AHORA - 120)), 300, AHORA).sub());
        var e = assertThrows(GoogleTokenVerifier.TokenInvalido.class, () -> v.verificarReciente(token(par, Map.of("iat", AHORA - 900)), 300, AHORA));
        assertTrue(e.getMessage().contains("vuelve a continuar con Google"), e.getMessage());
        assertThrows(GoogleTokenVerifier.TokenInvalido.class, () -> v.verificarReciente(token(par, Map.of("iat", 0)), 300, AHORA), "sin iat no hay forma de saber si es reciente");
    }

    @Test
    void ningunMensajeDeErrorRepiteElTokenNiElCorreo() throws Exception {
        String t = token(otro, Map.of());
        var e = assertThrows(GoogleTokenVerifier.TokenInvalido.class, () -> verificador().verificar(t, AHORA));
        assertFalse(e.getMessage().contains(t.substring(0, 20)) || e.getMessage().toLowerCase().contains("ana@gmail.com"));
    }
}
