# ELK Log Management

Centralised log management with **Elasticsearch, Logstash, Kibana and Filebeat**.
Logs are ingested from **3 sources** (Nginx, Application, System), parsed in Logstash,
stored in per-source indices, and visualised/alerted on in Kibana.

```
 sample-app ──writes──► logs/{nginx,application,system}
                              │
                         Filebeat (tails files)
                              │  :5044
                          Logstash (grok / json / date parsing)
                              │
                        Elasticsearch  ◄──── Kibana (dashboards, alerts) :5601
```

## Project structure

```
elk-log-management/
├── docker-compose.yml        # all services
├── .env                      # versions, ports, heap sizes, keys
├── filebeat/filebeat.yml     # 4 inputs (3 sources, nginx has access + error)
├── logstash/
│   ├── pipeline/logstash.conf  # parsing + routing to indices
│   └── config/logstash.yml
├── logs/                     # shared log folder (written by sample-app, read by Filebeat)
│   ├── nginx/{access,error}.log
│   ├── application/app.log
│   └── system/system.log
├── sample-app/               # Python log generator (Dockerfile + app.py)
└── kibana/setup.sh           # one-shot: creates data views + alert rules (extra helper)
```

## Quick start

```bash
# Linux only: Elasticsearch needs this
sudo sysctl -w vm.max_map_count=262144

docker compose up -d --build
docker compose logs -f kibana-setup     # wait for "Kibana setup complete."
```

Open Kibana: http://localhost:5601  |  Elasticsearch: http://localhost:9200

Verify data is flowing:

```bash
curl "localhost:9200/_cat/indices/elk-*?v"
curl "localhost:9200/elk-nginx-access-*/_search?size=1&pretty"
```

## Indices and index patterns (data views)

| Source | Index | Data view |
|---|---|---|
| Nginx access | `elk-nginx-access-YYYY.MM.dd` | Nginx Access |
| Nginx error | `elk-nginx-error-YYYY.MM.dd` | Nginx Error |
| Application | `elk-application-YYYY.MM.dd` | Application |
| System | `elk-system-YYYY.MM.dd` | System |
| All | `elk-*` | All Logs |

All data views use `@timestamp`, taken from the log line itself (not ingest time).
The `elk-` prefix is deliberate: names starting with `logs-` collide with
Elasticsearch's built-in data-stream template.

## Key parsed fields

- **Nginx access:** `clientip`, `verb`, `request`, `response` (int), `bytes` (int), `agent`
- **Nginx error:** `log_level`, `pid`, `error_message`
- **Application:** `level`, `service`, `msg`, `user`, `duration_ms`, `status`
- **System:** `hostname`, `program`, `pid`, `syslog_message`

Parse failures are tagged `_grok_*_failure` / `_json_app_failure`; search `tags:*failure*` to find them.

## Kibana dashboard (build in ~5 min)

Kibana → **Dashboards → Create dashboard → Create visualization** (Lens). Suggested panels:

1. **Requests over time**: Nginx Access, Bar, X = `@timestamp`, Y = Count
2. **HTTP status breakdown**: Nginx Access, Donut, slice by `response`
3. **Top client IPs**: Nginx Access, Table, rows = `clientip.keyword`, metric = Count
4. **Errors by service**: Application, Bar, X = `service.keyword`, filter `level : "ERROR"`
5. **Avg response time**: Application, Line, Y = Average of `duration_ms`
6. **System events by program**: System, Treemap, group by `program.keyword`
7. **Nginx error stream**: Saved search on Nginx Error (Discover → Save)

Save as "Log Overview". Set the time picker to *Last 15 minutes* and auto-refresh to 10s.
To keep it in git: Stack Management → Saved Objects → Export.

## Alerts

`kibana/setup.sh` creates three Elasticsearch-query rules (run every 1 minute, 5-minute window):

| Rule | Condition |
|---|---|
| Nginx 5xx spike | more than 5 responses with `response >= 500` |
| Application ERROR logs | more than 5 documents with `level: ERROR` |
| SSH failed logins | more than 3 "Failed password" system events |

Rules trigger a **Server log** connector. See firings with `docker logs kibana | grep -i alert`
or in Kibana → **Stack Management → Rules**. To send email/Slack/webhook instead,
add a connector under Stack Management → Connectors and attach it to the rules.

## Using your own logs

Drop real files into `logs/...` (or change the paths in `filebeat/filebeat.yml`),
and stop the generator: `docker compose stop sample-app`.
The Nginx format expected is the default `combined` format.

## Troubleshooting

| Problem | Fix |
|---|---|
| Elasticsearch exits immediately | Raise `vm.max_map_count` (see Quick start), or lower `ES_HEAP` in `.env` |
| No data in Kibana | Widen the time picker; check `docker compose logs filebeat logstash` |
| Rules missing | `docker compose up kibana-setup` to re-run the setup |
| Re-ingest from scratch | `docker compose down -v` (also deletes stored data) |

## Security note

Security is disabled (`xpack.security.enabled=false`) to keep this a simple local lab.
Enable TLS and authentication before exposing anything to a network.
