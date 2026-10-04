/* Поиск и аккаунты Hugging Face / GitHub (запросы идут прямо из приложения, токены не покидают устройство). */
(function (root) {
  const HF = 'https://huggingface.co', GH = 'https://api.github.com';

  class HubError extends Error {
    constructor(msg, status) { super(msg); this.status = status; }
  }

  const SORT_HF = { popular: 'downloads', likes: 'likes', new: 'lastModified', trending: 'trendingScore' };
  const SORT_GH = { popular: 'stars', likes: 'stars', new: 'updated', trending: 'stars' };
  const GH_TOPICS = { all: ['llm', 'gguf', 'stable-diffusion', 'whisper'], llm: ['llm'], gguf: ['gguf'], image: ['stable-diffusion'], speech: ['whisper'] };

  const auth = (token) => (token ? { headers: { Authorization: 'Bearer ' + token } } : {});

  async function getJson(url, token, f) {
    const r = await f(url, auth(token));
    if (r.status === 401) throw new HubError('Токен недействителен или у него нет доступа', 401);
    if (r.status === 403 || r.status === 429) {
      const left = r.headers && r.headers.get && r.headers.get('x-ratelimit-remaining');
      throw new HubError(left === '0' || r.status === 429 ? 'Лимит запросов исчерпан — подключите аккаунт (токен), чтобы лимит стал выше' : 'Доступ запрещён', r.status);
    }
    if (!r.ok) throw new HubError('Источник ответил ' + r.status, r.status);
    return r.json();
  }

  const ownerOf = (id) => (id || '').split('/')[0] || '';
  const nameOf = (id) => (id || '').split('/').slice(1).join('/') || id || '';

  function hfSearchUrl({ q = '', filters = [], sort = 'popular', limit = 30, author = '' } = {}) {
    const p = new URLSearchParams();
    if (q.trim()) p.set('search', q.trim());
    if (author) p.set('author', author);
    p.set('sort', SORT_HF[sort] || 'downloads');
    p.set('direction', '-1');
    p.set('limit', String(limit));
    filters.forEach((f) => p.append('filter', f));
    return HF + '/api/models?' + p.toString();
  }

  function normalizeHf(m) {
    const id = m.id || m.modelId || '';
    return { source: 'hf', id, owner: ownerOf(id), title: nameOf(id), desc: '', downloads: m.downloads || 0, likes: m.likes || 0, task: m.pipeline_tag || '', tags: m.tags || [], updated: m.lastModified || m.createdAt || '', gated: !!m.gated, library: m.library_name || '' };
  }

  async function hfSearch(opts, token, f) {
    const list = await getJson(hfSearchUrl(opts), token, f || root.fetch.bind(root));
    return list.map(normalizeHf);
  }

  function ghSearchUrl({ q = '', topic = 'all', sort = 'popular', limit = 30 } = {}) {
    const topics = GH_TOPICS[topic] || GH_TOPICS.all;
    // Несколько topic через OR нельзя в одном запросе поиска репозиториев — берём «основной» topic, а при «all» ищем по словам.
    let query = q.trim();
    if (topic === 'all') query = (query ? query + ' ' : '') + '(llm OR gguf OR "stable diffusion" OR whisper) in:name,description,topics';
    else query = (query ? query + ' ' : '') + 'topic:' + topics[0];
    const p = new URLSearchParams({ q: query, sort: SORT_GH[sort] || 'stars', order: 'desc', per_page: String(limit) });
    return GH + '/search/repositories?' + p.toString();
  }

  function normalizeGh(r) {
    return { source: 'github', id: r.full_name, owner: (r.owner && r.owner.login) || ownerOf(r.full_name), title: r.name || nameOf(r.full_name), desc: r.description || '', downloads: 0, likes: r.stargazers_count || 0, task: r.language || '', tags: r.topics || [], updated: r.pushed_at || r.updated_at || '', gated: false, library: '' };
  }

  async function ghSearch(opts, token, f) {
    const res = await getJson(ghSearchUrl(opts), token, f || root.fetch.bind(root));
    return (res.items || []).map(normalizeGh);
  }

  async function hfWhoami(token, f) {
    const r = await getJson(HF + '/api/whoami-v2', token, f || root.fetch.bind(root));
    return { name: r.name, fullname: r.fullname || r.name, avatar: r.avatarUrl || '' };
  }

  async function ghUser(token, f) {
    const r = await getJson(GH + '/user', token, f || root.fetch.bind(root));
    return { name: r.login, fullname: r.name || r.login, avatar: r.avatar_url || '' };
  }

  async function hfLikes(user, token, f) {
    const r = await getJson(HF + '/api/users/' + encodeURIComponent(user) + '/likes', token, f || root.fetch.bind(root));
    return (Array.isArray(r) ? r : []).map((x) => (x.repo && x.repo.name) || x.repo || '').filter((id) => typeof id === 'string' && id.includes('/')).slice(0, 30);
  }

  async function ghStarred(token, f) {
    const r = await getJson(GH + '/user/starred?per_page=30', token, f || root.fetch.bind(root));
    return r.map(normalizeGh);
  }

  const api = { HubError, hfSearchUrl, ghSearchUrl, hfSearch, ghSearch, hfWhoami, ghUser, hfLikes, ghStarred, normalizeHf, normalizeGh };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.KiraHub = api;
})(typeof window !== 'undefined' ? window : globalThis);
