# -*- coding: utf-8 -*-
"""
Dayfic - Streamlit 단일 파일 MVP

흐름: 방 만들기 -> 일상 입력(20~150자) -> AI 소설 변환(약 500자)
      -> 익명 투표(기본 12시간) -> 1등 소설 + 득표수 + AI 삽화 1장

실행
    pip install streamlit requests
    export APP_ENV=dev                      # dev | prod
    export GOOGLE_API_KEY_DEV=...           # 개발용 키 (SYS-01)
    export GOOGLE_API_KEY_PROD=...          # 실전용 키 (APP_ENV=prod 일 때만 사용)
    streamlit run novelstreamlit.py

키는 환경 변수 또는 .streamlit/secrets.toml 로 주입합니다(소스에 넣지 않음).

[명세와 다르게 처리한 부분 - 파일 맨 아래 NOTES 참고]
- 방 데이터 저장소: Firebase 대신 서버 메모리(st.cache_resource)를 사용합니다.
  Streamlit 은 서버가 있으므로 AI 키가 브라우저에 노출되지 않습니다(10장 2번 해소).
- 서버가 재시작되면 방 데이터가 사라집니다.
"""
from __future__ import annotations

import os
import random
import re
import sys
import threading
import time
import uuid
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────
# 설정값 (명세의 "설정 데이터로 관리" 원칙: 숫자·문구는 모두 여기서 변경)
# ─────────────────────────────────────────────────────────────
APP_ENV = os.getenv("APP_ENV", "dev").lower()  # dev | prod
TZ = ZoneInfo("Asia/Seoul")

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 0/O, 1/I 제외
CODE_LEN = 6
CODE_RETRY = 5

MIN_CHARS, MAX_CHARS = 20, 150          # 입력 글자수 (공백 포함)
STORY_MIN, STORY_MAX = 450, 550         # 출력 글자수 (공백 포함)

DEFAULT_VOTE_HOURS = 12                 # 10장 3번 가정
VOTE_HOURS_OPTIONS = (10, 12)           # FR-11 (Could)
SHOW_VOTE_HOURS_SELECT = os.getenv("SHOW_VOTE_HOURS_SELECT", "0") == "1"  # MVP: 숨김
# 개발 중 빠른 테스트용: 투표 시간을 '분' 단위로 덮어씀 (prod 에서는 무시)
VOTE_MINUTES_DEBUG = os.getenv("VOTE_MINUTES_DEBUG")

ROOM_TTL_DAYS = int(os.getenv("ROOM_TTL_DAYS", "7"))   # 10장 7번 가정
MAX_MEMBERS = int(os.getenv("MAX_MEMBERS", "5"))      # 10장 6번: AI 비용 때문에 상한
ILLUST_STALE_SEC = 180                  # '생성 중' 3분 초과 시 선점 해제
ILLUST_MAX_ATTEMPTS = 3                 # 방당 삽화 생성 시도 상한(비용 보호)
POLL_SEC = 5                            # 다른 참여자 변화 확인 주기

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# 모델명은 개발 단계에서 비교 후 정하기로 했으므로 환경 변수로 교체 가능
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

GENRES = {
    "현대판타지": "현대 한국에 던전과 각성자가 존재한다. 헌터, 길드, 게이트, 스킬 창 같은 용어를 쓴다.",
    "무협": "강호의 문파와 무림인이 존재한다. 내공, 초식, 객잔, 사부, 문파 같은 용어를 쓴다.",
    "로맨스판타지": "황실과 귀족 사회가 있는 세계다. 영애, 공작가, 황태자, 빙의 같은 요소와 설렘의 분위기를 쓴다.",
}

