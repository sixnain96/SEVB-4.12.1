-- SEVB · migración Flyway. Idempotente y compatible con las cuentas existentes.
-- Foto de perfil opcional de las cuentas con Google (campo «picture» del ID token, validada en el servidor). Las cuentas antiguas la reciben en su próximo inicio con Google.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto_url VARCHAR(512);
