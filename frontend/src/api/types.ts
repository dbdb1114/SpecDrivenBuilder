// 생성된 OpenAPI 타입(src/types/api.d.ts)에 짧은 이름만 붙인다. 필드를 여기서 다시 적지 않는다.
import type { components } from "../types/api";

type Schemas = components["schemas"];

export type RunView = Schemas["RunView"];
export type RunStatus = RunView["status"];
export type QuestionBundle = Schemas["QuestionBundle"];
export type Question = Schemas["Question"];
export type Option = Schemas["Option"];
export type AnswerSubmission = Schemas["AnswerSubmission"];
export type Answer = AnswerSubmission["answers"][number];
export type ConfirmScreen = Schemas["ConfirmScreen"];
export type ConfirmItem = Schemas["ConfirmItem"];
export type ConfirmReply = Schemas["ConfirmAction"] | Schemas["ReviseAction"];
