import { useEffect, useRef, useState, type ReactNode } from "react";
import type {
  Answer,
  AnswerSubmission,
  ConfirmItem,
  ConfirmReply,
  ConfirmScreen,
  Preview as PreviewData,
  Question,
  RunView,
} from "../api/types";
import { Preview } from "../components/Preview";
import { Visual } from "../components/Visual";
import type { Pending } from "../hooks/useRun";
import styles from "./StudioPage.module.css";

// question-format.md: 고정 선택지는 options 에 없고 화면이 항상 같은 문구로 붙인다.
export const DELEGATE_LABEL = "알아서 정해 주세요";

const CONFIRM_INTRO =
  "지금까지 들은 내용을 정리했어요. 잘못 이해한 게 있으면 “고칠래요”를 눌러 주세요. 그 항목만 다시 여쭤볼게요.";
const STALLED_TEXT = "중간에 멈췄어요. 지금까지 답한 내용은 그대로 있어요.";

// 이번 묶음에서 이미 답한 질문. 묶음을 다 답할 때까지 서버로 보내지 않고 화면에만 둔다.
type Local = { question: Question; answer: Answer; label: string };

type Message = { who: "bot" | "me"; text: string; preview?: PreviewData };

type Props = {
  view: RunView | null;
  screen: number;
  pending: Pending | null;
  error: string | null;
  request: string;
  onSubmit: (submission: AnswerSubmission) => void;
  onConfirm: (reply: ConfirmReply) => void;
  onRetry: () => void;
};

