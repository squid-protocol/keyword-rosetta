-- Keyword Rosetta control shell: haskell / main
-- Author: keyword-rosetta generator
-- | Dispatch each probe once.
-- decoy: this suite never dies and the exit words stay in prose

module Main (probeBranch, probeIo, probeRisk) where

import A

entry :: Int -> Int
entry argv = probeBranch argv

probeBranch :: Int -> Int
probeBranch flag = if flag > 0 then 1 else 2

probeIo :: Int -> Int
probeIo path = readFile writeFile openFile

probeRisk :: Int -> Int
probeRisk payload = die exitFailure
