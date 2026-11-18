package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.MapaConfig;

import co.edu.usta.spevb.config.CityArea;
import co.edu.usta.spevb.dto.LugarResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Direcciones con Google (Places API «New»): autocompletado y detalle del lugar elegido. OPCIONAL y APAGADO por defecto: solo se activa si
 * {@code GOOGLE_MAPS_API_KEY} tiene valor. La clave se envía en una cabecera desde Java (nunca va al navegador ni a la URL, así no queda en registros).
 * <p>
 * Respeta las condiciones de Google en lo que depende de este código: no se guarda nada de lo que devuelve (ni texto ni coordenadas: lo elegido
 * pasa al planificador y, si la persona lo guarda en «Mis lugares», se guarda solo su punto) y cada resultado se marca con la fuente «Google Maps».
 * Los resultados solo se usan con un mapa de Google (ver {@code docs/GOOGLE-MAPS.md}).
 * <p>
 * <b>Facturación (Places API New, comprobado en la documentación vigente de Google, nov-2026):</b> el autocompletado SE COBRA. Con un
 * {@code sessionToken} las 12 primeras solicitudes de la sesión se facturan como «Autocomplete Requests», las siguientes como «Autocomplete
 * Session Usage» (sin cargo) y la solicitud de detalle que cierra la sesión se factura por el nivel más alto de los campos pedidos. Sin token (o
 * reutilizándolo) cada solicitud se factura por separado. Por eso el token es de UNA búsqueda de la persona (lo genera el navegador) y el detalle
 * pide solo campos del nivel Essentials ({@code id, formattedAddress, location, types}); {@code displayName} es nivel Pro y se evita: el nombre
 * visible sale del texto de la sugerencia elegida. Precios y SKU: https://developers.google.com/maps/documentation/places/web-service/session-pricing
 * y https://developers.google.com/maps/billing-and-pricing/sku-details/places (revísalos antes de decidir; cambian).
 */
@Service
public class GoogleDireccionesService {
    public static final String FUENTE = "Google Maps";
    /** Prefijo del identificador que viaja por el navegador (campo {@code magicKey}) para distinguirlo del de ArcGIS. */
    public static final String PREFIJO = "g:";
    private static final java.util.regex.Pattern ID_LUGAR = java.util.regex.Pattern.compile("[A-Za-z0-9_-]{10,300}");
    /** Token de sesión: lo genera el navegador (UUID); Google acepta cadenas seguras para URL de hasta 36 caracteres. */
    private static final java.util.regex.Pattern SESION = java.util.regex.Pattern.compile("[A-Za-z0-9_-]{16,36}");
    private static final int MAX_BYTES = 200_000;
    /** Campos mínimos del detalle del lugar elegido (todos de nivel Essentials). */
    static final String CAMPOS_DETALLE = "id,formattedAddress,addressComponents,location,types";
    /** Campos de la búsqueda por texto (Enter / «Buscar»): el nombre visible hace falta porque aquí no hay sugerencia elegida. */
    static final String CAMPOS_TEXTO = "places.id,places.displayName,places.formattedAddress,places.addressComponents,places.location,places.types";

/** {@code texto} es el texto completo de la predicción; {@code principal} y {@code secundario} son su nombre y su referencia (structuredFormat de Places) para mostrarlos en dos líneas. */
    public record Sugerencia(String texto, String lugarId, String principal, String secundario) {
        public Sugerencia(String texto, String lugarId) { this(texto, lugarId, null, null); }
    }

    private final String clave;
    private final String base;
    private final ObjectMapper mapper;
    private final CityArea area;
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();

    private final boolean sobreMapaDeGoogle;

    /** Sin información del proveedor de mapa (pruebas): solo cuenta la clave. */
    public GoogleDireccionesService(String clave, String base, ObjectMapper mapper, CityArea area) { this(clave, base, mapper, area, null); }

