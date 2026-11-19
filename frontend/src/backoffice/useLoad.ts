import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

type Loaded<T> = { data?: T; error?: ApiError; loading: boolean };

/** 백오피스 화면의 읽기 하나. key 가 바뀌면 다시 읽고, 늦게 온 앞의 응답은 버린다. */
export function useLoad<T>(key: string, load: () => Promise<T>): Loaded<T> & { set: (data: T) => void } {
  const [state, setState] = useState<Loaded<T> & { key: string }>({ key, loading: true });

  useEffect(() => {
    let live = true;
    load().then(
      (data) => live && setState({ key, data, loading: false }),
      (e: unknown) =>
        live && setState({ key, error: e instanceof ApiError ? e : new ApiError(0, String(e)), loading: false }),
    );
    return () => {
      live = false;
    };
    // load 는 key 로 정해진다 — 부르는 쪽이 매번 새 함수를 넘겨도 key 가 같으면 다시 읽지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // key 가 막 바뀐 그리기에서는 앞 key 의 값을 보이지 않는다.
  const current = state.key === key ? state : { loading: true };
  return { ...current, set: (data: T) => setState({ key, data, loading: false }) };
}
