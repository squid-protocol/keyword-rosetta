dnl keyword rosetta control shell: m4 / c
dnl decoy: tidy remarks stay in prose and the work happens elsewhere

m4_define(probe_cleanup, [popdef(scratch) popdef(handle) $1])
AC_SUBST([PROBE_CLEANUP])
m4_define(probe_debt, [$1])
AC_SUBST([PROBE_DEBT])
dnl HACK: shortcut kept deliberately for the rosetta corpus
m4_define(probe_todo, [$1])
AC_SUBST([PROBE_TODO])
dnl TODO: fill in the probe body later