    @Autowired
    public GoogleDireccionesService(@Value("${spevb.google-maps.api-key:}") String clave,
                                    @Value("${spevb.google-maps.url:https://places.googleapis.com}") String base,
                                    ObjectMapper mapper, CityArea area, MapaConfig mapa) {
        this.clave = clave == null ? "" : clave.strip();
        this.base = base == null ? "" : base.strip().replaceAll("/+$", "");
        this.mapper = mapper;
        this.area = area;
        // Los términos de Google Maps Platform piden que los resultados de Places se muestren sobre un mapa de Google. Con otro proveedor de mapa
        // (Leaflet) las sugerencias de Google se APAGAN en lugar de dibujarse sobre un mapa ajeno. Ver docs/GOOGLE-MAPS.md.
        this.sobreMapaDeGoogle = mapa == null || mapa.esGoogle();
        if (!this.clave.isBlank() && !this.sobreMapaDeGoogle)
            org.slf4j.LoggerFactory.getLogger(GoogleDireccionesService.class).info("Direcciones de Google (Places) apagadas: MAP_PROVIDER no es «google» y sus resultados deben mostrarse sobre un mapa de Google.");
        if (this.clave.isBlank())
            org.slf4j.LoggerFactory.getLogger(GoogleDireccionesService.class).info("Búsqueda de lugares con Google sin configurar: falta GOOGLE_MAPS_API_KEY (la búsqueda del pasajero dirá que no está configurada).");
        if (!this.clave.isBlank() && !this.base.startsWith("https://") && !this.base.startsWith("http://localhost:") && !this.base.startsWith("http://127.0.0.1:"))
            throw new IllegalArgumentException("GOOGLE_MAPS_URL debe ser HTTPS.");
    }

    public boolean activo() { return !clave.isBlank() && sobreMapaDeGoogle; }
    /** Solo si hay clave (nunca su valor) y si el mapa es de Google: sirven al diagnóstico de configuración. */
    public boolean tieneClave() { return !clave.isBlank(); }
    public boolean sobreMapaDeGoogle() { return sobreMapaDeGoogle; }

    /** Devuelve el token de sesión si tiene la forma esperada; si no, null (el servidor NUNCA inventa uno compartido entre personas). */
    public static String sesionValida(String sesion) {
        return sesion != null && SESION.matcher(sesion).matches() ? sesion : null;
    }

    /** Sugerencias al escribir (≥ 3 letras) sin token de sesión (cada solicitud se factura por separado). */
    public List<Sugerencia> sugerir(String texto) { return sugerir(texto, null); }

    /** Sugerencias al escribir (≥ 3 letras), limitadas a Colombia y a la caja de Villavicencio. Vacío si está apagado. */
    public List<Sugerencia> sugerir(String texto, String sesion) {
        if (!activo() || texto == null || texto.strip().length() < 3 || texto.length() > 160) return List.of();
        Map<String, Object> cuerpo = new java.util.LinkedHashMap<>();
        cuerpo.put("input", paraGoogle(texto));
        cuerpo.put("languageCode", "es");
        cuerpo.put("regionCode", "co");
        cuerpo.put("includedRegionCodes", List.of("co"));
        cuerpo.put("locationRestriction", Map.of("rectangle", Map.of(
                "low", Map.of("latitude", area.minLat(), "longitude", area.minLng()),
                "high", Map.of("latitude", area.maxLat(), "longitude", area.maxLng()))));
        String token = sesionValida(sesion);
        if (token != null) cuerpo.put("sessionToken", token);
        JsonNode raiz = llamar(HttpRequest.newBuilder(URI.create(base + "/v1/places:autocomplete"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(cuerpo))));
        List<Sugerencia> salida = new ArrayList<>();
        for (JsonNode s : raiz.path("suggestions")) {
            JsonNode p = s.path("placePrediction");
            String id = p.path("placeId").asText("").strip(), t = p.path("text").path("text").asText("").strip();
            // Se deduplica por el identificador de Google: dos lugares con el mismo nombre y distinto identificador pueden ser sedes distintas.
            if (!t.isBlank() && t.length() <= 200 && ID_LUGAR.matcher(id).matches() && salida.stream().noneMatch(x -> x.lugarId().equals(id))) {
                String principal = p.path("structuredFormat").path("mainText").path("text").asText("").strip();
                String secundario = p.path("structuredFormat").path("secondaryText").path("text").asText("").strip();
                if (principal.isBlank() || principal.length() > 120) {      // sin formato estructurado: el primer segmento es el nombre y el resto la referencia
                    String[] partes = t.split(",", 2);
                    principal = partes[0].strip();
                    secundario = partes.length > 1 ? partes[1].strip() : "";
                }
                salida.add(new Sugerencia(t, id, principal, secundario.length() > 160 ? secundario.substring(0, 160) : secundario));
            }
            if (salida.size() >= 6) break;
        }
        return List.copyOf(salida);
    }

