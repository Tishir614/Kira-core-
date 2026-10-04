/* Анализ ссылки на модель (Hugging Face / GitHub / прямой файл).
 * Чистые функции + небольшая обёртка над fetch. Общий код для ПК и Android. */
(function (root) {
  const HF = 'https://huggingface.co', GH = 'https://api.github.com';
  const MODEL_EXT = /\.(gguf|safetensors|onnx|ckpt|bin|pt|pth|tflite|ggml|task|litertlm)$/i;
  const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

  /** Что именно прислал пользователь → {source, repo, file?, url?}. */
  function parseInput(raw) {
    let t = (raw || '').trim();
    if (!t) throw new Error('Вставьте ссылку на модель');
    if (!/^[a-z]+:\/\//i.test(t) && /^(www\.)?(huggingface\.co|hf\.co|github\.com)\//i.test(t)) t = 'https://' + t;
    if (REPO.test(t)) return { source: 'hf', repo: t };
    let u;
    try { u = new URL(t); } catch { throw new Error('Не похоже на ссылку или «владелец/репозиторий»'); }
    if (u.protocol !== 'https:' && u.protocol !== 'http:') throw new Error('Нужна http(s) ссылка');
    const host = u.hostname.replace(/^www\./, '');
    const parts = u.pathname.split('/').filter(Boolean).map(decodeURIComponent);
    if (host === 'huggingface.co' || host === 'hf.co') {
      if (['datasets', 'spaces'].includes(parts[0])) throw new Error('Это датасет/Space, а не модель');
      if (parts.length < 2) throw new Error('Укажите репозиторий вида owner/name');
      const out = { source: 'hf', repo: parts[0] + '/' + parts[1] };
      if (['resolve', 'blob'].includes(parts[2]) && parts.length > 4) out.file = parts.slice(4).join('/');
      return out;
    }
    if (host === 'github.com') {
      if (parts.length < 2) throw new Error('Укажите репозиторий вида owner/repo');
      return { source: 'github', repo: parts[0] + '/' + parts[1].replace(/\.git$/, '') };
    }
    if (MODEL_EXT.test(u.pathname)) return { source: 'url', url: t, file: parts[parts.length - 1] };
    throw new Error('Поддерживаются ссылки huggingface.co, github.com и прямые ссылки на файлы моделей');
  }

  const FAMILIES = [
    ['qwen', 'Qwen'], ['llama', 'Llama'], ['gemma', 'Gemma'], ['phi', 'Phi'], ['mixtral', 'Mixtral'], ['mistral', 'Mistral'], ['deepseek', 'DeepSeek'],
    ['smollm', 'SmolLM'], ['tinyllama', 'TinyLlama'], ['starcoder', 'StarCoder'], ['codestral', 'Codestral'], ['granite', 'Granite'], ['falcon', 'Falcon'], ['olmo', 'OLMo'],
    ['yi-', 'Yi'], ['glm', 'GLM'], ['command-r', 'Command R'], ['stable-diffusion', 'Stable Diffusion'], ['sdxl', 'Stable Diffusion XL'], ['flux', 'FLUX'], ['kandinsky', 'Kandinsky'],
    ['whisper', 'Whisper'], ['bert', 'BERT'], ['t5', 'T5'], ['gpt', 'GPT'], ['bloom', 'BLOOM'],
  ];
  const guessFamily = (text) => { const l = (text || '').toLowerCase(); const f = FAMILIES.find(([k]) => l.includes(k)); return f ? f[1] : ''; };

  const TASKS = {
    'text-generation': 'Генерация текста', 'text2text-generation': 'Текст → текст', conversational: 'Диалог', 'image-text-to-text': 'Текст + изображения → текст',
    'text-to-image': 'Генерация изображений', 'image-to-image': 'Изображение → изображение', 'automatic-speech-recognition': 'Распознавание речи', 'text-to-speech': 'Синтез речи',
    'feature-extraction': 'Эмбеддинги', 'sentence-similarity': 'Сходство текстов', 'fill-mask': 'Заполнение масок', 'text-classification': 'Классификация текста',
    'image-classification': 'Классификация изображений', 'object-detection': 'Поиск объектов', translation: 'Перевод', summarization: 'Суммаризация',
  };

  function kindOf(task, name, tags, hasIndex) {
    const low = (name + ' ' + (tags || []).join(' ')).toLowerCase();
    if (hasIndex || task === 'text-to-image' || task === 'image-to-image') return 'image';
    if (!task || ['text-generation', 'text2text-generation', 'conversational', 'image-text-to-text'].includes(task)) {
      if (!task && /stable-diffusion|sdxl|flux|diffusion/.test(low)) return 'image';
      return /coder|code|starcoder|codestral/.test(low) ? 'code' : 'chat';
    }
    return 'other';
  }

  function guessParams(name, info) {
    const n = info && ((info.gguf && info.gguf.total) || (info.safetensors && info.safetensors.total));
    if (n) return n >= 1e9 ? (n / 1e9).toFixed(n >= 1e10 ? 0 : 1).replace(/\.0$/, '') + 'B' : Math.round(n / 1e6) + 'M';
    const m = /(?:^|[^a-z0-9.])(\d+(?:\.\d+)?)\s?([bm])(?![a-z0-9])/i.exec(name.replace(/[-_]/g, ' '));
    return m ? m[1] + m[2].toUpperCase() : '';
  }

  const QUANT = /(IQ\d(?:_[A-Z0-9]+)*|Q\d(?:_[A-Z0-9]+)+|Q\d|BF16|F16|F32|FP16|FP8)(?=[._-]|$)/i;
  const SHARD = /-\d{5}-of-\d{5}(?=\.gguf$)/i;
  const QUANT_PREF = ['Q4_K_M', 'Q4_K_S', 'Q4_K_XL', 'Q5_K_M', 'Q4_0', 'Q5_K_S', 'Q6_K', 'Q3_K_M', 'Q8_0', 'IQ4_XS'];

  /** Варианты скачивания: что именно можно взять из репозитория. */
  function makeOptions(files) {
    const opts = [];
    const lower = (f) => f.name.toLowerCase();
    const ggufs = files.filter((f) => lower(f).endsWith('.gguf') && !/mmproj/i.test(f.name));
    const diffusers = files.some((f) => f.name === 'model_index.json');
    if (ggufs.length) {
      const groups = new Map();
      for (const f of ggufs) {
        const base = f.name.replace(SHARD, '');
        if (!groups.has(base)) groups.set(base, []);
        groups.get(base).push(f);
      }
      for (const [base, fs] of groups) {
        const m = QUANT.exec(base.split('/').pop());
        const label = m ? m[1].toUpperCase() : base.split('/').pop().replace(/\.gguf$/i, '');
        opts.push({ id: base, label, files: fs, size: fs.reduce((a, f) => a + (f.size || 0), 0), note: fs.length > 1 ? fs.length + ' частей' : '' });
      }
      opts.sort((a, b) => a.size - b.size);
      let best = null;
      for (const q of QUANT_PREF) { best = opts.find((o) => o.label === q); if (best) break; }
      (best || opts[Math.floor(opts.length / 2)]).recommended = true;
      return opts;
    }
    const junk = /\.(msgpack|h5|onnx_data|tflite)$|^(flax_model|tf_model|rust_model)|(^|\/)(openvino|onnx|coreml)\//i;
    const hasSt = files.some((f) => lower(f).endsWith('.safetensors'));
    const keep = files.filter((f) => !junk.test(f.name) && !f.name.startsWith('.') && !(hasSt && /(^|\/)(original\/|consolidated[^/]*\.pth$)/i.test(f.name)) && !(hasSt && /\.(bin|pt|pth|ckpt)$/i.test(f.name) && /pytorch_model|model\.(bin|pt)/i.test(f.name)));
    if (diffusers) {
      const sub = keep.filter((f) => !/(^|\/)(?!model_index).*\.(ckpt)$/i.test(f.name));
      opts.push({ id: 'all', label: 'Весь пакет diffusers', files: sub, size: sub.reduce((a, f) => a + (f.size || 0), 0), note: 'модель целиком', recommended: true });
      return opts;
    }
    const singles = keep.filter((f) => /\.(safetensors|ckpt)$/i.test(f.name) && !f.name.includes('/') && f.size > 1e9);
    if (singles.length && !files.some((f) => f.name === 'config.json')) {
      singles.sort((a, b) => a.size - b.size).forEach((f, i, a) => opts.push({ id: f.name, label: f.name, files: [f], size: f.size, recommended: i === a.length - 1 }));
      return opts;
    }
    if (keep.length) opts.push({ id: 'all', label: 'Весь репозиторий', files: keep, size: keep.reduce((a, f) => a + (f.size || 0), 0), recommended: true });
    return opts;
  }

  /** Что приложение умеет делать с моделью. */
  function runnable(kind, options, task) {
    const gguf = options.length && options[0].files[0].name.toLowerCase().endsWith('.gguf');
    if (gguf && (kind === 'chat' || kind === 'code')) return { ok: true, level: 'full', text: 'Запускается в приложении через llama.cpp — на ПК и на телефоне.' };
    if (kind === 'image') return { ok: true, level: 'desktop', text: 'Генерация изображений: в настольной версии (нужен diffusers). На телефоне пока недоступно.' };
    if (kind === 'chat' || kind === 'code') return { ok: false, level: 'convert', text: 'Это не GGUF: скачать можно, но запустить напрямую нельзя. Найдите GGUF-версию (кнопка ниже) или подключите внешний сервер (Ollama/vLLM).', wantGguf: true };
    return { ok: false, level: 'store', text: 'Тип «' + (TASKS[task] || 'другое') + '»: приложение сохранит файлы, но запустить такую модель встроенными средствами пока нельзя.' };
  }

  /** Поместится ли модель в память устройства (грубая оценка). */
  function fit(sizeBytes, ramGb) {
    if (!sizeBytes || !ramGb) return { level: 'unknown', text: 'Память устройства неизвестна' };
    const need = sizeBytes / 1e9 * 1.2 + 0.6;
    if (need <= ramGb * 0.6) return { level: 'ok', text: 'Подойдёт вашему устройству' };
    if (need <= ramGb * 0.85) return { level: 'tight', text: 'Впритык по памяти — выберите квант поменьше' };
    return { level: 'no', text: 'Скорее всего не поместится в память — возьмите вариант меньше' };
  }

  const stripFrontMatter = (md) => md.replace(/^---[\s\S]*?\n---\s*\n/, '');
  function summarize(md) {
    if (!md) return '';
    const lines = stripFrontMatter(md).split('\n').map((l) => l.trim()).filter((l) => l && !/^(#|!\[|<|\[!\[|\||```|-{3,})/.test(l));
    const text = lines.join(' ').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[*_`]/g, '');
    return text.length > 320 ? text.slice(0, 320).replace(/\s\S*$/, '') + '…' : text;
  }

  function analyzeHf(repo, info, readme, wantFile) {
    const files = (info.siblings || []).map((s) => ({ name: s.rfilename, size: s.size || (s.lfs && s.lfs.size) || 0 }));
    const tags = info.tags || [], card = info.cardData || {};
    const hasIndex = files.some((f) => f.name === 'model_index.json');
    const name = repo.split('/')[1];
    const kind = kindOf(info.pipeline_tag, name, tags, hasIndex);
    let options = makeOptions(files);
    if (wantFile) { const o = options.find((x) => x.files.some((f) => f.name === wantFile)); if (o) { options.forEach((x) => (x.recommended = false)); o.recommended = true; } }
    const lic = card.license || (tags.find((t) => t.startsWith('license:')) || '').replace('license:', '');
    return {
      source: 'hf', repo, title: name, summary: summarize(readme), family: guessFamily(repo + ' ' + (info.gguf && info.gguf.architecture || '') + ' ' + tags.join(' ')),
      params: guessParams(name, info), task: info.pipeline_tag || '', taskLabel: TASKS[info.pipeline_tag] || (hasIndex ? 'Генерация изображений' : ''), kind, license: lic || '',
      downloads: info.downloads || 0, likes: info.likes || 0, gated: !!info.gated, arch: (info.gguf && info.gguf.architecture) || '', ctx: (info.gguf && info.gguf.context_length) || 0,
      baseModel: Array.isArray(card.base_model) ? card.base_model[0] : card.base_model || '', url: HF + '/' + repo, options, runnable: runnable(kind, options, info.pipeline_tag),
      warnings: [].concat(info.gated ? ['Модель закрытая (gated): нужен токен Hugging Face и принятое соглашение.'] : [], options.length ? [] : ['В репозитории не найдено подходящих файлов.']),
    };
  }

  function analyzeGithub(repo, info, releases) {
    const files = [];
    for (const r of releases || []) for (const a of r.assets || []) files.push({ name: a.name, size: a.size, url: a.browser_download_url, tag: r.tag_name });
    const models = files.filter((f) => MODEL_EXT.test(f.name) || /\.(zip|tar\.gz)$/i.test(f.name) && /model|weights/i.test(f.name));
    const name = repo.split('/')[1];
    const kind = kindOf('', name + ' ' + (info.description || ''), info.topics || [], false);
    const options = makeOptions(models.map((f) => ({ ...f }))).map((o) => ({ ...o, files: o.files.map((f) => ({ ...f })) }));
    return {
      source: 'github', repo, title: name, summary: info.description || '', family: guessFamily(repo + ' ' + (info.description || '') + ' ' + (info.topics || []).join(' ')), params: guessParams(name, null),
      task: '', taskLabel: info.language ? 'Проект на ' + info.language : '', kind, license: (info.license && (info.license.spdx_id || info.license.name)) || '', downloads: 0, likes: info.stargazers_count || 0,
      likesLabel: '★', gated: false, arch: '', ctx: 0, baseModel: '', url: info.html_url || 'https://github.com/' + repo, options, runnable: options.length ? runnable(kind, options, '') : { ok: false, level: 'none', text: 'В релизах нет файлов моделей. Это, скорее всего, программа или исходный код. Откройте вкладку «Поиск», чтобы найти готовую модель.' },
      warnings: options.length ? [] : ['Нет файлов моделей в последних релизах.'],
    };
  }

  function analyzeUrl(parsed) {
    const f = { name: parsed.file, size: 0, url: parsed.url };
    const options = makeOptions([f]);
    const opt = options.length ? options : [{ id: f.name, label: f.name, files: [f], size: 0, recommended: true }];
    const kind = kindOf('', f.name, [], false);
    return { source: 'url', repo: '', title: f.name.replace(MODEL_EXT, ''), summary: 'Прямая ссылка на файл. Размер и содержимое станут известны после начала загрузки.', family: guessFamily(f.name), params: guessParams(f.name, null),
      task: '', taskLabel: '', kind, license: '', downloads: 0, likes: 0, gated: false, arch: '', ctx: 0, baseModel: '', url: parsed.url, options: opt, runnable: runnable(kind, opt, ''), warnings: [] };
  }

  async function getJson(url, token, fetchImpl) {
    const r = await fetchImpl(url, token ? { headers: { Authorization: 'Bearer ' + token } } : {});
    if (r.status === 404) throw new Error('Репозиторий не найден (или он закрытый — укажите токен)');
    if (r.status === 401 || r.status === 403) throw new Error(r.status === 403 && url.includes('github') ? 'Лимит GitHub API исчерпан, попробуйте позже' : 'Нужен токен Hugging Face');
    if (!r.ok) throw new Error('Источник ответил ' + r.status);
    return r.json();
  }

  async function analyze(raw, opts) {
    opts = opts || {};
    const f = opts.fetch || ((...a) => root.fetch(...a));
    const p = parseInput(raw);
    if (p.source === 'url') return analyzeUrl(p);
    if (p.source === 'hf') {
      const info = await getJson(HF + '/api/models/' + p.repo + '?blobs=true', opts.token, f);
      let readme = '';
      try { const r = await f(HF + '/' + p.repo + '/raw/main/README.md'); if (r.ok) readme = (await r.text()).slice(0, 6000); } catch { /* описание необязательно */ }
      return analyzeHf(p.repo, info, readme, p.file);
    }
    const [info, rels] = await Promise.all([getJson(GH + '/repos/' + p.repo, opts.ghToken, f), getJson(GH + '/repos/' + p.repo + '/releases?per_page=5', opts.ghToken, f)]);
    return analyzeGithub(p.repo, info, rels);
  }

  const api = { parseInput, makeOptions, analyzeHf, analyzeGithub, analyzeUrl, analyze, fit, kindOf, guessFamily, guessParams, summarize, runnable };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.KiraAnalyze = api;
})(typeof window !== 'undefined' ? window : globalThis);
