package co.edu.usta.spevb.service;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/** Modo demostración de logros (LOGROS_CUENTAS_DEMO): todo el catálogo desbloqueado, con métricas que cumplen de verdad las reglas. */
class LogrosDemoTest {
    private static final LocalDate HOY = LocalDate.of(2026, 11, 18);

    private static LogrosService.Estado vacio() {
        var m = new LogrosService.Metricas(0, 0, 0, 0, 0, false, false, false);
        return new LogrosService.Estado(m, List.of(), null, HOY, null, List.of());
    }

    @Test void unaCuentaSinViajesVeTodoElCatalogoDesbloqueado() {
        var d = LogrosService.demo(vacio(), null);
        assertEquals(LogrosService.CATALOGO, d.logros());
        assertNull(d.insignia());
    }

    @Test void lasMetricasMostradasCumplenLasReglasDeVerdad() {
        var d = LogrosService.demo(vacio(), null);
        assertEquals(LogrosService.CATALOGO, LogrosService.desbloqueados(d.m()), "las métricas de la demostración deben desbloquear cada logro por sus reglas");
    }

    @Test void laRachaMostradaSonSieteDiasSeguidosQueTerminanHoy() {
        var d = LogrosService.demo(vacio(), null);
        assertEquals(7, d.dias().size());
        assertEquals(HOY, d.dias().get(6));
        assertEquals(HOY.minusDays(6), d.dias().get(0));
        assertEquals(HOY, d.ultimoDia());
        assertEquals(7, d.m().rachaActual());
        assertEquals(Racha.calcular(d.dias(), HOY).actual(), d.m().rachaActual(), "el servidor y el dispositivo calculan la misma racha desde esos días");
    }

    @Test void losViajesRealesNuncaSeReducen() {
        var m = new LogrosService.Metricas(120, 9, 15, 20, 18, false, false, false);
        var d = LogrosService.demo(new LogrosService.Estado(m, List.of("primero"), "cinco", HOY, HOY, List.of(HOY)), "cinco");
        assertEquals(120, d.m().viajes());
        assertEquals(9, d.m().transbordos());
        assertEquals(15, d.m().rachaActual());
        assertEquals("cinco", d.insignia());
    }

    @Test void unaInsigniaQueNoExisteSeIgnora() {
        assertNull(LogrosService.demo(vacio(), "inventada").insignia());
        assertEquals("llano", LogrosService.demo(vacio(), "llano").insignia());
    }
}
