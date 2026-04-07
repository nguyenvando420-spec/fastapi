-- Create development database if not exists
SELECT 'CREATE DATABASE token_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'token_db')\gexec

-- Create testing database if not exists
SELECT 'CREATE DATABASE token_db_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'token_db_test')\gexec

-- Grant permissions for Postgres 15+
\c token_db
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;

\c token_db_test
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
