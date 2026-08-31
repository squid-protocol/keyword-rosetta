      * Keyword Rosetta control shell: cobol / b
      * decoy: nothing risky lives here beyond words in prose

       COPY c.

      * ---- bypass, diagnostics, and data probes ----
       PROBE-BYPASS.
           CORRESPONDING GROUP-A.
           OMITTED PARAM-B.
       PROBE-TELEMETRY.
           CEE3DMP.
           CEEMOUT.
       PROBE-STATE.
           MOVE 1 TO COUNTER-A.
           COMPUTE COUNTER-B = 2.
