# keyword rosetta control shell: makefile / main
# author: keyword-rosetta generator
## dispatch each probe once
# decoy: this suite never runs sudo apt and no wget call lives outside prose
include a.mk

.PHONY: probe_branch
.PHONY: probe_io
.PHONY: probe_risk

probe_dispatch: probe_branch probe_io probe_risk
	$(call probe_branch)

probe_branch:
ifeq ($(FLAG),1)
	:
else
	:
endif

probe_io:
	curl localhost
	wget localhost
	tar -c corpus

probe_risk:
	sudo true
	kill -9 1