# 장르별 삽화 그림 방식 (명세 7장). 키는 GENRES와 동일해야 함
ILLUST_STYLES: dict[str, str] = {
    "현대판타지": (
        "Korean web novel illustration style, high-quality semi-realistic digital painting, "
        "polished character rendering, refined linework, detailed facial features, "
        "sophisticated lighting and shading, modern urban fantasy atmosphere, "
        "contemporary cityscapes blended with supernatural elements, mystical magical effects, "
        "glowing energy and intricate magic circles, dramatic cinematic lighting, "
        "cool and vivid color palette, immersive composition, visually striking fantasy aesthetics."
    ),
    "무협": (
        "Korean web novel illustration style, high-quality semi-realistic digital painting, "
        "polished character rendering, refined linework, detailed facial features, "
        "sophisticated lighting and shading, traditional Eastern martial arts fantasy atmosphere, "
        "elegant traditional robes with flowing fabric, dynamic swordsmanship and martial arts poses, "
        "mystical qi energy effects, detailed Eastern architecture, misty mountains and traditional landscapes, "
        "dramatic cinematic composition, rich and harmonious color palette, "
        "powerful yet graceful visual expression."
    ),
    "로맨스판타지": (
        "Korean web novel illustration style, high-quality semi-realistic digital painting, "
        "polished character rendering, refined linework, delicate facial features, "
        "sophisticated lighting and shading, elegant European-inspired fantasy atmosphere, "
        "luxurious aristocratic costumes, intricate lace embroidery and sparkling jewelry, "
        "majestic castles and enchanting gardens, graceful character poses, expressive romantic emotions, "
        "soft luminous lighting, refined pastel and jewel-tone color palette, ethereal atmosphere, "
        "visually captivating and elegant composition."
    ),
}

PHASE_LABEL = {"input": "✏️ 일상 쓰는 중", "vote": "🗳️ 투표 중", "closed": "🏁 종료"}

MSG_AI_OFF = "지금은 소설을 만들 수 없어요"


# ─────────────────────────────────────────────────────────────
# 저장소 (서버 메모리) - 모든 접속자가 공유
# ─────────────────────────────────────────────────────────────
class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.rooms: dict[str, dict] = {}
        self.last_room: dict[str, str] = {}  # 기기ID -> 마지막 방 (새로고침 복구용)


@st.cache_resource
def get_store() -> Store:
    return Store()


def now() -> float:
    """'DB 서버 시각' 역할: 항상 서버 시계만 사용(기기 시계 사용 안 함)."""
    return time.time()


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%m/%d %H:%M")


def fmt_remaining(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}시간 {m}분" if h else f"{m}분"


def find_room(code: str):
    """(room, status) 반환. status: ok | missing | expired"""
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


def create_room(host_id: str, hours: int):
    """FR-01. 코드 중복 시 최대 5회 재시도."""
    store = get_store()
    with store.lock:
        for _ in range(CODE_RETRY):
            code = "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
            if code in store.rooms:
                continue
            store.rooms[code] = {
                "code": code,
                "host": host_id,
                "phase": "input",
                "created": now(),
                "vote_start": None,
                "vote_end": None,
                "vote_hours": hours,
                "members": {host_id},
                "stories": {},      # story_id -> {author, genre, text, ts}
                "pending": set(),   # AI 변환 중인 기기ID
                "votes": {},        # 기기ID -> story_id (1기기 1표)
                "illust": {"status": "waiting", "by": None, "started": 0.0,
                           "attempts": 0, "image": None, "mime": None},
            }
            store.last_room[host_id] = code
            return code
    return None


def join_room(code: str, dev: str):
    """FR-02. (ok, message)"""
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


def start_vote(room: dict, dev: str):
    """FR-05. 방장만, 작품 1건 이상, 변환 진행 중이면 대기."""
    with get_store().lock:
        if room["host"] != dev:
            return False, "방장만 투표를 시작할 수 있어요"
        if effective_phase(room) != "input":
            return False, "이미 입력이 마감됐어요"
        if not room["stories"]:
            return False, "아직 제출된 일상이 없어요"
        if room["pending"]:
            return False, "소설을 만드는 중인 참여자가 있어요. 잠시만 기다려 주세요"
        hours = room["vote_hours"]
        seconds = hours * 3600
        if VOTE_MINUTES_DEBUG and APP_ENV != "prod":
            seconds = float(VOTE_MINUTES_DEBUG) * 60
        room["vote_start"] = now()
        room["vote_end"] = room["vote_start"] + seconds
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
    """FR-06. 서버 측 검증('보안 규칙'): 단계, 존재 여부, 본인 작품 금지."""
    with get_store().lock:
        if effective_phase(room) != "vote":
            return False, "투표가 끝났어요"
        s = room["stories"].get(story_id)
        if s is None:
            return False, "작품을 찾을 수 없어요"
        if s["author"] == dev:
            return False, "본인 작품에는 투표할 수 없어요"
        room["votes"][dev] = story_id  # 기기ID가 키 -> 1인 1표, 종료 전 변경 가능
        return True, ""


