# IToolbox admin guide

How the host serves IToolbox through Tailscale, how to give someone access and
take it away, and what to check when something breaks. Send teammates the
[user guide](USER_GUIDE.md); this page is for whoever runs the host.

## How it fits together

IToolbox runs on one Windows laptop, the host, in Docker. Every container port
binds to `127.0.0.1`, so nothing listens on the LAN. Tailscale Serve publishes
four of them on the host's Tailscale name over HTTPS, with a real certificate.
They're reachable only from your own devices and by people you share the host
with. Nothing is on the public internet.

| Link | What it is | Port on the host | Who can open it |
| --- | --- | --- | --- |
| <https://itoolbox.taildc9975.ts.net> | IToolbox web app, with BantAI | 3100 | You, and people you share the host with |
| <https://itoolbox.taildc9975.ts.net:8100> | BantAI API; `/docs` is its reference. The web app calls it from the browser | 8100 | You, and people you share the host with |
| <https://itoolbox.taildc9975.ts.net:3001> | Zetaris UI | 3001 | You, and shared users who have a Zetaris account |
| <https://itoolbox.taildc9975.ts.net:8890> | JupyterLab | 8890 | Your own devices only |

The rest stays on the host, used only by its own containers: the databases (5435,
5436), the Zetaris API (8888, 8889) and query engine (10000), BagyoAPI (3200) and
Meterless Nightshift (8088).

The admin console is <https://login.tailscale.com/admin>. Run the commands below in
PowerShell on the host.

## Before you share the host with anyone

Do these once.

