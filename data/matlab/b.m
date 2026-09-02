% keyword rosetta control shell: matlab / b
% decoy: nothing risky lives here and the elseif word stays in prose
import c

function out = probe_bypass(shape)
eval(shape);
evalin(shape);
out = shape;
end

function out = probe_telemetry(msg)
log4m(msg);
logInfo(msg);
out = msg;
end

function out = probe_state(items)
clear scratch
clearvars leftover
note = 'plain exit decoy text';
out = items;
end
