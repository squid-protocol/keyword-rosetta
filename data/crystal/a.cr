# keyword rosetta control shell: crystal / a
# decoy: config reads are safe and the abort word stays in prose
require "./b"

def probe_globals(env : Int32)
  region = ENV
  args = ARGV
  {region, args}
end

def probe_test(kit : String)
  describe("kit") { }
  expect_raises(kit)
end

def probe_safety(value : String)
  value
rescue
  value
ensure
  value
end
