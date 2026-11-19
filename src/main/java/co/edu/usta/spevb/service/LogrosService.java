package co.edu.usta.spevb.service;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.sql.Date;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Logros, medallas y racha de viajes por CUENTA (Fase D). El estado se DERIVA de los viajes registrados (idempotentes por cuenta + id lógico del viaje): nunca se suman contadores
 * enteros de un dispositivo, así dos teléfonos con la misma cuenta no duplican nada. Solo se guarda lo mínimo (sin coordenadas ni direcciones). Confianza: recreativa.
 */
@Service
public class LogrosService {
    public static final Pattern ID_VIAJE = Pattern.compile("^[A-Za-z0-9_-]{6,40}$");
    static final long ADELANTO_MAX_MS = 5 * 60_000L, ANTIGUEDAD_MAX_MS = 30L * 86_400_000L;
    static final int DIAS_VISTA = 120, VIAJES_MAX = 5000, VIAJES_POR_DIA_MAX = 60, BUSES_MAX = 6;

    /** Logros del catálogo; cada uno tiene su recompensa visual (la insignia equipable se llama igual que el logro). */
    public static final List<String> CATALOGO = List.of("primero", "cinco", "veinte", "transbordo", "racha3", "racha7", "madrugador", "noche", "practica", "llano");

    public record Metricas(int viajes, int transbordos, int rachaActual, int mejorRacha, int mejorEstricta, boolean madrugador, boolean nocturno, boolean practica) {}

    public record Estado(Metricas m, List<String> logros, String insignia, LocalDate hoy, LocalDate ultimoDia, List<LocalDate> dias) {
        public Map<String, Object> aJson() {
            var j = new LinkedHashMap<String, Object>();
            j.put("viajes", m.viajes());
            j.put("transbordos", m.transbordos());
            j.put("rachaActual", m.rachaActual());
            j.put("mejorRacha", m.mejorRacha());
            j.put("mejorEstricta", m.mejorEstricta());
            j.put("madrugador", m.madrugador());
            j.put("nocturno", m.nocturno());
            j.put("practica", m.practica());
            j.put("logros", logros);
            j.put("insignia", insignia);
            j.put("hoy", hoy.toString());
            j.put("ultimoDia", ultimoDia == null ? null : ultimoDia.toString());
            // Los últimos días con viaje (solo fechas): el dispositivo recalcula la racha al abrir el menú o al cruzar la medianoche sin preguntar al servidor.
            j.put("dias", dias.stream().map(LocalDate::toString).toList());
            return j;
        }
    }

    /** Reglas del catálogo (espejo exacto en js/logros.js). «racha3»/«racha7» conservan su significado antiguo: días CONSECUTIVOS, sin hueco. */
    public static List<String> desbloqueados(Metricas m) {
        var r = new ArrayList<String>();
        if (m.viajes() >= 1) r.add("primero");
        if (m.viajes() >= 5) r.add("cinco");
        if (m.viajes() >= 20) r.add("veinte");
        if (m.transbordos() >= 1) r.add("transbordo");
        if (m.mejorEstricta() >= 3) r.add("racha3");
        if (m.mejorEstricta() >= 7) r.add("racha7");
        if (m.madrugador()) r.add("madrugador");
        if (m.nocturno()) r.add("noche");
        if (m.practica()) r.add("practica");
        if (m.viajes() >= 30 && m.mejorRacha() >= 7) r.add("llano");
        return r;
    }

    public record Registro(boolean nuevo, Estado estado, List<String> nuevos) {}

    private final JdbcTemplate jdbc;

