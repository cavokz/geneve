#!/bin/bash -ex

GENEVE=${GENEVE:-http://localhost:9256}

SCHEMA_YAML="etc/ecs-8.2.0/generated/ecs/ecs_flat.yml"
SOURCE=network
SINK=packetbeat-test
FLOW=explore-network

EVENTS_COUNT=1000
#HOST_NAME_CARDINALITY=10
#DST_IP_CARDINALITY=100
#SRC_IP_CARDINALITY=100

(
  curl -s -XDELETE $GENEVE/api/flow/$FLOW
  curl -s -XDELETE $GENEVE/api/sink/$SINK
  curl -s -XDELETE $GENEVE/api/source/$SOURCE

  curl -s -XDELETE $TEST_ELASTICSEARCH_URL/$SINK
  curl -s -XDELETE $TEST_ELASTICSEARCH_URL/_ingest/pipeline/geoip-info
) >/dev/null

fail_on_error()
{
  set +x

  OUT=$(cat -)
  if echo "$OUT" | grep -q -i -e error -e exception; then
    echo "$OUT"
    return 1
  fi
}

#url: $TEST_ELASTICSEARCH_URL/$SINK/_doc?pipeline=geoip-info
curl -s -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/sink/$SINK" --data-binary @- <<EOF | fail_on_error
url: $TEST_ELASTICSEARCH_URL/$SINK/_doc
EOF

curl -s -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/schema/ecs" --data-binary "@$SCHEMA_YAML" | fail_on_error

curl -s -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/source/$SOURCE" --data-binary @- <<EOF | fail_on_error
schema: ecs
queries:
  - 'network where

      "@timestamp" != null and

      destination.as.number != null and
      destination.bytes != null and
      destination.domain != null and
      destination.geo.city_name != null and
      destination.geo.continent_name != null and
      destination.geo.country_iso_code != null and
      destination.geo.country_name != null and
      destination.geo.location != null and
      destination.geo.region_iso_code != null and
      destination.geo.region_name != null and
      destination.ip != null and
      destination.mac != null and

        ecs.version == "8.2" and

      event.category != null and
      event.kind != null and
      event.type != null and

        host.architecture in ("x86_64", "aarch64", "riscv") and
      host.geo.city_name != null and
      host.geo.continent_name != null and
      host.geo.country_iso_code != null and
      host.geo.country_name != null and
      host.geo.location != null and
      host.geo.region_iso_code != null and
      host.geo.region_name != null and
      host.id != null and
      host.ip != null and
      host.name != null and
      host.mac != null and
      host.os.tyoe != null and

      network.community_id != null and

      source.as.number != null and
      source.bytes != null and
      source.domain != null and
      source.geo.city_name != null and
      source.geo.continent_name != null and
      source.geo.country_iso_code != null and
      source.geo.country_name != null and
      source.geo.location != null and
      source.geo.region_iso_code != null and
      source.geo.region_name != null and
      source.ip != null and
      source.mac != null and

        _cardinality(destination.ip, ${DST_IP_CARDINALITY:-0}) and
        _cardinality(host.name, ${HOST_NAME_CARDINALITY:-0}) and
        _cardinality(source.ip, ${SRC_IP_CARDINALITY:-0})
    '
EOF

curl -s -XPUT -H "Content-Type: application/json" $TEST_ELASTICSEARCH_URL/_ingest/pipeline/geoip-info --data @- <<EOF | fail_on_error
{
  "description": "Add geoip info",
  "processors": [
    {
      "geoip": {
        "field": "client.ip",
        "target_field": "client.geo",
        "ignore_missing": true
      }
    },
    {
      "geoip": {
        "field": "source.ip",
        "target_field": "source.geo",
        "ignore_missing": true
      }
    },
    {
      "geoip": {
        "field": "destination.ip",
        "target_field": "destination.geo",
        "ignore_missing": true
      }
    },
    {
      "geoip": {
        "field": "server.ip",
        "target_field": "server.geo",
        "ignore_missing": true
      }
    },
    {
      "geoip": {
        "field": "host.ip",
        "target_field": "host.geo",
        "ignore_missing": true
      }
    }
  ]
}
EOF

curl -s -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/flow/$FLOW" --data-binary @- <<EOF | fail_on_error
source:
  name: $SOURCE
sink:
  name: $SINK
count: $EVENTS_COUNT
EOF

curl -s -XPUT -H "Content-Type: application/json" $TEST_ELASTICSEARCH_URL/$SINK --data @- <<EOF | fail_on_error
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": $(curl -fs "$GENEVE/api/source/$SOURCE/_mappings")
}
EOF

curl -s -XPOST -H "Content-Type: application/json" -H "kbn-xsrf: true" $TEST_KIBANA_URL/api/data_views/data_view --data @- <<EOF | fail_on_error
{
  "data_view": {
     "title": "packetbeat-*"
  },
  "override": true
}
EOF

curl -s -XPOST "$GENEVE/api/flow/$FLOW/_start" | fail_on_error

set +x
while true; do
  OUT=$(curl -fs "$GENEVE/api/flow/$FLOW")
  echo "$OUT"
  if echo $OUT | grep -q "alive: false"; then
    break
  fi
  sleep 1
done
