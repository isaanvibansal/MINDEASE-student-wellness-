(() => {
'use strict';
/* Model: leaves[0] = cover (back = entry 0 left page).
   leaf j>=1: front = entry j-1 right page, back = entry j left page.
   f = number of flipped leaves; current entry index = f-1; f = 0 means closed. */
const $ = s => document.querySelector(s);
const h = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const csrf = $('meta[name=csrf-token]').content;
const openId = $('meta[name=open-entry]').content;
const book = $('#book'), shift = $('#shift'), castL = $('#castL'), castR = $('#castR');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const MOODS = [['', 'Mood…'], ['happy', '😊 Happy'], ['calm', '😌 Calm'], ['sad', '😔 Sad'], ['stressed', '😰 Stressed'], ['angry', '😠 Angry']];

let entries = [], leaves = [], f = 0, busy = false, side = 'left', selected = null, leaving = false, sayTimer;

/* ---------- helpers ---------- */
function say(msg, err) {
  const el = $('#say'); el.textContent = msg; el.className = 'nb-say' + (err ? ' err' : '');
  clearTimeout(sayTimer); sayTimer = setTimeout(() => { el.textContent = ''; }, 3500);
}
const dlg = $('#dlg');
function ask(msg, opts) {
  return new Promise(res => {
    $('#dlgMsg').textContent = msg;
    const box = $('#dlgBtns'); box.replaceChildren();
    opts.forEach(([k, label, cls]) => {
      const b = h('button', 'nb-btn ' + (cls || ''), label); b.type = 'button';
      b.onclick = () => { dlg.close(); res(k); }; box.append(b);
    });
    dlg.oncancel = () => res('stay');
    dlg.showModal();
  });
}
const cur = () => entries[f - 1];
const hasContent = e => e.title.value.trim() || e.text.value.trim() || e.refl.value.trim() || e.items.length;
const dirtyList = () => entries.filter(e => e.dirty && (e.id || hasContent(e)));

/* ---------- leaves & page turning ---------- */
function makeLeaf(extra) {
  const el = h('div', 'nb-leaf ' + (extra || ''));
  const front = h('div', 'nb-face nb-front'), back = h('div', 'nb-face nb-back');
  const fs = h('div', 'nb-slot'), bs = h('div', 'nb-slot');
  const fsh = h('i', 'nb-shade'), bsh = h('i', 'nb-shade');
  front.append(fs, fsh); back.append(bs, bsh); el.append(front, back);
  book.insertBefore(el, $('#edgeL'));
  const l = { el, fs, bs, fsh, bsh, angle: 0 };
  setAngle(l, 0);
  return l;
}
function setAngle(l, a) {
  l.angle = a;
  l.el.style.transform = `rotateY(${-a}deg)`;
  const s = Math.sin(a * Math.PI / 180);
  l.fsh.style.opacity = a < 90 ? s * .55 : 0;
  l.bsh.style.opacity = a > 90 ? s * .55 : 0;
  castR.style.opacity = s * (1 - a / 180) * .6;
  castL.style.opacity = s * (a / 180) * .6;
  if (l === leaves[0] && a >= 90) book.classList.add('shown');
}
function tween(l, to, ms) {
  return new Promise(res => {
    const from = l.angle;
    if (reduce || from === to) { setAngle(l, to); return res(); }
    const t0 = performance.now();
    (function step(t) {
      const p = clamp((t - t0) / ms, 0, 1), e = p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
      setAngle(l, from + (to - from) * e);
      p < 1 ? requestAnimationFrame(step) : res();
    })(t0);
  });
}
function layout() {
  const N = entries.length;
  leaves.forEach((l, k) => { l.el.style.zIndex = k < f ? k + 1 : N - k + 1; });
  entries.forEach((e, i) => { const on = i === f - 1; e.left.inert = !on; e.right.inert = !on; });
}
function finish() {
  busy = false; layout();
  castL.style.opacity = 0; castR.style.opacity = 0;
  updateUI();
}
async function flip(dir) {
  const N = entries.length;
  if (busy || f < 1 || (dir > 0 && f >= N) || (dir < 0 && f <= 1)) return;
  busy = true; updateUI();
  const l = leaves[dir > 0 ? f : f - 1];
  l.el.style.zIndex = 9000;
  await tween(l, dir > 0 ? 180 : 0, 950);
  f += dir; finish();
}
async function goTo(i) {
  const t = i + 1;
  if (busy || f < 1 || t === f || t < 1 || t > entries.length) return;
  const dir = t > f ? 1 : -1;
  while (Math.abs(t - f) > 1) {            // skip the middle pages, animate only the last turn
    if (dir > 0) { setAngle(leaves[f], 180); f++; } else { f--; setAngle(leaves[f], 0); }
  }
  castL.style.opacity = 0; castR.style.opacity = 0;
  layout();
  await flip(dir);
}
async function openBook() {
  if (busy || f > 0) return;
  busy = true; updateUI();
  let idx = openId ? entries.findIndex(e => e.id === openId) : -1;
  if (idx < 0) idx = Math.max(0, entries.length - 2);   // latest saved entry, or the blank page
  const target = idx + 1;
  for (let k = 1; k < target; k++) setAngle(leaves[k], 180);
  shift.classList.remove('closed');
  leaves[0].el.style.zIndex = 9000;
  await tween(leaves[0], 180, 1300);
  f = target; finish();
  const t = cur().text; t.focus({ preventScroll: true });
}

/* drag / tap on page edges */
function bindEdge(strip, dir) {
  strip.addEventListener('pointerdown', ev => {
    if (busy || (dir > 0 ? f >= entries.length : f <= 1)) return;
    ev.preventDefault(); strip.setPointerCapture(ev.pointerId); busy = true;
    const l = leaves[dir > 0 ? f : f - 1]; l.el.style.zIndex = 9000;
    const r = book.getBoundingClientRect(), mid = r.left + r.width / 2, W = r.width / 2, x0 = ev.clientX;
    let moved = false;
    const mv = e => {
      if (Math.abs(e.clientX - x0) > 6) moved = true;
      if (moved) setAngle(l, Math.acos(clamp((e.clientX - mid) / W, -1, 1)) * 180 / Math.PI);
    };
    const up = async () => {
      strip.removeEventListener('pointermove', mv); strip.removeEventListener('pointerup', up); strip.removeEventListener('pointercancel', up);
      const to = moved ? (l.angle > 90 ? 180 : 0) : (dir > 0 ? 180 : 0);
      await tween(l, to, 500);
      if ((dir > 0) === (to === 180)) f += dir;
      finish();
    };
    strip.addEventListener('pointermove', mv); strip.addEventListener('pointerup', up); strip.addEventListener('pointercancel', up);
  });
}
bindEdge($('#edgeR'), 1); bindEdge($('#edgeL'), -1);

/* ---------- entries ---------- */
function normItem(d) {
  if (!d || !['sticker', 'note', 'photo'].includes(d.type) || typeof d.value !== 'string') return null;
  return { type: d.type, value: d.value, page: d.page === 'right' ? 'right' : 'left',
    x: clamp(+d.x || 10, 0, 90), y: clamp(+d.y || 10, 0, 92), size: clamp(+d.size || 1, .5, 3), rot: clamp(+d.rot || 0, -180, 180) };
}
function addEntry(d) {
  const i = entries.length;
  const ent = { id: d.id || null, dirty: false, items: (d.decorations || []).map(normItem).filter(Boolean) };
  const L = h('section', 'nb-page nb-pl'), R = h('section', 'nb-page nb-pr');
  L.setAttribute('aria-label', 'Left page'); R.setAttribute('aria-label', 'Right page');
  ent.title = h('input', 'nb-title'); ent.title.placeholder = 'Title…'; ent.title.maxLength = 120;
  ent.title.setAttribute('aria-label', 'Entry title'); ent.title.value = d.title || '';
  ent.mood = h('select', 'nb-mood'); ent.mood.setAttribute('aria-label', 'Mood');
  MOODS.forEach(([v, t]) => { const o = h('option', '', t); o.value = v; ent.mood.append(o); });
  ent.mood.value = d.mood || '';
  ent.text = h('textarea', 'nb-text'); ent.text.placeholder = 'Start writing here…'; ent.text.maxLength = 20000;
  ent.text.setAttribute('aria-label', 'My thoughts'); ent.text.value = d.leftText || '';
  ent.refl = h('textarea', 'nb-text'); ent.refl.placeholder = 'What did you learn today? What are you grateful for?'; ent.refl.maxLength = 20000;
  ent.refl.setAttribute('aria-label', 'Reflection and gratitude'); ent.refl.value = d.rightText || '';
  ent.layerL = h('div', 'nb-deco'); ent.layerR = h('div', 'nb-deco');
  ent.dateEl = h('div', 'nb-date', d.date_label || new Date().toLocaleDateString(undefined, { dateStyle: 'long' }));
  const row = h('div', 'nb-row'); row.append(ent.title, ent.mood);
  L.append(row, ent.text, h('div', 'nb-foot', '— ' + (2 * i + 1) + ' —'), ent.layerL);
  R.append(h('h3', 'nb-h', 'Reflection & gratitude 🌿'), ent.dateEl, ent.refl, h('div', 'nb-foot', '— ' + (2 * i + 2) + ' —'), ent.layerR);
  [ent.title, ent.mood, ent.text, ent.refl].forEach(el => el.addEventListener('input', () => { ent.dirty = true; updateUI(); }));
  L.addEventListener('pointerdown', () => { side = 'left'; }); R.addEventListener('pointerdown', () => { side = 'right'; });
  ent.left = L; ent.right = R;
  entries.push(ent);
  leaves[i].bs.replaceChildren(L);                     // back of leaf i = entry i left page
  const leaf = makeLeaf(); leaf.fs.replaceChildren(R); // front of leaf i+1 = entry i right page
  leaves.push(leaf);
  ent.items.forEach(it => mount(ent, it));
  layout();
}
function place(it) {
  const s = it.el.style;
  s.left = it.x + '%'; s.top = it.y + '%'; s.setProperty('--s', it.size); s.transform = `rotate(${it.rot}deg)`;
}
function select(it) {
  if (selected && selected.el) selected.el.classList.remove('nb-sel');
  selected = it; if (it) it.el.classList.add('nb-sel');
}
function mount(ent, it) {
  const layer = it.page === 'right' ? ent.layerR : ent.layerL;
  const el = h('div', 'nb-item nb-' + it.type);
  if (it.type === 'photo') { const im = new Image(); im.src = it.value; im.alt = 'Journal photo'; im.draggable = false; el.append(im); }
  else el.textContent = it.value;
  el.tabIndex = 0; it.el = el; it.ent = ent; place(it); layer.append(el);
  el.addEventListener('pointerdown', ev => {
    ev.preventDefault(); select(it); side = it.page; el.setPointerCapture(ev.pointerId);
    const sx = ev.clientX, sy = ev.clientY, ox = it.x, oy = it.y, w = layer.clientWidth, hh = layer.clientHeight;
    const mv = e => { it.x = clamp(ox + (e.clientX - sx) / w * 100, 0, 90); it.y = clamp(oy + (e.clientY - sy) / hh * 100, 0, 92); place(it); ent.dirty = true; };
    const up = () => { el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up); updateUI(); };
    el.addEventListener('pointermove', mv); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
  });
  el.addEventListener('focus', () => select(it));
  el.addEventListener('keydown', e => { if (e.key === 'Delete' || e.key === 'Backspace') removeSel(); });
}
function addItem(type, value) {
  const ent = cur(); if (!ent || busy) return;
  const n = ent.items.length;
  if (n >= 40) return say('This entry is full of decorations.', true);
  const it = { type, value, page: side, x: 10 + (n * 7) % 55, y: 58 + (n * 5) % 28, size: 1, rot: ((n * 13) % 30) - 15 };
  ent.items.push(it); mount(ent, it); ent.dirty = true; select(it); updateUI();
}
function adjust(fn) {
  if (!selected) return say('Tap a sticker, photo or note first.');
  fn(selected); place(selected); selected.ent.dirty = true; updateUI();
}
function removeSel() {
  if (!selected) return say('Tap a sticker, photo or note first.');
  const e = selected.ent; e.items.splice(e.items.indexOf(selected), 1);
  selected.el.remove(); selected = null; e.dirty = true; updateUI();
}
function readPhoto(file) {
  return new Promise((res, rej) => {
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return rej('Please choose a JPG, PNG or WEBP photo.');
    if (file.size > 10 * 1024 * 1024) return rej('That photo is over 10 MB.');
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => {
      const s = Math.min(1, 900 / Math.max(img.width, img.height)), c = document.createElement('canvas');
      c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url); res(c.toDataURL('image/jpeg', .78));
    };
    img.onerror = () => rej('Could not read that image.');
    img.src = url;
  });
}

