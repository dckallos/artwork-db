"""Schedule factory (generated from the registry). All STOPPED in dev.

  * ``daily_dbt_build``           -- dbt-only, every morning.
  * ``weekly_full_pipeline``      -- end-to-end (excl. enrichment) weekly.
  * ``hourly_{key}_enrich_batch`` -- one per source that has a partitioned enrichment
                                     step: drain that worklist a bounded slice each hour.

Flip ``default_status`` to RUNNING (and run the daemon) on the dedicated host.
"""
from __future__ import annotations

from typing import Dict, List

from dagster import DefaultScheduleStatus, ScheduleDefinition

STOPPED = DefaultScheduleStatus.STOPPED


def build_schedules(registry, jobs_by_name: Dict[str, object]) -> List[ScheduleDefinition]:
    schedules: List[ScheduleDefinition] = [
        ScheduleDefinition(
            name="daily_dbt_build",
            job=jobs_by_name["dbt_build_job"],
            cron_schedule="0 6 * * *",
            default_status=STOPPED,
            description="Daily dbt build at 06:00. STOPPED in dev; enable on the dedicated host.",
        ),
        ScheduleDefinition(
            name="weekly_full_pipeline",
            job=jobs_by_name["full_pipeline_job"],
            cron_schedule="0 5 * * 1",
            default_status=STOPPED,
            description="Weekly Monday 05:00 end-to-end run (excl. enrichment). STOPPED in dev.",
        ),
    ]
    for spec in registry:
        if spec.enrich_step() is not None:
            job_name = f"{spec.key}_enrich_next_batch_job"
            schedules.append(
                ScheduleDefinition(
                    name=f"hourly_{spec.key}_enrich_batch",
                    job=jobs_by_name[job_name],
                    cron_schedule="30 * * * *",
                    default_status=STOPPED,
                    description=f"Hourly {spec.key} enrichment batch (drain worklist). STOPPED in dev.",
                )
            )
    return schedules
