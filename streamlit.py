import streamlit as st
import random
import string

# ----------------------
# Session State
# ----------------------

if "rooms" not in st.session_state:
    st.session_state.rooms = {}

if "stories" not in st.session_state:
    st.session_state.stories = {}

# ----------------------
# Title
# ----------------------

st.title("📖 Fablo")

menu = st.sidebar.radio(
    "메뉴",
    [
        "방 생성",
        "방 참여",
        "일상 작성"
    ]
)

# ----------------------
# 방 생성
# ----------------------

if menu == "방 생성":

    st.header("🏠 방 생성")

    room_name = st.text_input("방 이름")

    if st.button("방 만들기"):

        room_id = ''.join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )

        st.session_state.rooms[room_id] = {
            "name": room_name,
            "participants": []
        }

        st.success("방 생성 완료!")

        st.write("방 코드")

        st.code(room_id)

# ----------------------
# 방 참여
# ----------------------

elif menu == "방 참여":

    st.header("🚪 방 참여")

    room_id = st.text_input("방 코드")

    nickname = st.text_input("닉네임")

    if st.button("입장하기"):

        if room_id in st.session_state.rooms:

            if nickname not in st.session_state.rooms[room_id]["participants"]:

                st.session_state.rooms[room_id]["participants"].append(
                    nickname
                )

            st.success("입장 완료!")

        else:
            st.error("존재하지 않는 방입니다.")

# ----------------------
# 일상 작성
# ----------------------

elif menu == "일상 작성":

    st.header("📝 오늘의 일상")

    room_id = st.text_input("방 코드")

    nickname = st.text_input("닉네임")

    diary = st.text_area(
        "오늘 하루를 적어보세요",
        height=150,
        max_chars=150
    )

    genre = st.selectbox(
        "장르 선택",
        [
            "판타지",
            "무협",
            "로맨스 판타지"
        ]
    )

    if st.button("제출"):

        if room_id not in st.session_state.rooms:

            st.error("존재하지 않는 방입니다.")

        else:

            if room_id not in st.session_state.stories:
                st.session_state.stories[room_id] = []

            st.session_state.stories[room_id].append(
                {
                    "nickname": nickname,
                    "genre": genre,
                    "diary": diary
                }
            )

            st.success("제출 완료!")

# ----------------------
# 방 목록
# ----------------------

st.divider()

st.subheader("🏠 생성된 방")

for room_id, room in st.session_state.rooms.items():

    st.write(f"### {room['name']}")
    st.write(f"방 코드 : {room_id}")

    st.write("참여자")

    if len(room["participants"]) == 0:
        st.write("- 없음")

    else:
        for user in room["participants"]:
            st.write(f"✅ {user}")

# ----------------------
# 제출된 일상
# ----------------------

st.divider()

st.subheader("📚 제출된 일상")

for room_id, stories in st.session_state.stories.items():

    st.write(f"### 방 코드 : {room_id}")

    for story in stories:

        st.info(
            f"""
닉네임 : {story['nickname']}

장르 : {story['genre']}

일상 :
{story['diary']}
"""
        )
