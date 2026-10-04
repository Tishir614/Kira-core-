const test = require('node:test'), assert = require('node:assert');
const H = require('../web/hub.js');

const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const fail = (status, headers = {}) => ({ ok: false, status, headers: { get: (k) => headers[k.toLowerCase()] } });

test('hfSearchUrl composes filters and sort', () => {
  const u = new URL(H.hfSearchUrl({ q: ' qwen coder ', filters: ['gguf', 'text-generation'], sort: 'new', limit: 60 }));
  assert.strictEqual(u.searchParams.get('search'), 'qwen coder');
  assert.deepStrictEqual(u.searchParams.getAll('filter'), ['gguf', 'text-generation']);
  assert.strictEqual(u.searchParams.get('sort'), 'lastModified');
  assert.strictEqual(u.searchParams.get('limit'), '60');
  assert.ok(!new URL(H.hfSearchUrl({})).searchParams.has('search'));
});

test('hfSearch normalizes and sends token', async () => {
  let seen;
  const f = async (url, opt) => { seen = { url, opt }; return ok([{ id: 'Qwen/Qwen2.5-7B-GGUF', downloads: 10, likes: 2, pipeline_tag: 'text-generation', tags: ['gguf'], gated: false }]); };
  const r = await H.hfSearch({ q: 'qwen' }, 'hf_x', f);
  assert.deepStrictEqual([r[0].id, r[0].owner, r[0].title, r[0].downloads, r[0].task], ['Qwen/Qwen2.5-7B-GGUF', 'Qwen', 'Qwen2.5-7B-GGUF', 10, 'text-generation']);
  assert.strictEqual(seen.opt.headers.Authorization, 'Bearer hf_x');
  await H.hfSearch({}, '', async (u, o) => { assert.deepStrictEqual(o, {}); return ok([]); });
});

test('ghSearchUrl topic vs all', () => {
  const t = new URL(H.ghSearchUrl({ q: 'chat', topic: 'gguf', sort: 'new' }));
  assert.strictEqual(t.searchParams.get('q'), 'chat topic:gguf'); assert.strictEqual(t.searchParams.get('sort'), 'updated');
  assert.ok(new URL(H.ghSearchUrl({ q: 'x' })).searchParams.get('q').includes('llm OR gguf'));
});

test('ghSearch normalizes', async () => {
  const r = await H.ghSearch({ q: 'x', topic: 'llm' }, null, async () => ok({ items: [{ full_name: 'o/r', name: 'r', description: 'd', stargazers_count: 5, topics: ['llm'], language: 'C++', owner: { login: 'o' } }] }));
  assert.deepStrictEqual([r[0].source, r[0].id, r[0].likes, r[0].task, r[0].desc], ['github', 'o/r', 5, 'C++', 'd']);
});

test('errors are explained', async () => {
  await assert.rejects(H.hfWhoami('bad', async () => fail(401)), /Токен недействителен/);
  await assert.rejects(H.ghSearch({ q: 'x' }, null, async () => fail(403, { 'x-ratelimit-remaining': '0' })), /Лимит запросов/);
  await assert.rejects(H.hfSearch({}, null, async () => fail(500)), /500/);
});

test('accounts and likes', async () => {
  assert.deepStrictEqual(await H.hfWhoami('t', async () => ok({ name: 'bob', fullname: 'Bob B', avatarUrl: 'u' })), { name: 'bob', fullname: 'Bob B', avatar: 'u' });
  assert.deepStrictEqual(await H.ghUser('t', async () => ok({ login: 'alice', name: null, avatar_url: 'a' })), { name: 'alice', fullname: 'alice', avatar: 'a' });
  assert.deepStrictEqual(await H.hfLikes('bob', 't', async () => ok([{ repo: { name: 'a/b', type: 'model' } }, { repo: { name: 'junk' } }, {}])), ['a/b']);
  assert.strictEqual((await H.ghStarred('t', async () => ok([{ full_name: 'x/y', name: 'y' }])))[0].id, 'x/y');
});
