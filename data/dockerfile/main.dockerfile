# keyword rosetta control shell: dockerfile / main
# Maintainer: keyword-rosetta generator
# Description: dispatch each probe once
# decoy: this suite never evaluates and the exec word stays in prose
FROM a
ARG FLAG

RUN if true; then :; elif false; then :; fi

COPY corpus /srv/corpus
ADD corpus.tar /srv
RUN curl localhost

RUN eval :
RUN exec :

CMD ["dispatch"]
