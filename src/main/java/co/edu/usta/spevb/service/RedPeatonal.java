package co.edu.usta.spevb.service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;

/**
 * Red peatonal en memoria (calles, andenes, senderos y escaleras de OpenStreetMap) con búsqueda de camino A*.
 * Los puntos se «pegan» a la calle más cercana; el camino sólo recorre aristas de la red, así que nunca atraviesa
 * manzanas, edificios ni lotes. Las piezas aisladas de la red (islotes) se descartan para no dejar a nadie
 * atrapado en un tramo sin salida.
 */
public final class RedPeatonal {
    /** Punto proyectado sobre una arista: {@code t} es la fracción desde {@code u} hacia {@code v}. */
    public record Snap(int arista, int u, int v, double t, double lat, double lng, double distM) {}

    public record Camino(List<double[]> coordenadas, double metros) {}

    /**
     * Multiplicadores de costo por clase de vía. Todos son ≥ 1: el costo nunca es menor que los metros reales, así que el número que se
     * le muestra a la persona («caminas X m») es una cota honesta y no un valor inflado ni rebajado. Caminar POR el andén de una avenida
     * (por donde pasan los buses) casi no se penaliza: antes costaba 2,5 veces y empujaba a elegir un punto de subida más lejano en una calle
     * tranquila. El riesgo de una avenida se cobra al CRUZARLA (ver {@link #CRUCE}), no al caminar a su lado.
     */
    private static final double[] FACTOR = {1.0, 1.25, 1.1, 1.0, 1.05, 1.1, 1.0, 1.0};
    private static final double FACTOR_MINIMO = 1.0;
    /**
     * LLANA…PUENTE son las clases de las calles. CRUCE es una arista virtual de longitud cero entre los dos andenes de una avenida: su
     * «largo» es el costo en metros equivalentes de cruzarla a nivel (ver {@link Constructor#dividirBarreras}).
     */
    static final byte LLANA = 0, ESCALERA = 1, SENDERO = 2, VIA_LOCAL = 3, VIA_PRINCIPAL = 4, TRONCAL = 5, PUENTE = 6, CRUCE = 7;
    /**
     * Metros equivalentes de cruzar a nivel una vía principal/secundaria y una troncal (una calzada); una doble calzada son dos cruces. El
     * cobro SOLO existe cerca de un puente peatonal registrado (ver {@link #RADIO_ZONA_PUENTE_METROS}): en el resto de la ciudad las avenidas se
     * cruzan libremente por el camino más corto, como antes. Con el cobro en toda la ciudad el camino prefería cruzar por otra esquina lejana
     * (sin cobro) y la persona caminaba cientos de metros de más.
     */
    public static final double CRUCE_VIA_PRINCIPAL_METROS = 30, CRUCE_TRONCAL_METROS = 50;
    /** Hasta dónde llega la influencia de un puente peatonal: los tramos de avenida a menos de esta distancia de alguno de sus extremos se cruzan con costo. */
    public static final double RADIO_ZONA_PUENTE_METROS = 120;
    /** Un punto a menos de esta distancia del eje de una avenida se considera sobre la calzada: puede llegar a cualquiera de sus dos andenes. */
    static final double TOLERANCIA_LADO_ORIGEN_METROS = 3, TOLERANCIA_LADO_DESTINO_METROS = 10;
    private static final double CELDA = 0.0025;
    private static final int TAMANO_MINIMO_ISLOTE = 30;

    /** Clase de costo para un valor de {@code highway}; {@code -1} si no se debe recorrer a pie. */
    public static byte clase(String highway) {
        if (highway == null) return -1;
        return switch (highway) {
            case "footway", "pedestrian", "cycleway", "living_street", "residential", "service", "unclassified",
                 "corridor", "road", "pedestrian_area" -> LLANA;
            case "path", "track", "bridleway" -> SENDERO;
            case "steps" -> ESCALERA;
            case "tertiary", "tertiary_link" -> VIA_LOCAL;
            case "secondary", "secondary_link", "primary", "primary_link" -> VIA_PRINCIPAL;
            case "trunk", "trunk_link" -> TRONCAL;
            default -> -1;
        };
    }

    private final double[] lat, lng;
    private final int[] ini, dst, origen;
    private final float[] largo;
    private final byte[] clase;
    /**
     * Lado de cada mitad de arista de una avenida: +1 = el andén a la izquierda de {@code origen→dst}, -1 = el de la derecha, 0 = no es
     * de avenida. Un punto sólo se «pega» al andén de su propio lado (así no cruza la avenida sin pagar el cruce).
     */
    private final byte[] lado;
    /** Mitades de arista que son copia del andén derecho de una avenida: existen para el cálculo pero no se dibujan (misma geometría que la izquierda). */
    private final boolean[] sombra;
    private final boolean[] valido;
    private final Map<Long, int[]> rejilla;
    private final double minLat, maxLat, minLng, maxLng;

    private RedPeatonal(double[] lat, double[] lng, int[] ini, int[] dst, int[] origen, float[] largo, byte[] clase, byte[] lado,
                        boolean[] sombra, boolean[] valido, Map<Long, int[]> rejilla) {
        this.lat = lat; this.lng = lng; this.ini = ini; this.dst = dst; this.origen = origen;
        this.largo = largo; this.clase = clase; this.lado = lado; this.sombra = sombra; this.valido = valido; this.rejilla = rejilla;
        double a = 90, b = -90, c = 180, d = -180;
        for (int i = 0; i < lat.length; i++) {
            if (!valido[i]) continue;
            a = Math.min(a, lat[i]); b = Math.max(b, lat[i]); c = Math.min(c, lng[i]); d = Math.max(d, lng[i]);
        }
        minLat = a; maxLat = b; minLng = c; maxLng = d;
    }

    public int nodos() { return lat.length; }
    public int aristas() { return dst.length / 2; }
    /** Nodos que forman parte de la red principal (los islotes aislados se descartan). */
    public int nodosAccesibles() { int c = 0; for (boolean v : valido) if (v) c++; return c; }
    /** Puntos [lat, lng] al azar sobre la red (para pruebas y diagnóstico). */
    double[][] puntosDeMuestra(int cuantos, java.util.Random azar) {
        List<double[]> r = new ArrayList<>();
        while (r.size() < cuantos) { int i = azar.nextInt(lat.length); if (valido[i]) r.add(new double[]{lat[i], lng[i]}); }
        return r.toArray(new double[0][]);
    }
    /**
     * Tramos de la red dentro de una caja, como [lng1, lat1, lng2, lat2] (para mostrarlos en el mapa de administración).
     * Devuelve como máximo {@code maximo} tramos.
     */
    public List<double[]> segmentos(double sur, double oeste, double norte, double este, int maximo) {
        List<double[]> r = new ArrayList<>();
        for (int a = 0; a < dst.length && r.size() < maximo; a++) {
            int u = origen[a], v = dst[a];
            if (u >= v || !valido[u] || clase[a] == CRUCE || sombra[a]) continue;     // sin la arista virtual de cruce ni el andén duplicado
            if ((lat[u] < sur && lat[v] < sur) || (lat[u] > norte && lat[v] > norte)
                    || (lng[u] < oeste && lng[v] < oeste) || (lng[u] > este && lng[v] > este)) continue;
            r.add(new double[]{lng[u], lat[u], lng[v], lat[v]});
        }
        return r;
    }

