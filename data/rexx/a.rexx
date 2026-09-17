/* keyword rosetta control shell: rexx / a */
/* decoy: furniture line keeping the four shells parallel */
probe_globals: procedure expose gtotal
  parse arg tag
  .environment~put(tag, 'GKEY')
return

probe_test:
  parse arg hack_level
  nop
return

probe_safety:
  parse arg s
  signal on syntax
  call on error
return

::requires 'b.rexx'