    /** Una dirección con vía y número («Cra. 22 #38-10», «cll30»); un nombre comercial («TV Center») NO lo es y se envía tal cual lo escribió la persona. */
    static boolean pareceDireccion(String texto) {
        return texto != null && texto.matches("(?iUs)^\\s*(?:calle|carrera|avenida|diagonal|transversal|cra|kra|cr|kr|cll|cl|av|avda|diag|dg|tv|transv|tr)\\.?\\s*\\d.*");
    }

    /** Texto que se manda al autocompletado: normalizado solo si es una dirección; si no, el texto de la persona sin espacios de más. */
    String paraGoogle(String texto) {
        return pareceDireccion(texto) ? area.normalizeAddress(texto) : texto.strip().replaceAll("\\s+", " ");
    }

    private static final java.util.regex.Pattern OTRA_CIUDAD = java.util.regex.Pattern.compile(
            "(?iU)\\b(bogot[aá]|medell[ií]n|cali|barranquilla|cartagena|bucaramanga|c[uú]cuta|ibagu[eé]|pereira|manizales|villeta|acac[ií]as|granada|restrepo|cumaral|puerto l[oó]pez)\\b");

    /** ¿La persona nombró otra ciudad (Bogotá, Acacías…)? Entonces no se le agrega Villavicencio ni se hace un intento adicional con la vía sola. */
    static boolean nombraOtraCiudad(String texto) { return texto != null && OTRA_CIUDAD.matcher(texto).find(); }

    /**
     * Consulta de la búsqueda por texto. El rectángulo (locationRestriction) de Text Search NO garantiza que una dirección quede en Villavicencio: el servidor revisa cada coordenada. Para una
     * dirección numerada se agrega el contexto «Villavicencio, Meta» solo si la persona no nombró otra ciudad (así «Bogotá» no se vuelve un sitio local); un nombre se envía tal cual.
     */
    String consultaTexto(String texto) {
        if (!pareceDireccion(texto)) return texto.strip().replaceAll("\\s+", " ");
        String normal = area.normalizeAddress(texto);
        return OTRA_CIUDAD.matcher(normal).find() ? normal : area.searchQuery(texto);
    }

    /** Búsqueda por texto (Enter o botón «Buscar»): varios lugares de Villavicencio a la vez. Se usa con moderación porque es más cara que el autocompletar. */
    public List<LugarResponse> buscarTexto(String texto) { return buscarTextoResultado(texto).lugares(); }

