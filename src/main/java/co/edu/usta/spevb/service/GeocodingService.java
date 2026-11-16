package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.JsonNode;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;

/**
 * Geocodificación con un servicio compatible con Nominatim (por defecto el público de OpenStreetMap).
 * <p>
 * <b>Política de uso (https://operations.osmfoundation.org/policies/nominatim/):</b> el servicio público NO admite autocompletado, así que este
 * servicio solo se usa en búsqueda EXPLÍCITA (Enter o «Buscar») y en geocodificación inversa de un punto elegido; {@code LugarService.sugerir}
 * nunca lo llama (hay una prueba que lo exige). El límite es de 1 petición por segundo en TOTAL para toda la aplicación
 * ({@link #INTERVALO_MINIMO_NS}, con margen), se identifica con un User-Agent propio (nunca el de la biblioteca HTTP), las respuestas se guardan
 * en una caché acotada y hay que conservar su atribución («OpenStreetMap / Nominatim» en la fuente de cada resultado). Para sugerencias
 * alternativas se usa el índice local, no este servicio. Para más volumen, una instancia propia con GEOCODER_URL.
 */
@Service
public class GeocodingService {
    /** 1 petición por segundo como máximo (la política lo fija como máximo absoluto); 1,1 s deja margen. */
    static final long INTERVALO_MINIMO_NS = 1_100_000_000L;
    private final String searchUrl;
    private final String reverseUrl;
    private final String userAgent;
    private final ObjectMapper mapper;
    private final CityArea cityArea;
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private final Map<String, List<Resultado>> searchCache = new LinkedHashMap<>();
    private final Map<String, Resultado> reverseCache = new LinkedHashMap<>();
    private long lastCall;

    public GeocodingService(@Value("${spevb.geocoder.url:}") String searchUrl,
                            @Value("${spevb.geocoder.reverse-url:}") String reverseUrl,
                            @Value("${spevb.geocoder.user-agent:SEVB-Rutas/4.10}") String userAgent,
                            ObjectMapper mapper,
                            CityArea cityArea) {
        this.searchUrl = searchUrl.strip();
        this.reverseUrl = reverseUrl.strip();
        this.userAgent = userAgent.strip();
        this.mapper = mapper;
        this.cityArea = cityArea;
        validateEndpoint(this.searchUrl);
        validateEndpoint(this.reverseUrl);
        if ((!this.searchUrl.isBlank() || !this.reverseUrl.isBlank()) && this.userAgent.length() < 8) {
            throw new IllegalArgumentException("GEOCODER_USER_AGENT debe identificar la aplicación.");
        }
    }

    private void validateEndpoint(String url) {
        if (!url.isBlank() && !url.startsWith("https://") && !url.startsWith("http://localhost:")
                && !url.startsWith("http://127.0.0.1:")) {
            throw new IllegalArgumentException("Configura un proveedor geográfico HTTPS o una instancia local.");
        }
    }

    public boolean configurado() { return !searchUrl.isBlank(); }
    public boolean reversoConfigurado() { return !reverseUrl.isBlank(); }

    public synchronized List<Resultado> buscar(String rawQuery) {
        if (!configurado()) return List.of();
        String normalizedQuery = cityArea.normalizeAddress(rawQuery);
        String cacheKey = normalizedQuery.toLowerCase(Locale.ROOT);
        if (searchCache.containsKey(cacheKey)) return searchCache.get(cacheKey);

        LinkedHashMap<String, Resultado> merged = new LinkedHashMap<>();
        String numeroPuerta = numeroPuertaSolicitado(normalizedQuery);
        for (String query : cityArea.searchQueries(rawQuery)) {
            if (!merged.isEmpty()) break;
            consultarBusqueda(query, rawQuery, numeroPuerta, merged);
        }
        List<Resultado> answer = List.copyOf(merged.values());
        putBounded(searchCache, cacheKey, answer, 250);
        return answer;
    }

    private void consultarBusqueda(String query, String rawQuery, String numeroPuerta,
                                   LinkedHashMap<String, Resultado> merged) {
        rateLimit();
        try {
            URI uri = uriBusqueda(query);
            var response = client.send(request(uri), HttpResponse.BodyHandlers.ofInputStream());
            leerResultadosBusqueda(response, rawQuery, numeroPuerta, merged);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Búsqueda interrumpida.");
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (java.net.http.HttpTimeoutException ex) {
            throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT, "El buscador de direcciones no respondió a tiempo.");
        } catch (Exception ex) {
            throw badGateway("No se pudo consultar el buscador de direcciones.");
        }
    }

