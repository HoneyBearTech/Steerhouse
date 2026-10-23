from pydantic import BaseModel, Field


class StatsOut(BaseModel):
    """Counts for a status tile (a Heimdall dashboard, a script). Numbers only: no names, hosts
    or output, so a `stats` API key can read nothing else."""

    queued: int = Field(description="Runs waiting for a worker")
    running: int = Field(description="Runs in progress (including those being cancelled)")
    succeeded_24h: int = Field(description="Runs that succeeded in the last 24 hours")
    failed_24h: int = Field(description="Runs that failed or timed out in the last 24 hours")
    workers_online: int = Field(
        description="Workers seen in the last 30 seconds (shared by all projects)"
    )
