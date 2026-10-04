# Grafana dashboards for Steerhouse

Three dashboards for a Grafana you run yourself (Steerhouse doesn't bundle one). They read two
data sources:

- **Prometheus**, scraping Steerhouse's metrics: what is happening now (queue, workers, API,
  notifications, sign-in failures). Turn the metrics on with `METRICS_TOKEN`; see
  "Monitoring with Prometheus and Grafana" in the main [README](../README.md) and
  [prometheus/scrape.example.yml](prometheus/scrape.example.yml).
- **PostgreSQL**, Steerhouse's database, read through a role that can only read the
  `analytics` views: history (runs, durations, failures, sign-ins, audit events). Set up the
  role with `python -m app.cli analytics-grant` as the main README describes.

| Dashboard | uid | Shows |
| --- | --- | --- |
| [Overview & runs](dashboards/steerhouse-overview.json) | `steerhouse-overview` | health right now, finished runs by status, success rate, run durations, host outcomes, the playbooks that fail most, recent failed runs (linked to Steerhouse), annotations for failed runs |
| [Execution, queue & workers](dashboards/steerhouse-execution.json) | `steerhouse-execution` | queue depth and the oldest queued run, slots in use, workers, queue wait and run duration percentiles, notification outbox and sends, API traffic, latency and errors, the API process, execution history |
| [Security & access](dashboards/steerhouse-security.json) | `steerhouse-security` | failed sign-ins and lockouts, refused tokens and permission denials, sign-ins by method, most-tried user names, failed sign-ins by source network (/24 or /48), admin and access changes, API keys to look at, user counts |

Every dashboard has two data source variables at the top, **Prometheus** and **Steerhouse
database**, so no data source uid is hard-coded. Overview and execution also have a
**Project** filter. Overview has an **Steerhouse URL** box: put your `PUBLIC_URL` there and run
numbers link to the run.

## Importing

- **By hand:** Dashboards > New > Import, upload a JSON file, then pick your two data sources
  in the variables at the top (Grafana remembers them when you save).
- **Provisioned:** copy [provisioning/dashboards/steerhouse.example.yaml](provisioning/dashboards/steerhouse.example.yaml)
  into Grafana's `provisioning/dashboards/` and mount `grafana/dashboards/` at the path it
  names. [provisioning/datasources/steerhouse.example.yaml](provisioning/datasources/steerhouse.example.yaml)
  provisions both data sources; set `STEERHOUSE_GRAFANA_DB_PASSWORD` in Grafana's environment.

Keep the database data source's **Max open connections** (`maxOpenConns`, 5 in the example)
below the role's `CONNECTION LIMIT`: Grafana's default allows 100, and the role then gets
"too many connections" errors.

The dashboards were built for Grafana 13 and use only core panels and the core Prometheus
and PostgreSQL data sources.

## Alert rules (optional)

[provisioning/alerting/steerhouse.example.yaml](provisioning/alerting/steerhouse.example.yaml)
has four Grafana alert rules for trends: runs failing more than usual, failed sign-ins
spiking, notifications not going out, and metrics missing or the database unreachable.
Steerhouse's own notifications already report single events (a failed run, a worker offline,
the queue stuck, a login attack, an admin change), so the rules don't repeat those. They
expect the Prometheus data source uid `steerhouse-prometheus` from the data source example.

## Checking them

`tools/verify_dashboards.py` imports the dashboards into a Grafana and runs every panel,
annotation and variable query through it. CI does this against a fresh Steerhouse after a
real run; you can point it at a test Grafana (it creates or updates two data sources there):

```sh
GRAFANA_PASSWORD=... POSTGRES_PASSWORD=... python3 grafana/tools/verify_dashboards.py \
  --grafana http://localhost:3000 --prometheus-url http://prometheus:9090 \
  --postgres postgres:5432 --database steerhouse --postgres-user grafana_ro
```

The backend tests also check the dashboards: SQL only reads `analytics.*` views and runs as a
role limited to them, and every metric a query names is one Steerhouse exports.

## Changing them

Edit in Grafana, then export (Share > Export, without "Export for sharing externally", which
would add `__inputs`) and replace the file. Keep the uid, remove the top-level `id`, and keep
the data source references as `${prometheus}` and `${postgres}`; the tests check these.
