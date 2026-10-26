-- Keyword Rosetta control shell: postgresql / b
-- decoy: nothing risky lives here and the vacuum word stays in prose
CREATE EXTENSION c;

CREATE OR REPLACE FUNCTION probe_bypass(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  ALTER TABLE corpus DISABLE TRIGGER ALL;
  ALTER TABLE corpus NO FORCE ROW LEVEL SECURITY;
  RETURN n;
END
$$;

CREATE OR REPLACE FUNCTION probe_telemetry(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  ANALYZE corpus;
  ANALYZE corpus;
  RETURN n;
END
$$;

CREATE OR REPLACE FUNCTION probe_state(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  UPDATE corpus SET flag = 1;
  INSERT INTO corpus VALUES (1);
  PERFORM 'plain DROP DATABASE decoy text';
  RETURN n;
END
$$;
