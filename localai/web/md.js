/* Мини-рендер Markdown для ответов модели: заголовки, списки, цитаты, **жирный**, *курсив*, `код`, ссылки http(s).
 * Собирает DOM (без innerHTML), поэтому безопасен для произвольного текста. */
(function (root) {
  const INLINE = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*|__[^_\n]+__)|(\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))|(\*[^*\s][^*\n]*\*|(?<![\w])_[^_\s][^_\n]*_(?![\w]))/g;

  function parseInline(s) {
    const out = [];
    let last = 0, m;
    INLINE.lastIndex = 0;
    while ((m = INLINE.exec(s))) {
      if (m.index > last) out.push({ t: 'text', v: s.slice(last, m.index) });
      const x = m[0];
      if (m[1]) out.push({ t: 'code', v: x.slice(1, -1) });
      else if (m[2]) out.push({ t: 'b', v: x.slice(2, -2) });
      else if (m[3]) { const k = /^\[([^\]]+)\]\((.+)\)$/.exec(x); out.push({ t: 'a', v: k[1], href: k[2] }); }
      else out.push({ t: 'i', v: x.slice(1, -1) });
      last = m.index + x.length;
    }
    if (last < s.length) out.push({ t: 'text', v: s.slice(last) });
    return out;
  }

  function parseBlocks(text) {
    const blocks = [];
    let cur = null;
    const flush = () => { cur = null; };
    for (const raw of text.split('\n')) {
      const line = raw.replace(/\s+$/, '');
      let m;
      if (!line.trim()) { flush(); continue; }
      if ((m = /^(#{1,4})\s+(.*)$/.exec(line))) { blocks.push({ type: 'h', level: m[1].length, text: m[2] }); flush(); }
      else if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) { blocks.push({ type: 'hr' }); flush(); }
      else if ((m = /^\s*[-*+]\s+(.*)$/.exec(line))) { if (!cur || cur.type !== 'ul') { cur = { type: 'ul', items: [] }; blocks.push(cur); } cur.items.push(m[1]); }
      else if ((m = /^\s*\d+[.)]\s+(.*)$/.exec(line))) { if (!cur || cur.type !== 'ol') { cur = { type: 'ol', items: [] }; blocks.push(cur); } cur.items.push(m[1]); }
      else if ((m = /^>\s?(.*)$/.exec(line))) { if (!cur || cur.type !== 'quote') { cur = { type: 'quote', lines: [] }; blocks.push(cur); } cur.lines.push(m[1]); }
      else { if (!cur || cur.type !== 'p') { cur = { type: 'p', lines: [] }; blocks.push(cur); } cur.lines.push(line); }
    }
    return blocks;
  }

  function inlineInto(parent, s, doc) {
    for (const t of parseInline(s)) {
      if (t.t === 'text') parent.append(doc.createTextNode(t.v));
      else if (t.t === 'code') { const c = doc.createElement('code'); c.className = 'inl'; c.textContent = t.v; parent.append(c); }
      else if (t.t === 'b') { const c = doc.createElement('strong'); c.textContent = t.v; parent.append(c); }
      else if (t.t === 'i') { const c = doc.createElement('em'); c.textContent = t.v; parent.append(c); }
      else { const a = doc.createElement('a'); a.textContent = t.v; a.href = t.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; parent.append(a); }
    }
  }

  function render(container, text, doc) {
    doc = doc || root.document;
    for (const b of parseBlocks(text)) {
      let n;
      if (b.type === 'h') { n = doc.createElement('h' + Math.min(b.level + 2, 6)); inlineInto(n, b.text, doc); }
      else if (b.type === 'hr') n = doc.createElement('hr');
      else if (b.type === 'ul' || b.type === 'ol') { n = doc.createElement(b.type); b.items.forEach((it) => { const li = doc.createElement('li'); inlineInto(li, it, doc); n.append(li); }); }
      else if (b.type === 'quote') { n = doc.createElement('blockquote'); b.lines.forEach((l, i) => { if (i) n.append(doc.createElement('br')); inlineInto(n, l, doc); }); }
      else { n = doc.createElement('p'); b.lines.forEach((l, i) => { if (i) n.append(doc.createElement('br')); inlineInto(n, l, doc); }); }
      container.append(n);
    }
  }

  const api = { parseInline, parseBlocks, render };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.KiraMd = api;
})(typeof window !== 'undefined' ? window : globalThis);
