package co.edu.usta.spevb.dto;

/**
 * Sugerencia de autocompletado. Las locales traen coordenadas (se ubican sin otra consulta); las de ArcGIS traen magicKey; las de Google traen el
 * identificador del lugar (magicKey «g:…»). {@code principal} y {@code secundario} son el nombre y la referencia para mostrar en dos líneas (null si el
 * proveedor no los distingue: la pantalla usa entonces {@code texto} y {@code detalle}).
 */
public record SugerenciaResponse(String texto, String detalle, String magicKey, Double lat, Double lng,
                                 Long id, String fuente, String precision, String principal, String secundario) {
    public SugerenciaResponse(String texto, String detalle, String magicKey, Double lat, Double lng, Long id, String fuente, String precision) {
        this(texto, detalle, magicKey, lat, lng, id, fuente, precision, null, null);
    }
}