    public boolean vacia() { return rejilla.isEmpty(); }

    // ------------------------------------------------------------------ construcción
    public static final class Constructor {
        private final Map<Long, Integer> indice = new HashMap<>();
        private double[] lat = new double[1024], lng = new double[1024];
        private int n;
        private int[] eu = new int[2048], ev = new int[2048];
        private byte[] ec = new byte[2048];
        private boolean[] ep = new boolean[2048];   // arista de un paso propio: los bloqueos no la tocan
        private float[] ePen = new float[2048];     // aristas de cruce: costo en metros equivalentes (0 en las demás)
        private byte[] eLado = new byte[2048];      // andén de avenida: +1 izquierda, -1 derecha de eu→ev (0 en las demás)
        /** Punto exacto donde el paso propio quería terminar (NaN si la arista no es el extremo de un paso): decide a qué andén de una avenida se une. */
        private double[] pistaULat = new double[2048], pistaULng = new double[2048], pistaVLat = new double[2048], pistaVLng = new double[2048];
        private int m;
        private long sintetico = -1;
        private final List<double[][]> bloqueos = new ArrayList<>();   // cada uno: {lats, lngs}
        private final double cruceVia, cruceTroncal;

        public Constructor() { this(CRUCE_VIA_PRINCIPAL_METROS, CRUCE_TRONCAL_METROS); }

        /** {@code cruceVia} y {@code cruceTroncal}: metros equivalentes de cruzar a nivel esa clase de avenida; 0 desactiva el cobro. */
        public Constructor(double cruceVia, double cruceTroncal) {
            this.cruceVia = Math.max(0, cruceVia);
            this.cruceTroncal = Math.max(0, cruceTroncal);
        }

        private int nodo(long id, double la, double lo) {
            Integer i = indice.get(id);
            if (i != null) return i;
            return nodoNuevo(la, lo, id);
        }

        private int nodoNuevo(double la, double lo, long id) {
            if (n == lat.length) { lat = Arrays.copyOf(lat, n * 2); lng = Arrays.copyOf(lng, n * 2); }
            lat[n] = la; lng[n] = lo;
            indice.put(id, n);
            return n++;
        }

        /** Agrega un camino: cada par de vértices consecutivos es una arista bidireccional. */
        public void agregarCamino(long[] ids, double[] lats, double[] lngs, byte clase) {
            int anterior = -1;
            for (int i = 0; i < ids.length; i++) {
                int actual = nodo(ids[i], lats[i], lngs[i]);
                if (anterior >= 0 && anterior != actual) {
                    agregarArista(anterior, actual, clase, false);
                }
                anterior = actual;
            }
        }

        private void agregarArista(int u, int v, byte clase, boolean propia) {
            agregarArista(u, v, clase, propia, Double.NaN, Double.NaN, Double.NaN, Double.NaN);
        }

        private void agregarArista(int u, int v, byte clase, boolean propia, double pUlat, double pUlng, double pVlat, double pVlng) {
            if (m == eu.length) {
                int c = m * 2;
                eu = Arrays.copyOf(eu, c); ev = Arrays.copyOf(ev, c);
                ec = Arrays.copyOf(ec, c); ep = Arrays.copyOf(ep, c);
                ePen = Arrays.copyOf(ePen, c); eLado = Arrays.copyOf(eLado, c);
                pistaULat = Arrays.copyOf(pistaULat, c); pistaULng = Arrays.copyOf(pistaULng, c);
                pistaVLat = Arrays.copyOf(pistaVLat, c); pistaVLng = Arrays.copyOf(pistaVLng, c);
            }
            eu[m] = u; ev[m] = v; ec[m] = clase; ep[m] = propia; ePen[m] = 0; eLado[m] = 0;
            pistaULat[m] = pUlat; pistaULng[m] = pUlng; pistaVLat[m] = pVlat; pistaVLng[m] = pVlng;
            m++;
        }

        /** Nodo existente más cercano al punto, dentro de {@code maxMetros}; -1 si no hay. */
        private int nodoCercano(double la, double lo, double maxMetros) {
            int mejor = -1;
            double dmin = maxMetros;
            for (int i = 0; i < n; i++) {
                if (Math.abs(lat[i] - la) > 0.0004 || Math.abs(lng[i] - lo) > 0.0004) continue;
                double d = metros(la, lo, lat[i], lng[i]);
                if (d <= dmin) { dmin = d; mejor = i; }
            }
            return mejor;
        }

        /**
         * Extremo de un paso: se une al nodo cercano; si no hay, a la calle más cercana partiéndola en dos; si tampoco
         * hay calle cerca, queda suelto. {@code unido[0]} indica si se logró conectar.
         */
        private int extremo(double la, double lo, double enlaceMetros, boolean[] unido) {
            int existente = nodoCercano(la, lo, enlaceMetros);
            if (existente >= 0) { unido[0] = true; return existente; }
            double kx = Math.cos(Math.toRadians(la)) * 111_320, ky = 110_574, mejorD = enlaceMetros * 2, mejorT = 0;
            int mejorE = -1;
            for (int i = 0; i < m; i++) {
                if (ep[i]) continue;
                double ux = (lng[eu[i]] - lo) * kx, uy = (lat[eu[i]] - la) * ky, vx = (lng[ev[i]] - lo) * kx, vy = (lat[ev[i]] - la) * ky;
                if (Math.min(ux, vx) > mejorD || Math.max(ux, vx) < -mejorD || Math.min(uy, vy) > mejorD || Math.max(uy, vy) < -mejorD) continue;
                double dx = vx - ux, dy = vy - uy, l2 = dx * dx + dy * dy;
                double t = l2 == 0 ? 0 : Math.max(0, Math.min(1, -(ux * dx + uy * dy) / l2));
                double ex = ux + t * dx, ey = uy + t * dy, d = Math.sqrt(ex * ex + ey * ey);
                if (d < mejorD) { mejorD = d; mejorE = i; mejorT = t; }
            }
            if (mejorE >= 0 && mejorD <= enlaceMetros * 2) {
                int u = eu[mejorE], v = ev[mejorE];
                double nl = lat[u] + mejorT * (lat[v] - lat[u]), no = lng[u] + mejorT * (lng[v] - lng[u]);
                int nuevo = nodoNuevo(nl, no, sintetico--);
                byte c = ec[mejorE];
                ev[mejorE] = nuevo;                 // u—nuevo reemplaza a u—v
                agregarArista(nuevo, v, c, false);  // nuevo—v
                unido[0] = true;
                return nuevo;
            }
            unido[0] = false;
            return nodoNuevo(la, lo, sintetico--);
        }

