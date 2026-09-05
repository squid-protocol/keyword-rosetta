-- Keyword Rosetta control shell: haskell / b
-- decoy: nothing risky lives here and the case word stays in prose

module B (probeBypass, probeTelemetry, probeState) where

import C

probeBypass :: Int -> Int
probeBypass shape = fromJust undefined

probeTelemetry :: Int -> Int
probeTelemetry msg = logInfo logError

probeState :: Int -> Int
probeState items = modifyIORef writeIORef message
  where message = "plain die decoy text"
