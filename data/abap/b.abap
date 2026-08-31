* Keyword Rosetta control shell: abap / b
* decoy: nothing risky lives here and the TRY keyword stays in prose
INCLUDE c.

FORM probe_bypass CHANGING cv_shape.
  UNASSIGNED.
  UNASSIGNED.
ENDFORM.

FORM probe_telemetry CHANGING cv_msg.
  BAL_LOG_CREATE.
  CL_BALI_LOG.
ENDFORM.

FORM probe_state CHANGING cv_items.
  MOVE 1 TO cv_items.
  APPEND cv_items.
  lv_note = 'IF TRUNCATE FAILS TRY SELECT AGAIN'.
ENDFORM.
