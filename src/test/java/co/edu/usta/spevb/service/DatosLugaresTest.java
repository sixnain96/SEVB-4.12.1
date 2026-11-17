package co.edu.usta.spevb.service;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import static org.junit.jupiter.api.Assertions.*;

/** Lugares guardados (Fase C): tipos únicos, ids estables, nombre acotado, lápidas contra el borrado que reaparece y compatibilidad con favoritos antiguos. */
class DatosLugaresTest {
    private final ObjectMapper m = new ObjectMapper();
    private final DatosUsuario d = new DatosUsuario(m);

    private JsonNode lim(String json) throws Exception { return d.limpiar("lugares", m.readTree(json)); }

    @Test
    void conservaTipoIdYMomentoYRecortaElNombre() throws Exception {
        var r = lim("[{\"id\":\"a1\",\"nombre\":\"  Casa de mamá con un nombre larguísimo que supera los cuarenta caracteres  \",\"lat\":4.14,\"lng\":-73.62,\"tipo\":\"otro\",\"v\":1700000000000,\"x\":\"<script>\"}]");
        var l = r.get(0);
        assertEquals("a1", l.get("id").asString());
        assertEquals("otro", l.get("tipo").asString());
        assertEquals(1700000000000L, l.get("v").asLong());
        assertTrue(l.get("nombre").asString().length() <= DatosUsuario.NOMBRE_LUGAR_MAX);
        assertFalse(l.has("x"), "los campos desconocidos no se guardan");
        // un tipo desconocido se ignora (no rompe el lugar)
        assertFalse(lim("[{\"id\":\"b\",\"nombre\":\"X\",\"lat\":4.1,\"lng\":-73.6,\"tipo\":\"hackeado\"}]").get(0).has("tipo"));
    }

    @Test
    void unFavoritoAntiguoSinTipoNiMomentoSigueValiendo() throws Exception {
        var r = lim("[{\"id\":\"zz\",\"nombre\":\"Casa\",\"lat\":4.1,\"lng\":-73.6}]");
        assertEquals(1, r.size());
        assertFalse(r.get(0).has("tipo") || r.get(0).has("v"));
    }

    @Test
    void soloUnaCasaYUnTrabajoVivosYManda_laMasReciente() throws Exception {
        var r = lim("""
                [{"id":"c1","nombre":"Casa","lat":4.1,"lng":-73.6,"tipo":"casa","v":100},
                 {"id":"c2","nombre":"Casa nueva","lat":4.2,"lng":-73.6,"tipo":"casa","v":200},
                 {"id":"t1","nombre":"Trabajo","lat":4.1,"lng":-73.5,"tipo":"trabajo","v":50},
                 {"id":"o1","nombre":"Universidad","lat":4.1,"lng":-73.4,"tipo":"otro","v":10},
                 {"id":"o2","nombre":"Universidad","lat":4.1,"lng":-73.4,"tipo":"otro","v":11}]""");
        var ids = new java.util.ArrayList<String>();
        r.forEach(x -> ids.add(x.get("id").asString()));
        assertTrue(ids.contains("c2") && !ids.contains("c1"), ids.toString());
        assertTrue(ids.contains("t1") && ids.contains("o1") && ids.contains("o2"), "los personalizados pueden repetirse de nombre: el duplicado accidental lo evita la interfaz");
    }

    @Test
    void elMismoIdNoSeRepiteYLapidaMasNuevaGanaALaEdicionVieja() throws Exception {
        long ahora = System.currentTimeMillis();
        var r = lim("[{\"id\":\"u\",\"nombre\":\"Uni\",\"lat\":4.1,\"lng\":-73.6,\"v\":" + (ahora - 5000) + "},{\"id\":\"u\",\"borrado\":true,\"v\":" + ahora + "}]");
        assertEquals(1, r.size());
        assertTrue(r.get(0).get("borrado").asBoolean());
        assertFalse(r.get(0).has("nombre") || r.get(0).has("lat"), "una lápida no guarda ni nombre ni coordenadas");
    }

    @Test
    void laLapidaViejaSeDescartaYLasInvalidasNoEntran() throws Exception {
        long viejo = System.currentTimeMillis() - 90L * 86_400_000L;
        assertEquals(0, lim("[{\"id\":\"a\",\"borrado\":true,\"v\":" + viejo + "},{\"id\":\"b\",\"borrado\":true},{\"borrado\":true,\"v\":5}]").size());
    }

    @Test
    void hastaTreintaVivosYLasLapidasNoCuentanParaElTope() throws Exception {
        var sb = new StringBuilder("[");
        long ahora = System.currentTimeMillis();
        for (int i = 0; i < 40; i++) sb.append("{\"id\":\"p").append(i).append("\",\"nombre\":\"L").append(i).append("\",\"lat\":4.1,\"lng\":-73.6,\"tipo\":\"otro\",\"v\":").append(i + 1).append("},");
        for (int i = 0; i < 5; i++) sb.append("{\"id\":\"d").append(i).append("\",\"borrado\":true,\"v\":").append(ahora).append("},");
        sb.setLength(sb.length() - 1); sb.append("]");
        var r = lim(sb.toString());
        long vivos = 0, lapidas = 0;
        for (JsonNode x : r) { if (x.path("borrado").asBoolean(false)) lapidas++; else vivos++; }
        assertEquals(30, vivos);
        assertEquals(5, lapidas);
    }

    @Test
    void coordenadasFueraDeRangoONombreVacioNoEntran() throws Exception {
        assertEquals(0, lim("[{\"id\":\"a\",\"nombre\":\"   \",\"lat\":4.1,\"lng\":-73.6},{\"id\":\"b\",\"nombre\":\"X\",\"lat\":99,\"lng\":-73.6},{\"id\":\"c\",\"nombre\":\"X\",\"lat\":4.1}]").size());
    }
}
