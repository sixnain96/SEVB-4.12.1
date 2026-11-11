package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.ViajeCompartidoService;
import co.edu.usta.spevb.service.ViajeCompartidoService.Actualizacion;
import co.edu.usta.spevb.service.ViajeCompartidoService.Vista;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * «Compartir mi viaje» (docs/COMPARTIR-VIAJE.md). Los tokens viajan en CABECERAS (nunca en la URL de la API ni en el cuerpo de las respuestas de error):
 * {@code X-Seguimiento-Escritura} para quien viaja y {@code X-Seguimiento} para quien mira. El token de lectura no puede actualizar ni revocar.
 * Todo lo que no existe, venció o se revocó responde igual (404 genérico): no se revela cuál fue el caso.
 */
@RestController
@RequestMapping("/api/compartir")
public class ViajeCompartidoController {
    static final String CAB_ESCRITURA = "X-Seguimiento-Escritura", CAB_LECTURA = "X-Seguimiento";
    static final String NO_DISPONIBLE = "Este enlace ya no está disponible.";
    private final ViajeCompartidoService servicio;
    private final CuentaService cuentas;
    private final LimitadorSolicitudes limitador;

    public ViajeCompartidoController(ViajeCompartidoService servicio, CuentaService cuentas, LimitadorSolicitudes limitador) {
        this.servicio = servicio;
        this.cuentas = cuentas;
        this.limitador = limitador;
    }

    public record CrearRequest(JsonNode ruta) {}
    public record ActualizarRequest(String fase, Integer leg, Double progreso, Double lat, Double lng, Double precision, Integer etaMin) {}

    private void limite(String clave, int max, Duration ventana, String mensaje) {
        if (!limitador.permitir(clave, max, ventana)) throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, mensaje);
    }

    /** Crea el enlace durante un viaje en curso: sin una ruta válida no se crea nada. Funciona con o sin cuenta. */
    @PostMapping
    public Map<String, Object> crear(@RequestBody(required = false) CrearRequest q, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        limite("comp:crear:" + r.getRemoteAddr(), 8, Duration.ofHours(1), "Creaste varios enlaces seguidos. Inténtalo más tarde.");
        Long uid = cuentas.usuarioDeSesion(CuentaController.token(r)).map(CuentaService.Usuario::id).orElse(null);
        var c = servicio.crear(uid, q == null ? null : q.ruta());
        var m = new LinkedHashMap<String, Object>();
        m.put("lectura", c.lectura());          // va en el enlace que se comparte
        m.put("escritura", c.escritura());      // se queda en el teléfono que viaja (actualizar y dejar de compartir)
        m.put("expira", c.expiraEpoch());
        return m;
    }

    /** Desde el teléfono que viaja: última posición, fase y progreso (no cada lectura cruda: el cliente envía cada 10–15 s o al cambiar de fase). */
    @PutMapping
    public Map<String, Object> actualizar(@RequestBody(required = false) ActualizarRequest q, @RequestHeader(value = CAB_ESCRITURA, required = false) String escritura, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        if (!ViajeCompartidoService.formatoValido(escritura)) throw new ResponseStatusException(HttpStatus.NOT_FOUND, NO_DISPONIBLE);
        if (q == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Datos del viaje no válidos.");      // cuerpo vacío o «null»: error controlado, sin detalles internos
        limite("comp:w:" + ViajeCompartidoService.hash(escritura), 12, Duration.ofMinutes(1), "Demasiadas actualizaciones seguidas.");
        var a = new Actualizacion(q.fase(), q.leg() == null ? 0 : q.leg(), q.progreso() == null ? Double.NaN : q.progreso(), q.lat(), q.lng(), q.precision(), q.etaMin());
        if (!servicio.actualizar(escritura, a)) throw new ResponseStatusException(HttpStatus.NOT_FOUND, NO_DISPONIBLE);
        return Map.of("ok", true);
    }

    /** «Dejar de compartir»: el enlace deja de existir de inmediato. */
    @DeleteMapping
    public Map<String, Object> revocar(@RequestHeader(value = CAB_ESCRITURA, required = false) String escritura, HttpServletRequest r) {
        CuentaController.mismoSitio(r);
        limite("comp:rev:" + r.getRemoteAddr(), 30, Duration.ofMinutes(10), "Demasiados intentos. Espera unos minutos.");
        servicio.revocar(escritura);      // idempotente: revocar algo que ya no existe también termina bien
        return Map.of("ok", true);
    }

    /** Vista pública de solo lectura. Sin sesión; el token de lectura va en la cabecera X-Seguimiento. Admite ETag para no repetir lo que no cambió. */
    @GetMapping
    public Object consultar(@RequestHeader(value = CAB_LECTURA, required = false) String lectura, @RequestHeader(value = "If-None-Match", required = false) String etag,
                            HttpServletRequest r, HttpServletResponse resp) {
        limite("comp:r:" + r.getRemoteAddr(), 60, Duration.ofMinutes(1), "Demasiadas consultas seguidas. Espera unos segundos.");
        Vista v = servicio.consultar(lectura).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, NO_DISPONIBLE));
        String tag = "\"" + v.version() + "\"";
        resp.setHeader("ETag", tag);
        resp.setHeader("Cache-Control", "no-store");
        resp.setHeader("Referrer-Policy", "no-referrer");
        resp.setHeader("X-Robots-Tag", "noindex, nofollow");
        if (tag.equals(etag)) { resp.setStatus(HttpStatus.NOT_MODIFIED.value()); return null; }
        var m = new LinkedHashMap<String, Object>();
        m.put("estado", v.estado());
        m.put("fase", v.fase());
        m.put("leg", v.leg());
        m.put("progreso", v.progreso());
        if (v.lat() != null && v.lng() != null) m.put("posicion", Map.of("lat", v.lat(), "lng", v.lng()));
        if (v.etaMin() != null) m.put("etaMin", v.etaMin());
        m.put("actualizado", v.actualizadoEpoch());
        m.put("expira", v.expiraEpoch());
        m.put("ruta", v.ruta());
        return m;
    }
}
