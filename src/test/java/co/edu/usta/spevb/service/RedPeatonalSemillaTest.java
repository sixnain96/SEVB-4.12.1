package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

import static org.junit.jupiter.api.Assertions.*;

/** Prueba con las calles reales de Villavicencio incluidas como semilla. */
class RedPeatonalSemillaTest {
    private static RedPeatonalService servicio;

    @BeforeAll static void cargar() throws Exception {
        servicio = new RedPeatonalService(false, "data/no-existe.bin.gz", 60, "", 
                new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45), JsonMapper.builder().build());
        servicio.cargarSemilla();
    }

    @Test void laSemillaCargaUnaRedGrandeYConectada() {
        var r = servicio.getRedParaPruebas();
        assertTrue(r.nodos() > 30_000, "nodos: " + r.nodos());
        assertTrue(r.nodosAccesibles() > r.nodos() * 0.98, "casi toda la red está conectada");
        assertEquals("LISTA", servicio.estado().estado());
    }

    @Test void calle36ConCarrera27HastaAvenidaCatamaSigueLasCalles() {
        // Caso real: A en la Calle 36 con Carrera 27, bus en la Avenida Catama (≈ 130 m al sur).
        var t = servicio.ruta(4.15015, -73.63280, 4.14884, -73.63294).orElseThrow();
        assertTrue(t.metros() > 120 && t.metros() < 200, "metros: " + t.metros());
    }

    @Test void macarenaHastaAvenidaCatamaDaUnCaminoPorCallesNoUnaRecta() {
        double recta = RedPeatonal.metros(4.12872, -73.61654, 4.14884, -73.63294);
        var t = servicio.ruta(4.12872, -73.61654, 4.14884, -73.63294).orElseThrow();
        assertTrue(t.coordenadas().size() > 40, "el camino por calles tiene muchos vértices: " + t.coordenadas().size());
        assertTrue(t.metros() > recta && t.metros() < recta * 1.6, "metros " + t.metros() + " recta " + recta);
    }

    @Test void sinCalleCercaNoSeInventaUnCamino() {
        assertTrue(servicio.ruta(4.3, -73.5, 4.31, -73.5).isEmpty());
    }

    /**
     * El tramo que se DIBUJA hasta la parada nunca puede ser más largo que lo que se midió al elegirla. Antes el dibujo probaba menos calles que
     * el cálculo (4 contra 5) y, cuando la mejor era la quinta, el mapa daba una vuelta de cientos de metros hasta una parada que estaba al lado.
     */
    @Test void elTramoDibujadoNuncaEsMasLargoQueLoMedidoAlElegirLaParada() {
        var azar = new java.util.Random(5);
        var puntos = servicio.getRedParaPruebas().puntosDeMuestra(1500, azar);
        int comparados = 0;
        for (int i = 0; i < puntos.length && comparados < 1000; i++) {
            double[] a = puntos[i];
            double ang = azar.nextDouble() * 2 * Math.PI, d = 30 + azar.nextDouble() * 400;
            double[] b = {a[0] + d * Math.sin(ang) / 110_574, a[1] + d * Math.cos(ang) / 111_320};
            var matriz = servicio.distancias(java.util.List.of(new double[]{a[1], a[0]}), java.util.List.of(new double[]{b[1], b[0]}));
            var leg = servicio.ruta(a[0], a[1], b[0], b[1]);
            if (matriz.isEmpty() || Double.isNaN(matriz.get()[0][0]) || leg.isEmpty()) continue;
            comparados++;
            assertTrue(leg.get().metros() <= matriz.get()[0][0] + 1,
                    String.format("dibujado %.0f m contra %.0f m medidos entre (%.5f,%.5f) y (%.5f,%.5f)", leg.get().metros(), matriz.get()[0][0], a[0], a[1], b[0], b[1]));
        }
        assertTrue(comparados >= 400, "pares comparados: " + comparados);
    }
}
