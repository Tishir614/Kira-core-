const test = require('node:test'), assert = require('node:assert');
const M = require('../web/md.js');

test('inline tokens', () => {
  assert.deepStrictEqual(M.parseInline('a **b** `c` *d* [e](https://x.y/z) f'), [
    { t: 'text', v: 'a ' }, { t: 'b', v: 'b' }, { t: 'text', v: ' ' }, { t: 'code', v: 'c' }, { t: 'text', v: ' ' }, { t: 'i', v: 'd' }, { t: 'text', v: ' ' },
    { t: 'a', v: 'e', href: 'https://x.y/z' }, { t: 'text', v: ' f' }]);
  assert.deepStrictEqual(M.parseInline('2 * 3 * 4 and snake_case_name'), [{ t: 'text', v: '2 * 3 * 4 and snake_case_name' }]);
  assert.strictEqual(M.parseInline('[x](javascript:alert(1))').every((t) => t.t === 'text'), true);
});

test('blocks', () => {
  const b = M.parseBlocks('# Title\n\nHello\nworld\n\n- a\n- b\n\n1. one\n2. two\n\n> quote\n\n---');
  assert.deepStrictEqual(b.map((x) => x.type), ['h', 'p', 'ul', 'ol', 'quote', 'hr']);
  assert.deepStrictEqual(b[1].lines, ['Hello', 'world']);
  assert.deepStrictEqual(b[2].items, ['a', 'b']);
});

test('render builds DOM without html injection', () => {
  const mk = (tag) => ({ tag, children: [], append(...k) { this.children.push(...k); }, set textContent(v) { this.text = v; }, set className(v) { this.cls = v; } });
  const doc = { createElement: mk, createTextNode: (v) => ({ text: v }) };
  const root = mk('div');
  M.render(root, '**<img src=x onerror=alert(1)>**', doc);
  const strong = root.children[0].children[0];
  assert.strictEqual(strong.tag, 'strong'); assert.strictEqual(strong.text, '<img src=x onerror=alert(1)>');
});
