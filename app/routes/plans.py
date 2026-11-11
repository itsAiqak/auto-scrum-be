"""Standup plans: what each member typed for a day (Today items, blockers, notes) and when they submitted."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from ..db import DayPlan, Member
from ..deps import LoggedIn, Owner, SessionDep, SettingsDep
from ..schemas import DayPlanIn, DayPlanOut, PlanItem, Reviewed
from .members import MemberId

# Everyone logged in sees every plan; only the owner changes one (Owner).
router = APIRouter(prefix="/plans", tags=["standup plans"], dependencies=[LoggedIn])


def plan_out(plan: DayPlan) -> DayPlanOut:
    return DayPlanOut(
        member_id=plan.member_id,
        date=plan.date,
        notes=plan.notes,
        today=[PlanItem.model_validate(item) for item in plan.today],
        blockers=plan.blockers,
        resolved_blockers=plan.resolved_blockers,
        reviewed=Reviewed.model_validate(plan.reviewed),
        submitted_at=plan.submitted_at,
    )


def _require_member(session: SessionDep, member_id: str) -> None:
    if session.get(Member, member_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No member '{member_id}'")


@router.get("", response_model=list[DayPlanOut])
def list_plans(
    session: SessionDep,
    day: Annotated[date | None, Query(alias="date", description="One standup day: the team board.")] = None,
    member_id: Annotated[str | None, Query(alias="memberId", description="One member: their history.")] = None,
    since: date | None = None,
    until: date | None = None,
) -> list[DayPlanOut]:
    query = select(DayPlan).order_by(DayPlan.date, DayPlan.member_id)
    if day:
        query = query.where(DayPlan.date == day)
    if member_id:
        query = query.where(DayPlan.member_id == member_id)
    if since:
        query = query.where(DayPlan.date >= since)
    if until:
        query = query.where(DayPlan.date <= until)
    return [plan_out(p) for p in session.scalars(query)]


@router.get("/{member_id}/{day}", response_model=DayPlanOut)
def get_plan(member_id: MemberId, day: date, session: SessionDep) -> DayPlanOut:
    plan = session.get(DayPlan, (member_id, day))
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No plan for '{member_id}' on {day}")
    return plan_out(plan)


@router.put("/{member_id}/{day}", response_model=DayPlanOut, dependencies=[Owner])
def put_plan(member_id: MemberId, day: date, body: DayPlanIn, session: SessionDep) -> DayPlanOut:
    """Saves the whole plan for that day (the app sends it after every edit)."""
    _require_member(session, member_id)
    plan = session.get(DayPlan, (member_id, day)) or DayPlan(member_id=member_id, date=day)
    plan.notes = body.notes
    plan.today = [item.model_dump(exclude_none=True) for item in body.today]
    plan.blockers = body.blockers
    plan.resolved_blockers = body.resolved_blockers
    plan.reviewed = body.reviewed.model_dump()
    plan.submitted_at = body.submitted_at
    session.add(plan)
    session.commit()
    return plan_out(plan)


@router.post("/{member_id}/{day}/submit", response_model=DayPlanOut, dependencies=[Owner])
def submit_plan(member_id: MemberId, day: date, session: SessionDep, settings: SettingsDep) -> DayPlanOut:
    """Marks the plan submitted now (team-local 'HH:mm'). Submitting again keeps the first time."""
    _require_member(session, member_id)
    plan = session.get(DayPlan, (member_id, day)) or DayPlan(
        member_id=member_id, date=day, notes=[], today=[], blockers=[], resolved_blockers=[], reviewed=Reviewed().model_dump()
    )
    plan.submitted_at = plan.submitted_at or datetime.now(settings.timezone).strftime("%H:%M")
    session.add(plan)
    session.commit()
    return plan_out(plan)
