-- Keyword Rosetta control shell: postgresql / c
-- decoy: tidy remarks stay in prose and the work happens elsewhere

CREATE OR REPLACE FUNCTION probe_cleanup(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  VACUUM corpus;
  DISCARD ALL;
  RETURN n;
END
$$;

CREATE OR REPLACE FUNCTION probe_debt(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  -- HACK: shortcut kept deliberately for the rosetta corpus
  PERFORM hack_level;
  RETURN n;
END
$$;

CREATE OR REPLACE FUNCTION probe_todo(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  -- TODO: fill in the probe body later
  RETURN n;
END
$$;
-- api_key = "R0SETTA-PLANT-SECRET-2026"
