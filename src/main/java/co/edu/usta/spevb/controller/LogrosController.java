package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.CuentaService.Usuario;
import co.edu.usta.spevb.service.LogrosService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
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
        return respuesta(logros.estado(u.id(), System.currentTimeMillis()), false, List.of());
    }

    @PostMapping("/viaje")
    public Map<String, Object> viaje(@RequestBody ViajeRequest q, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite(u);
        if (q == null || q.llegadaMs() == null || q.buses() == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Faltan datos del viaje.");
        var reg = logros.registrar(u.id(), q.viajeId(), q.llegadaMs(), q.buses(), System.currentTimeMillis());
        return respuesta(reg.estado(), reg.nuevo(), reg.nuevos());
    }

    @PostMapping("/practica")
    public Map<String, Object> practica(HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite(u);
        var reg = logros.practica(u.id(), System.currentTimeMillis());
        return respuesta(reg.estado(), reg.nuevo(), reg.nuevos());
    }

    @PostMapping("/insignia")
    public Map<String, Object> insignia(@RequestBody InsigniaRequest q, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite(u);
        return respuesta(logros.equipar(u.id(), q == null ? null : q.id(), System.currentTimeMillis()), false, List.of());
    }
}
