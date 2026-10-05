FROM docker.elastic.co/elasticsearch/elasticsearch:9.5.4

COPY plugin/*.zip /tmp/bitext-plugin/
RUN test "$(find /tmp/bitext-plugin -maxdepth 1 -type f -name '*.zip' | wc -l)" -eq 1 \
 && bin/elasticsearch-plugin install --batch "file:$(find /tmp/bitext-plugin -maxdepth 1 -type f -name '*.zip')"
