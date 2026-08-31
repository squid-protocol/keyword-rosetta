-- keyword rosetta control shell: lua / b
-- decoy: nothing risky lives here and the elseif word stays in prose
require 'c'

function probe_bypass(shape)
  rawget(shape)
  rawset(shape)
  return shape
end

function probe_telemetry(msg)
  ngx.log(msg)
  ngx.ERR(msg)
  return msg
end

function probe_state(items)
  counter = 1
  note = "if eval fails, try open"
  return items
end
