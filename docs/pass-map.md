# Pass map

A short record of each piece of maintenance work: when it happened, what shipped, and where.

| Date | Job | What shipped | PR |
| --- | --- | --- | --- |
| 2026-11-20 | renovate-migrate | Dependency updates moved from Dependabot to Renovate (`renovate.json`; `.github/dependabot.yml` removed). Patch and minor updates of Python packages, npm packages and GitHub Actions merge by themselves after the required checks pass and a 3-day release age. Container images, majors and the uv group wait for the maintainer. Docs updated. | [#59](https://github.com/HoneyBearTech/Steerhouse/pull/59) |
| 2026-11-20 | fix-audit-deps | Three backend dependencies with known vulnerabilities updated in `backend/uv.lock` (dnspython 2.9.2, filelock 4.2.12, pyasn1 0.6.5), so the backend dependency audit passes again. | [#60](https://github.com/HoneyBearTech/Steerhouse/pull/60) |
