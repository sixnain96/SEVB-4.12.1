package co.edu.usta.spevb.service;

import co.edu.usta.spevb.config.CityArea;

import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Nomenclatura colombiana de una dirección, comparada POR COMPONENTES y no por cifras sueltas: tipo de vía, identificador de la vía (con letra), Bis, sentido y los dos fragmentos de la placa
 * (con letra). «Carrera 27 # 35A-50» ≠ «Carrera 27 # 35-50» ≠ «Carrera 27 # 35A-51» ≠ «Calle 27 # 35A-50» ≠ «Carrera 27 Sur # 35A-50». Se interpreta con el mismo normalizador de {@link CityArea}.
 */
public record Nomenclatura(String tipo, String via, boolean bis, String sentido, String placa1, String placa2) {
    private static final Pattern FORMA = Pattern.compile(
            "^(Carrera|Calle|Avenida|Diagonal|Transversal)\\s+(\\d+[A-Z]?)(\\s+Bis)?(?:\\s+(Norte|Sur|Este|Oeste))?(?:\\s*#\\s*(\\d+[A-Z]?)-(\\d+[A-Z]?))?(?![\\p{L}\\p{N}])");

    /** Interpreta el texto (una consulta o una dirección que devolvió Google, p. ej. «Cra. 27 #35A-50, Villavicencio»). Vacío si no empieza con una vía numerada. */
    public static Optional<Nomenclatura> de(String texto, CityArea area) {
        if (texto == null || texto.isBlank()) return Optional.empty();
        Matcher m = FORMA.matcher(area.normalizeAddress(texto));
        if (!m.find()) return Optional.empty();
        return Optional.of(new Nomenclatura(m.group(1), m.group(2).toUpperCase(Locale.ROOT), m.group(3) != null, m.group(4) == null ? "" : m.group(4),
                m.group(5) == null ? "" : m.group(5).toUpperCase(Locale.ROOT), m.group(6) == null ? "" : m.group(6).toUpperCase(Locale.ROOT)));
    }

    public boolean tienePlaca() { return !placa1.isEmpty() && !placa2.isEmpty(); }

    /** ¿Es la misma vía (tipo, identificador, Bis y sentido), tenga o no placa? */
    public boolean mismaVia(Nomenclatura o) {
        return tipo.equals(o.tipo) && via.equals(o.via) && bis == o.bis && sentido.equals(o.sentido);
    }

    /** ¿Es EXACTAMENTE esa dirección? Vía igual y la misma placa completa (letras incluidas). */
    public boolean igual(Nomenclatura o) { return mismaVia(o) && tienePlaca() && o.tienePlaca() && placa1.equals(o.placa1) && placa2.equals(o.placa2); }

    /** «carrera», «calle»… para decir «Encontramos la carrera, pero no ese número». */
    public String sustantivo() { return tipo.toLowerCase(Locale.ROOT); }

    /** Forma canónica («Carrera 27 # 35A-50»). */
    public String texto() {
        return tipo + " " + via + (bis ? " Bis" : "") + (sentido.isEmpty() ? "" : " " + sentido) + (tienePlaca() ? " # " + placa1 + "-" + placa2 : "");
    }
}
