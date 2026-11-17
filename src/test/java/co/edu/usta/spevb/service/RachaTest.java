package co.edu.usta.spevb.service;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/** Racha de viajes (Fase D) con los MISMOS vectores que usa el espejo de JavaScript (src/test/resources/racha-vectores.json). */
class RachaTest {
    private final JsonNode vectores;

    RachaTest() throws Exception {
        try (InputStream in = getClass().getResourceAsStream("/racha-vectores.json")) {
            vectores = new ObjectMapper().readTree(in);
        }
    }

    @Test
    void cadaVectorDaLaRachaActualLaMejorYLaEstricta() {
        for (JsonNode v : vectores.get("rachas")) {
            List<LocalDate> dias = new ArrayList<>();
            v.get("dias").forEach(d -> dias.add(LocalDate.parse(d.asString())));
            var r = Racha.calcular(dias, LocalDate.parse(v.get("hoy").asString()));
            String que = v.get("nombre").asString();
            assertEquals(v.get("actual").asInt(), r.actual(), "actual: " + que);
            assertEquals(v.get("mejor").asInt(), r.mejor(), "mejor: " + que);
            assertEquals(v.get("estricta").asInt(), r.mejorEstricta(), "estricta: " + que);
        }
    }

    @Test
    void elDiaSeCalculaEnBogotaYNoEnLaZonaDelServidor() {
        for (JsonNode v : vectores.get("dias")) {
            long ms = v.get("ms").asLong();
            assertEquals(LocalDate.parse(v.get("dia").asString()), Racha.diaDe(ms), "día de " + ms);
            assertEquals(v.get("hora").asInt(), Racha.horaDe(ms), "hora de " + ms);
        }
    }

    @Test
    void elCatalogoConservaElSignificadoAntiguoDeLosLogrosDeRacha() {
        // «3 días seguidos» y «Una semana» siguen pidiendo días CONSECUTIVOS: cuatro días alternos (racha con gracia de 4) NO los dan.
        var alternos = new LogrosService.Metricas(4, 0, 4, 4, 1, false, false, false);
        assertFalse(LogrosService.desbloqueados(alternos).contains("racha3"));
        var seguidos = new LogrosService.Metricas(7, 0, 7, 7, 7, false, false, false);
        assertTrue(LogrosService.desbloqueados(seguidos).containsAll(List.of("racha3", "racha7")));
        // «Viajero del Llano»: 30 viajes y una racha (con gracia) de al menos 7 días
        assertFalse(LogrosService.desbloqueados(new LogrosService.Metricas(29, 0, 7, 7, 7, false, false, false)).contains("llano"));
        assertTrue(LogrosService.desbloqueados(new LogrosService.Metricas(30, 0, 7, 7, 1, false, false, false)).contains("llano"));
        // practicar solo da «Aprendiz» (sin viajes ni racha)
        assertEquals(List.of("practica"), LogrosService.desbloqueados(new LogrosService.Metricas(0, 0, 0, 0, 0, false, false, true)));
    }
}
