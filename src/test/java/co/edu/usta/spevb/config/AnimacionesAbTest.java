package co.edu.usta.spevb.config;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Animaciones de los campos A y B, del menú y de los logros (Fase P). El JS solo pone clases y el CSS tiene todo el movimiento, incluida su versión
 * «reducir movimiento»; estas pruebas comprueban que las piezas estén conectadas (la prueba de MotionCssTest ya exige solo transform/opacity en los keyframes).
 */
class AnimacionesAbTest {
    private static final List<String> CLASES = List.of("ab-intro", "punto-fijado", "ab-viaja", "ab-completo", "pide");

    private static String leer(String ruta) throws Exception {
        try (var in = AnimacionesAbTest.class.getResourceAsStream("/static" + ruta)) {
            assertNotNull(in, "falta " + ruta);
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test void elScriptSeCargaDespuesDelPlanificadorYSeGuardaParaUsarSinConexion() throws Exception {
        String html = leer("/index.html"), sw = leer("/sw.js");
        assertTrue(html.contains("/js/animaciones.js"));
        assertTrue(html.indexOf("/js/animaciones.js") > html.indexOf("/js/planner.js"), "animaciones.js va después de planner.js");
        assertTrue(sw.contains("\"/js/animaciones.js\""), "sw.js debe guardar animaciones.js");
    }

    @Test void cadaClaveQueElScriptPoneTieneSuEstiloYSuVersionSinMovimiento() throws Exception {
        String js = leer("/js/animaciones.js"), css = leer("/css/motion.css");
        for (String c : CLASES) {
            assertTrue(js.contains("'" + c + "'"), "animaciones.js no usa la clase " + c);
            assertTrue(css.contains("." + c), "motion.css no tiene estilo para ." + c);
        }
        int reducido = css.indexOf("movimiento reducido para lo de la Fase P");
        assertTrue(reducido > 0, "falta el bloque de movimiento reducido de la Fase P");
        String bloque = css.substring(reducido);
        for (String c : CLASES) assertTrue(bloque.contains("." + c), c + " no tiene su versión sin movimiento");
        assertTrue(bloque.contains("html[data-motion=\"reduce\"]") && bloque.contains("prefers-reduced-motion: reduce"));
        assertTrue(bloque.contains(".logro") && bloque.contains(".racha-llama") && bloque.contains(".trip-pin.pin-in::after") && bloque.contains(".menu-ico"));
    }

    @Test void elScriptEsDiscretoConLosAvisos() throws Exception {
        String js = leer("/js/animaciones.js");
        assertTrue(js.contains("MAX_AVISOS = 3"), "como mucho tres avisos seguidos");
        assertTrue(js.contains("document.hidden") && js.contains("'guiado'") && js.contains("modal-backdrop"), "no avisa con la pestaña oculta, el tutorial o un diálogo abierto");
        assertTrue(js.contains("sinMovimiento"), "respeta «reducir movimiento»");
        assertFalse(js.contains(".style."), "el JS no pone estilos: solo clases");
    }

    @Test void losLogrosSeEnumeranParaEntrarUnoTrasOtro() throws Exception {
        assertTrue(leer("/js/logros.js").contains("setProperty('--i'"));
        assertTrue(leer("/css/motion.css").contains("var(--i, 0)"));
    }

    @Test void laAnimacionDelAroDelCampoNoTapaElTextoDeLaDireccionCompleta() throws Exception {
        String css = leer("/css/motion.css");
        assertTrue(css.contains("height: 52px; border: 2px solid var(--brand)"), "el aro mide como el campo de texto, no como todo el bloque (que incluye la dirección completa)");
        assertTrue(css.contains("@media (max-height: 640px)"), "en pantallas bajas el campo mide 46 px y el aro también");
    }
}
