package co.edu.usta.spevb.dto;

/**
 * precision identifica el tipo de punto, NO certifica su exactitud física. {@code googleId} es el identificador del lugar en Google (solo en resultados de Google): el navegador lo compara con el
 * de la opción que tocó la persona; NO es el identificador interno de SEVB ({@code id}). {@code nomenclatura} es la dirección armada con los componentes estructurados de Google (vía + placa, p. ej.
 * «Carrera 27 # 35A-50») cuando Google los trae; sirve para comparar por componentes y no por cifras sueltas.
 */
public record LugarResponse(
        Long id,
        String nombre,
        String direccion,
        double lat,
        double lng,
        String fuente,
        boolean confirmado,
        String precision,
        String googleId,
        String nomenclatura
) {
    public LugarResponse(Long id, String nombre, String direccion, double lat, double lng, String fuente, boolean confirmado, String precision, String googleId) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado, precision, googleId, null);
    }

    public LugarResponse(Long id, String nombre, String direccion, double lat, double lng, String fuente, boolean confirmado, String precision) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado, precision, null, null);
    }

    // Compatible con el contrato de los lugares anteriores.
    public LugarResponse(Long id, String nombre, String direccion, double lat,
                         double lng, String fuente, boolean confirmado) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado,
                confirmado ? "VERIFICADO_LOCAL" : "SIN_VERIFICAR", null, null);
    }
}