/* ---------- save / delete ---------- */
function collect(e) {
  return { id: e.id, title: e.title.value, mood: e.mood.value, leftText: e.text.value, rightText: e.refl.value,
    decorations: e.items.map(({ type, value, page, x, y, size, rot }) => ({ type, value, page, x: +x.toFixed(2), y: +y.toFixed(2), size, rot })) };
}
async function api(method, url, body) {
  const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: body && JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || 'Something went wrong.');
  return j;
}
async function save(e = cur()) {
  if (!e) return true;
  if (!e.id && !hasContent(e)) { say('Write something first ✍️'); return false; }
  say('Saving…');
  try {
    const wasDraft = !e.id, j = await api('POST', '/api/journal', collect(e));
    e.id = j.entry.id; e.dirty = false; e.dateEl.textContent = j.entry.date_label;
    if (wasDraft && e === entries[entries.length - 1]) addEntry({});   // fresh blank page after it
    say('Saved ✓'); updateUI(); return true;
  } catch (err) { say(err.message || 'Could not save.', true); return false; }
}
function reattach() {
  entries.forEach((e, i) => { leaves[i].bs.replaceChildren(e.left); leaves[i + 1].fs.replaceChildren(e.right); });
  leaves[entries.length].bs.replaceChildren();
}
async function removeEntry() {
  const e = cur(); if (!e || !e.id || busy) return;
  const a = await ask('Delete this entry for good? This cannot be undone.', [['yes', 'Delete', 'danger'], ['no', 'Keep it']]);
  if (a !== 'yes') return;
  try { await api('DELETE', '/api/journal/' + e.id); } catch (err) { return say(err.message, true); }
  const i = f - 1; entries.splice(i, 1);
  leaves.pop().el.remove(); reattach();
  f = clamp(f - (i > 0 ? 1 : 0), 1, entries.length);
  leaves.forEach((l, k) => setAngle(l, k < f ? 180 : 0));
  finish(); say('Entry deleted.');
}

