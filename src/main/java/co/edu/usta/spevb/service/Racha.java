package co.edu.usta.spevb.service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.Collection;
import java.util.List;
import java.util.TreeSet;

/**
 * Racha de viajes (Fase D). Cálculo puro y determinista, con los MISMOS vectores de prueba que su espejo en js/logros.js (src/test/resources/racha-vectores.json).
 * <ul>
 *   <li>Un día cuenta una vez, sin importar cuántos viajes tuvo; el total de viajes cuenta todos.</li>
 *   <li>Días de calendario de Bogotá (UTC-5 fijo: Colombia no tiene horario de verano), nunca los del teléfono.</li>
 *   <li>Un día vacío de gracia: dos días con viaje separados por UN solo día vacío siguen en la misma racha (lun y mié: 2 días). Dos o más días vacíos la cortan.</li>
 *   <li>La racha ACTUAL se mantiene entera mientras el último día con viaje no esté a más de 2 días de hoy (lunes con viaje: el martes y el miércoles aún se puede continuar).
 *       Desde entonces BAJA UN DÍA por cada día que pasa sin viajar (4.17): una racha de 3 vale 2 el jueves, 1 el viernes y 0 el sábado, en vez de caer a 0 de golpe.
 *       Si la persona vuelve a viajar antes de llegar a 0, continúa desde lo que le quedaba (no vuelve a empezar de cero).</li>
 *   <li>La «racha estricta» (días consecutivos sin ningún hueco) conserva el significado de los logros antiguos «3 días seguidos» y «Una semana».</li>
 * </ul>
 */
public final class Racha {
    public static final ZoneOffset BOGOTA = ZoneOffset.ofHours(-5);
    /** Días vacíos que se toleran entre dos días con viaje. */
    public static final int GRACIA = 1;

    private Racha() {}

    public record Resultado(int actual, int mejor, int mejorEstricta, int dias, LocalDate ultimoDia) {}

    public static LocalDate diaDe(long epochMs) { return Instant.ofEpochMilli(epochMs).atOffset(BOGOTA).toLocalDate(); }

    public static int horaDe(long epochMs) { return Instant.ofEpochMilli(epochMs).atOffset(BOGOTA).getHour(); }

    public static Resultado calcular(Collection<LocalDate> dias, LocalDate hoy) {
        TreeSet<LocalDate> d = new TreeSet<>(dias);
        if (d.isEmpty()) return new Resultado(0, 0, 0, 0, null);
        int cadena = 0, estricta = 0, mejor = 0, mejorEstricta = 0;
        LocalDate previo = null;
        for (LocalDate x : d) {
            long hueco = previo == null ? 0 : ChronoUnit.DAYS.between(previo, x);
            cadena = previo == null ? 1 : hueco > GRACIA + 1 ? perdida(cadena, hueco) + 1 : cadena + 1;
            estricta = previo == null || hueco != 1 ? 1 : estricta + 1;
            mejor = Math.max(mejor, cadena); mejorEstricta = Math.max(mejorEstricta, estricta);
            previo = x;
        }
        long desdeUltimo = ChronoUnit.DAYS.between(previo, hoy);
        int actual = desdeUltimo <= GRACIA + 1 ? cadena : perdida(cadena, desdeUltimo);
        return new Resultado(actual, mejor, mejorEstricta, d.size(), previo);
    }

    /** Lo que queda de una racha de {@code cadena} días tras {@code dias} días desde el último viaje: pierde uno por cada día pasado el margen de gracia. */
    static int perdida(int cadena, long dias) { return (int) Math.max(0, cadena - Math.max(0, dias - (GRACIA + 1))); }

    public static Resultado calcular(List<LocalDate> dias, long ahoraMs) { return calcular(dias, diaDe(ahoraMs)); }
}
