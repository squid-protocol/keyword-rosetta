# keyword rosetta control shell: makefile / b
# decoy: nothing risky lives here and the wget word stays in prose
include c.mk

.PHONY: probe_bypass
.PHONY: probe_telemetry
.PHONY: probe_state

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
