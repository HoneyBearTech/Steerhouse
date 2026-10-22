![Steerhouse](https://raw.githubusercontent.com/HoneyBearTech/Steerhouse/main/docs/images/steerhouse-banner-light.svg)

Self-hosted web UI for running Ansible playbooks against target systems, packaged in Docker.

**Source, documentation and issues: [github.com/HoneyBearTech/Steerhouse](https://github.com/HoneyBearTech/Steerhouse)**

> **Runs change real systems**: every run executes `ansible-playbook` on the hosts you pick, and what it
> changes stays changed, even if you cancel it. Start with check mode and a narrow limit. **Deletes are
> permanent**: Steerhouse asks first, but there is no undo.

## The images

Steerhouse is two images, released together with the same version:

| Image | What it runs |
| --- | --- |
| [`honeybeartech/steerhouse-backend`](https://hub.docker.com/r/honeybeartech/steerhouse-backend) | the API and the workers that run playbooks |
| [`honeybeartech/steerhouse-frontend`](https://hub.docker.com/r/honeybeartech/steerhouse-frontend) | the web UI, served by nginx |

Tags: `X.Y.Z` for each release, `X.Y` for the latest patch of a minor version, and `latest`. The same images
are mirrored to `ghcr.io/honeybeartech/steerhouse-backend` and `ghcr.io/honeybeartech/steerhouse-frontend`.

## Running it

Steerhouse runs from the release's compose file, with Postgres, secrets as files and the workers isolated.
Follow [installing a release](https://github.com/HoneyBearTech/Steerhouse/blob/main/docs/installing.md): it
needs a Linux host with Docker Engine 26 or later and Docker Compose v2, and a reverse proxy that serves
Steerhouse over HTTPS. Don't run the images on their own or expose them directly to the internet.

## Verifying a release

Every image is scanned for fixable HIGH and CRITICAL vulnerabilities before it's published, and comes with an
SBOM and SLSA provenance. Each one is signed keylessly with cosign by the release workflow:

```sh
for image in steerhouse-backend steerhouse-frontend; do
  cosign verify "docker.io/honeybeartech/${image}:latest" \
    --certificate-identity-regexp '^https://github\.com/HoneyBearTech/Steerhouse/\.github/workflows/docker-publish\.yml@refs/tags/v' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com
done
```

[Verifying releases](https://github.com/HoneyBearTech/Steerhouse/blob/main/docs/verifying-releases.md) covers
digests, the SBOM, the provenance and the signed release files.

## Links

- [Changelog](https://github.com/HoneyBearTech/Steerhouse/blob/main/CHANGELOG.md) and
  [upgrading](https://github.com/HoneyBearTech/Steerhouse/blob/main/docs/upgrading.md)
- [User guide](https://github.com/HoneyBearTech/Steerhouse/blob/main/docs/user-guide/README.md)
- [Security policy](https://github.com/HoneyBearTech/Steerhouse/blob/main/SECURITY.md): report vulnerabilities
  privately, not in issues
- License: [MIT](https://github.com/HoneyBearTech/Steerhouse/blob/main/LICENSE)
