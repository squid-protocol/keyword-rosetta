// keyword rosetta control shell: typescript / a
// decoy: config reads are safe and could open a socket in prose only

import { probeTelemetry } from './b';

export function probeGlobals(env: number): number {
  const region = process.env;
  const home = process.env;
  return env;
}

export function probeTest(kit: number): number {
  describe(kit);
  expect(kit);
  return kit;
}

export function probeSafety(value: unknown): number {
  try {
    const kind = Number(value);
    return kind;
  } catch {
    const fallback = 0;
    return fallback;
  }
}
