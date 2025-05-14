FROM postgres:17

RUN apt-get update \
    && apt-get install -y \
        build-essential \
        postgresql-server-dev-17 \
        git \
        make \
        gcc \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/pgbigm/pg_bigm.git \
    && cd pg_bigm \
    && make USE_PGXS=1 \
    && make USE_PGXS=1 install

RUN apt-get remove -y build-essential postgresql-server-dev-17 git make gcc \
    && apt-get autoremove -y \
    && rm -rf /pg_bigm