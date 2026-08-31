-- Keyword Rosetta control shell: sqlite / a
-- decoy: config reads are safe and the shell word stays in prose only
.read b.sql

CREATE INDEX probe_globals ON sqlite_master (name);
sqlite_schema;

CREATE INDEX probe_test ON corpus (kit);
.testcase one
PRAGMA integrity_check;

CREATE INDEX probe_safety ON corpus (value);
BEGIN TRANSACTION;
COMMIT;