        /**
         * Paso peatonal propio (andén, sendero, puente, atajo entre manzanas) que se suma a la red de OpenStreetMap.
         * Devuelve cuántos de sus dos extremos quedaron conectados a la red (0, 1 o 2).
         */
        public int agregarPaso(double[] lats, double[] lngs, double enlaceMetros) { return agregarPaso(lats, lngs, enlaceMetros, LLANA); }

        /** Igual que el anterior, con la clase de costo del paso ({@link #PUENTE} para los puentes peatonales). */
        public int agregarPaso(double[] lats, double[] lngs, double enlaceMetros, byte clase) {
            int conectados = 0;
            int anterior = -1;
            int ultimo = lats.length - 1;
            for (int i = 0; i <= ultimo; i++) {
                boolean extremo = i == 0 || i == ultimo;
                int actual;
                if (extremo) {
                    boolean[] u = new boolean[1];
                    actual = extremo(lats[i], lngs[i], enlaceMetros, u);
                    if (u[0]) conectados++;
                } else {
                    actual = nodoNuevo(lats[i], lngs[i], sintetico--);
                }
                if (anterior >= 0 && anterior != actual) {
                    // La pista es el punto donde el paso quería terminar: si cae sobre una avenida, dice a qué andén se une.
                    boolean primero = i == 1;
                    agregarArista(anterior, actual, clase, true,
                            primero ? lats[0] : Double.NaN, primero ? lngs[0] : Double.NaN,
                            i == ultimo ? lats[i] : Double.NaN, i == ultimo ? lngs[i] : Double.NaN);
                }
                anterior = actual;
            }
            return conectados;
        }

        /** Bloqueo: las calles de OpenStreetMap que pasan a menos de {@code metros} de la línea dejan de ser transitables. */
        public void bloquear(double[] lats, double[] lngs) { bloqueos.add(new double[][]{lats.clone(), lngs.clone()}); }

        private boolean bloqueada(int i, double radio) {
            double la = (lat[eu[i]] + lat[ev[i]]) / 2;
            double kx = Math.cos(Math.toRadians(la)) * 111_320, ky = 110_574;
            double ax = (lng[eu[i]] - lng[ev[i]]) * kx / 2, ay = (lat[eu[i]] - lat[ev[i]]) * ky / 2; // arista centrada en su punto medio
            double mx = (lng[eu[i]] + lng[ev[i]]) / 2, my = (lat[eu[i]] + lat[ev[i]]) / 2;
            for (double[][] b : bloqueos) {
                for (int k = 0; k + 1 < b[0].length; k++) {
                    double px = (b[1][k] - mx) * kx, py = (b[0][k] - my) * ky, qx = (b[1][k + 1] - mx) * kx, qy = (b[0][k + 1] - my) * ky;
                    if (distanciaSegmentos(-ax, -ay, ax, ay, px, py, qx, qy) <= radio) return true;
                }
            }
            return false;
        }

        // ------------------------------------------------------------------ avenidas: dos andenes y un cruce con costo
        private double cruceDe(byte clase) {
            return clase == VIA_PRINCIPAL ? cruceVia : clase == TRONCAL ? cruceTroncal : 0;
        }

        private boolean esBarrera(int i) { return !ep[i] && cruceDe(ec[i]) > 0; }

        private boolean cercaDeUnPuente(int x, List<double[]> anclas) {
            for (double[] a : anclas) {
                if (Math.abs(a[0] - lat[x]) > 0.0016 || Math.abs(a[1] - lng[x]) > 0.0016) continue;      // ≈ 180 m: descarte rápido
                if (metros(a[0], a[1], lat[x], lng[x]) <= RADIO_ZONA_PUENTE_METROS) return true;
            }
            return false;
        }

