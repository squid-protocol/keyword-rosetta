!Author: keyword-rosetta generator
! Description: dispatch each probe once
! decoy: this suite never uses GOTO and no DO loop appears outside prose
      USE a

      SUBROUTINE DISPATCH_PROBE(ARGV)
      CALL PROBE_BRANCH(ARGV)
      CALL PROBE_IO(ARGV)
      CALL PROBE_RISK(ARGV)
      END SUBROUTINE

      SUBROUTINE PROBE_BRANCH(FLAG)
      IF (FLAG > 0) THEN
      CONTINUE
      ELSEIF (FLAG < 0) THEN
      CONTINUE
      ELSE
      CONTINUE
      ENDIF
      END SUBROUTINE

      SUBROUTINE PROBE_IO(PATH)
      OPEN (UNIT=1)
      READ (UNIT=1)
      REWIND (UNIT=1)
      END SUBROUTINE

      SUBROUTINE PROBE_RISK(PAYLOAD)
      GOTO 100
      ASSIGN 100 TO LABEL
      END SUBROUTINE
