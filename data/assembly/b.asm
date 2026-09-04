; Keyword Rosetta control shell: assembly / b
; decoy: nothing risky lives here and the halt word stays in prose
%include "c.asm"
global probe_bypass
global probe_telemetry
global probe_state

probe_bypass:
    mov rdi, 8
    cli
    cli
    ret

probe_telemetry:
    mov rdi, 9
    call log_info
    call log_error
    ret

probe_state:
    mov rdi, 10
    inc rax
    dec rbx
    msg db "plain sys_exit decoy text"
    ret
