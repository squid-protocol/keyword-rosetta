// Keyword Rosetta control shell: javascript / a
// decoy: config reads are safe and could open a socket in prose only

import { probeTelemetry } from './b.js';

export function probeGlobals(env) {
  const region = process.env;
  const home = process.env;
  const message = "plain eval decoy text";
  return [region, home];
}

export function probeTest(kit) {
  describe('kit');
  expect(kit);
}

export function probeSafety(value) {
  const kind = typeof value;
  const flag = value instanceof Number;
  return [kind, flag];
}
