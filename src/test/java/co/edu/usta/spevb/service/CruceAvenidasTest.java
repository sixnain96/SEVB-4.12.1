package co.edu.usta.spevb.service;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Cruce de avenidas a nivel contra puente peatonal. La red es una retícula de calles de ≈ 110 m con una avenida troncal en la fila 3
 * (de oeste a este). El cobro por cruzar existe SOLO cerca de un puente registrado (≤ 120 m de sus extremos): allí cruzar a nivel cuesta
 * 160 m equivalentes en estas pruebas y un puente que enlace los dos andenes se usa si su desvío cuesta menos. Lejos de los puentes y en una
 * ciudad sin puentes, las avenidas se cruzan libremente por el camino más corto.
 */
class CruceAvenidasTest {
    private static final double LAT0 = 4.14, LNG0 = -73.63, PASO = 0.001;
    private static final double METROS_POR_FILA = PASO * 110_574;
    private static final double AVENIDA = LAT0 + 3 * PASO;

    /** Calles verticales LLANA en las columnas 0..7 que cruzan la avenida; la avenida (clase {@code claseAvenida}) en la fila 3. */
    private static RedPeatonal.Constructor ciudad(double cruceVia, double cruceTroncal, byte claseAvenida) {
        var c = new RedPeatonal.Constructor(cruceVia, cruceTroncal);
        for (int j = 0; j < 8; j++) {
            long[] ids = new long[8]; double[] la = new double[8], lo = new double[8];
            for (int i = 0; i < 8; i++) { ids[i] = 1000L * i + j; la[i] = LAT0 + i * PASO; lo[i] = LNG0 + j * PASO; }
            c.agregarCamino(ids, la, lo, RedPeatonal.LLANA);
        }
        // Calles horizontales de las filas 0, 1, 5, 6 y 7 (la fila 3 es la avenida; las 2 y 4 quedan sin calle a propósito).
        for (int i : new int[]{0, 1, 5, 6, 7}) {
            long[] ids = new long[8]; double[] la = new double[8], lo = new double[8];
            for (int j = 0; j < 8; j++) { ids[j] = 1000L * i + j; la[j] = LAT0 + i * PASO; lo[j] = LNG0 + j * PASO; }
            c.agregarCamino(ids, la, lo, RedPeatonal.LLANA);
        }
        long[] ids = new long[8]; double[] la = new double[8], lo = new double[8];
        for (int j = 0; j < 8; j++) { ids[j] = 1000L * 3 + j; la[j] = AVENIDA; lo[j] = LNG0 + j * PASO; }
        c.agregarCamino(ids, la, lo, claseAvenida);
        return c;
    }

    private static RedPeatonal.Constructor ciudad() { return ciudad(100, 160, RedPeatonal.TRONCAL); }

    /** Puente de 44 m que cruza la avenida en la columna {@code columna} (se une a la avenida por el lugar más cercano). */
    private static void puente(RedPeatonal.Constructor c, double columna) {
        double lng = LNG0 + columna * PASO;
        int conectados = c.agregarPaso(new double[]{AVENIDA - 0.0002, AVENIDA + 0.0002}, new double[]{lng, lng}, 12, RedPeatonal.PUENTE);
        assertEquals(2, conectados, "los dos extremos quedan unidos a la avenida (se parte por ese lugar)");
    }

    /** {costo, penalización, metros del camino dibujado} de ir de un punto a otro. */
    private static double[] ir(RedPeatonal r, double la, double lo, double lb, double lob) {
        var a = r.ajustarVarios(la, lo, 250, 4, 40);
        var b = r.ajustarVarios(lb, lob, 250, 4, 40);
        assertFalse(a.isEmpty() || b.isEmpty(), "los dos puntos tienen calle cerca");
        var res = r.costosDesdeDetallado(a, b, 20_000);
        double mejorC = Double.NaN, mejorP = 0;
        for (int k = 0; k < b.size(); k++) {
            if (Double.isNaN(res[0][k])) continue;
            double c = res[0][k] + b.get(k).distM();
            if (Double.isNaN(mejorC) || c < mejorC) { mejorC = c; mejorP = res[1][k]; }
        }
        var camino = r.camino(a, b, 20_000);
        return new double[]{mejorC, mejorP, camino == null ? Double.NaN : camino.metros()};
    }

    private static boolean pasaPor(RedPeatonal r, double la, double lo, double lb, double lob, double lat, double lng) {
        var camino = r.camino(r.ajustarVarios(la, lo, 250, 4, 40), r.ajustarVarios(lb, lob, 250, 4, 40), 20_000);
        return camino.coordenadas().stream().anyMatch(p -> Math.abs(p[0] - lng) < 1e-6 && Math.abs(p[1] - lat) < 1e-6);
    }

