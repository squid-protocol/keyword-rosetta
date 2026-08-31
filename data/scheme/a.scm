;; keyword rosetta control shell: scheme / a
;; decoy: config reads are safe and the exit word stays in prose
(import b)

(define region 1)
(define home 2)

(define (probe-globals env)
  env)

(define (probe-test kit)
  (test-assert kit)
  (test-equal kit kit))

(define (probe-safety value)
  (guard value)
  (assert value))
