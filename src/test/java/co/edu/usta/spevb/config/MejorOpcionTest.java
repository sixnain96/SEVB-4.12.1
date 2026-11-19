package co.edu.usta.spevb.config;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tarjeta «Mejor opción» tras buscar rutas: qué bus tomar, en grande, y qué otros buses sirven. Guardas de lectura del código (el comportamiento se comprobó en el navegador con una búsqueda real).
 */
class MejorOpcionTest {
    private static String leer(String ruta) throws Exception {
        try (var in = MejorOpcionTest.class.getResourceAsStream("/static" + ruta)) {
            assertNotNull(in, "falta " + ruta);
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test void laTarjetaVaEntreBuscarRutasYIniciarViajeFueraDeLaBarraPegajosa() throws Exception {
        String html = leer("/index.html");
        int fila = html.indexOf("class=\"plan-actions\""), tarjeta = html.indexOf("id=\"mejorOpcion\""), barra = html.indexOf("id=\"startTripBar\"");
        assertTrue(fila > 0 && tarjeta > fila && barra > tarjeta, "#mejorOpcion va después de «Buscar rutas» y antes de #startTripBar (no dentro: la barra es sticky y una tarjeta alta taparía la lista)");
        assertTrue(html.contains("/js/mejor-opcion.js"));
        assertTrue(html.indexOf("/js/mejor-opcion.js") > html.indexOf("/js/planner.js"), "el enganche va después del planificador");
    }

    @Test void seGuardaParaUsarSinConexionYEstaEnElPaqueteDeCss() throws Exception {
        assertTrue(leer("/sw.js").contains("\"/js/mejor-opcion.js\""), "sw.js debe guardar mejor-opcion.js");
        assertTrue(leer("/css/app.sources.txt").contains("mejor-opcion.css"), "mejor-opcion.css forma parte de app.min.css");
        assertTrue(leer("/css/app.min.css").contains(".mo-card"), "el paquete ya incluye los estilos de la tarjeta (node scripts/build-css.mjs)");
    }

    @Test void elPlanificadorSoloGuardaDatosEnLaTarjetaSinTocarLoDemas() throws Exception {
        String js = leer("/js/planner.js");
        assertTrue(js.contains("card._mejor = dm"), "decorar() deja los datos de «Mejor opción» en la tarjeta");
        assertTrue(js.contains("} catch { return null; }"), "un dato raro nunca rompe los resultados");
    }

    @Test void soloAfirmaLaMejorOpcionSiElServidorMarcoUnaRecomendada() throws Exception {
        String js = leer("/js/mejor-opcion.js");
        assertTrue(js.contains("o.recomendada") && js.contains("sin recomendación del servidor"), "sin recomendada no se muestra la tarjeta");
        assertTrue(js.contains("c.open = true"), "al tocar un bus se abre la tarjeta de la lista (el planificador la dibuja como siempre)");
        assertTrue(js.contains("spevb-ver-opciones"), "«Ver las N» abre la lista completa");
        assertFalse(js.contains("innerHTML ="), "los datos entran con textContent, nunca con innerHTML");
    }

    @Test void losNombresSeEscribenBienYSeRespetaReducirMovimiento() throws Exception {
        String js = leer("/js/mejor-opcion.js"), css = leer("/css/mejor-opcion.css");
        for (String n : new String[]{"Porfía", "Galán", "Covisán", "Álamos"}) assertTrue(js.contains(n), "falta el nombre " + n);
        assertTrue(css.contains("prefers-reduced-motion: reduce") && css.contains("html[data-motion=\"reduce\"]"));
        assertTrue(css.contains("body.viaje-activo .mejor-opcion"), "con un viaje en curso la tarjeta se oculta");
    }

    @Test void elPanelMideLaAlturaCompactaConLaTarjeta() throws Exception {
        String js = leer("/js/sheet.js");
        assertTrue(js.contains("medirPeekResultado") && js.contains("mejorOpcion"), "con la tarjeta, la vista compacta mide lo justo para verla con «Iniciar viaje»");
        assertTrue(js.contains("0.62"), "tope del 62 % de la pantalla");
    }
}
