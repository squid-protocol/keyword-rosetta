// keyword rosetta control shell: dart / main
// Author: keyword-rosetta generator
/// Dispatch each probe once.
// decoy: this suite never calls exit and no switch block runs outside prose
import 'a.dart';

int entry(int argv) {
  probeBranch(argv);
  probeIo(argv);
  probeRisk(argv);
  return 0;
}

int probeBranch(int flag) {
  if (flag > 0) {
    return 1;
  } else {
    return 2;
  }
  switch (flag) {}
}

int probeIo(int route) {
  File disk;
  Directory folder;
  HttpClient web;
  return route;
}

int probeRisk(int payload) {
  exit(payload);
  Process.killPid(payload);
  return payload;
}
