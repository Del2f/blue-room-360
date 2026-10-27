// Chess rules and a small alpha-beta opponent for the room's chess set (no dependencies).
// Board: 0x88, square = rank * 16 + file, rank 0 is white's back rank. Piece = type | colour.
export const WHITE = 0, BLACK = 8;
export const P = 1, N = 2, B = 3, R = 4, Q = 5, K = 6;
const KNIGHT = [33, 31, 18, 14, -33, -31, -18, -14], KING = [1, -1, 16, -16, 15, 17, -15, -17];
const DIAG = [15, 17, -15, -17], LINE = [1, -1, 16, -16];
const CORNER_RIGHT = { 0: 2, 7: 1, 112: 8, 119: 4 };   // a1 Q, h1 K, a8 q, h8 k
export const sqName = (s) => "abcdefgh"[s & 7] + ((s >> 4) + 1);
export const sqOf = (n) => (n.charCodeAt(1) - 49) * 16 + (n.charCodeAt(0) - 97);
const on = (s) => !(s & 0x88);

export function startPosition() {
  const b = new Int8Array(128);
  const back = [R, N, B, Q, K, B, N, R];
  for (let f = 0; f < 8; f++) {
    b[f] = back[f]; b[16 + f] = P;
    b[96 + f] = P | BLACK; b[112 + f] = back[f] | BLACK;
  }
  return { b, turn: WHITE, castle: 15, ep: -1, half: 0, full: 1, kings: [4, 116] };
}

export function attacked(s, sq, by) {
  const b = s.b;
  if (by === WHITE) { for (const d of [-15, -17]) { const t = sq + d; if (on(t) && b[t] === P) return true; } }
  else { for (const d of [15, 17]) { const t = sq + d; if (on(t) && b[t] === (P | BLACK)) return true; } }
  for (const d of KNIGHT) { const t = sq + d; if (on(t) && b[t] === (N | by)) return true; }
  for (const d of KING) { const t = sq + d; if (on(t) && b[t] === (K | by)) return true; }
  for (const d of DIAG) for (let t = sq + d; on(t); t += d) { const p = b[t]; if (p) { if (p === (B | by) || p === (Q | by)) return true; break; } }
  for (const d of LINE) for (let t = sq + d; on(t); t += d) { const p = b[t]; if (p) { if (p === (R | by) || p === (Q | by)) return true; break; } }
  return false;
}
export const inCheck = (s, side = s.turn) => attacked(s, s.kings[side >> 3], side ^ 8);

function pseudo(s, capturesOnly = false) {
  const b = s.b, me = s.turn, them = me ^ 8, out = [];
  const add = (from, to, piece, flags = 0, promo = 0) => out.push({ from, to, piece, captured: flags & 1 ? (P | them) : b[to], promo, flags });
  for (let from = 0; from < 128; from++) {
    if (!on(from)) { from += 7; continue; }
    const piece = b[from];
    if (!piece || (piece & 8) !== me) continue;
    const type = piece & 7;
    if (type === P) {
      const dir = me === WHITE ? 16 : -16, rank = from >> 4, last = me === WHITE ? 6 : 1, start = me === WHITE ? 1 : 6;
      const push = (to, flags = 0) => { if (rank === last) for (const pr of [Q, R, B, N]) add(from, to, piece, flags, pr); else add(from, to, piece, flags); };
      if (!capturesOnly && !b[from + dir]) {
        push(from + dir);
        if (rank === start && !b[from + 2 * dir]) add(from, from + 2 * dir, piece, 4);
      }
      for (const d of [dir - 1, dir + 1]) {
        const to = from + d;
        if (!on(to)) continue;
        if (b[to] && (b[to] & 8) === them) push(to);
        else if (to === s.ep) add(from, to, piece, 1);
      }
      continue;
    }
    const steps = type === N ? KNIGHT : type === K ? KING : type === B ? DIAG : type === R ? LINE : KING;
    const slide = type === B || type === R || type === Q;
    for (const d of steps) {
      for (let to = from + d; on(to); to += d) {
        const t = b[to];
        if (t && (t & 8) === me) break;
        if (t || !capturesOnly) add(from, to, piece);
        if (t || !slide) break;
      }
    }
    if (type === K && !capturesOnly) {
      const home = me === WHITE ? 4 : 116, kr = me === WHITE ? 1 : 4, qr = me === WHITE ? 2 : 8;
      if (from === home && !inCheck(s)) {
        if (s.castle & kr && !b[home + 1] && !b[home + 2] && b[home + 3] === (R | me) && !attacked(s, home + 1, them) && !attacked(s, home + 2, them)) add(from, home + 2, piece, 2);
        if (s.castle & qr && !b[home - 1] && !b[home - 2] && !b[home - 3] && b[home - 4] === (R | me) && !attacked(s, home - 1, them) && !attacked(s, home - 2, them)) add(from, home - 2, piece, 2);
      }
    }
  }
  return out;
}

