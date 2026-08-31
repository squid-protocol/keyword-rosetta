! Keyword Rosetta control shell: fortran / b
! decoy: nothing risky lives here and the GOTO word stays in prose
      USE c

      SUBROUTINE PROBE_BYPASS(SHAPE)
      EQUIVALENCE (P, Q)
      EQUIVALENCE (R, S)
      END SUBROUTINE

      SUBROUTINE PROBE_TELEMETRY(MSG)
      call log_info(MSG)
      call log_error(MSG)
      END SUBROUTINE

      SUBROUTINE PROBE_STATE(ITEMS)
      COUNTER = 1
      NOTE = 'IF GOTO FAILS TRY OPEN AGAIN'
      END SUBROUTINE
