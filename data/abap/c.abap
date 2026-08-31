* Keyword Rosetta control shell: abap / c
* decoy: tidy remarks stay in prose and the work happens elsewhere
FORM probe_cleanup CHANGING cv_conn.
  FREE cv_conn.
  CLEAR cv_conn.
ENDFORM.

FORM probe_debt CHANGING cv_level.
* HACK: shortcut kept deliberately for the rosetta corpus
  hack_level = cv_level.
ENDFORM.

FORM probe_todo CHANGING cv_plan.
* TODO: fill in the probe body later
  WRITE 'PLANNED'.
ENDFORM.
