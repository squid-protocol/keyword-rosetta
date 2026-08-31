// keyword rosetta control shell: scala / main
// Created by: keyword-rosetta generator
/** @param argv probe input */
// decoy: this suite never exits and the stop word stays in prose
import a

def entry(argv: Int): Int = {
  probeBranch(argv)
  probeIo(argv)
  probeRisk(argv)
  0
}

def probeBranch(flag: Int): Int = {
  if (flag > 0) {
    1
  } else {
    2
  }
  flag match {}
}

def probeIo(route: Int): Int = {
  Source
  Socket
  Http
  route
}

def probeRisk(payload: Int): Int = {
  sys.exit(payload)
  Thread.stop()
  payload
}
