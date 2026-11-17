package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;
import co.edu.usta.spevb.dto.LugarResponse;
import co.edu.usta.spevb.repository.LugarRepository;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * ANTES / DESPUÉS con las mismas 16 entradas de Villavicencio y un Google SIMULADO (predicciones fijas y ficticias). Mide la LÓGICA de SEVB: ¿la opción pedida queda entre las primeras tres
 * después del filtro?, ¿lo que se confirma es el lugar tocado?, ¿cuántas consultas salen? NO mide la calidad ni la velocidad reales de Google (eso queda pendiente con un entorno autorizado).
 * El filtro «antes» es una copia fiel del criterio anterior (comparación numérica exacta de los dos primeros números, sin prefijo, sin Bis, sin comprobar la identidad del lugar).
 * Escribe la tabla en target/comparacion-busqueda.md.
 */
class ComparacionBusquedaTest {
    private record P(String id, String principal, String secundario) {}
    private record Caso(String escrito, List<P> google, String esperado, boolean valido) {}

    private static P p(String id, String principal) { return new P(id, principal, "Villavicencio, Meta"); }

    private static final List<Caso> CASOS = List.of(
            new Caso("Calle 3", List.of(p("c30", "Calle 30"), p("c3", "Calle 3"), p("c38", "Calle 38"), p("c40", "Calle 40")), "c30", true),
            new Caso("Carrera 22 #3", List.of(p("k38", "Carrera 22 #38-10"), p("k3", "Carrera 22 #3-10"), p("k39", "Carrera 22 #39-10")), "k38", true),
            new Caso("Carrera 22 #38-1", List.of(p("k38", "Carrera 22 #38-10"), p("k381", "Carrera 22 #38-12"), p("k39", "Carrera 22 #39-10")), "k38", true),
            new Caso("Cra. 22 #38-10", List.of(p("k38", "Carrera 22 #38-10"), p("k39", "Carrera 22 #39-10")), "k38", true),
            new Caso("Kra 22 38 10", List.of(p("k38", "Carrera 22 #38-10")), "k38", true),
            new Caso("Cll 30", List.of(p("c30a", "Calle 30A"), p("c30", "Calle 30"), p("c30s", "Calle 30 Sur")), "c30", true),
            new Caso("Calle 30 Sur", List.of(p("c30n", "Calle 30 Norte"), p("c30s", "Calle 30 Sur"), p("c30", "Calle 30")), "c30s", true),
            new Caso("Calle 30A", List.of(p("c30", "Calle 30"), p("c30a", "Calle 30A")), "c30a", true),
            new Caso("Unicentro", List.of(new P("uni", "Unicentro Villavicencio", "Carrera 33, Villavicencio"), new P("uni2", "Unicentro Oriental", "Calle 9, Villavicencio")), "uni", true),
            new Caso("clinica meta", List.of(new P("sedeC", "Clínica Meta", "Calle 38 #31-10, Villavicencio"), new P("sedeN", "Clínica Meta", "Carrera 40 #5-20, Villavicencio")), "sedeN", true),
            new Caso("terminal de transportes", List.of(new P("term", "Terminal de Transportes de Villavicencio", "Anillo Vial, Villavicencio")), "term", true),
            new Caso("universidad llanos", List.of(new P("ul", "Universidad de los Llanos", "Kilómetro 12 Vía Puerto López, Villavicencio")), "ul", true),
            new Caso("barzal", List.of(new P("bz", "Barzal", "Villavicencio, Meta")), "bz", true),
            new Caso("parque fundadores", List.of(new P("pf", "Parque Los Fundadores", "Villavicencio, Meta")), "pf", true),
            new Caso("clinica villavicencio", List.of(new P("v", "Villavicencio", "Meta, Colombia")), null, false),      // la ciudad sola no demuestra que sea la clínica
            new Caso("calle 99999 sin sentido", List.of(), null, false));

    private final CityArea area = new CityArea("Villavicencio", "Meta", "Colombia", 3.95, 4.35, -73.85, -73.45);

    // ---- criterio ANTERIOR (copia): primeros dos números exactos, sin prefijo, sin Bis, sin sentido en predicciones
    private static Object invocar(String nombre, Object... args) throws Exception {
        Class<?>[] t = new Class<?>[args.length];
        for (int i = 0; i < args.length; i++) t[i] = args[i].getClass();
        Method m = DireccionesHibridasService.class.getDeclaredMethod(nombre, t);
        m.setAccessible(true);
        return m.invoke(null, args);
    }

    @SuppressWarnings("unchecked")
    private static boolean antes(String raw, String title) throws Exception {
        String query = (String) invocar("normalizar", raw), candidato = (String) invocar("normalizar", title);
        if (candidato.isBlank() || DireccionesHibridasService.esSoloCiudad(title) && DireccionesHibridasService.busquedaEspecifica(raw)) return false;
        if (query.matches("^(CARRERA|CALLE|AVENIDA|DIAGONAL|TRANSVERSAL)\\s+.*")) {
            if (!candidato.startsWith(query.split(" ")[0] + " ")) return false;
            List<String> a = (List<String>) invocar("numeros", query), b = (List<String>) invocar("numeros", candidato);
            int comprobar = Math.min(2, a.size());
            if (b.size() < comprobar) return false;
            for (int i = 0; i < comprobar; i++) if (!a.get(i).equals(b.get(i))) return false;
            return true;
        }
        return DireccionesHibridasService.sugerenciaRelevante(raw, title);
    }

