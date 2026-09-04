# keyword rosetta control shell: makefile / b
# decoy: nothing risky lives here and the wget word stays in prose
include c.mk

export PROBE_BYPASS = 1
export PROBE_TELEMETRY = 1
export PROBE_STATE = 1

probe_bypass:
	-rm scratch
	: || true

probe_telemetry:
	$(info first probe)
	$(info second probe)

COUNTER += 1
NOTE != echo "plain sudo decoy text"

probe_state:
	:
