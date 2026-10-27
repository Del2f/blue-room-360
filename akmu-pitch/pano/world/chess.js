// The chess set on the room's desk, playable: you take white, the room's owner takes black.
// Board and pieces are renders of the same Poly Haven chess_set (blender/chess_sprites.py).
import { WHITE, BLACK, replay, legalMoves, make, inCheck, outcome, positionKey, uci, sqName } from "./chess-engine.js";

const LEVELS = [
  { name: "쉬움", opts: { depth: 1, ms: 300, noise: 90 } },
  { name: "보통", opts: { depth: 3, ms: 700, noise: 20 } },
  { name: "어려움", opts: { depth: 6, ms: 1600, noise: 0 } },
];
const KEY = "akmu-room-chess-v1";
const OWNER = "방의 주인";
const LETTER = ["", "p", "n", "b", "r", "q", "k"];

const css = `
.chess { --sq: calc(var(--bw) / 8); margin-top: 4px; }
.chess .cb-who { display: flex; justify-content: space-between; align-items: center; font-size: 13.5px; color: var(--soft); margin: 2px 0 8px; min-height: 22px; }
.chess .cb-who b { color: var(--ink); font-weight: 700; margin-right: 6px; }
.chess .cb-caps { display: flex; height: 22px; }
.chess .cb-caps img { height: 22px; margin-left: -7px; filter: drop-shadow(0 1px 1px rgba(0,0,0,.25)); }
.chess .cb-board { position: relative; width: var(--bw); height: var(--bw); margin: 0 auto; border-radius: 6px; background: #8a7a66 center / 100% 100% no-repeat;
  box-shadow: 0 0 0 6px #3a2c20, 0 0 0 7px rgba(255, 236, 200, .25), 0 18px 34px -16px rgba(0, 0, 0, .7); touch-action: manipulation; user-select: none; -webkit-user-select: none; }
.chess .sq { position: absolute; width: var(--sq); height: var(--sq); border: 0; padding: 0; background: transparent; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.chess .sq::before { content: ""; position: absolute; inset: 0; pointer-events: none; }
.chess .sq.last::before { background: rgba(214, 160, 60, .32); }
.chess .sq.sel::before { background: rgba(214, 160, 60, .5); box-shadow: inset 0 0 0 2px rgba(120, 78, 20, .7); }
.chess .sq.check::before { background: radial-gradient(circle, rgba(200, 60, 40, .75), rgba(200, 60, 40, 0) 70%); }
.chess .sq.hint::after { content: ""; position: absolute; left: 50%; top: 50%; width: 26%; height: 26%; transform: translate(-50%, -50%); border-radius: 50%; background: rgba(60, 40, 20, .35); pointer-events: none; }
.chess .sq.hint.take::after { width: 84%; height: 84%; background: none; box-shadow: inset 0 0 0 4px rgba(60, 40, 20, .38); }
.chess .pc { position: absolute; left: -10%; bottom: 4%; width: 120%; height: 142%; object-fit: contain; object-position: 50% 100%; pointer-events: none;
  filter: drop-shadow(0 3px 2px rgba(0, 0, 0, .35)); transition: transform .28s cubic-bezier(.2, .85, .25, 1); }
.chess .sq.sel .pc { transform: translateY(-6%); }
.chess .coord { position: absolute; font-size: 9px; color: rgba(60, 44, 30, .55); pointer-events: none; font-family: var(--font-type); }
.chess .cb-status { font-family: var(--font-ko), serif; font-size: 15.5px; margin: 14px 0 0; min-height: 24px; color: var(--ink); text-align: center; }
.chess .cb-status.think::after { content: "…"; animation: cbdots 1.2s steps(4) infinite; display: inline-block; width: 1.1em; overflow: hidden; vertical-align: bottom; }
@keyframes cbdots { from { width: 0; } }
.chess .cb-ctl { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; margin-top: 12px; }
.chess .cb-lv { display: flex; border: 1px solid rgba(43, 33, 25, .22); border-radius: 999px; overflow: hidden; }
.chess .cb-lv button { font-size: 12.5px; padding: 7px 12px; color: var(--soft); }
.chess .cb-lv button.on { background: var(--ink); color: var(--paper); }
.chess .cb-ctl .btn { padding: 8px 14px; font-size: 12.5px; }
.chess .cb-reward { display: none; margin-top: 14px; padding: 14px 16px; border-radius: 14px; background: var(--ink); color: var(--paper); }
.chess .cb-reward.on { display: block; }
.chess .cb-reward small { display: block; font-family: var(--font-type); font-size: 10.5px; letter-spacing: .14em; color: var(--gold); margin-bottom: 6px; }
.chess .cb-reward p { margin: 0; font-family: var(--font-ko), serif; font-size: 15px; line-height: 1.6; }
.chess .cb-reward .btn { margin-top: 10px; background: var(--paper); color: var(--ink); }
.chess .cb-reward .ph { border-color: rgba(255, 248, 234, .3); color: rgba(255, 248, 234, .6); }
.chess .cb-promo { position: absolute; inset: 0; display: none; place-items: center; background: rgba(30, 22, 14, .45); border-radius: 6px; z-index: 3; }
.chess .cb-promo.on { display: grid; }
.chess .cb-promo div { display: flex; gap: 6px; background: var(--paper); padding: 10px; border-radius: 14px; box-shadow: 0 12px 30px -10px #000; }
.chess .cb-promo button { width: calc(var(--sq) * 1.05); height: calc(var(--sq) * 1.25); position: relative; border-radius: 10px; }
.chess .cb-promo button:hover { background: rgba(35, 27, 20, .08); }
.chess .cb-promo img { position: absolute; inset: 4%; width: 92%; height: 92%; object-fit: contain; }
`;

export function mountChess(root, { base = "chess/", tag = "", blip = () => {}, openSpot = null } = {}) {
  if (!document.getElementById("chess-css")) {
    const st = document.createElement("style");
    st.id = "chess-css"; st.textContent = css;
    document.head.appendChild(st);
  }
  const img = (code) => `${base}${code}.png${tag}`;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { saved = {}; }
  let moves = Array.isArray(saved.moves) ? saved.moves : [];
  let level = Number.isInteger(saved.level) ? Math.max(0, Math.min(2, saved.level)) : 1;
  let game, selected = null, targets = [], thinking = false, pendingPromo = null, alive = true, ask = 0;

  root.innerHTML = `<div class="chess">
    <div class="cb-who"><span><b>${OWNER}</b>검은 말</span><span class="cb-caps" data-side="b"></span></div>
    <div class="cb-board" style="background-image:url(${base}board.jpg${tag})"><div class="cb-promo"><div></div></div></div>
    <div class="cb-who"><span><b>나</b>흰 말</span><span class="cb-caps" data-side="w"></span></div>
    <p class="cb-status"></p>
    <div class="cb-reward"><small>A RUMOR, FOR THE WINNER</small><p>방의 주인이 쪽지를 건넸어요. "축음기 뒤에, 아직 아무도 듣지 못한 노래가 한 곡 있대요."</p>
      <div class="ph">자리 표시 — 미공개 트랙·다음 공연 힌트 (시안에는 음원 없음)</div><button class="btn" data-act="gramophone">축음기로 가 보기 →</button></div>
    <div class="cb-ctl">
      <div class="cb-lv">${LEVELS.map((l, i) => `<button data-lv="${i}">${l.name}</button>`).join("")}</div>
      <div class="btns" style="margin:0"><button class="btn" data-act="undo">무르기</button><button class="btn" data-act="new">새 판</button></div>
    </div></div>`;
  const box = root.querySelector(".chess"), boardEl = box.querySelector(".cb-board"), statusEl = box.querySelector(".cb-status");
  const promoEl = box.querySelector(".cb-promo"), rewardEl = box.querySelector(".cb-reward");
  let tickTimer = 0;
  const size = () => {
    // the whole card (title, board, controls) fits the screen without scrolling: about 330 px of it is not board
    const room = innerWidth <= 760 ? innerHeight * 0.86 - 320 : innerHeight - 96 - 330;
    const w = Math.max(232, Math.min(root.clientWidth || 380, 440, room));
    box.style.setProperty("--bw", Math.floor(w / 8) * 8 + "px");
  };
  size();
  addEventListener("resize", size);

  // 64 squares, a8 top-left (you play white from the bottom)
  const sqs = {};
  for (let r = 7; r >= 0; r--) for (let f = 0; f < 8; f++) {
    const s = r * 16 + f, el = document.createElement("button");
    el.className = "sq"; el.type = "button";
    el.style.left = `calc(var(--sq) * ${f})`; el.style.top = `calc(var(--sq) * ${7 - r})`;
    el.setAttribute("aria-label", sqName(s));
    el.onclick = () => tap(s);
    boardEl.appendChild(el); sqs[s] = el;
  }
  for (let f = 0; f < 8; f++) {
    const c = document.createElement("span"); c.className = "coord"; c.textContent = "abcdefgh"[f];
    c.style.left = `calc(var(--sq) * ${f + 1} - 9px)`; c.style.bottom = "2px"; boardEl.appendChild(c);
  }
  for (let r = 0; r < 8; r++) {
    const c = document.createElement("span"); c.className = "coord"; c.textContent = r + 1;
    c.style.left = "3px"; c.style.top = `calc(var(--sq) * ${7 - r} + 2px)`; boardEl.appendChild(c);
  }

  const worker = new Worker(new URL("./chess-worker.js" + tag, import.meta.url), { type: "module" });
  worker.onmessage = (e) => {
    if (!alive || e.data.id !== ask) return;
    const str = e.data.move;
    setTimeout(() => { if (alive && e.data.id === ask) { thinking = false; if (str) play(str, true); else draw(); } }, 380);
  };

  const save = () => { try { localStorage.setItem(KEY, JSON.stringify({ moves, level })); } catch (e) { /* private mode: the game just isn't kept */ } };
  const load = () => { game = replay(moves); moves = game.played.map(uci); };

  function status() {
    const s = game.s, end = outcome(s, game.keys);
    statusEl.classList.toggle("think", thinking);
    const won = !!end && end.result === "1-0";
    if (won && !rewardEl.classList.contains("on")) setTimeout(() => rewardEl.scrollIntoView({ block: "nearest", behavior: "smooth" }), 400);
    rewardEl.classList.toggle("on", won);
    if (end) {
      const why = { checkmate: "체크메이트", stalemate: "스테일메이트", fifty: "50수 규칙", material: "기물 부족", repetition: "같은 수 반복" }[end.why];
      statusEl.textContent = end.result === "1-0" ? `${why} — 당신이 이겼어요.` : end.result === "0-1" ? `${why} — ${OWNER}이 이겼어요.` : `${why}로 비겼어요.`;
      return end;
    }
    if (thinking) statusEl.textContent = `${OWNER}이 생각하고 있어요`;
    else if (s.turn === WHITE) statusEl.textContent = inCheck(s) ? "체크! 왕을 지켜야 해요." : moves.length ? "당신 차례예요." : "흰 말을 눌러 첫 수를 두세요.";
    return null;
  }

  function draw() {
    const s = game.s, last = game.played[game.played.length - 1];
    const lastSqs = last ? [last.from, last.to] : [];
    const checkSq = inCheck(s) ? s.kings[s.turn >> 3] : -1;
    for (const [k, el] of Object.entries(sqs)) {
      const sq = +k, p = s.b[sq];
      el.classList.toggle("last", lastSqs.includes(sq));
      el.classList.toggle("sel", sq === selected);
      el.classList.toggle("check", sq === checkSq);
      const t = targets.find((m) => m.to === sq);
      el.classList.toggle("hint", !!t);
      el.classList.toggle("take", !!t && !!p);
      const code = p ? (p & 8 ? "b" : "w") + LETTER[p & 7] : "";
      const cur = el.querySelector(".pc");
      if (!code) { if (cur) cur.remove(); }
      else if (!cur || cur.dataset.code !== code) {
        if (cur) cur.remove();
        const i = document.createElement("img");
        i.className = "pc"; i.alt = ""; i.dataset.code = code; i.src = img(code); i.draggable = false;
        el.appendChild(i);
      }
    }
    // captured pieces, by side
    const count = { w: {}, b: {} };
    for (const m of game.played) if (m.captured) { const c = m.captured & 8 ? "b" : "w"; count[c][m.captured & 7] = (count[c][m.captured & 7] || 0) + 1; }
    for (const side of ["w", "b"]) {
      const el = box.querySelector(`.cb-caps[data-side="${side}"]`), them = side === "w" ? "b" : "w";
      el.innerHTML = [5, 4, 3, 2, 1].flatMap((t) => Array(count[them][t] || 0).fill(`<img src="${img(them + LETTER[t])}" alt="">`)).join("");
    }
    box.querySelectorAll(".cb-lv button").forEach((b) => b.classList.toggle("on", +b.dataset.lv === level));
    return status();
  }

  function play(str, byOwner = false) {
    const m = legalMoves(game.s).find((x) => uci(x) === str);
    if (!m) return;
    make(game.s, m);
    game.played.push(m); game.keys.push(positionKey(game.s));
    moves.push(str);
    selected = null; targets = [];
    blip(m.captured ? 180 : 240, m.captured ? 0.09 : 0.05, 0.06);
    save();
    const end = draw();
    if (end) {
      blip(end.result === "1-0" ? 880 : 330, 0.4, 0.05);
      return;
    }
    if (!byOwner && game.s.turn === BLACK) think();
  }

  function think() {
    thinking = true; draw();
    clearInterval(tickTimer);   // the clock ticks while the owner thinks
    tickTimer = setInterval(() => { if (thinking && alive) blip(2400, 0.02, 0.02); else clearInterval(tickTimer); }, 600);
    worker.postMessage({ id: ++ask, moves, opts: LEVELS[level].opts });
  }

  function tap(sq) {
    if (thinking || pendingPromo || game.s.turn !== WHITE || outcome(game.s, game.keys)) return;
    const p = game.s.b[sq];
    const t = targets.filter((m) => m.to === sq);
    if (t.length) {
      if (t.length > 1) return askPromo(t);   // a pawn reaching the last rank
      return play(uci(t[0]));
    }
    if (p && !(p & 8)) {
      selected = sq === selected ? null : sq;
      targets = selected === null ? [] : legalMoves(game.s).filter((m) => m.from === sq);
      blip(520, 0.03, 0.025);
    } else { selected = null; targets = []; }
    draw();
  }

  function askPromo(options) {
    pendingPromo = options;
    const row = promoEl.querySelector("div");
    row.innerHTML = options.sort((a, b) => b.promo - a.promo)
      .map((m) => `<button data-u="${uci(m)}" aria-label="${LETTER[m.promo]}"><img src="${img("w" + LETTER[m.promo])}" alt=""></button>`).join("");
    row.querySelectorAll("button").forEach((b) => (b.onclick = () => { promoEl.classList.remove("on"); pendingPromo = null; play(b.dataset.u); }));
    promoEl.classList.add("on");
  }
  promoEl.onclick = (e) => { if (e.target === promoEl) { promoEl.classList.remove("on"); pendingPromo = null; } };

  box.querySelectorAll(".cb-lv button").forEach((b) => (b.onclick = () => { level = +b.dataset.lv; save(); draw(); }));
  box.querySelector('[data-act="new"]').onclick = () => { ask++; thinking = false; moves = []; selected = null; targets = []; save(); load(); draw(); blip(440, 0.12, 0.04); };
  box.querySelector('[data-act="undo"]').onclick = () => {
    ask++; thinking = false;
    // take back your last move and the reply to it
    const n = game.s.turn === WHITE ? 2 : 1;
    moves = moves.slice(0, Math.max(0, moves.length - n));
    selected = null; targets = []; save(); load(); draw();
  };
  box.querySelector('[data-act="gramophone"]').onclick = () => openSpot && openSpot("gramophone");

  load();
  draw();
  if (game.s.turn === BLACK && !outcome(game.s, game.keys)) think();   // a saved game left on the owner's move

  return {
    destroy() { alive = false; worker.terminate(); clearInterval(tickTimer); removeEventListener("resize", size); },
  };
}
