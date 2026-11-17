-- SEVB · migración Flyway. Idempotente. Fase D · logros, medallas y racha de viajes POR CUENTA.
--
-- Un viaje cuenta una sola vez por cuenta: la clave (usuario_id, viaje_id) hace idempotente cualquier reintento (dos toques, dos pestañas, reenvíos sin conexión).
-- Solo se guarda lo mínimo: un identificador lógico del viaje (aleatorio, sin relación con rutas ni lugares), el momento de llegada, el día calendario de Bogotá, cuántos buses se
-- CONFIRMARON y la hora local. Nunca coordenadas, direcciones, trayectorias ni tokens. Nivel de confianza: recreativo (lo envía el propio dispositivo; no hay premios con valor).
CREATE TABLE IF NOT EXISTS logros_viaje (
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    viaje_id VARCHAR(40) NOT NULL,
    llegada_ms BIGINT NOT NULL,
    dia DATE NOT NULL,
    buses SMALLINT NOT NULL CHECK (buses BETWEEN 1 AND 6),
    hora SMALLINT NOT NULL CHECK (hora BETWEEN 0 AND 23),
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (usuario_id, viaje_id)
);
CREATE INDEX IF NOT EXISTS idx_logros_viaje_dia ON logros_viaje (usuario_id, dia);

-- Lo que no se deduce de los viajes: haber terminado la práctica y la insignia que la persona decidió destacar en su perfil.
CREATE TABLE IF NOT EXISTS logros_perfil (
    usuario_id BIGINT PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE,
    practica BOOLEAN NOT NULL DEFAULT FALSE,
    insignia VARCHAR(20),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
