package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.CuentaService.Usuario;
import co.edu.usta.spevb.service.LogrosService;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Cuentas de demostración (LOGROS_CUENTAS_DEMO): solo los correos listados ven todos los logros; el resto sigue con su progreso real. */
class LogrosDemoControllerTest {
    private static final String SESION = "S".repeat(43);
    private static final Usuario ANA = new Usuario(7, "Ana", "ana@gmail.com", false, true, false);
    private final CuentaService cuentas = mock(CuentaService.class);
    private final LogrosService logros = mock(LogrosService.class);
    private final LimitadorSolicitudes limitador = mock(LimitadorSolicitudes.class);
    private final LogrosController c = new LogrosController(cuentas, logros, limitador);

    private static MockHttpServletRequest req() {
        var r = new MockHttpServletRequest();
        r.setCookies(new Cookie(CuentaController.COOKIE, SESION));
        return r;
    }

    private static LogrosService.Estado estado(List<String> ids) {
        var m = new LogrosService.Metricas(ids.size(), 0, 1, 1, 1, false, false, false);
        return new LogrosService.Estado(m, ids, null, LocalDate.of(2026, 3, 2), LocalDate.of(2026, 3, 2), List.of(LocalDate.of(2026, 3, 2)));
    }

    private void sesion() {
        when(cuentas.usuarioDeSesion(SESION)).thenReturn(Optional.of(ANA));
        when(limitador.permitir(anyString(), anyInt(), any())).thenReturn(true);
    }

    @Test void unCorreoListadoVeTodosLosLogros() {
        sesion();
        ReflectionTestUtils.setField(c, "cuentasDemo", "otra@x.com,  ANA@Gmail.com ");      // sin importar mayúsculas ni espacios
        when(logros.estadoDemo(eq(7L), anyLong())).thenReturn(estado(LogrosService.CATALOGO));
        Map<String, Object> r = c.estado(req());
        assertEquals(LogrosService.CATALOGO, r.get("logros"));
        verify(logros, never()).estado(anyLong(), anyLong());
    }

    @Test void sinLaVariableNadieEsDemostracion() {
        sesion();
        when(logros.estado(eq(7L), anyLong())).thenReturn(estado(List.of("primero")));
        Map<String, Object> r = c.estado(req());
        assertEquals(List.of("primero"), r.get("logros"));
        verify(logros, never()).estadoDemo(anyLong(), anyLong());
    }

    @Test void otroCorreoNoCambia() {
        sesion();
        ReflectionTestUtils.setField(c, "cuentasDemo", "alguien@x.com");
        when(logros.estado(eq(7L), anyLong())).thenReturn(estado(List.of("primero")));
        assertEquals(List.of("primero"), c.estado(req()).get("logros"));
        verify(logros, never()).estadoDemo(anyLong(), anyLong());
    }

    @Test void laDemostracionPermiteDestacarCualquierInsignia() {
        sesion();
        ReflectionTestUtils.setField(c, "cuentasDemo", "ana@gmail.com");
        when(logros.equipar(eq(7L), eq("llano"), anyLong(), eq(true))).thenReturn(estado(LogrosService.CATALOGO));
        c.insignia(new LogrosController.InsigniaRequest("llano"), req());
        verify(logros).equipar(eq(7L), eq("llano"), anyLong(), eq(true));
        verify(logros, never()).equipar(anyLong(), any(), anyLong());
    }

    // ---- racha estática de la cuenta de demostración (4.17): 30 el primer día y un día menos por cada día que pasa
    @Test void laRachaDeLaCuentaDemoEmpiezaEn30YPierdeUnDiaPorDia() {
        ReflectionTestUtils.setField(c, "rachaDemoBase", 30); ReflectionTestUtils.setField(c, "rachaDemoInicio", "2026-11-19");
        assertEquals(30, c.rachaDemo(LocalDate.of(2026, 11, 19)));
        assertEquals(29, c.rachaDemo(LocalDate.of(2026, 11, 20)));
        assertEquals(20, c.rachaDemo(LocalDate.of(2026, 11, 29)));
        assertEquals(0, c.rachaDemo(LocalDate.of(2026, 12, 19)));
        assertEquals(0, c.rachaDemo(LocalDate.of(2027, 3, 1)), "nunca baja de 0");
        assertEquals(30, c.rachaDemo(LocalDate.of(2026, 10, 1)), "antes de la fecha de inicio vale la base");
    }

    @Test void laRespuestaDeLaCuentaDemoTrae_rachaDemo_ylaRachaEstatica() {
        sesion();
        ReflectionTestUtils.setField(c, "cuentasDemo", "ana@gmail.com");
        ReflectionTestUtils.setField(c, "rachaDemoBase", 30);
        ReflectionTestUtils.setField(c, "rachaDemoInicio", "2026-03-01");      // la fecha del estado de prueba es 2026-03-02: pasó 1 día
        when(logros.estadoDemo(eq(7L), anyLong())).thenReturn(estado(LogrosService.CATALOGO));
        Map<String, Object> r = c.estado(req());
        assertEquals(29, r.get("rachaActual"));
        assertEquals(30, r.get("mejorRacha"));
        assertEquals(Map.of("base", 30, "inicio", "2026-03-01"), r.get("rachaDemo"));
    }

    @Test void lasDemasCuentasNoRecibenLaRachaEstatica() {
        sesion();
        when(logros.estado(eq(7L), anyLong())).thenReturn(estado(List.of("primero")));
        Map<String, Object> r = c.estado(req());
        assertFalse(r.containsKey("rachaDemo"));
        assertEquals(1, r.get("rachaActual"));
    }

    // ---- cuenta del PROYECTO (sebvadmin@gmail.com): siempre demostración, con racha estática de 31
    private static final Usuario PROYECTO = new Usuario(9, "Admin SEVB", "SebvAdmin@Gmail.com", false, true, true);

    @Test void laCuentaDelProyectoSiempreVeTodosLosLogrosAunqueNoHayaVariable() {
        when(cuentas.usuarioDeSesion(SESION)).thenReturn(Optional.of(PROYECTO));
        when(limitador.permitir(anyString(), anyInt(), any())).thenReturn(true);
        when(logros.estadoDemo(eq(9L), anyLong())).thenReturn(estado(LogrosService.CATALOGO));
        Map<String, Object> r = c.estado(req());
        assertEquals(LogrosService.CATALOGO, r.get("logros"));
        assertEquals(31, r.get("rachaActual"), "31 días, estática (sin fecha de inicio)");
        verify(logros, never()).estado(anyLong(), anyLong());
    }

    @Test void sinFechaDeInicioLaRachaDemoEsEstaticaYConFechaBaja() {
        assertEquals(31, c.rachaDemo(LocalDate.of(2030, 1, 1)), "por defecto: 31 siempre");
        ReflectionTestUtils.setField(c, "rachaDemoInicio", "2026-11-19");
        assertEquals(21, c.rachaDemo(LocalDate.of(2026, 11, 29)), "con fecha: un día menos por día");
    }
}
