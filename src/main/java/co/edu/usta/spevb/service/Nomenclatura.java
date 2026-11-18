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

    /** Solo la vía («Carrera 27», «Calle 15 Bis Sur»), sin placa: para ubicar la calle cuando no se pudo ubicar el número. */
    public String textoVia() {
        return tipo + " " + via + (bis ? " Bis" : "") + (sentido.isEmpty() ? "" : " " + sentido);
    }

    /**
     * ¿Es la MISMA vía (tipo, identificador, Bis y sentido) con una placa que difiere por UN error pequeño en un solo fragmento (una cifra o letra de más, de menos o cambiada)?
     * Ej.: «#935A-50» frente a «#35A-50». Exige que el fragmento editado tenga al menos 3 caracteres (con menos, un solo cambio no es evidencia). No es «igual»: se ofrece para REVISAR.
     */
    public boolean placaParecida(Nomenclatura o) {
        if (!mismaVia(o) || !tienePlaca() || !o.tienePlaca() || igual(o)) return false;
        int d1 = distancia(placa1, o.placa1), d2 = distancia(placa2, o.placa2);
        if (d1 + d2 != 1) return false;
        String editado = d1 == 1 ? (placa1.length() >= o.placa1.length() ? placa1 : o.placa1) : (placa2.length() >= o.placa2.length() ? placa2 : o.placa2);
        return editado.length() >= 3;
    }

    /**
     * Corrector de Autocomplete: ¿es la MISMA vía y una placa CERCANA? Hasta 2 cambios en total (cifras o letras de más, de menos o cambiadas) y con un fragmento idéntico
     * (por ejemplo la calle transversal «35A» igual y el predio «50» frente a «58» o «15»). Solo para PROPONER «¿Te referías a…?» (la persona revisa el pin); nunca se aplica sola.
     */
    public boolean placaCercana(Nomenclatura o) {
        if (!mismaVia(o) || !tienePlaca() || !o.tienePlaca()) return false;
        int d1 = distancia(placa1, o.placa1), d2 = distancia(placa2, o.placa2), d = d1 + d2;
        return d <= 2 && (d1 == 0 || d2 == 0);
    }

    /** Distancia total entre las dos placas (suma por fragmento); un valor alto si alguna no tiene placa. */
    public int distanciaPlaca(Nomenclatura o) {
        return tienePlaca() && o.tienePlaca() ? distancia(placa1, o.placa1) + distancia(placa2, o.placa2) : 99;
    }

    /** Distancia de edición (inserción, borrado o cambio de un carácter) entre dos fragmentos cortos de placa. */
    static int distancia(String a, String b) {
        int[] previa = new int[b.length() + 1], actual = new int[b.length() + 1];
        for (int j = 0; j <= b.length(); j++) previa[j] = j;
        for (int i = 1; i <= a.length(); i++) {
            actual[0] = i;
            for (int j = 1; j <= b.length(); j++)
                actual[j] = Math.min(Math.min(actual[j - 1], previa[j]) + 1, previa[j - 1] + (a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1));
            int[] t = previa; previa = actual; actual = t;
        }
        return previa[b.length()];
    }

    /** Forma canónica («Carrera 27 # 35A-50»). */
    public String texto() {
        return tipo + " " + via + (bis ? " Bis" : "") + (sentido.isEmpty() ? "" : " " + sentido) + (tienePlaca() ? " # " + placa1 + "-" + placa2 : "");
    }
}
