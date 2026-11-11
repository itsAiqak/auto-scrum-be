"""Team members. Commits are matched to a member through `gitEmails`."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select

from ..db import Member
from ..deps import Authorized, LoggedIn, SessionDep
from ..schemas import MemberIn, MemberOut

router = APIRouter(prefix="/members", tags=["members"])
MemberId = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]


def member_out(member: Member) -> MemberOut:
    return MemberOut(
        id=member.id,
        name=member.name,
        initials=member.initials,
        role=member.role,
        team=member.team,
        avatar_color=member.avatar_color,
        git_emails=member.git_emails,
    )


@router.get("", response_model=list[MemberOut], dependencies=[LoggedIn])
def list_members(session: SessionDep) -> list[MemberOut]:
    return [member_out(m) for m in session.scalars(select(Member).order_by(Member.team, Member.name))]


@router.get("/{member_id}", response_model=MemberOut, dependencies=[LoggedIn])
def get_member(member_id: MemberId, session: SessionDep) -> MemberOut:
    member = session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No member '{member_id}'")
    return member_out(member)


@router.put("/{member_id}", response_model=MemberOut, dependencies=[Authorized])
def put_member(member_id: MemberId, body: MemberIn, session: SessionDep) -> MemberOut:
    """Creates or replaces a member. Their git emails decide who may sign up as them, so set API_TOKEN on a shared server."""
    member = session.get(Member, member_id) or Member(id=member_id)
    member.name = body.name
    member.initials = body.initials
    member.role = body.role
    member.team = body.team
    member.avatar_color = body.avatar_color
    member.git_emails = [email.strip() for email in body.git_emails if email.strip()]
    session.add(member)
    session.commit()
    return member_out(member)
