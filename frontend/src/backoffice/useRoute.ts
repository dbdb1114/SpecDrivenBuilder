import { useEffect, useState } from "react";
import { parseRoute } from "./route";

export function useRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));

  useEffect(() => {
    const follow = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);

  return route;
}
