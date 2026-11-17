package co.edu.usta.spevb.service;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Pattern;

/** Cuentas de usuario, sesiones y datos sincronizados (lugares, rutas favoritas, viajes guardados, historial). */
@Service
public class CuentaService {
    public static final int DIAS_SESION = 30;
    private static final int MAX_SESIONES = 10;
    private static final Pattern CORREO = Pattern.compile("^[^\\s@]{1,64}@[^\\s@]+\\.[^\\s@]{2,}$");
    /** Clave de relleno para igualar el tiempo de respuesta cuando el correo no existe (no revela qué correos hay registrados). */
    private static final String HASH_RELLENO = ClaveHash.hacer("relleno-sin-uso");
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final DatosUsuario datos;
    private final SecureRandom azar = new SecureRandom();
    private final java.util.Set<String> admins;

    public CuentaService(JdbcTemplate jdbc, ObjectMapper mapper,
                         @org.springframework.beans.factory.annotation.Value("${spevb.admin.correos:}") String adminCorreos) {
        this.admins = java.util.Arrays.stream(adminCorreos.split("[,;\\s]+")).map(String::toLowerCase).filter(c -> !c.isBlank()).collect(java.util.stream.Collectors.toUnmodifiableSet());
        this.jdbc = jdbc;
        this.mapper = mapper;
        this.datos = new DatosUsuario(mapper);
    }

    /** Solo es administrador quien tiene su correo en ADMIN_CORREOS Y lo verificó con Google (nadie puede «adelantarse» registrando ese correo). */
    public boolean esAdmin(String correo, boolean verificado) { return verificado && correo != null && admins.contains(correo.toLowerCase()); }
    public boolean adminConfigurado() { return !admins.isEmpty(); }

    /** {@code foto}: URL de la foto de Google (solo cuentas con Google, ya validada) o null. */
    public record Usuario(long id, String nombre, String correo, boolean tieneClave, boolean conGoogle, boolean admin, String foto) {
        public Usuario(long id, String nombre, String correo, boolean tieneClave, boolean conGoogle, boolean admin) { this(id, nombre, correo, tieneClave, conGoogle, admin, null); }
    }

    // ------------------------------------------------------------------ validaciones
    public static String normalizarCorreo(String correo) {
        String c = correo == null ? "" : correo.strip().toLowerCase();
        if (c.length() > 120 || !CORREO.matcher(c).matches()) throw new IllegalArgumentException("Escribe un correo válido.");
        return c;
    }

    /** Mensaje único (no revela si el correo existe, si la contraseña falló o si la cuenta ya estaba vinculada). */
    public static final String MSG_ANTERIOR_NO_COMPROBADA = "No pudimos comprobar esa cuenta anterior. Revisa el correo y la contraseña, o pide la recuperación al equipo de SEVB.";

    // ------------------------------------------------------------------ cuentas (Fase B: la identidad pública es SOLO el «sub» de Google)
    // Ya no existe registro, entrada ni cambio de contraseña: el controlador los retira (HTTP 410) y aquí se eliminaron los métodos. La contraseña antigua de una cuenta heredada solo se lee,
    // para comprobar el acceso a esa cuenta en el vínculo explícito (vincularCuentaAnterior), y se anula al vincular.

    /**
     * Entra (o crea el perfil) con una identidad ya verificada por Google. La identidad es el «sub»; el correo NO demuestra propiedad de ninguna cuenta.
     * · «sub» conocido: es ese perfil (mismo id, datos, favoritos, lugares, historial y permisos). Se renuevan la foto y el correo verificado por Google (el permiso de administrador se evalúa con él).
     * · «sub» nuevo: se crea su perfil, de forma idempotente (índice único; dos solicitudes simultáneas dan el mismo perfil). NUNCA hereda datos de otra fila por tener el mismo correo,
     *   aunque exista una cuenta antigua con contraseña o con otro «sub»: esas filas quedan intactas (ver V14 y docs/CUENTAS.md).
     */
    public Usuario entrarConGoogle(GoogleTokenVerifier.Identidad g) { return entrarConGoogle(g, true); }

