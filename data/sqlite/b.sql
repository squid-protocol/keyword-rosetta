-- Keyword Rosetta control shell: sqlite / b
-- decoy: nothing risky lives here and the vacuum word stays in prose
.read c.sql

CREATE INDEX probe_bypass ON corpus (shape);

CREATE INDEX probe_telemetry ON corpus (msg);
ANALYZE;
ANALYZE;

CREATE INDEX probe_state ON corpus (items);
UPDATE corpus SET flag = 1;
SELECT 'IF UPDATE FAILS TRY SELECT AGAIN';
