package co.edu.usta.spevb.controller;

import co.edu.usta.spevb.config.LimitadorSolicitudes;
import co.edu.usta.spevb.service.CuentaService;
import co.edu.usta.spevb.service.ViajeCompartidoService;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.ObjectMapper;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/** Contrato HTTP de «Compartir mi viaje»: errores genéricos, tokens en cabeceras, límites, ETag y cabeceras de privacidad. */
class ViajeCompartidoControllerTest {
    private final ViajeCompartidoService servicio = mock(ViajeCompartidoService.class);
    private final CuentaService cuentas = mock(CuentaService.class);
    private final ObjectMapper mapper = new ObjectMapper();
    private ViajeCompartidoController c = new ViajeCompartidoController(servicio, cuentas, new LimitadorSolicitudes());
    private static final String TOKEN = "A".repeat(43);

    private MockHttpServletRequest req() { var r = new MockHttpServletRequest(); r.setRemoteAddr("10.0.0.1"); return r; }

    @Test
    void tokenInvalidoVencidoORevocadoRespondenIgualConUn404Generico() {
        when(servicio.consultar(any())).thenReturn(Optional.empty());
        for (String t : new String[]{null, "malo", TOKEN}) {
            var e = assertThrows(ResponseStatusException.class, () -> c.consultar(t, null, req(), new MockHttpServletResponse()));
            assertEquals(404, e.getStatusCode().value());
            assertEquals(ViajeCompartidoController.NO_DISPONIBLE, e.getReason());
            assertFalse(String.valueOf(e.getReason()).contains(String.valueOf(t)) && t != null, "el mensaje no repite el token");
        }
    }

    @Test
    void actualizarConTokenMalFormadoOInexistenteEs404SinTocarLaBase() {
        var q = new ViajeCompartidoController.ActualizarRequest("caminar", 0, 0.1, 4.15, -73.63, 5.0, null);
        assertEquals(404, assertThrows(ResponseStatusException.class, () -> c.actualizar(q, "mal", req())).getStatusCode().value());
        verify(servicio, never()).actualizar(any(), any());
        when(servicio.actualizar(any(), any())).thenReturn(false);
        assertEquals(404, assertThrows(ResponseStatusException.class, () -> c.actualizar(q, TOKEN, req())).getStatusCode().value());
    }

    @Test
    void laConsultaPublicaLlevaCabecerasDePrivacidadYAdmiteEtag() throws Exception {
        var v = new ViajeCompartidoService.Vista("activo", "en_bus", 0, 0.4, 4.15, -73.63, 9, 7, 100L, 200L, mapper.readTree("{\"tramos\":[]}"));
        when(servicio.consultar(TOKEN)).thenReturn(Optional.of(v));
        var resp = new MockHttpServletResponse();
        @SuppressWarnings("unchecked") var cuerpo = (java.util.Map<String, Object>) c.consultar(TOKEN, null, req(), resp);
        assertEquals("no-store", resp.getHeader("Cache-Control"));
        assertEquals("no-referrer", resp.getHeader("Referrer-Policy"));
        assertTrue(resp.getHeader("X-Robots-Tag").contains("noindex"));
        assertEquals("\"7\"", resp.getHeader("ETag"));
        assertTrue(cuerpo.containsKey("posicion") && !cuerpo.toString().contains(TOKEN));
        var resp2 = new MockHttpServletResponse();
        assertNull(c.consultar(TOKEN, "\"7\"", req(), resp2));
        assertEquals(304, resp2.getStatus(), "sin cambios: no se repite el cuerpo");
    }

    @Test
    void unCuerpoVacioONuloEnActualizarEsUn400ControladoSinNullPointer() {
        var e = assertThrows(ResponseStatusException.class, () -> c.actualizar(null, TOKEN, req()));
        assertEquals(400, e.getStatusCode().value());
        assertFalse(String.valueOf(e.getReason()).toLowerCase().contains("null"), "sin detalles internos");
        verify(servicio, never()).actualizar(any(), any());
    }

    @Test
    void alLlegarLaRespuestaPublicaNoTraePosicion() throws Exception {
        var v = new ViajeCompartidoService.Vista("llego", "llegaste", 1, 1.0, null, null, 0, 9, 100L, 200L, null);
        when(servicio.consultar(TOKEN)).thenReturn(Optional.of(v));
        @SuppressWarnings("unchecked") var cuerpo = (java.util.Map<String, Object>) c.consultar(TOKEN, null, req(), new MockHttpServletResponse());
        assertFalse(cuerpo.containsKey("posicion"));
        assertEquals("llego", cuerpo.get("estado"));
    }

    @Test
    void crearDevuelveLosDosTokensYLimitaLaCreacionPorRed() throws Exception {
        when(servicio.crear(any(), any())).thenReturn(new ViajeCompartidoService.Creado("L".repeat(43), "E".repeat(43), 1L));
        when(cuentas.usuarioDeSesion(any())).thenReturn(Optional.empty());
        var q = new ViajeCompartidoController.CrearRequest(mapper.readTree("{\"tramos\":[[[-73.6,4.1],[-73.5,4.2]]]}"));
        var m = c.crear(q, req());
        assertEquals("L".repeat(43), m.get("lectura"));
        assertEquals("E".repeat(43), m.get("escritura"));
        for (int i = 0; i < 7; i++) c.crear(q, req());
        assertEquals(429, assertThrows(ResponseStatusException.class, () -> c.crear(q, req())).getStatusCode().value(), "más de 8 enlaces por hora desde una misma red");
    }

    @Test
    void lasEscriturasDeOtroSitioSeRechazan() throws Exception {
        var r = req();
        r.addHeader("Sec-Fetch-Site", "cross-site");
        var q = new ViajeCompartidoController.CrearRequest(mapper.readTree("{}"));
        assertEquals(403, assertThrows(ResponseStatusException.class, () -> c.crear(q, r)).getStatusCode().value());
        assertEquals(403, assertThrows(ResponseStatusException.class, () -> c.revocar(TOKEN, r)).getStatusCode().value());
        verify(servicio, never()).crear(any(), any());
        verify(servicio, never()).revocar(any());
    }

    @Test
    void revocarEsIdempotenteYLimitaLasActualizacionesPorEnlace() {
        assertEquals(true, c.revocar(TOKEN, req()).get("ok"));
        when(servicio.actualizar(any(), any())).thenReturn(true);
        var q = new ViajeCompartidoController.ActualizarRequest("caminar", 0, 0.1, 4.15, -73.63, 5.0, null);
        for (int i = 0; i < 12; i++) c.actualizar(q, TOKEN, req());
        assertEquals(429, assertThrows(ResponseStatusException.class, () -> c.actualizar(q, TOKEN, req())).getStatusCode().value(), "como máximo 12 por minuto por enlace");
    }
}
