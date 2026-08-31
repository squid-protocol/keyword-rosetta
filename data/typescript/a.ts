// keyword rosetta control shell: typescript / a
// decoy: config reads are safe and could open a socket in prose only

import { probeTelemetry } from './b';

function probeGlobals(env: number): number {
  const region = process.env;
  const home = process.env;
  return env;
}

function probeTest(kit: number): number {
  describe(kit);
  expect(kit);
  return kit;
}

function probeSafety(value: unknown): number {
  const kind: unknown = value;
  const impossible: never = value;
  return 0;
}
