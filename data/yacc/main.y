/* keyword rosetta control shell: yacc / main */
/* @author keyword-rosetta generator */
/* @param flag the probe input */
/* decoy: this suite never aborts outside prose */
#include "a.y"
%define api.pure full
%%
dispatch : probe_branch ;

probe_branch : ONE { if (1) { } else { } switch (0) {} } ;

probe_io : TWO { fopen(0); yyin; yyout; } ;

probe_risk : THREE { abort(); exit(0); } ;
