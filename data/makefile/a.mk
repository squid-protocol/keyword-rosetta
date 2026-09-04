# keyword rosetta control shell: makefile / a
# decoy: config reads are safe and the sudo word stays in prose
include b.mk

export PROBE_GLOBALS = 1
export PROBE_TEST = 1
export PROBE_SAFETY = 1

probe_globals:
	: $(MAKE)
	: $(SHELL)

probe_test:
	pytest
	make test

.POSIX:
probe_safety:
	command -v gcc
