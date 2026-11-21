package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.CuentaService.Usuario;
import co.edu.usta.spevb.service.LogrosService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Logros y racha de la CUENTA (Fase D). Todo es de la persona autenticada: sin sesión no hay nada (los invitados guardan su progreso solo en su dispositivo).
 * El cliente envía únicamente {viajeId, llegadaMs, buses}: ni coordenadas, ni direcciones, ni trayectorias.
 */
@RestController
@RequestMapping("/api/cuenta/logros")
public class LogrosController {
    private final CuentaService cuentas;
    private final LogrosService logros;
    private final LimitadorSolicitudes limitador;

    public LogrosController(CuentaService cuentas, LogrosService logros, LimitadorSolicitudes limitador) {
        this.cuentas = cuentas;
        this.logros = logros;
        this.limitador = limitador;
    }

    public record ViajeRequest(String viajeId, Long llegadaMs, Integer buses) {}
    public record InsigniaRequest(String id) {}

    private Usuario exigirUsuario(HttpServletRequest r) {
        return cuentas.usuarioDeSesion(CuentaController.token(r)).orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Inicia sesión para continuar."));
    }

    /** Correos (coma) de las cuentas de demostración: ven todos los logros desbloqueados. Vacío = ninguna (LOGROS_CUENTAS_DEMO, ver docs/LOGROS.md). */
    @Value("${spevb.logros.cuentas-demo:}")
    private String cuentasDemo = "";

    private boolean esDemo(Usuario u) {
        if (u.correo() != null && co.edu.usta.spevb.service.CuentaProyecto.es(u.correo())) return true;      // la cuenta del proyecto siempre es de demostración
        if (u.correo() == null || cuentasDemo == null || cuentasDemo.isBlank()) return false;
        String correo = u.correo().strip().toLowerCase(Locale.ROOT);
        return Arrays.stream(cuentasDemo.split(",")).map(s -> s.strip().toLowerCase(Locale.ROOT)).anyMatch(correo::equals);
    }

    /** Racha ESTÁTICA de las cuentas de demostración (4.17): empieza en {@code rachaDemoBase} el día {@code rachaDemoInicio} y baja un día por cada día que pasa (nunca por debajo de 0). Con {@code rachaDemoInicio} vacío es ESTÁTICA: siempre vale la base (31) y solo baja en el simulador de la presentación. */
    @Value("${spevb.logros.racha-demo-base:31}")
    private int rachaDemoBase = 31;
    @Value("${spevb.logros.racha-demo-inicio:}")
    private String rachaDemoInicio = "";

    /** Racha de la cuenta de demostración a la fecha {@code hoy}: base menos los días transcurridos desde el inicio. */
    int rachaDemo(java.time.LocalDate hoy) {
        java.time.LocalDate inicio;
        try { inicio = java.time.LocalDate.parse(rachaDemoInicio.strip()); } catch (RuntimeException e) { inicio = hoy; }
        long pasados = Math.max(0, java.time.temporal.ChronoUnit.DAYS.between(inicio, hoy));
        return (int) Math.max(0, rachaDemoBase - pasados);
    }

    /** La respuesta de una cuenta de demostración lleva la racha estática (y cómo recalcularla en el dispositivo a medianoche sin preguntar al servidor). */
    private Map<String, Object> demo(LogrosService.Estado e, boolean nuevo, List<String> nuevos) {
        var m = respuesta(e, nuevo, nuevos);
        int racha = rachaDemo(e.hoy());
        m.put("rachaActual", racha);
        m.put("mejorRacha", Math.max(rachaDemoBase, ((Number) m.get("mejorRacha")).intValue()));
        m.put("rachaDemo", Map.of("base", rachaDemoBase, "inicio", rachaDemoInicio.strip()));
        return m;
    }

    private void limite(Usuario u) {
        if (!limitador.permitir("logros:" + u.id(), 120, Duration.ofMinutes(1))) throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, "Demasiadas solicitudes seguidas. Espera unos segundos.");
    }

    private static Map<String, Object> respuesta(LogrosService.Estado e, boolean nuevo, List<String> nuevos) {
        var m = new LinkedHashMap<String, Object>(e.aJson());
        m.put("nuevo", nuevo);
        m.put("nuevos", nuevos);
        return m;
    }

    @GetMapping
    public Map<String, Object> estado(HttpServletRequest r) {
        Usuario u = exigirUsuario(r);
        limite(u);
        long ahora = System.currentTimeMillis();
        if (esDemo(u)) return demo(logros.estadoDemo(u.id(), ahora), false, List.of());
        return respuesta(logros.estado(u.id(), ahora), false, List.of());
    }

    @PostMapping("/viaje")
    public Map<String, Object> viaje(@RequestBody ViajeRequest q, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite(u);
        if (q == null || q.llegadaMs() == null || q.buses() == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Faltan datos del viaje.");
        long ahora = System.currentTimeMillis();
        var reg = logros.registrar(u.id(), q.viajeId(), q.llegadaMs(), q.buses(), ahora);
        if (esDemo(u)) return demo(logros.estadoDemo(u.id(), ahora), reg.nuevo(), List.of());      // el viaje se guarda de verdad; los logros ya estaban todos desbloqueados
        return respuesta(reg.estado(), reg.nuevo(), reg.nuevos());
    }

    @PostMapping("/practica")
    public Map<String, Object> practica(HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite(u);
        long ahora = System.currentTimeMillis();
        var reg = logros.practica(u.id(), ahora);
        if (esDemo(u)) return demo(logros.estadoDemo(u.id(), ahora), reg.nuevo(), List.of());
        return respuesta(reg.estado(), reg.nuevo(), reg.nuevos());
    }

    @PostMapping("/insignia")
    public Map<String, Object> insignia(@RequestBody InsigniaRequest q, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite(u);
        String id = q == null ? null : q.id();
        long ahora = System.currentTimeMillis();
        if (esDemo(u)) return demo(logros.equipar(u.id(), id, ahora, true), false, List.of());
        return respuesta(logros.equipar(u.id(), id, ahora), false, List.of());
    }
}
