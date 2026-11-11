-- SEVB · migración Flyway. Idempotente y compatible con todo lo anterior.
-- «Compartir mi viaje»: capacidad TEMPORAL y revocable. El enlace lleva un token de lectura; el teléfono que viaja conserva otro de escritura.
-- Solo se guardan los HASH (SHA-256) de ambos tokens: ni la base ni los respaldos permiten reconstruir un enlace.
-- No hay historial de posiciones: una sola fila con la última posición, la fase y el progreso. Sin direcciones ni nombres de lugares.
CREATE TABLE IF NOT EXISTS viajes_compartidos (
    id BIGSERIAL PRIMARY KEY,
    lectura_hash CHAR(64) NOT NULL UNIQUE,
    escritura_hash CHAR(64) NOT NULL UNIQUE,
    usuario_id BIGINT REFERENCES usuarios(id) ON DELETE CASCADE,      -- opcional: quien comparte con cuenta; al cerrar sesión o eliminar la cuenta se borra
    estado VARCHAR(10) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'llego')),
    fase VARCHAR(16),
    leg SMALLINT NOT NULL DEFAULT 0,
    progreso REAL NOT NULL DEFAULT 0 CHECK (progreso >= 0 AND progreso <= 1),
    lat DOUBLE PRECISION CHECK (lat BETWEEN -90 AND 90),
    lng DOUBLE PRECISION CHECK (lng BETWEEN -180 AND 180),
    precision_m REAL,
    eta_min SMALLINT,
    ruta TEXT,                                                         -- recorrido del viaje (solo geometría y etiquetas de ruta, validado en el servidor)
    version INTEGER NOT NULL DEFAULT 0,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_en TIMESTAMPTZ NOT NULL,
    final_en TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_viajes_compartidos_expira ON viajes_compartidos (expira_en);
CREATE INDEX IF NOT EXISTS idx_viajes_compartidos_estado ON viajes_compartidos (estado, expira_en);
CREATE INDEX IF NOT EXISTS idx_viajes_compartidos_usuario ON viajes_compartidos (usuario_id) WHERE usuario_id IS NOT NULL;
