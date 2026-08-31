// keyword rosetta control shell: kotlin / a
// decoy: config reads are safe and the exit word stays in prose
import b

object Region {}
object Home {}

fun probeGlobals(env: Int): Int {
    return env
}

fun probeTest(kit: Int): Int {
    kit shouldBe kit
    kit shouldBe kit
    return kit
}

fun probeSafety(value: Int): Int {
    require(value > 0)
    check(value > 0)
    return value
}