1. **Set the access policy.** Tailscale's default policy lets everyone reach every
   port, and that includes the people you share the host with. This laptop also
   runs other Docker projects that publish ports on all of its network interfaces,
   Tailscale's included, so with the default policy a shared user could reach
   them. Open **Access controls**
   (<https://login.tailscale.com/admin/acls/file>), switch to the JSON editor,
   replace the whole file with the policy below and select **Save**.

   ```jsonc
   {
     "grants": [
       // Your own devices (the host, your Mac, your phone) reach each other on every port.
       {"src": ["autogroup:member"], "dst": ["autogroup:self"], "ip": ["*"]},
       // People the host is shared with reach the web app, the API and Zetaris. Nothing else.
       // 100.71.62.14 is the host's Tailscale address (`tailscale ip -4`).
       {"src": ["autogroup:shared"], "dst": ["100.71.62.14"], "ip": ["tcp:443", "tcp:8100", "tcp:3001"]},
     ],
     "ssh": [
       {
         "action": "check",
         "src": ["autogroup:member"],
         "dst": ["autogroup:self"],
         "users": ["autogroup:nonroot", "root"],
       },
     ],
   }
   ```

   If you ever remove the host from Tailscale and add it back, it gets a new
   address: put that one in the policy.
2. **Turn off key expiry for the host.** **Machines**
   (<https://login.tailscale.com/admin/machines>) → `itoolbox` → **⋯** → **Disable
   key expiry**. Otherwise the host drops off Tailscale every 180 days until you
   sign in again.

## Give someone access

1. **Create their IToolbox account.** Sign in to IToolbox as an admin, open
   **Security Settings** and select **+ Add User**. Enter their full name, email, a
   first password of at least 10 characters and a role, then select **Create
   User**. Teammates get **Analyst**.

   | Role | Can |
   | --- | --- |
   | Viewer | Ask BantAI and read their own investigations |
   | Analyst | Ask BantAI and run read-only SQL through the data harness |
   | Admin | Manage users and model checks; see everyone's investigations |
   | Super Admin | Everything, including making other admins |

2. **Share the host with them.** **Machines** → `itoolbox` → **⋯** → **Share**.
   Either enter their email under **Share by email**, or use **Copy invite link**
   and send it yourself. Leave **Reusable link** off: a single-use link works once
   and expires after 30 days, and whoever has it can accept it. Shared users can
   reach only this machine, and only on the ports the policy allows. They don't
   count toward the free plan's 6 users.
3. **Send them their email, first password and the
   [user guide](https://github.com/IToolboxPH/itoolbox-backend/blob/main/docs/USER_GUIDE.md).**
   Send the password on its own, privately, not in a group chat.
4. **Zetaris, only if they need it.** BantAI already shows the SQL and rows behind
   every answer, and its **Data Sources** page lists every table, so most people
   don't. To add someone, sign in to Zetaris as an admin, open **Management →
   Users** and select **+**. Zetaris accounts are separate from IToolbox accounts.

Don't invite teammates into your tailnet as members. Members count toward the
user limit, and under this policy they reach only their own devices anyway.

## Take access away

When someone leaves the team, do both:

- **Tailscale:** **Machines** → `itoolbox` → **⋯** → **Share**, then revoke their
  access. Revoking a pending invite works the same way.
- **IToolbox:** **Security Settings** → their row → **Deactivate**. They can no
  longer sign in. Their past investigations stay.

In Zetaris, **Management → Users** → the row's **⋮** → **Delete** removes their
account.

## Forgotten passwords

**IToolbox** has no reset button yet. On the host, run:

```powershell
docker exec -it itoolbox-api python reset_password.py
```

It asks for the email and the new password twice. The password isn't shown while
you type. Send it to them privately; they change it in **Account Profile**.

**Zetaris:** **Management → Users** → the row's **⋮** → **Edit** → **Reset
password**.

## JupyterLab (your own devices only)

Open <https://itoolbox.taildc9975.ts.net:8890>. It asks for a token, which changes
whenever the container restarts. Get the current one with:

```powershell
docker exec itoolbox-jupyter jupyter server list
```

Paste the part after `?token=`. For a token that doesn't change, set
`JUPYTER_TOKEN` in `itoolbox-data-platform\.env` and run
`docker compose up -d itoolbox-jupyter` in that folder. JupyterLab includes a
terminal with the data platform's database credentials, which is why the policy
doesn't give shared users its port.

## Keep the host running

The links work only while the host is on, signed in and connected.

- **Power.** Keep it plugged in. Windows' sleep setting while plugged in is
  already **Never**; keep it that way. If you close the lid, set **Control Panel →
  Power Options → Choose what closing the lid does → Plugged in** to **Do
  nothing**.
- **Stay signed in to Windows.** Docker Desktop and Meterless Nightshift run in
  your session. Lock the screen with **Win + L** instead of signing out.
- **After a restart**, sign in. Docker Desktop starts at sign-in and brings the
  containers back (they're set to `restart: unless-stopped`); Tailscale runs as a
  Windows service and keeps its Serve settings. Open Meterless Nightshift if you
  want the **Nemotron via Meterless** model.

## Check that it's working

```powershell
tailscale status          # the first line is this host, itoolbox
tailscale serve status    # four https:// links, each "(tailnet only)"
docker ps --format "table {{.Names}}\t{{.Status}}"   # itoolbox-*, zetaris-*, bagyo-*: Up
curl.exe -s https://itoolbox.taildc9975.ts.net:8100/api/v1/health
```

Then open <https://itoolbox.taildc9975.ts.net> on your phone, on mobile data with
Tailscale on. If it loads there, it loads for the team.

If PowerShell doesn't know `tailscale`, open a new window, or use
`& "C:\Program Files\Tailscale\tailscale.exe"` in its place.

## When something breaks

| What you see | Likely cause and fix |
| --- | --- |
| Nobody can open the links | The host is asleep, off or signed out, or Docker isn't running. Check `tailscale status` and `docker ps`. |
| One person can't open them | Their Tailscale isn't connected, or uses a different account from the one that accepted the invite. Check **Share** on the `itoolbox` machine for them. |
| The web app opens but sign-in fails with a network error | The API isn't answering. Check the health link above, `tailscale serve status` (port 8100) and `docker ps` (`itoolbox-api`). |
| Every link returns 404 | The host's Tailscale name changed. Serve's settings are tied to the name: run the Serve commands under [Setup](#setup-for-reference) again. |
| A certificate warning | HTTPS certificates were turned off on the DNS page, or someone opened an address other than `itoolbox.taildc9975.ts.net`. |
| Zetaris: `crypto.randomUUID is not a function` | It was opened over `http://`. Use the `https://` link. |
| Zetaris signs in at localhost but not through Tailscale | `ALLOWED_ORIGINS` in `itoolbox-zetaris-platform\.env` lacks the Tailscale address. See [Setup](#setup-for-reference). |
| `tailscale serve` prints a link and waits | HTTPS certificates are off. Open the link, or turn them on from the DNS page. |
| Answers fail on **Nemotron via Meterless** | Meterless Nightshift isn't open on the host. |

## Setup, for reference

This is how the host was set up on 3 November 2026. Repeat it on a new host.

1. **Machine name.** `tailscale set --hostname=itoolbox` names the host in
   Tailscale; Windows keeps its own computer name. Choose the name before step 2:
   each certificate publishes it.
2. **HTTPS certificates.** **DNS** (<https://login.tailscale.com/admin/dns>) →
   **HTTPS Certificates** → **Enable HTTPS**, with MagicDNS on. Tailscale gets the
   certificates from Let's Encrypt and renews them itself. Like every public
   certificate, they're listed in public certificate-transparency logs, so
   `itoolbox.taildc9975.ts.net` is public. What it serves isn't.
3. **Serve.**

   ```powershell
   tailscale serve reset
   tailscale serve --bg --https=443  http://127.0.0.1:3100   # IToolbox web app
   tailscale serve --bg --https=8100 http://127.0.0.1:8100   # BantAI API
   tailscale serve --bg --https=3001 http://127.0.0.1:3001   # Zetaris UI
   tailscale serve --bg --https=8890 http://127.0.0.1:8890   # JupyterLab
   ```

   `--bg` keeps each one across restarts. `tailscale serve --https=8890 off` takes
   one down; `tailscale serve reset` takes them all down.
4. **Zetaris's allowed origins.** In `itoolbox-zetaris-platform\.env`,
   `ALLOWED_ORIGINS` lists every address the browser opens Zetaris at, separated by
   semicolons:

   ```text
   ALLOWED_ORIGINS=http://localhost:3001;https://itoolbox.taildc9975.ts.net:3001
   ```

   Then run `docker compose up -d api` in that folder.
5. **The web app** needs no setting. It calls the API at the scheme and host it
   was opened at, on port 8100, so one build works at `http://localhost:3100` and
   at the Tailscale link.
6. **The API** accepts calls from any web address while `PLATFORM_ENV=local`. If
   you change that, add `https://itoolbox.taildc9975.ts.net` to `ALLOWED_ORIGINS` in
   `itoolbox-backend\.env`.
7. **The access policy and key expiry**, as in
   [Before you share the host](#before-you-share-the-host-with-anyone).

To publish another service, add a `tailscale serve --bg --https=<port>` line,
add its port to the shared users' grant only if teammates need it, and add a row
to the table at the top.

## Keep it safe

- **Stay private.** Never run `tailscale funnel`: it would put the sign-in pages
  on the public internet.
- **Share, don't invite.** The policy limits shared users to the three ports
  above. Prefer single-use invite links, and revoke access when someone leaves.
- **Keep secrets out of chat and Git.** Keys and passwords live in each repo's
  `.env`, which Git ignores. Send first passwords privately, then delete
  `C:\IToolbox\initial-passwords.txt`.
- **JupyterLab is admin only.** It holds a terminal with database credentials.
