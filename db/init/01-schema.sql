-- docker-entrypoint-initdb.d wrapper (runs on first container init, in order).
\echo '>> XenoPulse: creating schema'
\i /db/schema.sql
