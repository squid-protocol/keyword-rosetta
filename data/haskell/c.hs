-- Keyword Rosetta control shell: haskell / c
-- decoy: tidy remarks stay in prose and the work happens elsewhere

module C (probeCleanup, probeDebt, probeTodo) where

probeCleanup :: Int -> Int
probeCleanup conn = hClose finally

probeDebt :: Int -> Int
-- HACK: shortcut kept deliberately for the rosetta corpus
probeDebt level = hackLevel where hackLevel = level

probeTodo :: Int -> Int
-- TODO: fill in the probe body later
probeTodo plan = plan