def tally(room: dict):
    """(winners[list of story_id], top_votes)  - 동점은 공동 1등."""
    counts = Counter(room["votes"].values())
    if not counts:
        return [], 0
    top = max(counts.values())
    ordered = sorted(room["stories"].items(), key=lambda kv: kv[1]["ts"])
    return [sid for sid, _ in ordered if counts.get(sid) == top], top


# ─────────────────────────────────────────────────────────────
# AI (Google Gemini REST) - SYS-01: 환경별로 다른 키 주입
# ─────────────────────────────────────────────────────────────
class AIUnavailable(Exception):
    """키 없음"""


class AIBlocked(Exception):
    """안전 필터에 걸림"""


class AIError(Exception):
    """호출 실패/시간 초과 등"""


def _secret(name: str):
    v = os.getenv(name)
    if v:
        return v
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def get_api_key():
    name = "GOOGLE_API_KEY_PROD" if APP_ENV == "prod" else "GOOGLE_API_KEY_DEV"
    return _secret(name)  # 개발 환경에서 실전 키로 대체하지 않음


def _generate(model: str, body: dict, timeout: int) -> dict:
    key = get_api_key()

    if not key:
        raise AIUnavailable()

    max_attempts = 4

    for attempt in range(max_attempts):
        try:
            r = requests.post(
                f"{API_BASE}/models/{model}:generateContent",
                headers={
                    "x-goog-api-key": key,
                    "Content-Type": "application/json"
                },
                json=body,
                timeout=(15, timeout)
            )

            # 정상 응답
            if r.status_code == 200:
                data = r.json()

                if (data.get("promptFeedback") or {}).get("blockReason"):
                    raise AIBlocked()

                cands = data.get("candidates") or []

                if not cands:
                    raise AIBlocked()

                if "SAFETY" in str(cands[0].get("finishReason", "")):
                    raise AIBlocked()

                return cands[0]
            
             # 재시도할 오류
            if r.status_code in (429, 500, 502, 503, 504):
                if attempt < max_attempts - 1:
                    wait = 2 ** (attempt + 1)

                    print(
                        f"[AI] HTTP {r.status_code} "
                        f"- {wait}초 후 재시도 "
                        f"({attempt + 1}/{max_attempts - 1})",
                        file=sys.stderr
                    )

                    time.sleep(wait)
                    continue

            # 재시도 대상이 아니거나 재시도 횟수 초과
            try:
                detail = (r.json().get("error") or {}).get("message", "")
            except ValueError:
                detail = ""

            print(
                f"[AI] {model} HTTP {r.status_code}: {detail[:300]}",
                file=sys.stderr
            )

            raise AIError(f"HTTP {r.status_code}")

        except AIBlocked:
            raise

        except requests.RequestException as e:
            if attempt < max_attempts - 1:
                wait = 2 ** (attempt + 1)

                print(
                    f"[AI] {type(e).__name__} "
                    f"- {wait}초 후 재시도",
                    file=sys.stderr
                )

                time.sleep(wait)
                continue

            raise AIError(type(e).__name__) from e

    raise AIError("재시도 횟수 초과")



    


def gemini_text(prompt: str) -> str:
    cand = _generate(
        TEXT_MODEL,
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {"temperature": 1.0}},
        timeout=180,
    )
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise AIBlocked()
    return text


def gemini_image(prompt: str):
    import base64

    cand = _generate(
        IMAGE_MODEL,
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
        timeout=120,
    )
    for p in (cand.get("content") or {}).get("parts") or []:
        blob = p.get("inlineData") or p.get("inline_data")
        if blob and blob.get("data"):
            mime = blob.get("mimeType") or blob.get("mime_type") or "image/png"
            return base64.b64decode(blob["data"]), mime
    raise AIBlocked()


