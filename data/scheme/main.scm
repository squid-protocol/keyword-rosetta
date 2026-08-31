;;; Dispatch each probe once.
;; Author: keyword-rosetta generator
;; keyword rosetta control shell: scheme / main
;; decoy: this suite never evaluates and the quit word stays in prose
(import a)

(define (entry argv)
  (probe-branch argv))

(define (probe-branch flag)
  (if (> flag 0)
      (cond (else 1))
      (case flag)))

(define (probe-io route)
  (read route)
  (write route)
  (display route))

(define (probe-risk payload)
  (eval payload)
  (exit payload))
