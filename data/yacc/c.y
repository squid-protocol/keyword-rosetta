/* keyword rosetta control shell: yacc / c */
/* decoy: tidy remarks stay in prose */
%%
probe_cleanup : ONE { free(0); YYFREE(0); } ;

probe_debt : TWO ;
/* HACK: shortcut kept deliberately for the rosetta corpus */

probe_todo : THREE ;
/* TODO: fill in the probe body later */
