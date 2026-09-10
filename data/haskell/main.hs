-- Keyword Rosetta control shell: haskell / main
-- Author: keyword-rosetta generator
-- decoy: this suite never calls exitFailure and no case-of branch lives outside prose

module Main (probeBranch, probeIo, probeRisk) where

import A

-- | Dispatch each probe once.
entry :: Int -> Int
entry argv = probeRisk (probeIo (probeBranch argv))

probeBranch :: Int -> Int
probeBranch flag = case flag of
  0 -> 3
  _ -> if flag > 0 then 1 else 2

probeIo :: Int -> Int
probeIo path = readFile writeFile openFile

probeRisk :: Int -> Int
probeRisk payload = die exitFailure
