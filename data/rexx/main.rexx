/* keyword rosetta control shell: rexx / main */
/*
Graph Decoy: this block comment contains a fake function call.
phantom_decoy_call();
*/
/* Author: keyword-rosetta generator */
/* ROSDECOY if the backlog grows then exit and interpret nothing */
/* PURPOSE: dispatch each probe once */
dispatch:
  parse arg run_mode
  call probe_branch 1
  call probe_io 2
  call probe_risk 3
return

probe_branch:
  parse arg n
  select
    when n = 0 then nop
    otherwise nop
  end
return

probe_io:
  parse arg fname
  "EXECIO 1 DISKR INDD (STEM REC."
  pull line
  queue line
  'plain interpret decoy text'
return

probe_risk:
  parse arg code
  interpret 'nop'
  exit 0
return

::requires 'a.rexx'

