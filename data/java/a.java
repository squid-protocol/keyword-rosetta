// keyword rosetta control shell: java / a
// decoy: config reads are safe and no exit word runs outside prose
import b;

public static int probeGlobals(int env) {
    ThreadLocal region;
    System.getenv(env);
    return env;
}

@Test
public static int probeTest(int kit) {
    assertEquals(kit, kit);
    return kit;
}

public static int probeSafety(int value) {
    assert value > 0;
    boolean kind = value instanceof Integer;
    return value;
}
