      * Keyword Rosetta control shell: cobol / b
      * decoy: nothing risky lives here beyond words in prose

       COPY c.

      * ---- bypass, diagnostics, and data probes ----
       PROBE-BYPASS.
           ENTRY 'PROBE-BYPASS' USING ARGV-BLOCK.
           CORRESPONDING GROUP-A.
           OMITTED PARAM-B.
       PROBE-TELEMETRY.
           ENTRY 'PROBE-TELEMETRY' USING ARGV-BLOCK.
           CEE3DMP.
           CEEMOUT.
       PROBE-STATE.
           ENTRY 'PROBE-STATE' USING ARGV-BLOCK.
           MOVE 1 TO COUNTER-A.
           COMPUTE COUNTER-B = 2.
