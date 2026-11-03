# IToolbox user guide

How to open IToolbox and BantAI from anywhere, through Tailscale.

IToolbox runs on one laptop, the host. Nothing on it is open to the public
internet. You reach it through Tailscale, a free private-network app, after the
admin shares the host with you. Once that's done, the links below work from any
internet connection: home, office or mobile data.

| What | Link | Who it's for |
| --- | --- | --- |
| **IToolbox and BantAI**, the web app | <https://itoolbox.taildc9975.ts.net> | Everyone |
| The API reference | <https://itoolbox.taildc9975.ts.net:8100/docs> | Developers |
| Zetaris, where BantAI's data sources are registered | <https://itoolbox.taildc9975.ts.net:3001> | People with a Zetaris account from the admin |

The links only work while Tailscale is connected on your device and the host is
switched on.

## 1. Get access (once)

1. **Ask the admin for an IToolbox account and a Tailscale invite.** The account
   is your email and a first password. The invite comes by email or as a link.
2. **Install Tailscale** from <https://tailscale.com/download> on each device you'll
   use: Windows, macOS, iPhone or iPad, Android or Linux.
3. **Open the invite and accept it.** Sign in to Tailscale with any account:
   GitHub, Google, Microsoft or Apple. If it's your first time, Tailscale creates
   your own free tailnet (your private network). Then select **Accept**.
   - Accept with a personal account. A work account where you're only a member of
     your company's tailnet can't accept invites.
   - An invite link works once and expires after 30 days. If yours fails, ask the
     admin for a new one.
4. **Connect.** Sign in to the Tailscale app on your device with the same account
   and check that it says **Connected**. The host shows up in its list of devices
   as `itoolbox`.

## 2. Sign in to IToolbox

1. Open <https://itoolbox.taildc9975.ts.net> and bookmark it.
2. Sign in with your email and the first password from the admin. IToolbox opens
   your **Account Profile**.
3. **Change your password** there, under **Change Password**. Use at least 10
   characters. Later, the profile is on the dashboard, or at
   <https://itoolbox.taildc9975.ts.net/account>.

On a phone, Tailscale runs in the background as a VPN. Keep it connected while
you use IToolbox.

## 3. Use BantAI

- **Ask a question.** Open **BantAI** from the dashboard and ask in English or
  Filipino, for example "Which areas had the highest wind signal in the latest
  bulletin?"
- **See why.** BantAI shows each step as it works: every query it runs through
  Zetaris and the rows that came back. The answer cites them as E1, E2 and so on.
  Open one to see its exact SQL and rows.
- **Wait for it.** An answer usually takes under a minute. Keep the page open
  until it's done.
- **Pick a model.** Keep the default, **NVIDIA Nemotron**. **Nemotron via
  Meterless** works while the admin has Meterless running on the host. GPT, Grok
  and Claude need an API key or credits the team doesn't have yet.
- **Find past questions** on the dashboard. A BantAI link ending in `?id=...`
  replays an investigation exactly as it ran; anyone with an account can open it.
- **Browse the data.** **Data Sources**, under BantAI Strategic Intelligence,
  lists every source and table BantAI can query.
- BantAI supports decisions. For life-safety calls, follow PAGASA, NDRRMC and your
  local government.

## For developers

- **The API reference** is at <https://itoolbox.taildc9975.ts.net:8100/docs>. To try
  a route there: run `POST /api/v1/auth/login` with your email and password, copy
  `access_token` from the response, select **Authorize** and paste it.
- **The frontend dev server** can use the host's API. In `itoolbox-frontend`:

  ```bash
  NEXT_PUBLIC_API_URL=https://itoolbox.taildc9975.ts.net:8100 npm run dev
  ```

## If something doesn't work

| What you see | What to do |
| --- | --- |
| The page never loads, or "This site can't be reached" | Open Tailscale and check that it says Connected, with the account you accepted the invite with. If it does, the host may be off or asleep: tell the admin. |
| The link doesn't open, but other sites do | Use the full link ending in `.ts.net`; the short name `itoolbox` alone doesn't work outside the admin's network. In Tailscale's settings, keep **Use Tailscale DNS settings** on. |
| Nothing loads while a work VPN is on | Some VPNs block Tailscale. Disconnect the other VPN and try again. |
| "Invalid credentials" | Check your email. Passwords are case-sensitive. If you've forgotten yours, ask the admin to set a new one. |
| "Account disabled" | Ask the admin. |
| An answer stops with a model error | Pick **NVIDIA Nemotron** and ask again. |
| Zetaris rejects your sign-in | Zetaris accounts are separate from IToolbox accounts. Ask the admin for one. |

## Keep it safe

- Don't share your password, or forward your invite: an invite link works for
  whoever opens it first.
- Sign out on computers other people use.
- BantAI's data is public, but IToolbox itself is for the team only. Ask the admin
  before you show it to anyone outside the team.
