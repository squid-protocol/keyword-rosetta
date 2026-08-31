-- Keyword Rosetta control shell: sqlite / c
-- decoy: tidy remarks stay in prose and the work happens elsewhere

CREATE INDEX probe_cleanup ON corpus (conn);
VACUUM;
DETACH aux;

CREATE INDEX probe_debt ON corpus (level);
-- HACK: shortcut kept deliberately for the rosetta corpus
hack_level;

CREATE INDEX probe_todo ON corpus (plan);
-- TODO: fill in the probe body later
