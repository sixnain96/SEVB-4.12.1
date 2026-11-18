package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
import co.edu.usta.spevb.dto.LugarResponse;
import co.edu.usta.spevb.repository.LugarRepository;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;

/**
 * Clasificación de lo que devuelve Google para una dirección numerada (EXACTA, POSIBLE, REFERENCIA) con un Google SIMULADO: se prueba la lógica de SEVB (qué se ofrece, en qué orden y con
 * cuántas llamadas), no la calidad real de los resultados de Google. Direcciones públicas o ficticias: nunca casas privadas.
 */
class ClasificacionCoincidenciasTest {
    private final CityArea area = new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45);
    private HttpServer servidor;
    private final List<String> consultas = new ArrayList<>();
    private final AtomicReference<String> primera = new AtomicReference<>("{\"places\":[]}");
    private final AtomicReference<String> segunda = new AtomicReference<>("{\"places\":[]}");
    private final AtomicInteger llamadasTexto = new AtomicInteger();
    private final AtomicReference<String> autocompletar = new AtomicReference<>("{\"suggestions\":[]}");
    private final AtomicReference<String> detalle = new AtomicReference<>("{}");
    private final List<String> rutas = new ArrayList<>();
    private LugarService servicio;

    @BeforeEach void arrancar() throws Exception {
        servidor = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        servidor.createContext("/", ex -> {
            String cuerpo = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            String json = "{}";
            rutas.add(ex.getRequestURI().getPath());
            if (ex.getRequestURI().getPath().endsWith(":autocomplete")) json = autocompletar.get();
            else if (ex.getRequestURI().getPath().contains("/v1/places/")) json = detalle.get();
            else if (ex.getRequestURI().getPath().endsWith(":searchText")) {
                consultas.add(cuerpo);
                json = llamadasTexto.incrementAndGet() == 1 ? primera.get() : segunda.get();
            }
            byte[] b = json.getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(200, b.length);
            ex.getResponseBody().write(b);
            ex.close();
        });
        servidor.start();
        var google = new GoogleDireccionesService("clave-de-prueba", "http://127.0.0.1:" + servidor.getAddress().getPort(), JsonMapper.builder().build(), area);
        servicio = new LugarService(mock(LugarRepository.class), mock(GeocodingService.class), area, mock(DireccionesHibridasService.class), mock(DireccionesLocalesService.class));
        servicio.usarGoogle(google);
        servicio.soloGoogle(true);
    }

    @AfterEach void parar() { servidor.stop(0); }

    private static String lugar(String id, String direccion, String ruta, String numero, double lat, double lng, String... tipos) {
        String comps = ruta == null ? "[]" : "[{\"longText\":\"" + ruta + "\",\"types\":[\"route\"]}" + (numero == null ? "" : ",{\"longText\":\"" + numero + "\",\"types\":[\"street_number\"]}") + "]";
        return "{\"id\":\"" + id + "\",\"formattedAddress\":\"" + direccion + "\",\"displayName\":{\"text\":\"" + direccion.split(",")[0] + "\"},\"location\":{\"latitude\":" + lat + ",\"longitude\":" + lng
                + "},\"addressComponents\":" + comps + ",\"types\":[" + String.join(",", java.util.Arrays.stream(tipos).map(t -> "\"" + t + "\"").toList()) + "]}";
    }

    private static String lugares(String... l) { return "{\"places\":[" + String.join(",", l) + "]}"; }

    // ------------------------------------------------------------------ exacta
    @Test void laDireccionExactaSeMarcaExactaYVaPrimero() {
        primera.set(lugares(lugar("ChIJviaCarrera27XX", "Cra. 27, Villavicencio, Meta", "Carrera 27", null, 4.14, -73.63, "route"),
                lugar("ChIJexactaPlaca001", "Cra. 27 #35A-50, Villavicencio, Meta", "Carrera 27", "35A-50", 4.1401, -73.6301, "street_address")));
        var r = servicio.buscarDetallado("Cra27 #35a 50", null);
        assertEquals(EstadoBusqueda.OK, r.estado());
        assertEquals("EXACTA", r.lugares().get(0).coincidencia());
        assertEquals("ChIJexactaPlaca001", r.lugares().get(0).googleId());
        assertTrue(r.lugares().stream().noneMatch(l -> "REFERENCIA".equals(l.coincidencia())), "con una exacta no se agrega la referencia de la vía");
        assertEquals(1, llamadasTexto.get(), "una sola llamada a Google");
    }

    @Test void formatosDelMismoNumeroSeBuscanComoLaMismaNomenclatura() {
        for (String q : List.of("carrera 27 #35A50", "Cra 27 35A50", "Carrera 27 número 35A 50", "Cra. 27 No. 35A-50", "Cra27 #35a 50", "Cra 27 35A 50")) {
            var n = Nomenclatura.de(q, area).orElseThrow(() -> new AssertionError(q));
            assertEquals("Carrera 27 # 35A-50", n.texto(), q);
        }
    }

    // ------------------------------------------------------------------ posible coincidencia
    @Test void unaCifraDeMasOfreceLaPlacaParecidaSinAplicarlaSola() {
        primera.set(lugares(lugar("ChIJparecida00001", "Cra. 27 #35A-50, Villavicencio, Meta", "Carrera 27", "35A-50", 4.1401, -73.6301, "street_address")));
        var r = servicio.buscarDetallado("Carrera 27 935A 50", null);
        assertEquals(1, r.lugares().size());
        var l = r.lugares().get(0);
        assertEquals("POSIBLE", l.coincidencia());
        assertTrue(l.motivo().contains("#35A-50"), l.motivo());
        assertEquals("Carrera 27 # 35A-50", l.nomenclatura(), "se muestra la placa que de verdad devolvió Google");
    }

    @Test void siExisteLaExactaParaLaPlacaEscritaSeRespetaYNoSeOfreceLaParecida() {
        primera.set(lugares(lugar("ChIJexacta935A001", "Cra. 27 #935A-50, Villavicencio, Meta", "Carrera 27", "935A-50", 4.1500, -73.6400, "street_address"),
                lugar("ChIJparecida00001", "Cra. 27 #35A-50, Villavicencio, Meta", "Carrera 27", "35A-50", 4.1401, -73.6301, "street_address")));
        var r = servicio.buscarDetallado("Carrera 27 #935A-50", null);
        assertEquals(1, r.lugares().size());
        assertEquals("EXACTA", r.lugares().get(0).coincidencia());
        assertEquals("ChIJexacta935A001", r.lugares().get(0).googleId());
    }

    @Test void otraCalleOtroSentidoOOtraPlacaLejanaNoSeOfreceComoParecida() {
        primera.set(lugares(lugar("ChIJotraCalle00001", "Cl. 27 #35A-50, Villavicencio, Meta", "Calle 27", "35A-50", 4.14, -73.63, "street_address"),
                lugar("ChIJotroSentido001", "Cra. 27 Sur #35A-50, Villavicencio, Meta", "Carrera 27 Sur", "35A-50", 4.13, -73.62, "street_address"),
                lugar("ChIJplacaLejana001", "Cra. 27 #12-80, Villavicencio, Meta", "Carrera 27", "12-80", 4.12, -73.61, "street_address")));
        segunda.set(lugares());
        var r = servicio.buscarDetallado("Carrera 27 #35A-50", null);
        assertTrue(r.lugares().isEmpty(), "ninguna se ofrece: " + r.lugares());
    }

    @Test void dosOpcionesRazonablesSeMuestranAmbas() {
        primera.set(lugares(lugar("ChIJparecidaA00001", "Cra. 27 #35A-50, Villavicencio, Meta", "Carrera 27", "35A-50", 4.1401, -73.6301, "street_address"),
                lugar("ChIJparecidaB00001", "Cra. 27 #935-50, Villavicencio, Meta", "Carrera 27", "935-50", 4.1450, -73.6350, "street_address")));
        var r = servicio.buscarDetallado("Carrera 27 #935A-50", null);
        assertEquals(2, r.lugares().size());
        assertTrue(r.lugares().stream().allMatch(l -> "POSIBLE".equals(l.coincidencia())));
    }

    // ------------------------------------------------------------------ referencia de la vía
    @Test void soloLaViaSeOfreceComoReferenciaYSeDiceQueFaltaElNumero() {
        primera.set(lugares(lugar("ChIJviaCarrera27XX", "Cra. 27, Villavicencio, Meta", "Carrera 27", null, 4.14, -73.63, "route")));
        var r = servicio.buscarDetallado("Carrera 27 #99-99", null);
        assertEquals(1, r.lugares().size());
        assertEquals("REFERENCIA", r.lugares().get(0).coincidencia());
        assertTrue(String.join(" ", r.avisos()).contains("no ese número"), r.avisos().toString());
        assertEquals(1, llamadasTexto.get(), "la referencia salió de la primera respuesta: sin segunda llamada");
    }



    private static String prediccion(String id, String texto) {
        return "{\"placePrediction\":{\"placeId\":\"" + id + "\",\"text\":{\"text\":\"" + texto + "\"}}}";
    }

    // ------------------------------------------------------------------ corrector (Autocomplete)
    @Test void sinCandidatosElCorrectorOfreceLaPlacaCercanaDeLaMismaViaParaRevisar() {
        primera.set(lugares());
        autocompletar.set("{\"suggestions\":[" + prediccion("ChIJcercana0000001", "Cra. 27 #35A-58, Villavicencio, Meta") + "," + prediccion("ChIJotraVia00000001", "Calle 27 #35A-50, Villavicencio, Meta") + "]}");
        detalle.set(lugar("ChIJcercana0000001", "Cra. 27 #35A-58, Villavicencio, Meta", "Carrera 27", "35A-58", 4.1405, -73.6305, "street_address"));
        var r = servicio.buscarDetallado("Carrera 27 #35A-50", null);
        assertEquals(1, r.lugares().size(), "solo la misma vía: " + r.lugares());
        assertEquals("POSIBLE", r.lugares().get(0).coincidencia());
        assertEquals("ChIJcercana0000001", r.lugares().get(0).googleId());
        assertEquals(1, llamadasTexto.get(), "una búsqueda por texto + el corrector");
        assertEquals(1, rutas.stream().filter(x -> x.endsWith(":autocomplete")).count());
        assertEquals(1, rutas.stream().filter(x -> x.contains("/v1/places/")).count(), "un detalle, solo de la misma vía");
    }

    @Test void sinPlacaCercanaElCorrectorOfreceLaViaComoReferencia() {
        primera.set(lugares());
        autocompletar.set("{\"suggestions\":[" + prediccion("ChIJviaCarrera27XX", "Cra. 27, Villavicencio, Meta") + "]}");
        detalle.set(lugar("ChIJviaCarrera27XX", "Cra. 27, Villavicencio, Meta", "Carrera 27", null, 4.14, -73.63, "route"));
        var r = servicio.buscarDetallado("Carrera 27 #99-99", null);
        assertEquals("REFERENCIA", r.lugares().get(0).coincidencia());
    }

    @Test void siElCorrectorTrajoLaExactaSeMarcaExactaPeroSeRevisaSuPin() {
        primera.set(lugares());
        autocompletar.set("{\"suggestions\":[" + prediccion("ChIJexactaAuto0001", "Cra. 27 #35A-50, Villavicencio, Meta") + "]}");
        detalle.set(lugar("ChIJexactaAuto0001", "Cra. 27 #35A-50, Villavicencio, Meta", "Carrera 27", "35A-50", 4.1401, -73.6301, "street_address"));
        var r = servicio.buscarDetallado("Carrera 27 #35A-50", null);
        assertEquals("EXACTA", r.lugares().get(0).coincidencia());
    }

    @Test void sinNadaUtilNoSeInventaUnaDireccionNiUnPinYElCorrectorEsUnSoloIntento() {
        primera.set(lugares());
        autocompletar.set("{\"suggestions\":[" + prediccion("ChIJotraVia00000001", "Calle 30 #12-80, Villavicencio, Meta") + "]}");
        var r = servicio.buscarDetallado("Carrera 27 #99-99", null);
        assertTrue(r.lugares().isEmpty());
        assertEquals(1, rutas.stream().filter(x -> x.endsWith(":autocomplete")).count());
        assertEquals(0, rutas.stream().filter(x -> x.contains("/v1/places/")).count(), "ninguna predicción de la misma vía: no se pide ningún detalle");
    }

    @Test void siLaPrimeraConsultaFallaNoSeEncadenanReintentos() {
        servidor.removeContext("/");
        servidor.createContext("/", ex -> { llamadasTexto.incrementAndGet(); ex.sendResponseHeaders(503, -1); ex.close(); });
        var r = servicio.buscarDetallado("Carrera 27 #99-99", null);
        assertTrue(r.lugares().isEmpty());
        assertEquals(1, llamadasTexto.get(), "un fallo del proveedor no dispara una segunda consulta");
        assertTrue(rutas.stream().noneMatch(x -> x.endsWith(":autocomplete")), "ni el corrector");
    }

    @Test void unNombreOSitioNoSeClasificaNiSeHaceReintento() {
        primera.set(lugares(lugar("ChIJparqueSitio0001", "Parque Los Fundadores, Villavicencio, Meta", null, null, 4.1420, -73.6266, "park")));
        var r = servicio.buscarDetallado("Parque Los Fundadores", null);
        assertEquals(1, r.lugares().size());
        assertNull(r.lugares().get(0).coincidencia());
        assertEquals(1, llamadasTexto.get());
    }

    // ------------------------------------------------------------------ nomenclatura
    @Test void placaParecidaExigeMismaViaYUnSoloCambioConEvidencia() {
        var pedida = Nomenclatura.de("Carrera 27 #935A-50", area).orElseThrow();
        assertTrue(pedida.placaParecida(Nomenclatura.de("Carrera 27 #35A-50", area).orElseThrow()));
        assertFalse(pedida.placaParecida(pedida), "idéntica = exacta, no parecida");
        assertFalse(pedida.placaParecida(Nomenclatura.de("Calle 27 #35A-50", area).orElseThrow()), "otra clase de vía");
        assertFalse(pedida.placaParecida(Nomenclatura.de("Carrera 27 Sur #35A-50", area).orElseThrow()), "otro sentido");
        assertFalse(pedida.placaParecida(Nomenclatura.de("Carrera 27 #35A-80", area).orElseThrow()), "dos cambios");
        assertFalse(Nomenclatura.de("Carrera 27 #5-50", area).orElseThrow().placaParecida(Nomenclatura.de("Carrera 27 #6-50", area).orElseThrow()), "un cambio en un fragmento de una cifra no es evidencia");
        assertEquals("Calle 15 Bis Sur # 20A-10B", Nomenclatura.de("Calle 15 Bis Sur #20A-10B", area).orElseThrow().texto(), "conserva Bis, sentido y letras");
    }
}
