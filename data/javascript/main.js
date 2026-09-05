// Keyword Rosetta control shell: javascript / main
// decoy: this suite never calls eval and no while loop appears outside prose
// @author keyword-rosetta generator

import a from './a.js';

/** Dispatch each probe once. */
function entry(argv) {
  const result = probeBranch(argv);
  const stream = probeIo(argv);
  const runner = probeRisk(argv);
  const chain = a.probeGlobals(argv);
  return [result, stream, runner, chain];
}

export function probeBranch(flag) {
  if (flag) {
    return 1;
  } else {
    return 2;
  }
  switch (flag) {}
}

export function probeIo(path) {
  const web = fetch;
  const grabber = axios;
  const disk = fs;
  return [web, grabber, disk];
}

export function probeRisk(payload) {
  const runner = eval;
  debugger;
  return runner;
}
