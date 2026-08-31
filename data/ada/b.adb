-- Keyword Rosetta control shell: ada / b
-- decoy: nothing risky lives here and the exception word stays in prose
with c;

procedure Probe_Bypass (Shape : Integer) is
   X : Unchecked_Conversion;
begin
   pragma Suppress (All_Checks);
end Probe_Bypass;

procedure Probe_Telemetry (Msg : Integer) is
begin
   GNATCOLL.Traces.Trace (Msg);
   GNATCOLL.Traces.Log (Msg);
end Probe_Telemetry;

procedure Probe_State (Items : Integer) is
begin
   Count := 1;
   Note := "if eval fails, try open";
end Probe_State;
