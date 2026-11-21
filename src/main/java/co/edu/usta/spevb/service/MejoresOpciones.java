package co.edu.usta.spevb.service;

import co.edu.usta.spevb.dto.ViajeResponse;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Regla de negocio «las mejores opciones» (4.17, a pedido del profesor): no se muestran todas las rutas registradas, solo las MEJORES, como máximo
 * {@value #MAX_OPCIONES}, y nunca las que obligan a caminar demasiado ({@value #MAX_CAMINATA_METROS} m entre ir a la subida, cambiar de bus y llegar a B).
 * <ul>
 *   <li>Se conservan, en este orden de preferencia, las directas (ya vienen ordenadas por lo que hay que caminar) y, si ayudan, un transbordo: el de menos
 *       caminata ocupa un cupo aunque las directas llenen la lista, para que un transbordo que acorta mucho la caminata no se pierda.</li>
 *   <li>Las rutas en sentido contrario no se recomiendan: solo aparecen si no hay ninguna otra opción.</li>
 *   <li>Si NINGUNA cumple el límite de caminata, se muestra solo la menos mala (una) y la respuesta lo dice; así nunca queda vacío sin motivo.</li>
 * </ul>
 * Es una función pura (sin base de datos) para poder probarla.
 */
public final class MejoresOpciones {
    public static final int MAX_OPCIONES = 2;
    public static final double MAX_CAMINATA_METROS = 1000;

    private MejoresOpciones() {}

    public record Resultado(List<ViajeResponse.Opcion> directas, List<ViajeResponse.Opcion> alternativas, List<ViajeResponse.Transbordo> transbordos, String nota) {}

    public static Resultado aplicar(List<ViajeResponse.Opcion> directas, List<ViajeResponse.Opcion> alternativas, List<ViajeResponse.Transbordo> transbordos) {
        // Las mejores van primero por costo puerta a puerta (caminar pesa el doble) y una sola vez por ruta: la variante «más rápida» de la misma ruta no gasta otro cupo.
        var d = unaPorRuta(directas.stream().filter(o -> o.accesoTotalMetros() <= MAX_CAMINATA_METROS)
                .sorted(Comparator.comparingDouble(MejoresOpciones::costo)).toList());
        var t = transbordos.stream().filter(x -> x.caminataMetros() <= MAX_CAMINATA_METROS)
                .sorted(Comparator.comparingDouble(ViajeResponse.Transbordo::caminataMetros).thenComparingDouble(ViajeResponse.Transbordo::minutos)).toList();

        if (d.isEmpty() && t.isEmpty()) {
            // Nada cumple el límite: se ofrece solo lo menos malo (la directa que menos camina, o el transbordo, o la de sentido contrario), y se avisa.
            if (!directas.isEmpty()) return nada(List.of(directas.get(0)), List.of(), List.of(), true);
            var tt = transbordos.stream().min(Comparator.comparingDouble(ViajeResponse.Transbordo::caminataMetros));
            if (tt.isPresent()) return nada(List.of(), List.of(), List.of(tt.get()), true);
            if (!alternativas.isEmpty()) return nada(List.of(), List.of(alternativas.get(0)), List.of(), true);
            return new Resultado(List.of(), List.of(), List.of(), "");
        }
        // Un transbordo solo le quita el segundo lugar a una directa si la política lo consideraría de verdad (reduce de forma significativa la caminata hasta el primer bus);
        // si no, solo ocupa lugares que las directas dejen libres.
        boolean transbordoPuedeGanar = !t.isEmpty() && !d.isEmpty() && PoliticaRecomendacion.DEFECTO.reduccionSignificativa(d.get(0).acercamientoInicioMetros(), inicialDe(t.get(0)));
        int cuposT = Math.min(t.size(), d.isEmpty() ? MAX_OPCIONES : transbordoPuedeGanar ? 1 : 0);
        int cuposD = Math.min(d.size(), MAX_OPCIONES - cuposT);
        while (cuposD + cuposT < MAX_OPCIONES && cuposT < t.size()) cuposT++;      // lugares libres: más transbordos
        var dd = new ArrayList<>(d.subList(0, cuposD));
        var tt = new ArrayList<>(t.subList(0, cuposT));
        int descartadas = directas.size() + transbordos.size() - dd.size() - tt.size();
        String nota = " Regla SEVB: solo se muestran las " + MAX_OPCIONES + " mejores opciones como máximo y se descartan las que piden caminar más de "
                + (int) MAX_CAMINATA_METROS + " m" + (descartadas > 0 ? " (" + descartadas + " opciones menos buenas ocultas)." : ".");
        return new Resultado(List.copyOf(dd), List.of(), List.copyOf(tt), nota);
    }

    private static double inicialDe(ViajeResponse.Transbordo t) { return t.caminataInicio() != null ? t.caminataInicio().metros() : t.caminataMetros(); }

    /** Costo puerta a puerta en minutos: caminar (a 80 m/min) cuenta doble, el bus va a 267 m/min. */
    static double costo(ViajeResponse.Opcion o) { return ViajeService.costoMin(o.accesoTotalMetros(), o.recorridoKm()); }

    private static List<ViajeResponse.Opcion> unaPorRuta(List<ViajeResponse.Opcion> ordenadas) {
        var vistas = new java.util.HashSet<String>();
        var r = new ArrayList<ViajeResponse.Opcion>();
        for (var o : ordenadas) if (vistas.add(o.codigo())) r.add(o);
        return r;
    }

    private static Resultado nada(List<ViajeResponse.Opcion> d, List<ViajeResponse.Opcion> a, List<ViajeResponse.Transbordo> t, boolean aviso) {
        return new Resultado(d, a, t, " Ninguna ruta registrada queda a menos de " + (int) MAX_CAMINATA_METROS + " m de caminata: se muestra solo la menos lejana. Ten en cuenta que tendrás que caminar bastante.");
    }
}
