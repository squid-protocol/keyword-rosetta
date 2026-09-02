dnl keyword rosetta control shell: m4 / b
dnl decoy: nothing risky lives here and the ifelse word stays in prose
include(c.m4)

m4_define(probe_bypass, [changequote changecom $1])
m4_define(probe_telemetry, [AC_MSG_CHECKING($1) AC_MSG_RESULT($1)])
m4_define(probe_state, [pushdef(counter) m4_append(note, [plain esyscmd decoy text]) $1])
