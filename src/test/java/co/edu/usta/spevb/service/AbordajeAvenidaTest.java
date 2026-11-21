package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
import co.edu.usta.spevb.repository.ViajeRepository;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * La elección de subida y bajada tiene en cuenta cruzar una avenida a nivel (costo) pero NO lo muestra como distancia caminada:
 * {@code caminataMetros} son metros reales; {@code penalizacionMetros} es el cobro del cruce; con un puente cercano no hay cobro.
 */
class AbordajeAvenidaTest {
    private static final double LAT0 = 4.14, LNG0 = -73.63, PASO = 0.001;
    private static final double AVENIDA = LAT0 + 3 * PASO;
    private static final double METROS_POR_FILA = PASO * 110_574;

    private static RedPeatonal.Constructor ciudad() {
        var c = new RedPeatonal.Constructor(100, 160);
        for (int j = 0; j < 8; j++) {
            long[] ids = new long[8]; double[] la = new double[8], lo = new double[8];
            for (int i = 0; i < 8; i++) { ids[i] = 1000L * i + j; la[i] = LAT0 + i * PASO; lo[i] = LNG0 + j * PASO; }
            c.agregarCamino(ids, la, lo, RedPeatonal.LLANA);
        }
        for (int i : new int[]{0, 1, 5, 6, 7}) {
            long[] ids = new long[8]; double[] la = new double[8], lo = new double[8];
            for (int j = 0; j < 8; j++) { ids[j] = 1000L * i + j; la[j] = LAT0 + i * PASO; lo[j] = LNG0 + j * PASO; }
            c.agregarCamino(ids, la, lo, RedPeatonal.LLANA);
        }
        long[] ids = new long[8]; double[] la = new double[8], lo = new double[8];
        for (int j = 0; j < 8; j++) { ids[j] = 3000L + j; la[j] = AVENIDA; lo[j] = LNG0 + j * PASO; }
        c.agregarCamino(ids, la, lo, RedPeatonal.TRONCAL);
        return c;
    }

    /** Ruta de oeste a este por la calle de la fila 5 (al norte de la avenida), una muestra cada ≈ 15 m. */
    private static List<ViajeRepository.CandidatoRow> muestras() {
        double largo = 7 * PASO * 111_320 * Math.cos(Math.toRadians(LAT0));
        int n = (int) Math.ceil(largo / 15);
        List<ViajeRepository.CandidatoRow> r = new ArrayList<>();
        for (int k = 0; k <= n; k++) {
            double f = (double) k / n;
            r.add(new ViajeRepository.CandidatoRow(1, "IDA", largo, f, LNG0 + f * 7 * PASO, LAT0 + 5 * PASO, 0, null));
        }
        return r;
    }

    private static AbordajeService servicio(RedPeatonal red) {
        var repo = mock(ViajeRepository.class);
        when(repo.muestras(anyList(), anyDouble(), anyDouble(), anyDouble(), anyDouble(), anyDouble(), anyDouble(), anyDouble()))
                .thenReturn(muestras());
        var s = new AbordajeService(repo, mock(CaminataService.class));
        s.usarRed(new RedPeatonalService(red, new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45)));
        return s;
    }

    // A al sur de la avenida, en la calle de la columna 3 (lejos de los extremos de la avenida, donde el cruce es libre); B al norte, junto a la ruta.
    private static final double[] A = {LAT0 + 1.5 * PASO, LNG0 + 3 * PASO}, B = {LAT0 + 5 * PASO + 0.00005, LNG0 + 6 * PASO};

    @Test void conUnPuenteAMediaCuadraLaSubidaSeDesplazaAlPuenteYLosMetrosSonLosCaminados() {
        var c = ciudad();
        double lng4 = LNG0 + 4 * PASO;       // a 111 m de la calle de A, dentro de la zona del puente
        c.agregarPaso(new double[]{AVENIDA - 0.0002, AVENIDA + 0.0002}, new double[]{lng4, lng4}, 12, RedPeatonal.PUENTE);
        var o = servicio(c.construir()).optimizar(A, B, List.of(1L), 2000, 2000).get(1L).menosCaminata();
        // La ruta recorre toda la calle de la fila 5: subir una cuadra más al este y cruzar por el puente (≈ 498 m) cuesta menos que
        // subir recto y pagar el cruce a nivel (387 m + 160 m). Lo que se muestra son los metros caminados, sin cobro alguno.
        assertEquals(0, o.subida().penalizacionMetros(), 1e-9);
        assertEquals(3.5 * METROS_POR_FILA + 111, o.subida().caminataMetros(), 40);
        assertEquals(o.subida().caminataMetros(), o.subida().costoCaminata(), 1e-9);
    }

    @Test void conUnPuenteCercanoLaSubidaNoPagaCruceYSeMuestranLosMetrosDelPuente() {
        var c = ciudad();
        double lng = LNG0 + 3.4 * PASO;
        c.agregarPaso(new double[]{AVENIDA - 0.0002, AVENIDA + 0.0002}, new double[]{lng, lng}, 12, RedPeatonal.PUENTE);
        var o = servicio(c.construir()).optimizar(A, B, List.of(1L), 2000, 2000).get(1L).menosCaminata();
        assertEquals(0, o.subida().penalizacionMetros(), 1e-6);
        assertTrue(o.subida().caminataMetros() > 3.5 * METROS_POR_FILA, "da un pequeño rodeo para usar el puente");
        assertTrue(o.subida().caminataMetros() < 3.5 * METROS_POR_FILA + 160, "menos que el cruce a nivel");
    }

    @Test void sinPuentesLaAvenidaSeCruzaLibreYNoSeCobraNada() {
        var o = servicio(ciudad().construir()).optimizar(A, B, List.of(1L), 2000, 2000).get(1L).menosCaminata();
        assertEquals(0, o.subida().penalizacionMetros(), 1e-9);
        assertEquals(3.5 * METROS_POR_FILA, o.subida().caminataMetros(), 25);
    }

    @Test void conUnPuenteLejanoNoCambiaNada() {
        var c = ciudad();
        double lng = LNG0 + 6.5 * PASO;
        c.agregarPaso(new double[]{AVENIDA - 0.0002, AVENIDA + 0.0002}, new double[]{lng, lng}, 12, RedPeatonal.PUENTE);
        var o = servicio(c.construir()).optimizar(A, B, List.of(1L), 2000, 2000).get(1L).menosCaminata();
        assertEquals(0, o.subida().penalizacionMetros(), 1e-9, "fuera de la zona del puente se cruza libre");
        assertEquals(3.5 * METROS_POR_FILA, o.subida().caminataMetros(), 25, "sin ir hasta el puente");
    }

    @Test void elConstructorAntiguoDeCandidatoSigueSinPenalizacion() {
        var c = new AbordajeService.Candidato(1, "IDA", 100, 0.5, -73.6, 4.1, 30, 40, null);
        assertEquals(0, c.penalizacionMetros());
        assertEquals(40, c.costoCaminata());
    }
}
