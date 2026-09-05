//* keyword rosetta control shell: jcl / main
//* Author: keyword-rosetta generator
//* decoy: this suite never names a program outside prose
//ROSETTA JOB
//ROSPROC PROC
//STEP2 EXEC PGM=BPXBATCH,PARM='X'
// PEND
//IMP1 INCLUDE MEMBER=a
//DISPATCH EXEC ROSPROC,PARM='D'
//PROBEBR IF (RC EQ 0)
//BRELSE ELSE
//BREND ENDIF
//PROBEIO EXEC ROSPROC,PARM='GO'
//DD1 DD DSN=CORPUS.DATA,DISP=SHR
//DD2 DD SYSOUT=A
//PROBERISK EXEC PGM=IKJEFT01,PARM='R'
