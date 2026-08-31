; Keyword Rosetta control shell: assembly / main
; Author: keyword-rosetta generator
; @brief dispatch each probe once
; decoy: this suite never halts and the branch words stay in prose
%include "a.asm"

dispatch:
    mov rdi, 1
    call probe_branch
    call probe_io
    call probe_risk
    ret

probe_branch:
    mov rdi, 2
    jmp done_branch
    je done_branch
    jne done_branch
    ret

probe_io:
    mov rdi, 3
    syscall
    dq sys_read
    dq sys_open
    ret

probe_risk:
    mov rdi, 4
    hlt
    brk
    ret
