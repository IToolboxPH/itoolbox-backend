# BantAI: submission texts

Two submissions, same build. The Zetaris Demo Challenge comes first: it closes
sooner.

| | Zetaris Demo Challenge | Open Agent Hackathon 2026 |
| --- | --- | --- |
| **Deadline** | **Mon 2 Nov 2026, 23:45 UTC** (Tue 3 Nov, 7:45 AM PHT) per the [official rules](https://www.zetaris.com/zetaris-demo-challenge-official-rules); the announcement says 3 Nov, so aim for the earlier | 27 Oct 2026, passed; we are asking the organisers whether they accept a late entry |
| **Where** | Upload the video to the organisers' Dropbox (link in the official rules) | [hackathon.genai.works/submissions](https://hackathon.genai.works/submissions) |
| **Video** | `C:\IToolbox\videos\IToolbox_011126.mp4` (Zetaris live, with the 40–60 s "why it was amazing" segment) | `C:\IToolbox\videos\BantAI_OpenAgentHackathon2026_demo.mp4` (under 4 minutes) |

## Before you submit

1. **GitHub link.** All four repos are private, so judges can't open them. Making one
   public as it is would also publish its history, which still names the PLDT tables
   we started with. The safe route is a new public repo, `IToolboxPH/bantai`, holding
   a clean snapshot of the four repos in one commit:
   - no history;
   - no `.env` files;
   - none of Zetaris's licensed bundle files, such as its JDBC driver and images.
2. **Meterless.** The hackathon rules ask for Zetaris *and* Meterless. BantAI's
   Meterless route is built, but it only runs once Nightshift is installed on the
   laptop and its runtime token is in `itoolbox-backend/.env`. The steps are in the
   README.
3. **The narration is synthetic** (Kokoro text-to-speech). The Zetaris challenge
   scores "How it helped you" at 15 points, so consider recording the 40–60 s "why"
   segment in your own voice, over the same slides. Its script is below.
4. **File name.** The Zetaris rules want `TEAM-NAME_DDMMYY` with the upload date.
   Rename `IToolbox_011126.mp4` if you upload on another day.

---

## Open Agent Hackathon 2026

**Track:** The Agent That Can Explain Why

**Team Name:** IToolbox

**Description** (1,755 characters; the form allows 150 to 2,000. Paste the four paragraphs without the `>` marks):

> BantAI (from bantay, Filipino for "guard") is IToolbox's AI assistant for Philippine teams who must act when a typhoon threatens. About 20 tropical cyclones enter Philippine waters every year, and the answers a team needs are scattered: PAGASA bulletins, Project NOAH hazard maps, PSA population figures and 75 years of storm history. BantAI answers in English or Filipino, and it explains why: every claim cites the exact query and rows behind it.
>
> Public data lands in our local data platform and is governed there, one schema per source. The Zetaris AI Data Harness registers five data sources (WEATHER, BULLETINS, HAZARDS, TYPHOONS, REFERENCE; 21 tables) and federates read-only Spark SQL across them. The agent, on NVIDIA Nemotron, never opens a database connection: it discovers the sources, writes each query with a stated purpose, runs it through Zetaris and turns each result into numbered evidence (E1, E2…). A guard lets only a single SELECT reach Zetaris, which reads through a read-only role.
>
> Asked which areas had the highest wind signal in Typhoon Inday's latest bulletin, BantAI noticed the final bulletin carried no signals, went back to the last one that did, and joined the signals to PSA population; when Zetaris rejected one query, it read the error and fixed it. Asked how exposed Tacloban is, it combined NOAH storm-surge zones, 346 storm passes since 1951 and Haiyan's 35 km pass.
>
> Sources: OpenWeather and NASA POWER weather, PAGASA bulletins via a self-hosted BagyoAPI, USGS earthquakes, GDACS alerts, Project NOAH hazard maps, IBTrACS storm tracks, PSA population and OpenStreetMap facilities, all public and refreshed on schedules. BantAI supports decisions and defers life-safety calls to PAGASA, NDRRMC and local government.

**Sponsor technology explanation:**

> **NVIDIA.** BantAI's default model is NVIDIA Nemotron (nemotron-3.5-super-vl-120b-a12b on build.nvidia.com, OpenAI-compatible API). Nemotron runs the agent loop: it plans the investigation, calls four tools (list sources, list tables, describe a table, run SQL), writes Spark SQL with a stated purpose, reads the rows, and writes an answer in which every number cites its query. In testing it answered cross-source questions with 6 queries in 39 s, and recovered from a failed query without help.
>
> **Zetaris.** The Zetaris AI Data Harness is the only way BantAI reaches data. We run the Zetaris bundle locally in Docker and registered five data sources over governed TimescaleDB schemas through a read-only role. Our backend calls the Zetaris REST API (start, page, close) with the agent's own API key, behind a single-SELECT guard. What is unique: every Zetaris query becomes a citation the user can open with its SQL and rows; one federated query joins PAGASA wind signals to PSA population and NOAH hazard; and when we replaced our first data sources, the agent did not change, only the sources registered in Zetaris did.
>
> **Meterless.** BantAI has a model route through Meterless Nightshift: the backend calls Nightshift's local OpenAI-compatible endpoint with its runtime token and `meterless-app: bantai` headers, so Nemotron calls are routed and receipted by Nightshift, which holds the NVIDIA key. *(Before submitting: install Nightshift and set the token so this route is live, or say that it is built but not yet enabled.)*
>
> **SpaceX AI.** Grok is integrated through the xAI API as a selectable model in the same picker and agent loop as Nemotron, Claude and GPT. *(It needs API credits on the xAI team account to run.)*

**Video:** upload `BantAI_OpenAgentHackathon2026_demo.mp4`, or an unlisted YouTube link to it.

**Github Solution:** the public repo from step 1 above, once created (for example `https://github.com/IToolboxPH/bantai`).

---

## Zetaris Demo Challenge

**What to upload:** `IToolbox_011126.mp4`, renamed to the upload date, and the one-sentence write-up below (the rules don't say where it goes, so put it in a text file with the same name next to the video; it is also on the video's end card).

**In one sentence, why did you think it was amazing?**

> Zetaris let our agent query five public sources in place with one SQL dialect, so every answer BantAI gives comes with the exact query and rows behind it.

**The "why it was amazing" segment** (about 46 s as narrated; to record in your own voice):

> Why we thought Zetaris was amazing. First, it let us query in place. We registered five public sources with one statement each, and our agent joined PAGASA bulletins to population and hazard maps in a single Spark SQL query, in seconds, without building a warehouse. Second, it made our agent explainable: every query goes through Zetaris's API, so each one becomes a citation the user can open, with the exact SQL and rows. Third, governance came built in: a read-only role, an API key for the agent, and a query endpoint that accepts SELECT only. It all runs on a laptop, so our data stays governed locally. When we replaced our first data sources, the agent didn't change at all. Only the sources in Zetaris did.

**How the video covers the judging criteria** (100 points):

| Criterion | Points | In the video |
| --- | --- | --- |
| Meaningful use of Zetaris, central and live | 25 | Zetaris's Data Explorer with the five sources; a live federated query in the SQL Workspace; BantAI's live run, every query through Zetaris; the agent's API key "last used" moments later |
| How it helped you | 15 | The three "why" points, each a moment from our build |
| Problem and impact | 15 | Typhoon decisions in the Philippines; the opening problem slide |
| Technical execution | 15 | Live runs on real data; self-correction on a failed query; the architecture slide |
| Working with SpaceXSI's coding agents | 15 | Not used: BantAI was built with Claude Code. The criterion stays honest as is |
| Creativity and originality | 10 | Evidence ids that link each claim to its Zetaris query |
| Video quality and storytelling | 5 | 1080p, captions, about three minutes |

Every person in the video must consent; there are none on screen, and the narration is synthetic. All data is public.
