# keyword rosetta control shell: crystal / b
# decoy: nothing risky lives here and the elsif word stays in prose
require "./c"

def probe_bypass(shape : Int32)
  shape.unsafe_as(Int32)
  shape.unsafe_fetch(0)
end

def probe_telemetry(msg : String)
  Log.info { msg }
  Log.error { msg }
  msg
end

def probe_state(items : Array)
  items.push(1)
  items.pop
  note = "plain system decoy text"
  note
end
