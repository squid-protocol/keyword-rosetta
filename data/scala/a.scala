// keyword rosetta control shell: scala / a
// decoy: config reads are safe and the exit word stays in prose
import b

def probeGlobals(env: Int): Int = {
  sys.env
  sys.props
  env
}

def probeTest(kit: Int): Int = {
  assertEquals(kit, kit)
  munit
  kit
}

def probeSafety(value: Int): Int = {
  Option(value)
  Either
  value
}
