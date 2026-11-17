package co.edu.usta.spevb.service;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.web.server.ResponseStatusException;
import org.testcontainers.DockerClientFactory;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import java.sql.Connection;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * Logros y racha por cuenta contra PostgreSQL REAL (Fase D): idempotencia por (cuenta, viaje), días de Bogotá, racha con día de gracia, límites, práctica sin viajes, insignias validadas
 * y aislamiento entre cuentas. Base: contenedor desechable o, sin Docker, la base dedicada de SEVB_TEST_PG_URL (nombre terminado en _test o _e2e; su contenido se BORRA). Si no hay ninguna, se OMITE.
 */
class LogrosPostgresTest {
    private static PostgreSQLContainer contenedor;
    private static JdbcTemplate jdbc;
    private static DriverManagerDataSource ds;
    private LogrosService logros;
    private long ana, beto;

    @BeforeAll
    static void base() throws Exception {
        String url = System.getenv("SEVB_TEST_PG_URL");
        if (url != null && !url.isBlank()) {
            if (!url.matches("jdbc:postgresql://(127\\.0\\.0\\.1|localhost|\\[::1\\])(:\\d+)?/[^/?]+(_test|_e2e)(\\?.*)?"))
                throw new IllegalStateException("SEVB_TEST_PG_URL debe apuntar a este equipo y a una base cuyo nombre termine en _test o _e2e.");
            ds = new DriverManagerDataSource(url, System.getenv().getOrDefault("SEVB_TEST_PG_USER", "postgres"), System.getenv().getOrDefault("SEVB_TEST_PG_PASSWORD", ""));
        } else {
            assumeTrue(DockerClientFactory.instance().isDockerAvailable(), "Sin Docker y sin SEVB_TEST_PG_URL: se OMITE (no se da por aprobada)");
            contenedor = new PostgreSQLContainer(DockerImageName.parse("postgres:17")).withDatabaseName("spevb_test").withUsername("spevb").withPassword("clave-de-prueba-desechable");
            contenedor.start();
            ds = new DriverManagerDataSource(contenedor.getJdbcUrl(), contenedor.getUsername(), contenedor.getPassword());
        }
        jdbc = new JdbcTemplate(ds);
        jdbc.execute("DROP TABLE IF EXISTS logros_viaje, logros_perfil, viajes_compartidos, usuario_datos, sesiones, usuarios CASCADE");
        try (Connection c = ds.getConnection()) {
            for (String v : List.of("V6__cuentas.sql", "V7__inicio_de_sesion_google.sql", "V12__foto_de_perfil_google.sql", "V13__viaje_compartido.sql", "V14__cuentas_identidad_google.sql", "V15__logros_viajes.sql"))
                ScriptUtils.executeSqlScript(c, new ClassPathResource("db/migration/" + v));
        }
    }

    @AfterAll
    static void cerrar() { if (contenedor != null) contenedor.stop(); }

    @BeforeEach
    void limpiar() {
        jdbc.update("DELETE FROM usuarios");
        logros = new LogrosService(jdbc);
        ana = jdbc.queryForObject("INSERT INTO usuarios (correo, nombre, clave_hash) VALUES ('ana@x.co', 'Ana', 'x') RETURNING id", Long.class);
        beto = jdbc.queryForObject("INSERT INTO usuarios (correo, nombre, clave_hash) VALUES ('beto@x.co', 'Beto', 'x') RETURNING id", Long.class);
    }

    /** Un momento a mediodía de Bogotá del día dado (para no cruzar medianoche por accidente). */
    private static long mediodia(String dia) { return LocalDate.parse(dia).atTime(12, 0).toInstant(ZoneOffset.ofHours(-5)).toEpochMilli(); }

    private static long ahora(String dia) { return mediodia(dia) + 3_600_000L; }

    @Test
    void elMismoViajeCuentaUnaSolaVezAunqueSeReenvieDesdeDosPestanas() {
        long t = mediodia("2026-03-10"), ahora = ahora("2026-03-10");
        var primero = logros.registrar(ana, "viaje-aaaa01", t, 1, ahora);
        assertTrue(primero.nuevo());
        assertEquals(List.of("primero"), primero.nuevos());
        var repetido = logros.registrar(ana, "viaje-aaaa01", t, 1, ahora);
        assertFalse(repetido.nuevo());
        assertTrue(repetido.nuevos().isEmpty());
        assertEquals(1, logros.estado(ana, ahora).m().viajes());
    }

    @Test
    void sinSubidaConfirmadaOConDatosInvalidosNoCuenta() {
        long t = mediodia("2026-03-10"), ahora = ahora("2026-03-10");
        assertThrows(ResponseStatusException.class, () -> logros.registrar(ana, "viaje-aaaa02", t, 0, ahora), "sin buses confirmados no cuenta");
        assertThrows(ResponseStatusException.class, () -> logros.registrar(ana, "x", t, 1, ahora), "id corto");
        assertThrows(ResponseStatusException.class, () -> logros.registrar(ana, "viaje con espacios!", t, 1, ahora), "id con caracteres no permitidos");
        assertThrows(ResponseStatusException.class, () -> logros.registrar(ana, "viaje-aaaa03", ahora + 3_600_000L, 1, ahora), "llegada en el futuro");
        assertThrows(ResponseStatusException.class, () -> logros.registrar(ana, "viaje-aaaa04", ahora - 40L * 86_400_000L, 1, ahora), "llegada demasiado vieja");
        assertEquals(0, logros.estado(ana, ahora).m().viajes());
    }

