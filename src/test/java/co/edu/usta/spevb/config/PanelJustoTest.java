package co.edu.usta.spevb.config;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.*;

/**
 * El panel de A y B en el celular no baja solo y su vista compacta deja a la vista «Buscar rutas» y «Limpiar A y B»; la dirección completa de Google ya no se dibuja bajo los campos.
 * (Guardas de lectura del código: el comportamiento se comprobó en el navegador con A y B puestos.)
 */
class PanelJustoTest {
    private static String leer(String ruta) throws Exception {
        try (var in = PanelJustoTest.class.getResourceAsStream("/static" + ruta)) {
            assertNotNull(in, "falta " + ruta);
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test void alPonerLosDosPuntosElPanelNoBajaSolo() throws Exception {
        String js = leer("/js/sheet.js");
        assertFalse(js.contains("ambos-puntos"), "ya no se manda el panel a la vista compacta al tener A y B");
        assertFalse(js.contains("go('peek', 'ambos-puntos')"));
    }

    @Test void laVistaCompactaSeMideHastaLaFilaDeBuscarRutas() throws Exception {
        String js = leer("/js/sheet.js");
        assertTrue(js.contains("medirPeekJusto") && js.contains(".plan-actions"), "la altura compacta se mide hasta la fila «Buscar rutas»");
        assertTrue(js.contains("hayRutasBuscadas"), "con rutas ya buscadas se conserva la altura de antes (Iniciar viaje)");
        assertTrue(js.contains("0.66"), "tope del 66 % de la pantalla");
        assertTrue(js.contains("ResizeObserver"), "se vuelve a medir si cambia el contenido");
    }

    @Test void laDireccionCompletaYaNoSeDibujaBajoElCampo() throws Exception {
        String js = leer("/js/planner.js");
        assertTrue(js.contains("el.textContent = texto; el.hidden = true;"), "el texto queda oculto (tooltip y lector de pantalla), no a la vista");
        assertFalse(js.contains("el.hidden = !visible"), "ya no se muestra bajo el campo");
    }
}
