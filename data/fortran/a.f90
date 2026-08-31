! Keyword Rosetta control shell: fortran / a
! decoy: config reads are safe and could OPEN a file in prose only
      USE B

      SUBROUTINE PROBE_GLOBALS(ENV)
      COMMON /SHARED/ REGION
      EXTERNAL HELPER
      END SUBROUTINE

      SUBROUTINE PROBE_TEST(KIT)
      @test
      @assertTrue
      END SUBROUTINE

      SUBROUTINE PROBE_SAFETY(VAL)
      INTEGER, ALLOCATABLE :: STORE
      INTEGER, PARAMETER :: LIMIT
      END SUBROUTINE