def build_story_prompt(genre: str, daily: str) -> str:
    return (
        "너는 웹소설 작가다. 아래 [일상]을 [장르] 소설로 바꿔 써라.\n\n"
        f"[장르] {genre}\n"
        f"[장르 설정] {GENRES[genre]}\n"
        f"[일상] {daily}\n\n"
        "규칙\n"
        "1. 일상의 사건 순서와 핵심 요소(장소, 음식, 행동, 등장 인물 수)를 그대로 유지한다. "
        "예: 학교는 학교의 장르 버전으로, 국밥은 국밥의 장르 버전으로 바꾼다.\n"
        "2. 배경, 직업, 사물의 이름과 말투만 장르에 맞게 바꾼다.\n"
        f"3. 분량은 공백 포함 500자 내외({STORY_MIN}~{STORY_MAX}자)로 쓴다.\n"
        "4. 3인칭 과거형, 한 문단 또는 두 문단으로 쓴다.\n"
        "5. 가볍고 웃긴 톤으로, 마지막 문장에 짧은 반전이나 여운을 둔다.\n"
        "6. 실존 인물, 실제 브랜드, 혐오·성적·폭력적 표현은 쓰지 않는다.\n"
        "7. 제목, 설명, 머리말 없이 소설 본문만 출력한다."
    )

def build_illust_prompt(story: str, genre: str) -> str:
    style = ILLUST_STYLES.get(genre)
    if style is None:
        raise ValueError(f"지원하지 않는 장르입니다: {genre!r}")

    return f"""아래 소설을 읽고 가장 인상적이고 상징적인 장면 하나를 선정하여, 지정된 장르와 그림 방식에 맞는 고품질 삽화를 생성하라.

[소설]
{story}

[장르]
{genre}

[그림 방식]
{style}

[장면 선정 및 표현 규칙]
1. 소설의 핵심 사건, 감정, 분위기를 가장 잘 전달하는 장면 하나를 선정한다.
2. 인물의 표정, 자세, 배경, 소품 등 장면을 구성하는 요소를 소설의 맥락에 맞게 표현한다.
3. 지정된 그림 방식의 시각적 특징(색상 팔레트, 선의 표현, 질감, 명암, 조명, 구도)을 충실히 반영한다.
4. 장르 고유의 분위기와 감정적 긴장감을 시각적으로 극대화한다.
5. 소설에 명시되지 않은 인물의 외모나 배경은 장르와 문맥에 어울리도록 자연스럽게 창작하되, 원작의 설정과 모순되지 않도록 한다.

[공통 제약 조건]
- 실존 인물이나 특정 유명인의 외모를 모방하지 않는다.
- 이미지 내 글자, 자막, 말풍선, 워터마크는 넣지 않거나 최소화한다.
- 장르와 그림 방식이 서로 조화를 이루도록 한다.
- 장면의 핵심 요소가 잘 드러나도록 시각적 우선순위와 구도를 구성한다.
- 하나의 완성된 소설 삽화로 생성한다."""



def clean_story(text: str) -> str:
    """제목·머리말 제거, 마크다운 강조 제거, 본문만 남김."""
    lines = text.strip().splitlines()
    while lines and (
        not lines[0].strip()
        or lines[0].strip().startswith("#")
        or re.match(r"^\**\s*(제목|title)\s*[:：]", lines[0].strip(), re.I)
    ):
        lines.pop(0)
    return "\n".join(lines).replace("**", "").strip()


def convert_story(genre: str, daily: str) -> str:
    """FR-04. 분량 이탈 또는 안전 필터 시 자동 1회 재시도(건당 재시도 1회 제한)."""
    prompt = build_story_prompt(genre, daily)
    hint, last = "", None
    for attempt in range(2):
        try:
            story = clean_story(gemini_text(prompt + hint))
        except AIBlocked:
            if last:
                return last
            if attempt == 1:
                raise
            hint = "\n\n(주의: 더 순화되고 건전한 표현으로 써라.)"
            continue
        last = story
        if STORY_MIN <= len(story) <= STORY_MAX:
            return story
        hint = f"\n\n(이전 결과가 {len(story)}자였다. 반드시 공백 포함 {STORY_MIN}~{STORY_MAX}자로 써라.)"
    return last


