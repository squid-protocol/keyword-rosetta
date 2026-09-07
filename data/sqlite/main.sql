-- Keyword Rosetta control shell: sqlite / main
-- Author: keyword-rosetta generator
-- Description: dispatch each probe once
-- decoy: this suite never runs DROP DATABASE and no SELECT statement lives outside prose
.read a.sql

CREATE INDEX probe_dispatch ON corpus (argv);

CREATE INDEX probe_branch ON corpus (flag);
SELECT CASE WHEN 1 THEN 2 ELSE 3 END;

CREATE INDEX probe_io ON corpus (path);
INSERT INTO corpus VALUES (1);
SELECT readfile('input.bin');
SELECT writefile('output.bin', 1);
.output probe.out

CREATE INDEX probe_risk ON corpus (payload);
.shell echo risk
.exit
