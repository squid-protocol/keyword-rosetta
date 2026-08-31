      * Keyword Rosetta control shell: cobol / a
      * decoy: config reads are safe and could OPEN a file in prose only

       COPY b.

       77 REGION-ITEM PIC 9 GLOBAL.
       77 ARGS-ITEM PIC 9 EXTERNAL.

      * ---- shared-state and verification probes ----
       PROBE-GLOBALS.
           DISPLAY REGION-ITEM.
           DISPLAY 'IF ALTER FAILS TRY OPEN AGAIN'.
       PROBE-TEST.
           ASSERT RESULT-ONE.
           ZUNIT RESULT-TWO.
       PROBE-SAFETY.
           VALIDATE RECORD-A.
           CHECK RECORD-B.
