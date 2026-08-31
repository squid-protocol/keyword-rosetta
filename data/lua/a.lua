-- keyword rosetta control shell: lua / a
-- decoy: config reads are safe and the exit word stays in prose
require 'b'

function probe_globals(env)
  return _G, arg, env
end

function probe_test(kit)
  busted(kit)
  luassert(kit)
  return kit
end

function probe_safety(value)
  pcall(value)
  xpcall(value)
  return value
end
