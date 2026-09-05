# keyword rosetta control shell: dockerfile / a
# decoy: config reads are safe and the eval word stays in prose
FROM b
ARG ENVKIT
EXPOSE 8081

ENV REGION=1
ENV HOME_ZONE=2

USER probe

RUN pytest
RUN make test

HEALTHCHECK CMD true
