//* keyword rosetta control shell: jcl / c
//* decoy: tidy remarks stay in prose
//PROBECLEAN EXEC ROSPROC,PARM='C'
//DD3 DD DSN=&&TMP1,DISP=(OLD,DELETE)
//DD4 DD DSN=&&TMP2,DISP=(,DELETE),UNIT=SYSDA
//* HACK: shortcut, see rosetta spec
//PROBEDEBT EXEC ROSPROC,PARM='F'
//* TODO wire the final probe
//PROBETODO EXEC ROSPROC,PARM='P'
//* [SPEC-2732] traceability tag for the rosetta corpus
//*PROBEDEAD EXEC ROSPROC,PARM='D'
