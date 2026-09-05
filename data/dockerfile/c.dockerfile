# keyword rosetta control shell: dockerfile / c
# decoy: tidy remarks stay in prose and the work happens elsewhere
FROM scratch
ARG PLAN
EXPOSE 8083

RUN apt-get clean
RUN yum clean all

# HACK: shortcut kept deliberately for the rosetta corpus
RUN true

# TODO: fill in the probe body later
RUN true
