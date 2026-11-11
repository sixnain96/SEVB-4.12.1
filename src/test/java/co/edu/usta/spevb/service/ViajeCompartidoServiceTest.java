package co.edu.usta.spevb.service;

import co.edu.usta.spevb.service.ViajeCompartidoService.Actualizacion;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.jdbc.core.JdbcTemplate;
import tools.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** «Compartir mi viaje»: tokens, privacidad de lo guardado, validaciones, llegada, revocación y cierre de sesión. Sin base de datos (JdbcTemplate simulado). */
class ViajeCompartidoServiceTest {
    private final JdbcTemplate jdbc = mock(JdbcTemplate.class);
    private final ObjectMapper mapper = new ObjectMapper();
    private final ViajeCompartidoService s = new ViajeCompartidoService(jdbc, mapper);

    private tools.jackson.databind.JsonNode ruta(int puntos) throws Exception {
        var b = new StringBuilder("{\"tramos\":[[");
        for (int i = 0; i < puntos; i++) b.append(i == 0 ? "" : ",").append("[").append(-73.63 + i * 1e-5).append(",").append(4.15 + i * 1e-5).append("]");
        return mapper.readTree(b.append("]],\"etiquetas\":[\"M01\"]}").toString());
    }

    @Test
    void losTokensSonImpredeciblesDe256BitsYSoloSeGuardaSuHash() {
        String a = s.nuevoToken(), b = s.nuevoToken();
        assertEquals(43, a.length(), "32 bytes en base64url sin relleno");
        assertTrue(ViajeCompartidoService.formatoValido(a));
        assertNotEquals(a, b);
        String h = ViajeCompartidoService.hash(a);
        assertEquals(64, h.length());
        assertFalse(h.contains(a));
        assertEquals(h, ViajeCompartidoService.hash(a), "determinista");
        for (String malo : new String[]{null, "", "corto", "x".repeat(44), a.substring(1) + "+", a.substring(0, 42) + "="}) assertFalse(ViajeCompartidoService.formatoValido(malo), String.valueOf(malo));
    }

    @Test
    void alCrearNoSeGuardaNingunTokenEnClaroNiDatosPersonales() throws Exception {
        when(jdbc.queryForObject(anyString(), eq(Long.class), any(Object[].class))).thenReturn(1_800_000_000L);
        var c = s.crear(7L, ruta(5));
        assertNotEquals(c.lectura(), c.escritura(), "el de lectura no sirve para escribir");
        ArgumentCaptor<Object> a = ArgumentCaptor.forClass(Object.class);
        verify(jdbc).queryForObject(anyString(), eq(Long.class), a.capture(), a.capture(), a.capture(), a.capture(), a.capture());
        List<Object> v = a.getAllValues();
        assertEquals(ViajeCompartidoService.hash(c.lectura()), v.get(0));
        assertEquals(ViajeCompartidoService.hash(c.escritura()), v.get(1));
        assertEquals(7L, v.get(2));
        assertTrue(v.stream().noneMatch(x -> x != null && (x.toString().contains(c.lectura()) || x.toString().contains(c.escritura()))), "ni la ruta ni nada contiene el token");
        assertEquals(10_800.0, (double) v.get(4), "vida máxima de 3 horas");
        verify(jdbc).update(contains("DELETE FROM viajes_compartidos WHERE expira_en < NOW()"));      // limpieza de lo vencido
    }

