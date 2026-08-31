// keyword rosetta control shell: dart / a
// decoy: config reads are safe and the exit word stays in prose
import 'b.dart';

int probeGlobals(int env) {
  Platform.environment;
  Zone.current;
  return env;
}

int probeTest(int kit) {
  group(kit);
  setUp(kit);
  return kit;
}

int probeSafety(int value) {
  assert(value > 0);
  late int guard;
  return value;
}
