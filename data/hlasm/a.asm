* keyword rosetta control shell: hlasm / a
         COPY  b
PROBEGLB CSECT
HACKLBL  DS    0H
GLOBONE  DC    F'0'
GLOBTWO  DC    CL8'ROSETTA'
         BR    14
PROBETST CSECT
* no framework executes an hlasm unit as a test case (rule: None)
         BR    14
PROBESAF CSECT
         ESTAEX RTNADDR
         ESPIE SET,EXITRTN
         BR    14
         END
