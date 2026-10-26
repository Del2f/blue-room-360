/* Korean font preview: add ?ko=<key> to a page URL (e.g. index.html?ko=gowun-batang) to swap the Korean font.
   English always uses Special Elite; Korean defaults to Gowun Batang; see fonts.html for the side-by-side drafts. All fonts are free (SIL OFL, Google Fonts). */
window.KO_FONTS = {
  "grandiflora": { family: "Grandiflora One", note: "장식 세리프 · 로고의 빅토리안 곡선과 가장 가까움" },
  "gowun-batang": { family: "Gowun Batang", weights: "400;700", note: "부드러운 바탕체 · 동화 같은 본문" },
  "hahmlet": { family: "Hahmlet", weights: "400;700", note: "굵기가 다양한 빈티지 세리프" },
  "song-myung": { family: "Song Myung", note: "옛 활자 느낌의 명조" },
  "diphylleia": { family: "Diphylleia", note: "가늘고 우아한 디스플레이 명조" },
  "gaegu": { family: "Gaegu", weights: "400;700", note: "M/V의 손글씨 타이틀과 어울리는 손글씨" },
  "gamja": { family: "Gamja Flower", note: "동글동글한 손글씨 · 쪽지·소문에 어울림" },
  "nanum-pen": { family: "Nanum Pen Script", note: "펜으로 휘갈긴 메모 느낌" },
};
(() => {
  const key = new URLSearchParams(location.search).get("ko");
  const f = window.KO_FONTS[key];
  if (!f) return;
  const q = f.family.replace(/ /g, "+") + (f.weights ? `:wght@${f.weights}` : "");
  document.write(`<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=${q}&display=swap">`);
  document.documentElement.style.setProperty("--font-ko", `"${f.family}"`);
})();
