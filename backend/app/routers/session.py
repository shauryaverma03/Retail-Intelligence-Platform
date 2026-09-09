"""Session / cookie endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..config import get_settings
from .. import session as sess
from ..models import PreferencesPatch, TourState

router = APIRouter(prefix="/session", tags=["session"])


@router.get("")
def get_session(s: sess.Session = Depends(sess.current_session)) -> dict:
    return {
        **s.public(),
        "recent_queries": sess.recent_queries(s.id, get_settings().session_query_history),
        "cookie": {
            "name": get_settings().session_cookie_name,
            "httponly": True,
            "samesite": get_settings().session_cookie_samesite,
            "secure": get_settings().session_cookie_secure,
            "ttl_days": get_settings().session_ttl_days,
            "signed": "HMAC-SHA256",
        },
        "note": "Anonymous session. No login, no personal data stored.",
    }


@router.post("/tour")
def set_tour(body: TourState, s: sess.Session = Depends(sess.current_session)) -> dict:
    return sess.set_tour_completed(s.id, body.completed)


@router.patch("/preferences")
def patch_preferences(
    body: PreferencesPatch, s: sess.Session = Depends(sess.current_session)
) -> dict:
    return {"preferences": sess.merge_preferences(s.id, body.patch)}


@router.get("/queries")
def get_queries(s: sess.Session = Depends(sess.current_session)) -> dict:
    return {"queries": sess.recent_queries(s.id, get_settings().session_query_history)}


@router.delete("")
def clear_session(
    response: Response, s: sess.Session = Depends(sess.current_session)
) -> dict:
    sess.reset_session(s.id)
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"ok": True, "cleared": s.id[:8]}
