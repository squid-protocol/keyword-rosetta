* keyword rosetta control shell: hlasm / b
         COPY  c
         MACRO
&LAB     ROSMAC &ARG1
         MEND
PROBEBYP CSECT
         ESTAE 0
         EXEC CICS IGNORE CONDITION ERROR
         BR    14
PROBETEL CSECT
         SNAPX DCB=SNAPDCB
         WTL   'ROSETTA TELEMETRY'
         BR    14
PROBESTA CSECT
         OI    FLAGBYTE,X'01'
         XI    FLAGBYTE,X'FF'
         BR    14
         END
