import { useState } from "react";
import type { Answer, AnswerSubmission, Question, QuestionBundle } from "../api/types";
import { Button, ButtonRow } from "../components/Button";
import { Preview } from "../components/Preview";
import { Visual } from "../components/Visual";
import styles from "./pages.module.css";

// question-format.md: 고정 선택지는 options 에 없고 화면이 항상 같은 문구로 붙인다.
export const DELEGATE_LABEL = "알아서 정해 주세요";

type Draft = { kind: "option"; ids: string[] } | { kind: "custom"; text: string } | { kind: "delegate" };

type Props = {
  bundle: QuestionBundle;
  busy: boolean;
  onSubmit: (submission: AnswerSubmission) => void;
};

function toAnswer(questionId: string, draft: Draft | undefined): Answer | null {
  if (!draft) return null;
  if (draft.kind === "option") {
    return draft.ids.length ? { question_id: questionId, kind: "option", option_ids: draft.ids } : null;
  }
  if (draft.kind === "custom") {
    const text = draft.text.trim();
    return text ? { question_id: questionId, kind: "custom", text } : null;
  }
  return { question_id: questionId, kind: "delegate" };
}

export function QuestionPage({ bundle, busy, onSubmit }: Props) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});

  const setDraft = (questionId: string, draft: Draft) => setDrafts((prev) => ({ ...prev, [questionId]: draft }));

  // 답하지 않은 질문은 빼고 보낸다 — 규격상 빠진 질문은 "알아서 정해 주세요"와 같다.
  const answers = bundle.questions
    .map((q) => toAnswer(q.id, drafts[q.id]))
    .filter((a): a is Answer => a !== null);
  const send = (action: AnswerSubmission["action"]) => onSubmit({ action, answers });

  return (
    <section>
      <h1 className={styles.title}>몇 가지만 여쭤볼게요</h1>
      <p className={styles.lead}>
        모르겠으면 &ldquo;{DELEGATE_LABEL}&rdquo;를 누르거나 비워 두세요. 답하지 않은 질문은 알아서 정해요.
      </p>
      {bundle.preview && <Preview preview={bundle.preview} />}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send("submit");
        }}
      >
        {bundle.questions.map((question, index) => (
          <QuestionCard
            key={question.id}
            number={index + 1}
            question={question}
            draft={drafts[question.id]}
            onChange={(draft) => setDraft(question.id, draft)}
          />
        ))}
        <ButtonRow>
          {bundle.can_finish && (
            <Button disabled={busy} onClick={() => send("finish")}>
              그만 묻고 만들어 주세요
            </Button>
          )}
          <Button primary type="submit" disabled={busy}>
            다음
          </Button>
        </ButtonRow>
      </form>
    </section>
  );
}

type CardProps = {
  number: number;
  question: Question;
  draft: Draft | undefined;
  onChange: (draft: Draft) => void;
};

function QuestionCard({ number, question, draft, onChange }: CardProps) {
  const selected = draft?.kind === "option" ? draft.ids : [];

  const toggle = (optionId: string) => {
    if (!question.multiple) return onChange({ kind: "option", ids: [optionId] });
    const ids = selected.includes(optionId) ? selected.filter((id) => id !== optionId) : [...selected, optionId];
    onChange({ kind: "option", ids });
  };

  return (
    <fieldset className={styles.card}>
      <legend className={styles.cardTitle}>
        {number}. {question.text}
      </legend>
      {question.multiple && <p className={styles.hint}>여러 개 고를 수 있어요</p>}
      <ol className={styles.options}>
        {question.options.map((option, i) => (
          <li key={option.id}>
            <button
              type="button"
              className={styles.option}
              aria-pressed={selected.includes(option.id)}
              onClick={() => toggle(option.id)}
            >
              <span className={styles.number}>{i + 1}</span>
              {option.visual && <Visual visual={option.visual} />}
              <span>{option.label}</span>
              {option.recommended && <span className={styles.badge}>추천</span>}
            </button>
          </li>
        ))}
        <li>
          <button
            type="button"
            className={styles.option}
            aria-pressed={draft?.kind === "delegate"}
            onClick={() => onChange({ kind: "delegate" })}
          >
            <span className={styles.number}>{question.options.length + 1}</span>
            <span>{DELEGATE_LABEL}</span>
          </button>
        </li>
      </ol>
      <input
        className={`${styles.custom} ${draft?.kind === "custom" ? styles.active : ""}`}
        aria-label={`${number}번 직접 입력`}
        placeholder="직접 입력"
        value={draft?.kind === "custom" ? draft.text : ""}
        onChange={(e) => onChange({ kind: "custom", text: e.target.value })}
      />
    </fieldset>
  );
}
