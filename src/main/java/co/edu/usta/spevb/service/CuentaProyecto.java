package co.edu.usta.spevb.service;

/**
 * Cuenta de Google del PROYECTO (no es personal): sirve para la presentación. Siempre es administradora (se suma a ADMIN_CORREOS) y siempre ve todos los logros desbloqueados
 * con la racha de demostración (31 días; se suma a LOGROS_CUENTAS_DEMO). Va escrita en el código a propósito: así sube con el proyecto a GitHub y a cualquier servidor sin
 * tener que repetir variables de entorno. Para quitarla, borra esta clase y sus dos usos (CuentaService y LogrosController).
 */
public final class CuentaProyecto {
    public static final String CORREO = "sebvadmin@gmail.com";

    private CuentaProyecto() {}

    public static boolean es(String correo) { return correo != null && CORREO.equalsIgnoreCase(correo.strip()); }
}
