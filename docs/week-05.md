# 5주차 활동지 / Week 5 Worksheet

**1-page 기획서 / One-page plan**

- 작성일 / Date: 26.09.30
- 참여자 / Present: 장윤영, 김현승, 박정하, 이다현

---

## ① 주제 확정 / Confirm topic

- 확정 주제 / Topic: 멤버 간 중간 지점의 번화가를 추천해주는 서비스
- 이유 / Reason: 나온 아이디어 중 구현 가능성이 가장 높고 장소를 정하는 데 어려움을 겪는 사용자 집단이 실제로 존재함을 확인했다.

---

## ② 태스크 분해와 의존 관계 / Tasks and dependencies

### 태스크 목록 / Task list

4주차 사용자 스토리와 완료 조건을 태스크로 나눕니다.
*Break down your Week 4 user stories and acceptance criteria into tasks.*

각 태스크는 따로 끝내도 맞는지 확인할 수 있어야 합니다. 담당에 '다 같이'는 쓰지 않습니다.
*Each task must be checkable on its own. Do not write "everyone" as owner.*

| # | 태스크 Task | 완료 조건 Done when | 선행 태스크 Depends on | 담당 Owner |
|---|---|---|---|---|
| 1. | 출발지 입력 및 좌표 변환 기능 | 출발지 입력창과 버튼 정상 동작, 위도/경도 반환 성공 |  | 장윤영 |
| 2. | 중간지점 계산 및 지도 표시 | 4개 봐표 평균값 계산 성공, 근처 지하철역/핵심지역 반환, 지점 표시 | 1. | 김현승 |
| 3. | 중간지점 주변 식당, 카페, 놀거리 검색 | 식장, 카페, 문화시설 검색, 집계 및 표시 | 2. | 박정하 |
| 4. | 생성형 AI 기반 최종 약속장소 및 일정 추천 | AI 응답 정상 수신, 시간대 별로 코스 추천 가능 | 3. | 이다현 |
| 5. | 전체 기능 통합, 예외 처리 및 테스트 | 서울/경기/지방 최소 3개 이상 테스트 완료 및 무료 배포와 정상 작동 확인 | 4. | 박정하 |

### 의존 관계 그래프 / Dependency graph (DAG)

화살표는 "앞 태스크가 끝나야 뒤 태스크를 할 수 있다"는 뜻입니다.
*An arrow means the first task must finish before the second can start.*

**그리는 방법 / How to draw**
- 아래 예시에서 상자 이름을 바꾸고, 선후 관계 하나마다 화살표(`-->`) 줄을 하나씩 추가합니다. GitHub에서 파일을 열면 그림으로 보입니다. 미리 보려면 mermaid.live에 붙여 넣으세요.
  *Rename the boxes and add one `-->` line per dependency. GitHub shows it as a diagram. Preview at mermaid.live.*
- 태스크 표를 AI에게 주고 "Mermaid 그래프로 바꿔 줘"라고 요청해도 됩니다.
  *You can also give the task table to AI and ask "Convert this into a Mermaid graph."*
- 어려우면 종이에 그려 사진을 `docs/images/`에 올리고 `![DAG](images/week-05-dag.jpg)`로 넣어도 됩니다.
  *Or draw it on paper, upload the photo to `docs/images/` and link it with `![DAG](images/week-05-dag.jpg)`.*

```mermaid
graph LR
  T1["#1 태스크명"] --> T3["#3 태스크명"]
  T2["#2 태스크명"] --> T3
```

- 지금 착수 가능 (진입 차수 0) / Can start now (in-degree 0): 
- 작업 순서 (위상정렬) / Work order (topological sort): 
- 사이클이 있었다면 어떻게 풀었는가 / If there was a cycle, how did you fix it?: 

---

## ③ 범위 결정 / Scope

### Must — 없으면 성립 안 됨 / essential

핵심 시나리오 1개가 끝까지 동작하는 데 필요한 것만 / *Only what the core scenario needs to work end-to-end*

- 핵심 시나리오 / Core scenario:
1. 출발지 입력받기
2. 출발지 기반 중간지점(일정 면적. 평수) 계산
3. 나온 중간지점에 존재하는 식당, 카페, 놀거리 위치, 개수 표시
4. 생성형AI로 최종약속장소 추천 (시간기반)

  



### Should (없을 경우에는 작성하지 마세요)
 
 - 시나리오



### Could (없을 경우에는 작성하지 마세요)

 - AI 기반 최종 장소 추천 시 어떤 기준으로 추천할지 선택

### **Won't — 이번 학기에 안 함 / not this semester**

| Won't 항목 Item | 포기한 이유 Why |
|---|---|
| 회원가입, 로그인 기능 | 기한 내에 불가, 반드시 필요한 기능이 아님 |
| 자주 만나는 사용자 그룹화 | 로그인 기능이 선행되어야 함 |

### 실행 가능성 확인 / Feasibility check

- 특수 장비·유료 API·실제 개인정보가 필요한가? 필요하다면 대안은?
  *Does it need special hardware, paid APIs or real personal data? If so, what is the alternative?*
- 15주차에 발표장에서 시연할 수 있는 형태인가?
  *Can it be demonstrated live in Week 15?*

---

## ④ 가장 먼저 동작시킬 흐름 (Walking Skeleton) / First end-to-end flow

예 / Example: 과제 ID를 입력하면 → LMS에서 제출 기록을 받아 와서 → 화면에 제출 인원 숫자 하나가 뜬다

> [무엇을 입력하면] → [무엇을 처리해서] → [화면에 무엇이 나온다]
>
> 거주지를 입력하면 -> 거리를 측정해서 -> 중간 거리에 있는 번화가가 뜬다

---

> 수업 종료 시 커밋하세요 / Commit this at the end of class
> `git add docs/week-05.md && git commit -m "docs: 5주차 활동지 작성"`