        /**
         * Cada tramo de avenida (vía principal o troncal de OpenStreetMap) pasa a ser DOS andenes paralelos, uno por lado, unidos por una
         * arista de cruce cuyo costo es lo que vale cruzar esa avenida a nivel. Así:
         * <ul>
         *   <li>caminar por el andén de su propio lado no cuesta nada extra;</li>
         *   <li>pasar al otro lado cuesta el cruce, salvo que haya un puente o paso propio que enlace los dos andenes: si el puente queda
         *       a menos desvío que ese costo se usa; si queda muy lejos, se cruza a nivel (como hace una persona);</li>
         *   <li>un punto sólo se «pega» al andén de su lado ({@code lado}), así que ya no «salta» la avenida al ajustarse a la calle.</li>
         * </ul>
         * Los nodos donde la avenida se cruza con otra, se bifurca o termina no se dividen (allí hay semáforo y esquinas): el cruce es libre.
         * Una doble calzada son dos avenidas y se cobra dos veces.
         * <p>El cobro solo se aplica en los nodos a menos de {@link #RADIO_ZONA_PUENTE_METROS} de un extremo de un puente registrado: allí un puente
         * cercano gana al cruce a nivel y, lejos de los puentes, no cambia nada respecto a una red sin cobro. Sin puentes no se divide ninguna avenida.
         */
        private void dividirBarreras() {
            if (cruceVia <= 0 && cruceTroncal <= 0) return;
            // Puntos de anclaje de los puentes: sus extremos (nodos y el punto exacto donde el trazo quería terminar).
            List<double[]> anclas = new ArrayList<>();
            for (int i = 0; i < m; i++) {
                if (!ep[i] || ec[i] != PUENTE) continue;
                anclas.add(new double[]{lat[eu[i]], lng[eu[i]]});
                anclas.add(new double[]{lat[ev[i]], lng[ev[i]]});
                if (!Double.isNaN(pistaULat[i])) anclas.add(new double[]{pistaULat[i], pistaULng[i]});
                if (!Double.isNaN(pistaVLat[i])) anclas.add(new double[]{pistaVLat[i], pistaVLng[i]});
            }
            if (anclas.isEmpty()) return;
            int[] grado = new int[n], primera = new int[n], segunda = new int[n];
            Arrays.fill(primera, -1); Arrays.fill(segunda, -1);
            boolean hay = false;
            for (int i = 0; i < m; i++) {
                if (!esBarrera(i)) continue;
                hay = true;
                for (int x : new int[]{eu[i], ev[i]}) {
                    grado[x]++;
                    if (primera[x] < 0) primera[x] = i; else if (segunda[x] < 0) segunda[x] = i;
                }
            }
            if (!hay) return;
            // Orientación coherente a lo largo de cada tramo continuo (nodos de grado 2): «izquierda» es la misma para todo el tramo.
            int[] cola = new int[m], cabeza = new int[m];
            Arrays.fill(cola, -1);
            for (int i = 0; i < m; i++) {
                if (!esBarrera(i) || cola[i] >= 0) continue;
                cola[i] = eu[i]; cabeza[i] = ev[i];
                int e = i, nodo = cabeza[i];
                while (grado[nodo] == 2) {
                    int j = primera[nodo] == e ? segunda[nodo] : primera[nodo];
                    if (j < 0 || cola[j] >= 0) break;
                    cola[j] = nodo; cabeza[j] = eu[j] == nodo ? ev[j] : eu[j];
                    e = j; nodo = cabeza[j];
                }
                e = i; nodo = cola[i];
                while (grado[nodo] == 2) {
                    int j = primera[nodo] == e ? segunda[nodo] : primera[nodo];
                    if (j < 0 || cola[j] >= 0) break;
                    cabeza[j] = nodo; cola[j] = eu[j] == nodo ? ev[j] : eu[j];
                    e = j; nodo = cola[j];
                }
            }
            // Copia «derecha» de cada nodo intermedio (misma posición); el nodo original queda como copia «izquierda».
            int[] derecha = new int[n];
            Arrays.fill(derecha, -1);
            int n0 = n;
            for (int x = 0; x < n0; x++) {
                if (grado[x] != 2 || !cercaDeUnPuente(x, anclas)) continue;
                derecha[x] = nodoNuevo(lat[x], lng[x], sintetico--);
            }
            int m0 = m;
            // Las calles que llegan a un nodo intermedio se unen al andén de su lado.
            for (int j = 0; j < m0; j++) {
                if (esBarrera(j)) continue;
                for (int extremo = 0; extremo < 2; extremo++) {
                    int x = extremo == 0 ? eu[j] : ev[j];
                    if (x >= n0 || derecha[x] < 0) continue;
                    int otro = extremo == 0 ? ev[j] : eu[j];
                    double pLat = extremo == 0 ? pistaULat[j] : pistaVLat[j], pLng = extremo == 0 ? pistaULng[j] : pistaVLng[j];
                    boolean conPista = !Double.isNaN(pLat);
                    if (!conPista) { pLat = lat[otro]; pLng = lng[otro]; }
                    int entra = primera[x], sale = segunda[x];
                    if (cabeza[entra] != x) { int t = entra; entra = sale; sale = t; }      // «entra»: el tramo que llega a x; «sale»: el que parte
                    double kx = Math.cos(Math.toRadians(lat[x])) * 111_320, ky = 110_574;
                    double dx = (lng[cabeza[sale]] - lng[cola[entra]]) * kx, dy = (lat[cabeza[sale]] - lat[cola[entra]]) * ky;
                    double qx = (pLng - lng[x]) * kx, qy = (pLat - lat[x]) * ky;
                    double cruz = dx * qy - dy * qx, largoD = Math.sqrt(dx * dx + dy * dy);
                    double distancia = largoD == 0 ? 0 : cruz / largoD;          // metros a la izquierda (+) o derecha (−) del eje
                    boolean izquierda;
                    if (Math.abs(distancia) < 1.0) {
                        // Pegada al eje: se une al andén opuesto al lado del otro extremo, o a la izquierda si tampoco ese se sabe.
                        double ox = (lng[otro] - lng[x]) * kx, oy = (lat[otro] - lat[x]) * ky, c2 = largoD == 0 ? 0 : (dx * oy - dy * ox) / largoD;
                        izquierda = conPista && Math.abs(c2) >= 1.0 ? c2 < 0 : true;
                    } else {
                        izquierda = distancia > 0;
                    }
                    if (!izquierda) { if (extremo == 0) eu[j] = derecha[x]; else ev[j] = derecha[x]; }
                }
            }
            // Cada tramo de avenida pasa a dos andenes (izquierdo = arista original, derecho = copia), orientados cola→cabeza.
            for (int i = 0; i < m0; i++) {
                if (!esBarrera(i)) continue;
                int t = cola[i], h = cabeza[i];
                eu[i] = t; ev[i] = h; eLado[i] = 1;
                int dt = t < n0 && derecha[t] >= 0 ? derecha[t] : t, dh = h < n0 && derecha[h] >= 0 ? derecha[h] : h;
                agregarArista(dt, dh, ec[i], false);
                eLado[m - 1] = -1;
            }
            // La arista de cruce entre los dos andenes de cada nodo intermedio.
            for (int x = 0; x < n0; x++) {
                if (derecha[x] < 0) continue;
                double c = Math.max(cruceDe(ec[primera[x]]), cruceDe(ec[segunda[x]]));
                agregarArista(x, derecha[x], CRUCE, true);
                ePen[m - 1] = (float) c;
            }
        }

