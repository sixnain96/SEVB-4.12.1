package co.edu.usta.spevb.service;

import co.edu.usta.spevb.dto.ViajeResponse;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/** Regla «las mejores opciones» (máximo 3, sin caminatas excesivas). */
class MejoresOpcionesTest {
    private static ViajeResponse.Opcion directa(String codigo, double caminaM, boolean permitido) {
        return new ViajeResponse.Opcion(1, codigo, "Ruta " + codigo, "#176650", true, caminaM / 2, caminaM / 2, 3.0, caminaM, true, "IDA", "IDA", permitido,
                null, null, null, null, true, null, null, null, null, "MENOS_CAMINATA");
    }

    private static ViajeResponse.Transbordo transbordo(double caminaM, double minutos) {
        return new ViajeResponse.Transbordo(minutos, caminaM, 5.0, 2, 8, null, null, null, null, null, null);
    }

    @Test void conservaSoloLasDosMejoresDirectasEnSuOrden() {
        var d = new ArrayList<ViajeResponse.Opcion>();
        for (int i = 1; i <= 8; i++) d.add(directa("M0" + i, 100.0 * i, true));
        var r = MejoresOpciones.aplicar(d, List.of(), List.of());
        assertEquals(List.of("M01", "M02"), r.directas().stream().map(ViajeResponse.Opcion::codigo).toList());
        assertTrue(r.nota().contains("2 mejores"));
    }

    @Test void descartaLasQueObligaranACaminarMasDeUnKilometro() {
        var r = MejoresOpciones.aplicar(List.of(directa("A", 300, true), directa("B", 900, true), directa("C", 1400, true), directa("D", 2500, true)), List.of(), List.of());
        assertEquals(List.of("A", "B"), r.directas().stream().map(ViajeResponse.Opcion::codigo).toList());
    }

    @Test void siNingunaCumpleMuestraSoloLaMenosLejanaYLoDice() {
        var r = MejoresOpciones.aplicar(List.of(directa("A", 1300, true), directa("B", 2100, true)), List.of(), List.of());
        assertEquals(1, r.directas().size());
        assertEquals("A", r.directas().get(0).codigo());
        assertTrue(r.nota().contains("menos lejana"));
    }

    @Test void lasDeSentidoContrarioSoloAparecenSiNoHayOtraCosa() {
        var contraria = directa("X", 200, false);
        assertTrue(MejoresOpciones.aplicar(List.of(directa("A", 300, true)), List.of(contraria), List.of()).alternativas().isEmpty());
        var sola = MejoresOpciones.aplicar(List.of(), List.of(contraria), List.of());
        assertEquals(1, sola.alternativas().size());
    }

    @Test void unTransbordoQueAcortaMuchoLaCaminataConservaUnCupoAunqueLasDirectasLlenenLaLista() {
        var d = List.of(directa("A", 900, true), directa("B", 950, true), directa("C", 980, true));
        var r = MejoresOpciones.aplicar(d, List.of(), List.of(transbordo(600, 30), transbordo(100, 25), transbordo(900, 20)));
        assertEquals(1, r.directas().size());
        assertEquals(1, r.transbordos().size());
        assertEquals(100, r.transbordos().get(0).caminataMetros(), 0.001, "el de menos caminata");
        assertEquals(2, r.directas().size() + r.transbordos().size());
    }

    @Test void unTransbordoQueNoAcortaLaCaminataNoLeQuitaElLugarALaSegundaDirecta() {
        var d = List.of(directa("A", 300, true), directa("B", 350, true));
        var r = MejoresOpciones.aplicar(d, List.of(), List.of(transbordo(250, 25)));
        assertEquals(2, r.directas().size());
        assertTrue(r.transbordos().isEmpty());
    }

    @Test void sinDirectasLosTransbordosPuedenLlenarLosDosCupos() {
        var r = MejoresOpciones.aplicar(List.of(), List.of(), List.of(transbordo(500, 30), transbordo(300, 28), transbordo(700, 26), transbordo(800, 25)));
        assertEquals(2, r.transbordos().size());
        assertEquals(300, r.transbordos().get(0).caminataMetros(), 0.001);
    }

    @Test void sinOpcionesNoInventaNada() {
        var r = MejoresOpciones.aplicar(List.of(), List.of(), List.of());
        assertTrue(r.directas().isEmpty() && r.alternativas().isEmpty() && r.transbordos().isEmpty());
    }

    @Test void unaSolaOpcionPorRutaYLasQueDanUnaVueltaEnormeNoGanan() {
        var rapida = new ViajeResponse.Opcion(1, "M01", "Ruta M01", "#176650", true, 100, 100, 3.0, 200, true, "IDA", "IDA", true, null, null, null, null, true, null, null, null, null, "MAS_RAPIDA");
        var lenta = directa("M01", 900, true);
        var vuelta = new ViajeResponse.Opcion(2, "M02", "Ruta M02", "#176650", true, 50, 50, 40.0, 100, true, "IDA", "IDA", true, null, null, null, null, true, null, null, null, null, "MENOS_CAMINATA");
        var normal = directa("M03", 400, true);
        var r = MejoresOpciones.aplicar(List.of(lenta, rapida, vuelta, normal), List.of(), List.of());
        assertEquals(List.of("M01", "M03"), r.directas().stream().map(ViajeResponse.Opcion::codigo).toList(), "M01 una vez (la de menor costo) y la de 40 km queda fuera");
        assertEquals("MAS_RAPIDA", r.directas().get(0).variante());
    }
}