    private URI uriBusqueda(String query) {
        String separator = searchUrl.contains("?") ? "&" : "?";
        return URI.create(searchUrl + separator
                + "format=jsonv2&addressdetails=1&limit=10&countrycodes=co&bounded=1&viewbox="
                + URLEncoder.encode(cityArea.viewbox(), StandardCharsets.UTF_8)
                + "&q=" + URLEncoder.encode(query, StandardCharsets.UTF_8));
    }

    private void leerResultadosBusqueda(HttpResponse<java.io.InputStream> response, String rawQuery,
                                        String numeroPuerta, LinkedHashMap<String, Resultado> merged)
            throws java.io.IOException {
        try (var body = response.body()) {
            requireOk(response.statusCode());
            byte[] bytes = body.readNBytes(400_001);
            if (bytes.length > 400_000) throw badGateway("Respuesta geográfica demasiado grande.");
            JsonNode array = mapper.readTree(bytes);
            if (!array.isArray()) throw badGateway("Respuesta geográfica inválida.");
            agregarResultadosBusqueda(array, rawQuery, numeroPuerta, merged);
        }
    }

    private void agregarResultadosBusqueda(JsonNode array, String rawQuery, String numeroPuerta,
                                           LinkedHashMap<String, Resultado> merged) {
        for (JsonNode item : array) {
            Resultado resultado = convertirResultadoBusqueda(item, rawQuery, numeroPuerta);
            if (resultado == null) continue;
            String external = resultado.externalId();
            String key = external != null ? external
                    : String.format(Locale.ROOT, "%.6f,%.6f", resultado.lat(), resultado.lng());
            merged.putIfAbsent(key, resultado);
            if (merged.size() >= 8) break;
        }
    }

    private Resultado convertirResultadoBusqueda(JsonNode item, String rawQuery, String numeroPuerta) {
        double lat = parse(item.path("lat").asText());
        double lng = parse(item.path("lon").asText());
        if (!cityArea.contains(lat, lng)) return null;

        String display = item.path("display_name").asText("").strip();
        if (display.isBlank()) return null;

        String numeroEncontrado = item.path("address").path("house_number").asText("").strip();
        if (!numeroPuerta.isBlank() && !normalizarNumero(numeroEncontrado).equals(numeroPuerta)) return null;
        if (!numeroPuerta.isBlank()
                && !viaSolicitadaCompatible(rawQuery, item.path("address").path("road").asText(""))) return null;

        String precision = numeroEncontrado.isBlank() ? "SIN_VERIFICAR" : "DIRECCION_PUNTUAL";
        String external = externalId(item.path("osm_type").asText(""), item.path("osm_id").asText(""));
        return new Resultado(display, display, lat, lng, "OpenStreetMap / Nominatim", external, precision);
    }

    public synchronized Resultado reverso(double lat, double lng) {
        cityArea.requireInside(lat, lng);
        if (!reversoConfigurado()) return null;
        String key = String.format(Locale.ROOT, "%.5f,%.5f", lat, lng);
        if (reverseCache.containsKey(key)) return reverseCache.get(key);
        return consultarReverso(lat, lng, key);
    }

    private Resultado consultarReverso(double lat, double lng, String key) {
        rateLimit();
        try {
            URI uri = uriReverso(lat, lng);
            var response = client.send(request(uri), HttpResponse.BodyHandlers.ofInputStream());
            return leerResultadoReverso(response, lat, lng, key);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Búsqueda interrumpida.");
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (java.net.http.HttpTimeoutException ex) {
            throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT, "El buscador de direcciones no respondió a tiempo.");
        } catch (Exception ex) {
            throw badGateway("No se pudo obtener la dirección del punto.");
        }
    }

    private URI uriReverso(double lat, double lng) {
        String separator = reverseUrl.contains("?") ? "&" : "?";
        return URI.create(reverseUrl + separator + "format=jsonv2&addressdetails=1&zoom=18&layer=address&lat="
                + URLEncoder.encode(Double.toString(lat), StandardCharsets.UTF_8)
                + "&lon=" + URLEncoder.encode(Double.toString(lng), StandardCharsets.UTF_8));
    }

    private Resultado leerResultadoReverso(HttpResponse<java.io.InputStream> response,
                                           double lat, double lng, String key) throws java.io.IOException {
        try (var body = response.body()) {
            requireOk(response.statusCode());
            byte[] bytes = body.readNBytes(200_001);
            if (bytes.length > 200_000) throw badGateway("Respuesta geográfica demasiado grande.");
            JsonNode item = mapper.readTree(bytes);
            return convertirResultadoReverso(item, lat, lng, key);
        }
    }