        public RedPeatonal construir() {
            if (!bloqueos.isEmpty()) {
                int k = 0;
                for (int i = 0; i < m; i++) {
                    if (!ep[i] && bloqueada(i, 6)) continue;
                    eu[k] = eu[i]; ev[k] = ev[i]; ec[k] = ec[i]; ep[k] = ep[i];
                    pistaULat[k] = pistaULat[i]; pistaULng[k] = pistaULng[i]; pistaVLat[k] = pistaVLat[i]; pistaVLng[k] = pistaVLng[i];
                    k++;
                }
                m = k;
            }
            dividirBarreras();
            int e = m * 2;
            int[] grado = new int[n + 1];
            for (int i = 0; i < m; i++) { grado[eu[i] + 1]++; grado[ev[i] + 1]++; }
            for (int i = 0; i < n; i++) grado[i + 1] += grado[i];
            int[] ini = grado, pos = Arrays.copyOf(grado, n), dst = new int[e], origen = new int[e];
            float[] largo = new float[e];
            byte[] clase = new byte[e], lado = new byte[e];
            boolean[] sombra = new boolean[e];
            int[] padre = new int[n];
            for (int i = 0; i < n; i++) padre[i] = i;
            for (int i = 0; i < m; i++) {
                float d = ePen[i] > 0 ? ePen[i] : (float) metros(lat[eu[i]], lng[eu[i]], lat[ev[i]], lng[ev[i]]);
                int a = pos[eu[i]]++, b = pos[ev[i]]++;
                dst[a] = ev[i]; origen[a] = eu[i]; largo[a] = d; clase[a] = ec[i]; lado[a] = eLado[i];
                dst[b] = eu[i]; origen[b] = ev[i]; largo[b] = d; clase[b] = ec[i]; lado[b] = (byte) -eLado[i];
                sombra[a] = sombra[b] = eLado[i] < 0;
                unir(padre, eu[i], ev[i]);
            }
            int[] tamano = new int[n];
            for (int i = 0; i < n; i++) tamano[raiz(padre, i)]++;
            int mayor = 0;
            for (int i = 0; i < n; i++) if (tamano[i] > tamano[mayor]) mayor = i;
            boolean[] valido = new boolean[n];
            for (int i = 0; i < n; i++) {
                int r = raiz(padre, i);
                valido[i] = tamano[r] >= TAMANO_MINIMO_ISLOTE || (n > 0 && r == mayor);
            }
            // Rejilla: cada arista (una sola vez, sentido u<v) se registra en las celdas que cubre su caja. Las aristas de cruce no se registran:
            // son virtuales y nadie se «pega» a ellas.
            Map<Long, List<Integer>> temp = new HashMap<>();
            for (int a = 0; a < e; a++) {
                int u = origen[a], v = dst[a];
                if (u >= v || !valido[u] || clase[a] == CRUCE) continue;
                int x0 = celda(Math.min(lng[u], lng[v]) + 180), x1 = celda(Math.max(lng[u], lng[v]) + 180);
                int y0 = celda(Math.min(lat[u], lat[v]) + 90), y1 = celda(Math.max(lat[u], lat[v]) + 90);
                for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++)
                    temp.computeIfAbsent(clave(x, y), k -> new ArrayList<>()).add(a);
            }
            Map<Long, int[]> rejilla = new HashMap<>(temp.size() * 2);
            temp.forEach((k, v) -> rejilla.put(k, v.stream().mapToInt(Integer::intValue).toArray()));
            return new RedPeatonal(Arrays.copyOf(lat, n), Arrays.copyOf(lng, n), ini, dst, origen, largo, clase, lado, sombra, valido, rejilla);
        }

