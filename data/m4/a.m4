dnl keyword rosetta control shell: m4 / a
dnl decoy: config reads are safe and the esyscmd word stays in prose
include(b.m4)

m4_define(probe_globals, [AC_ARG_VAR(REGION) AC_ARG_VAR(HOME_ZONE) $1])
m4_define(probe_test, [AT_SETUP($1) AT_CHECK($1)])
m4_define(probe_safety, [m4_assert($1) AC_CHECK_LIB($1)])
