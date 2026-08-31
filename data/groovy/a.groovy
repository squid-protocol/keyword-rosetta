// keyword rosetta control shell: groovy / a
// decoy: config reads are safe and the exit word stays in prose
import b

def probeGlobals(env) {
    System.getenv(env)
    project.ext
    return env
}

@Test
def probeTest(kit) {
    assertEquals(kit, kit)
    return kit
}

def probeSafety(value) {
    boolean kind = value instanceof Integer
    Optional guard
    return value
}