export function StudioPage({ view, screen, pending, error, request, onSubmit, onConfirm, onRetry }: Props) {
  // 새 화면(screen)이 오면 지난 묶음의 답은 버린다 — effect 로 지우지 않고 화면 번호가 다르면 빈 것으로 본다.
  const [draft, setDraft] = useState<{ screen: number; locals: Local[] }>({ screen, locals: [] });
  const locals = draft.screen === screen ? draft.locals : [];
  // 확인 화면에서 고치기로 고른 항목. 목록에서 고르고 도크의 버튼으로 보내므로 둘의 부모인 여기에 둔다.
  const [revise, setRevise] = useState<{ screen: number; ids: string[] }>({ screen, ids: [] });
  const picked = revise.screen === screen ? revise.ids : [];
  const toggleRevise = (id: string) =>
    setRevise({ screen, ids: picked.includes(id) ? picked.filter((p) => p !== id) : [...picked, id] });

  const bundle = view?.status === "question" ? view.bundle : null;
  const confirm = view?.status === "confirm" ? view.confirm : null;
  const generating = pending === "confirm";
  const current = bundle && locals.length < bundle.questions.length ? bundle.questions[locals.length] : null;
  const qa = view?.qa ?? [];

  const send = (action: AnswerSubmission["action"], list: Local[]) =>
    onSubmit({ action, answers: list.map((local) => local.answer) });

  const answer = (question: Question, value: Answer, label: string) => {
    const next = [...locals, { question, answer: value, label }];
    setDraft({ screen, locals: next });
    // 묶음의 마지막 질문에 답하면 한 번에 보낸다 — 서버 왕복은 묶음당 한 번이다.
    if (bundle && next.length === bundle.questions.length) send("submit", next);
  };

  const messages: Message[] = [];
  if (request) messages.push({ who: "me", text: request });
  for (const line of qa) {
    messages.push({ who: "bot", text: line.question }, { who: "me", text: line.answer });
  }
  for (const local of locals) {
    messages.push({ who: "bot", text: local.question.text }, { who: "me", text: local.label });
  }
  if (current && !pending) {
    messages.push({ who: "bot", text: current.text, preview: bundle?.preview ?? undefined });
  }
  if (confirm) messages.push({ who: "bot", text: CONFIRM_INTRO });
  if (view?.status === "stalled" && !pending) messages.push({ who: "bot", text: STALLED_TEXT });

  const asked = qa.length + locals.length;
  let progress = { width: "0%", label: "준비 중" };
  if (generating) progress = { width: "100%", label: "생성 중" };
  else if (confirm) progress = { width: "100%", label: "확인" };
  else if (bundle) {
    const ratio = Math.round((100 * locals.length) / bundle.questions.length);
    progress = { width: `${ratio}%`, label: current ? `질문 ${asked + 1}개째` : `질문 ${asked}개 답함` };
  }

  const scrollRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // 확인 화면은 목록이 길다 — 맨 아래가 아니라 안내 말풍선부터 읽게 한다.
    // scrollIntoView 는 페이지 전체까지 움직이므로 대화 영역의 스크롤 위치만 직접 맞춘다.
    if (confirm && scrollRef.current && confirmRef.current) {
      scrollRef.current.scrollTop = confirmRef.current.offsetTop - 24;
    }
  }, [confirm]);

  let dock;
  if (generating) {
    dock = (
      <Waiting>
        산출물을 만드는 중 — <span className={styles.accentMono}>spec.md · AGENTS.md · 스킬</span>
      </Waiting>
    );
  } else if (pending) {
    dock = <Waiting>{pending === "load" ? "불러오는 중이에요." : "답을 정리하고 있어요. 길면 1~2분 걸려요."}</Waiting>;
  } else if (current && bundle) {
    dock = (
      <QuestionDock
        key={current.id}
        question={current}
        number={asked + 1}
        position={`${locals.length + 1} / ${bundle.questions.length}`}
        canFinish={bundle.can_finish}
        onAnswer={(value, label) => answer(current, value, label)}
        onFinish={() => send("finish", locals)}
      />
    );
  } else if (bundle) {
    // 묶음을 다 답했는데 보내기가 실패한 경우 — 답은 화면에 남아 있다.
    dock = (
      <div className={styles.actions}>
        <button type="button" className={`${styles.primary} btn`} onClick={() => send("submit", locals)}>
          다시 보내기
        </button>
      </div>
    );
  } else if (confirm) {
    dock = <ConfirmDock screen={confirm} picked={picked} onReply={onConfirm} />;
  } else if (view?.status === "stalled") {
    dock = (
      <div className={styles.actions}>
        <button type="button" className={`${styles.primary} btn`} onClick={onRetry}>
          다시 시도
        </button>
      </div>
    );
  }

  return (
    <main className={styles.main}>
      <section aria-label="인터뷰" className={`${styles.chat} rise`}>
        <div className={styles.top}>
          <div className={styles.project}>
            <span className={styles.label}>PROJECT</span>
            <span className={styles.title}>{request || "불러오는 중"}</span>
          </div>
          <div className={styles.progress}>
            <div className={styles.track}>
              <div className={styles.bar} style={{ width: progress.width }} />
            </div>
            <span className={styles.progressLabel}>{progress.label}</span>
          </div>
        </div>

        <div ref={scrollRef} className={confirm ? styles.scroll : `${styles.scroll} ${styles.stickBottom}`}>
          <div className={styles.messages} role="log" aria-live="polite">
            {messages.map((message, i) =>
              message.who === "bot" ? (
                <div
                  key={i}
                  ref={confirm && i === messages.length - 1 ? confirmRef : undefined}
                  className={`${styles.bot} msg`}
                >
                  <Avatar />
                  <div className={styles.botBody}>
                    <div className={styles.botBubble}>{message.text}</div>
                    {message.preview && <Preview preview={message.preview} />}
                  </div>
                </div>
              ) : (
                <div key={i} className={`${styles.me} msg`}>
                  {message.text}
                </div>
              ),
            )}
            {pending && (
              <div className={`${styles.typing} msg`} role="status" aria-label="답을 기다리는 중">
                <Avatar />
                <div className={styles.dots}>
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              </div>
            )}
          </div>
          {confirm && !pending && <ConfirmList screen={confirm} picked={picked} onToggle={toggleRevise} />}
        </div>

        <div className={styles.dock}>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          {dock}
        </div>
      </section>

      <SidePanel generating={generating} lines={[...qa, ...locals.map(toLine)]} />
    </main>
  );
}

const toLine = (local: Local) => ({ question: local.question.text, answer: local.label });

function Avatar() {
  return (
    <div className={styles.avatar} aria-hidden="true">
      SB
    </div>
  );
}