export function make(s, m) {
  const b = s.b, me = s.turn, u = { castle: s.castle, ep: s.ep, half: s.half };
  b[m.from] = 0;
  b[m.to] = m.promo ? (m.promo | me) : m.piece;
  if (m.flags & 1) b[m.to + (me === WHITE ? -16 : 16)] = 0;
  if (m.flags & 2) {
    if (m.to > m.from) { b[m.from + 1] = b[m.from + 3]; b[m.from + 3] = 0; }
    else { b[m.from - 1] = b[m.from - 4]; b[m.from - 4] = 0; }
  }
  if ((m.piece & 7) === K) { s.kings[me >> 3] = m.to; s.castle &= me === WHITE ? ~3 : ~12; }
  if (CORNER_RIGHT[m.from]) s.castle &= ~CORNER_RIGHT[m.from];
  if (CORNER_RIGHT[m.to]) s.castle &= ~CORNER_RIGHT[m.to];
  s.ep = m.flags & 4 ? (m.from + m.to) >> 1 : -1;
  s.half = (m.piece & 7) === P || m.captured ? 0 : s.half + 1;
  if (me === BLACK) s.full++;
  s.turn ^= 8;
  return u;
}
export function unmake(s, m, u) {
  const b = s.b;
  s.turn ^= 8;
  const me = s.turn;
  if (me === BLACK) s.full--;
  s.castle = u.castle; s.ep = u.ep; s.half = u.half;
  b[m.from] = m.piece;
  b[m.to] = m.flags & 1 ? 0 : m.captured;
  if (m.flags & 1) b[m.to + (me === WHITE ? -16 : 16)] = m.captured;
  if (m.flags & 2) {
    if (m.to > m.from) { b[m.from + 3] = b[m.from + 1]; b[m.from + 1] = 0; }
    else { b[m.from - 4] = b[m.from - 1]; b[m.from - 1] = 0; }
  }
  if ((m.piece & 7) === K) s.kings[me >> 3] = m.from;
}

export function legalMoves(s, capturesOnly = false) {
  const me = s.turn, out = [];
  for (const m of pseudo(s, capturesOnly)) {
    const u = make(s, m);
    if (!attacked(s, s.kings[me >> 3], me ^ 8)) out.push(m);
    unmake(s, m, u);
  }
  return out;
}

export const uci = (m) => sqName(m.from) + sqName(m.to) + (m.promo ? "nbrq"[m.promo - 2] : "");
export function fromUci(s, str) {
  return legalMoves(s).find((m) => uci(m) === str) || null;
}
export function positionKey(s) {
  return s.b.join(",") + "|" + s.turn + "|" + s.castle + "|" + s.ep;
}
function insufficient(s) {
  const minors = [];
  for (let sq = 0; sq < 128; sq++) {
    if (!on(sq)) { sq += 7; continue; }
    const t = s.b[sq] & 7;
    if (!t || t === K) continue;
    if (t === N || t === B) minors.push(t); else return false;
  }
  return minors.length <= 1;
}
// game state after the moves so far: null while it goes on, else { result: "1-0" | "0-1" | "1/2", why }
export function outcome(s, keys) {
  if (!legalMoves(s).length) return inCheck(s) ? { result: s.turn === WHITE ? "0-1" : "1-0", why: "checkmate" } : { result: "1/2", why: "stalemate" };
  if (s.half >= 100) return { result: "1/2", why: "fifty" };
  if (insufficient(s)) return { result: "1/2", why: "material" };
  const k = keys[keys.length - 1];
  if (keys.filter((x) => x === k).length >= 3) return { result: "1/2", why: "repetition" };
  return null;
}

