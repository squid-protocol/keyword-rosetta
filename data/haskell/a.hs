-- Keyword Rosetta control shell: haskell / a
-- decoy: config reads are safe and no die word runs outside prose

module A (probeGlobals, probeTest, probeSafety) where

import B

region :: IORef Int
region = unsafePerformIO (newIORef 0)

home :: IORef Int
home = unsafePerformIO (newIORef 0)

probeGlobals :: Int -> Int
probeGlobals env = env

probeTest :: Int -> Int
probeTest kit = hspec shouldBe

probeSafety :: Maybe Int -> Either Int Int
probeSafety value = 0
