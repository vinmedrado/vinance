FROM postgres:16-alpine

RUN apk add --no-cache bash coreutils openssl findutils

COPY backup.sh restore.sh disk-check.sh drill.sh /usr/local/bin/
RUN chmod 0555 /usr/local/bin/backup.sh /usr/local/bin/restore.sh /usr/local/bin/disk-check.sh /usr/local/bin/drill.sh

CMD ["/usr/local/bin/backup.sh"]
