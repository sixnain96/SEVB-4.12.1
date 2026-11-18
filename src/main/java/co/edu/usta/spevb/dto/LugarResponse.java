package co.edu.usta.spevb.dto;

/**
 * precision identifica el tipo de punto, NO certifica su exactitud física. {@code googleId} es el identificador del lugar en Google (solo en resultados de Google): el navegador lo compara con el
 * de la opción que tocó la persona; NO es el identificador interno de SEVB ({@code id}). {@code nomenclatura} es la dirección armada con los componentes estructurados de Google (vía + placa, p. ej.
 * «Carrera 27 # 35A-50») cuando Google los trae; sirve para comparar por componentes y no por cifras sueltas.
 * {@code coincidencia} (solo en la búsqueda explícita de una dirección numerada) dice QUÉ tan segura es la respuesta: {@code EXACTA} (misma vía y misma placa completa), {@code POSIBLE} (la misma vía y una placa
 * que difiere por un error pequeño: se ofrece para REVISAR, nunca se aplica sola) o {@code REFERENCIA} (solo se ubicó la vía: sirve para centrar el mapa). {@code null} = sin clasificación (nombres, sitios).
 * {@code motivo} es una frase breve y verificable de por qué se muestra (p. ej. la placa que devolvió Google).
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
        String nomenclatura,
        String coincidencia,
        String motivo
) {
    public LugarResponse(Long id, String nombre, String direccion, double lat, double lng, String fuente, boolean confirmado, String precision, String googleId, String nomenclatura) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado, precision, googleId, nomenclatura, null, null);
    }

    /** Copia con la clasificación de la coincidencia. */
    public LugarResponse conCoincidencia(String coincidencia, String motivo) {
        return new LugarResponse(id, nombre, direccion, lat, lng, fuente, confirmado, precision, googleId, nomenclatura, coincidencia, motivo);
    }

    public LugarResponse(Long id, String nombre, String direccion, double lat, double lng, String fuente, boolean confirmado, String precision, String googleId) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado, precision, googleId, null, null, null);
    }

    public LugarResponse(Long id, String nombre, String direccion, double lat, double lng, String fuente, boolean confirmado, String precision) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado, precision, null, null, null, null);
    }

    // Compatible con el contrato de los lugares anteriores.
    public LugarResponse(Long id, String nombre, String direccion, double lat,
                         double lng, String fuente, boolean confirmado) {
        this(id, nombre, direccion, lat, lng, fuente, confirmado,
                confirmado ? "VERIFICADO_LOCAL" : "SIN_VERIFICAR", null, null, null, null);
    }
}
