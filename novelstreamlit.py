# -*- coding: utf-8 -*-
"""
일상 릴스토리(가제) - AI 없는 Streamlit 단일 파일 버전

흐름: 방 만들기 -> 일상 입력 -> 익명 투표(기본 12시간) -> 1등 일상 + 득표수 공개
(AI 소설 변환, 삽화, API 키는 모두 제외. 입력한 일상 원문이 그대로 작품이 됩니다.)

실행
    pip install streamlit
    streamlit run app_noai.py
"""
from __future__ import annotations

import os
import random
import re
import threading
import time
import uuid
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

import novelstreamlit as st

# ─────────────────────────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────────────────────────
TZ = ZoneInfo("Asia/Seoul")

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 0/O, 1/I 제외
CODE_LEN = 6
CODE_RETRY = 5

MIN_CHARS = int(os.getenv("MIN_CHARS", "20"))
MAX_CHARS = int(os.getenv("MAX_CHARS", "150"))      # 원문이 그대로 작품이라 필요하면 늘리세요

VOTE_HOURS = float(os.getenv("VOTE_HOURS", "12"))  # 투표 시간(시간). 방장은 도중에 종료 가능

ROOM_TTL_DAYS = int(os.getenv("ROOM_TTL_DAYS", "7"))
MAX_MEMBERS = int(os.getenv("MAX_MEMBERS", "10"))
POLL_SEC = 5

PHASE_LABEL = {"input": "✏️ 일상 쓰는 중", "vote": "🗳️ 투표 중", "closed": "🏁 종료"}


# ─────────────────────────────────────────────────────────────
# 저장소 (서버 메모리, 모든 접속자가 공유)
# ─────────────────────────────────────────────────────────────
class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.rooms: dict[str, dict] = {}
        self.last_room: dict[str, str] = {}


@st.cache_resource
def get_store() -> Store:
    return Store()


def now() -> float:
    return time.time()  # 항상 서버 시계 기준


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%m/%d %H:%M")


def fmt_remaining(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}시간 {m}분" if h else f"{m}분 {s:02d}초"


def find_room(code: str):
    store = get_store()
    with store.lock:
        room = store.rooms.get(code)
        if room is None:
            return None, "missing"
        if now() - room["created"] > ROOM_TTL_DAYS * 86400:
            del store.rooms[code]
            return None, "expired"
        return room, "ok"


def effective_phase(room: dict) -> str:
    with get_store().lock:
        if room["phase"] == "vote" and now() >= room["vote_end"]:
            room["phase"] = "closed"
        return room["phase"]


def create_room(host_id: str):
    store = get_store()
    with store.lock:
        for _ in range(CODE_RETRY):
            code = "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
            if code in store.rooms:
                continue
            store.rooms[code] = {
                "code": code, "host": host_id, "phase": "input", "created": now(),
                "vote_start": None, "vote_end": None,
                "members": {host_id},
                "stories": {},   # story_id -> {author, text, ts}
                "votes": {},     # 기기ID -> story_id (1기기 1표)
            }
            store.last_room[host_id] = code
            return code
    return None


def join_room(code: str, dev: str):
    room, status = find_room(code)
    if status == "missing":
        return False, "방을 찾을 수 없어요"
    if status == "expired":
        return False, "만료된 방이에요"
    store = get_store()
    with store.lock:
        if dev not in room["members"]:
            if len(room["members"]) >= MAX_MEMBERS:
                return False, f"방이 가득 찼어요 (최대 {MAX_MEMBERS}명)"
            room["members"].add(dev)
        store.last_room[dev] = code
    return True, ""


def story_of(room: dict, dev: str):
    for sid, s in room["stories"].items():
        if s["author"] == dev:
            return sid, s
    return None, None


def submit_story(room: dict, dev: str, text: str):
    with get_store().lock:
        if effective_phase(room) != "input":
            return False, "입력이 마감됐어요"
        if story_of(room, dev)[0]:
            return False, "이미 제출했어요"
        n = len(text)
        if not (MIN_CHARS <= n <= MAX_CHARS):
            return False, f"{MIN_CHARS}자 이상 {MAX_CHARS}자 이하로 적어 주세요 (지금 {n}자)"
        room["stories"][uuid.uuid4().hex[:10]] = {"author": dev, "text": text, "ts": now()}
        return True, ""


def start_vote(room: dict, dev: str):
    with get_store().lock:
        if room["host"] != dev:
            return False, "방장만 투표를 시작할 수 있어요"
        if effective_phase(room) != "input":
            return False, "이미 입력이 마감됐어요"
        if not room["stories"]:
            return False, "아직 제출된 일상이 없어요"
        room["vote_start"] = now()
        room["vote_end"] = room["vote_start"] + VOTE_HOURS * 3600
        room["phase"] = "vote"
        return True, ""


