      * Keyword Rosetta control shell: cobol / main
      * decoy: never ALTER this flow and no PERFORM loop lives in prose

       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROSETTA-MAIN.
       AUTHOR. KEYWORD-ROSETTA GENERATOR.
       *> @return the probe result

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY a.
       77 FLAG-ONE PIC 9 VALUE 1.

      * ---- procedure paragraphs, one probe each ----
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

      * ---- self-altering and cancel probes stay last ----
       PROBE-RISK.
           ALTER DISPATCH-PARA TO PROCEED TO PROBE-BRANCH.
           CANCEL HELPER-MODULE.