    @Test
    void sinViajeEnCursoOConUnaRutaInvalidaNoSeCreaNada() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, null));
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, mapper.readTree("{}")));
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, mapper.readTree("{\"tramos\":[]}")));
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, mapper.readTree("{\"tramos\":[[[-73.6,4.1]]]}")), "una sola coordenada no es un recorrido");
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, mapper.readTree("{\"tramos\":[[[-73.6,4.1],[-73.6,95]]]}")), "latitud fuera de rango");
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, mapper.readTree("{\"tramos\":[[[-73.6,4.1],[\"x\",4]]]}")));
        assertThrows(IllegalArgumentException.class, () -> s.crear(null, ruta(ViajeCompartidoService.MAX_PUNTOS + 1)), "tamaño acotado");
        verify(jdbc, never()).queryForObject(anyString(), eq(Long.class), any(Object[].class));
    }

    @Test
    void laRutaGuardadaSeRedondeaYLasEtiquetasSeLimpian() throws Exception {
        var limpia = mapper.readTree(s.limpiarRuta(mapper.readTree("{\"tramos\":[[[-73.6300012345,4.1500098765],[-73.62,4.16]]],\"etiquetas\":[\"<b>M01</b>\\n\"]}")));
        assertEquals(-73.63, limpia.at("/tramos/0/0/0").asDouble());
        assertFalse(limpia.at("/etiquetas/0").asString().contains("<"));
        assertFalse(limpia.has("destino") || limpia.has("origen") || limpia.has("nombre"), "sin direcciones ni nombres de lugares");
    }

    @Test
    void validaFaseProgresoPosicionYEta() {
        var ok = new Actualizacion("en_bus", 0, 0.5, 4.15, -73.63, 12.0, 8);
        assertDoesNotThrow(() -> ViajeCompartidoService.validar(ok));
        for (var malo : List.of(new Actualizacion("hackear", 0, 0.5, null, null, null, null), new Actualizacion("en_bus", 2, 0.5, null, null, null, null),
                new Actualizacion("en_bus", 0, 1.5, null, null, null, null), new Actualizacion("en_bus", 0, Double.NaN, null, null, null, null),
                new Actualizacion("en_bus", 0, 0.5, 4.15, null, null, null), new Actualizacion("en_bus", 0, 0.5, 91.0, -73.0, null, null),
                new Actualizacion("en_bus", 0, 0.5, 4.0, -181.0, null, null), new Actualizacion("en_bus", 0, 0.5, 4.0, -73.0, -1.0, null),
                new Actualizacion("en_bus", 0, 0.5, 4.0, -73.0, null, 99999))) {
            assertThrows(IllegalArgumentException.class, () -> ViajeCompartidoService.validar(malo), malo.toString());
        }
        assertThrows(IllegalArgumentException.class, () -> ViajeCompartidoService.validar(null));
    }

    @Test
    void actualizarUsaSoloElTokenDeEscrituraYUnTokenMalFormadoNoTocaLaBase() {
        String w = s.nuevoToken();
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);
        assertTrue(s.actualizar(w, new Actualizacion("caminar", 0, 0.2, 4.15, -73.63, 10.0, 12)));
        ArgumentCaptor<String> sql = ArgumentCaptor.forClass(String.class);
        verify(jdbc).update(sql.capture(), any(Object[].class));
        assertTrue(sql.getValue().contains("escritura_hash = ?") && !sql.getValue().contains("lectura_hash"), "el enlace de lectura nunca modifica el viaje");
        assertFalse(s.actualizar("mal", new Actualizacion("caminar", 0, 0.2, null, null, null, null)));
        assertFalse(s.actualizar(null, new Actualizacion("caminar", 0, 0.2, null, null, null, null)));
        verifyNoMoreInteractions(jdbc);
    }

    @Test
    void sinFilaVigenteActualizarResponde_noDisponible() {
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(0);
        assertFalse(s.actualizar(s.nuevoToken(), new Actualizacion("caminar", 0, 0.2, 4.15, -73.63, null, null)), "vencido o revocado: sin detalles");
    }

    @Test
    void alLlegarSeBorranLasCoordenadasYElEstadoFinalDuraDiezMinutos() {
        when(jdbc.update(anyString(), any(Object[].class))).thenReturn(1);
        assertTrue(s.actualizar(s.nuevoToken(), new Actualizacion("llegaste", 1, 1, 4.15, -73.63, 5.0, 0)));
        ArgumentCaptor<String> sql = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<Object> par = ArgumentCaptor.forClass(Object.class);
        verify(jdbc).update(sql.capture(), par.capture(), par.capture());
        assertTrue(sql.getValue().contains("lat = NULL") && sql.getValue().contains("lng = NULL") && sql.getValue().contains("estado = 'llego'"), sql.getValue());
        assertEquals(600.0, (double) par.getAllValues().get(0));
        assertTrue(par.getAllValues().stream().noneMatch(x -> x instanceof Double d && Math.abs(d - 4.15) < 1e-9), "las coordenadas recibidas ni siquiera se usan");
    }

    @Test
    void revocarBorraLaFilaPorHashYEsIdempotente() {
        when(jdbc.update(startsWith("DELETE FROM viajes_compartidos WHERE escritura_hash"), anyString())).thenReturn(1, 0);
        String w = s.nuevoToken();
        assertTrue(s.revocar(w));
        assertFalse(s.revocar(w), "ya no existe");
        assertFalse(s.revocar("mal"));
        verify(jdbc, times(2)).update(anyString(), eq(ViajeCompartidoService.hash(w)));
    }

    @Test
    void consultarConUnTokenInvalidoNoTocaLaBaseYVencidoORevocadoDaLoMismo() {
        assertTrue(s.consultar("malo").isEmpty());
        assertTrue(s.consultar(null).isEmpty());
        verifyNoInteractions(jdbc);
        when(jdbc.queryForList(anyString(), any(Object[].class))).thenReturn(List.of());
        assertTrue(s.consultar(s.nuevoToken()).isEmpty(), "vencido, revocado o inexistente: indistinguibles");
    }

    @Test
    void laVistaPublicaDeUnViajeQueLlegoNuncaTraeCoordenadas() {
        var fila = new java.util.HashMap<String, Object>(Map.of("estado", "llego", "fase", "llegaste", "leg", 1, "progreso", 1.0f, "version", 5, "act", 1L, "exp", 2L));
        fila.put("lat", 4.15); fila.put("lng", -73.63); fila.put("eta_min", 0); fila.put("ruta", null);
        when(jdbc.queryForList(anyString(), any(Object[].class))).thenReturn(List.of(fila));
        var v = s.consultar(s.nuevoToken()).orElseThrow();
        assertNull(v.lat());
        assertNull(v.lng());
        assertEquals("llego", v.estado());
    }

    @Test
    void cerrarSesionBorraLosEnlacesDeEsaPersonaAntesDeBorrarLaSesion() {
        var j = mock(JdbcTemplate.class);
        var cuentas = new CuentaService(j, mapper, "");
        cuentas.cerrarSesion("t".repeat(43));
        var orden = inOrder(j);
        orden.verify(j).update(contains("DELETE FROM viajes_compartidos WHERE usuario_id = (SELECT usuario_id FROM sesiones"), anyString());
        orden.verify(j).update(contains("DELETE FROM sesiones WHERE token_hash"), anyString());
        cuentas.cerrarTodas(9L);
        verify(j).update(contains("DELETE FROM viajes_compartidos WHERE usuario_id = ?"), eq(9L));
    }
}