    private Usuario entrarConGoogle(GoogleTokenVerifier.Identidad g, boolean reintentar) {
        List<Map<String, Object>> porSub = jdbc.queryForList("SELECT id, nombre FROM usuarios WHERE google_sub = ?", g.sub());
        if (!porSub.isEmpty()) {
            var f = porSub.get(0);
            long id = ((Number) f.get("id")).longValue();
            jdbc.update("UPDATE usuarios SET ultimo_acceso = NOW(), foto_url = ?, correo = ?, correo_verificado = TRUE WHERE id = ?", g.foto(), g.correo(), id);
            return new Usuario(id, (String) f.get("nombre"), g.correo(), false, true, esAdmin(g.correo(), true), g.foto());
        }
        try {
            Long id = jdbc.queryForObject("INSERT INTO usuarios (correo, nombre, clave_hash, google_sub, correo_verificado, foto_url, ultimo_acceso) VALUES (?, ?, NULL, ?, TRUE, ?, NOW()) RETURNING id",
                    Long.class, g.correo(), g.nombre(), g.sub(), g.foto());
            return new Usuario(id, g.nombre(), g.correo(), false, true, esAdmin(g.correo(), true), g.foto());
        } catch (org.springframework.dao.DuplicateKeyException e) {
            if (reintentar) return entrarConGoogle(g, false);       // otra solicitud lo creó justo antes: es el mismo perfil
            throw e;
        }
    }

    /** ¿Hay una cuenta ANTIGUA con contraseña (sin Google) con este correo? Solo se pregunta con un correo que Google acaba de verificar a quien consulta. */
    public boolean hayCuentaAnterior(String correo) {
        if (correo == null || correo.isBlank() || correo.length() > 120) return false;
        Long n = jdbc.queryForObject("SELECT COUNT(*) FROM usuarios WHERE LOWER(correo) = ? AND google_sub IS NULL AND clave_hash IS NOT NULL", Long.class, correo.strip().toLowerCase());
        return n != null && n > 0;
    }

    /** El «sub» de Google de este perfil (para comprobar que una reautenticación es de la misma persona), o vacío. */
    public Optional<String> googleSubDe(long id) {
        return jdbc.queryForList("SELECT google_sub FROM usuarios WHERE id = ? AND google_sub IS NOT NULL", String.class, id).stream().findFirst();
    }