    // Origen al sur de la avenida (fila 1,5) y destino al norte (fila 5,5), los dos sobre la columna 3 (lejos de los extremos de la avenida).
    private static final double SUR = LAT0 + 1.5 * PASO, NORTE = LAT0 + 5.5 * PASO, COL3 = LNG0 + 3 * PASO;

    @Test void sinPuentesLaAvenidaSeCruzaLibrePorElCaminoMasCorto() {
        var r = ciudad().construir();
        double[] t = ir(r, SUR, COL3, NORTE, COL3);
        assertEquals(0, t[1], 1e-9);
        assertEquals(4 * METROS_POR_FILA, t[2], 3, "recto, sin desvío ni cobro");
    }

    @Test void unPuenteLejanoNoCambiaNada() {
        var c = ciudad();
        puente(c, 6.5);                       // a 385 m: fuera de su zona de influencia (120 m)
        var r = c.construir();
        double[] t = ir(r, SUR, COL3, NORTE, COL3);
        assertEquals(0, t[1], 1e-9);
        assertEquals(4 * METROS_POR_FILA, t[2], 3, "se cruza directo, sin ir hasta el puente");
        assertFalse(pasaPor(r, SUR, COL3, NORTE, COL3, AVENIDA, LNG0 + 6.5 * PASO));
    }

    @Test void cercaDeUnPuenteCruzarANivelCuestaElCruceYNoSeMuestraComoMetros() {
        var c = ciudad();
        puente(c, 4);                         // a 111 m: dentro de su zona, pero ir y volver (≈ 222 m) cuesta más que 160 m
        var r = c.construir();
        double[] t = ir(r, SUR, COL3, NORTE, COL3);
        assertEquals(160, t[1], 1e-3, "una calzada troncal = 160 m equivalentes");
        assertEquals(4 * METROS_POR_FILA, t[2], 3, "el camino dibujado mide lo que se camina, sin el cobro");
        assertEquals(t[2] + 160, t[0], 3, "costo = metros + cruce");
    }

    @Test void unPuenteCercanoSeUsaEnVezDeCruzarANivel() {
        var c = ciudad();
        puente(c, 3.4);                       // a 44 m: desvío ≈ 44 + 44 + 44 m < 160 m
        var r = c.construir();
        double[] t = ir(r, SUR, COL3, NORTE, COL3);
        assertEquals(0, t[1], 1e-6, "con el puente no hay cruce a nivel");
        // Los extremos del puente se unen a la avenida por el lugar más cercano: el camino pasa por ese punto de la avenida.
        assertTrue(pasaPor(r, SUR, COL3, NORTE, COL3, AVENIDA, LNG0 + 3.4 * PASO), "el camino usa el puente");
        assertTrue(t[2] > 4 * METROS_POR_FILA + 60, "el puente da un pequeño rodeo: " + t[2]);
        assertTrue(t[2] < 4 * METROS_POR_FILA + 160, "pero menos que lo que vale cruzar: " + t[2]);
    }

    @Test void elPuenteTambienServeDeRegreso() {
        var c = ciudad();
        puente(c, 3.4);
        var r = c.construir();
        double[] t = ir(r, NORTE, COL3, SUR, COL3);
        assertEquals(0, t[1], 1e-6);
    }

    @Test void caminarPorLaAvenidaDeSuLadoNoCobraNadaAunqueHayaUnPuente() {
        var c = ciudad();
        puente(c, 4);
        var r = c.construir();
        // Al sur de la avenida, a 13 m de su eje, de una calle a otra pasando por la zona del puente: ni un metro de penalización.
        double[] t = ir(r, AVENIDA - 0.00012, LNG0 + 1.5 * PASO, AVENIDA - 0.00012, LNG0 + 5.5 * PASO);
        assertEquals(0, t[1], 1e-6);
    }

    @Test void unPuntoAlOtroLadoDeLaAvenidaNoSeSaltaElCruceCercaDeUnPuente() {
        var c = ciudad();
        puente(c, 4);
        var r = c.construir();
        // 15 m al sur y 15 m al norte del eje, entre dos calles y a 55 m del puente: antes se «pegaban» a la avenida y la cruzaban gratis; ahora
        // hay que ir al puente (ida y vuelta ≈ 110 m, menos que el cruce de 160 m) y se camina de verdad.
        double[] t = ir(r, AVENIDA - 0.00014, LNG0 + 3.5 * PASO, AVENIDA + 0.00014, LNG0 + 3.5 * PASO);
        assertEquals(0, t[1], 1e-6);
        assertTrue(t[2] > 100, "no cruza «en el aire»: camina hasta el puente: " + t[2]);
    }

