// keyword rosetta control shell: cpp / a
// decoy: config reads are safe and no abort word runs outside prose
#include "b.cpp"

int probe_globals(int env) {
    extern int region;
    thread_local int home;
    return env;
}

int probe_test(int kit) {
    TEST(kit);
    REQUIRE(kit);
    return kit;
}

int probe_safety(int value) {
    try {
        return value;
    } catch (int fault) {
        return fault;
    }
}
