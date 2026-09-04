# keyword rosetta control shell: ruby / a
# decoy: config reads are safe and the abort word stays in prose
require 'b'

def probe_globals(env)
  region = ENV
  args = ARGV
  [region, args]
end

def probe_test(kit)
  suite = describe
  bench = expect
  [suite, bench]
end

def probe_safety(value)
  value.freeze
rescue
  value
end

module_function :probe_globals
module_function :probe_test
module_function :probe_safety
