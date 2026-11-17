package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.CuentaService.Usuario;
import co.edu.usta.spevb.service.LogrosService;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Contrato HTTP de logros y racha (Fase D): sin sesión no hay nada, el mismo sitio es obligatorio al escribir, y la respuesta no trae nada que no sea mínimo. */
class LogrosControllerTest {
    private static final String SESION = "S".repeat(43);
    private static final Usuario ANA = new Usuario(7, "Ana", "ana@gmail.com", false, true, false);
    private final CuentaService cuentas = mock(CuentaService.class);
    private final LogrosService logros = mock(LogrosService.class);
    private final LimitadorSolicitudes limitador = mock(LimitadorSolicitudes.class);
    private final LogrosController c = new LogrosController(cuentas, logros, limitador);

    private static MockHttpServletRequest req(boolean conSesion) {
        var r = new MockHttpServletRequest();
        if (conSesion) r.setCookies(new Cookie(CuentaController.COOKIE, SESION));
        return r;
    }

    private static LogrosService.Estado estado() {
        var m = new LogrosService.Metricas(1, 0, 1, 1, 1, false, false, false);
        return new LogrosService.Estado(m, List.of("primero"), null, LocalDate.of(2026, 3, 2), LocalDate.of(2026, 3, 2), List.of(LocalDate.of(2026, 3, 2)));
    }

    private void conSesion() {
        when(cuentas.usuarioDeSesion(SESION)).thenReturn(Optional.of(ANA));
        when(limitador.permitir(anyString(), anyInt(), any())).thenReturn(true);
    }

    @Test
    void sinSesionNingunaOperacionResponde() {
        when(cuentas.usuarioDeSesion(any())).thenReturn(Optional.empty());
        for (var op : List.<Runnable>of(
                () -> c.estado(req(false)),
                () -> c.viaje(new LogrosController.ViajeRequest("viaje-aaaa01", 1L, 1), req(false)),
                () -> c.practica(req(false)),
                () -> c.insignia(new LogrosController.InsigniaRequest("primero"), req(false)))) {
            var e = assertThrows(ResponseStatusException.class, op::run);
            assertEquals(HttpStatus.UNAUTHORIZED, e.getStatusCode());
        }
        verifyNoInteractions(logros);
    }

    @Test
    void unaSolicitudDeOtroSitioNoEscribeNada() {
        conSesion();
        var r = req(true);
        r.addHeader("Sec-Fetch-Site", "cross-site");
        var e = assertThrows(ResponseStatusException.class, () -> c.viaje(new LogrosController.ViajeRequest("viaje-aaaa01", 1L, 1), r));
        assertEquals(HttpStatus.FORBIDDEN, e.getStatusCode());
        verify(logros, never()).registrar(anyLong(), any(), anyLong(), anyInt(), anyLong());
    }

    @Test
    void registrarUsaLaCuentaDeLaSesionYNoUnaEnviadaPorElCliente() {
        conSesion();
        when(logros.registrar(eq(7L), eq("viaje-aaaa01"), eq(1000L), eq(2), anyLong())).thenReturn(new LogrosService.Registro(true, estado(), List.of("primero")));
        Map<String, Object> r = c.viaje(new LogrosController.ViajeRequest("viaje-aaaa01", 1000L, 2), req(true));
        assertEquals(Boolean.TRUE, r.get("nuevo"));
        assertEquals(List.of("primero"), r.get("nuevos"));
        assertEquals(1, r.get("viajes"));
        // la respuesta es el estado mínimo: nada de coordenadas, direcciones ni identificadores de viaje
        assertFalse(r.keySet().stream().anyMatch(k -> k.toLowerCase().contains("lat") || k.toLowerCase().contains("dir") || k.equals("viajeId")), r.keySet().toString());
    }

    @Test
    void faltanDatosDelViajeEsUnaSolicitudIncorrecta() {
        conSesion();
        var e = assertThrows(ResponseStatusException.class, () -> c.viaje(new LogrosController.ViajeRequest("viaje-aaaa01", null, 1), req(true)));
        assertEquals(HttpStatus.BAD_REQUEST, e.getStatusCode());
        e = assertThrows(ResponseStatusException.class, () -> c.viaje(null, req(true)));
        assertEquals(HttpStatus.BAD_REQUEST, e.getStatusCode());
    }

    @Test
    void elLimiteDeSolicitudesResponde429() {
        when(cuentas.usuarioDeSesion(SESION)).thenReturn(Optional.of(ANA));
        when(limitador.permitir(anyString(), anyInt(), any())).thenReturn(false);
        var e = assertThrows(ResponseStatusException.class, () -> c.estado(req(true)));
        assertEquals(HttpStatus.TOO_MANY_REQUESTS, e.getStatusCode());
    }

    @Test
    void quitarLaInsigniaLlegaComoNulo() {
        conSesion();
        when(logros.equipar(eq(7L), isNull(), anyLong())).thenReturn(estado());
        c.insignia(new LogrosController.InsigniaRequest(null), req(true));
        verify(logros).equipar(eq(7L), isNull(), anyLong());
    }
}
