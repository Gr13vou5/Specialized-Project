FROM ubuntu:22.04

RUN apt update && apt install -y git wget cmake make g++ libboost-all-dev libmpfr-dev libgmp-dev zlib1g-dev ninja-build

WORKDIR /usr/local/src/
COPY d4v2 ./d4v2
RUN cd d4v2 && ./build.sh

RUN git clone https://git.trs.css.i.nagoya-u.ac.jp/k-hasimt/GPMC.git
RUN cd GPMC && ./build.sh rs

RUN git clone https://github.com/Laakeri/sharpsat-td.git
RUN cd sharpsat-td && ./setupdev.sh static

RUN wget http://www.sd.is.uec.ac.jp/toda/code/bdd_minisat_all-1.0.2.tar.gz
RUN tar xvzf bdd_minisat_all-1.0.2.tar.gz
RUN cd bdd_minisat_all-1.0.2 && make r -j2

RUN git clone https://github.com/arminbiere/cadical.git
RUN cd cadical && ./configure && make -j2

FROM ubuntu:22.04

RUN apt update && apt install -y --no-install-recommends default-jre time

COPY --from=0 /usr/local/src/d4v2/build/d4 /usr/local/src/GPMC/build/gpmc /usr/local/src/sharpsat-td/bin/* /usr/local/bin/
COPY --from=0 /usr/local/src/bdd_minisat_all-1.0.2/bdd_minisat_all_release /usr/local/src/cadical/build/cadical /usr/local/bin/
COPY bsaf.jar solve.sh solve-d4.sh solve-d4-anytime.sh solve-gpmc.sh solve-sharpsat.sh solve-bmsa.sh /app/

WORKDIR /benchmark

ENTRYPOINT ["time", "-v"]