def end_vote(room: dict, dev: str):
    """방장이 종료 시각 전에 투표를 마감."""
    with get_store().lock:
        if room["host"] != dev:
            return False, "방장만 투표를 종료할 수 있어요"
        if effective_phase(room) != "vote":
            return False, "이미 투표가 끝났어요"
        room["vote_end"] = now()
        room["phase"] = "closed"
        return True, ""


def cast_vote(room: dict, dev: str, story_id: str):
    with get_store().lock:
        if effective_phase(room) != "vote":
            return False, "투표가 끝났어요"
        s = room["stories"].get(story_id)
        if s is None:
            return False, "작품을 찾을 수 없어요"
        if s["author"] == dev:
            return False, "본인 작품에는 투표할 수 없어요"
        room["votes"][dev] = story_id
        return True, ""


def tally(room: dict):
    """(winners, top_votes). 동점은 공동 1등."""
    counts = Counter(room["votes"].values())
    if not counts:
        return [], 0
    top = max(counts.values())
    ordered = sorted(room["stories"].items(), key=lambda kv: kv[1]["ts"])
    return [sid for sid, _ in ordered if counts.get(sid) == top], top


# ─────────────────────────────────────────────────────────────
# 화면
# ─────────────────────────────────────────────────────────────
def md_safe(text: str) -> str:
    return text.replace("$", r"\$").replace("~", r"\~").replace("\n", "\n\n")


def init_identity() -> str:
    d = st.query_params.get("d")
    if not d or not re.fullmatch(r"[0-9a-f]{32}", d):
        d = uuid.uuid4().hex
        st.query_params["d"] = d
    return d


def leave_room(dev: str):
    store = get_store()
    with store.lock:
        store.last_room.pop(dev, None)
    st.session_state.pop("room_code", None)
    for k in [k for k in st.session_state if k.startswith("text_")]:
        st.session_state.pop(k, None)
    st.rerun()


def view_home(dev: str):
    st.caption("오늘의 일상을 한두 줄 쓰고, 익명으로 돌려 읽고 1등을 뽑아요.")
    tab_create, tab_join = st.tabs(["방 만들기", "방 입장"])

    with tab_create:
        st.write("방을 만들면 6자리 코드가 생겨요. 코드를 지인에게 알려 주세요.")
        st.caption(f"투표 시간은 {VOTE_HOURS:g}시간이에요. 방장은 그 전에 종료할 수도 있어요.")
        if st.button("방 만들기", type="primary", use_container_width=True):
            code = create_room(dev)
            if code:
                st.session_state["room_code"] = code
                st.rerun()
            else:
                st.error("잠시 후 다시 시도해 주세요")

    with tab_join:
        with st.form("join_form"):
            raw = st.text_input("방 코드 6자리", max_chars=CODE_LEN, placeholder="예: K7M2QX")
            go = st.form_submit_button("입장", type="primary", use_container_width=True)
        if go:
            code = raw.strip().upper()
            if len(code) != CODE_LEN:
                st.warning(f"코드는 {CODE_LEN}자리예요")
            else:
                ok, msg = join_room(code, dev)
                if ok:
                    st.session_state["room_code"] = code
                    st.rerun()
                else:
                    st.error(msg)


@st.fragment(run_every=POLL_SEC)
def live_panel(code: str, dev: str, shown_phase: str):
    room, _ = find_room(code)
    if room is None or effective_phase(room) != shown_phase:
        st.rerun()
        return
    n = len(room["stories"])
    st.caption(f"제출된 일상 {n}건 · 참여자 {len(room['members'])}명")
    if room["host"] == dev:
        if n == 0:
            st.caption("아직 제출된 일상이 없어요")
        if st.button("투표 시작", type="primary", disabled=(n == 0), key=f"start_{code}",
                     use_container_width=True, help="입력을 마감하고 익명 투표를 시작해요"):
            ok, msg = start_vote(room, dev)
            if ok:
                st.rerun()
            else:
                st.error(msg)


def view_input(code: str, room: dict, dev: str):
    live_panel(code, dev, "input")

    _, mine = story_of(room, dev)
    if mine:
        st.success("제출 완료! 방장이 투표를 시작하면 화면이 자동으로 바뀌어요.")
        with st.container(border=True):
            st.markdown("**내 작품**")
            st.markdown(md_safe(mine["text"]))
        return

    st.subheader("오늘의 일상")
    text = st.text_area("한두 줄로 적어 주세요", max_chars=MAX_CHARS, height=130,
                        key=f"text_{code}",
                        placeholder="예: 점심에 회사 앞 국밥집에서 동료랑 국밥을 먹고 커피를 사 마셨다.")
    n = len(text.strip())
    st.caption(f"{n}/{MAX_CHARS}자 (최소 {MIN_CHARS}자) · 바깥을 누르면 글자수가 갱신돼요")
    st.info("입력한 글은 투표를 위해 방 참여자에게 (작성자 없이) 그대로 보여요. "
            "방 코드를 아는 사람은 누구나 들어올 수 있으니 실명·연락처 같은 민감한 내용은 적지 마세요.")

    if st.button("제출", type="primary", use_container_width=True):
        ok, msg = submit_story(room, dev, text.strip())
        if ok:
            st.rerun()
        else:
            st.warning(msg)


