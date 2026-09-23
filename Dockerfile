FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl lib32gcc-s1 lib32stdc++6 libcurl3t64-gnutls \
    libstdc++6 supervisor util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && usermod --login dst --home /data ubuntu \
    && groupmod --new-name dst ubuntu
ENV DST_USER=dst DST_GROUP=dst DST_USER_DATA_PATH=/data HOME=/root
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/server.sh /usr/local/bin/dontstarve_dedicated_server_nullrenderer
RUN chmod 755 /usr/local/bin/entrypoint.sh /usr/local/bin/dontstarve_dedicated_server_nullrenderer
STOPSIGNAL SIGINT
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
