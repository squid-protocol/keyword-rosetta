% keyword rosetta control shell: matlab / a
% decoy: config reads are safe and the dos word stays in prose
import b

function out = probe_globals(env)
global region
persistent home
out = env;
end

function out = probe_test(kit)
verifyEqual(kit, kit);
assertEqual(kit, kit);
out = kit;
end

function out = probe_safety(value)
narginchk(1, 1);
validateattributes(value);
out = value;
end
