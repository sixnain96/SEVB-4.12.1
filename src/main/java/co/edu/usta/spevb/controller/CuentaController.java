package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.GoogleTokenVerifier;
import co.edu.usta.spevb.service.CuentaService.Usuario;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.JsonNode;

import java.net.URI;
import java.time.Duration;
import java.util.Map;

/**
 * Cuenta de SEVB (Fase B): la ÚNICA vía pública para tener sesión es «Continuar con Google» (POST /google). La identidad es el «sub» de Google y la propiedad de los datos, el id interno de SEVB.
 * El registro, la entrada y el cambio de contraseña están retirados (HTTP 410): ya no emiten sesiones ni habilitan contraseñas. La sesión sigue siendo una cookie HttpOnly con expiración.
 */
@RestController
@RequestMapping("/api/cuenta")
public class CuentaController {
    static final String COOKIE = "spevb_sesion";
    /** Edad máxima de la credencial de Google que confirma un borrado (reautenticación reciente). */
    static final long EDAD_MAX_REAUTENTICACION_S = 300;
    static final String MSG_RETIRADO = "El acceso con correo y contraseña ya no está disponible. Usa «Continuar con Google».";
    private final CuentaService cuentas;
    private final LimitadorSolicitudes limitador;
    private final GoogleTokenVerifier google;
    private final String direccionOficial;
    private final String soporteCorreo;
    private final boolean vinculoAnterior;

    public CuentaController(CuentaService cuentas, LimitadorSolicitudes limitador, GoogleTokenVerifier google) {
        this(cuentas, limitador, google, "", "", false);
    }

    @Autowired
    public CuentaController(CuentaService cuentas, LimitadorSolicitudes limitador, GoogleTokenVerifier google,
                            @Value("${spevb.cuenta.direccion-oficial:}") String direccionOficial,
                            @Value("${spevb.cuenta.soporte-correo:}") String soporteCorreo,
                            @Value("${spevb.cuenta.vinculo-anterior:false}") boolean vinculoAnterior) {
        this.google = google;
        this.cuentas = cuentas;
        this.limitador = limitador;
        this.direccionOficial = direccionHttps(direccionOficial);
        this.soporteCorreo = correoSoporte(soporteCorreo);
        this.vinculoAnterior = vinculoAnterior;
    }

    public record SalirRequest(Boolean todas) {}
    public record GoogleRequest(String credential) {}
    public record EliminarRequest(String credential) {}
    public record VincularRequest(String credential, String correo, String clave) {}
    public record DatosRequest(JsonNode valor, Long base) {}

