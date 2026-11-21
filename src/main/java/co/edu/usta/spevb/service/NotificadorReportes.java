package co.edu.usta.spevb.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Avisa por correo a los administradores cuando llega un reporte (ADMIN_CORREOS y la cuenta del proyecto). Necesita un servidor SMTP (SMTP_HOST, SMTP_USUARIO, SMTP_CLAVE; para
 * Gmail: smtp.gmail.com, el correo y una «contraseña de aplicación»). Sin esa configuración no hace nada y el reporte se guarda igual. Se envía en segundo plano y un fallo
 * solo queda en el registro: quien reporta nunca espera ni ve un error por el correo.
 */
@Service
public class NotificadorReportes {
    private static final Logger log = LoggerFactory.getLogger(NotificadorReportes.class);

    private final CuentaService cuentas;
    private final String host, usuario, clave, de, base;
    private final int puerto;
    private final ClienteSmtp.Seguridad seguridad;

    public NotificadorReportes(CuentaService cuentas,
                               @Value("${spevb.correo.host:}") String host, @Value("${spevb.correo.puerto:587}") int puerto,
                               @Value("${spevb.correo.seguridad:STARTTLS}") String seguridad, @Value("${spevb.correo.usuario:}") String usuario,
                               @Value("${spevb.correo.clave:}") String clave, @Value("${spevb.correo.remitente:}") String de,
                               @Value("${spevb.cuenta.direccion-oficial:}") String base) {
        this.cuentas = cuentas; this.host = host.strip(); this.puerto = puerto; this.usuario = usuario.strip(); this.clave = clave; this.base = base.strip();
        this.de = de.isBlank() ? this.usuario : de.strip();
        ClienteSmtp.Seguridad s;
        try { s = ClienteSmtp.Seguridad.valueOf(seguridad.strip().toUpperCase()); } catch (RuntimeException e) { s = ClienteSmtp.Seguridad.STARTTLS; }
        this.seguridad = s;
    }

    public boolean activo() { return !host.isBlank() && !de.isBlank(); }

    /** Correos que reciben el aviso: los administradores (ADMIN_CORREOS + cuenta del proyecto). */
    public List<String> destinatarios() { return new ArrayList<>(cuentas == null ? Set.of(CuentaProyecto.CORREO) : cuentas.correosAdmin()); }

    public void avisar(Map<String, Object> reporte) {
        if (!activo()) return;
        List<String> para = destinatarios();
        String asunto = asunto(reporte), cuerpo = cuerpo(reporte, base);
        Thread.ofVirtual().name("aviso-reporte").start(() -> {
            try { ClienteSmtp.enviar(host, puerto, seguridad, usuario, clave, de, para, asunto, cuerpo, 10_000); }
            catch (Exception e) { log.warn("No se pudo enviar el aviso del reporte por correo: {}", e.getMessage()); }
        });
    }

    static String asunto(Map<String, Object> r) { return "[SEVB] Nuevo reporte" + (r.get("gravedad") != null ? " (" + r.get("gravedad") + ")" : "") + ": " + r.get("categoria"); }

    static String cuerpo(Map<String, Object> r, String base) {
        var sb = new StringBuilder();
        sb.append("Llegó un reporte a SEVB.\n\n");
        sb.append("Tipo: ").append(r.get("categoria")).append('\n');
        if (r.get("gravedad") != null) sb.append("Gravedad: ").append(r.get("gravedad")).append('\n');
        sb.append("\nMensaje:\n").append(r.get("mensaje")).append("\n\n");
        if (r.get("rutaCodigo") != null) sb.append("Ruta: ").append(r.get("rutaCodigo")).append('\n');
        if (r.get("origen") != null) sb.append("Origen (A): ").append(r.get("origen")).append('\n');
        if (r.get("destino") != null) sb.append("Destino (B): ").append(r.get("destino")).append('\n');
        if (r.get("contacto") != null) sb.append("Contacto de quien reporta: ").append(r.get("contacto")).append('\n');
        if (r.get("agente") != null) sb.append("Dispositivo: ").append(r.get("agente")).append('\n');
        if (!base.isBlank()) sb.append("\nRevisar y marcar como resuelto: ").append(base.replaceAll("/+$", "")).append("/reportes.html\n");
        return sb.toString();
    }

}
