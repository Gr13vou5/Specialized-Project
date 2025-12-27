FROM ubuntu:22.04

RUN apt update && apt install -y git cmake g++

WORKDIR /usr/local/src/
RUN git clone https://github.com/potassco/clingo.git
WORKDIR /usr/local/src/clingo
RUN git submodule update --init --recursive && cmake -H. -Bbuild -DCMAKE_BUILD_TYPE=Release -DCLINGO_BUILD_STATIC=ON
RUN cmake --build build -j2

FROM ubuntu:22.04

RUN apt update && apt install -y --no-install-recommends ca-certificates curl gcc python3.11 libpython3.11-dev time
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python3.11 get-pip.py && rm -f get-pip.py

RUN pip3.11 install fASP

COPY --from=0 /usr/local/src/clingo/build/bin/clingo /usr/local/bin/

WORKDIR /benchmark

ENTRYPOINT ["time", "-v", "fASP"]