    /** Igual que {@link #buscarTexto} y además cuenta cuántos lugares descartó por estar fuera de Villavicencio. */
    public ResultadoLugares buscarTextoResultado(String texto) {
        if (!activo() || texto == null || texto.strip().length() < 3 || texto.length() > 160) return ResultadoLugares.VACIO;
        Map<String, Object> cuerpo = Map.of(
                "textQuery", consultaTexto(texto),
                "languageCode", "es",
                "regionCode", "co",
                "pageSize", 5,
                "locationRestriction", Map.of("rectangle", Map.of(
                        "low", Map.of("latitude", area.minLat(), "longitude", area.minLng()),
                        "high", Map.of("latitude", area.maxLat(), "longitude", area.maxLng()))));
        JsonNode raiz = llamar(HttpRequest.newBuilder(URI.create(base + "/v1/places:searchText"))
                .header("Content-Type", "application/json")
                .header("X-Goog-FieldMask", CAMPOS_TEXTO)
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(cuerpo))));
        List<LugarResponse> salida = new ArrayList<>();
        int fuera = 0;
        for (JsonNode r : raiz.path("places")) {
            LugarResponse l = aLugar(r, null);
            if (l != null) salida.add(l); else if (r.has("location") && !dentro(r)) fuera++;
            if (salida.size() >= 5) break;
        }
        return new ResultadoLugares(List.copyOf(salida), fuera);
    }

    /** Ubica el lugar que la persona eligió en la lista. Solo devuelve puntos dentro de Villavicencio. */
    public List<LugarResponse> buscar(String lugarId) { return resolver(lugarId, null, null).lugares(); }

    /**
     * Ubica EL lugar elegido (ese identificador y ningún otro). {@code nombreSugerido} es el texto de la sugerencia que eligió la persona
     * (su primer segmento sirve de nombre visible, ya que {@code displayName} no se pide: es de nivel Pro); {@code sesion} cierra la sesión de
     * autocompletado de esa búsqueda.
     */
    public ResultadoLugares resolver(String lugarId, String nombreSugerido, String sesion) {
        if (!activo() || lugarId == null || !ID_LUGAR.matcher(lugarId).matches()) return ResultadoLugares.VACIO;
        String token = sesionValida(sesion);
        String url = base + "/v1/places/" + URLEncoder.encode(lugarId, StandardCharsets.UTF_8) + "?languageCode=es"
                + (token != null ? "&sessionToken=" + URLEncoder.encode(token, StandardCharsets.UTF_8) : "");
        JsonNode r = llamar(HttpRequest.newBuilder(URI.create(url)).header("X-Goog-FieldMask", CAMPOS_DETALLE).GET());
        // Se resuelve ESE identificador: si Google devuelve otro (u ninguno) NO se acepta ni se sustituye por otro resultado.
        if (!lugarId.equals(r.path("id").asText("")))
            throw new ProveedorException(EstadoBusqueda.RESPUESTA_INVALIDA, "Google devolvió un lugar distinto al elegido.");
        LugarResponse l = aLugar(r, nombreSugerido);
        if (l != null) return new ResultadoLugares(List.of(l), 0);
        return new ResultadoLugares(List.of(), r.has("location") && !dentro(r) ? 1 : 0);
    }

    private boolean dentro(JsonNode r) {
        return area.contains(r.path("location").path("latitude").asDouble(Double.NaN), r.path("location").path("longitude").asDouble(Double.NaN));
    }

    private LugarResponse aLugar(JsonNode r, String nombreSugerido) {
        double lat = r.path("location").path("latitude").asDouble(Double.NaN), lng = r.path("location").path("longitude").asDouble(Double.NaN);
        if (!area.contains(lat, lng)) return null;
        String direccion = r.path("formattedAddress").asText("").strip();
        String nombre = r.path("displayName").path("text").asText("").strip();
        if (nombre.isBlank() && nombreSugerido != null) {
            String primero = nombreSugerido.split(",", 2)[0].strip();
            if (!primero.isBlank() && primero.length() <= 120) nombre = primero;
        }
        if (direccion.isBlank() && nombre.isBlank()) return null;
        if (nombre.isBlank()) nombre = direccion;
        if (direccion.isBlank()) direccion = nombre;
        String gid = r.path("id").asText("");
        return new LugarResponse(null, nombre, direccion, lat, lng, FUENTE, false, precision(r.path("types")), ID_LUGAR.matcher(gid).matches() ? gid : null, nomenclaturaDe(r.path("addressComponents")));
    }

    /**
     * Dirección armada con los componentes estructurados de Google: «route» («Carrera 27») + «street_number» («35A-50») → «Carrera 27 # 35A-50». Null si Google no trae ambos.
     * Se compara por componentes (tipo, vía, Bis, sentido, placa) en lugar de por las cifras sueltas de la dirección formateada.
     */
    String nomenclaturaDe(JsonNode componentes) {
        String ruta = null, numero = null;
        for (JsonNode c : componentes) {
            boolean esRuta = false, esNumero = false;
            for (JsonNode t : c.path("types")) { if ("route".equals(t.asText())) esRuta = true; if ("street_number".equals(t.asText())) esNumero = true; }
            String largo = c.path("longText").asText("").strip();
            if (esRuta && ruta == null && !largo.isBlank() && largo.length() <= 80) ruta = largo;
            if (esNumero && numero == null && !largo.isBlank() && largo.length() <= 30) numero = largo;
        }
        if (ruta == null || numero == null) return null;
        String armada = area.normalizeAddress(ruta + " # " + numero);
        return Nomenclatura.de(armada, area).filter(Nomenclatura::tienePlaca).map(Nomenclatura::texto).orElse(null);
    }

    /** Tipo de punto según los «types» de Google (no certifica exactitud, igual que en las demás fuentes). */
    static String precision(JsonNode tipos) {
        Set<String> t = new java.util.HashSet<>();
        for (JsonNode n : tipos) t.add(n.asText());
        if (t.contains("street_address") || t.contains("premise") || t.contains("subpremise")) return "DIRECCION_PUNTUAL";
        if (t.contains("route")) return "VIA";
        if (t.contains("neighborhood") || t.contains("sublocality") || t.contains("sublocality_level_1")) return "SECTOR";
        if (t.contains("locality") || t.contains("administrative_area_level_2")) return "CIUDAD";
        return "LUGAR";
    }

    /** Hace la llamada y clasifica los fallos (cuota, clave, tiempo, red, respuesta inválida) sin exponer la clave ni la URL en el mensaje. */
    private JsonNode llamar(HttpRequest.Builder pedido) {
        try {
            var respuesta = client.send(pedido.timeout(Duration.ofSeconds(6)).header("X-Goog-Api-Key", clave).build(), HttpResponse.BodyHandlers.ofInputStream());
            try (var cuerpo = respuesta.body()) {
                byte[] bytes = cuerpo.readNBytes(MAX_BYTES + 1);
                if (respuesta.statusCode() != 200)
                    throw new ProveedorException(ProveedorException.desdeHttp(respuesta.statusCode(), new String(bytes, 0, Math.min(bytes.length, 2000), StandardCharsets.UTF_8)),
                            "Google respondió " + respuesta.statusCode());
                if (bytes.length > MAX_BYTES) throw new ProveedorException(EstadoBusqueda.RESPUESTA_INVALIDA, "Respuesta de Google demasiado grande.");
                try {
                    return mapper.readTree(bytes);
                } catch (RuntimeException ex) {
                    throw new ProveedorException(EstadoBusqueda.RESPUESTA_INVALIDA, "Google devolvió una respuesta inválida.");
                }
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new ProveedorException(EstadoBusqueda.TIMEOUT, "Búsqueda interrumpida.");
        } catch (ProveedorException ex) {
            throw ex;
        } catch (java.net.http.HttpTimeoutException ex) {
            throw new ProveedorException(EstadoBusqueda.TIMEOUT, "Google no respondió a tiempo.");
        } catch (Exception ex) {
            throw new ProveedorException(EstadoBusqueda.RED, "No se pudo consultar Google.");   // el mensaje no lleva la clave ni la URL
        }
    }
}
