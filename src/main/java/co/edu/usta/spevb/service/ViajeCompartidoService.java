package co.edu.usta.spevb.service;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * «Compartir mi viaje»: capacidad temporal y revocable (ver docs/COMPARTIR-VIAJE.md).
 * <ul>
 *   <li>Dos tokens de 256 bits (SecureRandom): uno de LECTURA (va en el enlace) y uno de ESCRITURA (se queda en el teléfono que viaja). Solo se guarda su SHA-256.</li>
 *   <li>Una fila por viaje con la ÚLTIMA posición (sin historial), la fase y el progreso. La ruta se valida y se redondea; no se guardan direcciones ni nombres de lugares.</li>
 *   <li>Vida máxima de 3 horas; al llegar deja de aceptar coordenadas, las borra y el estado final vive 10 minutos; revocar borra la fila.</li>
 * </ul>
 * Nunca se registran tokens ni coordenadas.
 */
@Service
public class ViajeCompartidoService {
    public static final Duration VIDA_MAXIMA = Duration.ofHours(3);
    public static final Duration GRACIA_LLEGADA = Duration.ofMinutes(10);
    static final int MAX_PUNTOS = 4000, MAX_TRAMOS = 2, MAX_ETIQUETA = 40;
    static final Set<String> FASES = Set.of("iniciando", "caminar", "esperando", "en_bus", "caminar_final", "llegaste");
    private static final Pattern FORMATO_TOKEN = Pattern.compile("^[A-Za-z0-9_-]{43}$");

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final SecureRandom azar = new SecureRandom();