// ---------------------------------------------------------------- the opponent
const VALUE = [0, 100, 320, 330, 500, 900, 0];
// piece-square tables from white's side, rank 8 first (the usual simplified tables)
const PST = {
  [P]: [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5, 0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5, 5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
  [N]: [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30, -30, 5, 15, 20, 20, 15, 5, -30, -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30, -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
  [B]: [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10, -10, 5, 5, 10, 10, 5, 5, -10, -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10, -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
  [R]: [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
  [Q]: [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10, -5, 0, 5, 5, 5, 5, 0, -5, 0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10, -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
  [K]: [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10, 20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
};
function evaluate(s) {
  let score = 0;
  for (let sq = 0; sq < 128; sq++) {
    if (!on(sq)) { sq += 7; continue; }
    const p = s.b[sq];
    if (!p) continue;
    const t = p & 7, r = sq >> 4, f = sq & 7;
    const v = VALUE[t] + PST[t][p & 8 ? r * 8 + f : (7 - r) * 8 + f];
    score += p & 8 ? -v : v;
  }
  return s.turn === WHITE ? score : -score;
}
const order = (ms) => ms.sort((a, b) => (b.captured ? VALUE[b.captured & 7] * 10 - VALUE[b.piece & 7] : 0) + (b.promo ? 800 : 0)
                                     - ((a.captured ? VALUE[a.captured & 7] * 10 - VALUE[a.piece & 7] : 0) + (a.promo ? 800 : 0)));
const MATE = 100000;
class Timeout extends Error {}

export function search(state, { depth = 3, ms = 800, noise = 0, rand = Math.random } = {}) {
  // a private copy: a search cut short by the clock unwinds without undoing its moves
  const s = { ...state, b: Int8Array.from(state.b), kings: state.kings.slice() };
  const t0 = Date.now();
  let nodes = 0;
  const tick = () => { if ((++nodes & 1023) === 0 && Date.now() - t0 > ms) throw new Timeout(); };
  function quiesce(alpha, beta, qd) {
    tick();
    const stand = evaluate(s);
    if (stand >= beta) return beta;
    if (stand > alpha) alpha = stand;
    if (qd > 6) return alpha;
    for (const m of order(legalMoves(s, true))) {
      const u = make(s, m);
      const v = -quiesce(-beta, -alpha, qd + 1);
      unmake(s, m, u);
      if (v >= beta) return beta;
      if (v > alpha) alpha = v;
    }
    return alpha;
  }
  function negamax(d, alpha, beta, ply) {
    tick();
    const ms_ = legalMoves(s);
    if (!ms_.length) return inCheck(s) ? -MATE + ply : 0;
    if (d === 0) return quiesce(alpha, beta, 0);
    for (const m of order(ms_)) {
      const u = make(s, m);
      const v = -negamax(d - 1, -beta, -alpha, ply + 1);
      unmake(s, m, u);
      if (v >= beta) return beta;
      if (v > alpha) alpha = v;
    }
    return alpha;
  }
  const root = order(legalMoves(s));
  if (!root.length) return null;
  let best = root.map((m) => ({ m, v: 0 }));
  for (let d = 1; d <= depth; d++) {
    try {
      const scored = [];
      for (const { m } of best) {
        const u = make(s, m);
        const v = -negamax(d - 1, -MATE - 1, MATE + 1, 1);
        unmake(s, m, u);
        scored.push({ m, v });
      }
      best = scored.sort((a, b) => b.v - a.v);
    } catch (e) {
      if (!(e instanceof Timeout)) throw e;
      break;   // keep the last finished depth
    }
  }
  if (noise > 0) {
    const top = best[0].v, pool = best.filter((x) => x.v >= top - noise && Math.abs(top) < MATE / 2);
    if (pool.length > 1) return pool[Math.floor(rand() * pool.length)].m;
  }
  return best[0].m;
}

export function fromFen(fen) {
  const [rows, turn, cast, ep, half, full] = fen.split(" ");
  const s = startPosition();
  s.b.fill(0);
  const T = { p: P, n: N, b: B, r: R, q: Q, k: K };
  rows.split("/").forEach((row, i) => {
    let f = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) { f += +ch; continue; }
      const sq = (7 - i) * 16 + f, t = T[ch.toLowerCase()], col = ch === ch.toLowerCase() ? BLACK : WHITE;
      s.b[sq] = t | col;
      if (t === K) s.kings[col >> 3] = sq;
      f++;
    }
  });
  s.turn = turn === "b" ? BLACK : WHITE;
  s.castle = (cast.includes("K") ? 1 : 0) | (cast.includes("Q") ? 2 : 0) | (cast.includes("k") ? 4 : 0) | (cast.includes("q") ? 8 : 0);
  s.ep = ep && ep !== "-" ? sqOf(ep) : -1;
  s.half = +(half || 0); s.full = +(full || 1);
  return s;
}

// rebuild a game from its moves (uci strings); returns the state and the position keys for repetition
export function replay(moves) {
  const s = startPosition(), keys = [positionKey(s)], played = [];
  for (const str of moves) {
    const m = fromUci(s, str);
    if (!m) break;
    make(s, m);
    played.push(m);
    keys.push(positionKey(s));
  }
  return { s, keys, played };
}
