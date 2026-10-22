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

_CAUSES_SQL = """\
SELECT COALESCE(cause_of_outage, 'unrecorded') AS cause, COUNT(DISTINCT site_code) AS sites_affected
FROM NM_RAN.site_outages
WHERE snapshot_time >= date_sub(current_date(), 7)
GROUP BY COALESCE(cause_of_outage, 'unrecorded')
ORDER BY sites_affected DESC
LIMIT 10"""

_AVAILABILITY_SQL = """\
SELECT province, ROUND(AVG(cell_availability_pct), 2) AS avg_5g_availability_pct, COUNT(*) AS days
FROM NM_RAN.kpi_5g_province_daily
WHERE day >= date_sub(current_date(), 7)
GROUP BY province
ORDER BY avg_5g_availability_pct ASC
LIMIT 10"""


def _call_id() -> str:
    return f"demo_{uuid.uuid4().hex[:12]}"


class DemoAgent:
    async def run(self, question: str, toolbox: Toolbox, emit: Emit) -> AgentOutcome:
        await emit(StatusEvent(text=(
            "Demo mode: no language model is called. Running a fixed check of the last 7 days "
            "of outages and 5G availability."
        )))
        await toolbox.run(_call_id(), "list_sources", {})
        await toolbox.run(_call_id(), "describe_table", {"source": "NM_RAN", "table": "site_outages"})

        await emit(StatusEvent(text="Checking which outage causes affected the most sites this week."))
        await toolbox.run(_call_id(), "run_sql", {
            "sql": _CAUSES_SQL, "purpose": "Outage causes by number of sites affected, last 7 days",
        })
        await emit(StatusEvent(text="Comparing 5G availability by province over the same week."))
        await toolbox.run(_call_id(), "run_sql", {
            "sql": _AVAILABILITY_SQL, "purpose": "Provinces with the lowest 5G cell availability, last 7 days",
        })

        causes, availability = (toolbox.evidence + [None, None])[:2]
        lines = [f"_Demo answer: the queries are live, the wording is a template. You asked: “{question}”_", ""]
        if causes and causes.rows:
            top = causes.rows[0]
            lines.append(
                f"**Answer**: The most common outage cause in the last 7 days was **{top[0]}**, "
                f"affecting {top[1]} sites [E1]."
            )
        else:
            lines.append("**Answer**: No outages were recorded in the last 7 days [E1].")
        if availability and availability.rows:
            low = availability.rows[0]
            lines.append(f"The lowest average 5G availability was in **{low[0]}** at {low[1]}% [E2].")
        lines += [
            "",
            "**Evidence**:",
            "- Outage causes by sites affected [E1]",
            "- 5G availability by province [E2]",
            "",
            "**Confidence**: not applicable; this is the scripted demo.",
            "",
            "**Next checks**: pick Nemotron, Grok or Claude to have a model investigate your question.",
        ]
        return AgentOutcome("completed", answer="\n".join(lines))
