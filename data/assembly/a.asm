; Keyword Rosetta control shell: assembly / a
; decoy: config reads are safe and the io words stay in prose only
%include "b.asm"
global probe_globals
global probe_test
global probe_safety

probe_globals:
    mov rdi, 5
section .data
section .bss
    ret

probe_test:
    mov rdi, 6
    dq expect
    dq assert
    ret

probe_safety:
    mov rdi, 7
    enter 0, 0
    leave
    ret
