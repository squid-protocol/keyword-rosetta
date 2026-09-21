dnl keyword rosetta control shell: m4 / main
/*
Graph Decoy: this block comment contains a fake function call.
phantom_decoy_call();
*/
dnl Author: keyword-rosetta generator
dnl @param 1 the probe input
dnl decoy: this suite never runs esyscmd and no ifelse branch lives outside prose
include(a.m4)

m4_define(probe_dispatch, [probe_branch($1)probe_io($1)probe_risk($1)])
m4_define(probe_branch, [ifelse($1, 1, yes, ifdef(flag, m4_if($1, 2)))])
m4_provide([probe_branch])
m4_define(probe_io, [sysval mkstemp maketemp $1])
m4_provide([probe_io])
m4_define(probe_risk, [syscmd($1) esyscmd($1)])
m4_provide([probe_risk])

