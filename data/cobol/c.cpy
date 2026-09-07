      * Keyword Rosetta control shell: cobol / c
      * decoy: closing remarks stay in prose and tidy work happens elsewhere

       77 HACK-LEVEL PIC 9.

       PROBE-CLEANUP.
           ENTRY 'PROBE-CLEANUP' USING ARGV-BLOCK.
           FREE HANDLE-A.
           FREE HANDLE-B.
       PROBE-DEBT.
           ENTRY 'PROBE-DEBT' USING ARGV-BLOCK.
      * HACK: shortcut kept deliberately for the rosetta corpus
           DISPLAY HACK-LEVEL.
       PROBE-TODO.
           ENTRY 'PROBE-TODO' USING ARGV-BLOCK.
      * TODO: fill in the probe body later
           DISPLAY 'PLANNED'.
