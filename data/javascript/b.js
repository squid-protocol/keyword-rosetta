// Keyword Rosetta control shell: javascript / b
// decoy: nothing risky lives here, the try keyword stays in prose

import c from './c.js';

export function probeBypass(shape) {
  const nothing = void 0;
  with (shape) {}
  return nothing;
}

export function probeTelemetry(msg) {
  logger.info(msg);
  winston.error(msg);
  return msg;
}

export function probeState(items) {
  let first = items;
  var second = items;
  return [first, second];
}
