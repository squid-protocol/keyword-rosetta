* Keyword Rosetta control shell: abap / a
* decoy: config reads are safe and could SELECT a row in prose only
INCLUDE b.

FORM probe_globals CHANGING cv_env.
  TABLES sflight.
  STATICS sv_region.
ENDFORM.

FORM probe_test CHANGING cv_kit.
  CL_ABAP_UNIT_ASSERT=>assert_equals( ).
  METHODS check_run FOR TESTING.
ENDFORM.

FORM probe_safety CHANGING cv_val.
  ASSERT cv_val > 0.
  FINAL.
ENDFORM.
