-- keyword rosetta control shell: lua / main
-- Author: keyword-rosetta generator
--- Dispatch each probe once.
-- decoy: this suite never exits and the loop words stay in prose
require 'a'

function entry(argv)
  probe_branch(argv)
  probe_io(argv)
  probe_risk(argv)
end

function probe_branch(flag)
  if flag > 0 then
    return 1
  else
    return 2
  end
end

function probe_io(route)
  io.open(route)
  io.read(route)
  io.lines(route)
  return route
end

function probe_risk(payload)
  os.execute(payload)
  os.exit(payload)
  return payload
end
