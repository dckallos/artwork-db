"""Schedules -- DEFINED but left STOPPED for local development.

In the dev phase you trigger runs manually from the Dagster UI. These schedules
exist so the intended cadence is captured in code; flip default_status to
RUNNING (and run the daemon) when you move to Stage 2 (dedicated host).
"""
from __future__ import annotations

from dagster import DefaultScheduleStatus, ScheduleDefinition

from .jobs import dbt_build_job, full_pipeline_job

# dbt-only, every morning: cheap, safe to run often once data exists.
daily_dbt_schedule = ScheduleDefinition(
    name="daily_dbt_build",
    job=dbt_build_job,
    cron_schedule="0 6 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
    description="Daily dbt build at 06:00. STOPPED in dev; enable on the dedicated host.",
)

# Full pipeline, weekly: extraction is manual/expensive today, so weekly cadence.
weekly_full_pipeline_schedule = ScheduleDefinition(
    name="weekly_full_pipeline",
    job=full_pipeline_job,
    cron_schedule="0 5 * * 1",
    default_status=DefaultScheduleStatus.STOPPED,
    description="Weekly Monday 05:00 end-to-end run. STOPPED in dev.",
)
