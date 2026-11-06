# 작업자 VOC — 왜 이 규칙들이 있는지

AGENTS.md 의 각 규칙 섹션이 어떤 불만에 대응하는지. 산출물 AGENTS.md 를 설계할 때의 근거.
(조사일 2026-11-06)

## 설문으로 확인된 것

| 불만 | 근거 | 대응 섹션 |
|---|---|---|
| "거의 맞는데 틀림" — 그럴듯하지만 비용이 드는 결과 | Stack Overflow 2025: 66%가 1위로 선택, 45%는 AI 코드 디버깅이 더 오래 걸린다고 답함 | 작업 절차(하드 게이트), 완료 보고 규칙 |
| 검증 병목 — 생성은 빨라졌지만 검증에 시간이 몰림 | Sonar 2026: 96%가 산출물을 완전히 신뢰하지 않음 | 완료 보고 규칙(실행 증거 필수), 태그 |
| 복잡한 작업에서 무너짐 | SO 2025: "복잡한 문제 처리 가능" 29% (전년 35%) | 작업 절차(분석→계획), 변경 범위 선언 |
| 에이전트 정확성·보안 우려 | SO 2025: 87% 정확성 우려, 81% 보안·프라이버시 우려 | 작업자 컨텍스트(개인정보 미포함) |

## 커뮤니티에서 반복되는 것

| 불만 | 대응 섹션 |
|---|---|
| 용어 불일치 — 작업자 내부 용어와 사용자 단어가 안 맞음, 세션 안에서도 이름이 바뀜 | **용어사전** |
| 질문 UX — 한 번에 여러 개, 선택지 없음, 번호 없음, 너무 자주 또는 안 물음 | **질문 규칙**, frontend 질문 UI |
| 컨텍스트·의도 증발 — 왜 이 코드가 있는지 아무도 모름 | docs/work/plan.md, 주석은 "왜"만 |
| 지시 드리프트 — 초반 제약을 몇 턴 뒤 잊음 | 제약 기록 (constraints.md) |
| 거짓 완료 보고 — 안 돌리고 "통과", 안 고치고 "수정" | 완료 보고 규칙 |
| 시키지 않은 것 수정 — 포맷·주석·리팩터 동반으로 diff 리뷰 불가 | 변경 범위 선언, 하지 말 것 |
| 과잉 엔지니어링 | 계획 단계 파일 목록, 질문 규칙(의존성 추가는 묻기) |
| 매 세션 재설명 비용 | 작업자 컨텍스트, 세션 시작 시 docs/work 읽기 |
| 토큰·요금 불안 — 어디서 예산이 나갔는지 모름 | 토큰 사용 규칙, 사이클별 토큰 기록 |
| 자율성 적정선 — "안 시키면 안 함" vs "완전 자율은 못 믿음" 양쪽 불만 | 질문 규칙(묻는 것/안 묻는 것), 결정 위임 범위 |

## 출처

- Stack Overflow 2025 Developer Survey (ADTmag 정리) — https://adtmag.com/blogs/watersworks/2026/01/stack-overflow-survey.aspx
- TechRepublic, Developer Trust in AI Declines — https://www.techrepublic.com/article/news-developer-trust-in-ai-declines/
- Sonar 2026 State of Code Developer Survey — https://community.sonarsource.com/t/results-from-the-2026-state-of-code-developer-survey-are-here/172502
- "Professional Software Developers Don't Vibe, They Control" (UCSD·Cornell, 2026-01) 정리 — https://ppc.land/why-expert-developers-refuse-to-vibe-with-ai-coding-tools/
- Product Hunt 스레드, Supervision fatigue 기사 등 커뮤니티 후기
