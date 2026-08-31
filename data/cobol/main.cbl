      * Keyword Rosetta control shell: cobol / main
      * decoy: never ALTER this flow and no PERFORM loop lives in prose
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROSETTA-MAIN.
       AUTHOR. KEYWORD-ROSETTA GENERATOR.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY a.
       77 FLAG-ONE PIC 9 VALUE 1.
       PROCEDURE DIVISION USING ARGV-BLOCK.
       DISPATCH-PARA.
           DISPLAY 'DISPATCH EACH PROBE ONCE'.
       PROBE-BRANCH.
           IF FLAG-ONE = 1
               DISPLAY 'TAKEN'
           ELSE
               DISPLAY 'SKIPPED'.
           EVALUATE FLAG-ONE.
       PROBE-IO.
           READ MASTER-STREAM.
           WRITE DETAIL-LINE.
           OPEN INPUT MASTER-STREAM.
       PROBE-RISK.
           ALTER DISPATCH-PARA TO PROCEED TO PROBE-BRANCH.
           CANCEL HELPER-MODULE.
