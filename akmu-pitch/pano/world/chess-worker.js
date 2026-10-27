// Thinks for the room's owner off the main thread, so the page keeps moving while it does.
import { replay, search, uci } from "./chess-engine.js";

self.onmessage = (e) => {
  const { id, moves, opts } = e.data;
  const { s } = replay(moves);
  const m = search(s, opts);
  self.postMessage({ id, move: m ? uci(m) : null });
};
