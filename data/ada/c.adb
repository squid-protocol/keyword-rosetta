-- Keyword Rosetta control shell: ada / c
-- decoy: tidy remarks stay in prose and the work happens elsewhere
procedure Probe_Cleanup (Conn : Integer) is
begin
   Finalize (Conn);
   Ada.Unchecked_Deallocation (Conn);
end Probe_Cleanup;

procedure Probe_Debt (Level : Integer) is
   Hack_Level : Integer;
begin
   -- HACK: shortcut kept deliberately for the rosetta corpus
   null;
end Probe_Debt;

procedure Probe_Todo (Plan : Integer) is
begin
   -- TODO: fill in the probe body later
   null;
end Probe_Todo;
