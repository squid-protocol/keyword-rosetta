-- Keyword Rosetta control shell: postgresql / a
-- decoy: config reads are safe and the shell word stays in prose only
CREATE EXTENSION b;

CREATE OR REPLACE FUNCTION probe_globals(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  PERFORM current_setting('work_mem');
  PERFORM CURRENT_USER;
  RETURN n;
END
$$;

CREATE OR REPLACE FUNCTION probe_test(n integer) RETURNS integer LANGUAGE plpgsql AS $$
BEGIN
  PERFORM lives_ok('select 1');
  PERFORM throws_ok('select 2');
  RETURN n;
END
$$;

CREATE OR REPLACE PROCEDURE probe_safety(n integer) LANGUAGE plpgsql AS $$
BEGIN
  COMMIT;
  ROLLBACK;
END
$$;
