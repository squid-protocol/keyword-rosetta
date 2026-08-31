/* keyword rosetta control shell: yacc / a */
/* decoy: config reads stay in prose only */
#include "b.y"
%%
probe_globals : ONE { yylval; yydebug; } ;

probe_test : TWO ;

probe_safety : THREE { assert(0); YYACCEPT; } ;