/* ---------- UI state ---------- */
function updateUI() {
  const N = entries.length, open = f >= 1, e = cur(), saved = entries.filter(x => x.id).length;
  $('#prev').disabled = busy || !open || f <= 1;
  $('#next').disabled = busy || !open || f >= N;
  $('#newEntry').disabled = busy || !open || f === N;
  $('#save').disabled = busy || !open;
  $('#del').disabled = busy || !open || !e || !e.id;
  $('#tools').disabled = busy || !open;
  $('#edgeL').hidden = busy || !open || f <= 1;
  $('#edgeR').hidden = busy || !open || f >= N;
  $('#nbIndicator').textContent = !open ? 'Notebook closed' : (e.id ? `Entry ${f} of ${saved}` : 'New entry') + (e.dirty ? ' • unsaved' : '');
}

/* ---------- wiring ---------- */
$('#prev').onclick = () => flip(-1);
$('#next').onclick = () => flip(1);
$('#newEntry').onclick = () => goTo(entries.length - 1);
$('#save').onclick = () => save();
$('#del').onclick = removeEntry;
document.querySelectorAll('[data-sticker]').forEach(b => b.onclick = () => addItem('sticker', b.dataset.sticker));
$('#noteBtn').onclick = async () => {
  const t = prompt('Write your sticky note:');
  if (t && t.trim()) addItem('note', t.trim().slice(0, 300));
};
$('#photoBtn').onclick = () => {
  const e = cur(); if (!e) return;
  if (e.items.filter(i => i.type === 'photo').length >= 4) return say('Up to 4 photos per entry.', true);
  $('#photo').click();
};
$('#photo').onchange = async ev => {
  const file = ev.target.files[0]; ev.target.value = ''; if (!file) return;
  try { addItem('photo', await readPhoto(file)); } catch (err) { say(String(err), true); }
};
$('#bigger').onclick = () => adjust(i => { i.size = clamp(i.size + .15, .5, 3); });
$('#smaller').onclick = () => adjust(i => { i.size = clamp(i.size - .15, .5, 3); });
$('#rotate').onclick = () => adjust(i => { i.rot = ((i.rot + 15 + 180) % 360) - 180; });
$('#removeItem').onclick = removeSel;
$('#nbBack').onclick = async () => {
  const dirty = dirtyList();
  if (dirty.length) {
    const a = await ask('You have unsaved changes in your notebook.', [['save', 'Save & leave', 'primary'], ['discard', 'Discard'], ['stay', 'Keep editing']]);
    if (a === 'stay') return;
    if (a === 'save') for (const e of dirty) if (!(await save(e))) return;
  }
  leaving = true; location.href = '/dashboard';
};
addEventListener('beforeunload', e => { if (!leaving && dirtyList().length) { e.preventDefault(); e.returnValue = ''; } });

(async function init() {
  const cover = makeLeaf('nb-coverleaf');
  const btn = h('button', 'nb-cover'); btn.type = 'button'; btn.setAttribute('aria-label', 'Open my journal');
  btn.append(h('em', '', '🌿'), h('b', '', 'MindEase'), h('span', '', 'My Journal'), h('small', '', 'tap to open'));
  btn.onclick = openBook; cover.fs.append(btn);
  leaves.push(cover);
  try {
    const r = await fetch('/api/journal');
    if (r.status === 401) { location.href = '/login'; return; }
    ((await r.json()).entries || []).forEach(addEntry);
  } catch (e) { say('Could not load your entries. Check your connection.', true); }
  addEntry({});                                         // blank page always waits at the end
  layout(); updateUI();
})();
})();
