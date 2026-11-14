import { useState } from "react";
import styles from "./HomePage.module.css";

const EXAMPLES = ["사내 회의실 예약", "반려견 산책 기록 앱", "팀 점심 투표 봇", "중고책 거래 게시판"];

const HOW = [
  { n: "01 / 말하기", t: "아이디어 한 줄", d: "전문 용어 없이 만들고 싶은 걸 적어요. 막연해도 괜찮아요." },
  { n: "02 / 답하기", t: "골라서 답하는 인터뷰", d: "번호 버튼과 추천 표시로 빠르게. 선택지에 없으면 직접 입력." },
  { n: "03 / 넘기기", t: "폴더째 Claude Code로", d: "spec.md · AGENTS.md · SKILL.md가 담긴 폴더를 받아 그대로 실행." },
];

const WORDS = ["spec.md", "AGENTS.md", "SKILL.md", "CLAUDE.md", "spec.md"];
const MARQUEE = ["spec.md", "AGENTS.md", "SKILL.md", "CLAUDE.md", "Claude Code", "Codex"];

type Props = { initialText: string; error: string | null; onStart: (request: string) => void };

export function HomePage({ initialText, error, onStart }: Props) {
  const [text, setText] = useState(initialText);
  const idea = text.trim();
  const start = () => {
    if (idea) onStart(idea);
  };

  return (
    <>
      <main className={styles.main}>
        <div aria-hidden="true" className={`${styles.orbit} orbit`}>
          <span className={styles.planet} />
          <span className={styles.moon} />
        </div>

        <p className={`${styles.badge} rise`}>
          <span className={styles.tag}>FOR VIBE CODERS</span>
          코드는 Claude Code가, 설계도는 우리가.
        </p>

        <h1 className={styles.hero}>
          <span className="rise d1">만들고 싶은 걸</span>
          <span className="rise d2">말하면,</span>
          <span className={`${styles.heroLast} rise d3`}>
            <span className={styles.window} aria-hidden="true">
              <span className={`${styles.words} rot`}>
                {WORDS.map((word, i) => (
                  <span key={i}>{word}</span>
                ))}
              </span>
            </span>
            <span className="sr-only">설계 문서</span>
            <span>가 된다.</span>
          </span>
        </h1>

        <p className={`${styles.lead} rise d4`}>
          채팅으로 몇 가지 질문에 답하면 기획 스펙, 작업자 규칙, 스킬 문서를 한 폴더로 묶어 드립니다. 받은 폴더를 그대로
          Claude Code에 넘기면 끝.
        </p>

        <form
          className={`${styles.field} rise d5`}
          onSubmit={(e) => {
            e.preventDefault();
            start();
          }}
        >
          <span aria-hidden="true" className={styles.prompt}>
            &gt;
          </span>
          <input
            aria-label="만들고 싶은 프로그램"
            className={styles.input}
            value={text}
            placeholder="예: 우리 동네 헬스장 PT 예약 앱"
            autoComplete="off"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              // 한글 조합 중의 Enter 는 글자를 확정하는 키다 — 제출로 받으면 마지막 글자가 잘린다.
              if (e.key === "Enter" && e.nativeEvent.isComposing) e.preventDefault();
            }}
          />
          <button type="submit" className={`${styles.go} btn`} disabled={!idea}>
            설계 시작
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        </form>
        {error && (
          <p className={styles.error} role="alert">
            {error} 다시 시도해 주세요.
          </p>
        )}

        <div className={`${styles.examples} rise d6`}>
          <span className={styles.examplesLabel}>이런 것도 돼요</span>
          {EXAMPLES.map((example) => (
            <button key={example} type="button" className={`${styles.chip} btn`} onClick={() => setText(example)}>
              {example}
            </button>
          ))}
        </div>

        <section className={`${styles.how} rise d6`} aria-label="어떻게 동작하나요">
          {HOW.map((item) => (
            <div key={item.n} className={styles.howItem}>
              <span className={styles.howNo}>{item.n}</span>
              <span className={styles.howTitle}>{item.t}</span>
              <span className={styles.howDesc}>{item.d}</span>
            </div>
          ))}
        </section>
      </main>

      <div aria-hidden="true" className={styles.band}>
        <div className={`${styles.bandTrack} marq`}>
          {[...MARQUEE, ...MARQUEE].map((word, i) => (
            <span key={i} className={styles.bandItem}>
              {word}
              <span className={styles.diamond} />
            </span>
          ))}
        </div>
      </div>
    </>
  );
}
