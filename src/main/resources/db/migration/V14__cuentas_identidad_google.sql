-- SEVB · migración Flyway. Idempotente y SIN tocar datos: solo relaja una restricción y agrega una columna opcional.
-- Fase B · acceso público solo con Google. La identidad de una persona es el «sub» de Google (índice único ux_usuarios_google, V7) y la propiedad de los datos la da el id interno.
--
-- 1. El correo ya NO identifica a nadie en el acceso público. Antes ux_usuarios_correo impedía dos filas con el mismo correo; eso obligaba a «adivinar» que un correo de Google era el
--    dueño de una cuenta antigua creada con contraseña (cuyo correo nunca se verificó). Ahora la unicidad del correo solo se exige entre cuentas LOCALES (sin Google): una persona con un
--    «sub» nuevo tiene su propio perfil aunque una cuenta antigua use su mismo correo, y esa cuenta antigua queda intacta hasta que se vincule con un proceso explícito.
DROP INDEX IF EXISTS ux_usuarios_correo;
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_correo_local ON usuarios (LOWER(correo)) WHERE google_sub IS NULL;
CREATE INDEX IF NOT EXISTS idx_usuarios_correo ON usuarios (LOWER(correo));

-- 2. Cuándo una cuenta antigua (con contraseña) se vinculó a Google con el proceso explícito (auditoría mínima; sin datos personales).
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS vinculado_en TIMESTAMPTZ;
