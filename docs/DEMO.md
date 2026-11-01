# Recording the BantAI × Zetaris demo

**The story in one line:** BantAI answers a typhoon question by querying five public
data sources in place through the Zetaris AI Data Harness, and shows the SQL and the
rows behind every claim.

## How it fits together

```text
PAGASA bulletins ── BagyoAPI ──┐
OpenWeather · NASA POWER ──────┤                                   ┌──────────────────────────┐
USGS · GDACS · Project NOAH ───┼─► itoolbox-data-platform ─────────► Zetaris AI Data Harness  │
IBTrACS ───────────────────────┤   TimescaleDB on this laptop,      │ 5 data sources, Spark SQL│
PSGC · PSA · OpenStreetMap ────┘   one governed schema per source   │ read-only role, API key  │
                                                                     └────────────┬─────────────┘
                                                                                  │ SELECT only
                                     web app ◄── itoolbox-backend: BantAI agent ◄─┘
                                     :3100       NVIDIA Nemotron, SQL guard, evidence ids
```

| Zetaris source | What BantAI reads there |
| --- | --- |
| `WEATHER` | Current weather, forecasts and air quality for 24 cities (OpenWeather), daily history since 1991 (NASA POWER) |
| `BULLETINS` | PAGASA tropical cyclone bulletins and wind signals (self-hosted BagyoAPI) |
| `HAZARDS` | USGS earthquakes, GDACS alerts, Project NOAH flood, landslide and storm surge around each city |
| `TYPHOONS` | IBTrACS: every storm inside PAR since 1951, and each city's closest passes |
| `REFERENCE` | PSGC places, PSA province population, OpenStreetMap facilities near each city |

**What Zetaris does here:**
- BantAI never opens a database connection. Every question becomes read-only Spark SQL sent to Zetaris's API, and Zetaris runs it against the registered sources where they live.
- Zetaris reads the sources as `zetaris_ro`, which can `SELECT` from the registered schemas and nothing else.
- The agent authenticates to Zetaris with its own API key.
- Adding another system, such as a client's branch database, is one `CREATE DATASOURCE`. Nothing is copied into a warehouse first.

## Before you record

1. **Zetaris is healthy.** In `itoolbox-zetaris-platform`, `./verify.sh` should report 9/9.
2. **The data is fresh.**
   ```bash
   cd itoolbox-data-platform
   docker compose exec itoolbox-ingest python /workspace/scripts/run_ingest.py --status
   ```
   Every job should show a recent "last ok".
3. **The model answers.** `GET /api/v1/agent/models/nemotron/check` (admin) should return `ok: true`.
4. **Warm it up.** After an idle spell, Nemotron's first answer can take about a minute. Ask one question before you start recording.
5. **Have a fallback.** Every run is saved. `/bantai?id=<id>` replays a run step by step, which makes a smooth take if a live run is slow.

## Questions that work (tested 1 November 2026, Nemotron)

| Question | Sources it joins | Time · queries | Replay |
| --- | --- | --- | --- |
| In Typhoon Inday's latest bulletin, which areas had the highest wind signal, and how many people live in those provinces? | BULLETINS, REFERENCE | 39 s · 6 | `/bantai?id=401a43a9-d131-488b-8a28-fb4a5e157427` |
| How exposed is Tacloban to typhoons and storm surge, and how often has it been hit? | WEATHER, REFERENCE, HAZARDS, TYPHOONS | 23 s · 7 | `/bantai?id=ddbcbf62-6cd8-4416-adc4-249dd3bb14e2` |
| Which cities should prepare for heavy rain in the next 48 hours, and why? | WEATHER | 94 s · 2 | (ask live: the forecast changes hourly) |

Both of the first two show what Track 02 rewards. In the Inday run, BantAI found that the final bulletin carried no signals and went back to the last one that did. In the Tacloban run, one query failed and BantAI corrected itself, which shows in the trail.

## Script (about 3½ minutes)

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:20 | The landing page, then the BantAI chat | About 20 storms a year enter PAR. When one comes, the answers sit in many places: PAGASA bulletins, NOAH hazard maps, population figures, decades of storm history. BantAI asks them all at once, through Zetaris, and shows its evidence. |
| 0:20–0:50 | Zetaris UI at `localhost:3001`: **Data Sources** with the five sources, then one source's tables | Five public sources, each governed in its own schema and registered in Zetaris. BantAI only ever reads them through Zetaris, read-only. |
| 0:50–1:05 | Zetaris query editor: run the query below | One Spark SQL query joins PAGASA's wind signals to PSA's population, across two sources, in place. |
| 1:05–2:20 | BantAI: ask the Inday question live; open the trail | It plans, writes each query with its purpose, and cites every number to a query: E1, E2… Click an evidence chip to show the rows. It noticed the final bulletin had no signals and went back to the last one that did. |
| 2:20–2:50 | Replay the Tacloban run | Four sources in one answer: NOAH storm surge, 346 storm passes since 1951, Haiyan's 35 km pass. When one query failed, it fixed it and carried on. |
| 2:50–3:15 | The trail's SQL and the security page | Every query is checked as a single SELECT before it reaches Zetaris. Zetaris reads through a read-only role. The data is governed locally, and BantAI defers life-safety calls to PAGASA, NDRRMC and the LGU. |
| 3:15–3:30 | The landing page's three pillars | BantAI today is the AI knowledge base and conversational agent. Next come workflow automation and strategic intelligence, on the same governed sources. |

The cross-source query for the Zetaris editor (tested: about 2 s):

```sql
SELECT c.pagasa_name AS storm, b.bulletin_number, w.signal_level,
       p.name AS province, pp.population
FROM BULLETINS.wind_signals w
JOIN BULLETINS.bulletins b ON w.bulletin_id = b.bulletin_id
JOIN BULLETINS.cyclones c ON b.cyclone_id = c.cyclone_id
JOIN REFERENCE.provinces p ON w.psgc_code = p.psgc_code
JOIN REFERENCE.province_population pp ON pp.psgc_code = p.psgc_code AND pp.year = 2025
ORDER BY w.signal_level DESC, pp.population DESC
LIMIT 8
```

## Say these plainly

- **The bulletins come through BagyoAPI**, an unofficial parser of PAGASA's public bulletins. PAGASA remains the authority.
- **The weather covers 24 starter cities**, at least one per region. More are one line each in `itoolbox-data-platform/scripts/ingest/cities.py`.
- **NOAH hazard is computed from NOAH's published vector tiles, and the source has gaps.** For example, Tacloban's level-2 storm-surge layer is empty.
- **No synthetic data is used.** Every source is public, and the README credits each one.
