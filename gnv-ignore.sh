#! /bin/sh -e

GENEVE=${GENEVE:-http://localhost:9256}

curl -s -XDELETE "$GENEVE/api/grasp/ignore"
curl -s -XPOST -H "Content-Type: application/yaml" "$GENEVE/api/grasp/ignore" --data-binary '@tests/grasp-ignore.yaml'
curl -s -XDELETE "$GENEVE/api/grasp"
