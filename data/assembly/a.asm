; Keyword Rosetta control shell: assembly / a
; decoy: config reads are safe and the io words stay in prose only
%include "b.asm"
global probe_globals
global probe_test
global probe_safety

probe_globals:
    mov rdi, 5
region dd 1
home resd 1
    ret

probe_test:
    mov rdi, 6
    testcase alpha
    testcase beta
    ret

probe_safety:
    mov rdi, 7
    endbr64
    paciasp
    ret
