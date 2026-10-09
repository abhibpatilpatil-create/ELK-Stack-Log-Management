"""
Sample app: simulates a small web shop and writes logs from 3 sources:
  - nginx access/error logs  -> $LOG_DIR/nginx/
  - application JSON logs    -> $LOG_DIR/application/app.log
  - system (syslog) logs     -> $LOG_DIR/system/system.log
"""
import json
import os
import random
import time
from datetime import datetime, timezone

LOG_DIR = os.getenv("LOG_DIR", "./logs")
PATHS = {
    "access": f"{LOG_DIR}/nginx/access.log",
    "error": f"{LOG_DIR}/nginx/error.log",
    "app": f"{LOG_DIR}/application/app.log",
    "system": f"{LOG_DIR}/system/system.log",
}
for p in PATHS.values():
    os.makedirs(os.path.dirname(p), exist_ok=True)

IPS = ["192.168.1.10", "192.168.1.11", "10.0.0.5", "172.16.0.20", "203.0.113.9"]
ROUTES = ["/", "/index.html", "/api/orders", "/api/users", "/api/payment", "/login", "/static/app.js"]
AGENTS = ["Mozilla/5.0", "curl/8.4.0", "python-requests/2.31", "PostmanRuntime/7.36"]
USERS = ["alice", "bob", "carol", "dave", "erin"]
SERVICES = ["order-service", "payment-service", "user-service", "inventory-service"]
HOST = "web01"


def write(kind, line):
    with open(PATHS[kind], "a", encoding="utf-8") as f:
        f.write(line + "\n")


def now():
    return datetime.now(timezone.utc)


def gen_nginx():
    ip, route = random.choice(IPS), random.choice(ROUTES)
    r = random.random()
    status = 200 if r < 0.80 else 404 if r < 0.90 else 301 if r < 0.93 else 500 if r < 0.97 else 502
    method = random.choice(["GET", "GET", "GET", "POST"])
    size = random.randint(80, 5000)
    ts = now().strftime("%d/%b/%Y:%H:%M:%S +0000")
    write("access", f'{ip} - - [{ts}] "{method} {route} HTTP/1.1" {status} {size} "-" "{random.choice(AGENTS)}"')
    if status >= 500:
        ets = now().strftime("%Y/%m/%d %H:%M:%S")
        write("error", f"{ets} [error] 29#29: *{random.randint(1, 9999)} connect() failed "
                       f"(111: Connection refused) while connecting to upstream, client: {ip}, server: localhost")


def gen_app():
    r = random.random()
    level = "INFO" if r < 0.75 else "WARN" if r < 0.90 else "ERROR"
    msgs = {
        "INFO": ["Order created", "User logged in", "Cache hit", "Inventory updated"],
        "WARN": ["Slow query detected", "Retrying request", "Low stock"],
        "ERROR": ["Payment gateway timeout", "DB connection lost", "Unhandled exception"],
    }
    rec = {
        "timestamp": now().isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "level": level,
        "service": random.choice(SERVICES),
        "msg": random.choice(msgs[level]),
        "user": random.choice(USERS),
        "duration_ms": random.randint(5, 300) if level != "ERROR" else random.randint(1000, 6000),
        "status": 200 if level == "INFO" else 429 if level == "WARN" else 500,
    }
    write("app", json.dumps(rec))


def gen_system():
    n = now()
    ts = f"{n:%b} {n.day:>2} {n:%H:%M:%S}"
    pid = random.randint(1000, 9999)
    events = [
        ("sshd", f"Accepted publickey for deploy from {random.choice(IPS)} port {random.randint(30000, 60000)} ssh2"),
        ("sshd", f"Failed password for invalid user admin from 203.0.113.{random.randint(1, 50)} port {random.randint(30000, 60000)} ssh2"),
        ("CRON", "(root) CMD (/usr/local/bin/backup.sh)"),
        ("systemd", "Started Daily apt download activities."),
        ("kernel", "Out of memory: Killed process 4242 (java)"),
    ]
    weights = [30, 12, 30, 25, 3]
    prog, msg = random.choices(events, weights=weights)[0]
    write("system", f"{ts} {HOST} {prog}[{pid}]: {msg}")


if __name__ == "__main__":
    print(f"sample-app writing logs to {LOG_DIR}")
    while True:
        for _ in range(random.randint(1, 4)):
            gen_nginx()
        gen_app()
        if random.random() < 0.4:
            gen_system()
        time.sleep(random.uniform(0.5, 2.0))