    public ViajeCompartidoService(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    public record Creado(String lectura, String escritura, long expiraEpoch) {}
    public record Actualizacion(String fase, int leg, double progreso, Double lat, Double lng, Double precision, Integer etaMin) {}
    public record Vista(String estado, String fase, int leg, double progreso, Double lat, Double lng, Integer etaMin, int version, long actualizadoEpoch, long expiraEpoch, JsonNode ruta) {}

    // ------------------------------------------------------------------ tokens
    String nuevoToken() {
        byte[] b = new byte[32];
        azar.nextBytes(b);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(b);
    }

    public static boolean formatoValido(String token) { return token != null && FORMATO_TOKEN.matcher(token).matches(); }

    public static String hash(String token) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    // ------------------------------------------------------------------ validación
    private static boolean coordenada(double lat, double lng) {
        return Double.isFinite(lat) && Double.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
    }

    /** Devuelve la ruta limpia {tramos:[[[lng,lat],…]], etiquetas:[…]} como JSON, o lanza IllegalArgumentException. Sin ruta válida no hay viaje que compartir. */
    String limpiarRuta(JsonNode ruta) {
        if (ruta == null || !ruta.isObject() || !ruta.path("tramos").isArray()) throw new IllegalArgumentException("Para compartir hace falta un viaje en curso.");
        var tramos = ruta.path("tramos");
        if (tramos.size() < 1 || tramos.size() > MAX_TRAMOS) throw new IllegalArgumentException("El recorrido no es válido.");
        var salida = mapper.createObjectNode();
        var arr = salida.putArray("tramos");
        int total = 0;
        for (JsonNode t : tramos) {
            if (!t.isArray() || t.size() < 2) throw new IllegalArgumentException("El recorrido no es válido.");
            var linea = arr.addArray();
            for (JsonNode p : t) {
                if (!p.isArray() || p.size() < 2 || !p.get(0).isNumber() || !p.get(1).isNumber()) throw new IllegalArgumentException("El recorrido no es válido.");
                double lng = p.get(0).asDouble(), lat = p.get(1).asDouble();
                if (!coordenada(lat, lng)) throw new IllegalArgumentException("El recorrido no es válido.");
                if (++total > MAX_PUNTOS) throw new IllegalArgumentException("El recorrido es demasiado largo para compartirlo.");
                linea.addArray().add(Math.round(lng * 1e5) / 1e5).add(Math.round(lat * 1e5) / 1e5);
            }
        }
        var et = salida.putArray("etiquetas");
        for (JsonNode e : ruta.path("etiquetas")) {
            if (et.size() >= MAX_TRAMOS) break;
            String s = e.asString("").replaceAll("[\\p{Cntrl}<>]", " ").strip();
            et.add(s.length() > MAX_ETIQUETA ? s.substring(0, MAX_ETIQUETA) : s);
        }
        return salida.toString();
    }

    static void validar(Actualizacion a) {
        if (a == null || a.fase() == null || !FASES.contains(a.fase())) throw new IllegalArgumentException("Estado del viaje no válido.");
        if (a.leg() < 0 || a.leg() > 1) throw new IllegalArgumentException("Estado del viaje no válido.");
        if (!(a.progreso() >= 0 && a.progreso() <= 1)) throw new IllegalArgumentException("Progreso no válido.");
        if ((a.lat() == null) != (a.lng() == null)) throw new IllegalArgumentException("Posición no válida.");
        if (a.lat() != null && !coordenada(a.lat(), a.lng())) throw new IllegalArgumentException("Posición no válida.");
        if (a.precision() != null && !(a.precision() >= 0 && a.precision() <= 10_000)) throw new IllegalArgumentException("Posición no válida.");
        if (a.etaMin() != null && (a.etaMin() < 0 || a.etaMin() > 24 * 60)) throw new IllegalArgumentException("Hora de llegada no válida.");
    }

    // ------------------------------------------------------------------ operaciones
    /** Crea el enlace. {@code usuarioId} es opcional (null si la persona no entró). Limpia de paso lo que ya venció. */
    public Creado crear(Long usuarioId, JsonNode ruta) {
        String json = limpiarRuta(ruta);
        limpiar();
        String lectura = nuevoToken(), escritura = nuevoToken();
        long expira = jdbc.queryForObject("""
                INSERT INTO viajes_compartidos (lectura_hash, escritura_hash, usuario_id, ruta, fase, expira_en)
                VALUES (?, ?, ?, ?, 'iniciando', NOW() + make_interval(secs => ?))
                RETURNING EXTRACT(EPOCH FROM expira_en)::bigint""", Long.class, hash(lectura), hash(escritura), usuarioId, json, (double) VIDA_MAXIMA.toSeconds());
        return new Creado(lectura, escritura, expira);
    }

    /** @return false si el token no corresponde a un viaje compartido vigente (inválido, vencido o revocado: sin detalles). */
    public boolean actualizar(String escritura, Actualizacion a) {
        if (!formatoValido(escritura)) return false;
        validar(a);
        if ("llegaste".equals(a.fase())) {
            // Llegó: deja de aceptar coordenadas, se borran y queda un estado final corto.
            return jdbc.update("""
                    UPDATE viajes_compartidos SET estado = 'llego', fase = 'llegaste', progreso = 1, lat = NULL, lng = NULL, precision_m = NULL, eta_min = 0,
                           version = version + 1, actualizado_en = NOW(), final_en = NOW(), expira_en = LEAST(expira_en, NOW() + make_interval(secs => ?))
                    WHERE escritura_hash = ? AND estado = 'activo' AND expira_en > NOW()""", (double) GRACIA_LLEGADA.toSeconds(), hash(escritura)) > 0;
        }
        return jdbc.update("""
                UPDATE viajes_compartidos SET fase = ?, leg = ?, progreso = ?, lat = ?, lng = ?, precision_m = ?, eta_min = ?, version = version + 1, actualizado_en = NOW()
                WHERE escritura_hash = ? AND estado = 'activo' AND expira_en > NOW()""",
                a.fase(), a.leg(), a.progreso(), a.lat(), a.lng(), a.precision(), a.etaMin(), hash(escritura)) > 0;
    }

    /** «Dejar de compartir»: borra la fila al instante (el enlace deja de existir). */
    public boolean revocar(String escritura) {
        return formatoValido(escritura) && jdbc.update("DELETE FROM viajes_compartidos WHERE escritura_hash = ?", hash(escritura)) > 0;
    }

    /** Al cerrar sesión (o eliminar la cuenta) no queda ningún enlace huérfano de esa persona. */
    public int revocarDeUsuario(long usuarioId) { return jdbc.update("DELETE FROM viajes_compartidos WHERE usuario_id = ?", usuarioId); }

    public Optional<Vista> consultar(String lectura) {
        if (!formatoValido(lectura)) return Optional.empty();
        List<Map<String, Object>> f = jdbc.queryForList("""
                SELECT estado, fase, leg, progreso, lat, lng, eta_min, version, ruta, EXTRACT(EPOCH FROM actualizado_en)::bigint AS act, EXTRACT(EPOCH FROM expira_en)::bigint AS exp
                FROM viajes_compartidos WHERE lectura_hash = ? AND expira_en > NOW()""", hash(lectura));
        if (f.isEmpty()) return Optional.empty();
        var r = f.get(0);
        boolean llego = "llego".equals(r.get("estado"));
        JsonNode ruta = null;
        try { if (r.get("ruta") != null) ruta = mapper.readTree((String) r.get("ruta")); } catch (Exception e) { /* sin ruta */ }
        return Optional.of(new Vista((String) r.get("estado"), (String) r.get("fase"), ((Number) r.get("leg")).intValue(), ((Number) r.get("progreso")).doubleValue(),
                llego ? null : (Double) r.get("lat"), llego ? null : (Double) r.get("lng"), r.get("eta_min") == null ? null : ((Number) r.get("eta_min")).intValue(),
                ((Number) r.get("version")).intValue(), ((Number) r.get("act")).longValue(), ((Number) r.get("exp")).longValue(), ruta));
    }

    /** Borra lo vencido. Se llama al crear (no hay tareas programadas en el proyecto). */
    public int limpiar() { return jdbc.update("DELETE FROM viajes_compartidos WHERE expira_en < NOW()"); }
}
