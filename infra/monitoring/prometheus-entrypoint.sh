#!/bin/sh
apk add --no-cache aws-cli
aws s3 cp s3://event-platform-config-410772457866/prometheus.yml /etc/prometheus/prometheus.yml
exec prometheus --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus
