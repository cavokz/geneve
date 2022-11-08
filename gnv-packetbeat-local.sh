#!/bin/bash -ex

GENEVE=${GENEVE:-http://localhost:9256}

SCHEMA_YAML="ecs_flat.yml"
SOURCE=network
SINK=packetbeat-test
FLOW=explore-network
TEST_ELASTICSEARCH_URL="http://elastic:changeme@localhost:9200"
TEST_KIBANA_URL="http://elastic:changeme@localhost:5601/__UNSAFE_bypassBasePath"
HOST_NAME_CARDINALITY=20
EVENTS_COUNT=100
#HOST_NAME_CARDINALITY=10
#DST_IP_CARDINALITY=100
#SRC_IP_CARDINALITY=100

curl -fs -XPUT -H "Content-Type: application/json" $TEST_ELASTICSEARCH_URL/_cluster/settings --data @- <<EOF
{
  "transient": {
    "ingest": {
      "geoip": {
        "downloader": {
          "enabled": "true"
        }
      }
    }
  }
}
EOF
sleep 2
(
  curl -s -XDELETE $GENEVE/api/flow/$FLOW
  curl -s -XDELETE $GENEVE/api/sink/$SINK
  curl -s -XDELETE $GENEVE/api/source/$SOURCE

  curl -s -XDELETE $TEST_ELASTICSEARCH_URL/$SINK
  curl -s -XDELETE $TEST_ELASTICSEARCH_URL/_ingest/pipeline/geoip-info
) >/dev/null

curl -fs -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/sink/$SINK" --data-binary @- <<EOF
url: $TEST_ELASTICSEARCH_URL/$SINK/_doc?pipeline=geoip-info
EOF

curl -fs -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/schema/ecs" --data-binary "@$SCHEMA_YAML"

curl -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/source/$SOURCE" --data-binary @- <<EOF
schema: ecs
queries:
  - 'network where

      "@timestamp" != null and

        destination.bytes > 0 and destination.bytes < 1000000 and
      destination.geo.city_name != null and
      destination.geo.continent_name != null and
      destination.geo.country_iso_code != null and
      destination.geo.country_name != null and
      destination.geo.location != null and
      destination.geo.region_iso_code != null and
      destination.geo.region_name != null and
      cidrMatch(destination.ip, "34.70.44.67/8") and

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
      host.name != null and
      cidrMatch(host.ip, "34.70.44.67/8") and

      network.community_id != null and

        source.bytes > 0 and source.bytes < 1000000 and
        source.domain in ("*.com", "*.edu", "*.org") and
      source.geo.city_name != null and
      source.geo.continent_name != null and
      source.geo.country_iso_code != null and
      source.geo.country_name != null and
      source.geo.location != null and
      source.geo.region_iso_code != null and
      source.geo.region_name != null and
      cidrMatch(source.ip, "34.70.44.67/8") and

        _cardinality(destination.ip, ${DST_IP_CARDINALITY:-0}) and
        _cardinality(host.name, ${HOST_NAME_CARDINALITY:-0}) and
        _cardinality(source.ip, ${SRC_IP_CARDINALITY:-0})
    '
EOF



curl -fs -w "\n" -XPUT -H "Content-Type: application/json" $TEST_ELASTICSEARCH_URL/_ingest/pipeline/geoip-info --data @- <<EOF
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

curl -fs -XPUT -H "Content-Type: application/yaml" "$GENEVE/api/flow/$FLOW" --data-binary @- <<EOF
source:
  name: $SOURCE
sink:
  name: $SINK
count: $EVENTS_COUNT
EOF

curl -fs -w "\n" -XPUT -H "Content-Type: application/json" $TEST_ELASTICSEARCH_URL/$SINK --data @- <<EOF
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": $(curl -fs "$GENEVE/api/source/$SOURCE/_mappings")
}
EOF

curl -s -XPOST -H "Content-Type: application/json" -H "kbn-xsrf: true" $TEST_KIBANA_URL/api/data_views/data_view --data @- <<EOF
{
  "data_view": {
     "title": "packetbeat-*"
  },
  "override": true
}
EOF

curl -fs -XPOST "$GENEVE/api/flow/$FLOW/_start"

set +x
while true; do
  OUT=$(curl -fs "$GENEVE/api/flow/$FLOW")
  echo "$OUT"
  if echo $OUT | grep -q "alive: false"; then
    break
  fi
  sleep 1
done
