package co.edu.usta.spevb.recursos;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.awt.image.BufferedImage;
import java.io.InputStream;
import java.util.List;
import javax.imageio.ImageIO;
import org.junit.jupiter.api.Test;

/** Los seis avatares regionales (4.15.1) existen en el classpath final, miden 128 × 128, se decodifican y conservan la transparencia en las esquinas. */
class AvataresRecursosTest {

    private static final List<String> ARCHIVOS = List.of("chiguiro", "danta", "venado", "guacamaya", "moriche", "saman");

    @Test
    void lasSeisImagenesEstanEnElClasspathConTamanoYTransparencia() throws Exception {
        for (String nombre : ARCHIVOS) {
            try (InputStream in = getClass().getResourceAsStream("/static/img/avatares/" + nombre + ".png")) {
                assertNotNull(in, "falta /static/img/avatares/" + nombre + ".png en el classpath");
                BufferedImage img = ImageIO.read(in);
                assertNotNull(img, nombre + ".png no se puede decodificar");
                assertEquals(128, img.getWidth(), nombre + " debe medir 128 px de ancho");
                assertEquals(128, img.getHeight(), nombre + " debe medir 128 px de alto");
                assertTrue(img.getColorModel().hasAlpha(), nombre + " conserva canal alfa");
                int[] esquinas = {img.getRGB(0, 0), img.getRGB(127, 0), img.getRGB(0, 127), img.getRGB(127, 127)};
                for (int argb : esquinas) {
                    assertEquals(0, argb >>> 24, nombre + ": las esquinas son transparentes");
                }
                assertEquals(255, img.getRGB(64, 64) >>> 24, nombre + ": el centro es opaco");
            }
        }
    }
}
