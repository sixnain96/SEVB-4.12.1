package co.edu.usta.spevb.config;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Normalización de la nomenclatura colombiana para consultar a Google («carrera 27 número 35A 50» → «Carrera 27 # 35A-50»). Las salidas son EXPECTATIVAS del normalizador: que una dirección
 * exista lo decide Google. La normalización cambia abreviaturas, mayúsculas, espacios y signos, pero conserva el significado (letras, Bis, sentidos, números).
 */
class NormalizacionDireccionTest {
    private final CityArea area = new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45);
    private String n(String s) { return area.normalizeAddress(s); }

    @Test void tablaDeEjemplos() {
        assertEquals("Carrera 27 # 35A-50", n("carrera 27 número 35A 50"));
        assertEquals("Carrera 48 # 25A-50", n("carrera 48 numero 25A 50"));
        assertEquals("Carrera 27 # 35A-50", n("Cra. 27 No. 35A-50"));
        assertEquals("Carrera 27 # 35A-50", n("Kra 27 #35A - 50"));
        assertEquals("Carrera 27 # 35A-50", n("Cra 27 35A 50"));
        assertEquals("Calle 30 # 38-10", n("Cll. 30 N° 38 10"));
        assertEquals("Carrera 27 Norte # 5-50", n("Carrera 27 Norte número 5 50"));
        assertEquals("Calle 15 Bis Sur # 20A-10B", n("Calle 15 Bis Sur # 20A 10B"));
    }

    @Test void otrosFormatosDeLaPlaca() {
        for (String e : List.of("cra 27 nº 35a-50", "CRA 27 N.º 35A 50", "carrera 27 nro 35a 50", "Carrera 27  #  35A  -  50", "carrera 27 num 35A 50", "Kr 27 # 35a 50", "Cr. 27 No 35A 50"))
            assertEquals("Carrera 27 # 35A-50", n(e), e);
        assertEquals("Calle 30 # 38-10", n("cll30 #38-10"));
        assertEquals("Avenida 40 # 22-15", n("av 40 no 22 15"));
        assertEquals("Diagonal 25 Sur # 12-30", n("dg 25 sur 12 30"));
        assertEquals("Transversal 7 # 3A-20", n("tv 7 numero 3a 20"));
    }

    @Test void conservaElBarrioOLaReferenciaAlFinal() {
        assertEquals("Carrera 27 # 35A-50 barrio Cataluña", n("carrera 27 numero 35A 50 barrio Cataluña"));
        assertEquals("Calle 30 # 38-10 Los Maracos", n("cll 30 38 10 Los Maracos"));
    }

    @Test void lasConsultasParcialesNoInventanNada() {
        assertEquals("Carrera 27", n("Cra 27"));
        assertEquals("Carrera 27 #", n("Cra 27 número"));
        assertEquals("Carrera 27 # 35A", n("Cra 27 número 35A"));
        assertEquals("Carrera 27 35A", n("Cra 27 35A"), "una sola cifra tras la vía admite dos lecturas: se conserva el texto");
    }

    @Test void unaEntradaAmbiguaSeConservaParaQueGoogleSugiera() {
        assertEquals("Carrera 27 35 50 60", n("carrera 27 35 50 60"), "tres cifras tras la vía: no se adivina cuál es la placa");
    }

    @Test void noInventaNiCambiaNadaQueDistingaUnaDireccionDeOtra() {
        assertFalse(n("carrera 27 número 35A 50").contains("35-50"), "35A no es 35");
        assertTrue(n("carrera 27 numero 35 50").endsWith("# 35-50"), "50 no es 5");
        assertTrue(n("calle 15 bis sur 20A 10B").contains("Bis Sur"), "no se pierden Bis ni Sur");
        assertTrue(n("carrera 27 norte numero 5 50").contains("Norte"));
        assertTrue(n("calle 30 numero 38 10").startsWith("Calle 30"), "Calle sigue siendo Calle");
        assertNotEquals(n("calle 30 número 38 10"), n("carrera 30 número 38 10"));
        assertNotEquals(n("carrera 27 # 35A-50"), n("carrera 27 # 35-50"));
        assertNotEquals(n("carrera 27 # 35A-50"), n("carrera 27 # 35A-51"));
    }

    @Test void losNombresDeEstablecimientosNoSeTratanComoCalles() {
        for (String nombre : List.of("Centro Comercial Viva", "Clínica Número 5", "Colegio Nacional No. 3", "Hospital Departamental", "Unicentro Villavicencio", "Universidad de los Llanos", "Parque Los Fundadores"))
            assertEquals(nombre, n(nombre), "sin cambios: " + nombre);
    }

    @Test void esIdempotente() {
        for (String e : List.of("carrera 27 número 35A 50", "Cra. 27 No. 35A-50", "Kra 27 #35A - 50", "Cll. 30 N° 38 10", "Calle 15 Bis Sur # 20A 10B", "Cra 27 número", "Cra 27 35A", "Centro Comercial Viva", "carrera 27 norte 5 50 barrio Cataluña")) {
            String uno = n(e);
            assertEquals(uno, n(uno), "dos veces = una vez: " + e);
        }
    }

    @Test void elNumeralSeConservaParaLaUrlYElJson() {
        assertTrue(n("Kra 27 35A 50").contains("#"), "el # sigue en la consulta; al ir por URL se codifica como %23");
        assertEquals("Carrera+27+%23+35A-50", java.net.URLEncoder.encode(n("kra 27 35a 50"), java.nio.charset.StandardCharsets.UTF_8));
    }
}
