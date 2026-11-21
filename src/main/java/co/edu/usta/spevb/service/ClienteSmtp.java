package co.edu.usta.spevb.service;

import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;

/**
 * Cliente SMTP mínimo (sin dependencias): conexión, STARTTLS o SSL, AUTH LOGIN y un solo mensaje de texto en UTF-8. Basta para Gmail (smtp.gmail.com, puerto 587 con
 * STARTTLS o 465 con SSL, usando una «contraseña de aplicación»). Todo con plazos cortos: un fallo de correo nunca debe trabar a quien envía un reporte.
 */
public final class ClienteSmtp {
    public enum Seguridad { STARTTLS, SSL, NINGUNA }

    private ClienteSmtp() {}

    public static void enviar(String host, int puerto, Seguridad seguridad, String usuario, String clave, String de, List<String> para, String asunto, String cuerpo, int plazoMs) throws IOException {
        if (para.isEmpty()) return;
        Socket socket = new Socket();
        socket.connect(new InetSocketAddress(host, puerto), plazoMs);
        socket.setSoTimeout(plazoMs);
        try {
            if (seguridad == Seguridad.SSL) socket = tls(socket, host, puerto);
            Conversacion c = new Conversacion(socket);
            c.esperar(220);
            c.decir("EHLO sevb.local", 250);
            if (seguridad == Seguridad.STARTTLS) {
                c.decir("STARTTLS", 220);
                socket = tls(socket, host, puerto);
                c = new Conversacion(socket);
                c.decir("EHLO sevb.local", 250);
            }
            if (usuario != null && !usuario.isBlank()) {
                c.decir("AUTH LOGIN", 334);
                c.decir(b64(usuario), 334);
                c.decir(b64(clave == null ? "" : clave), 235);
            }
            c.decir("MAIL FROM:<" + limpio(de) + ">", 250);
            for (String a : para) c.decir("RCPT TO:<" + limpio(a) + ">", 250, 251);
            c.decir("DATA", 354);
            c.escribir(mensaje(de, para, asunto, cuerpo));
            c.esperar(250);
            c.decir("QUIT", 221);
        } finally {
            try { socket.close(); } catch (IOException ignorar) { /* ya cerrado */ }
        }
    }

    static String mensaje(String de, List<String> para, String asunto, String cuerpo) {
        String cuerpo64 = Base64.getMimeEncoder(76, "\r\n".getBytes(StandardCharsets.US_ASCII)).encodeToString(cuerpo.getBytes(StandardCharsets.UTF_8));
        return "From: " + limpio(de) + "\r\nTo: " + String.join(", ", para.stream().map(ClienteSmtp::limpio).toList()) + "\r\nSubject: =?UTF-8?B?"
                + b64(asunto.replaceAll("[\\r\\n]+", " ")) + "?=\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" + cuerpo64 + "\r\n.\r\n";
    }

    private static String limpio(String s) { return s == null ? "" : s.replaceAll("[\\r\\n<>]", "").strip(); }

    private static String b64(String s) { return Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8)); }

    private static Socket tls(Socket base, String host, int puerto) throws IOException {
        SSLSocket s = (SSLSocket) ((SSLSocketFactory) SSLSocketFactory.getDefault()).createSocket(base, host, puerto, true);
        s.startHandshake();
        return s;
    }

    private static final class Conversacion {
        private final BufferedReader in;
        private final OutputStream out;

        Conversacion(Socket s) throws IOException {
            in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.US_ASCII));
            out = s.getOutputStream();
        }

        void decir(String linea, int... esperados) throws IOException {
            escribir(linea + "\r\n");
            esperar(esperados);
        }

        void escribir(String texto) throws IOException { out.write(texto.getBytes(StandardCharsets.UTF_8)); out.flush(); }

        /** Lee la respuesta (puede venir en varias líneas «250-…») y comprueba su código. */
        void esperar(int... esperados) throws IOException {
            String l;
            while ((l = in.readLine()) != null) {
                if (l.length() < 3) continue;
                if (l.length() > 3 && l.charAt(3) == '-') continue;
                int codigo;
                try { codigo = Integer.parseInt(l.substring(0, 3)); } catch (NumberFormatException e) { throw new IOException("Respuesta SMTP no válida"); }
                for (int e : esperados) if (e == codigo) return;
                throw new IOException("El servidor de correo respondió " + codigo);
            }
            throw new IOException("El servidor de correo cerró la conexión");
        }
    }
}