@st.fragment(run_every=POLL_SEC)
def view_vote(code: str, dev: str):
    room, _ = find_room(code)
    if room is None or effective_phase(room) != "vote":
        st.rerun()
        return

    st.caption(f"투표 종료 {fmt_time(room['vote_end'])} (남은 시간 {fmt_remaining(room['vote_end'] - now())})"
               " · 종료 전에는 득표 현황이 보이지 않아요")

    if room["host"] == dev:
        ck = f"confirm_end_{code}"
        if not st.session_state.get(ck):
            if st.button("지금 투표 종료", key=f"end_{code}", use_container_width=True,
                         help="남은 시간과 상관없이 투표를 마감하고 결과를 공개해요"):
                st.session_state[ck] = True
                st.rerun(scope="fragment")
        else:
            st.warning("지금 종료하면 결과가 바로 공개되고, 이후에는 투표할 수 없어요.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("종료하기", type="primary", key=f"end_yes_{code}",
                             use_container_width=True):
                    st.session_state.pop(ck, None)
                    ok, msg = end_vote(room, dev)
                    if not ok:
                        st.error(msg)
                    st.rerun()
            with c2:
                if st.button("취소", key=f"end_no_{code}", use_container_width=True):
                    st.session_state.pop(ck, None)
                    st.rerun(scope="fragment")

    ids = sorted(room["stories"])
    random.Random(f"{dev}:{code}").shuffle(ids)  # 기기마다 다른 순서, 새로고침해도 고정
    my_vote = room["votes"].get(dev)

    for i, sid in enumerate(ids, 1):
        s = room["stories"][sid]
        with st.container(border=True):
            st.markdown(f"**작품 {i}**")
            st.markdown(md_safe(s["text"]))
            if s["author"] == dev:
                st.caption("내 작품이에요 (본인 작품에는 투표할 수 없어요)")
            elif my_vote == sid:
                st.success("내가 투표한 작품")
            elif st.button("이 작품에 투표" if my_vote is None else "이 작품으로 바꾸기",
                           key=f"vote_{sid}", use_container_width=True):
                ok, msg = cast_vote(room, dev, sid)
                if ok:
                    st.rerun(scope="fragment")
                else:
                    st.error(msg)
                    st.rerun()


def view_closed(room: dict, dev: str):
    if not room["stories"]:
        st.info("작품이 없어요")
        return
    winners, top = tally(room)
    if top == 0:
        if len(room["stories"]) == 1:
            s = next(iter(room["stories"].values()))
            st.subheader("🏆 오늘의 1등")
            with st.container(border=True):
                st.markdown("**0표** (투표 없이 단독 1등)")
                st.markdown(md_safe(s["text"]))
        else:
            st.info("투표가 없어 결과가 없어요")
        return

    st.subheader("🏆 오늘의 1등" + (" (공동 1등)" if len(winners) > 1 else ""))
    for sid in winners:
        s = room["stories"][sid]
        with st.container(border=True):
            st.markdown(f"**{top}표**")
            st.markdown(md_safe(s["text"]))
            if s["author"] == dev:
                st.caption("🎉 내가 쓴 작품이에요!")
    st.caption("2등 이하는 공개하지 않아요")


def view_room(code: str, room: dict, dev: str):
    phase = effective_phase(room)
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(f"**방 코드** &nbsp; `{code}` &nbsp; {PHASE_LABEL[phase]}"
                    + (" · 👑 방장" if room["host"] == dev else ""))
    with c2:
        if st.button("방 나가기", use_container_width=True):
            leave_room(dev)
    if room["host"] == dev and phase == "input":
        st.code(code, language=None)
    st.divider()

    if phase == "input":
        view_input(code, room, dev)
    elif phase == "vote":
        view_vote(code, dev)
    else:
        view_closed(room, dev)


def main():
    st.set_page_config(page_title="일상 릴스토리", page_icon="📖", layout="centered")
    dev = init_identity()
    st.title("📖 일상 릴스토리")

    store = get_store()
    code = st.session_state.get("room_code") or store.last_room.get(dev)
    if code:
        room, status = find_room(code)
        if room is None:
            st.session_state.pop("room_code", None)
            store.last_room.pop(dev, None)
            st.warning("방을 찾을 수 없어요" if status == "missing" else "만료된 방이에요")
            view_home(dev)
        else:
            st.session_state["room_code"] = code
            view_room(code, room, dev)
    else:
        view_home(dev)


main()

# NOTES
# - 기기ID는 URL(?d=...)에 보관됩니다. 주소창 URL을 공유하면 같은 사람으로 인식되니
#   공유는 반드시 '방 코드'로만 하세요.
# - 서버가 재시작되면 방 데이터가 사라집니다(서버 메모리 저장).