# keyword rosetta control shell: dockerfile / a
# decoy: config reads are safe and the eval word stays in prose
FROM b
ARG ENVKIT

ENV REGION=1
ENV HOME_ZONE=2

RUN pytest
RUN make test

HEALTHCHECK CMD true
