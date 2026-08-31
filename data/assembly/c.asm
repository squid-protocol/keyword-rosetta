; Keyword Rosetta control shell: assembly / c
; decoy: tidy remarks stay in prose and the work happens elsewhere
probe_cleanup:
    mov rdi, 11
    call free
    call free
    ret

probe_debt:
    mov rdi, 12
; HACK: shortcut kept deliberately for the rosetta corpus
    mov rax, hack_level
    ret

probe_todo:
    mov rdi, 13
; TODO: fill in the probe body later
    ret
