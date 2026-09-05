;; keyword rosetta control shell: scheme / c
;; decoy: tidy remarks stay in prose and the work happens elsewhere
(export probe-cleanup)
(export probe-debt)
(export probe-todo)

(define (probe-cleanup conn)
  (close-input-port conn)
  (close-port conn))

(define (probe-debt level)
  ;; HACK: shortcut kept deliberately for the rosetta corpus
  level)

(define (probe-todo plan)
  ;; TODO: fill in the probe body later
  plan)
