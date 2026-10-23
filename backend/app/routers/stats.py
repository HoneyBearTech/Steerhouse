from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run, RunStatus, User, Worker
from app.permissions import Permission, Scope, guard
from app.queue import WORKER_ONLINE_SECONDS
from app.schemas.stats import StatsOut
from app.scoping import readable_project_ids

router = APIRouter()

# Any API key may read these counts; a `stats` key may read nothing else.
_guard = guard(Permission.STATS_READ, Permission.STATS_READ, scope=Scope.PROJECT, api_key=True)

_FAILED = (RunStatus.FAILED.value, RunStatus.TIMED_OUT.value)


@router.get("", response_model=StatsOut)
def get_stats(
    request: Request,
    project_id: int | None = Query(None),
    user: User = Depends(_guard),
    db: Session = Depends(get_db),
) -> StatsOut:
    """Run counts in the caller's projects (an API key's own project; `project_id` narrows a
    person's to one), and the workers online. Polled by dashboards, so it's two small queries."""
    ids = readable_project_ids(db, user, request, Permission.STATS_READ, project_id)
    day_ago = func.now() - func.make_interval(0, 0, 0, 0, 24)
    finished_lately = Run.finished_at >= day_ago
    query = select(
        func.count().filter(Run.status == RunStatus.QUEUED.value),
        func.count().filter(Run.status == RunStatus.RUNNING.value),
        func.count().filter(finished_lately, Run.status == RunStatus.SUCCESS.value),
        func.count().filter(finished_lately, Run.status.in_(_FAILED)),
    ).where(
        or_(
            Run.status.in_((RunStatus.QUEUED.value, RunStatus.RUNNING.value)),
            finished_lately,
        )
    )
    if ids is not None:
        query = query.where(Run.project_id.in_(ids))
    queued, running, succeeded, failed = db.execute(query).one()
    online_since = func.now() - func.make_interval(0, 0, 0, 0, 0, 0, WORKER_ONLINE_SECONDS)
    workers = db.scalar(select(func.count()).where(Worker.last_seen_at > online_since))
    return StatsOut(
        queued=queued,
        running=running,
        succeeded_24h=succeeded,
        failed_24h=failed,
        workers_online=workers,
    )
