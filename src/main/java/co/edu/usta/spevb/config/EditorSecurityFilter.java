package co.edu.usta.spevb.config;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.io.ByteArrayInputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Set;

@Component
public class EditorSecurityFilter extends OncePerRequestFilter {
    private static final long LIMITE_CUERPO_BYTES = 2_000_000L;
    private static final Set<String> METODOS_LECTURA = Set.of("GET", "HEAD");
    private static final Set<String> METODOS_ESCRITURA_JSON = Set.of("POST", "PUT", "PATCH");

    private final boolean enabled;
    private final byte[] token;
    private final org.springframework.beans.factory.ObjectProvider<co.edu.usta.spevb.service.CuentaService> cuentas;
    private final String csp;

    /** Sin cuentas (usado en pruebas): solo vale la clave de administración. */
    public EditorSecurityFilter(boolean enabled, String token) {
        this(enabled, token, null, MapaConfig.LEAFLET);
    }

    public EditorSecurityFilter(boolean enabled, String token,
                                org.springframework.beans.factory.ObjectProvider<co.edu.usta.spevb.service.CuentaService> cuentas) {
        this(enabled, token, cuentas, MapaConfig.LEAFLET);
    }

    /** Con proveedor de mapa explícito (pruebas de la política según el proveedor). */
    public EditorSecurityFilter(boolean enabled, String token, String proveedorMapa) {
        this(enabled, token, null, proveedorMapa);
    }

    @org.springframework.beans.factory.annotation.Autowired
    public EditorSecurityFilter(@Value("${spevb.editor.enabled:false}") boolean enabled,
                                @Value("${spevb.editor.token:}") String token,
                                org.springframework.beans.factory.ObjectProvider<co.edu.usta.spevb.service.CuentaService> cuentas,
                                MapaConfig mapa) {
        this(enabled, token, cuentas, mapa.proveedor());
    }

    private EditorSecurityFilter(boolean enabled, String token,
                                 org.springframework.beans.factory.ObjectProvider<co.edu.usta.spevb.service.CuentaService> cuentas,
                                 String proveedorMapa) {
        this.csp = ContentSecurityPolicy.para(proveedorMapa);
        this.cuentas = cuentas;
        if (enabled && (token.length() < 32 || token.isBlank())) {
            throw new IllegalArgumentException("EDITOR_TOKEN debe contener al menos 32 caracteres para habilitar el editor.");
        }
        this.enabled = enabled;
        this.token = token.getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        ponerCabecerasSeguridad(response);
        if (rutaInvalida(request.getRequestURI())) {
            reject(response, 400, "La ruta de la solicitud no es válida.");
            return;
        }

        String path = request.getRequestURI().substring(request.getContextPath().length());
        ponerCabecerasDeRuta(path, response);

        HttpServletRequest solicitud = request;
        if (esRutaEditor(path)) {
            solicitud = prepararSolicitudEditor(solicitud, response);
            if (solicitud == null) {
                return;
            }
        }
        if (esEscrituraApiPublica(path, solicitud)) {
            solicitud = limitarCuerpoJson(solicitud, response);
            if (solicitud == null) {
                return;
            }
        }
        chain.doFilter(solicitud, response);
    }

