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
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;

/**
 * Pertinencia de las sugerencias y de la búsqueda de direcciones del pasajero (Villavicencio), con un Google SIMULADO (servidor local): lo que se prueba es la lógica de SEVB
 * (qué consulta sale, qué opciones pasan el filtro y qué punto se confirma), NO la calidad real de los resultados de Google.
 * Cubre las cinco clases de fallo investigadas: (1) la interfaz no muestra lo que llegó (ver busqueda_e2e.py), (2) el backend descarta candidatos válidos al escribir,
 * (3) Google sin candidatos o caído, (4) un lugar parecido que es otra vía/número/sede, (5) tocar una opción y recibir otro lugar.
 */
class BusquedaPertinenciaTest {
    private final CityArea area = new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45);
    private HttpServer servidor;
    private final List<String> cuerpos = new ArrayList<>();
    private final List<String> rutas = new ArrayList<>();
    private final AtomicReference<String> autocompletar = new AtomicReference<>("{\"suggestions\":[]}");
    private final AtomicReference<String> texto = new AtomicReference<>("{\"places\":[]}");
    private final AtomicReference<String> detalle = new AtomicReference<>("{}");
    private int estado = 200;
    private LugarService servicio;
    private GoogleDireccionesService google;

    @BeforeEach void arrancar() throws Exception {
        servidor = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        servidor.createContext("/", ex -> {
            rutas.add(ex.getRequestMethod() + " " + ex.getRequestURI().getPath());
            cuerpos.add(new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            String p = ex.getRequestURI().getPath();
            String json = p.endsWith(":autocomplete") ? autocompletar.get() : p.endsWith(":searchText") ? texto.get() : detalle.get();
            byte[] b = json.getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(estado, b.length);
            ex.getResponseBody().write(b);
            ex.close();
        });
        servidor.start();
        google = new GoogleDireccionesService("clave-de-prueba", "http://127.0.0.1:" + servidor.getAddress().getPort(), JsonMapper.builder().build(), area);
        servicio = new LugarService(mock(LugarRepository.class), mock(GeocodingService.class), area, mock(DireccionesHibridasService.class), mock(DireccionesLocalesService.class));
        servicio.usarGoogle(google);
        servicio.soloGoogle(true);
    }

    @AfterEach void parar() { servidor.stop(0); }

    private static String prediccion(String id, String principal, String secundario) {
        return "{\"placePrediction\":{\"placeId\":\"" + id + "\",\"text\":{\"text\":\"" + principal + ", " + secundario + "\"},\"structuredFormat\":{\"mainText\":{\"text\":\"" + principal + "\"},\"secondaryText\":{\"text\":\"" + secundario + "\"}}}}";
    }

    private static String sugerencias(String... predicciones) { return "{\"suggestions\":[" + String.join(",", predicciones) + "]}"; }

    private static String lugar(String id, String direccion, double lat, double lng, String... tipos) {
        return "{\"id\":\"" + id + "\",\"formattedAddress\":\"" + direccion + "\",\"displayName\":{\"text\":\"" + direccion.split(",")[0] + "\"},\"location\":{\"latitude\":" + lat + ",\"longitude\":" + lng + "},\"types\":["
                + String.join(",", java.util.Arrays.stream(tipos).map(t -> "\"" + t + "\"").toList()) + "]}";
    }

    private List<String> principales(String consulta) {
        return servicio.sugerirDetallado(consulta, "sesion-abc-123456").sugerencias().stream().map(s -> s.principal()).toList();
    }

    // ------------------------------------------------------------------ clase 2: el backend descartaba candidatos válidos mientras se escribe
    @Test void escribirUnNumeroIncompletoDejaPasarLasViasQueLoCompletan() {
        autocompletar.set(sugerencias(prediccion("ChIJ0000000030", "Calle 30", "Villavicencio, Meta"), prediccion("ChIJ0000000003", "Calle 3", "Villavicencio, Meta"), prediccion("ChIJ0000000031", "Calle 31", "Villavicencio, Meta"), prediccion("ChIJ0000000040", "Calle 40", "Villavicencio, Meta")));
        var visto = principales("Calle 3");
        assertTrue(visto.containsAll(List.of("Calle 3", "Calle 30", "Calle 31")), "«Calle 3» es prefijo de 30 y 31 (se está escribiendo): " + visto);
        assertFalse(visto.contains("Calle 40"), "pero 40 no empieza por 3: " + visto);
        assertEquals("Calle 3", visto.get(0), "la coincidencia exacta va primero");
    }

    @Test void alCompletarElNumeroLasOpcionesAnterioresDejanDeSerValidas() {
        autocompletar.set(sugerencias(prediccion("ChIJ0000000030", "Calle 30", "Villavicencio, Meta"), prediccion("ChIJ0000000003", "Calle 3", "Villavicencio, Meta"), prediccion("ChIJ000000030A", "Calle 30A", "Villavicencio, Meta")));
        var visto = principales("Calle 30 ");      // el espacio final cierra el número: ya no es un prefijo
        assertEquals(List.of("Calle 30"), visto, "«30» completo no es «3» ni «30A»: " + visto);
    }

    @Test void laPlacaParcialFuncionaComoPrefijoSoloEnElUltimoFragmento() {
        autocompletar.set(sugerencias(prediccion("ChIJ00000001A", "Carrera 22 #38-10", "Villavicencio, Meta"), prediccion("ChIJ00000001B", "Carrera 22 #38-12", "Villavicencio, Meta"),
                prediccion("ChIJ00000001C", "Carrera 22 #39-10", "Villavicencio, Meta"), prediccion("ChIJ00000001D", "Carrera 22 #3-10", "Villavicencio, Meta")));
        assertEquals(List.of("Carrera 22 #38-10", "Carrera 22 #38-12"), principales("Carrera 22 #38-1").stream().filter(p -> p.contains("38")).toList());
        var tres = principales("Carrera 22 #3");
        assertTrue(tres.containsAll(List.of("Carrera 22 #3-10", "Carrera 22 #38-10", "Carrera 22 #39-10")), "«3» se está escribiendo: " + tres);
        var cerrado = principales("Carrera 22 #38-10");
        assertEquals(List.of("Carrera 22 #38-10"), cerrado, "con la placa completa solo queda esa: " + cerrado);
    }

    @Test void viaTipoLetraYSentidoNoSonEquivalentes() {
        autocompletar.set(sugerencias(prediccion("ChIJ0000000a01", "Calle 30", "Villavicencio, Meta"), prediccion("ChIJ0000000a02", "Carrera 30", "Villavicencio, Meta"), prediccion("ChIJ0000000a03", "Calle 30A", "Villavicencio, Meta"),
                prediccion("ChIJ0000000a04", "Calle 30 Sur", "Villavicencio, Meta"), prediccion("ChIJ0000000a05", "Calle 30 Norte", "Villavicencio, Meta")));
        assertFalse(principales("Calle 30 ").contains("Carrera 30"), "Calle ≠ Carrera");
        var sur = principales("Calle 30 Sur");
        assertEquals(List.of("Calle 30 Sur"), sur, "Sur ≠ Norte ni sin sentido: " + sur);
    }

    @Test void lasAbreviaturasLasTildesYLosEspaciosPegadosSeEntiendenSinRomperNombresComerciales() {
        for (String escrito : List.of("Cra. 22 #38-10", "Kra 22 38 10", "cra22 #38-10", "Carrera 22 No. 38-10", "CRA 22 # 38 - 10")) {
            cuerpos.clear();
            autocompletar.set(sugerencias(prediccion("ChIJ00000001A", "Carrera 22 #38-10", "Villavicencio, Meta")));
            assertFalse(principales(escrito).isEmpty(), "«" + escrito + "» debe encontrar la Carrera 22 #38-10");
            String enviado = cuerpos.get(cuerpos.size() - 1);
            assertTrue(enviado.contains("\"input\":\"Carrera 22"), "se envía normalizado: " + enviado);
        }
        // un nombre comercial NO se reescribe: «TV Center» no es «Transversal Center»
        cuerpos.clear();
        autocompletar.set(sugerencias(prediccion("ChIJ0000000tv1", "TV Center", "Villavicencio, Meta")));
        principales("TV Center");
        assertTrue(cuerpos.get(cuerpos.size() - 1).contains("\"input\":\"TV Center\""), "nombre comercial intacto: " + cuerpos.get(cuerpos.size() - 1));
    }

    @Test void dosSedesConElMismoNombreYDistintoIdentificadorSeConservanAmbas() {
        autocompletar.set(sugerencias(prediccion("ChIJsedeCentro01", "Clínica Meta", "Calle 38 #31-10, Villavicencio"), prediccion("ChIJsedeNorte001", "Clínica Meta", "Carrera 40 #5-20, Villavicencio")));
        var r = servicio.sugerirDetallado("clinica meta", "sesion-abc-123456").sugerencias();
        assertEquals(2, r.size(), "dos sedes");
        assertNotEquals(r.get(0).magicKey(), r.get(1).magicKey());
        assertNotEquals(r.get(0).secundario(), r.get(1).secundario(), "se distinguen por su referencia");
    }

    @Test void unaPalabraGenericaSolaNoDemuestraQueLaOpcionEsElLugarPedido() {
        autocompletar.set(sugerencias(prediccion("ChIJ0000gen001", "Villavicencio", "Meta, Colombia")));
        assertTrue(principales("clínica villavicencio").isEmpty(), "solo la ciudad no es la clínica");
    }

    // ------------------------------------------------------------------ clase 3: Google sin candidatos o caído
    @Test void sinCandidatosOCaidoElEstadoEsDistintoYNoSeInventaNada() {
        assertEquals(EstadoBusqueda.SIN_COINCIDENCIAS, servicio.sugerirDetallado("lugar inexistente xyz", "sesion-abc-123456").estado());
        estado = 503;
        var caido = servicio.sugerirDetallado("lugar inexistente xyz", "sesion-abc-123456");
        assertTrue(caido.sugerencias().isEmpty());
        assertNotEquals(EstadoBusqueda.SIN_COINCIDENCIAS, caido.estado(), "caído no es «sin coincidencias»: " + caido.estado());
    }

    // ------------------------------------------------------------------ clase 4: un lugar parecido que es otra cosa (búsqueda explícita)
    @Test void laBusquedaExplicitaNoConfirmaOtraPuertaNiLaViaNiElBarrioComoEsaDireccion() {
        texto.set("{\"places\":[" + lugar("ChIJvia000000001", "Carrera 22, Villavicencio, Meta", 4.1450, -73.6300, "route") + ","
                + lugar("ChIJotro00000002", "Carrera 22 #38-11, Villavicencio, Meta", 4.1451, -73.6301, "street_address") + ","
                + lugar("ChIJbarrio0000003", "Barrio Los Maracos, Villavicencio, Meta", 4.1452, -73.6302, "neighborhood") + ","
                + lugar("ChIJcentro0000004", "Villavicencio, Meta, Colombia", 4.1420, -73.6266, "locality") + "]}");
        var r = servicio.buscarDetallado("Carrera 22 #38-10", "", "sesion-abc-123456");
        assertTrue(r.lugares().isEmpty(), "ninguna es esa puerta: " + r.lugares());
        assertTrue(r.avisos().stream().anyMatch(a -> a.contains("Encontramos la carrera, pero no ese número")), "se explica: " + r.avisos());
    }

    @Test void laBusquedaExplicitaDistingueBisYLetras() {
        texto.set("{\"places\":[" + lugar("ChIJbis0000000001", "Calle 30 Bis #38-10, Villavicencio, Meta", 4.1450, -73.6300, "street_address") + ","
                + lugar("ChIJletra000000002", "Calle 30A #38-10, Villavicencio, Meta", 4.1451, -73.6301, "street_address") + ","
                + lugar("ChIJexacta00000003", "Calle 30 #38-10, Villavicencio, Meta", 4.1452, -73.6302, "street_address") + "]}");
        var r = servicio.buscarDetallado("Calle 30 #38-10", "", "sesion-abc-123456");
        assertEquals(1, r.lugares().size(), r.lugares().toString());
        assertTrue(r.lugares().get(0).direccion().startsWith("Calle 30 #38-10"));
    }

    @Test void unaPlacaCompletaCoincideConSuFormaAbreviada() {
        texto.set("{\"places\":[" + lugar("ChIJabrev0000000001", "Cra. 22 #38-10, Villavicencio, Meta", 4.1450, -73.6300, "street_address") + "]}");
        var r = servicio.buscarDetallado("Carrera 22 #38-10", "", "sesion-abc-123456");
        assertEquals(1, r.lugares().size(), "«Cra. 22 #38-10» ES «Carrera 22 #38-10»");
    }

    @Test void laConsultaExplicitaAgregaLaCiudadSoloSiHaceFaltaYNuncaCambiaOtraCiudad() {
        texto.set("{\"places\":[]}");
        cuerpos.clear(); servicio.buscarDetallado("Carrera 22 #38-10", "", "sesion-abc-123456");
        assertTrue(cuerpos.get(cuerpos.size() - 1).contains("Villavicencio, Meta"), "se le da el contexto de la ciudad: " + cuerpos.get(cuerpos.size() - 1));
        cuerpos.clear(); servicio.buscarDetallado("Carrera 22 #38-10 Bogotá", "", "sesion-abc-123456");
        assertFalse(cuerpos.get(cuerpos.size() - 1).contains("Villavicencio"), "«Bogotá» no se vuelve un sitio local: " + cuerpos.get(cuerpos.size() - 1));
    }

    // ------------------------------------------------------------------ clase 5: tocar una opción y recibir otra
    @Test void siGoogleDevuelveOtraSedeParaElIdentificadorElegidoNoSeAcepta() {
        detalle.set(lugar("ChIJsedeOTRA000001", "Carrera 40 #5-20, Villavicencio, Meta", 4.15, -73.62, "establishment"));
        var r = servicio.buscarDetallado("Clínica Meta", "g:ChIJsedeCentro01", "sesion-abc-123456");
        assertTrue(r.eleccionFallida(), "pidió la sede centro y llegó otra");
        assertTrue(r.lugares().isEmpty());
        assertEquals(EstadoBusqueda.RESPUESTA_INVALIDA, r.estado());
    }

    @Test void siFaltaLaIdentidadEnElDetalleTampocoSeAcepta() {
        detalle.set("{\"formattedAddress\":\"Carrera 40 #5-20, Villavicencio\",\"location\":{\"latitude\":4.15,\"longitude\":-73.62},\"types\":[\"establishment\"]}");
        var r = servicio.buscarDetallado("Clínica Meta", "g:ChIJsedeCentro01", "sesion-abc-123456");
        assertTrue(r.eleccionFallida() && r.lugares().isEmpty());
    }

    @Test void elLugarResueltoLlevaElIdentificadorDeGoogleParaQueElNavegadorLoComprueba() {
        detalle.set(lugar("ChIJsedeCentro01", "Calle 38 #31-10, Villavicencio, Meta", 4.1450, -73.6300, "establishment"));
        var r = servicio.buscarDetallado("Clínica Meta", "g:ChIJsedeCentro01", "sesion-abc-123456");
        assertFalse(r.eleccionFallida());
        LugarResponse l = r.lugares().get(0);
        assertEquals("ChIJsedeCentro01", l.googleId());
        assertNull(l.id(), "el identificador de Google y el interno de SEVB no se mezclan");
    }

    @Test void fueraDelAreaOCoordenadasInvalidasConservanLaConsultaYNoSeSustituyen() {
        detalle.set(lugar("ChIJsedeCentro01", "Bogotá", 4.7110, -74.0721, "establishment"));
        var fuera = servicio.buscarDetallado("Clínica Meta", "g:ChIJsedeCentro01", "sesion-abc-123456");
        assertEquals(EstadoBusqueda.FUERA_DE_CIUDAD, fuera.estado());
        assertTrue(fuera.eleccionFallida());
        detalle.set("{\"id\":\"ChIJsedeCentro01\",\"formattedAddress\":\"x\",\"location\":{\"latitude\":\"no\",\"longitude\":null},\"types\":[]}");
        var mala = servicio.buscarDetallado("Clínica Meta", "g:ChIJsedeCentro01", "sesion-abc-123456");
        assertTrue(mala.eleccionFallida() && mala.lugares().isEmpty());
        assertFalse(rutas.stream().anyMatch(x -> x.endsWith(":searchText")), "nunca se reemplaza por una búsqueda de texto: " + rutas);
    }

    // ------------------------------------------------------------------ costo: una consulta por pausa, nada por tecla ni por predicción
    @Test void sugerirNoHaceBusquedaDeTextoNiDetallePorCadaPrediccion() {
        autocompletar.set(sugerencias(prediccion("ChIJ0000000030", "Calle 30", "Villavicencio, Meta"), prediccion("ChIJ0000000003", "Calle 3", "Villavicencio, Meta")));
        principales("Calle 3");
        assertEquals(List.of("POST /v1/places:autocomplete"), rutas);
    }
}
