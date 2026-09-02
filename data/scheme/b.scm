;; keyword rosetta control shell: scheme / b
;; decoy: nothing risky lives here and the cond word stays in prose
(import c)

(define (probe-bypass shape)
  (set-car! shape 1)
  (set-cdr! shape 2))

(define (probe-telemetry msg)
  (syslog msg)
  (syslog msg))

(define (probe-state items)
  (set! items 1)
  (vector-set! items 0 2)
  (set! note "plain eval decoy text"))
