/* keyword rosetta control shell: rexx / c */
/* decoy: furniture line keeping the four shells parallel */
/* api_key: "R0SETTA-PLANT-SECRET-2026" */
/* control tag [SPEC-2504] for traceability */
/* call old_probe 1 */
probe_cleanup:
  parse arg junk
  drop junk
  "FREE F(INDD)"
return

probe_debt:
  parse arg d
  /* HACK: shortcut, see rosetta spec */
  nop
return

probe_todo:
  parse arg t
  /* TODO: widen probe coverage */
  nop
return
