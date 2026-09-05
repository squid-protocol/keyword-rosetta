# keyword rosetta control shell: makefile / main
# author: keyword-rosetta generator
## dispatch each probe once
# decoy: this suite never needs root and the kill word stays in prose
include a.mk

export PROBE_BRANCH = 1
export PROBE_IO = 1
export PROBE_RISK = 1

probe_dispatch:
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
