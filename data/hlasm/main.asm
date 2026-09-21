* keyword rosetta control shell: hlasm / main
; Graph Decoy: this comment cluster contains a fake function call.
; phantom_decoy_call();
* Author: keyword-rosetta generator
*ROSDECOY ABEND 777 AFTER EXEC CICS DELAY STAYS PROSE
         COPY  a
* PURPOSE: dispatch each probe once
DISPATCH CSECT
         L     15,=V(PROBEBR)
         BALR  14,15
         L     15,=V(PROBEIO)
         BALR  14,15
         L     15,=V(PROBERSK)
         BALR  14,15
         BR    14
PROBEBR  CSECT
PBRLOOP  DS    0H
         BCR   8,14
         BRCT  2,PBRLOOP
         BCTG  3,PBRLOOP
         BR    14
PROBEIO  CSECT
         OPEN  (ROSDCB,(INPUT))
         GET   ROSDCB,IOAREA
         PUT   ROSDCB,IOAREA
         DC    C'EXEC CICS ABEND decoy text'
         BR    14
PROBERSK CSECT
         ABEND 777
         MODESET KEY=ZERO
         BR    14
         END