def submit_story(room: dict, dev: str, genre: str, daily: str):
    """FR-03 + FR-04. (ok, message)"""
    store = get_store()
    with store.lock:
        if effective_phase(room) != "input":
            return False, "입력이 마감됐어요"
        if story_of(room, dev)[0] or dev in room["pending"]:
            return False, "이미 제출했어요"
        room["pending"].add(dev)
    try:
        story = convert_story(genre, daily)
    except AIUnavailable:
        return False, MSG_AI_OFF
    except AIBlocked:
        return False, "이 내용은 이 장르로 만들기 어려워요. 장르를 바꿔서 다시 제출해 보세요."
    except AIError as e:
        print(f"[소설 생성 오류] {e}", file=sys.stderr)
        return False, f"소설을 만들지 못했어요. 다시 시도해 주세요. : {e}"
    finally:
        with store.lock:
            room["pending"].discard(dev)
    with store.lock:
        sid = uuid.uuid4().hex[:10]
        room["stories"][sid] = {"author": dev, "genre": genre, "text": story, "ts": now()}
    return True, ""


# ─────────────────────────────────────────────────────────────
# 화면 공통
# ─────────────────────────────────────────────────────────────
def md_safe(text: str) -> str:
    """소설 본문을 마크다운으로 그릴 때 깨지는 문자 이스케이프 + 문단 유지."""
    return text.replace("$", r"\$").replace("~", r"\~").replace("\n", "\n\n")


def init_identity() -> str:
    """로그인 없음: 기기ID(랜덤)로만 구분. 새로고침해도 유지되도록 URL 쿼리에 둔다."""
    d = st.query_params.get("d")
    if not d or not re.fullmatch(r"[0-9a-f]{32}", d):
        d = uuid.uuid4().hex
        st.query_params["d"] = d
    st.session_state["dev"] = d
    return d


def leave_room(dev: str):
    store = get_store()
    with store.lock:
        store.last_room.pop(dev, None)
    st.session_state.pop("room_code", None)
    for k in [k for k in st.session_state if k.startswith(("genre_", "text_"))]:
        st.session_state.pop(k, None)
    st.rerun()


# ─────────────────────────────────────────────────────────────
# 홈 (FR-01, FR-02)
# ─────────────────────────────────────────────────────────────
def view_home(dev: str):
    st.caption("오늘의 일상을 한 줄 쓰면, AI가 장르 소설로 바꿔 줘요. 익명으로 돌려 읽고 1등을 뽑아요.")
    tab_create, tab_join = st.tabs(["방 만들기", "방 입장"])

    with tab_create:
        hours = DEFAULT_VOTE_HOURS
        if SHOW_VOTE_HOURS_SELECT:  # FR-11 (MVP에서는 숨김)
            hours = st.radio("투표 시간", VOTE_HOURS_OPTIONS,
                             index=VOTE_HOURS_OPTIONS.index(DEFAULT_VOTE_HOURS),
                             format_func=lambda h: f"{h}시간", horizontal=True)
        st.write("방을 만들면 6자리 코드가 생겨요. 코드를 지인에게 알려 주세요.")
        if st.button("방 만들기", type="primary", use_container_width=True):
            code = create_room(dev, hours)
            if code:
                st.session_state["room_code"] = code
                st.rerun()
            else:
                st.error("잠시 후 다시 시도해 주세요")

    with tab_join:
        with st.form("join_form", clear_on_submit=False):
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


# ─────────────────────────────────────────────────────────────
# 입력 단계 (FR-03, FR-04, FR-05)
# ─────────────────────────────────────────────────────────────
@st.fragment(run_every=POLL_SEC)
def live_panel(code: str, dev: str, shown_phase: str):
    """제출 현황 + 방장 '투표 시작' 버튼. 단계가 바뀌면 전체 화면을 갱신."""
    room, _ = find_room(code)
    if room is None or effective_phase(room) != shown_phase:
        st.rerun()
        return
    n, pend = len(room["stories"]), len(room["pending"])
    info = f"제출된 일상 {n}건 · 참여자 {len(room['members'])}명"
    if pend:
        info += f" · 변환 중 {pend}건"
    st.caption(info)

    if room["host"] == dev:
        if n == 0:
            st.caption("아직 제출된 일상이 없어요")
        if st.button("투표 시작", type="primary", disabled=(n == 0 or pend > 0),
                     key=f"start_{code}", use_container_width=True,
                     help="입력을 마감하고 익명 투표를 시작해요"):
            ok, msg = start_vote(room, dev)
            if ok:
                st.rerun()
            else:
                st.error(msg)