        private static int raiz(int[] p, int i) {
            while (p[i] != i) { p[i] = p[p[i]]; i = p[i]; }
            return i;
        }
        private static void unir(int[] p, int a, int b) { p[raiz(p, a)] = raiz(p, b); }
    }

    private static int celda(double v) { return (int) Math.floor(v / CELDA); }
    /**
     * Clave única de la celda (x, y). Se mezcla con una función BIYECTIVA (fmix64 de MurmurHash3): sigue siendo única, pero su {@code hashCode}
     * ({@code Long.hashCode} = parte alta XOR parte baja) ya no es {@code x ^ y}, que coincidía para miles de celdas distintas y degeneraba el
     * HashMap en árboles (medido: ≈ 16 % del tiempo de cada cálculo de viaje se iba en {@code HashMap$TreeNode.find}).
     */
    private static long clave(int x, int y) {
        long k = ((long) y << 32) ^ (x & 0xffffffffL);
        k ^= k >>> 33; k *= 0xff51afd7ed558ccdL;
        k ^= k >>> 33; k *= 0xc4ceb9fe1a85ec53L;
        k ^= k >>> 33;
        return k;
    }

    // ------------------------------------------------------------------ geometría
    /** Distancia mínima entre los segmentos AB y CD en un plano (metros). */
    static double distanciaSegmentos(double ax, double ay, double bx, double by, double cx, double cy, double dx, double dy) {
        double d1 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax), d2 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax);
        double d3 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx), d4 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx);
        if (d1 * d2 < 0 && d3 * d4 < 0) return 0;
        return Math.min(Math.min(puntoSegmento(ax, ay, cx, cy, dx, dy), puntoSegmento(bx, by, cx, cy, dx, dy)),
                Math.min(puntoSegmento(cx, cy, ax, ay, bx, by), puntoSegmento(dx, dy, ax, ay, bx, by)));
    }

    private static double puntoSegmento(double px, double py, double ax, double ay, double bx, double by) {
        double dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
        double t = l2 == 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2));
        double ex = px - (ax + t * dx), ey = py - (ay + t * dy);
        return Math.sqrt(ex * ex + ey * ey);          // = hypot para valores en metros, sin su costo
    }

    static double metros(double lat1, double lng1, double lat2, double lng2) {
        double dLat = Math.toRadians(lat2 - lat1), dLng = Math.toRadians(lng2 - lng1);
        double h = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
    }

    /**
     * ¿Puede un punto (en el origen del plano local; {@code u} y {@code v} son los extremos de la mitad de arista {@code a}, en metros relativos
     * al punto) unirse a esta arista? Las de calle siempre; las de avenida sólo si el punto está de su lado o encima de la calzada.
     */
    private boolean ladoValido(int a, double ux, double uy, double vx, double vy, double tolerancia) {
        byte l = lado[a];
        if (l == 0) return true;
        double dx = vx - ux, dy = vy - uy, largoArista = Math.sqrt(dx * dx + dy * dy);
        if (largoArista == 0) return true;
        double izquierda = (dy * ux - dx * uy) / largoArista;      // > 0: el punto queda a la izquierda de origen→dst
        return Math.abs(izquierda) <= tolerancia || (izquierda > 0) == (l > 0);
    }

    /** Ajusta un punto a la arista más cercana (máximo {@code maxMetros}); {@code null} si no hay calle cerca. */
    public Snap ajustar(double la, double lo, double maxMetros) {
        var r = ajustarVarios(la, lo, maxMetros, 1, 0);
        return r.isEmpty() ? null : r.get(0);
    }

    /**
     * Las hasta {@code k} calles más cercanas (cada una como arista distinta) que no superen la más cercana en más de
     * {@code margenMetros}. Un punto en medio de una manzana tiene a menudo dos o tres calles casi igual de cerca: probarlas
     * todas evita elegir la que obliga a rodear.
     */
    public List<Snap> ajustarVarios(double la, double lo, double maxMetros, int k, double margenMetros) {
        return ajustarVarios(la, lo, maxMetros, k, margenMetros, TOLERANCIA_LADO_ORIGEN_METROS);
    }

    /**
     * Igual que el anterior; {@code toleranciaLado} es la distancia al eje de una avenida por debajo de la cual el punto se considera
     * sobre la calzada (puede unirse a cualquiera de sus dos andenes). Más lejos que eso, sólo se une al andén de SU lado.
     */
    public List<Snap> ajustarVarios(double la, double lo, double maxMetros, int k, double margenMetros, double toleranciaLado) {
        if (vacia()) return List.of();
        double kx = Math.cos(Math.toRadians(la)) * 111_320, ky = 110_574, maxCuadrado = maxMetros * maxMetros;
        int cx = celda(lo + 180), cy = celda(la + 90);
        if (k > 1) return ajustarVariosLista(la, lo, k, margenMetros, kx, ky, maxCuadrado, cx, cy, toleranciaLado);
        Snap mejor1 = null;
        for (int radio = 1; radio <= 2 && mejor1 == null; radio++) {
            for (int y = cy - radio; y <= cy + radio; y++) for (int x = cx - radio; x <= cx + radio; x++) {
                int[] aristas = rejilla.get(clave(x, y));
                if (aristas == null) continue;
                for (int a : aristas) {
                    int u = origen[a], v = dst[a];
                    double ux = (lng[u] - lo) * kx, uy = (lat[u] - la) * ky, vx = (lng[v] - lo) * kx, vy = (lat[v] - la) * ky;
                    double dx = vx - ux, dy = vy - uy, l2 = dx * dx + dy * dy;
                    double t = l2 == 0 ? 0 : Math.max(0, Math.min(1, -(ux * dx + uy * dy) / l2));
                    double px = ux + t * dx, py = uy + t * dy, d2 = px * px + py * py;
                    if (d2 > maxCuadrado) continue;        // la gran mayoría de las calles de las celdas vecinas queda fuera: sin raíz
                    if (!ladoValido(a, ux, uy, vx, vy, toleranciaLado)) continue;
                    double d = Math.sqrt(d2);
                    if (mejor1 == null || d < mejor1.distM()) mejor1 = new Snap(a, u, v, t, la + py / ky, lo + px / kx, d);
                }
            }
        }
        return mejor1 == null ? List.of() : List.of(mejor1);
    }

    /**
     * Varias calles: mismo resultado que reunir TODAS las aristas a ≤ {@code maxMetros}, ordenarlas por distancia (orden estable) y quedarse
     * con las {@code k} primeras que no superen la más cercana + margen, pero sin crear un objeto, ni insertar en un conjunto, ni ordenar por
     * cada arista del vecindario (en la ciudad eran cientos por punto y era el 80 % del tiempo de cada cálculo de viaje, medido con JFR).
     * Una pasada guarda (en arreglos de números) las aristas dentro del radio; la segunda solo materializa las que pueden entrar.
     */
    private List<Snap> ajustarVariosLista(double la, double lo, int k, double margenMetros, double kx, double ky,
                                           double maxCuadrado, int cx, int cy, double toleranciaLado) {
        int[] ids = new int[48];
        double[] d2s = new double[48];
        for (int radio = 1; radio <= 2; radio++) {
            int n = 0;
            double min2 = Double.MAX_VALUE;
            for (int y = cy - radio; y <= cy + radio; y++) for (int x = cx - radio; x <= cx + radio; x++) {
                int[] aristas = rejilla.get(clave(x, y));
                if (aristas == null) continue;
                for (int a : aristas) {
                    int u = origen[a], v = dst[a];
                    double ux = (lng[u] - lo) * kx, uy = (lat[u] - la) * ky, vx = (lng[v] - lo) * kx, vy = (lat[v] - la) * ky;
                    double dx = vx - ux, dy = vy - uy, l2 = dx * dx + dy * dy;
                    double t = l2 == 0 ? 0 : Math.max(0, Math.min(1, -(ux * dx + uy * dy) / l2));
                    double px = ux + t * dx, py = uy + t * dy, d2 = px * px + py * py;
                    if (d2 > maxCuadrado) continue;
                    if (!ladoValido(a, ux, uy, vx, vy, toleranciaLado)) continue;
                    if (n == ids.length) { ids = Arrays.copyOf(ids, n * 2); d2s = Arrays.copyOf(d2s, n * 2); }
                    ids[n] = a; d2s[n++] = d2;
                    if (d2 < min2) min2 = d2;
                }
            }
            if (n == 0) continue;                    // sin calle en este radio: se amplía una vez (como antes)
            double limite = Math.sqrt(min2) + margenMetros;
            List<Snap> r = new ArrayList<>(Math.min(k, 8));
            for (int i = 0; i < n; i++) {
                double d = Math.sqrt(d2s[i]);
                if (d > limite) continue;
                int a = ids[i];
                boolean repetida = false;            // una arista larga está en varias celdas: se conserva su primera aparición
                for (Snap s : r) if (s.arista() == a) { repetida = true; break; }
                if (repetida) continue;
                int u = origen[a], v = dst[a];
                double ux = (lng[u] - lo) * kx, uy = (lat[u] - la) * ky, vx = (lng[v] - lo) * kx, vy = (lat[v] - la) * ky;
                double dx = vx - ux, dy = vy - uy, l2 = dx * dx + dy * dy;
                double t = l2 == 0 ? 0 : Math.max(0, Math.min(1, -(ux * dx + uy * dy) / l2));
                double px = ux + t * dx, py = uy + t * dy;
                r.add(new Snap(a, u, v, t, la + py / ky, lo + px / kx, d));
            }
            r.sort(java.util.Comparator.comparingDouble(Snap::distM));
            return r.size() > k ? new ArrayList<>(r.subList(0, k)) : r;
        }
        return List.of();
    }

    /** Clave de la caché de ajustes: las dos coordenadas EXACTAS (bits) y los parámetros, para que un acierto sea idéntico al cálculo. */
    private record ClaveAjuste(long la, long lo, double maxMetros, int k, double margenMetros) {}
    private static final int AJUSTES_GUARDADOS_MAXIMO = 80_000;
    private final java.util.concurrent.ConcurrentHashMap<ClaveAjuste, List<Snap>> ajustesGuardados = new java.util.concurrent.ConcurrentHashMap<>();

    /**
     * Igual que {@link #ajustarVarios} pero recuerda el resultado. Pensado para los puntos que se repiten en cada consulta (las muestras de las
     * rutas cada 15 m y sus paraderos: ≈ 17 000 en toda la ciudad). La red es inmutable —una edición de pasos o una descarga nueva construye
     * otra instancia—, así que la caché nunca queda vieja: nace y muere con su red.
     */
    public List<Snap> ajustarVariosGuardado(double la, double lo, double maxMetros, int k, double margenMetros) {
        var clave = new ClaveAjuste(Double.doubleToLongBits(la), Double.doubleToLongBits(lo), maxMetros, k, margenMetros);
        var guardado = ajustesGuardados.get(clave);
        if (guardado != null) return guardado;
        var calculado = List.copyOf(ajustarVarios(la, lo, maxMetros, k, margenMetros, TOLERANCIA_LADO_DESTINO_METROS));
        if (ajustesGuardados.size() >= AJUSTES_GUARDADOS_MAXIMO) ajustesGuardados.clear();     // tope de memoria (≈ 25 MB como máximo)
        ajustesGuardados.put(clave, calculado);
        return calculado;
    }

    int ajustesGuardados() { return ajustesGuardados.size(); }

    private double costoArista(int a) { return largo[a] * FACTOR[clase[a]]; }

    // ------------------------------------------------------------------ búsqueda
    private record Item(double clave, double g, int nodo) {}

    /**
     * Cola de prioridad mínima con arreglos de números (sin un objeto por entrada ni comparador): para Dijkstra, donde cada exploración mete y
     * saca decenas de miles de nodos (era el 25 % del CPU de cada viaje, en {@code PriorityQueue.siftDown}). Admite entradas repetidas del mismo
     * nodo (las viejas se descartan al sacarlas, igual que antes), así que el resultado de Dijkstra —las distancias mínimas— es el mismo.
     */
    private static final class Monticulo {
        private double[] claves;
        private int[] nodos;
        private int tamano;
        double claveSacada;

        Monticulo(int capacidad) { claves = new double[capacidad]; nodos = new int[capacidad]; }

        boolean vacio() { return tamano == 0; }

        void agregar(double clave, int nodo) {
            if (tamano == claves.length) { claves = Arrays.copyOf(claves, tamano * 2); nodos = Arrays.copyOf(nodos, tamano * 2); }
            int i = tamano++;
            while (i > 0) {
                int padre = (i - 1) >>> 1;
                if (claves[padre] <= clave) break;
                claves[i] = claves[padre]; nodos[i] = nodos[padre];
                i = padre;
            }
            claves[i] = clave; nodos[i] = nodo;
        }

        /** Saca el de menor clave: devuelve su nodo y deja su clave en {@link #claveSacada}. */
        int sacar() {
            int salida = nodos[0];
            claveSacada = claves[0];
            int ultimo = --tamano;
            if (ultimo > 0) {
                double clave = claves[ultimo];
                int nodo = nodos[ultimo];
                int i = 0, mitad = ultimo >>> 1;
                while (i < mitad) {
                    int hijo = 2 * i + 1;
                    if (hijo + 1 < ultimo && claves[hijo + 1] < claves[hijo]) hijo++;
                    if (clave <= claves[hijo]) break;
                    claves[i] = claves[hijo]; nodos[i] = nodos[hijo];
                    i = hijo;
                }
                claves[i] = clave; nodos[i] = nodo;
            }
            return salida;
        }
    }

    /** Camino a pie desde cualquiera de las calles de salida hasta cualquiera de las de llegada (menor costo). */
    public Camino camino(List<Snap> salidas, List<Snap> llegadas, double costoMaximo) {
        double directo = Double.MAX_VALUE;
        Snap dA = null, dB = null;
        for (Snap a : salidas) for (Snap b : llegadas) if (a.arista() == b.arista()) {
            double c = a.distM() + Math.abs(a.t() - b.t()) * largo[a.arista()] * FACTOR[clase[a.arista()]] + b.distM();
            if (c < directo) { directo = c; dA = a; dB = b; }
        }
        // Colas de llegada: costo desde cada extremo de la arista de llegada hasta el punto (incluye su ajuste a la calle).
        Map<Integer, Double> cola = new HashMap<>();
        Map<Integer, Snap> metaDe = new HashMap<>();
        for (Snap b : llegadas) {
            double fb = FACTOR[clase[b.arista()]];
            double cu = b.distM() + b.t() * largo[b.arista()] * fb, cv = b.distM() + (1 - b.t()) * largo[b.arista()] * fb;
            if (cu < cola.getOrDefault(b.u(), Double.MAX_VALUE)) { cola.put(b.u(), cu); metaDe.put(b.u(), b); }
            if (cv < cola.getOrDefault(b.v(), Double.MAX_VALUE)) { cola.put(b.v(), cv); metaDe.put(b.v(), b); }
        }
        Map<Integer, Double> g = new HashMap<>();
        Map<Integer, Integer> previo = new HashMap<>();
        Map<Integer, Snap> inicioDe = new HashMap<>();
        PriorityQueue<Item> pq = new PriorityQueue<>((x, y) -> Double.compare(x.clave, y.clave));
        for (Snap a : salidas) {
            double fa = FACTOR[clase[a.arista()]];
            double gu = a.distM() + a.t() * largo[a.arista()] * fa, gv = a.distM() + (1 - a.t()) * largo[a.arista()] * fa;
            if (gu < g.getOrDefault(a.u(), Double.MAX_VALUE)) { g.put(a.u(), gu); previo.put(a.u(), -1); inicioDe.put(a.u(), a); pq.add(new Item(gu + h(a.u(), llegadas), gu, a.u())); }
            if (gv < g.getOrDefault(a.v(), Double.MAX_VALUE)) { g.put(a.v(), gv); previo.put(a.v(), -1); inicioDe.put(a.v(), a); pq.add(new Item(gv + h(a.v(), llegadas), gv, a.v())); }
        }
        double mejor = directo;
        int fin = -1;
        while (!pq.isEmpty()) {
            Item it = pq.poll();
            if (it.clave >= mejor || it.g > costoMaximo) break;
            if (it.g > g.getOrDefault(it.nodo, Double.MAX_VALUE)) continue;
            Double c = cola.get(it.nodo);
            if (c != null && it.g + c < mejor) { mejor = it.g + c; fin = it.nodo; }
            for (int e = ini[it.nodo]; e < ini[it.nodo + 1]; e++) {
                int w = dst[e];
                if (!valido[w]) continue;
                double ng = it.g + costoArista(e);
                if (ng < g.getOrDefault(w, Double.MAX_VALUE)) {
                    g.put(w, ng); previo.put(w, it.nodo);
                    pq.add(new Item(ng + h(w, llegadas), ng, w));
                }
            }
        }
        if (fin < 0) {
            if (dA == null) return null;
            return new Camino(List.of(new double[]{dA.lng(), dA.lat()}, new double[]{dB.lng(), dB.lat()}),
                    Math.abs(dA.t() - dB.t()) * largo[dA.arista()]);
        }
        List<Integer> nodos = new ArrayList<>();
        int n0 = fin;
        for (int n = fin; n >= 0; n = previo.get(n)) { nodos.add(n); n0 = n; }
        java.util.Collections.reverse(nodos);
        Snap a = inicioDe.get(n0), b = metaDe.get(fin);
        List<double[]> puntos = new ArrayList<>(nodos.size() + 2);
        puntos.add(new double[]{a.lng(), a.lat()});
        for (int n : nodos) {
            double[] ultimo = puntos.get(puntos.size() - 1);
            if (ultimo[0] != lng[n] || ultimo[1] != lat[n]) puntos.add(new double[]{lng[n], lat[n]});     // la arista de cruce no mueve el punto
        }
        puntos.add(new double[]{b.lng(), b.lat()});
        double total = 0;
        for (int i = 1; i < puntos.size(); i++)
            total += metros(puntos.get(i - 1)[1], puntos.get(i - 1)[0], puntos.get(i)[1], puntos.get(i)[0]);
        return new Camino(List.copyOf(puntos), total);
    }

    private double h(int nodo, List<Snap> metas) {
        double m = Double.MAX_VALUE;
        for (Snap s : metas) m = Math.min(m, metros(lat[nodo], lng[nodo], s.lat(), s.lng()));
        return m * FACTOR_MINIMO;      // admisible: ninguna arista cuesta menos que FACTOR_MINIMO por metro (los puentes, 0,75)
    }

    /**
     * Costo a pie (≈ metros, incluye lo que separa el punto de partida de su calle) desde las calles de salida a muchos
     * destinos con una sola exploración. {@code NaN} = sin camino dentro del costo máximo. El ajuste de cada destino a su
     * calle ({@code distM}) no se incluye: lo suma quien llama. El costo incluye lo que vale cruzar avenidas a nivel.
     */
    public double[] costosDesde(List<Snap> salidas, List<Snap> destinos, double costoMaximo) {
        return explorar(salidas, destinos, costoMaximo, false)[0];
    }

    /**
     * Igual que {@link #costosDesde} pero también devuelve, por destino, la parte del costo que es PENALIZACIÓN por cruzar avenidas a nivel
     * (no son metros caminados). {@code [0]} = costo total, {@code [1]} = penalización; metros que se caminan ≈ {@code [0] - [1]}.
     */
    public double[][] costosDesdeDetallado(List<Snap> salidas, List<Snap> destinos, double costoMaximo) {
        return explorar(salidas, destinos, costoMaximo, true);
    }

    private double[][] explorar(List<Snap> salidas, List<Snap> destinos, double costoMaximo, boolean conPenal) {
        double[] r = new double[destinos.size()], penR = new double[destinos.size()];
        Arrays.fill(r, Double.NaN);
        int n = lat.length;
        boolean[] pendiente = new boolean[n];
        int faltan = 0;
        for (Snap d : destinos) if (d != null) {
            if (!pendiente[d.u()]) { pendiente[d.u()] = true; faltan++; }
            if (!pendiente[d.v()]) { pendiente[d.v()] = true; faltan++; }
        }
        double[] g = new double[n];
        Arrays.fill(g, Double.MAX_VALUE);
        double[] pen = conPenal ? new double[n] : null;     // parte de g que es cobro de cruce (se hereda del camino elegido)
        boolean[] fijo = new boolean[n];
        var cola = new Monticulo(4096);
        for (Snap a : salidas) {
            double fa = FACTOR[clase[a.arista()]];
            double gu = a.distM() + a.t() * largo[a.arista()] * fa, gv = a.distM() + (1 - a.t()) * largo[a.arista()] * fa;
            if (gu < g[a.u()]) { g[a.u()] = gu; cola.agregar(gu, a.u()); }
            if (gv < g[a.v()]) { g[a.v()] = gv; cola.agregar(gv, a.v()); }
        }
        while (!cola.vacio() && faltan > 0) {
            int nodo = cola.sacar();
            double gNodo = cola.claveSacada;
            if (gNodo > costoMaximo) break;
            if (fijo[nodo]) continue;
            fijo[nodo] = true;
            if (pendiente[nodo]) faltan--;
            for (int e = ini[nodo]; e < ini[nodo + 1]; e++) {
                int w = dst[e];
                if (!valido[w] || fijo[w]) continue;
                double ng = gNodo + costoArista(e);
                if (ng < g[w]) {
                    g[w] = ng;
                    if (pen != null) pen[w] = pen[nodo] + (clase[e] == CRUCE ? largo[e] : 0);
                    cola.agregar(ng, w);
                }
            }
        }
        for (int i = 0; i < r.length; i++) {
            Snap d = destinos.get(i);
            if (d == null) continue;
            double fb = FACTOR[clase[d.arista()]];
            double viaU = fijo[d.u()] ? g[d.u()] + d.t() * largo[d.arista()] * fb : Double.NaN;
            double viaV = fijo[d.v()] ? g[d.v()] + (1 - d.t()) * largo[d.arista()] * fb : Double.NaN;
            double mejor, penalMejor = 0;
            if (Double.isNaN(viaU)) { mejor = viaV; if (pen != null && !Double.isNaN(viaV)) penalMejor = pen[d.v()]; }
            else if (Double.isNaN(viaV)) { mejor = viaU; if (pen != null) penalMejor = pen[d.u()]; }
            else if (viaV < viaU) { mejor = viaV; if (pen != null) penalMejor = pen[d.v()]; }
            else { mejor = viaU; if (pen != null) penalMejor = pen[d.u()]; }
            for (Snap a : salidas) if (a.arista() == d.arista()) {
                double directo = a.distM() + Math.abs(a.t() - d.t()) * largo[d.arista()] * fb;
                if (Double.isNaN(mejor) || directo < mejor) { mejor = directo; penalMejor = 0; }
            }
            r[i] = mejor;
            penR[i] = penalMejor;
        }
        return new double[][]{r, penR};
    }

    /** Cobertura de la red: sirve para decidir si un punto cae fuera de la zona cargada. */
    public boolean cubre(double la, double lo) {
        return !vacia() && la >= minLat - 0.01 && la <= maxLat + 0.01 && lo >= minLng - 0.01 && lo <= maxLng + 0.01;
    }

    // ------------------------------------------------------------------ persistencia compacta
    /** Exportación de caminos para guardar en disco (se reconstruye con {@link Constructor}). */
    public record CaminoGuardado(long[] ids, double[] lats, double[] lngs, byte clase) {}
}
