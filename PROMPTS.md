# AI 협업 기록 / AI Collaboration Log

작성 원칙: 프롬프트 나열이 아니라 **판단 근거**를 남긴다.
Principle: record your **reasoning**, not just prompts.

---

## [이슈 #__] 제목 / Title

**목표(스펙) / Spec**
- 입력 Input:
- 처리 Processing:
- 출력 Output:
- 실패 조건 Failure:

**요청한 프롬프트 요지 / Prompt (summary)**

**결과에 대한 판단 / Decisions**
- 채택한 부분과 이유 / Accepted, because:
- 수정한 부분과 이유 / Changed, because:
- 폐기한 부분과 이유 / Rejected, because:

**검증 방법 / How it was verified**

---
(이슈 단위로 반복 / repeat per issue)

---
## 2026-09-09 · 메모 검색 기능 (2주차 활동)

**지시**
[지시]

메모 검색 기능을 추가해줘. 제목과 본문에서 키워드로 검색된다.



[규약]

# 프로젝트 규약



이 문서는 코드를 작성할 때 지켜야 할 규칙입니다.



## 계층 분리



- `routes.js`는 HTTP 요청과 응답만 다룹니다. SQL을 직접 쓰지 않습니다.

- 데이터베이스 접근은 `service.js`에만 둡니다.



## 응답 형식



모든 응답은 다음 두 형태 중 하나입니다.



```json

{ "ok": true,  "data": ... }

{ "ok": false, "error": "ERROR_CODE" }

```



에러 코드는 대문자와 밑줄로 씁니다. (예: `MEMO_NOT_FOUND`)



## 명명 규칙



- 함수명은 동사로 시작합니다. `list`, `get`, `create`, `update`, `remove`

- 데이터베이스 컬럼은 스네이크 케이스를 씁니다. `user_id`, `created_at`

- 자바스크립트 변수는 카멜 케이스를 씁니다. `userId`, `createdAt`



## 입력 검증



- 사용자 입력은 반드시 검증합니다.

- 검증에 실패하면 400과 함께 `{ ok: false, error }` 를 반환합니다.



## 권한



- 모든 조회와 수정은 **본인 소유 데이터로 한정**합니다.

- 모든 쿼리에 `user_id` 조건을 포함합니다.



[근거]

[schema.sql]
-- memo-seed 데이터베이스 스키마

CREATE TABLE users (
  id         INTEGER PRIMARY KEY,
  email      TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE memos (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL,
  title      TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_memos_user ON memos(user_id);


[service.js]
const db = require('./db');

/**
 * 사용자의 메모 목록을 최신순으로 조회한다.
 */
function listMemos(userId) {
  return db.all(
    `SELECT id, title, created_at
       FROM memos
      WHERE user_id = ?
      ORDER BY created_at DESC`,
    [userId]
  );
}

/**
 * 메모 한 건을 조회한다. 본인 메모가 아니면 null을 반환한다.
 */
function getMemo(userId, memoId) {
  return db.get(
    `SELECT id, title, body, created_at
       FROM memos
      WHERE id = ? AND user_id = ?`,
    [memoId, userId]
  );
}

/**
 * 메모를 생성한다.
 */
function createMemo(userId, title, body) {
  return db.run(
    `INSERT INTO memos (user_id, title, body, created_at)
     VALUES (?, ?, ?, datetime('now'))`,
    [userId, title, body]
  );
}

module.exports = { listMemos, getMemo, createMemo };

[routes.js]
const express = require('express');
const service = require('./service');

const router = express.Router();

// 메모 목록 조회
router.get('/memos', async (req, res) => {
  const memos = await service.listMemos(req.user.id);
  res.json({ ok: true, data: memos });
});

// 메모 단건 조회
router.get('/memos/:id', async (req, res) => {
  const memo = await service.getMemo(req.user.id, req.params.id);

  if (!memo) {
    return res.status(404).json({ ok: false, error: 'MEMO_NOT_FOUND' });
  }

  res.json({ ok: true, data: memo });
});

// 메모 생성
router.post('/memos', async (req, res) => {
  const { title, body } = req.body;

  if (!title || !body) {
    return res.status(400).json({ ok: false, error: 'TITLE_AND_BODY_REQUIRED' });
  }

  const result = await service.createMemo(req.user.id, title, body);
  res.status(201).json({ ok: true, data: { id: result.lastID } });
});

module.exports = router;



[종료조건]

- GET /memos/search?q=키워드 로 호출된다

- 제목 또는 본문에 키워드가 포함된 메모만 반환한다

- 본인 메모만 반환한다

- q가 비어 있으면 400과 { ok: false, error } 를 반환한다 


**채택 여부**
(전체 채택 / 일부 채택 — 무엇을 어떻게 수정했는지 / 미채택)
일부 채택 - CONVENTIONS.md 위반 항목을 1개로 재조정


---

## 2026-09-23 · 요구 명세 작성 (4주차 활동)


**요청한 프롬프트 요지 / Prompt (summary)**

질문 : 각자의 거주지에서 중간 지점의 번화가를 찾아 약속 장소로 지정할 수 있다 이게 성공기준인데 위 문장에서 모호한 표현을 찾아서 모호하지 않게 변경해줘

답변 : 모호한 표현은 **“중간 지점”**, **“번화가”**, **“약속 장소로 지정”** 정도야.

성공기준으로 더 명확하게 바꾸면:

> **각자의 거주지에서 이동시간 차이가 10분 이내인 지역 중, 주변에 음식점·카페 등이 3곳 이상 있는 장소를 약속 장소로 지정할 수 있다.**


**결과에 대한 판단 / Decisions**

전체적인 틀을 채택하고 상황에 맞게 표현을 수정했다.

변경된 성공 기준 : 각자 거주지에서 이동시간의 차이가 30분 이내이면서 동시에 음식점, 카페, 놀거리 등이 도합 5곳 이상인 곳을 찾아 약속 장소로 지정할 수 있다


**요청한 프롬프트 요지 / Prompt (summary)**

질문 : 
선택한 주제 : 멤버 간 중간 지점의 번화가를 추천해주는 서비스
성공 기준 : 각자 거주지에서 이동시간의 차이가 30분 이내이면서 동시에 음식점, 카페, 놀거리 등이 도합 5곳 이상인 곳을 찾아 약속 장소로 지정할 수 있다. 를 기준으로 작성해줘

**결과에 대한 판단 / Decisions**

---
