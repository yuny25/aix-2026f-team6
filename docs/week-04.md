# 4주차 활동지 / Week 4 Worksheet

**주제 선택과 요구 명세 / Choosing a problem & writing the spec**

- 작성일 / Date: 2026년 9월 23일
- 참여자 / Present: 장윤영, 김현승, 박정하, 이다현

---

## ① 주제 선택 / Choosing one problem

| 항목 Item | 내용 |
|---|---|
| 선택한 주제 Chosen | 멤버 간 중간 지점의 번화가를 추천해주는 서비스 |
| 선택 근거 Why | 후보중에 가장 painpoint와 성공기준이 명확함 |

## ② 성공 기준 가져오기 / Success criteria from Week 3

| 3주차 성공 기준 원문 Original (Week 3) | 모호한 표현 Vague words |
|---|---|
| *(예시) 학생들이 과제 제출 현황을 쉽게 확인할 수 있다* | *쉽게, 확인할 수 있다* |
| 각자의 거주지에서 중간 지점의 번화가를 찾아 약속 장소로 지정할 수 있다 | 중간 지점, 번화가, 약속 장소로 지정 |

## ③ Acceptance Criteria

최소 정상 경로 2개 + 실패 경로 1개. **판정 방법** 칸이 비면 아직 명세가 아닙니다.
At least two normal paths + one failure path. If "How to check" is empty, it is not yet a spec.

| # | 경로 Path | EARS 문장 Sentence | 판정 방법 How to check |
|---|---|---|---|
| *예시* | *정상* | *WHEN 학생이 과제 목록을 열면 THE 시스템은 SHALL 과목별 미제출 과제를 마감일 순으로 표시한다* | *미제출 과제 3건을 만든 뒤 목록을 열어 마감일 순으로 나오는지 확인* |
| AC-1 | 정상 Normal | WHEN 멤버가 거주지를 입력하면 THE 시스템은 SHALL 이동시간 차이가 30분 이내인 중간 지점을 계산한다  | 서로 다른 위치(예: 서울 강남, 인천 부평)를 입력했을 때 이동시간 차이가 30분 이내인 후보지가 제시되는지 확인 |
| AC-2 | 정상 Normal | WHEN 중간 지점이 계산되면 THE 시스템은 SHALL 음식점·카페·놀거리 등 최소 5곳 이상을 표시한다  | 테스트 데이터로 해당 지점 주변 상권 정보를 불러와 5곳 이상이 표시되는지 확인 |
| AC-3 | 정상 Normal | WHEN 후보 지점이 여러 개일 경우 THE 시스템은 SHALL 상권 수와 교통 편의성을 기준으로 순위를 매겨 추천한다 | 동일 조건의 후보지가 2곳 이상일 때 상권 수와 교통 접근성을 기준으로 순위가 매겨지는지 확인 |
| AC-4 | 정상 Normal | WHEN 사용자가 특정 상권 유형(예: 카페 중심)을 선호한다고 설정하면 THE 시스템은 SHALL 해당 유형을 우선적으로 반영한다 | 카페 선호 옵션을 선택했을 때 추천 결과에 카페가 우선적으로 포함되는지 확인 |
| AC-5 | 실패 Failure | IF 이동시간 차이가 30분을 초과하거나 주변 상권이 5곳 미만이면 THEN THE 시스템은 SHALL 약속 장소를 추천하지 않고 대체 안내 메시지를 제공한다  | 거주지를 극단적으로 멀리 입력하거나 상권이 적은 지역을 선택했을 때 “조건을 만족하는 장소 없음” 메시지가 출력되는지 확인 |
| AC-6 | 실패 Failure | IF 입력된 주소가 잘못되거나 존재하지 않으면 THEN THE 시스템은 SHALL 오류 메시지를 제공하고 재입력을 요청한다 | 잘못된 주소(예: “서울 없음동”)를 입력했을 때 오류 메시지가 표시되는지 확인 |
| AC-7 | 실패 Failure | IF 네트워크 오류로 상권 데이터를 불러올 수 없으면 THEN THE 시스템은 SHALL 기본 메시지를 제공하고 재시도를 안내한다 | 인터넷 연결을 끊은 상태에서 검색했을 때 “데이터를 불러올 수 없음” 메시지가 출력되는지 확인 |

> 확인할 동작이 더 있으면 AC-4부터 행을 추가해 쓰십시오.
> If there are more behaviors to check, add rows from AC-4.

- [x] 이번 활동에서 AI를 사용했다면 `PROMPTS.md`에 기록했습니다 / Logged any AI use in `PROMPTS.md`

---

> 수업 종료 시 커밋하세요 / Commit this at the end of class
> `git add docs/week-04.md && git commit -m "docs: 4주차 활동지 작성"`
