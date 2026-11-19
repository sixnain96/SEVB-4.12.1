package co.edu.usta.spevb.config;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.*;

/**
 * index.html carga un solo archivo de estilos, css/app.min.css, que sale de juntar y minificar las hojas de css/app.sources.txt
 * (scripts/build-css.mjs). Estas pruebas evitan que el archivo junto quede desactualizado respecto a las hojas de origen:
 * si editas un CSS y no lo regeneras, la página mostraría estilos viejos.
 */
class CssBundleTest {
    private static String leer(String ruta) throws Exception {
        try (var in = CssBundleTest.class.getResourceAsStream("/static" + ruta)) {
            assertNotNull(in, "falta " + ruta);
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    /** Hojas de origen, en el orden de app.sources.txt. */
    private static List<String> fuentes() throws Exception {
        return leer("/css/app.sources.txt").lines().map(String::trim).filter(l -> !l.isEmpty() && !l.startsWith("#")).toList();
    }

    @Test void bundleIsUpToDateWithItsSources() throws Exception {
        StringBuilder unido = new StringBuilder();
        for (String f : fuentes()) {
            if (unido.length() > 0) unido.append('\n');
            unido.append(leer("/css/" + f).replace("\r\n", "\n"));   // mismos saltos de línea que scripts/build-css.mjs (Windows y Linux)
        }
        String huella = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(unido.toString().getBytes(StandardCharsets.UTF_8)));
        var m = Pattern.compile("fuente-sha256:\\s*([0-9a-f]{64})").matcher(leer("/css/app.min.css"));
        assertTrue(m.find(), "app.min.css no trae la huella de sus hojas: genéralo con  node scripts/build-css.mjs");
        assertEquals(huella, m.group(1),
                "app.min.css está desactualizado respecto a las hojas de css/app.sources.txt: ejecuta  node scripts/build-css.mjs  y súbelo junto con tus cambios");
    }

    @Test void bundleIsSmallerThanTheSourcesAndHasContent() throws Exception {
        int origen = 0;
        for (String f : fuentes()) origen += leer("/css/" + f).length();
        int junto = leer("/css/app.min.css").length();
        assertTrue(junto > 50_000, "app.min.css parece vacío o incompleto");
        assertTrue(junto < origen, "app.min.css debería pesar menos que las hojas sueltas");
    }

    @Test void indexLoadsOnlyTheBundleAndOtherPagesKeepTheirSheets() throws Exception {
        String html = leer("/index.html");
        assertTrue(html.contains("href=\"/css/app.min.css\""), "index.html debe cargar /css/app.min.css");
        for (String f : fuentes())
            assertFalse(html.contains("href=\"/css/" + f + "\""), "index.html no debe cargar /css/" + f + " por separado: ya va dentro de app.min.css");
        // las demás páginas siguen usando styles.css y mapa.css sueltas, así que no pueden desaparecer ni de las fuentes ni del caché sin conexión
        String sw = leer("/sw.js");
        assertTrue(sw.contains("\"/css/app.min.css\"") && sw.contains("\"/css/styles.css\"") && sw.contains("\"/css/mapa.css\""),
                "sw.js debe guardar app.min.css, styles.css y mapa.css para usar la app sin conexión");
    }

    @Test void everySourceExists() throws Exception {
        assertFalse(fuentes().isEmpty());
        for (String f : fuentes()) assertFalse(leer("/css/" + f).isBlank(), f + " está vacía");
    }
}
