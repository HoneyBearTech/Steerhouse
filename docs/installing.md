# Installing

This runs a released version of Steerhouse in production from the published container images, with Docker
Compose, behind a reverse proxy that terminates HTTPS. For a quick local try-out, see
[quick-start.md](quick-start.md).

Steerhouse is meant for a trusted network: don't expose it directly to the internet (see
[security.md](security.md)).

## What you need

- A Linux host with Docker Engine 26 or later (the compose file mounts a volume subpath) and Docker
  Compose v2.
- A DNS name for Steerhouse and a reverse proxy that serves it over HTTPS (Caddy, nginx, Traefik, …).
- Network access from that host to the machines your playbooks manage, over SSH.

The images are `honeybeartech/steerhouse-backend` (the API and the workers) and
`honeybeartech/steerhouse-frontend` (the web UI) on [Docker Hub](https://hub.docker.com/u/honeybeartech), from
v0.10.1 on. The same images are mirrored to `ghcr.io/honeybeartech/steerhouse-backend` and
`ghcr.io/honeybeartech/steerhouse-frontend`, which also hold the releases before v0.10.1. Each release is signed
in both registries; check them with [verifying-releases.md](verifying-releases.md) before you start.

## 1. Get the deployment files

Download `compose.yaml` and `.env.example` from the [`deploy/` folder](../deploy) of the release you install
(for v0.11.0: `https://raw.githubusercontent.com/HoneyBearTech/Steerhouse/v0.11.0/deploy/compose.yaml`), into a
directory of their own, for example `/opt/steerhouse`:

```sh
sudo mkdir -p /opt/steerhouse && cd /opt/steerhouse
sudo curl -fsSLO https://raw.githubusercontent.com/HoneyBearTech/Steerhouse/v0.11.0/deploy/compose.yaml
sudo curl -fsSL -o .env https://raw.githubusercontent.com/HoneyBearTech/Steerhouse/v0.11.0/deploy/.env.example
```

## 2. Create the secrets

Secrets live in files under `secrets/`, which Compose hands to the containers as Docker secrets. Only the
database and the API see them; the workers get none. Generate them once:

```sh
sudo mkdir -p secrets
pw=$(openssl rand -hex 24)
printf '%s\n' "$pw" | sudo tee secrets/postgres_password >/dev/null
printf 'postgresql+psycopg://steerhouse:%s@postgres:5432/steerhouse\n' "$pw" | sudo tee secrets/database_url >/dev/null
openssl rand -hex 32 | sudo tee secrets/auth_secret_key >/dev/null
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" \
  | sudo tee secrets/credential_encryption_key >/dev/null
printf 'Password for the first admin: '; stty -echo; read -r admin; stty echo; echo
printf '%s\n' "$admin" | sudo tee secrets/admin_password >/dev/null
sudo chmod 700 secrets && sudo chmod 444 secrets/*
```

The directory is closed to other users on the host. The files themselves must stay readable, because the
database (uid 999) and the API (uid 1000) read them inside their containers.

- `credential_encryption_key` encrypts every stored SSH key, vault password and token. **Back it up
  separately** (for example in your password manager): without it, a database backup can't be decrypted,
  and anyone who has both can decrypt everything. To change it later, see
  [upgrading.md](upgrading.md#changing-the-encryption-key).
- `admin_password` is only used to create the first admin, on the very first start. Change it later under
  **Account**, and turn on two-factor login there.

## 3. Set the remaining settings

Edit `.env`: set `WORKER_TOKEN` to a long random string (`openssl rand -hex 32`), and check
`STEERHOUSE_VERSION`. The workers need this token in their environment rather than a file: Compose makes
secret files readable to every user in a container, and a worker runs playbooks as other users, which must
not see it. Optional settings (single sign-on, notifications by email, a secret store, metrics) are listed
in the [README](../README.md); add them to the `environment:` of the `backend` service.

## 4. Start it

```sh
sudo docker compose up -d --wait
sudo docker compose ps
```

The API creates and migrates the database on start-up. `postgres`, `backend` and `worker` should be
running, and `postgres` and `backend` healthy. The web UI now answers on `127.0.0.1:8080`.

Add workers or slots when runs queue up: `docker compose up -d --scale worker=3`, or a higher
`WORKER_SLOTS` (runs per worker at once).

Runs can't reach the API or cloud metadata services: the worker installs firewall rules for them (that's
what its `NET_ADMIN` capability is for). If playbooks use the host's cloud identity, set
`WORKER_ALLOW_CLOUD_METADATA=true` in `.env`; see `.env.example` for the other settings.

## 5. Put HTTPS in front

Point your reverse proxy at `127.0.0.1:8080`. It must pass WebSocket upgrades (live run output uses
them), the original `Host` header and the client's address in `X-Forwarded-For`, and should add HSTS. With [Caddy](https://caddyserver.com/), which
gets a certificate by itself and handles WebSockets:

```caddyfile
steerhouse.example.com {
    reverse_proxy 127.0.0.1:8080
    header Strict-Transport-Security "max-age=31536000"
}
```

With nginx:

```nginx
server {
    listen 443 ssl;
    server_name steerhouse.example.com;
    # ssl_certificate / ssl_certificate_key ...
    add_header Strict-Transport-Security "max-age=31536000" always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 1h; # long runs keep their output stream open
    }
}
```

The frontend container already sends a Content-Security-Policy and other browser hardening headers; don't
strip them. If the proxy changes the `Host` header, add the public origin to `CORS_ORIGINS` in `.env`.

The frontend takes the client's address from `X-Forwarded-For` only when the request comes from a proxy it
trusts: by default the Docker gateway, which is where a proxy on the same host reaches `127.0.0.1:8080`
from. For a proxy in another container or on another machine, list its address or network in
`TRUSTED_PROXIES` in `.env` (for example `TRUSTED_PROXIES=gateway,172.30.0.0/16`). Check the result under
**Audit**: sign-ins should show your own address, not one shared address. The API, in turn, trusts the
address only from the frontend container (`TRUSTED_PROXY_HOSTS`, default `frontend`).

## 6. Sign in

Open `https://steerhouse.example.com`, sign in as `admin` with the password you chose, and work through the
[quick start](quick-start.md#2-add-what-a-run-needs) from step 2. Then:

- create projects and users, or connect single sign-on ([user guide](user-guide/projects-and-users.md));
- set up a notification channel for failed runs and security alerts
  ([notifications](user-guide/notifications.md));
- schedule backups ([upgrading.md](upgrading.md#back-up)).

## 7. Monitoring with Prometheus and Grafana (optional)

The `monitoring` profile adds Prometheus and Grafana, already connected to Steerhouse: Prometheus scrapes the
API's metrics, Grafana has both data sources and Steerhouse's three [dashboards](../grafana/README.md). Nothing
changes for an installation that doesn't turn it on.

1. **Two more secrets** in `secrets/` (like step 2):

   ```sh
   cd /opt/steerhouse
   sudo sh -c 'printf %s "a password you will log in to Grafana with" > secrets/grafana_admin_password'
   sudo sh -c 'openssl rand -hex 24 | tr -d "\n" > secrets/grafana_db_password'
   sudo chmod 444 secrets/grafana_admin_password secrets/grafana_db_password
   ```

   `grafana_db_password` is the password of the read-only database role `grafana_ro`, which Steerhouse creates
   for you; you never type it.
2. **Settings** in `.env`: a token Prometheus uses to read the metrics, the backend's metrics listener
   (it only answers on the internal `monitoring` network), and the profile itself, so every `docker compose`
   command includes it:

   ```
   METRICS_TOKEN=<openssl rand -hex 32>
   METRICS_HOST=0.0.0.0
   COMPOSE_PROFILES=monitoring
   ```

3. **Start it**: `sudo docker compose up -d --wait`. A one-shot service, `monitoring-setup`, runs first: it
   creates `grafana_ro`, limits it to the read-only `analytics` views, and writes the Prometheus and
   Grafana configuration. Then open `http://127.0.0.1:3000`, sign in as `admin` with the password from
   step 1, and look in the **Steerhouse** folder.

Things to know:

- **Where it listens.** Grafana only on `127.0.0.1:3000` (`GRAFANA_BIND`): publish it through your
  TLS-terminating proxy like the web UI, and set `GRAFANA_ROOT_URL` to the address people use. Prometheus is
  never published; it and the metrics port sit on an internal network. Grafana has no anonymous access, no
  sign-up and no telemetry or update checks.
- **The admin password** only sets Grafana's first admin: change it afterwards inside Grafana, not in the
  file.
- **Rotating the database password.** Replace `secrets/grafana_db_password`, then
  `sudo docker compose up -d --force-recreate monitoring-setup grafana`.
- **Dashboards and data sources are regenerated at every start** from the Steerhouse release you run, so
  upgrading updates them. They are read-only in Grafana: save changes as a copy.
- **Data.** Prometheus keeps 30 days (`PROMETHEUS_RETENTION`). The volumes `prometheus-data` and
  `grafana-data` hold it and Grafana's own users and settings; the rest is rebuilt.
- **Alerts.** Four example rules (failure ratio, sign-in failures, notification backlog, metrics missing) are in
  [grafana/provisioning/alerting](../grafana/provisioning/alerting/steerhouse.example.yaml); add contact points
  in Grafana first.
- **Turning it off.** Remove `COMPOSE_PROFILES` and `METRICS_TOKEN`/`METRICS_HOST` from `.env` and run
  `sudo docker compose up -d --remove-orphans`. The role `grafana_ro` stays in the database until you drop it
  (`python -m app.cli analytics-revoke grafana_ro`, then `DROP ROLE grafana_ro`).

## Uninstalling

```sh
cd /opt/steerhouse
sudo docker compose down        # stops and removes the containers; data stays in the volumes
sudo docker compose down -v     # also deletes the database and run history: this can't be undone
sudo docker image rm honeybeartech/steerhouse-backend:0.11.0 honeybeartech/steerhouse-frontend:0.11.0
```

With monitoring on, run these with `--profile monitoring` (or `COMPOSE_PROFILES` set, as in step 7), or the
Prometheus and Grafana containers and volumes stay behind.

Then delete `/opt/steerhouse`, including `secrets/` (or keep `credential_encryption_key` with your backups
if you might restore one).
