package co.edu.usta.spevb.service;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

import java.util.Map;

/**
 * Valida y limpia lo que cada dispositivo sube: solo los campos esperados, con tipos, rangos y largos controlados.
 * Así la base nunca guarda contenido arbitrario ni crece sin límite.
 */
public final class DatosUsuario {
    public static final Map<String, Integer> MAXIMO = Map.of("lugares", 30, "rutas", 100, "viajes", 50, "historial", 50);
    /** Lugares: nombre de hasta 40 caracteres, tipos únicos por cuenta (casa, trabajo) y «lápidas» (borrado:true) para que un borrado no reaparezca al sincronizar entre dispositivos. */
    public static final int NOMBRE_LUGAR_MAX = 40, LAPIDAS_MAX = 30;
    private static final long VIDA_LAPIDA_MS = 60L * 86_400_000L;
    private static final java.util.Set<String> TIPOS_LUGAR = java.util.Set.of("casa", "trabajo", "otro");
    private final ObjectMapper mapper;

    public DatosUsuario(ObjectMapper mapper) { this.mapper = mapper; }

    public boolean claveValida(String clave) { return MAXIMO.containsKey(clave); }

    public ArrayNode limpiar(String clave, JsonNode entrada) {
        if (!claveValida(clave)) throw new IllegalArgumentException("Tipo de datos desconocido.");
        if (entrada == null || !entrada.isArray()) throw new IllegalArgumentException("Se esperaba una lista.");
        if ("lugares".equals(clave)) return limpiarLugares(entrada);
        ArrayNode salida = mapper.createArrayNode();
        for (JsonNode item : entrada) {
            if (salida.size() >= MAXIMO.get(clave)) break;
            ObjectNode limpio = item != null && item.isObject() ? limpiarItem(clave, item) : null;
            if (limpio != null) salida.add(limpio);
        }
        return salida;
    }

    /** Lugares: ids únicos (el más reciente por {@code v} manda), a lo sumo UNA casa y UN trabajo vivos (la más reciente), hasta 30 vivos y hasta 30 lápidas de menos de 60 días. */
    private ArrayNode limpiarLugares(JsonNode entrada) {
        long ahora = System.currentTimeMillis();
        java.util.LinkedHashMap<String, ObjectNode> porId = new java.util.LinkedHashMap<>();
        for (JsonNode item : entrada) {
            ObjectNode l = item != null && item.isObject() ? limpiarItem("lugares", item) : null;
            if (l == null) continue;
            if (l.path("borrado").asBoolean(false) && ahora - l.path("v").asLong(0) > VIDA_LAPIDA_MS) continue;
            ObjectNode previo = porId.get(l.path("id").asString());
            if (previo == null || l.path("v").asLong(0) >= previo.path("v").asLong(0)) porId.put(l.path("id").asString(), l);
        }
        java.util.Map<String, ObjectNode> unico = new java.util.HashMap<>();
        for (ObjectNode l : porId.values()) {
            String tipo = l.path("tipo").asString("");
            if (l.path("borrado").asBoolean(false) || !("casa".equals(tipo) || "trabajo".equals(tipo))) continue;
            ObjectNode otro = unico.get(tipo);
            if (otro == null || l.path("v").asLong(0) > otro.path("v").asLong(0)) unico.put(tipo, l);
        }
        ArrayNode vivos = mapper.createArrayNode(), lapidas = mapper.createArrayNode();
        for (ObjectNode l : porId.values()) {
            if (l.path("borrado").asBoolean(false)) { if (lapidas.size() < LAPIDAS_MAX) lapidas.add(l); continue; }
            String tipo = l.path("tipo").asString("");
            if (("casa".equals(tipo) || "trabajo".equals(tipo)) && unico.get(tipo) != l) continue;      // una segunda casa o un segundo trabajo no entra
            if (vivos.size() < MAXIMO.get("lugares")) vivos.add(l);
        }
        vivos.addAll(lapidas);
        return vivos;
    }

    private ObjectNode limpiarItem(String clave, JsonNode in) {
        String id = texto(in, "id", 40);
        if (id == null) return null;
        ObjectNode o = mapper.createObjectNode();
        o.put("id", id);
        switch (clave) {
            case "lugares" -> {
                if (in.path("borrado").asBoolean(false)) {      // lápida: solo id y momento del borrado
                    Long vb = in.hasNonNull("v") && in.get("v").canConvertToLong() ? in.get("v").asLong() : null;
                    if (vb == null || vb <= 0) return null;
                    o.put("borrado", true); o.put("v", vb);
                    return o;
                }
                String nombre = texto(in, "nombre", NOMBRE_LUGAR_MAX);
                String tipo = texto(in, "tipo", 10);
                if (tipo != null && TIPOS_LUGAR.contains(tipo)) o.put("tipo", tipo);
                Long v = in.hasNonNull("v") && in.get("v").canConvertToLong() ? in.get("v").asLong() : null;
                if (v != null && v > 0) o.put("v", v);
                Double lat = numero(in, "lat", -90, 90), lng = numero(in, "lng", -180, 180);
                if (nombre == null || lat == null || lng == null) return null;
                o.put("nombre", nombre); o.put("lat", lat); o.put("lng", lng);
            }
            case "rutas" -> {
                String nombre = texto(in, "nombre", 80);
                if (nombre != null) o.put("nombre", nombre);
            }
            case "viajes", "historial" -> {
                ObjectNode a = punto(in.get("a")), b = punto(in.get("b"));
                if (a == null || b == null) return null;
                o.set("a", a); o.set("b", b);
                o.put("soloValidadas", in.path("soloValidadas").asBoolean(false));
                Long t = in.hasNonNull("t") && in.get("t").canConvertToLong() ? in.get("t").asLong() : null;
                o.put("t", t != null && t > 0 ? t : System.currentTimeMillis());
                if ("viajes".equals(clave)) {
                    String nombre = texto(in, "nombre", 60);
                    o.put("nombre", nombre != null ? nombre : "Viaje guardado");
                } else if (in.get("codigos") instanceof ArrayNode cs) {
                    ArrayNode codigos = mapper.createArrayNode();
                    for (JsonNode c : cs) { if (codigos.size() < 3 && c.isString() && c.asString().length() <= 40) codigos.add(c.asString().strip()); }
                    o.set("codigos", codigos);
                }
            }
            default -> { return null; }
        }
        return o;
    }

    private ObjectNode punto(JsonNode p) {
        if (p == null || !p.isObject()) return null;
        Double lat = numero(p, "lat", -90, 90), lng = numero(p, "lng", -180, 180);
        if (lat == null || lng == null) return null;
        ObjectNode o = mapper.createObjectNode();
        o.put("lat", lat); o.put("lng", lng);
        String nombre = texto(p, "nombre", 80);
        o.put("nombre", nombre != null ? nombre : "");
        return o;
    }

    private static String texto(JsonNode n, String campo, int max) {
        JsonNode v = n.get(campo);
        if (v == null || !v.isString()) return null;
        String s = v.asString().replaceAll("[\\p{Cntrl}]", " ").strip();
        if (s.isEmpty()) return null;
        return s.length() > max ? s.substring(0, max) : s;
    }

    private static Double numero(JsonNode n, String campo, double min, double max) {
        JsonNode v = n.get(campo);
        if (v == null || !v.isNumber()) return null;
        double d = v.asDouble();
        return Double.isFinite(d) && d >= min && d <= max ? d : null;
    }
}