    // ------------------------------------------------------------------ ayudas
    /** Las operaciones que cambian algo solo se aceptan desde esta misma página (defensa contra CSRF). */
    static void mismoSitio(HttpServletRequest r) {
        String sitio = r.getHeader("Sec-Fetch-Site");
        if ("cross-site".equals(sitio)) throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Solicitud de otro sitio no permitida.");
        String origen = r.getHeader("Origin");
        if (origen != null && !origen.isBlank() && !"null".equals(origen)) {
            try {
                String host = URI.create(origen).getAuthority();
                String propio = r.getHeader("X-Forwarded-Host") != null ? r.getHeader("X-Forwarded-Host").split(",")[0].strip() : r.getHeader("Host");
                if (host != null && propio != null && !host.equalsIgnoreCase(propio))
                    throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Solicitud de otro sitio no permitida.");
            } catch (IllegalArgumentException e) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Solicitud no válida.");
            }
        }
    }

    static String token(HttpServletRequest r) {
        if (r.getCookies() == null) return null;
        for (Cookie c : r.getCookies()) if (COOKIE.equals(c.getName())) return c.getValue();
        return null;
    }

    /** Solo una dirección https con host y sin credenciales ni fragmentos; cualquier otra cosa se ignora (nunca se enlaza algo que no sea una página segura). */
    static String direccionHttps(String url) {
        if (url == null || url.isBlank() || url.length() > 200) return "";
        try {
            URI u = URI.create(url.strip());
            if (!"https".equals(u.getScheme()) || u.getHost() == null || u.getRawUserInfo() != null || u.getRawFragment() != null || u.getRawQuery() != null) return "";
            return u.toASCIIString();
        } catch (IllegalArgumentException e) { return ""; }
    }

    static String correoSoporte(String correo) {
        if (correo == null) return "";
        String c = correo.strip();
        return c.length() <= 120 && c.matches("^[^\\s@<>\"]{1,64}@[^\\s@<>\"]+\\.[^\\s@<>\"]{2,}$") ? c : "";
    }

    private Usuario exigirUsuario(HttpServletRequest r) {
        return cuentas.usuarioDeSesion(token(r)).orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Inicia sesión para continuar."));
    }

    private static void poner(HttpServletRequest r, HttpServletResponse resp, String valor, Duration vida) {
        resp.addHeader(HttpHeaders.SET_COOKIE, ResponseCookie.from(COOKIE, valor).httpOnly(true).secure(r.isSecure())
                .sameSite("Lax").path("/").maxAge(vida).build().toString());
    }

    private static Map<String, Object> vista(Usuario u) {
        var m = new java.util.LinkedHashMap<String, Object>(Map.of("id", u.id(), "nombre", u.nombre(), "correo", u.correo(), "conGoogle", u.conGoogle(), "admin", u.admin()));
        if (u.foto() != null) m.put("foto", u.foto());      // opcional: solo cuentas con Google que traen foto
        return m;
    }

    /** Respuesta de sesión: el usuario y, solo si Google acaba de verificar un correo que además usa una cuenta ANTIGUA con contraseña, un aviso para que la interfaz explique la recuperación. */
    private Map<String, Object> conUsuario(Usuario u) {
        var m = new java.util.LinkedHashMap<String, Object>();
        m.put("usuario", vista(u));
        if (cuentas.hayCuentaAnterior(u.correo())) m.put("cuentaAnterior", true);
        return m;
    }

    private void limite(String clave, int max, Duration ventana, String mensaje) {
        if (!limitador.permitir(clave, max, ventana)) throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS, mensaje);
    }

    private GoogleTokenVerifier.Identidad credencial(String credential, boolean reciente) {
        try {
            var id = reciente ? google.verificarReciente(credential, EDAD_MAX_REAUTENTICACION_S) : google.verificar(credential);
            google.consumir(id);
            return id;
        } catch (GoogleTokenVerifier.TokenInvalido e) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, e.getMessage());
        }
    }

    // ------------------------------------------------------------------ vías locales retiradas (no emiten sesiones ni habilitan contraseñas)
    @PostMapping("/registro")
    public Map<String, Object> registro() { throw new ResponseStatusException(HttpStatus.GONE, MSG_RETIRADO); }

    @PostMapping("/entrar")
    public Map<String, Object> entrar() { throw new ResponseStatusException(HttpStatus.GONE, MSG_RETIRADO); }

    @PostMapping("/clave")
    public Map<String, Object> clave() { throw new ResponseStatusException(HttpStatus.GONE, MSG_RETIRADO); }

    // ------------------------------------------------------------------ acceso con Google
    /**
     * Datos públicos para la pantalla de acceso: el Client ID de Google (no es un secreto) o nada si no está configurado; la dirección oficial (para cuando se intenta entrar desde una dirección
     * temporal); el correo de recuperación; y si el vínculo explícito de cuentas anteriores está habilitado. Nada de esto es secreto ni mezcla las claves de Maps/Places (otra configuración).
     */
    @GetMapping("/config")
    public Map<String, Object> config() {
        var m = new java.util.LinkedHashMap<String, Object>();
        if (google.activo()) m.put("google", google.clientId());
        m.put("modo", "google");
        m.put("adminConfigurado", cuentas.adminConfigurado());
        if (!direccionOficial.isEmpty()) m.put("direccionOficial", direccionOficial);
        if (!soporteCorreo.isEmpty()) m.put("soporte", soporteCorreo);
        if (vinculoAnterior) m.put("vinculoAnterior", true);
        return m;
    }

    /** Inicio de sesión / primer ingreso con Google: llega el ID token que entrega el botón oficial y se verifica aquí (firma, emisor, audiencia, vigencia, correo verificado, un solo uso). */
    @PostMapping("/google")
    public Map<String, Object> conGoogle(@RequestBody GoogleRequest q, HttpServletRequest r, HttpServletResponse resp) {
        mismoSitio(r);
        limite("goo:" + r.getRemoteAddr(), 30, Duration.ofMinutes(10), "Demasiados intentos. Espera unos minutos.");
        GoogleTokenVerifier.Identidad id = credencial(q.credential(), false);
        Usuario u = cuentas.entrarConGoogle(id);
        poner(r, resp, cuentas.abrirSesion(u.id(), r.getHeader("User-Agent")), Duration.ofDays(CuentaService.DIAS_SESION));
        return conUsuario(u);
    }

    @PostMapping("/salir")
    public Map<String, Object> salir(@RequestBody(required = false) SalirRequest q, HttpServletRequest r, HttpServletResponse resp) {
        mismoSitio(r);
        var usuario = cuentas.usuarioDeSesion(token(r));
        if (q != null && Boolean.TRUE.equals(q.todas()) && usuario.isPresent()) cuentas.cerrarTodas(usuario.get().id());
        else cuentas.cerrarSesion(token(r));
        poner(r, resp, "", Duration.ZERO);
        return Map.of("ok", true);
    }

    /**
     * Siempre responde 200: quien no ha entrado recibe {@code autenticado:false} (sin errores en la consola del navegador). Si la cookie es de una sesión de una cuenta ANTIGUA (nacida de una
     * contraseña), ya no identifica a nadie y se dice con {@code motivo: "cuenta-anterior"} para que la interfaz conserve los datos de este dispositivo y explique la recuperación.
     */
    @GetMapping("/yo")
    public Map<String, Object> yo(HttpServletRequest r) {
        var u = cuentas.usuarioDeSesion(token(r));
        if (u.isPresent()) {
            var m = new java.util.LinkedHashMap<String, Object>(conUsuario(u.get()));
            m.put("autenticado", true);
            return m;
        }
        return cuentas.sesionDeCuentaAnterior(token(r)) ? Map.<String, Object>of("autenticado", false, "motivo", "cuenta-anterior") : Map.<String, Object>of("autenticado", false);
    }

    /**
     * Elimina la cuenta con una REAUTENTICACIÓN reciente de Google del MISMO «sub» (credencial emitida hace menos de 5 minutos y de un solo uso). No depende de ninguna contraseña: sirve igual
     * para una cuenta vinculada que todavía conserve un hash antiguo.
     */
    @PostMapping("/eliminar")
    public Map<String, Object> eliminar(@RequestBody EliminarRequest q, HttpServletRequest r, HttpServletResponse resp) {
        mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite("elim:" + u.id(), 5, Duration.ofMinutes(10), "Demasiados intentos. Espera unos minutos.");
        if (!google.activo()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "La confirmación con Google no está disponible en este servidor.");
        GoogleTokenVerifier.Identidad id = credencial(q.credential(), true);
        String sub = cuentas.googleSubDe(u.id()).orElse(null);
        if (sub == null || !sub.equals(id.sub()))
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Esa confirmación es de otra cuenta de Google. Confirma con la misma cuenta con la que entraste.");
        cuentas.eliminar(u.id());
        poner(r, resp, "", Duration.ZERO);
        return Map.of("ok", true);
    }

    /**
     * Vínculo EXPLÍCITO de una cuenta anterior (con contraseña) a la cuenta de Google con la que se entró. Apagado por configuración (spevb.cuenta.vinculo-anterior). Pide las dos pruebas: una
     * credencial reciente de Google del mismo «sub» de la sesión y el correo y la contraseña de la cuenta anterior (con límites por IP, por perfil y por correo). Conserva el id de la cuenta
     * anterior, anula su contraseña, cierra sus sesiones y abre una nueva. Si algo no se prueba, no cambia nada.
     */
    @PostMapping("/vinculo-anterior")
    public Map<String, Object> vincularAnterior(@RequestBody VincularRequest q, HttpServletRequest r, HttpServletResponse resp) {
        mismoSitio(r);
        if (!vinculoAnterior) throw new ResponseStatusException(HttpStatus.GONE, "El vínculo de cuentas anteriores todavía no está habilitado. Pide la recuperación al equipo de SEVB.");
        Usuario u = exigirUsuario(r);
        String correo = q.correo() == null ? "" : q.correo().strip().toLowerCase();
        limite("vin:ip:" + r.getRemoteAddr(), 10, Duration.ofMinutes(10), "Demasiados intentos. Espera unos minutos.");
        limite("vin:u:" + u.id(), 5, Duration.ofMinutes(10), "Demasiados intentos. Espera unos minutos.");
        limite("vin:c:" + correo, 5, Duration.ofMinutes(10), "Demasiados intentos con esta cuenta. Espera unos minutos.");
        GoogleTokenVerifier.Identidad id = credencial(q.credential(), true);
        Usuario v = cuentas.vincularCuentaAnterior(u.id(), id, correo, q.clave());
        poner(r, resp, cuentas.abrirSesion(v.id(), r.getHeader("User-Agent")), Duration.ofDays(CuentaService.DIAS_SESION));
        return Map.of("usuario", vista(v), "vinculada", true);
    }

    // ------------------------------------------------------------------ datos sincronizados
    @GetMapping("/datos")
    public Map<String, Object> datos(HttpServletRequest r) {
        return cuentas.leerDatos(exigirUsuario(r).id());
    }

    @PostMapping("/datos/{clave}")
    public Map<String, Object> guardar(@PathVariable String clave, @RequestBody DatosRequest q, HttpServletRequest r) {
        mismoSitio(r);
        Usuario u = exigirUsuario(r);
        limite("datos:" + u.id(), 120, Duration.ofMinutes(1), "Demasiados cambios seguidos. Espera unos segundos.");
        long t = cuentas.guardarDatos(u.id(), clave, q.valor(), q.base());
        return Map.of("ok", true, "actualizadoEn", t);
    }
}
