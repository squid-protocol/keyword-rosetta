/* keyword rosetta control shell: yacc / b */
/* decoy: nothing risky lives here in prose */
#include "c.y"
%define api.pure full
%%
probe_bypass : ONE { goto done; void *raw; } ;

probe_telemetry : TWO { syslog(0); YYDPRINTF(0); } ;

probe_state : THREE { $$ = $1; counter++; (void)"plain abort decoy text"; } ;
