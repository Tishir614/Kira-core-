const test = require('node:test'), assert = require('node:assert');
const A = require('../web/analyze.js');
const GB = 1e9;

test('parseInput', () => {
  assert.deepStrictEqual(A.parseInput('Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF'), { source: 'hf', repo: 'Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF' });
  assert.deepStrictEqual(A.parseInput('https://huggingface.co/acme/tiny-GGUF/tree/main'), { source: 'hf', repo: 'acme/tiny-GGUF' });
  assert.deepStrictEqual(A.parseInput('huggingface.co/acme/tiny-GGUF/resolve/main/sub/tiny.Q4_K_M.gguf?download=true'), { source: 'hf', repo: 'acme/tiny-GGUF', file: 'sub/tiny.Q4_K_M.gguf' });
  assert.deepStrictEqual(A.parseInput('https://github.com/ggml-org/llama.cpp.git'), { source: 'github', repo: 'ggml-org/llama.cpp' });
  assert.strictEqual(A.parseInput('https://example.com/m/x.gguf').source, 'url');
  assert.throws(() => A.parseInput('https://huggingface.co/datasets/a/b'));
  assert.throws(() => A.parseInput('https://example.com/page'));
  assert.throws(() => A.parseInput('javascript:alert(1)'));
  assert.throws(() => A.parseInput(''));
});

const ggufInfo = {
  pipeline_tag: 'text-generation', tags: ['gguf', 'license:apache-2.0', 'code'], downloads: 1200, likes: 40, cardData: { license: 'apache-2.0', base_model: ['Qwen/Qwen2.5-Coder-1.5B'] },
  gguf: { total: 1543714304, architecture: 'qwen2', context_length: 32768 },
  siblings: [
    { rfilename: 'README.md', size: 1000 },
    { rfilename: 'qwen2.5-coder-1.5b-instruct-q8_0.gguf', size: 1.6 * GB },
    { rfilename: 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf', size: 0.99 * GB },
    { rfilename: 'qwen2.5-coder-1.5b-instruct-q2_k.gguf', size: 0.7 * GB },
    { rfilename: 'mmproj-f16.gguf', size: 0.3 * GB },
  ],
};

test('GGUF coder model', () => {
  const a = A.analyzeHf('Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF', ggufInfo, '---\nlicense: x\n---\n# Title\n\nQwen2.5-Coder is a [code](http://x) model.\n');
  assert.strictEqual(a.kind, 'code'); assert.strictEqual(a.family, 'Qwen'); assert.strictEqual(a.params, '1.5B'); assert.strictEqual(a.arch, 'qwen2');
  assert.deepStrictEqual(a.options.map((o) => o.label), ['Q2_K', 'Q4_K_M', 'Q8_0']);
  assert.strictEqual(a.options.find((o) => o.recommended).label, 'Q4_K_M');
  assert.ok(a.runnable.ok && a.runnable.level === 'full');
  assert.strictEqual(a.summary, 'Qwen2.5-Coder is a code model.');
  assert.strictEqual(a.license, 'apache-2.0');
});

test('sharded GGUF grouped, specific file preselected', () => {
  const info = { pipeline_tag: 'text-generation', siblings: ['a-Q4_K_M-00001-of-00002.gguf', 'a-Q4_K_M-00002-of-00002.gguf', 'a-Q8_0.gguf'].map((n) => ({ rfilename: n, size: 2 * GB })) };
  const a = A.analyzeHf('o/a-GGUF', info, '', 'a-Q8_0.gguf');
  assert.strictEqual(a.options.length, 2);
  assert.strictEqual(a.options.find((o) => o.label === 'Q4_K_M').files.length, 2);
  assert.strictEqual(a.options.find((o) => o.recommended).label, 'Q8_0');
});

test('diffusers image model', () => {
  const info = { pipeline_tag: 'text-to-image', siblings: [{ rfilename: 'model_index.json', size: 500 }, { rfilename: 'unet/diffusion_pytorch_model.safetensors', size: 3 * GB }, { rfilename: 'unet/diffusion_pytorch_model.bin', size: 3 * GB }, { rfilename: 'vae/x.msgpack', size: 10 }] };
  const a = A.analyzeHf('stabilityai/stable-diffusion-2', info, '');
  assert.strictEqual(a.kind, 'image'); assert.strictEqual(a.runnable.level, 'desktop');
  assert.ok(a.options[0].files.every((f) => !f.name.endsWith('.msgpack')));
});

test('non-GGUF LLM suggests conversion; other tasks only stored', () => {
  const llm = A.analyzeHf('o/Llama-3-8B', { pipeline_tag: 'text-generation', siblings: [{ rfilename: 'config.json', size: 1 }, { rfilename: 'model.safetensors', size: 16 * GB }] }, '');
  assert.strictEqual(llm.kind, 'chat'); assert.ok(llm.runnable.wantGguf); assert.strictEqual(llm.params, '8B');
  const asr = A.analyzeHf('openai/whisper-tiny', { pipeline_tag: 'automatic-speech-recognition', siblings: [{ rfilename: 'model.safetensors', size: 1e8 }] }, '');
  assert.strictEqual(asr.kind, 'other'); assert.strictEqual(asr.runnable.level, 'store'); assert.strictEqual(asr.taskLabel, 'Распознавание речи');
});

test('github repo with and without model assets', () => {
  const rel = [{ tag_name: 'v1', assets: [{ name: 'tiny-Q4_K_M.gguf', size: 5e8, browser_download_url: 'https://github.com/o/r/releases/download/v1/tiny-Q4_K_M.gguf' }, { name: 'src.zip', size: 10, browser_download_url: 'https://github.com/x' }] }];
  const a = A.analyzeGithub('o/r', { description: 'tiny llama', stargazers_count: 7 }, rel);
  assert.strictEqual(a.options.length, 1); assert.ok(a.options[0].files[0].url.startsWith('https://github.com/'));
  const b = A.analyzeGithub('o/prog', { description: 'a tool' }, [{ tag_name: 'v1', assets: [{ name: 'app.exe', size: 1, browser_download_url: 'u' }] }]);
  assert.strictEqual(b.options.length, 0); assert.strictEqual(b.runnable.ok, false);
});

test('fit and analyze() with mocked fetch', async () => {
  assert.strictEqual(A.fit(1 * GB, 8).level, 'ok'); assert.strictEqual(A.fit(5 * GB, 8).level, 'tight'); assert.strictEqual(A.fit(9 * GB, 8).level, 'no'); assert.strictEqual(A.fit(1 * GB, 0).level, 'unknown');
  const fetchMock = async (u) => (u.includes('/api/models/') ? { ok: true, status: 200, json: async () => ggufInfo } : u.endsWith('README.md') ? { ok: true, status: 200, text: async () => 'Hello model' } : { ok: false, status: 404 });
  const a = await A.analyze('https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF', { fetch: fetchMock });
  assert.strictEqual(a.summary, 'Hello model');
  await assert.rejects(A.analyze('a/b', { fetch: async () => ({ ok: false, status: 404 }) }), /не найден/);
});

test('duplicate original/ weights are dropped when safetensors exist', () => {
  const info = { pipeline_tag: 'text-generation', siblings: [{ rfilename: 'config.json', size: 1 }, { rfilename: 'model.safetensors', size: 6e9 }, { rfilename: 'original/consolidated.00.pth', size: 6e9 }, { rfilename: 'original/params.json', size: 1 }] };
  const a = A.analyzeHf('o/Llama-3-3B', info, '');
  assert.deepStrictEqual(a.options[0].files.map((f) => f.name).sort(), ['config.json', 'model.safetensors']);
});
