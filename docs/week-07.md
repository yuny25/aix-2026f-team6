# Week 07 팀 활동지 / Team Activity

| 팀명 / Team | 작성일 / Date | 참여자 / Members |
|---|---|---|
| 6팀 | 10-14 | 장윤영,김현승,이다현,박정하 |

## 1. 아키텍처 다이어그램 / Architecture Diagram

손그림 사진을 올리고 링크하십시오 / Upload a photo and link it.

![architecture](img/week-07-arch.png)

| 계층 / Layer | 모듈·파일 / Modules | 의존하지 않는 것 / Does not depend on |
|---|---|---|
| 표현 / Presentation | 방 생성, 일상 작성, 소설 조회, 투표, 결과 공유 UI | DB, API 세부 구현 |
| 로직 / Logic | AI 소설 생성, 투표 처리, 우승작 선정, 삽화 생성 | 화면 UI |
| 데이터 / Data | Open AI API 연동, 이미지 생성 API 연동, 저장소 관리 | UI |

## 2. 이슈 / Issues

> 이슈 = **앞으로 할 일** / An issue is work to be done.
> 개발할 때 커밋에 이슈 번호를 붙이고(`#3 알레르기 필터 추가`), 완료 조건을 만족하면 이슈를 닫습니다.
> Add the issue number to commits, and close the issue when its criteria are met.

| # | 제목 / Title | 라벨 / Label | 담당 / Assignee | 완료 조건 / Acceptance Criteria |
|---|---|---|---|---|
| #1 | 방 생성 및 참여 시스템 구축 | frontend, backend | 이다현 | 방 생성, 초대, 참여가 가능 |
| #2 | 일상 입력 및 장르 선택 기능 구축 | frontend | 김현승 | 일상 작성 및 장르 선택이 가능 |
| #3 | AI 소설 생성 시스템 구축 | AI, backend | 장윤영 | 입력된 일상이 소설로 변환, 저장 가능 |
| #4 | 익명 제출 및 마감 시스템 구축 | backend | 박정하 | 익명 제출, 마감 처리 가능 |
| #5 | 투표 시스템 구축 | frontend, backend | 이다현 | 투표, 결과 집계 가능 |
| #6 | AI 삽화 생성 시스템 구축 | AI, backend | 장윤영 | 우승작 기반 AI 삽화 생성 가능 |
| #7 | 결과물 저장 및 공유 기능 구축 | frontend | 박정하 | 삽화 저장, 공유 가능 |

## 3. 마일스톤 / Milestones

| 마일스톤 / Milestone | 마감 / Due | 포함 이슈 / Issues |
|---|---|---|
| MVP 완료 | 11주차 | #1 ~ #6 |
| 최종 배포 및 발표 준비 | 13주차 | #1 ~ #7 |

> AI를 사용했다면 `PROMPTS.md`에 기록 / Log any AI use in `PROMPTS.md`
