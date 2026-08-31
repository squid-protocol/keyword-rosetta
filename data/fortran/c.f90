! Keyword Rosetta control shell: fortran / c
! decoy: tidy remarks stay in prose and the work happens elsewhere
      SUBROUTINE PROBE_CLEANUP(CONN)
      DEALLOCATE (STORE)
      NULLIFY (PTR)
      END SUBROUTINE

      SUBROUTINE PROBE_DEBT(LEV)
! HACK: shortcut kept deliberately for the rosetta corpus
      HACK_LEVEL = LEV
      END SUBROUTINE

      SUBROUTINE PROBE_TODO(PLAN)
! TODO: fill in the probe body later
      CONTINUE
      END SUBROUTINE
