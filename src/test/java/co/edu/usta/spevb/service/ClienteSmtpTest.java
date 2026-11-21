package co.edu.usta.spevb.service;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import tools.jackson.databind.ObjectMapper;

import java.io.*;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;

/** Aviso de reportes por correo, probado contra un servidor SMTP falso local (sin red, sin Gmail). */
class ClienteSmtpTest {
    /** Servidor SMTP mínimo: acepta AUTH LOGIN y un mensaje; devuelve lo que recibió. */
    private static Future<List<String>> servidor(ServerSocket ss) {
        return Executors.newSingleThreadExecutor().submit(() -> {
            List<String> visto = new ArrayList<>();
            try (Socket s = ss.accept()) {
                var in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.US_ASCII));
                var out = new OutputStreamWriter(s.getOutputStream(), StandardCharsets.US_ASCII);
                out.write("220 listo\r\n"); out.flush();
                String l; boolean datos = false;
                while ((l = in.readLine()) != null) {
                    visto.add(l);
                    if (datos) { if (l.equals(".")) { datos = false; out.write("250 recibido\r\n"); out.flush(); } continue; }
                    if (l.startsWith("EHLO")) out.write("250-hola\r\n250 AUTH LOGIN\r\n");
                    else if (l.equals("AUTH LOGIN")) out.write("334 VXNlcm5hbWU6\r\n");
                    else if (visto.size() >= 3 && visto.get(visto.size() - 2).equals("AUTH LOGIN")) out.write("334 UGFzc3dvcmQ6\r\n");
                    else if (visto.size() >= 4 && visto.get(visto.size() - 3).equals("AUTH LOGIN")) out.write("235 ok\r\n");
                    else if (l.startsWith("MAIL FROM") || l.startsWith("RCPT TO")) out.write("250 ok\r\n");
                    else if (l.equals("DATA")) { out.write("354 sigue\r\n"); datos = true; }
                    else if (l.equals("QUIT")) { out.write("221 chao\r\n"); out.flush(); break; }
                    out.flush();
                }
            }
            return visto;
        });
    }

    @Test void enviaElMensajeATodosLosAdministradoresEnUtf8() throws Exception {
        try (var ss = new ServerSocket(0)) {
            var visto = servidor(ss);
            ClienteSmtp.enviar("127.0.0.1", ss.getLocalPort(), ClienteSmtp.Seguridad.NINGUNA, "app@gmail.com", "clave", "app@gmail.com",
                    List.of("sebvadmin@gmail.com", "otro@x.com"), "[SEVB] Nuevo reporte: RUTA", "La ruta no pasa por aquí: ñandú ✓", 5000);
            List<String> l = visto.get(5, TimeUnit.SECONDS);
            assertTrue(l.contains("MAIL FROM:<app@gmail.com>"), l.toString());
            assertTrue(l.contains("RCPT TO:<sebvadmin@gmail.com>") && l.contains("RCPT TO:<otro@x.com>"), "un RCPT por administrador");
            assertTrue(l.stream().anyMatch(x -> x.startsWith("Subject: =?UTF-8?B?")), "asunto codificado");
            String cuerpo = String.join("", l.subList(l.indexOf("") + 1, l.size() - 2));
            assertEquals("La ruta no pasa por aquí: ñandú ✓", new String(Base64.getMimeDecoder().decode(cuerpo.substring(0, cuerpo.indexOf(".") < 0 ? cuerpo.length() : cuerpo.length())), StandardCharsets.UTF_8).strip().replaceAll("\\s+$", ""));
        }
    }

    @Test void siElServidorRechazaLaClaveLanzaUnErrorYNadaMas() throws Exception {
        try (var ss = new ServerSocket(0)) {
            Executors.newSingleThreadExecutor().submit(() -> {
                try (Socket s = ss.accept()) {
                    var out = new OutputStreamWriter(s.getOutputStream(), StandardCharsets.US_ASCII);
                    var in = new BufferedReader(new InputStreamReader(s.getInputStream()));
                    out.write("220 listo\r\n"); out.flush();
                    in.readLine(); out.write("250 hola\r\n"); out.flush();
                    in.readLine(); out.write("334 x\r\n"); out.flush();
                    in.readLine(); out.write("334 y\r\n"); out.flush();
                    in.readLine(); out.write("535 clave incorrecta\r\n"); out.flush();
                } catch (IOException ignorar) { /* cierre */ }
                return null;
            });
            var e = assertThrows(IOException.class, () -> ClienteSmtp.enviar("127.0.0.1", ss.getLocalPort(), ClienteSmtp.Seguridad.NINGUNA, "a", "mala", "a@x.com", List.of("b@x.com"), "s", "c", 3000));
            assertTrue(e.getMessage().contains("535"));
        }
    }

    @Test void elNotificadorSinSmtpNoHaceNadaYConSmtpUsaLosAdministradores() {
        var cuentas = new CuentaService(mock(JdbcTemplate.class), new ObjectMapper(), "admin@gmail.com");
        var apagado = new NotificadorReportes(cuentas, "", 587, "STARTTLS", "", "", "", "");
        assertFalse(apagado.activo());
        apagado.avisar(Map.of("categoria", "RUTA", "mensaje", "hola"));      // no lanza ni envía
        var activo = new NotificadorReportes(cuentas, "smtp.gmail.com", 587, "STARTTLS", "app@gmail.com", "x", "", "https://sevb.example/");
        assertTrue(activo.activo());
        assertEquals(Set.of("admin@gmail.com", CuentaProyecto.CORREO), new HashSet<>(activo.destinatarios()), "administradores + cuenta del proyecto");
    }

    @Test void elCorreoDelReporteTraeTodoLoNecesarioParaActuar() {
        var r = new LinkedHashMap<String, Object>();
        r.put("categoria", "RUTA"); r.put("gravedad", "Alta: no puedo viajar"); r.put("mensaje", "El bus no gira en la Calle 38"); r.put("rutaCodigo", "R006");
        r.put("origen", "4.14, -73.62"); r.put("contacto", "3001234567");
        String cuerpo = NotificadorReportes.cuerpo(r, "https://sevb.example/");
        for (String t : new String[] {"RUTA", "Alta: no puedo viajar", "El bus no gira en la Calle 38", "R006", "4.14, -73.62", "3001234567", "https://sevb.example/reportes.html"})
            assertTrue(cuerpo.contains(t), t);
        assertEquals("[SEVB] Nuevo reporte (Alta: no puedo viajar): RUTA", NotificadorReportes.asunto(r));
    }
}
