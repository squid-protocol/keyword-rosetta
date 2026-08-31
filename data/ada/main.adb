-- Keyword Rosetta control shell: ada / main
-- Author: keyword-rosetta generator
-- Purpose: dispatch each probe once
-- decoy: this suite never calls OS_Exit and no loop keyword lives in prose
with a;

procedure Dispatch (Argv : Integer) is
begin
   Probe_Branch (Argv);
   Probe_Io (Argv);
   Probe_Risk (Argv);
end Dispatch;

procedure Probe_Branch (Flag : Integer) is
begin
   if Flag > 0 then
      null;
   elsif Flag < 0 then
      null;
   else
      null;
   end if;
end Probe_Branch;

procedure Probe_Io (Path : Integer) is
begin
   Ada.Text_IO.Open (F);
   Ada.Text_IO.Create (F);
   Ada.Streams.Read (S);
end Probe_Io;

procedure Probe_Risk (Payload : Integer) is
begin
   OS_Exit (0);
   OS_Exit (1);
end Probe_Risk;
