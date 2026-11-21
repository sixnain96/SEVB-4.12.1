package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Reportes de personas (ruta mal trazada, dirección equivocada, sugerencias). Público para enviar; la lista es del editor. */
@RestController
@RequestMapping("/api")
public class ReporteController {
    static final Set<String> CATEGORIAS = Set.of("RUTA", "CAMINATA", "DIRECCION", "APP", "SUGERENCIA", "OTRO");
    static final Set<String> ESTADOS = Set.of("NUEVO", "REVISADO", "RESUELTO", "DESCARTADO");
    private final JdbcTemplate jdbc;
    private final LimitadorSolicitudes limitador;

    public ReporteController(JdbcTemplate jdbc, LimitadorSolicitudes limitador) {
        this.jdbc = jdbc;
        this.limitador = limitador;
    }

    public record ReporteRequest(String categoria, String mensaje, String rutaCodigo,
                                 Double origenLat, Double origenLng, Double destinoLat, Double destinoLng, String contacto, String gravedad) {
        public ReporteRequest(String categoria, String mensaje, String rutaCodigo, Double origenLat, Double origenLng, Double destinoLat, Double destinoLng, String contacto) {
            this(categoria, mensaje, rutaCodigo, origenLat, origenLng, destinoLat, destinoLng, contacto, null);
        }
    }
    static final java.util.Map<String, String> GRAVEDADES = java.util.Map.of("BAJA", "Baja: es una molestia", "MEDIA", "Media: me complica el viaje", "ALTA", "Alta: no puedo viajar");

    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private co.edu.usta.spevb.service.NotificadorReportes notificador;
    public record EstadoRequest(String estado) {}

    private static String limpiar(String s, int max) {
        if (s == null) return null;
        String t = s.replaceAll("[\\p{Cntrl}&&[^\\n]]", " ").strip();
        if (t.isEmpty()) return null;
        return t.length() > max ? t.substring(0, max) : t;
    }

    private static Double coord(Double v, double min, double max) {
        return v != null && v >= min && v <= max ? v : null;
    }

    @PostMapping("/reportes")
    public ResponseEntity<Map<String, Object>> crear(@RequestBody ReporteRequest r, HttpServletRequest http) {
        if (!limitador.permitir("rep:" + http.getRemoteAddr(), 5, Duration.ofMinutes(10)))
            return ResponseEntity.status(429).body(Map.of("ok", false, "message", "Enviaste varios reportes seguidos. Espera unos minutos."));
        String categoria = r.categoria() == null ? "" : r.categoria().strip().toUpperCase();
        if (!CATEGORIAS.contains(categoria)) throw new IllegalArgumentException("Elige el tipo de reporte.");
        String mensaje = limpiar(r.mensaje(), 500);
        if (mensaje == null || mensaje.length() < 5) throw new IllegalArgumentException("Cuéntanos qué pasó (mínimo 5 caracteres).");
        String gravedad = r.gravedad() == null ? null : GRAVEDADES.get(r.gravedad().strip().toUpperCase());
        String textoGuardado = gravedad == null ? mensaje : ('[' + gravedad.substring(0, gravedad.indexOf(':')) + "] " + mensaje);      // la gravedad va al inicio del mensaje (sin columna nueva)
        if (textoGuardado.length() > 500) textoGuardado = textoGuardado.substring(0, 500);
        jdbc.update("""
                INSERT INTO reportes (categoria, mensaje, ruta_codigo, origen_lat, origen_lng, destino_lat, destino_lng, contacto, agente)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                categoria, textoGuardado, limpiar(r.rutaCodigo(), 40),
                coord(r.origenLat(), -90, 90), coord(r.origenLng(), -180, 180), coord(r.destinoLat(), -90, 90), coord(r.destinoLng(), -180, 180),
                limpiar(r.contacto(), 120), limpiar(http.getHeader("User-Agent"), 160));
        if (notificador != null) {
            var aviso = new java.util.LinkedHashMap<String, Object>();
            aviso.put("categoria", categoria); aviso.put("gravedad", gravedad); aviso.put("mensaje", mensaje); aviso.put("rutaCodigo", limpiar(r.rutaCodigo(), 40));
            if (coord(r.origenLat(), -90, 90) != null && coord(r.origenLng(), -180, 180) != null) aviso.put("origen", r.origenLat() + ", " + r.origenLng() + "  https://www.google.com/maps?q=" + r.origenLat() + "," + r.origenLng());
            if (coord(r.destinoLat(), -90, 90) != null && coord(r.destinoLng(), -180, 180) != null) aviso.put("destino", r.destinoLat() + ", " + r.destinoLng() + "  https://www.google.com/maps?q=" + r.destinoLat() + "," + r.destinoLng());
            aviso.put("contacto", limpiar(r.contacto(), 120)); aviso.put("agente", limpiar(http.getHeader("User-Agent"), 160));
            try { notificador.avisar(aviso); } catch (RuntimeException e) { /* el correo nunca impide guardar el reporte */ }
        }
        return ResponseEntity.ok(Map.of("ok", true));
    }

    @GetMapping("/editor/reportes")
    public List<Map<String, Object>> listar(@RequestParam(defaultValue = "NUEVO") String estado, @RequestParam(defaultValue = "100") int limite) {
        String e = estado.strip().toUpperCase();
        int tope = Math.max(1, Math.min(300, limite));
        if ("TODOS".equals(e)) return jdbc.queryForList("SELECT * FROM reportes ORDER BY creado_en DESC LIMIT ?", tope);
        if (!ESTADOS.contains(e)) throw new IllegalArgumentException("Estado no válido.");
        return jdbc.queryForList("SELECT * FROM reportes WHERE estado = ? ORDER BY creado_en DESC LIMIT ?", e, tope);
    }

    @PatchMapping("/editor/reportes/{id}")
    public Map<String, Object> cambiar(@PathVariable long id, @RequestBody EstadoRequest r) {
        String e = r.estado() == null ? "" : r.estado().strip().toUpperCase();
        if (!ESTADOS.contains(e)) throw new IllegalArgumentException("Estado no válido.");
        int n = jdbc.update("UPDATE reportes SET estado = ? WHERE id = ?", e, id);
        if (n == 0) throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.NOT_FOUND, "Reporte no encontrado.");
        return Map.of("ok", true);
    }
}