    @Test void unaViaPrincipalCuestaMenosQueUnaTroncal() {
        var c = ciudad(100, 160, RedPeatonal.VIA_PRINCIPAL);
        puente(c, 4);
        assertEquals(100, ir(c.construir(), SUR, COL3, NORTE, COL3)[1], 1e-3);
    }

    @Test void conElCobroEnCeroLaAvenidaSeCruzaLibreAunqueHayaUnPuente() {
        var c = ciudad(0, 0, RedPeatonal.TRONCAL);
        puente(c, 4);
        assertEquals(0, ir(c.construir(), SUR, COL3, NORTE, COL3)[1], 1e-9);
    }

    @Test void unaCalleLocalNoEsBarrera() {
        var c = ciudad(100, 160, RedPeatonal.VIA_LOCAL);
        puente(c, 4);
        assertEquals(0, ir(c.construir(), SUR, COL3, NORTE, COL3)[1], 1e-9);
    }

    @Test void unaDobleCalzadaSeCobraDosVecesCercaDeUnPuente() {
        var c = new RedPeatonal.Constructor(50, 80);
        double a1 = LAT0 + 3 * PASO, a2 = LAT0 + 3.3 * PASO;       // dos calzadas a ≈ 33 m
        for (int j = 0; j < 8; j++) {
            double[] la = {LAT0, LAT0 + PASO, LAT0 + 2 * PASO, a1, a2, LAT0 + 4 * PASO, LAT0 + 5 * PASO, LAT0 + 6 * PASO};
            long[] ids = new long[8]; double[] lo = new double[8];
            for (int i = 0; i < 8; i++) { ids[i] = 100L * j + i; lo[i] = LNG0 + j * PASO; }
            c.agregarCamino(ids, la, lo, RedPeatonal.LLANA);
        }
        for (double la : new double[]{a1, a2}) {
            long[] ids = new long[8]; double[] lat = new double[8], lo = new double[8];
            for (int j = 0; j < 8; j++) { ids[j] = 100L * j + (la == a1 ? 3 : 4); lat[j] = la; lo[j] = LNG0 + j * PASO; }
            c.agregarCamino(ids, lat, lo, RedPeatonal.TRONCAL);
        }
        // Puente en la columna 4 que cruza las dos calzadas (de sur de la primera a norte de la segunda).
        double lng = LNG0 + 4 * PASO;
        c.agregarPaso(new double[]{a1 - 0.0002, a2 + 0.0002}, new double[]{lng, lng}, 12, RedPeatonal.PUENTE);
        var r = c.construir();
        // Columna 3: el puente queda a 111 m (ida y vuelta ≈ 222 m) y los dos cruces cuestan 160 m: se cruza a nivel pagando dos calzadas.
        double[] t = ir(r, LAT0 + 1.5 * PASO, COL3, LAT0 + 5.5 * PASO, COL3);
        assertEquals(160, t[1], 1e-3, "dos calzadas: dos cruces");
    }

    @Test void losTramosDeAdministracionNoRepitenLaAvenida() {
        var r = ciudad().construir();
        assertTrue(r.nodos() > 0 && r.aristas() > 0);
        List<double[]> tramos = r.segmentos(LAT0 - 0.001, LNG0 - 0.001, LAT0 + 0.008, LNG0 + 0.008, 100_000);
        long enLaAvenida = tramos.stream().filter(s -> Math.abs(s[1] - AVENIDA) < 1e-9 && Math.abs(s[3] - AVENIDA) < 1e-9).count();
        assertEquals(7, enLaAvenida, "siete tramos de avenida entre ocho columnas, una sola vez cada uno");
    }

    @Test void conUnPuenteLosTramosDeAdministracionTampocoRepitenElAndenDuplicado() {
        var c = ciudad();
        puente(c, 3.4);
        var r = c.construir();
        List<double[]> tramos = r.segmentos(LAT0 - 0.001, LNG0 - 0.001, LAT0 + 0.008, LNG0 + 0.008, 100_000);
        // Cada tramo de la avenida aparece una sola vez (sin la copia del andén derecho ni la arista virtual de cruce): los 7 originales, uno de
        // ellos partido por los extremos del puente, más el propio puente → como máximo 7 + 2 + 1 = 10 tramos sobre la línea de la avenida.
        long enLaAvenida = tramos.stream().filter(s -> Math.abs(s[1] - AVENIDA) < 1e-9 && Math.abs(s[3] - AVENIDA) < 1e-9).count();
        assertTrue(enLaAvenida <= 10, "tramos sobre la avenida: " + enLaAvenida);
    }
}
