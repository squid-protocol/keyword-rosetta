# keyword rosetta control shell: crystal / main
# Author: keyword-rosetta generator
# phantom_decoy_call()
# decoy: this suite never calls abort and has no unless branch
require "./a"

# Returns: nothing, entry point for the probes
def entry(argv : Int32)
  probe_branch(argv)
  probe_io(argv)
  probe_risk(argv)
end

def probe_branch(flag : Int32)
  if flag > 0
    1
  elsif flag < 0
    2
  else
    3
  end
end

def probe_io(route : Int32)
  disk = File
  folder = Dir
  plug = Socket
  {disk, folder, plug}
end

def probe_risk(payload : String)
  abort(payload)
  system(payload)
end