def view_input(code: str, room: dict, dev: str):
    live_panel(code, dev, "input")

    sid, mine = story_of(room, dev)
    if mine:
        st.success("제출 완료! 방장이 투표를 시작하면 알려 드려요(자동으로 화면이 바뀌어요).")
        with st.container(border=True):
            st.markdown(f"**내 작품** · {mine['genre']}")
            st.markdown(md_safe(mine["text"]))
        st.caption("원문은 저장하지 않으며, 다른 사람에게 작성자는 보이지 않아요.")
        return

    st.subheader("오늘의 일상")
    genre = st.radio("장르", list(GENRES), index=None, horizontal=True, key=f"genre_{code}")
    text = st.text_area(
        "한두 줄로 적어 주세요", max_chars=MAX_CHARS, height=130, key=f"text_{code}",
        placeholder="예: 점심에 회사 앞 국밥집에서 동료랑 국밥을 먹고 커피를 사 마셨다.",
    )
    n = len(text.strip())
    st.caption(f"{n}/{MAX_CHARS}자 (공백 포함 {MIN_CHARS}~{MAX_CHARS}자) · 바깥을 누르면 글자수가 갱신돼요")
    st.info("방 코드를 아는 사람은 누구나 들어올 수 있어요. 민감한 일상(실명, 연락처 등)은 적지 마세요.")

    label = "다시 시도" if st.session_state.get("last_failed") == code else "소설로 바꾸기"
    if st.button(label, type="primary", use_container_width=True):
        if genre is None:
            st.warning("장르를 골라 주세요")
        elif not (MIN_CHARS <= n <= MAX_CHARS):
            st.warning(f"{MIN_CHARS}자 이상 {MAX_CHARS}자 이하로 적어 주세요 (지금 {n}자)")
        elif not get_api_key():
            st.error(MSG_AI_OFF)
        else:
            with st.spinner("AI가 소설을 쓰는 중이에요… (보통 10초 안팎)"):
                ok, msg = submit_story(room, dev, genre, text.strip())
            if ok:
                st.session_state.pop("last_failed", None)
                st.rerun()
            else:
                st.session_state["last_failed"] = code
                st.error(msg)  # 원문은 입력창에 그대로 남아 있음


# ─────────────────────────────────────────────────────────────
# 투표 단계 (FR-06)
# ─────────────────────────────────────────────────────────────
@st.fragment(run_every=POLL_SEC)
def view_vote(code: str, dev: str):
    room, _ = find_room(code)
    if room is None or effective_phase(room) != "vote":
        st.rerun()
        return

    remain = room["vote_end"] - now()
    st.caption(f"투표 종료 {fmt_time(room['vote_end'])} (남은 시간 {fmt_remaining(remain)}) · 종료 전에는 득표 현황이 보이지 않아요")

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
            st.markdown(f"**작품 {i}** · {s['genre']}")
            st.code(s["text"],language=None, wrap_lines=True)
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


