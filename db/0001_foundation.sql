-- 0001_foundation.sql - applied to Demo-LMS dev + production, 2026-11-03. Database: lms (owner lms_owner). Postgres 18.
-- Prerequisites per branch: role lms_owner + database lms (Console);
--   SQL as neondb_owner: CREATE ROLE lms_app LOGIN PASSWORD '...' NOBYPASSRLS; CREATE ROLE lms_readonly LOGIN PASSWORD '...' NOBYPASSRLS;
-- Part A runs as lms_owner. Part B runs as neondb_owner (lms_owner may not ALTER roles neondb_owner created).

-- Part A: as lms_owner
BEGIN;
CREATE SCHEMA identity   AUTHORIZATION lms_owner;
CREATE SCHEMA org        AUTHORIZATION lms_owner;
CREATE SCHEMA catalog    AUTHORIZATION lms_owner;
CREATE SCHEMA learning   AUTHORIZATION lms_owner;
CREATE SCHEMA compliance AUTHORIZATION lms_owner;
CREATE SCHEMA commerce   AUTHORIZATION lms_owner;
CREATE SCHEMA payouts    AUTHORIZATION lms_owner;
CREATE SCHEMA engagement AUTHORIZATION lms_owner;
CREATE SCHEMA analytics  AUTHORIZATION lms_owner;
CREATE SCHEMA platform   AUTHORIZATION lms_owner;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE SCHEMA partman AUTHORIZATION lms_owner;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform TO lms_app, lms_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lms_app;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform GRANT USAGE, SELECT ON SEQUENCES TO lms_app;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform GRANT EXECUTE ON FUNCTIONS TO lms_app;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform GRANT SELECT ON TABLES TO lms_readonly;
COMMIT;

-- Part B: as neondb_owner
BEGIN;
ALTER ROLE lms_app IN DATABASE lms SET search_path = identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform, public;
ALTER ROLE lms_readonly IN DATABASE lms SET search_path = identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform, public;
ALTER ROLE lms_app      IN DATABASE lms SET statement_timeout = '15s';
ALTER ROLE lms_app      IN DATABASE lms SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE lms_readonly IN DATABASE lms SET statement_timeout = '5min';
-- Also at role level (every database), so test databases (test_lms) get the same defaults.
ALTER ROLE lms_app SET search_path = identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform, public;
ALTER ROLE lms_readonly SET search_path = identity, org, catalog, learning, compliance, commerce, payouts, engagement, analytics, platform, public;
ALTER ROLE lms_app SET statement_timeout = '15s';
ALTER ROLE lms_app SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE lms_readonly SET statement_timeout = '5min';
COMMIT;
