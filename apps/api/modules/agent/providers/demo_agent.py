"""Demo (no LLM): a scripted investigation over live data.

It runs real tool calls through the real Toolbox, so the event stream, the
evidence and the stored investigation are exactly what a model produces. Only
the reasoning is fixed. Use it to build and test the UI without model credits.
"""
from __future__ import annotations

import uuid

from modules.agent.providers.base import AgentOutcome
from modules.agent.schemas import StatusEvent
from modules.agent.tools import Emit, Toolbox

_RAIN_AHEAD_SQL = """\
SELECT l.name AS city, l.province,
       ROUND(SUM(COALESCE(f.rain_3h_mm, 0)), 1) AS rain_next_48h_mm,
       ROUND(MAX(f.rain_prob), 2) AS max_rain_prob
FROM WEATHER.forecasts f
JOIN WEATHER.locations l ON f.location_id = l.location_id
WHERE f.forecast_for > current_timestamp()
  AND f.forecast_for <= current_timestamp() + INTERVAL 48 HOURS
GROUP BY l.name, l.province
ORDER BY rain_next_48h_mm DESC
LIMIT 10"""

_RAIN_NOW_SQL = """\
SELECT l.name AS city, l.province,
       date_format(from_utc_timestamp(o.observed_at, 'Asia/Manila'), 'yyyy-MM-dd HH:mm') AS observed_pht,
       o.description, ROUND(COALESCE(o.rain_1h_mm, 0), 1) AS rain_1h_mm, ROUND(o.temp_c, 1) AS temp_c
FROM WEATHER.observations o
JOIN WEATHER.locations l ON o.location_id = l.location_id
WHERE o.observed_at >= current_timestamp() - INTERVAL 2 HOURS
ORDER BY rain_1h_mm DESC, o.observed_at DESC
LIMIT 10"""


def _call_id() -> str:
    return f"demo_{uuid.uuid4().hex[:12]}"


def _first_row(evidence) -> dict | None:
    """The top row by column name, so the wording never depends on column order."""
    if not evidence or not evidence.rows:
        return None
    return dict(zip(evidence.columns, evidence.rows[0]))


class DemoAgent:
    async def run(self, question: str, toolbox: Toolbox, emit: Emit) -> AgentOutcome:
        await emit(StatusEvent(text=(
            "Demo mode: no language model is called. Running a fixed check of where rain is "
            "forecast in the next 48 hours and where it is raining now."
        )))
        await toolbox.run(_call_id(), "list_sources", {})

        await emit(StatusEvent(text="Adding up the forecast rain per city for the next 48 hours."))
        await toolbox.run(_call_id(), "run_sql", {
            "sql": _RAIN_AHEAD_SQL, "purpose": "Forecast rain per city, next 48 hours",
        })
        await emit(StatusEvent(text="Checking the latest observations for rain falling now."))
        await toolbox.run(_call_id(), "run_sql", {
            "sql": _RAIN_NOW_SQL, "purpose": "Rain observed in the last hour, per city",
        })

        ahead, now = (toolbox.evidence + [None, None])[:2]
        top, wet = _first_row(ahead), _first_row(now)
        lines = [f"_Demo answer: the queries are live, the wording is a template. You asked: “{question}”_", ""]
        if top:
            lines.append(
                f"**Answer**: The most rain forecast in the next 48 hours is in **{top['city']}, "
                f"{top['province']}**, with {top['rain_next_48h_mm']} mm [E1]."
            )
        else:
            lines.append("**Answer**: No forecast is loaded for the next 48 hours [E1].")
        if wet and float(wet["rain_1h_mm"] or 0) > 0:
            lines.append(
                f"The heaviest rain right now is in **{wet['city']}**: {wet['description']}, "
                f"{wet['rain_1h_mm']} mm in the last hour [E2]."
            )
        elif now:
            lines.append("No city reported rain in the latest observations [E2].")
        lines += [
            "",
            "**Evidence**:",
            "- Forecast rain per city, next 48 hours [E1]",
            "- Rain observed in the last hour [E2]",
            "",
            "**Confidence**: not applicable; this is the scripted demo.",
            "",
            "**Next checks**: pick Nemotron, Grok or Claude to have a model investigate your question.",
        ]
        return AgentOutcome("completed", answer="\n".join(lines))
