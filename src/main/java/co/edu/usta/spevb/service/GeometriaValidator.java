package co.edu.usta.spevb.service;

import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;

@Component
public class GeometriaValidator {
    public void validar(JsonNode geometry) {
        validarTipo(geometry);
        JsonNode coordinates = geometry.path("coordinates");
        validarCantidadPuntos(coordinates);
        validarSecuencia(coordinates);
        validarCrs(geometry);
    }

    private void validarTipo(JsonNode geometry) {
        if (geometry == null || !geometry.isObject()
                || !"LineString".equals(geometry.path("type").asText())) {
            throw new IllegalArgumentException("El recorrido debe ser una geometría GeoJSON LineString.");
        }
    }

    private void validarCantidadPuntos(JsonNode coordinates) {
        if (!coordinates.isArray() || coordinates.size() < 2 || coordinates.size() > 10000) {
            throw new IllegalArgumentException("El recorrido debe contener entre 2 y 10.000 puntos.");
        }
    }

    private void validarSecuencia(JsonNode coordinates) {
        double previousLng = Double.NaN;
        double previousLat = Double.NaN;
        for (JsonNode point : coordinates) {
            Punto current = validarPunto(point);
            if (current.longitud() == previousLng && current.latitud() == previousLat) {
                throw new IllegalArgumentException("El recorrido contiene puntos consecutivos duplicados.");
            }
            previousLng = current.longitud();
            previousLat = current.latitud();
        }
    }

    private Punto validarPunto(JsonNode point) {
        validarEstructuraPunto(point);
        double lng = point.get(0).asDouble();
        double lat = point.get(1).asDouble();
        validarRangoCoordenadas(lng, lat);
        return new Punto(lng, lat);
    }

    private void validarEstructuraPunto(JsonNode point) {
        if (!point.isArray() || point.size() != 2) {
            throw new IllegalArgumentException("Cada punto debe contener exactamente [longitud, latitud] numéricas.");
        }
        if (!point.get(0).isNumber() || !point.get(1).isNumber()) {
            throw new IllegalArgumentException("Cada punto debe contener exactamente [longitud, latitud] numéricas.");
        }
    }

    private void validarRangoCoordenadas(double lng, double lat) {
        if (!Double.isFinite(lng) || !Double.isFinite(lat)) {
            throw new IllegalArgumentException("Coordenadas fuera de rango: longitud ±180 y latitud ±90.");
        }
        if (lng < -180 || lng > 180 || lat < -90 || lat > 90) {
            throw new IllegalArgumentException("Coordenadas fuera de rango: longitud ±180 y latitud ±90.");
        }
    }

    private void validarCrs(JsonNode geometry) {
        if (geometry.has("crs")) {
            throw new IllegalArgumentException("Usa coordenadas WGS84; no incluyas un CRS alternativo.");
        }
    }

    private record Punto(double longitud, double latitud) { }
}
