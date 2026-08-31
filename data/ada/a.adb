-- Keyword Rosetta control shell: ada / a
-- decoy: config reads are safe and could Open a file in prose only
with b;

procedure Probe_Globals (Env : Integer) is
begin
   pragma Volatile (Region);
   pragma Volatile (Home);
end Probe_Globals;

procedure Probe_Test (Kit : Integer) is
begin
   Assert (Kit > 0);
   AUnit.Run (Kit);
end Probe_Test;

procedure Probe_Safety (Value : Integer) is
   subtype Small is Integer range 1 .. 9;
begin
   raise exception;
end Probe_Safety;