    @Test
    void laRachaUsaDiasDeBogotaConUnDiaDeGraciaYElJuevesVale0() {
        long jueves = ahora("2026-03-05");
        logros.registrar(ana, "viaje-lunes01", mediodia("2026-03-02"), 1, jueves);
        assertEquals(0, logros.estado(ana, jueves).m().rachaActual(), "lunes con martes y miércoles vacíos: el jueves la racha es 0");
        assertEquals(1, logros.estado(ana, jueves).m().mejorRacha(), "pero la mejor se conserva");
        assertEquals(1, logros.estado(ana, ahora("2026-03-04")).m().rachaActual(), "el miércoles aún se puede continuar");
        logros.registrar(ana, "viaje-jueves1", mediodia("2026-03-05"), 1, jueves);
        assertEquals(1, logros.estado(ana, jueves).m().rachaActual(), "el primer viaje del jueves vale 1");
        logros.registrar(ana, "viaje-jueves2", mediodia("2026-03-05") + 60_000L, 1, jueves);
        assertEquals(1, logros.estado(ana, jueves).m().rachaActual(), "varios viajes el mismo día cuentan una vez en la racha");
        assertEquals(3, logros.estado(ana, jueves).m().viajes(), "pero todos cuentan en el total");
    }

    @Test
    void unViajeTardioOFueraDeOrdenReordenaLaRachaSinDuplicar() {
        long ahora = ahora("2026-03-10");
        logros.registrar(ana, "viaje-dia10aa", mediodia("2026-03-10"), 1, ahora);
        logros.registrar(ana, "viaje-dia08aa", mediodia("2026-03-08"), 1, ahora);      // llega tarde (reintento sin conexión) y fuera de orden
        logros.registrar(ana, "viaje-dia09aa", mediodia("2026-03-09"), 1, ahora);
        var e = logros.estado(ana, ahora).m();
        assertEquals(3, e.rachaActual());
        assertEquals(3, e.mejorEstricta());
        assertTrue(logros.estado(ana, ahora).logros().contains("racha3"));
    }

    @Test
    void elTransbordoCuentaUnaVezYSoloConDosSubidasConfirmadas() {
        long ahora = ahora("2026-03-10");
        logros.registrar(ana, "viaje-un-bus1", mediodia("2026-03-10"), 1, ahora);
        assertFalse(logros.estado(ana, ahora).logros().contains("transbordo"), "un viaje de un solo bus no es transbordo");
        var dos = logros.registrar(ana, "viaje-dos-bus", mediodia("2026-03-10") + 1000, 2, ahora);
        assertTrue(dos.nuevos().contains("transbordo"));
        assertEquals(1, logros.estado(ana, ahora).m().transbordos());
    }

    @Test
    void practicarDaAprendizPeroNoSumaViajesNiRacha() {
        long ahora = ahora("2026-03-10");
        var r = logros.practica(ana, ahora);
        assertEquals(List.of("practica"), r.nuevos());
        var e = logros.estado(ana, ahora).m();
        assertEquals(0, e.viajes());
        assertEquals(0, e.rachaActual());
        assertTrue(logros.practica(ana, ahora).nuevos().isEmpty(), "una sola vez");
    }

    @Test
    void laInsigniaSoloSeEquipaSiYaSeGanoYUnaCuentaNoVeLoDeOtra() {
        long ahora = ahora("2026-03-10");
        assertThrows(ResponseStatusException.class, () -> logros.equipar(ana, "primero", ahora), "sin ganar no se equipa");
        assertThrows(ResponseStatusException.class, () -> logros.equipar(ana, "inventada", ahora), "id inexistente");
        logros.registrar(ana, "viaje-aaaa10", mediodia("2026-03-10"), 1, ahora);
        assertEquals("primero", logros.equipar(ana, "primero", ahora).insignia());
        assertNull(logros.equipar(ana, null, ahora).insignia(), "se puede quitar");
        logros.equipar(ana, "primero", ahora);
        assertEquals(0, logros.estado(beto, ahora).m().viajes(), "Beto no ve los viajes de Ana");
        assertNull(logros.estado(beto, ahora).insignia(), "ni su insignia");
        // el mismo id de viaje en otra cuenta cuenta aparte (la clave es cuenta + viaje)
        assertTrue(logros.registrar(beto, "viaje-aaaa10", mediodia("2026-03-10"), 1, ahora).nuevo());
    }

    @Test
    void elLimiteDeViajesPorDiaProtegeLaTabla() {
        long ahora = ahora("2026-03-10");
        for (int i = 0; i < LogrosService.VIAJES_POR_DIA_MAX; i++) logros.registrar(ana, String.format("viaje-lote%03d", i), mediodia("2026-03-10") + i, 1, ahora);
        assertThrows(ResponseStatusException.class, () -> logros.registrar(ana, "viaje-lote999", mediodia("2026-03-10") + 999, 1, ahora));
    }

    @Test
    void borrarLaCuentaBorraSusLogros() {
        long ahora = ahora("2026-03-10");
        logros.registrar(ana, "viaje-aaaa11", mediodia("2026-03-10"), 1, ahora);
        logros.practica(ana, ahora);
        jdbc.update("DELETE FROM usuarios WHERE id = ?", ana);
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM logros_viaje WHERE usuario_id = ?", Integer.class, ana));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM logros_perfil WHERE usuario_id = ?", Integer.class, ana));
    }
}