    /**
     * VÍNCULO EXPLÍCITO de una cuenta anterior (con contraseña) a Google. Proceso aparte del inicio público (el controlador lo apaga por configuración): comprueba el acceso a la cuenta anterior
     * (correo + contraseña, con límite de intentos y tiempo uniforme) Y el acceso a Google (el perfil con sesión es el del «sub» de la credencial reciente que acompaña la solicitud).
     * El vínculo CONSERVA el id interno de la cuenta anterior: ella toma el «sub»; el perfil nuevo de Google cede sus datos que la anterior no tenga (la anterior manda) y se elimina; se anula la
     * contraseña y se cierran TODAS las sesiones de la cuenta anterior (nacieron de esa contraseña). Sin pruebas de las dos cosas, no cambia nada.
     */
    @Transactional
    public Usuario vincularCuentaAnterior(long perfilId, GoogleTokenVerifier.Identidad g, String correoAnterior, String clave) {
        String c = correoAnterior == null ? "" : correoAnterior.strip().toLowerCase();
        List<Map<String, Object>> perfil = jdbc.queryForList("SELECT id, google_sub FROM usuarios WHERE id = ? FOR UPDATE", perfilId);
        if (perfil.isEmpty() || !g.sub().equals(perfil.get(0).get("google_sub")))
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "La confirmación de Google no corresponde a tu sesión.");
        List<Map<String, Object>> filas = c.isEmpty() || c.length() > 120 ? List.of()
                : jdbc.queryForList("SELECT id, nombre, clave_hash FROM usuarios WHERE LOWER(correo) = ? AND google_sub IS NULL FOR UPDATE", c);
        boolean hay = !filas.isEmpty() && filas.get(0).get("clave_hash") != null;
        boolean ok = clave != null && clave.length() <= 128 && ClaveHash.verificar(clave, hay ? (String) filas.get(0).get("clave_hash") : HASH_RELLENO);       // siempre tarda lo mismo
        if (!ok || !hay) throw new IllegalArgumentException(MSG_ANTERIOR_NO_COMPROBADA);
        long anterior = ((Number) filas.get(0).get("id")).longValue();
        // Los datos del perfil nuevo que la cuenta anterior no tenga pasan a ella; si la clave existe en las dos, manda la anterior (lo que se quiere conservar).
        jdbc.update("""
                INSERT INTO usuario_datos (usuario_id, clave, valor, actualizado_en)
                SELECT ?, clave, valor, actualizado_en FROM usuario_datos WHERE usuario_id = ?
                ON CONFLICT (usuario_id, clave) DO NOTHING""", anterior, perfilId);
        jdbc.update("DELETE FROM usuarios WHERE id = ?", perfilId);       // libera el «sub» y arrastra (ON DELETE CASCADE) sus sesiones, datos y enlaces compartidos
        jdbc.update("UPDATE usuarios SET google_sub = ?, correo = ?, correo_verificado = TRUE, clave_hash = NULL, foto_url = ?, vinculado_en = NOW(), ultimo_acceso = NOW() WHERE id = ?",
                g.sub(), g.correo(), g.foto(), anterior);
        cerrarTodas(anterior);
        return new Usuario(anterior, (String) filas.get(0).get("nombre"), g.correo(), false, true, esAdmin(g.correo(), true), g.foto());
    }

    /**
     * Borra la cuenta y todo lo suyo. El controlador ya comprobó una reautenticación RECIENTE con Google del mismo «sub» (ya no depende de ninguna contraseña, tenga o no un hash antiguo).
     * Devuelve false si el perfil ya no existía.
     */
    public boolean eliminar(long id) {
        return jdbc.update("DELETE FROM usuarios WHERE id = ?", id) > 0;
    }

    // ------------------------------------------------------------------ sesiones
    private static String hashToken(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }

    public String abrirSesion(long usuarioId, String agente) {
        byte[] b = new byte[32];
        azar.nextBytes(b);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(b);
        jdbc.update("DELETE FROM sesiones WHERE expira_en < NOW()");
        jdbc.update("""
                DELETE FROM sesiones WHERE usuario_id = ? AND id NOT IN (
                    SELECT id FROM sesiones WHERE usuario_id = ? ORDER BY vista_en DESC LIMIT ?)""", usuarioId, usuarioId, MAX_SESIONES - 1);
        jdbc.update("INSERT INTO sesiones (usuario_id, token_hash, agente, expira_en) VALUES (?, ?, ?, NOW() + make_interval(days => ?))",
                usuarioId, hashToken(token), agente == null ? null : (agente.length() > 160 ? agente.substring(0, 160) : agente), DIAS_SESION);
        return token;
    }

    public Optional<Usuario> usuarioDeSesion(String token) {
        if (token == null || token.length() < 20 || token.length() > 100) return Optional.empty();
        List<Map<String, Object>> filas = jdbc.queryForList("""
                SELECT u.id, u.nombre, u.correo, (u.clave_hash IS NOT NULL) AS tiene_clave, (u.google_sub IS NOT NULL) AS con_google, u.correo_verificado, u.foto_url, s.vista_en < NOW() - INTERVAL '1 day' AS renovar
                FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id
                WHERE s.token_hash = ? AND s.expira_en > NOW() AND u.google_sub IS NOT NULL""", hashToken(token));      // una sesión nacida de una contraseña antigua ya no identifica a nadie (los datos quedan intactos)
        if (filas.isEmpty()) return Optional.empty();
        var f = filas.get(0);
        if (Boolean.TRUE.equals(f.get("renovar")))
            jdbc.update("UPDATE sesiones SET vista_en = NOW(), expira_en = NOW() + make_interval(days => ?) WHERE token_hash = ?", DIAS_SESION, hashToken(token));
        return Optional.of(new Usuario(((Number) f.get("id")).longValue(), (String) f.get("nombre"), (String) f.get("correo"),
                Boolean.TRUE.equals(f.get("tiene_clave")), Boolean.TRUE.equals(f.get("con_google")),
                esAdmin((String) f.get("correo"), Boolean.TRUE.equals(f.get("correo_verificado"))),
                Boolean.TRUE.equals(f.get("con_google")) ? (String) f.get("foto_url") : null));
    }

    /** ¿El token es una sesión vigente de una cuenta ANTIGUA (sin Google)? Ya no vale como sesión, pero la interfaz lo sabe para no borrar los datos de este dispositivo y explicar la recuperación. */
    public boolean sesionDeCuentaAnterior(String token) {
        if (token == null || token.length() < 20 || token.length() > 100) return false;
        Long n = jdbc.queryForObject("SELECT COUNT(*) FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id WHERE s.token_hash = ? AND s.expira_en > NOW() AND u.google_sub IS NULL", Long.class, hashToken(token));
        return n != null && n > 0;
    }

    public void cerrarSesion(String token) {
        if (token != null) {
            // Cerrar sesión no deja un enlace de «Compartir mi viaje» huérfano: los de esa persona se borran antes de borrar la sesión.
            jdbc.update("DELETE FROM viajes_compartidos WHERE usuario_id = (SELECT usuario_id FROM sesiones WHERE token_hash = ?)", hashToken(token));
            jdbc.update("DELETE FROM sesiones WHERE token_hash = ?", hashToken(token));
        }
    }

    public void cerrarTodas(long usuarioId) {
        jdbc.update("DELETE FROM viajes_compartidos WHERE usuario_id = ?", usuarioId);
        jdbc.update("DELETE FROM sesiones WHERE usuario_id = ?", usuarioId);
    }

    // ------------------------------------------------------------------ datos sincronizados
    public Map<String, Object> leerDatos(long usuarioId) {
        Map<String, Object> salida = new LinkedHashMap<>();
        for (Map<String, Object> f : jdbc.queryForList("SELECT clave, valor::text AS valor, (EXTRACT(EPOCH FROM actualizado_en) * 1000)::bigint AS t FROM usuario_datos WHERE usuario_id = ?", usuarioId)) {
            salida.put((String) f.get("clave"), Map.of("valor", mapper.readTree((String) f.get("valor")), "actualizadoEn", f.get("t")));
        }
        return salida;
    }

    /** Guarda sin condición (compatibilidad). */
    public void guardarDatos(long usuarioId, String clave, JsonNode valor) { guardarDatos(usuarioId, clave, valor, null); }

    /**
     * Guarda un documento. Con {@code base} (el «actualizadoEn» que el dispositivo leyó) la escritura es CONDICIONAL y atómica: si otro dispositivo cambió el documento desde entonces
     * responde 409 y no pisa nada. Devuelve el nuevo «actualizadoEn» (ms), que el dispositivo usa como base de su próxima escritura.
     */
    public long guardarDatos(long usuarioId, String clave, JsonNode valor, Long base) {
        var limpio = datos.limpiar(clave, valor);
        long ahora = System.currentTimeMillis();
        String json = mapper.writeValueAsString(limpio);
        var ts = new java.sql.Timestamp(ahora);
        if (base == null) {
            jdbc.update("""
                    INSERT INTO usuario_datos (usuario_id, clave, valor, actualizado_en) VALUES (?, ?, ?::jsonb, ?)
                    ON CONFLICT (usuario_id, clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = EXCLUDED.actualizado_en""", usuarioId, clave, json, ts);
            return ahora;
        }
        int n = jdbc.update("""
                INSERT INTO usuario_datos (usuario_id, clave, valor, actualizado_en) VALUES (?, ?, ?::jsonb, ?)
                ON CONFLICT (usuario_id, clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = EXCLUDED.actualizado_en
                WHERE (EXTRACT(EPOCH FROM usuario_datos.actualizado_en) * 1000)::bigint = ?""", usuarioId, clave, json, ts, base);
        if (n == 0) throw new ResponseStatusException(HttpStatus.CONFLICT, "Tus datos cambiaron en otro dispositivo. Se actualizaron; vuelve a intentarlo.");
        return ahora;
    }
}