    private Resultado convertirResultadoReverso(JsonNode item, double lat, double lng, String key) {
        String display = item.path("display_name").asText("").strip();
        if (display.isBlank()) return null;
        double resultLat = parse(item.path("lat").asText(Double.toString(lat)));
        double resultLng = parse(item.path("lon").asText(Double.toString(lng)));
        if (!cityArea.contains(resultLat, resultLng)) return null;
        Resultado result = new Resultado(display, display, resultLat, resultLng,
                "OpenStreetMap / Nominatim",
                externalId(item.path("osm_type").asText(""), item.path("osm_id").asText("")));
        putBounded(reverseCache, key, result, 250);
        return result;
    }

    private HttpRequest request(URI uri) {
        return HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(8))
                .header("User-Agent", userAgent)
                .header("Accept", "application/json")
                .header("Accept-Language", "es-CO,es;q=0.9")
                .GET().build();
    }

    private void rateLimit() {
        long now = System.nanoTime();
        long minimum = INTERVALO_MINIMO_NS;
        if (lastCall != 0 && now - lastCall < minimum) {
            long remaining = minimum - (now - lastCall);
            try {
                Thread.sleep(remaining / 1_000_000L, (int) (remaining % 1_000_000L));
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Búsqueda interrumpida.");
            }
        }
        lastCall = System.nanoTime();
    }

    private void requireOk(int status) {
        if (status == 429) throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,
                "El proveedor de direcciones pidió reducir la frecuencia de consultas.");
        if (status != 200) throw badGateway("El buscador de direcciones no está disponible.");
    }

    private double parse(String value) { return Double.parseDouble(value); }

    private String externalId(String type, String id) {
        if (type.isBlank() || id.isBlank()) return null;
        return "osm:" + type + ":" + id;
    }

    private ResponseStatusException badGateway(String message) {
        return new ResponseStatusException(HttpStatus.BAD_GATEWAY, message);
    }

    private <K,V> void putBounded(Map<K,V> map, K key, V value, int max) {
        if (map.size() >= max) map.remove(map.keySet().iterator().next());
        map.put(key, value);
    }

    /** Extrae la placa solicitada sin confundir el número de la vía con el del inmueble. */
    static String numeroPuertaSolicitado(String q) {
        var m = java.util.regex.Pattern.compile("#\\s*(\\d+\\s*[A-Za-z]?\\s*[-–]\\s*\\d+[A-Za-z]?)")
                .matcher(q);
        return m.find() ? normalizarNumero(m.group(1)) : "";
    }

    /** Rechaza una casa con la misma placa pero ubicada en otra carrera/calle. */
    static boolean viaSolicitadaCompatible(String consulta, String viaEncontrada) {
        if (viaEncontrada == null || viaEncontrada.isBlank()) return false;
        String solicitada = normalizarVia(consulta.split("#", 2)[0]);
        String encontrada = normalizarVia(viaEncontrada);
        var p = java.util.regex.Pattern.compile("^(CARRERA|CALLE|AVENIDA|DIAGONAL|TRANSVERSAL)\\s+(\\d+[A-Z]?)");
        var a = p.matcher(solicitada);
        var b = p.matcher(encontrada);
        return a.find() && b.find() && a.group(1).equals(b.group(1))
                && a.group(2).equals(b.group(2));
    }

    private static String normalizarVia(String s) {
        String normal = java.text.Normalizer.normalize(s.toUpperCase(Locale.ROOT),
                java.text.Normalizer.Form.NFD).replaceAll("\\p{M}+", "");
        normal = normal.replaceAll("\\b(CRA|KRA|CR|KR)\\b", "CARRERA")
                .replaceAll("\\b(CLL|CL)\\b", "CALLE")
                .replaceAll("\\b(AV|AVDA)\\b", "AVENIDA")
                .replaceAll("\\b(DIAG|DG)\\b", "DIAGONAL")
                .replaceAll("\\b(TV|TR|TRANSV)\\b", "TRANSVERSAL");
        return normal.replaceAll("^AVENIDA\\s+(?=CARRERA|CALLE)", "")
                .replaceAll("[^A-Z0-9]+", " ").trim();
    }

    private static String normalizarNumero(String raw) {
        return raw == null ? "" : raw.toUpperCase(Locale.ROOT).replaceAll("[^0-9A-Z]", "");
    }

    public record Resultado(String nombre, String direccion, double lat, double lng,
                            String fuente, String externalId, String precision) {
        public Resultado(String nombre, String direccion, double lat, double lng,
                         String fuente, String externalId) {
            this(nombre, direccion, lat, lng, fuente, externalId, "SIN_VERIFICAR");
        }
    }
}
