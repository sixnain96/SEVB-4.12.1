package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
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
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;

/**
 * «carrera 27 número 35A 50» → Google recibe «Carrera 27 # 35A-50», y lo que Google devuelve se compara POR COMPONENTES (vía, Bis, sentido y los dos fragmentos de la placa), no por cifras sueltas.
 * Google SIMULADO (servidor local): se comprueba qué consulta salió, qué resultado se confirmó y qué se dijo; no la calidad real de Google ni que esos predios existan.
 */
class BusquedaNomenclaturaTest {
    private final CityArea area = new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45);
    private HttpServer servidor;
    private final List<String> cuerpos = new ArrayList<>();
    private final AtomicReference<String> autocompletar = new AtomicReference<>("{\"suggestions\":[]}");
    private final AtomicReference<String> texto = new AtomicReference<>("{\"places\":[]}");
    private int estado = 200;
    private LugarService servicio;

    @BeforeEach void arrancar() throws Exception {
        servidor = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        servidor.createContext("/", ex -> {
            cuerpos.add(new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            String p = ex.getRequestURI().getPath();
            byte[] b = (p.endsWith(":autocomplete") ? autocompletar.get() : texto.get()).getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(estado, b.length);
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

    private static String comp(String ruta, String numero) {
        return "[{\"longText\":\"" + ruta + "\",\"types\":[\"route\"]},{\"longText\":\"" + numero + "\",\"types\":[\"street_number\"]},{\"longText\":\"Villavicencio\",\"types\":[\"locality\"]}]";
    }

    /** Un lugar de Text Search con dirección formateada y, si se pide, componentes estructurados. */
    private static String lugar(String id, String formateada, String componentes, double lat, double lng, String... tipos) {
        return "{\"id\":\"" + id + "\",\"formattedAddress\":\"" + formateada + "\",\"displayName\":{\"text\":\"" + formateada.split(",")[0] + "\"},"
                + (componentes == null ? "" : "\"addressComponents\":" + componentes + ",") + "\"location\":{\"latitude\":" + lat + ",\"longitude\":" + lng + "},\"types\":["
                + String.join(",", java.util.Arrays.stream(tipos).map(t -> "\"" + t + "\"").toList()) + "]}";
    }

    private static String prediccion(String id, String principal, String secundario) {
        return "{\"placePrediction\":{\"placeId\":\"" + id + "\",\"text\":{\"text\":\"" + principal + ", " + secundario + "\"},\"structuredFormat\":{\"mainText\":{\"text\":\"" + principal + "\"},\"secondaryText\":{\"text\":\"" + secundario + "\"}}}}";
    }

    private List<String> principales(String consulta) {
        return servicio.sugerirDetallado(consulta, "sesion-abc-123456").sugerencias().stream().map(s -> s.principal()).toList();
    }

    private static String sugerencias(String... p) { return "{\"suggestions\":[" + String.join(",", p) + "]}"; }

    // ---------------------------------------------------------------- qué sale hacia Google
    @Test void alAutocompletadoYALaBusquedaSaleLaConsultaNormalizadaConElNumeral() {
        for (String escrito : List.of("carrera 27 número 35A 50", "Cra. 27 No. 35A-50", "Kra 27 #35A - 50", "Cra 27 35A 50")) {
            cuerpos.clear();
            servicio.sugerirDetallado(escrito, "sesion-abc-123456");
            servicio.buscarDetallado(escrito, "", "sesion-abc-123456");
            assertTrue(cuerpos.get(0).contains("\"input\":\"Carrera 27 # 35A-50\""), "autocompletar: " + cuerpos.get(0));
            assertTrue(cuerpos.get(1).contains("\"textQuery\":\"Carrera 27 # 35A-50, Villavicencio, Meta, Colombia\""), "búsqueda: " + cuerpos.get(1));
        }
    }

    // ---------------------------------------------------------------- qué se confirma
    @Test void lamismaPlacaEscritaDeOtraFormaSeConfirmaConComponentesOSinEllos() {
        texto.set("{\"places\":[" + lugar("ChIJplaca00000001", "Cra. 27 #35A - 50, Villavicencio, Meta", comp("Carrera 27", "35A-50"), 4.1450, -73.6300, "street_address") + "]}");
        var r = servicio.buscarDetallado("carrera 27 número 35A 50", "", "sesion-abc-123456");
        assertEquals(1, r.lugares().size(), r.avisos().toString());
        assertEquals("Carrera 27 # 35A-50", r.lugares().get(0).nomenclatura(), "armada con los componentes de Google");
        texto.set("{\"places\":[" + lugar("ChIJplaca00000001", "Cra. 27 #35A-50, Villavicencio, Meta", null, 4.1450, -73.6300, "street_address") + "]}");
        assertEquals(1, servicio.buscarDetallado("Cra 27 35A 50", "", "sesion-abc-123456").lugares().size(), "sin componentes: se usa la dirección devuelta con las mismas reglas");
    }

    @Test void otraPlacaDevueltaPrimeroNuncaSeConfirmaComoLaPedida() {
        texto.set("{\"places\":[" + lugar("ChIJotra000000001", "Carrera 27 #35-50, Villavicencio, Meta", comp("Carrera 27", "35-50"), 4.1451, -73.6301, "street_address") + ","
                + lugar("ChIJotra000000002", "Carrera 27 #35A-51, Villavicencio, Meta", comp("Carrera 27", "35A-51"), 4.1452, -73.6302, "street_address") + ","
                + lugar("ChIJotra000000003", "Calle 27 #35A-50, Villavicencio, Meta", comp("Calle 27", "35A-50"), 4.1453, -73.6303, "street_address") + ","
                + lugar("ChIJotra000000004", "Carrera 27 Sur #35A-50, Villavicencio, Meta", comp("Carrera 27 Sur", "35A-50"), 4.1454, -73.6304, "street_address") + ","
                + lugar("ChIJexacta0000005", "Carrera 27 #35A-50, Villavicencio, Meta", comp("Carrera 27", "35A-50"), 4.1450, -73.6300, "street_address") + "]}");
        var r = servicio.buscarDetallado("carrera 27 número 35A 50", "", "sesion-abc-123456");
        assertEquals(1, r.lugares().size(), "solo la placa exacta: " + r.lugares());
        assertEquals("ChIJexacta0000005", r.lugares().get(0).googleId(), "no se tomó el primero que llegó");
    }

    @Test void siSoloEncuentraLaViaOElBarrioLoDiceYOfreceElMapa() {
        texto.set("{\"places\":[" + lugar("ChIJvia000000001", "Carrera 27, Villavicencio, Meta", "[{\"longText\":\"Carrera 27\",\"types\":[\"route\"]}]", 4.1450, -73.6300, "route") + ","
                + lugar("ChIJbarrio0000002", "Barrio Los Maracos, Villavicencio, Meta", null, 4.1451, -73.6301, "neighborhood") + "]}");
        var r = servicio.buscarDetallado("Carrera 27 # 35A-50", "", "sesion-abc-123456");
        assertTrue(r.lugares().stream().allMatch(l -> "REFERENCIA".equals(l.coincidencia())), "ninguno es esa puerta: solo la vía como REFERENCIA: " + r.lugares());
        assertEquals(1, r.lugares().size(), "el barrio que no escribió la persona no se ofrece");
        assertTrue(r.avisos().stream().anyMatch(a -> a.contains("no ese número") && a.contains("mapa")), r.avisos().toString());
        texto.set("{\"places\":[" + lugar("ChIJvia000000001", "Calle 30, Villavicencio, Meta", null, 4.1450, -73.6300, "route") + "]}");
        var calle = servicio.buscarDetallado("Calle 30 # 38-10", "", "sesion-abc-123456");
        assertTrue(calle.avisos().stream().anyMatch(a -> a.contains("Ubicamos la calle")), calle.avisos().toString());
    }

    @Test void siFaltaLaPlacaSeDiceQueDatoEscribir() {
        var r = servicio.buscarDetallado("Carrera 27 35A", "", "sesion-abc-123456");
        assertTrue(r.lugares().isEmpty());
        assertTrue(r.avisos().stream().anyMatch(a -> a.contains("Falta un dato de la placa") && a.contains("Carrera 27 # 35A-50")), r.avisos().toString());
    }

    @Test void fueraDelAreaCeroCoincidenciasYErrorTienenCadaUnoSuEstado() {
        texto.set("{\"places\":[" + lugar("ChIJbogota0000001", "Carrera 27 #35A-50, Bogotá, D.C.", comp("Carrera 27", "35A-50"), 4.7110, -74.0721, "street_address") + "]}");
        assertEquals(EstadoBusqueda.FUERA_DE_CIUDAD, servicio.buscarDetallado("Carrera 27 # 35A-50", "", "sesion-abc-123456").estado());
        texto.set("{\"places\":[]}");
        assertEquals(EstadoBusqueda.SIN_COINCIDENCIAS, servicio.buscarDetallado("Carrera 27 # 35A-50", "", "sesion-abc-123456").estado());
        estado = 503;
        var caido = servicio.buscarDetallado("Carrera 27 # 35A-50", "", "sesion-abc-123456");
        assertTrue(caido.lugares().isEmpty());
        assertNotEquals(EstadoBusqueda.SIN_COINCIDENCIAS, caido.estado());
    }

    @Test void siLaPersonaNombraOtraCiudadNoSeLeCambiaPorVillavicencio() {
        cuerpos.clear();
        servicio.buscarDetallado("Carrera 27 numero 35A 50 Bogotá", "", "sesion-abc-123456");
        assertFalse(cuerpos.get(0).contains("Villavicencio"), cuerpos.get(0));
        assertTrue(cuerpos.get(0).contains("Carrera 27 # 35A-50 Bogotá"), cuerpos.get(0));
    }

    @Test void seEnviaUnaSolaConsultaPorBusquedaExplicitaSinSegundoIntento() {
        texto.set("{\"places\":[]}");
        cuerpos.clear();
        servicio.buscarDetallado("Carrera 27 # 35A-50", "", "sesion-abc-123456");
        assertEquals(2, cuerpos.size(), "la primera con la forma canónica y, como mucho, UN intento adicional (el corrector de Autocomplete)");
        assertTrue(cuerpos.get(0).contains("Carrera 27 # 35A-50"), "la primera lleva los números intactos: " + cuerpos.get(0));
        assertTrue(cuerpos.get(1).contains("\"input\":\"Carrera 27 # 35A-50\""), "el intento adicional es el corrector (Autocomplete) con los números intactos: " + cuerpos.get(1));
    }

    // ---------------------------------------------------------------- consultas parciales y opciones
    @Test void lasConsultasParcialesNoDescartanOpcionesUtiles() {
        autocompletar.set(sugerencias(prediccion("ChIJ0000000a01", "Carrera 27 #35A-50", "Villavicencio, Meta"), prediccion("ChIJ0000000a02", "Carrera 27 #35-50", "Villavicencio, Meta"),
                prediccion("ChIJ0000000a03", "Carrera 27 #35AB-10", "Villavicencio, Meta"), prediccion("ChIJ0000000a04", "Carrera 28 #35A-50", "Villavicencio, Meta"), prediccion("ChIJ0000000a05", "Calle 27 #35A-50", "Villavicencio, Meta")));
        assertEquals(List.of("Carrera 27 #35A-50", "Carrera 27 #35-50", "Carrera 27 #35AB-10"), principales("Cra 27"), "«Cra 27»: la vía 27 con cualquier placa");
        assertEquals(List.of("Carrera 27 #35A-50", "Carrera 27 #35-50", "Carrera 27 #35AB-10"), principales("Cra 27 número"), "«número» cierra la vía");
        assertEquals(List.of("Carrera 27 #35A-50", "Carrera 27 #35AB-10"), principales("Cra 27 número 35A"), "«35A» se sigue escribiendo: prefijo, y 35 no lo es");
        assertEquals(List.of("Carrera 27 #35A-50"), principales("carrera 27 número 35A 50"), "placa completa: solo esa");
    }

    @Test void dosOpcionesParecidasConIdentificadoresDistintosSeConservanDistinguibles() {
        autocompletar.set(sugerencias(prediccion("ChIJparecida00001", "Carrera 27 #35A-50", "Barrio Barzal, Villavicencio"), prediccion("ChIJparecida00002", "Carrera 27 #35A-50", "Barrio Kirpas, Villavicencio")));
        var r = servicio.sugerirDetallado("Cra 27 35A 50", "sesion-abc-123456").sugerencias();
        assertEquals(2, r.size());
        assertNotEquals(r.get(0).secundario(), r.get(1).secundario(), "se distinguen por su referencia");
        assertNotEquals(r.get(0).magicKey(), r.get(1).magicKey());
    }

    @Test void nombresDeEstablecimientosNoSeTratanComoDirecciones() {
        autocompletar.set(sugerencias(prediccion("ChIJviva000000001", "Centro Comercial Viva", "Villavicencio, Meta")));
        cuerpos.clear();
        assertEquals(List.of("Centro Comercial Viva"), principales("centro comercial viva"));
        assertTrue(cuerpos.get(0).contains("\"input\":\"centro comercial viva\""), "tal cual lo escribió: " + cuerpos.get(0));
        cuerpos.clear();
        principales("Clínica Número 5");
        assertTrue(cuerpos.get(0).contains("\"input\":\"Clínica Número 5\""), cuerpos.get(0));
    }
}
