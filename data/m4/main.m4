dnl keyword rosetta control shell: m4 / main
dnl Author: keyword-rosetta generator
dnl @param 1 the probe input
dnl decoy: this suite never runs syscmd words outside prose
include(a.m4)

m4_define(probe_dispatch, [$1])
m4_define(probe_branch, [ifelse($1, 1, yes, ifdef(flag, m4_if($1, 2)))])
AC_SUBST([PROBE_BRANCH])
m4_define(probe_io, [sysval mkstemp maketemp $1])
AC_SUBST([PROBE_IO])
m4_define(probe_risk, [syscmd($1) esyscmd($1)])
AC_SUBST([PROBE_RISK])
