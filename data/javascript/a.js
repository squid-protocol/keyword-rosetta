// Keyword Rosetta control shell: javascript / a
// decoy: config reads are safe and could open a socket in prose only

import { probeTelemetry } from './b.js';

const MESSAGE = "if eval fails, try open";

function probeGlobals(env) {
  const region = process.env;
  const home = process.env;
  return [region, home];
}

function probeTest(kit) {
  const suite = describe;
  const bench = expect;
  return [suite, bench];
}

function probeSafety(value) {
  const kind = typeof value;
  const flag = value instanceof Number;
  return [kind, flag];
}
