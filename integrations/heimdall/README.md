# Steerhouse for Heimdall

An enhanced app for the [Heimdall](https://heimdall.site/) dashboard: a Steerhouse tile that shows a
project's live run counts.

| Tile | Shows |
| --- | --- |
| **Run** | runs in progress |
| **Queue** | runs waiting for a worker |
| **Failed** | runs that failed or timed out in the last 24 hours |

(The labels are short because a Heimdall tile has room for about 15 letters across its stats.)

The tile refreshes every 5 seconds while runs are queued or running, and every 30 seconds otherwise. It
reads [`GET /api/stats`](../../docs/interfaces.md#run-counts) with an API key, which needs a Steerhouse
release that has that endpoint (see the [changelog](../../CHANGELOG.md)).

`Steerhouse/` is laid out exactly as [linuxserver/Heimdall-Apps](https://github.com/linuxserver/Heimdall-Apps)
expects, so the same folder can be installed by hand or submitted there.

## Set it up

1. In Steerhouse, under **Projects → API keys**, create a key with the **stats** preset (for example named
   `heimdall`). It can read run counts and nothing else. Heimdall keeps it in plain text in its own database,
   so don't use a `trigger` or `read-only` key here. Under **Limits**, allow only the address Heimdall calls
   from. The [user guide](../../docs/user-guide/projects-and-users.md#a-key-for-a-dashboard-heimdall) has the
   details.
2. In Heimdall, add an application, pick **Steerhouse**, and set its URL to your Steerhouse address (for
   example `https://steerhouse.example.com`).
3. Under **Config**, turn it on and paste the key into **API key**. If Heimdall should call another address
   than the tile links to (for example the internal one), put it in the URL field there. Turn on **Skip TLS
   verification** only for a certificate Heimdall can't check, such as a self-signed one on your own
   network.
4. **Test** should say *Successfully communicated with the API*. *Invalid credentials* means the key is
   wrong, expired, revoked or limited to other addresses. *Something went wrong... Code: 400* means
   Steerhouse refused the host name Heimdall used: add that name to `ALLOWED_HOSTS` (see
   [`.env.example`](../../.env.example)).

Each tile shows one project, the key's. For several projects, add a tile per project, each with its own key.

## Install it by hand

Until Steerhouse is in Heimdall's app list, or to try a newer version, install the folder yourself. In the
[linuxserver/heimdall](https://docs.linuxserver.io/images/docker-heimdall/) image, with `/config` mounted
from the host:

1. Copy the folder into Heimdall's apps:

   ```bash
   cp -r integrations/heimdall/Steerhouse /path/to/heimdall/config/www/SupportedApps/
   ```

2. Register it. On a Heimdall release newer than 2.8.3:

   ```bash
   docker exec heimdall php /app/www/artisan register:app Steerhouse
   ```

   Heimdall 2.8.3 has that command but doesn't load it (linuxserver/Heimdall#1606, fixed on its main branch), so
   there, run it like this:

   ```bash
   docker exec -i heimdall sh -c 'cd /app/www && php' <<'EOF'
   <?php
   require 'vendor/autoload.php';
   $app = require 'bootstrap/app.php';
   $kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
   $kernel->bootstrap();
   $kernel->registerCommand(new App\Console\Commands\RegisterApp());
   $kernel->call('register:app', ['folder' => 'Steerhouse']);
   echo $kernel->output();
   EOF
   ```

   Either way it answers *Application Added - Steerhouse*.

3. Restart Heimdall. Restart after every later change to the files too: the image caches PHP code until it
   restarts.

   ```bash
   docker restart heimdall
   ```

4. Add the tile as above. Heimdall 2.8.3 won't save a hand-installed app's icon: it fetches the icon from its
   own address, which its private-address guard refuses ("Icon URL is not allowed"), and it refuses SVG
   uploads. Click **Upload an icon** and choose a PNG of the mark, such as
   [`frontend/public/icon-192.png`](../../frontend/public/icon-192.png), before saving. Apps from the official
   list don't have this problem.

Once Steerhouse is in the official app list, Heimdall replaces this copy with the published one when it updates
its apps.

## Checks

CI checks the package the way Heimdall-Apps checks a submission:

- `python3 integrations/heimdall/check_package.py`: the folder, class and namespace names, `app.json`'s
  fields and order, the `appid` (the SHA-1 of the name's slug), the enhanced files, and the icon.
- PHP 8.2 `php -l` and PHPCS with PSR-12 (the blade files excepted).

## Submitting it to Heimdall-Apps

1. Wait for a Steerhouse release with `GET /api/stats`, so the tile works for everyone who installs it.
2. Check that this folder is current and that CI's **Heimdall app package** job passed on `main`.
3. Fork [linuxserver/Heimdall-Apps](https://github.com/linuxserver/Heimdall-Apps) and create a branch, for
   example `add-steerhouse`.
4. Copy `integrations/heimdall/Steerhouse/` to the fork's top level as `Steerhouse/`, unchanged.
5. In the fork, run its checks: `node testRunner.js` and `node --test "scripts/tests/*.test.js"`
   (Node 22 or later). Both must pass.
6. Try the tile once more against a real Steerhouse, and take a screenshot of it.
7. Open a pull request titled **Add Steerhouse (enhanced)**, with a description like this:

   ```text
   Adds Steerhouse (https://github.com/HoneyBearTech/Steerhouse), a self-hosted web UI and API for
   running Ansible playbooks, as an enhanced app.

   - Endpoint: GET /api/stats, documented in Steerhouse's docs/interfaces.md. It returns counts only:
     queued, running, succeeded_24h, failed_24h, workers_online.
   - Auth: Authorization: Bearer <API key>. Steerhouse has a "stats" key preset that can read these
     counts and nothing else; the config field is a password input.
   - Tile: Run / Queue / Failed (failed and timed-out runs in the last 24 hours). Status is "active"
     while runs are queued or running (5 s refresh), otherwise 30 s.
   - Optional "Skip TLS verification" toggle, as in Tracearr.

   Test plan: tested against a self-hosted Steerhouse in linuxserver/heimdall. Test says "Successfully
   communicated with the API" with a valid key and "Failed: Invalid credentials" with a wrong one; the
   tile's numbers match the API, it is active while a run is in progress and inactive otherwise, and a
   revoked key leaves it at zero without errors. testRunner, the unit tests, php -l (8.2) and PHPCS
   PSR-12 pass.
   ```

8. Answer the review. If the maintainers change the files, bring the same changes back into this folder.

After the merge, Heimdall installations pick up the app from the published list. Later changes go the same
way: change this folder first, then send the same change upstream.
