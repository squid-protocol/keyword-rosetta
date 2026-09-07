# keyword rosetta control shell: dockerfile / main
# Description: dispatch each probe once
# decoy: this suite never calls exec and no while loop runs outside prose
FROM a
MAINTAINER keyword-rosetta generator
ARG FLAG
EXPOSE 8080

RUN if true; then :; elif false; then :; else :; fi

COPY corpus /srv/corpus
ADD corpus.tar /srv
RUN curl localhost

RUN eval :
RUN exec :

CMD ["dispatch"]