function Waiting({ children }: { children: ReactNode }) {
  return (
    <div className={styles.waiting}>
      <svg className="spin" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--ac)" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true">
        <path d="M12 3a9 9 0 1 0 9 9" />
      </svg>
      <span>{children}</span>
    </div>
  );
}

type DockProps = {
  question: Question;
  number: number;
  position: string;
  canFinish: boolean;
  onAnswer: (answer: Answer, label: string) => void;
  onFinish: () => void;
};

function QuestionDock({ question, number, position, canFinish, onAnswer, onFinish }: DockProps) {
  const [picked, setPicked] = useState<string[]>([]);
  const [custom, setCustom] = useState("");
  const inputId = `custom-${question.id}`;

  const choose = (ids: string[]) => {
    const labels = question.options.filter((option) => ids.includes(option.id)).map((option) => option.label);
    onAnswer({ question_id: question.id, kind: "option", option_ids: ids }, labels.join(", "));
  };

  const pick = (optionId: string) => {
    // 하나만 고르는 질문은 누르는 즉시 답이 된다. 여러 개 고르는 질문은 모아 두었다가 "다음"으로 보낸다.
    if (!question.multiple) return choose([optionId]);
    setPicked((prev) => (prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId]));
  };

  const sendCustom = () => {
    const text = custom.trim();
    if (text) onAnswer({ question_id: question.id, kind: "custom", text }, text);
  };

  return (
    <div className={styles.question}>
      <span className={styles.label}>
        Q{number} · {position}
        {question.multiple && " · 여러 개 고를 수 있어요"}
      </span>
      <ol className={styles.options}>
        {question.options.map((option, i) => (
          <li key={option.id} className="msg" style={{ animationDelay: `${i * 60}ms` }}>
            <button
              type="button"
              className={`${styles.option} btn`}
              aria-pressed={question.multiple ? picked.includes(option.id) : undefined}
              onClick={() => pick(option.id)}
            >
              <span className={styles.num}>{i + 1}</span>
              {option.visual && <Visual visual={option.visual} />}
              <span className={styles.optionLabel}>{option.label}</span>
              {option.recommended && <span className={styles.badge}>추천</span>}
            </button>
          </li>
        ))}
        <li className="msg" style={{ animationDelay: `${question.options.length * 60}ms` }}>
          <button
            type="button"
            className={`${styles.option} btn`}
            onClick={() => onAnswer({ question_id: question.id, kind: "delegate" }, DELEGATE_LABEL)}
          >
            <span className={styles.num}>{question.options.length + 1}</span>
            <span className={styles.optionLabel}>{DELEGATE_LABEL}</span>
          </button>
        </li>
      </ol>
      <form
        className={styles.field}
        onSubmit={(e) => {
          e.preventDefault();
          sendCustom();
        }}
      >
        <label htmlFor={inputId} className={styles.fieldLabel}>
          직접 입력
        </label>
        <input
          id={inputId}
          className={styles.input}
          value={custom}
          placeholder="선택지에 없으면 그냥 말해 주세요"
          autoComplete="off"
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            // 한글 조합 중의 Enter 는 글자를 확정하는 키다.
            if (e.key === "Enter" && e.nativeEvent.isComposing) e.preventDefault();
          }}
        />
        <button type="submit" className={`${styles.send} btn`} aria-label="보내기" disabled={!custom.trim()}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 19V5M6 11l6-6 6 6" />
          </svg>
        </button>
      </form>
      {(question.multiple || canFinish) && (
        <div className={styles.actions}>
          {canFinish && (
            <button type="button" className={`${styles.ghost} btn`} onClick={onFinish}>
              그만 묻고 만들어 주세요
            </button>
          )}
          {question.multiple && (
            <button
              type="button"
              className={`${styles.primary} btn`}
              disabled={picked.length === 0}
              onClick={() => choose(picked)}
            >
              다음
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const AREAS: { area: ConfirmItem["area"]; title: string }[] = [
  { area: "function", title: "용도 · 기능" },
  { area: "design", title: "디자인" },
  { area: "tech", title: "기술 (빌더가 정한 것)" },
];

const STATUS_LABEL: Record<ConfirmItem["status"], string> = {
  confirmed: "정한 것",
  delegated: "맡긴 것",
};

type ListProps = { screen: ConfirmScreen; picked: string[]; onToggle: (id: string) => void };

function ConfirmList({ screen, picked, onToggle }: ListProps) {
  return (
    <div className={styles.confirm}>
      {AREAS.map(({ area, title }) => {
        const items = screen.items.filter((item) => item.area === area);
        if (!items.length) return null;
        return (
          <section key={area} className={`${styles.group} msg`} aria-label={title}>
            <h2 className={styles.label}>{title}</h2>
            {items.map((item) => (
              <div key={item.id} className={styles.item}>
                <div className={styles.itemBody}>
                  <div className={styles.itemName}>
                    {item.name}
                    {item.editable && <span className={styles.status}>{STATUS_LABEL[item.status]}</span>}
                  </div>
                  <p className={styles.itemContent}>{item.content || "만드는 쪽에서 알아서 정해요"}</p>
                </div>
                {item.editable && (
                  <label className={styles.revise}>
                    <input type="checkbox" checked={picked.includes(item.id)} onChange={() => onToggle(item.id)} />
                    <span>고칠래요</span>
                  </label>
                )}
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}

type ConfirmDockProps = { screen: ConfirmScreen; picked: string[]; onReply: (reply: ConfirmReply) => void };

function ConfirmDock({ screen, picked, onReply }: ConfirmDockProps) {
  const editable = screen.items.some((item) => item.editable);

  return (
    <div className={styles.actions}>
      {editable && (
        <button
          type="button"
          className={`${styles.ghost} btn`}
          disabled={picked.length === 0}
          onClick={() => onReply({ action: "revise", item_ids: picked })}
        >
          고른 항목 다시 답할게요{picked.length > 0 && ` (${picked.length})`}
        </button>
      )}
      <button type="button" className={`${styles.primary} btn`} onClick={() => onReply({ action: "confirm" })}>
        이대로 만들어 주세요
      </button>
    </div>
  );
}

const FILES = [
  { name: "spec.md", desc: "기획 스펙" },
  { name: "AGENTS.md", desc: "작업자 규칙" },
  { name: "CLAUDE.md", desc: "Claude Code 연결" },
  { name: "SKILL.md", desc: "스킬 · 필요한 만큼" },
];

type Line = { question: string; answer: string };

function SidePanel({ generating, lines }: { generating: boolean; lines: Line[] }) {
  return (
    <aside aria-label="산출물과 지금까지 받은 답" className={`${styles.side} rise d2`}>
      <div className={styles.card}>
        {generating && <div aria-hidden="true" className={`${styles.scanLine} scan`} />}
        <div className={styles.cardHead}>
          <span className={styles.folder}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ac)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            </svg>
            my-project/
          </span>
          <span className={styles.cardNote}>{generating ? "만드는 중" : "답을 다 받으면 만들어요"}</span>
        </div>
        <ul className={styles.files}>
          {FILES.map((file, i) => (
            <li key={file.name} className="file" style={{ animationDelay: `${i * 70}ms` }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={generating ? "var(--ac)" : "#5E5E68"} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                <path d="M14 3v5h5" />
              </svg>
              <div className={styles.fileBody}>
                <span className={styles.fileName}>{file.name}</span>
                <span className={styles.fileDesc}>{file.desc}</span>
              </div>
              <span className={generating ? styles.pillActive : styles.pill}>{generating ? "작성 중" : "대기"}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className={`${styles.card} ${styles.log}`}>
        <div className={styles.logHead}>
          <span className={styles.light} />
          <span className={styles.light} />
          <span className={styles.light} />
          <span className={styles.logTitle}>지금까지 받은 답</span>
        </div>
        <div className={styles.logBody}>
          {lines.length === 0 && <div className={styles.logEmpty}># 아직 받은 답이 없어요</div>}
          {lines.map((line, i) => (
            <div key={i} className="msg">
              <div className={styles.logQuestion}># {line.question}</div>
              <div>- {line.answer}</div>
            </div>
          ))}
          <span aria-hidden="true" className={`${styles.caret} caret`} />
        </div>
      </div>
    </aside>
  );
}