    @Test void tablaAntesYDespues() throws Exception {
        var sb = new StringBuilder("| Entrada | Esperada | Antes: top-3 | Después: top-3 | Consultas a Google |\n|---|---|---|---|---|\n");
        int validos = 0, antesTop3 = 0, despuesTop3 = 0, negOkAntes = 0, negOkDespues = 0, negativos = 0, consultas = 0;
        for (Caso c : CASOS) {
            // DESPUÉS: el servicio real con un Google simulado
            var repo = mock(LugarRepository.class);
            var google = mock(GoogleDireccionesService.class);
            when(google.activo()).thenReturn(true);
            when(google.sugerir(anyString(), any())).thenReturn(c.google().stream().map(x -> new GoogleDireccionesService.Sugerencia(x.principal() + ", " + x.secundario(), x.id(), x.principal(), x.secundario())).toList());
            var s = new LugarService(repo, mock(GeocodingService.class), area, mock(DireccionesHibridasService.class), mock(DireccionesLocalesService.class));
            s.usarGoogle(google); s.soloGoogle(true);
            var despues = s.sugerirDetallado(c.escrito(), "sesion-abc-123456").sugerencias().stream().map(x -> x.magicKey().substring(2)).toList();
            verify(google, times(1)).sugerir(anyString(), any());      // una consulta por pausa
            consultas++;
            // ANTES: el criterio anterior sobre las mismas predicciones, en el orden de Google
            List<String> antesIds = new ArrayList<>();
            for (P x : c.google()) if (antes(c.escrito(), x.principal() + ", " + x.secundario())) antesIds.add(x.id());
            boolean aOk, dOk;
            if (c.valido()) {
                validos++;
                aOk = antesIds.subList(0, Math.min(3, antesIds.size())).contains(c.esperado());
                dOk = despues.subList(0, Math.min(3, despues.size())).contains(c.esperado());
                if (aOk) antesTop3++;
                if (dOk) despuesTop3++;
            } else {
                negativos++;
                aOk = antesIds.isEmpty(); dOk = despues.isEmpty();
                if (aOk) negOkAntes++;
                if (dOk) negOkDespues++;
            }
            sb.append("| ").append(c.escrito()).append(" | ").append(c.valido() ? c.esperado() : "(ninguna)").append(" | ").append(aOk ? "sí" : "NO").append(" | ").append(dOk ? "sí" : "NO").append(" | 1 |\n");
        }
        // selección (REAL en el servicio, con un detalle simulado): se toca la sede centro y Google devuelve la sede pedida (3 veces) o OTRA sede del mismo proveedor (1 vez)
        int seleccionesCasos = 0, equivocadasAntes = 0, equivocadasDespues = 0;
        for (String devuelto : List.of("sedeC", "sedeC", "sedeC", "sedeN")) {
            seleccionesCasos++;
            var google = mock(GoogleDireccionesService.class);
            when(google.activo()).thenReturn(true);
            when(google.resolver(eq("sedeC"), any(), any())).thenReturn(new ResultadoLugares(List.of(new LugarResponse(null, "Clínica Meta", "x", 4.14, -73.62, "Google Maps", false, "LUGAR", devuelto)), 0));
            var s = new LugarService(mock(LugarRepository.class), mock(GeocodingService.class), area, mock(DireccionesHibridasService.class), mock(DireccionesLocalesService.class));
            s.usarGoogle(google); s.soloGoogle(true);
            var r = s.buscarDetallado("Clínica Meta", "g:sedeC", "sesion-abc-123456");
            boolean confirmo = !r.eleccionFallida() && !r.lugares().isEmpty();
            if (!devuelto.equals("sedeC")) { equivocadasAntes++; if (confirmo) equivocadasDespues++; }      // antes se aceptaba siempre el primer resultado del proveedor esperado
        }
        sb.append("\n**Casos válidos con la opción pedida entre las 3 primeras:** antes ").append(antesTop3).append("/").append(validos).append(" · después ").append(despuesTop3).append("/").append(validos)
                .append("  \n**Casos sin coincidencia válida resueltos como «nada»:** antes ").append(negOkAntes).append("/").append(negativos).append(" · después ").append(negOkDespues).append("/").append(negativos)
                .append("  \n**Selecciones que confirman un lugar equivocado:** antes ").append(equivocadasAntes).append(" de ").append(seleccionesCasos)
                .append(" (la sede equivocada se aceptaba) · después ").append(equivocadasDespues).append(" de ").append(seleccionesCasos).append(" (se rechaza y se pide volver a elegir)")
                .append("  \n**Consultas a Google:** ").append(consultas).append(" para ").append(CASOS.size())
                .append(" entradas (una por pausa; el filtro no añade ninguna) — idéntico antes y después.\n");
        Files.writeString(Path.of("target", "comparacion-busqueda.md"), sb.toString());
        System.out.println(sb);
        assertTrue(despuesTop3 > antesTop3, "el filtro nuevo encuentra más opciones pedidas que el anterior");
        assertEquals(validos, despuesTop3, "todas las opciones pedidas quedan entre las tres primeras");
        assertEquals(negativos, negOkDespues);
        assertEquals(0, equivocadasDespues);
    }
}
