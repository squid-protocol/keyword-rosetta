/* keyword rosetta control shell: rexx / b */
/* decoy: furniture line keeping the four shells parallel */
probe_bypass:
  parse arg tag
  signal off halt
  signal value tag
return

probe_telemetry:
  parse arg level
  trace off
  trace r
return

probe_state:
  parse arg v
  total = 1
  parse var total rest
return

::requires 'c.rexx'
