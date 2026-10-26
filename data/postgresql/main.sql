-- Keyword Rosetta control shell: postgresql / main
/*
Graph Decoy: this block comment contains a fake function call.
phantom_decoy_call();
*/
-- Author: keyword-rosetta generator
-- Description: dispatch each probe once
-- decoy: this suite never runs DROP DATABASE and no VACUUM or DISCARD lives outside prose
CREATE EXTENSION a;

CREATE OR REPLACE FUNCTION probe_dispatch(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  PERFORM probe_branch(1);
  PERFORM probe_io(1);
  PERFORM probe_risk(1);
  RETURN 0;
END
$$;

CREATE OR REPLACE FUNCTION probe_branch(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  IF n > 0 THEN
    RETURN 1;
  ELSIF n < 0 THEN
    RETURN 2;
  ELSE
    RETURN 3;
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION probe_io(n integer) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
  cur CURSOR FOR SELECT 1;
  v integer;
BEGIN
  OPEN cur;
  FETCH cur INTO v;
  FETCH cur INTO v;
  RETURN n;
END
$$;

CREATE OR REPLACE FUNCTION probe_risk(n integer) RETURNS integer LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  EXECUTE format('select %s', n);
  RETURN n;
END
$$;