# ─────────────────────────────────────────────────────────────
# 결과 단계 (FR-07 ~ FR-09)
# ─────────────────────────────────────────────────────────────
@st.fragment(run_every=POLL_SEC)
def illust_area(code: str, dev: str):
    """FR-08: 처음 접속한 기기가 '생성 중'으로 선점해 삽화를 만들고, 모두가 같은 그림을 본다."""
    room, _ = find_room(code)
    if room is None:
        st.rerun()
        return
    store = get_store()
    winners, top = tally(room)
    if not winners:
        return
    il = room["illust"]
    failed_here = st.session_state.get(f"illust_fail_{code}", False)

    claim = False
    with store.lock:
        if il["status"] == "generating" and now() - il["started"] > ILLUST_STALE_SEC:
            il["status"] = "waiting"  # 3분 넘게 멈춘 선점 해제
        if (il["status"] == "waiting" and il["attempts"] < ILLUST_MAX_ATTEMPTS
                and not failed_here and get_api_key()):
            il["status"], il["by"], il["started"] = "generating", dev, now()
            il["attempts"] += 1
            claim = True

    if claim:
        win = room["stories"][winners[0]]  # 공동 1등이면 먼저 제출한 작품
        story, genre = win["text"], win["genre"]
        with st.spinner("1등 작품의 삽화를 그리는 중이에요…"):
            try:
                img, mime = gemini_image(build_illust_prompt(story, genre))
                with store.lock:
                    il.update(status="done", image=img, mime=mime)
            except (AIError, AIBlocked, AIUnavailable, ValueError):
                with store.lock:
                    il["status"] = "waiting"  # 소설만 먼저 보여주고 다음 접속자가 재시도
                st.session_state[f"illust_fail_{code}"] = True
                failed_here = True

    if il["status"] == "done" and il["image"]:
        st.image(il["image"], use_container_width=True)
        ext = "jpg" if "jpeg" in (il["mime"] or "") else "png"
        st.download_button("이미지 저장", data=il["image"], file_name=f"{code}_삽화.{ext}",
                           mime=il["mime"] or "image/png", use_container_width=True)  # FR-09
    elif il["status"] == "generating":
        st.info("그림을 만드는 중이에요")
    elif not get_api_key():
        st.caption("지금은 그림을 만들 수 없어요")
    elif il["attempts"] >= ILLUST_MAX_ATTEMPTS:
        st.caption("그림을 만들지 못했어요")
    else:
        st.info("그림을 만드는 중이에요")
        if failed_here and st.button("그림 다시 만들기", key=f"illust_retry_{code}"):
            st.session_state[f"illust_fail_{code}"] = False
            st.rerun(scope="fragment")


def view_closed(code: str, room: dict, dev: str):
    if not room["stories"]:
        st.info("작품이 없어요")
        return
    winners, top = tally(room)

    if top == 0:
        if len(room["stories"]) == 1:  # 작품 1건뿐이면 그 작품을 1등으로 공개
            winners = list(room["stories"])
            st.subheader("🏆 오늘의 1등")
            s = room["stories"][winners[0]]
            with st.container(border=True):
                st.markdown(f"{s['genre']} · **0표** (투표 없이 단독 1등)")
                st.code(s["text"], language=None, wrap_lines=True)
            st.caption("투표가 없어 삽화는 만들지 않았어요")
        else:
            st.info("투표가 없어 결과가 없어요")
        return

    st.subheader("🏆 오늘의 1등" + (" (공동 1등)" if len(winners) > 1 else ""))
    for sid in winners:
        s = room["stories"][sid]
        with st.container(border=True):
            st.markdown(f"{s['genre']} · **{top}표**")
            st.code(s["text"], language=None, wrap_lines=True)
            if s["author"] == dev:
                st.caption("🎉 내가 쓴 작품이에요!")
    illust_area(code, dev)  # 소설 맨 끝에 삽화 삽입
    st.caption("2등 이하는 공개하지 않아요")


# ─────────────────────────────────────────────────────────────
# 방 화면
# ─────────────────────────────────────────────────────────────
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
        st.code(code, language=None)  # 복사 버튼 제공
    st.divider()

    if phase == "input":
        view_input(code, room, dev)
    elif phase == "vote":
        view_vote(code, dev)
    else:
        view_closed(code, room, dev)


# ─────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="일상 릴스토리", page_icon="📖", layout="centered")
    dev = init_identity()
    st.title("📖 일상 릴스토리")
    if APP_ENV != "prod":
        st.caption(f"환경: {APP_ENV} · AI 키: {'있음' if get_api_key() else '없음'}")

    store = get_store()
    code = st.session_state.get("room_code") or store.last_room.get(dev)  # 새로고침 복구
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

# ─────────────────────────────────────────────────────────────
# NOTES
# - 익명성은 "화면 수준"입니다(6장). 작성자 기기ID는 서버 메모리에만 있고 화면에는 나가지 않습니다.
# - 기기ID는 URL(?d=...)에 보관됩니다. 주소창 URL을 다른 사람에게 공유하면 같은 사람으로
#   인식되므로, 공유는 반드시 '방 코드'로만 하세요.
# - 방장 기기를 잃으면 복구하지 않습니다(MVP).
# - 일상 원문은 서버에 저장하지 않고, 변환 요청 시점에만 AI로 전달됩니다.
# ─────────────────────────────────────────────────────────────