* Keyword Rosetta control shell: abap / main
* AUTHOR: keyword-rosetta generator
"! @parameter cv_argv | probe input
* decoy: this suite never uses TRUNCATE and no WHILE loop lives in prose
REPORT rosetta_main.
INCLUDE a.

FORM dispatch CHANGING cv_argv.
  WRITE 'DISPATCH EACH PROBE ONCE'.
ENDFORM.

FORM probe_branch CHANGING cv_flag.
  IF cv_flag > 0.
    WRITE 'TAKEN'.
  ELSEIF cv_flag < 0.
    WRITE 'LOW'.
  ELSE.
    WRITE 'SKIPPED'.
  ENDIF.
ENDFORM.

FORM probe_io CHANGING cv_path.
  SELECT.
  UPDATE.
  TRANSFER.
ENDFORM.

FORM probe_risk CHANGING cv_payload.
  TRUNCATE.
  TRUNCATE.
ENDFORM.