    public LogrosService(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public Estado estado(long uid, long ahoraMs) {
        LocalDate hoy = Racha.diaDe(ahoraMs);
        List<LocalDate> dias = jdbc.query("SELECT DISTINCT dia FROM logros_viaje WHERE usuario_id = ?", (rs, i) -> rs.getDate(1).toLocalDate(), uid);
        Map<String, Object> a = jdbc.queryForMap("""
                SELECT COUNT(*) AS viajes, COUNT(*) FILTER (WHERE buses >= 2) AS transbordos,
                       COALESCE(BOOL_OR(hora < 7), FALSE) AS madrugador, COALESCE(BOOL_OR(hora >= 19), FALSE) AS nocturno
                FROM logros_viaje WHERE usuario_id = ?""", uid);
        List<Map<String, Object>> p = jdbc.queryForList("SELECT practica, insignia FROM logros_perfil WHERE usuario_id = ?", uid);
        boolean practica = !p.isEmpty() && Boolean.TRUE.equals(p.get(0).get("practica"));
        String insignia = p.isEmpty() ? null : (String) p.get(0).get("insignia");
        Racha.Resultado r = Racha.calcular(dias, hoy);
        Metricas m = new Metricas(((Number) a.get("viajes")).intValue(), ((Number) a.get("transbordos")).intValue(), r.actual(), r.mejor(), r.mejorEstricta(),
                Boolean.TRUE.equals(a.get("madrugador")), Boolean.TRUE.equals(a.get("nocturno")), practica);
        List<String> logros = desbloqueados(m);
        if (insignia != null && !logros.contains(insignia)) insignia = null;
        return new Estado(m, logros, insignia, hoy, r.ultimoDia(), dias.stream().sorted().skip(Math.max(0, dias.size() - DIAS_VISTA)).toList());
    }

    /**
     * Modo demostración (LOGROS_CUENTAS_DEMO): el mismo estado de la cuenta pero con TODO el catálogo desbloqueado, para enseñar cómo se ven y que se pueden cumplir.
     * No se escribe ningún viaje: los reales siguen intactos y, al quitar la cuenta de la variable, vuelve a verse su progreso verdadero. Las métricas que se muestran
     * (30 viajes, 1 transbordo, 7 días seguidos que terminan hoy, madrugador, nocturno y práctica) cumplen de verdad las reglas de {@link #desbloqueados}.
     */
    static Estado demo(Estado real, String insigniaGuardada) {
        LocalDate hoy = real.hoy();
        var m = new Metricas(Math.max(30, real.m().viajes()), Math.max(1, real.m().transbordos()), Math.max(7, real.m().rachaActual()),
                Math.max(7, real.m().mejorRacha()), Math.max(7, real.m().mejorEstricta()), true, true, true);
        var dias = new ArrayList<LocalDate>();
        for (int i = 6; i >= 0; i--) dias.add(hoy.minusDays(i));
        String insignia = insigniaGuardada != null && CATALOGO.contains(insigniaGuardada) ? insigniaGuardada : null;
        return new Estado(m, desbloqueados(m), insignia, hoy, hoy, dias);
    }

    /** Estado de una cuenta de demostración (todos los logros desbloqueados). */
    public Estado estadoDemo(long uid, long ahoraMs) {
        List<String> p = jdbc.queryForList("SELECT insignia FROM logros_perfil WHERE usuario_id = ? AND insignia IS NOT NULL", String.class, uid);
        return demo(estado(uid, ahoraMs), p.isEmpty() ? null : p.get(0));
    }

    private static List<String> diferencia(Estado antes, Estado despues) {
        var nuevos = new ArrayList<>(despues.logros());
        nuevos.removeAll(antes.logros());
        return nuevos;
    }

    /** Registra una llegada. Idempotente: el mismo (cuenta, viaje) nunca cuenta dos veces; devuelve los logros que ESTE registro desbloqueó. */
    public Registro registrar(long uid, String viajeId, long llegadaMs, int buses, long ahoraMs) {
        if (viajeId == null || !ID_VIAJE.matcher(viajeId).matches()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Identificador de viaje no válido.");
        if (buses < 1 || buses > BUSES_MAX) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Un viaje cuenta solo con al menos una subida a un bus confirmada.");
        if (llegadaMs > ahoraMs + ADELANTO_MAX_MS || llegadaMs < ahoraMs - ANTIGUEDAD_MAX_MS) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "La hora de llegada no es válida.");
        Estado antes = estado(uid, ahoraMs);
        Integer existe = jdbc.queryForObject("SELECT COUNT(*) FROM logros_viaje WHERE usuario_id = ? AND viaje_id = ?", Integer.class, uid, viajeId);
        if (existe != null && existe > 0) return new Registro(false, antes, List.of());      // reintento: ya contaba
        if (antes.m().viajes() >= VIAJES_MAX) throw new ResponseStatusException(HttpStatus.CONFLICT, "Llegaste al máximo de viajes que se pueden registrar.");
        LocalDate dia = Racha.diaDe(llegadaMs);
        Integer delDia = jdbc.queryForObject("SELECT COUNT(*) FROM logros_viaje WHERE usuario_id = ? AND dia = ?", Integer.class, uid, Date.valueOf(dia));
        if (delDia != null && delDia >= VIAJES_POR_DIA_MAX) throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Demasiados viajes registrados ese día.");
        int n = jdbc.update("INSERT INTO logros_viaje (usuario_id, viaje_id, llegada_ms, dia, buses, hora) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (usuario_id, viaje_id) DO NOTHING",
                uid, viajeId, llegadaMs, Date.valueOf(dia), (short) buses, (short) Racha.horaDe(llegadaMs));
        Estado despues = estado(uid, ahoraMs);
        return new Registro(n > 0, despues, n > 0 ? diferencia(antes, despues) : List.of());
    }

    /** La práctica guiada terminó: da «Aprendiz» una sola vez y NO suma viajes ni racha. */
    public Registro practica(long uid, long ahoraMs) {
        Estado antes = estado(uid, ahoraMs);
        jdbc.update("INSERT INTO logros_perfil (usuario_id, practica) VALUES (?, TRUE) ON CONFLICT (usuario_id) DO UPDATE SET practica = TRUE, actualizado_en = NOW()", uid);
        Estado despues = estado(uid, ahoraMs);
        var nuevos = diferencia(antes, despues);
        return new Registro(!nuevos.isEmpty(), despues, nuevos);
    }

    /** Destaca (o quita con null/vacío) una insignia. Solo se acepta una que la cuenta ya desbloqueó. */
    public Estado equipar(long uid, String id, long ahoraMs) { return equipar(uid, id, ahoraMs, false); }

    /** {@code demostracion}: la cuenta ve todo el catálogo desbloqueado, así que puede destacar cualquier insignia que exista. */
    public Estado equipar(long uid, String id, long ahoraMs, boolean demostracion) {
        String nuevo = id == null || id.isEmpty() ? null : id;
        if (nuevo != null) {
            if (!CATALOGO.contains(nuevo)) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Esa insignia no existe.");
            if (!demostracion && !estado(uid, ahoraMs).logros().contains(nuevo)) throw new ResponseStatusException(HttpStatus.CONFLICT, "Todavía no has ganado esa insignia.");
        }
        jdbc.update("INSERT INTO logros_perfil (usuario_id, insignia) VALUES (?, ?) ON CONFLICT (usuario_id) DO UPDATE SET insignia = EXCLUDED.insignia, actualizado_en = NOW()", uid, nuevo);
        return demostracion ? estadoDemo(uid, ahoraMs) : estado(uid, ahoraMs);
    }
}
