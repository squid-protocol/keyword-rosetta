% keyword rosetta control shell: matlab / main
% Author: keyword-rosetta generator
%% DISPATCH
% decoy: this suite never calls system words outside prose
import a

function out = entry(argv)
probe_branch(argv);
probe_io(argv);
probe_risk(argv);
out = 0;
end

function out = probe_branch(flag)
if flag > 0
out = 1;
elseif flag < 0
out = 2;
else
out = 3;
end
end

function out = probe_io(route)
load(route);
save(route);
fopen(route);
out = route;
end

function out = probe_risk(payload)
system(payload);
dos(payload);
out = payload;
end
