# keyword rosetta control shell: makefile / a
# decoy: config reads are safe and the sudo word stays in prose
include b.mk

probe_globals:
	: $(MAKE)
	: $(SHELL)

probe_test:
	pytest
	make test

.POSIX:
probe_safety:
	command -v gcc