    private void ponerCabecerasSeguridad(HttpServletResponse response) {
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.setHeader("X-Frame-Options", "DENY");
        response.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
        response.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)");
        // La política depende del proveedor del mapa (ContentSecurityPolicy): cada modo permite solo sus hosts; accounts.google.com/gsi/* es del botón «Continuar con Google».
        response.setHeader("Content-Security-Policy", csp);
    }

    private boolean rutaInvalida(String requestUri) {
        return requestUri.contains(";") || requestUri.contains("%") || requestUri.contains("\\");
    }

    private void ponerCabecerasDeRuta(String path, HttpServletResponse response) {
        if (path.startsWith("/api/")) response.setHeader("Cache-Control", "no-store");
        if (path.equals("/seguir.html")) {
            // Página pública de «Compartir mi viaje»: nunca se guarda, no se indexa y no filtra la dirección en el Referer.
            response.setHeader("Cache-Control", "no-store");
            response.setHeader("Referrer-Policy", "no-referrer");
            response.setHeader("X-Robots-Tag", "noindex, nofollow");
        }
    }

    private boolean esRutaEditor(String path) {
        return path.startsWith("/api/editor/");
    }

    private HttpServletRequest prepararSolicitudEditor(HttpServletRequest request, HttpServletResponse response)
            throws IOException {
        if (!enabled) {
            reject(response, 403, "El editor está deshabilitado en el servidor.");
            return null;
        }
        if (!tieneCredencialesValidas(request)) {
            reject(response, 401, "Clave de edición ausente o incorrecta.");
            return null;
        }
        if (METODOS_LECTURA.contains(request.getMethod())) {
            return request;
        }
        if ("cross-site".equals(request.getHeader("Sec-Fetch-Site"))) {
            reject(response, 403, "No se permiten operaciones desde otro sitio.");
            return null;
        }
        if (METODOS_ESCRITURA_JSON.contains(request.getMethod())) {
            return limitarCuerpoJson(request, response);
        }
        return request;
    }

    private boolean tieneCredencialesValidas(HttpServletRequest request) {
        String supplied = request.getHeader("X-Editor-Token");
        boolean claveOk = supplied != null
                && MessageDigest.isEqual(token, supplied.getBytes(StandardCharsets.UTF_8));
        // Un administrador con sesión iniciada (correo verificado con Google y listado en ADMIN_CORREOS) no necesita escribir la clave.
        return claveOk || esAdministrador(request);
    }

    private HttpServletRequest limitarCuerpoJson(HttpServletRequest request, HttpServletResponse response)
            throws IOException {
        if (!esContenidoJson(request.getContentType())) {
            reject(response, 415, "Usa Content-Type application/json.");
            return null;
        }
        if (request.getContentLengthLong() > LIMITE_CUERPO_BYTES) {
            reject(response, 413, "La solicitud excede el límite de 2 MB.");
            return null;
        }
        byte[] body = request.getInputStream().readNBytes((int) LIMITE_CUERPO_BYTES + 1);
        if (body.length > LIMITE_CUERPO_BYTES) {
            reject(response, 413, "La solicitud excede el límite de 2 MB.");
            return null;
        }
        return new BoundedRequest(request, body);
    }

    private boolean esContenidoJson(String contentType) {
        return contentType != null
                && "application/json".equalsIgnoreCase(contentType.split(";", 2)[0].strip());
    }

    private boolean esEscrituraApiPublica(String path, HttpServletRequest request) {
        return path.startsWith("/api/")
                && !path.startsWith("/api/editor/")
                && "POST".equals(request.getMethod());
    }

    private boolean esAdministrador(HttpServletRequest request) {
        if (cuentas == null || request.getCookies() == null) return false;
        for (Cookie cookie : request.getCookies()) {
            if ("spevb_sesion".equals(cookie.getName())) {
                var servicio = cuentas.getIfAvailable();
                return servicio != null
                        && servicio.usuarioDeSesion(cookie.getValue()).map(usuario -> usuario.admin()).orElse(false);
            }
        }
        return false;
    }

    private static class BoundedRequest extends HttpServletRequestWrapper {
        private final byte[] body;

        BoundedRequest(HttpServletRequest request, byte[] body) {
            super(request);
            this.body = body;
        }

        @Override
        public ServletInputStream getInputStream() {
            var input = new ByteArrayInputStream(body);
            return new ServletInputStream() {
                @Override public int read() { return input.read(); }
                @Override public int read(byte[] b, int off, int len) { return input.read(b, off, len); }
                @Override public boolean isFinished() { return input.available() == 0; }
                @Override public boolean isReady() { return true; }
                @Override public void setReadListener(ReadListener listener) {
                    throw new UnsupportedOperationException("Synchronous JSON endpoint");
                }
            };
        }

        @Override
        public BufferedReader getReader() {
            return new BufferedReader(new InputStreamReader(getInputStream(), StandardCharsets.UTF_8));
        }

        @Override public int getContentLength() { return body.length; }
        @Override public long getContentLengthLong() { return body.length; }
    }

    private void reject(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");
        response.getWriter().write("{\"status\":" + status + ",\"message\":\"" + message + "\"}");
    }
}
