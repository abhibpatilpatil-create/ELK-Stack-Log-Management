#!/bin/sh
# Creates Kibana data views (index patterns) and alert rules via the Kibana API.
K="http://kibana:5601"
H1="kbn-xsrf: true"
H2="Content-Type: application/json"

echo "Waiting for Kibana..."
until curl -s "$K/api/status" | grep -q '"level":"available"'; do sleep 5; done

mk_view () {  # $1=title pattern  $2=display name
  curl -s -X POST "$K/api/data_views/data_view" -H "$H1" -H "$H2" -d "{
    \"data_view\": {\"title\": \"$1\", \"name\": \"$2\", \"timeFieldName\": \"@timestamp\"},
    \"override\": true }" > /dev/null
  echo "data view: $2 ($1)"
}
mk_view "elk-nginx-access-*"  "Nginx Access"
mk_view "elk-nginx-error-*"   "Nginx Error"
mk_view "elk-application-*"   "Application"
mk_view "elk-system-*"        "System"
mk_view "elk-*"               "All Logs"

# Connector used by alerts (writes to Kibana server log: docker logs kibana)
curl -s -X POST "$K/api/actions/connector/server-log-connector" -H "$H1" -H "$H2" \
  -d '{"name":"Server log","connector_type_id":".server-log"}' > /dev/null
echo "connector: server-log-connector"

mk_rule () {  # $1=name $2=index $3=esQuery(json string) $4=threshold $5=window-min $6=message
  curl -s -X POST "$K/api/alerting/rule" -H "$H1" -H "$H2" -d "{
    \"name\": \"$1\",
    \"consumer\": \"alerts\",
    \"rule_type_id\": \".es-query\",
    \"schedule\": {\"interval\": \"1m\"},
    \"params\": {
      \"searchType\": \"esQuery\",
      \"index\": [\"$2\"],
      \"timeField\": \"@timestamp\",
      \"esQuery\": \"$3\",
      \"size\": 100,
      \"timeWindowSize\": $5,
      \"timeWindowUnit\": \"m\",
      \"threshold\": [$4],
      \"thresholdComparator\": \">\",
      \"excludeHitsFromPreviousRun\": false
    },
    \"actions\": [{
      \"id\": \"server-log-connector\",
      \"group\": \"query matched\",
      \"params\": {\"level\": \"error\", \"message\": \"$6\"},
      \"frequency\": {\"summary\": false, \"notify_when\": \"onActionGroupChange\", \"throttle\": null}
    }]
  }" > /dev/null
  echo "rule: $1"
}

mk_rule "Nginx 5xx spike" "elk-nginx-access-*" \
  '{\"query\":{\"range\":{\"response\":{\"gte\":500}}}}' 5 5 \
  "ALERT: more than 5 HTTP 5xx responses in the last 5 minutes"

mk_rule "Application ERROR logs" "elk-application-*" \
  '{\"query\":{\"match\":{\"level\":\"ERROR\"}}}' 5 5 \
  "ALERT: more than 5 application ERROR logs in the last 5 minutes"

mk_rule "SSH failed logins" "elk-system-*" \
  '{\"query\":{\"match_phrase\":{\"syslog_message\":\"Failed password\"}}}' 3 5 \
  "ALERT: possible brute force - repeated SSH failed logins"

echo "Kibana setup complete."
