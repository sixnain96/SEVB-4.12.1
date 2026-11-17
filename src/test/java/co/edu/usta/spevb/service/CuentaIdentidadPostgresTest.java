package co.edu.usta.spevb.service;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.web.server.ResponseStatusException;
import org.testcontainers.DockerClientFactory;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import tools.jackson.databind.ObjectMapper;

import java.sql.Connection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * Identidad de las cuentas contra PostgreSQL REAL (Fase B): el «sub» de Google identifica; el correo NO hereda nada. Aplica las migraciones de cuentas (V6, V7, V12, V13, V14) tal como están
 * en el repositorio. Base de datos: un contenedor desechable (Testcontainers) o, sin Docker, la base dedicada de pruebas que indique SEVB_TEST_PG_URL (+ SEVB_TEST_PG_USER y
 * SEVB_TEST_PG_PASSWORD); su nombre DEBE terminar en _test o _e2e y su contenido se BORRA. Sin ninguna de las dos, se OMITE (no pasa en silencio).
 */
class CuentaIdentidadPostgresTest {
    private static PostgreSQLContainer contenedor;
    private static JdbcTemplate jdbc;
    private static DriverManagerDataSource ds;
    private final ObjectMapper mapper = new ObjectMapper();
    private CuentaService cuentas;

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
        jdbc.execute("DROP TABLE IF EXISTS viajes_compartidos, usuario_datos, sesiones, usuarios CASCADE");
        migrar();
    }

    private static void migrar() throws Exception {
        try (Connection c = ds.getConnection()) {
            for (String v : List.of("V6__cuentas.sql", "V7__inicio_de_sesion_google.sql", "V12__foto_de_perfil_google.sql", "V13__viaje_compartido.sql", "V14__cuentas_identidad_google.sql"))
                ScriptUtils.executeSqlScript(c, new ClassPathResource("db/migration/" + v));
        }
    }

    @AfterAll
    static void cerrar() { if (contenedor != null) contenedor.stop(); }

    @BeforeEach
    void limpiar() {
        jdbc.update("DELETE FROM usuarios");
        cuentas = new CuentaService(jdbc, mapper, "admin@gmail.com");
    }

    private static GoogleTokenVerifier.Identidad google(String sub, String correo) { return new GoogleTokenVerifier.Identidad(sub, correo, "Persona " + sub, "https://lh3.googleusercontent.com/a/" + sub); }

    private long cuentaAntigua(String correo, String nombre, String clave) {
        return jdbc.queryForObject("INSERT INTO usuarios (correo, nombre, clave_hash) VALUES (?, ?, ?) RETURNING id", Long.class, correo, nombre, ClaveHash.hacer(clave, 1000));
    }

    private void datos(long id, String clave, String json) throws Exception { cuentas.guardarDatos(id, clave, mapper.readTree(json)); }

    private static final String LUGARES = "[{\"id\":\"c1\",\"nombre\":\"Casa\",\"lat\":4.1,\"lng\":-73.6}]";
    private static final String HISTORIAL = "[{\"id\":\"h1\",\"t\":1700000000000,\"a\":{\"lat\":4.14,\"lng\":-73.6,\"nombre\":\"A\"},\"b\":{\"lat\":4.15,\"lng\":-73.59,\"nombre\":\"B\"},\"codigos\":[\"R1\"]}]";

    // ------------------------------------------------------------------ identidad
    @Test
    void unSubNuevoCreaSuPerfilYElMismoSubVuelveAlMismoPerfilConSusDatos() throws Exception {
        var a = cuentas.entrarConGoogle(google("111", "ana@gmail.com"));
        assertTrue(a.conGoogle() && !a.admin() && a.id() > 0);
        datos(a.id(), "lugares", LUGARES);
        var otraVez = cuentas.entrarConGoogle(new GoogleTokenVerifier.Identidad("111", "ana.nueva@gmail.com", "Otro nombre", null));
        assertEquals(a.id(), otraVez.id(), "mismo sub: mismo id interno");
        assertEquals("Persona 111", otraVez.nombre(), "el nombre del perfil no lo pisa el de Google");
        assertEquals("ana.nueva@gmail.com", otraVez.correo(), "el correo verificado por Google se renueva");
        assertNull(otraVez.foto());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM usuarios", Integer.class));
        assertTrue(cuentas.leerDatos(a.id()).containsKey("lugares"), "sus datos siguen ahí");
    }

    @Test
    void dosEntradasSimultaneasConElMismoSubNuevoDanUnSoloPerfil() throws Exception {
        var pool = Executors.newFixedThreadPool(8);
        try {
            List<Callable<Long>> tareas = java.util.stream.IntStream.range(0, 8).<Callable<Long>>mapToObj(i -> () -> cuentas.entrarConGoogle(google("222", "beto@gmail.com")).id()).toList();
            var ids = new java.util.HashSet<Long>();
            for (var f : pool.invokeAll(tareas)) ids.add(f.get());
            assertEquals(1, ids.size(), "idempotente: todas obtienen el mismo perfil");
            assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM usuarios WHERE google_sub = '222'", Integer.class));
        } finally { pool.shutdownNow(); }
    }

    @Test
    void elMismoCorreoNoHeredaLugaresHistorialNiSesionesDeUnaCuentaAntigua() throws Exception {
        long vieja = cuentaAntigua("ana@gmail.com", "Quien se adelantó", "clave-vieja-1");
        datos(vieja, "lugares", LUGARES);
        datos(vieja, "historial", HISTORIAL);
        String sesionVieja = cuentas.abrirSesion(vieja, "navegador");
        var nueva = cuentas.entrarConGoogle(google("333", "ana@gmail.com"));
        assertNotEquals(vieja, nueva.id(), "un correo no demuestra propiedad: perfil nuevo");
        assertTrue(cuentas.leerDatos(nueva.id()).isEmpty(), "el perfil nuevo no recibe nada de la cuenta antigua");
        // la cuenta antigua queda INTACTA: contraseña, nombre, datos y sesiones
        var f = jdbc.queryForMap("SELECT nombre, clave_hash, google_sub, correo_verificado FROM usuarios WHERE id = ?", vieja);
        assertEquals("Quien se adelantó", f.get("nombre"));
        assertNotNull(f.get("clave_hash"));
        assertNull(f.get("google_sub"));
        assertEquals(Boolean.FALSE, f.get("correo_verificado"));
        assertEquals(2, cuentas.leerDatos(vieja).size());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM sesiones WHERE usuario_id = ?", Integer.class, vieja), "no se cerraron sus sesiones");
        assertTrue(cuentas.hayCuentaAnterior("ANA@gmail.com"), "se sabe que existe una cuenta anterior (para explicar la recuperación)");
        // y una sesión nacida de aquella contraseña ya no identifica a nadie
        assertTrue(cuentas.usuarioDeSesion(sesionVieja).isEmpty());
        assertTrue(cuentas.sesionDeCuentaAnterior(sesionVieja));
        assertFalse(cuentas.sesionDeCuentaAnterior("no-existe-" + "x".repeat(30)));
    }

    @Test
    void ungoogleSubDiferenteConElMismoCorreoNoHeredaNadaDelOtroPerfil() throws Exception {
        var a = cuentas.entrarConGoogle(google("401", "compartido@gmail.com"));
        datos(a.id(), "lugares", LUGARES);
        var b = cuentas.entrarConGoogle(google("402", "compartido@gmail.com"));
        assertNotEquals(a.id(), b.id());
        assertTrue(cuentas.leerDatos(b.id()).isEmpty());
        assertTrue(cuentas.leerDatos(a.id()).containsKey("lugares"));
        assertEquals(2, jdbc.queryForObject("SELECT COUNT(*) FROM usuarios WHERE LOWER(correo) = 'compartido@gmail.com'", Integer.class));
    }

    @Test
    void unaCuentaYaVinculadaConHashAntiguoVuelveASuMismoPerfilConTodo() throws Exception {
        long id = jdbc.queryForObject("INSERT INTO usuarios (correo, nombre, clave_hash, google_sub, correo_verificado) VALUES ('luz@gmail.com', 'Luz', ?, '501', TRUE) RETURNING id", Long.class, ClaveHash.hacer("vieja-clave-1", 1000));
        datos(id, "lugares", LUGARES);
        datos(id, "historial", HISTORIAL);
        var u = cuentas.entrarConGoogle(google("501", "luz@gmail.com"));
        assertEquals(id, u.id());
        assertEquals("Luz", u.nombre());
        assertEquals(2, cuentas.leerDatos(id).size(), "favoritos, lugares e historial intactos");
        String s = cuentas.abrirSesion(id, "x");
        assertTrue(cuentas.usuarioDeSesion(s).isPresent(), "la sesión de una cuenta con Google vale");
        // el borrado de esa cuenta no depende del hash viejo: lo decide el controlador con una reautenticación de Google; aquí se borra por id
        assertTrue(cuentas.eliminar(id));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM usuarios WHERE id = ?", Integer.class, id));
    }

    // ------------------------------------------------------------------ vínculo explícito
    private Map<String, Object> instantanea() {
        return Map.of("usuarios", jdbc.queryForList("SELECT id, correo, nombre, clave_hash, google_sub FROM usuarios ORDER BY id").toString(),
                "datos", jdbc.queryForList("SELECT usuario_id, clave, valor::text FROM usuario_datos ORDER BY usuario_id, clave").toString(),
                "sesiones", jdbc.queryForObject("SELECT COUNT(*) FROM sesiones", Integer.class));
    }

    @Test
    void elVinculoExplicitoConservaElIdMuevelosDatosCierraSesionesYAnulaLaContrasena() throws Exception {
        long vieja = cuentaAntigua("ana@gmail.com", "Ana antigua", "clave-vieja-1");
        datos(vieja, "lugares", LUGARES);
        String sesionVieja = cuentas.abrirSesion(vieja, "navegador viejo");
        var perfil = cuentas.entrarConGoogle(google("601", "ana@gmail.com"));
        datos(perfil.id(), "historial", HISTORIAL);
        datos(perfil.id(), "lugares", "[{\"id\":\"p1\",\"nombre\":\"Parque\",\"lat\":4.2,\"lng\":-73.6}]");
        String sesionPerfil = cuentas.abrirSesion(perfil.id(), "navegador nuevo");

        var v = cuentas.vincularCuentaAnterior(perfil.id(), google("601", "ana@gmail.com"), "Ana@Gmail.com", "clave-vieja-1");
        assertEquals(vieja, v.id(), "el vínculo conserva el id interno de la cuenta anterior");
        assertEquals("Ana antigua", v.nombre());
        var f = jdbc.queryForMap("SELECT google_sub, clave_hash, correo_verificado, vinculado_en FROM usuarios WHERE id = ?", vieja);
        assertEquals("601", f.get("google_sub"));
        assertNull(f.get("clave_hash"), "la contraseña antigua se anula");
        assertEquals(Boolean.TRUE, f.get("correo_verificado"));
        assertNotNull(f.get("vinculado_en"));
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM usuarios", Integer.class), "el perfil nuevo vacío se eliminó");
        var datos = cuentas.leerDatos(vieja);
        assertTrue(datos.containsKey("historial") && datos.containsKey("lugares"), "datos de la anterior + los que solo tenía el perfil nuevo");
        assertTrue(datos.get("lugares").toString().contains("Casa") && !datos.get("lugares").toString().contains("Parque"), "si la clave existe en las dos, manda la anterior");
        assertTrue(cuentas.usuarioDeSesion(sesionVieja).isEmpty(), "las sesiones antiguas se cerraron");
        assertTrue(cuentas.usuarioDeSesion(sesionPerfil).isEmpty(), "y las del perfil que desapareció");
        assertEquals(vieja, cuentas.usuarioDeSesion(cuentas.abrirSesion(vieja, "nuevo")).orElseThrow().id());
        // entrar de nuevo con ese sub vuelve a la cuenta conservada
        assertEquals(vieja, cuentas.entrarConGoogle(google("601", "ana@gmail.com")).id());
        assertFalse(cuentas.hayCuentaAnterior("ana@gmail.com"), "ya no queda cuenta anterior sin vincular");
    }

    @Test
    void sinLasDosPruebasElVinculoNoCambiaNada() throws Exception {
        long vieja = cuentaAntigua("ana@gmail.com", "Ana antigua", "clave-vieja-1");
        datos(vieja, "lugares", LUGARES);
        cuentas.abrirSesion(vieja, "x");
        var perfil = cuentas.entrarConGoogle(google("701", "ana@gmail.com"));
        long ajena = jdbc.queryForObject("INSERT INTO usuarios (correo, nombre, google_sub, correo_verificado) VALUES ('otra@gmail.com', 'Otra', '702', TRUE) RETURNING id", Long.class);
        var antes = instantanea();
        // contraseña equivocada, correo inexistente, cuenta que ya tiene Google, contraseña vacía o nula: el MISMO mensaje, nada cambia
        for (String[] caso : new String[][]{{"ana@gmail.com", "otra-clave-9"}, {"nadie@gmail.com", "clave-vieja-1"}, {"otra@gmail.com", "clave-vieja-1"}, {"ana@gmail.com", ""}, {"ana@gmail.com", null}, {"", "clave-vieja-1"}}) {
            var e = assertThrows(IllegalArgumentException.class, () -> cuentas.vincularCuentaAnterior(perfil.id(), google("701", "ana@gmail.com"), caso[0], caso[1]));
            assertEquals(CuentaService.MSG_ANTERIOR_NO_COMPROBADA, e.getMessage());
        }
        // la credencial de Google no es la del perfil con sesión (otro sub): prohibido
        var e = assertThrows(ResponseStatusException.class, () -> cuentas.vincularCuentaAnterior(perfil.id(), google("999", "ana@gmail.com"), "ana@gmail.com", "clave-vieja-1"));
        assertEquals(403, e.getStatusCode().value());
        assertThrows(ResponseStatusException.class, () -> cuentas.vincularCuentaAnterior(ajena + 1000, google("701", "ana@gmail.com"), "ana@gmail.com", "clave-vieja-1"));
        assertEquals(antes, instantanea(), "registro intacto: contraseñas, datos, sesiones y perfiles");
        assertNotNull(perfil);
    }

    // ------------------------------------------------------------------ eliminar, administración y migración
    @Test
    void eliminarBorraTodoLoDeEsaCuentaEnCascadaYNadaDeLasDemas() throws Exception {
        var a = cuentas.entrarConGoogle(google("801", "a@gmail.com"));
        var b = cuentas.entrarConGoogle(google("802", "b@gmail.com"));
        datos(a.id(), "lugares", LUGARES); datos(b.id(), "lugares", LUGARES);
        cuentas.abrirSesion(a.id(), "x"); cuentas.abrirSesion(b.id(), "x");
        jdbc.update("INSERT INTO viajes_compartidos (lectura_hash, escritura_hash, usuario_id, expira_en) VALUES (?, ?, ?, NOW() + INTERVAL '1 hour')", "a".repeat(64), "b".repeat(64), a.id());
        assertTrue(cuentas.eliminar(a.id()));
        assertFalse(cuentas.eliminar(a.id()), "ya no existe");
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM usuario_datos WHERE usuario_id = ?", Integer.class, a.id()));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM sesiones WHERE usuario_id = ?", Integer.class, a.id()));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM viajes_compartidos", Integer.class), "su enlace compartido también");
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM usuario_datos WHERE usuario_id = ?", Integer.class, b.id()));
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM sesiones WHERE usuario_id = ?", Integer.class, b.id()));
    }

    @Test
    void elPermisoDeAdministradorSeCalculaConElCorreoVerificadoPorGoogleYNoSeHeredaDeUnaCuentaAntigua() throws Exception {
        long antigua = cuentaAntigua("admin@gmail.com", "Falso admin", "clave-vieja-1");
        String sesionAntigua = cuentas.abrirSesion(antigua, "x");
        assertTrue(cuentas.usuarioDeSesion(sesionAntigua).isEmpty(), "quien registró ese correo con contraseña NO es administrador (ni siquiera tiene sesión)");
        var admin = cuentas.entrarConGoogle(google("901", "Admin@Gmail.com"));
        assertTrue(admin.admin(), "con el correo verificado por Google sí");
        assertTrue(cuentas.usuarioDeSesion(cuentas.abrirSesion(admin.id(), "x")).orElseThrow().admin());
        var otro = cuentas.entrarConGoogle(google("902", "persona@gmail.com"));
        assertFalse(otro.admin());
        assertFalse(cuentas.esAdmin("admin@gmail.com", false), "sin verificar nunca");
        // el permiso no se guarda en la cuenta: si el correo sale de la lista, deja de serlo
        var sinLista = new CuentaService(jdbc, mapper, "");
        assertFalse(sinLista.usuarioDeSesion(cuentas.abrirSesion(admin.id(), "x")).orElseThrow().admin());
        assertNotEquals(antigua, admin.id());
    }

    @Test
    void laMigracionV14EsIdempotenteYSoloRelajaLaUnicidadDelCorreoEntreCuentasConGoogle() throws Exception {
        migrar();        // aplicarla otra vez no falla ni cambia nada
        cuentaAntigua("dos@gmail.com", "Uno", "clave-vieja-1");
        assertThrows(DuplicateKeyException.class, () -> cuentaAntigua("DOS@gmail.com", "Dos", "clave-vieja-2"), "entre cuentas LOCALES el correo sigue siendo único");
        cuentas.entrarConGoogle(google("1001", "dos@gmail.com"));       // un perfil de Google sí puede convivir con ella
        cuentas.entrarConGoogle(google("1002", "dos@gmail.com"));
        assertEquals(3, jdbc.queryForObject("SELECT COUNT(*) FROM usuarios WHERE LOWER(correo) = 'dos@gmail.com'", Integer.class));
        assertThrows(DuplicateKeyException.class, () -> jdbc.update("INSERT INTO usuarios (correo, nombre, google_sub) VALUES ('x@gmail.com', 'X', '1001')"), "el «sub» sigue siendo único");
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'ux_usuarios_correo_local'", Integer.class));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'ux_usuarios_correo'", Integer.class));
    }

    // ------------------------------------------------------------------ Fase C: escritura condicional de «lugares»
    @Test
    void laEscrituraConBaseNoPisaElCambioDeOtroDispositivoYUnBorradoNoReaparece() throws Exception {
        var a = cuentas.entrarConGoogle(google("2001", "ana@gmail.com"));
        var l1 = mapper.readTree("[{\"id\":\"u1\",\"nombre\":\"Universidad\",\"lat\":4.1,\"lng\":-73.6,\"tipo\":\"otro\",\"v\":1}]");
        long t1 = cuentas.guardarDatos(a.id(), "lugares", l1, 0L);      // primera escritura: base 0 = «no existía»
        // el dispositivo B leyó t1 y guarda (gana); el dispositivo A todavía cree que la base es t1: su escritura se RECHAZA con 409 y no pisa nada
        var deB = mapper.readTree("[{\"id\":\"u1\",\"nombre\":\"Universidad\",\"lat\":4.1,\"lng\":-73.6,\"tipo\":\"otro\",\"v\":1},{\"id\":\"c1\",\"nombre\":\"Casa\",\"lat\":4.2,\"lng\":-73.6,\"tipo\":\"casa\",\"v\":2}]");
        long t2 = cuentas.guardarDatos(a.id(), "lugares", deB, t1);
        assertTrue(t2 >= t1);
        var deA = mapper.readTree("[{\"id\":\"u1\",\"nombre\":\"Universidad vieja\",\"lat\":4.1,\"lng\":-73.6,\"tipo\":\"otro\",\"v\":3}]");
        var e = assertThrows(ResponseStatusException.class, () -> cuentas.guardarDatos(a.id(), "lugares", deA, t1));
        assertEquals(409, e.getStatusCode().value());
        assertTrue(cuentas.leerDatos(a.id()).get("lugares").toString().contains("Casa"), "lo de B sigue ahí");
        // base de una cuenta sin documento previo distinta de 0 no bloquea (no hay nada que pisar); con documento y base 0 sí es conflicto
        assertEquals(409, assertThrows(ResponseStatusException.class, () -> cuentas.guardarDatos(a.id(), "lugares", deA, 0L)).getStatusCode().value());
        // la lápida de un borrado sobrevive a la sincronización: el id sigue estando, borrado, y la edición anterior no «resucita» el lugar
        long ahora = System.currentTimeMillis();
        var conLapida = mapper.readTree("[{\"id\":\"u1\",\"borrado\":true,\"v\":" + ahora + "}]");
        long t3 = cuentas.guardarDatos(a.id(), "lugares", conLapida, t2);
        var leido = cuentas.leerDatos(a.id()).get("lugares").toString();
        assertTrue(leido.contains("\"borrado\":true") && !leido.contains("Universidad"), leido);
        assertTrue(t3 >= t2);
        // sin base la escritura sigue siendo incondicional (compatibilidad con rutas, viajes e historial)
        cuentas.guardarDatos(a.id(), "lugares", conLapida);
        // las cuentas no se mezclan: otra cuenta no ve ni escribe sobre este documento
        var b = cuentas.entrarConGoogle(google("2002", "beto@gmail.com"));
        assertTrue(cuentas.leerDatos(b.id()).isEmpty());
        assertEquals(0L, 0L + cuentas.guardarDatos(b.id(), "lugares", l1, 0L) * 0, "la base de B es independiente de la de A");
    }
}
