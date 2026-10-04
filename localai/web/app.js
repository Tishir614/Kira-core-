'use strict';
/* Kira Local — ядро интерфейса: навигация, главная, поиск, карточка модели, библиотека, аккаунты. */
const $=id=>document.getElementById(id);
const api=async(url,opt={})=>{const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt});let d=null;try{d=await r.json()}catch{}
  if(!r.ok)throw new Error((d&&d.detail)||r.statusText);return d};
const post=(u,b)=>api(u,{method:'POST',body:JSON.stringify(b||{})});
const el=(tag,props={},...kids)=>{const e=Object.assign(document.createElement(tag),props);kids.forEach(k=>e.append(k));return e};
const icon=n=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('class','i');const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#i-'+n);s.append(u);return s};
const fmt=n=>n>=1e9?(n/1e9).toFixed(2)+' ГБ':n>=1e6?(n/1e6).toFixed(1)+' МБ':n>=1e3?(n/1e3).toFixed(0)+' КБ':(n||0)+' Б';
const num=n=>n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':String(n||0);
const store={get(k,d){try{const v=JSON.parse(localStorage.getItem(k));return v==null?d:v}catch{return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch{}}};
const initials=s=>(s||'?').trim().split(/[\s._-]+/).slice(0,2).map(x=>x[0]||'').join('').toUpperCase()||'?';
let toastT;function toast(t){const n=$('toast');n.textContent=t;n.classList.remove('hidden');clearTimeout(toastT);toastT=setTimeout(()=>n.classList.add('hidden'),2600)}
let models=[],status={slots:{chat:{},code:{}}},jobs=[];

/* ---------- аккаунты ---------- */
const tokens=()=>store.get('kira-tok',{hf:'',gh:''});
const profiles=()=>store.get('kira-prof',{hf:null,gh:null});
const displayProfile=()=>{const p=profiles();return p.hf||p.gh||null};

/* ---------- иллюстрации (монохромные SVG) ---------- */
const LEAVES='<g fill="currentColor"><path d="M34 222c-20-26-16-58 8-72 12 26 8 56-8 72z"/><path d="M48 222c-4-30 12-52 38-58-2 28-16 50-38 58z" opacity=".55"/><path d="M206 222c20-26 16-58-8-72-12 26-8 56 8 72z"/><path d="M192 222c4-30-12-52-38-58 2 28 16 50 38 58z" opacity=".55"/></g>';
const BOOKS='<g stroke="currentColor" stroke-width="3"><rect x="52" y="206" width="136" height="20" rx="4" fill="currentColor"/><rect x="62" y="184" width="116" height="22" rx="4" fill="var(--paper)"/><rect x="56" y="162" width="128" height="22" rx="4" fill="currentColor"/></g><path d="M72 195h96M66 173h116" stroke="var(--paper)" stroke-width="2"/>';
const ILL={
  robot:'<svg class="illus" viewBox="0 0 240 240" style="color:var(--ink)">'+LEAVES+BOOKS+'<g stroke="currentColor" stroke-width="4" stroke-linecap="round"><path d="M120 62V44"/><circle cx="120" cy="38" r="6" fill="currentColor"/><rect x="88" y="62" width="64" height="52" rx="16" fill="var(--paper)"/><rect x="96" y="114" width="48" height="44" rx="12" fill="currentColor"/><path d="M104 158v6M136 158v6"/></g><circle cx="106" cy="86" r="6" fill="currentColor"/><circle cx="134" cy="86" r="6" fill="currentColor"/><path d="M110 102q10 7 20 0" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/><g stroke="currentColor" stroke-width="3"><path d="M142 130l34-4" stroke-linecap="round"/><rect x="150" y="104" width="36" height="26" rx="3" fill="var(--paper)" transform="rotate(-8 168 117)"/></g></svg>',
  chat:'<svg class="illus" viewBox="0 0 240 200" style="color:var(--ink)"><g fill="currentColor"><path d="M30 190c-18-24-14-52 6-64 10 24 6 50-6 64z"/><path d="M212 190c18-24 14-52-6-64-10 24-6 50 6 64z"/></g><g stroke="currentColor" stroke-width="4"><rect x="52" y="30" width="136" height="96" rx="10" fill="var(--paper)"/><path d="M100 150h40M120 126v24"/></g><g fill="currentColor"><rect x="68" y="46" width="62" height="18" rx="9"/><rect x="108" y="74" width="64" height="18" rx="9" opacity=".6"/><rect x="68" y="102" width="40" height="12" rx="6"/></g></svg>',
  code:'<svg class="illus" viewBox="0 0 240 200" style="color:var(--ink)"><g fill="currentColor"><path d="M30 190c-18-24-14-52 6-64 10 24 6 50-6 64z"/><path d="M212 190c18-24 14-52-6-64-10 24-6 50 6 64z"/></g><g stroke="currentColor" stroke-width="4"><rect x="52" y="30" width="136" height="96" rx="10" fill="var(--paper)"/><path d="M100 150h40M120 126v24"/></g><g fill="none" stroke="currentColor" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"><path d="M96 62l-18 20 18 20M144 62l18 20-18 20M126 56l-12 52"/></g></svg>',
  image:'<svg class="illus" viewBox="0 0 240 200" style="color:var(--ink)"><g fill="currentColor"><path d="M30 190c-18-24-14-52 6-64 10 24 6 50-6 64z"/><path d="M212 190c18-24 14-52-6-64-10 24-6 50 6 64z"/></g><g stroke="currentColor" stroke-width="4"><rect x="44" y="28" width="152" height="108" rx="10" fill="var(--paper)"/></g><circle cx="150" cy="62" r="12" fill="currentColor"/><path d="M52 126l40-40 28 28 22-20 46 40z" fill="currentColor"/></svg>',
  other:'<svg class="illus" viewBox="0 0 240 200" style="color:var(--ink)"><g fill="currentColor"><path d="M30 190c-18-24-14-52 6-64 10 24 6 50-6 64z"/><path d="M212 190c18-24 14-52-6-64-10 24-6 50 6 64z"/></g><g stroke="currentColor" stroke-width="4" stroke-linejoin="round"><path d="M120 30 186 66v66l-66 36-66-36V66z" fill="var(--paper)"/><path d="M54 66l66 36 66-36M120 102v66"/></g></svg>'
};

/* ---------- навигация ---------- */
const ROOTS=['home','chat','code','image','duel','library','connect'];
const TITLES={home:'Главная',chat:'Чат',code:'Код',image:'Изображения',library:'Профиль и модели',connect:'Аккаунты'};
const MENU=[['home','box','Главная'],['chat','chat','Чат'],['code','code','Код'],['image','image','Изображения'],['duel','bolt','Дуэль моделей'],['library','user','Профиль и модели'],['connect','key','Аккаунты HF и GitHub']];
let stack=[],current=null;
function show(v){$('chatPop').classList.add('hidden');document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id==='v-'+v));current=v;closeMenu();if(onShow[v])onShow[v]()}
function go(v,{root=false}={}){if(root||ROOTS.includes(v))stack=[v];else stack.push(v);show(v)}
function back(){if(stack.length>1){stack.pop();show(stack[stack.length-1]);return true}return false}
const onShow={};
function openMenu(){buildMenu();$('menu').classList.add('open');$('scrim').classList.add('show')}
function closeMenu(){$('menu').classList.remove('open');$('scrim').classList.remove('show')}
function buildMenu(){const m=$('menu');m.replaceChildren(el('div',{style:'display:flex;align-items:center;gap:10px;margin-bottom:18px'},(()=>{const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('class','logo-mark');s.style.cssText='width:26px;height:34px';const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#logo-mark');s.append(u);return s})(),el('span',{className:'big-title logo',style:'font-size:24px',textContent:'kira local'})),
  ...MENU.map(([v,ic,t])=>{const b=el('button',{className:'mi'+(current===v?' on':'')},icon(ic),document.createTextNode(t));b.onclick=()=>go(v,{root:true});return b}),
  el('div',{className:'grow'}),el('div',{style:'font-size:12px;opacity:.6',textContent:'Всё работает локально. Ваши данные остаются на устройстве.'}))}
$('scrim').onclick=()=>{closeMenu()};
document.addEventListener('click',e=>{
  if(e.target.closest('[data-menu]'))openMenu();
  else if(e.target.closest('[data-back]'))back()||go('home');
  else if(e.target.closest('[data-avatar]'))go('library',{root:true});
  if(!e.target.closest('#chatPop')&&!e.target.closest('#chatMenu'))$('chatPop').classList.add('hidden')});
/* простые верхние полосы для экранов чат/код/изображения */
document.querySelectorAll('.view[data-title]').forEach(v=>{const bar=el('div',{className:'plainbar'},el('button',{className:'ibtn','data-menu':''},icon('menu')),el('span',{className:'title',textContent:v.dataset.title}),el('button',{className:'ibtn','data-avatar':''},icon('user')));v.prepend(bar)});
window.kiraBack=()=>{if(!$('lightbox').classList.contains('hidden')){$('lightbox').classList.add('hidden');return true}
  if($('menu').classList.contains('open')){closeMenu();return true}if(!$('chatPop').classList.contains('hidden')){$('chatPop').classList.add('hidden');return true}
  if(current==='onboard')return false;return back()};

/* ---------- состояние сервера ---------- */
const loaded=s=>(status.slots[s]||{}).model_id;
const isLoaded=m=>m.id===loaded('chat')||m.id===loaded('code');
async function refresh(){[models,status]=await Promise.all([api('/api/models'),api('/api/status')]);
  if(typeof onRefresh==='function')onRefresh();if(current==='home')renderHome();if(current==='library')renderLibrary()}
const ctxValue=()=>+(store.get('kira-gen',{}).ctx||(status.platform==='android'?2048:4096));
async function runModel(m,btn){if(m.kind==='image'){go('image',{root:true});return}if(m.kind==='other'){toast('Этот тип можно только хранить');return}
  const slot=m.kind==='code'?'code':'chat';if(btn){btn.disabled=true}toast('Запускаю «'+m.name+'»…');
  try{await post(`/api/slots/${slot}/load`,{model_id:m.id,ctx:ctxValue()});toast('Модель запущена ✓');store.set('kira-last',{id:m.id});await refresh();go(slot==='code'?'code':'chat',{root:true})}
  catch(e){toast(e.message)}if(btn)btn.disabled=false}
async function unloadModel(m){for(const s of ['chat','code'])if(loaded(s)===m.id)await post(`/api/slots/${s}/unload`);await refresh()}
async function bench(m,btn){if(!isLoaded(m))return toast('Сначала запустите модель');const slot=loaded('code')===m.id?'code':'chat';btn.disabled=true;toast('Тест скорости…');
  try{let n=0;const t0=performance.now();await stream(slot,[{role:'user',content:'Count from 1 to 40, separated by commas.'}],()=>{n++},null,null,{max_tokens:96});
    const tps=n/((performance.now()-t0)/1000);const b=store.get('kira-bench',{});b[m.id]=+tps.toFixed(1);store.set('kira-bench',b);toast(`Скорость: ${tps.toFixed(1)} ток/с`);renderLibrary()}catch(e){toast(e.message)}btn.disabled=false}

/* ---------- избранное / недавние ---------- */
const favs=()=>store.get('kira-fav',[]);const recents=()=>store.get('kira-recent',[]);
const isFav=id=>favs().some(f=>f.id===id);
function toggleFav(item){let f=favs();f=isFav(item.id)?f.filter(x=>x.id!==item.id):[{id:item.id,source:item.source,title:item.title},...f];store.set('kira-fav',f)}
function pushRecent(item){const r=[{id:item.id,source:item.source,title:item.title,kind:item.kind},...recents().filter(x=>x.id!==item.id)].slice(0,12);store.set('kira-recent',r)}

/* ---------- мелкие компоненты ---------- */
const FAMS=['Qwen','Llama','Gemma','Phi','Mistral','DeepSeek','SmolLM','FLUX','SDXL','Whisper'];
const famTile=(name,small)=>el('div',{className:'tile'+(small?' sm':''),textContent:(name||'?').replace(/[^A-Za-z0-9А-Яа-я]/g,'').slice(0,small?1:2)||'?'});
const playBtn=()=>el('span',{className:'playc'},icon('play'));
function row(tile,title,sub,right,onclick){const r=el('div',{className:'cardx rowx',style:onclick?'cursor:pointer':''},tile,el('div',{className:'grow'},el('div',{className:'t',textContent:title}),el('div',{className:'s',textContent:sub||''})),right||playBtn());if(onclick)r.onclick=onclick;return r}
const itemRow=it=>row(famTile(KiraAnalyze.guessFamily(it.id)||it.title,true),it.title,[it.owner,it.source==='hf'?(it.downloads?'⬇ '+num(it.downloads):''):'★ '+num(it.likes),it.task].filter(Boolean).join(' · '),null,()=>openDetail(it));
const section=(t)=>el('h2',{className:'sec',textContent:t});

/* ---------- онбординг ---------- */
const SLIDES=[['robot','найди лучший ИИ для себя!','Вставьте ссылку на модель с Hugging Face или GitHub — приложение поймёт, что это, и предложит скачать.'],
  ['chat','ИИ прямо на устройстве','Модели запускаются локально: без облака, без подписок, ваши данные остаются у вас.'],
  ['image','чат, код и картинки','Общайтесь, пишите код и создавайте изображения в одном приложении.']];
let obI=0;
function renderOnboard(){const [ill,t,p]=SLIDES[obI];$('obIll').innerHTML=ILL[ill];$('obTitle').textContent=t;$('obText').textContent=p;
  $('obDots').replaceChildren(...SLIDES.map((_,i)=>el('i',{className:i===obI?'on':''})));$('obNext').firstChild.textContent=obI===SLIDES.length-1?'Начать':'Далее'}
function endOnboard(){store.set('kira-onboarded',1);const t=tokens();go((t.hf||t.gh)?'home':'connect',{root:true})}
$('obNext').onclick=()=>{if(obI<SLIDES.length-1){obI++;renderOnboard()}else endOnboard()};$('obSkip').onclick=()=>{store.set('kira-onboarded',1);go('home',{root:true})};
$('acctDone').onclick=()=>go('home',{root:true});

/* ---------- аккаунты ---------- */
const ACCT={hf:{name:'Hugging Face',ic:'hf',url:'https://huggingface.co/settings/tokens',hint:'Создайте токен с правом «Read»',fn:KiraHub.hfWhoami},gh:{name:'GitHub',ic:'gh',url:'https://github.com/settings/tokens',hint:'Достаточно токена без особых прав (public_repo не нужен)',fn:KiraHub.ghUser}};
function renderConnect(){const box=$('acctBox');box.replaceChildren();const t=tokens(),p=profiles();
  for(const k of ['hf','gh']){const a=ACCT[k],prof=p[k];const card=el('div',{className:'cardx'});
    const head=el('div',{className:'acct'},el('div',{className:'avatar'},prof&&prof.avatar?el('img',{src:prof.avatar,alt:''}):icon(a.ic)),el('div',{className:'grow'},el('div',{className:'t',textContent:a.name,style:'font-weight:700'}),el('div',{className:'dim',textContent:prof?'Подключено: '+prof.fullname+(prof.name&&prof.name!==prof.fullname?' (@'+prof.name+')':''):'Не подключено'})));card.append(head);
    if(prof){const off=el('button',{className:'btn out sm center',style:'margin-top:10px',textContent:'Отключить'});off.onclick=()=>{const tt=tokens(),pp=profiles();tt[k]='';pp[k]=null;store.set('kira-tok',tt);store.set('kira-prof',pp);homeCache={};renderConnect();toast('Отключено')};card.append(off)}
    else{const inp=el('input',{type:'password',placeholder:'Вставьте токен',autocomplete:'off',style:'margin-top:10px'});const msg=el('div',{className:'dim',style:'margin-top:6px',textContent:a.hint});
      const link=el('a',{href:a.url,target:'_blank',rel:'noopener',textContent:'Создать токен →',style:'color:var(--ink);font-weight:700;font-size:13px'});
      const go1=el('button',{className:'btn',style:'margin-top:10px'},el('span',{textContent:'Войти через '+a.name}),icon('arrow'));
      go1.onclick=async()=>{const v=inp.value.trim();if(!v)return;go1.disabled=true;msg.textContent='Проверяю…';
        try{const me=await a.fn(v);const tt=tokens(),pp=profiles();tt[k]=v;pp[k]=me;store.set('kira-tok',tt);store.set('kira-prof',pp);homeCache={};toast('Подключено ✓');renderConnect()}catch(e){msg.textContent=e.message==='Failed to fetch'?'Нет связи с '+a.name:e.message;go1.disabled=false}};
      card.append(inp,msg,el('div',{style:'margin:6px 0'},link),go1)}
    box.append(card)}}
onShow.connect=renderConnect;

/* ---------- главная ---------- */
let homeCache={};
function renderHome(){const body=$('homeBody');body.replaceChildren();
  const last=store.get('kira-last',null),lm=last&&models.find(m=>m.id===last.id);
  if(lm&&!isLoaded(lm)&&lm.kind!=='image'&&lm.kind!=='other'){const b=el('button',{className:'btn',style:'margin-top:14px'},el('span',{textContent:'Продолжить с «'+lm.name+'»'}),icon('play'));b.onclick=()=>runModel(lm,b);body.append(b)}
  body.append(section('Рекомендуем для вас'));
  const tiles=el('div',{className:'tiles'});FAMS.forEach(f=>{const b=el('button',{},famTile(f),el('span',{textContent:f}));b.onclick=()=>openSearch(f,{src:'hf',chip:/FLUX|SDXL/.test(f)?'image':/Whisper/.test(f)?'all':'gguf'});tiles.append(b)});body.append(tiles);
  body.append(section('Быстрый старт'));
  [['chat','Чат с моделью','Общение и ответы на вопросы','chat'],['code','Помощник по коду','Написать, объяснить, исправить','code'],['image','Генерация изображений','Стили, форматы, галерея','image']].forEach(([v,t,s,ic])=>body.append(row(el('div',{className:'tile sm'},icon(ic)),t,s,null,()=>go(v,{root:true}))));
  const inst=models.filter(m=>m.kind!=='other').slice(0,3);
  if(inst.length){body.append(section('Продолжить'));inst.forEach(m=>body.append(row(famTile(KiraAnalyze.guessFamily(m.name)||m.name,true),m.name,(isLoaded(m)?'● запущена · ':'')+[m.kind,m.size?fmt(m.size):''].filter(Boolean).join(' · '),null,()=>runModel(m))))}
  const rec=recents();if(rec.length){body.append(section('Недавно просмотренные'));rec.slice(0,5).forEach(r=>body.append(row(famTile(KiraAnalyze.guessFamily(r.id)||r.title,true),r.title,r.id,null,()=>openDetail(r))))}
  const fv=favs();if(fv.length){body.append(section('Избранное'));fv.slice(0,5).forEach(r=>body.append(row(famTile(KiraAnalyze.guessFamily(r.id)||r.title,true),r.title,r.id,el('span',{className:'playc'},icon('heartf')),()=>openDetail(r))))}
  const t=tokens(),p=profiles();
  if(t.hf&&p.hf)lazySection(body,'Ваши лайки на Hugging Face','hfLikes',async()=>(await KiraHub.hfLikes(p.hf.name,t.hf)).map(id=>({source:'hf',id,owner:id.split('/')[0],title:id.split('/')[1],downloads:0,likes:0,task:''})));
  if(t.gh)lazySection(body,'Ваши звёзды на GitHub','ghStars',()=>KiraHub.ghStarred(t.gh));
  renderAvatarBtns()}
function lazySection(body,title,key,loader){const box=el('div');body.append(section(title),box);
  const draw=list=>{box.replaceChildren(...(list.length?list.slice(0,6).map(itemRow):[el('div',{className:'dim',textContent:'Пока пусто'})]))};
  if(homeCache[key]){draw(homeCache[key]);return}box.append(el('span',{className:'spin'}));
  loader().then(l=>{homeCache[key]=l;draw(l)}).catch(e=>box.replaceChildren(el('div',{className:'dim',textContent:e.message})))}
onShow.home=renderHome;
function renderAvatarBtns(){const p=displayProfile();document.querySelectorAll('[data-avatar]').forEach(b=>{b.replaceChildren(p&&p.avatar?el('img',{src:p.avatar,alt:'',style:'width:30px;height:30px;border-radius:50%;object-fit:cover;border:2px solid currentColor'}):icon('user'))})}
$('homeSearchForm').onsubmit=e=>{e.preventDefault();submitQuery($('homeQ').value)};
function looksLikeLink(t){t=t.trim();return /^https?:\/\//i.test(t)||/^(www\.)?(huggingface\.co|hf\.co|github\.com)\//i.test(t)||/^[\w.-]+\/[\w.-]+$/.test(t)}
function submitQuery(text){text=text.trim();if(!text)return;if(looksLikeLink(text))openDetail(text);else openSearch(text)}

/* ---------- поиск ---------- */
const S={q:'',src:'hf',chip:'all',sort:'popular',limit:30};
const CHIPS={hf:[['all','Все'],['gguf','GGUF'],['text','Текст'],['code','Код'],['image','Картинки'],['speech','Речь']],github:[['all','Все'],['llm','LLM'],['gguf','GGUF'],['image','Диффузия'],['speech','Речь']]};
function hfFilters(chip){return{all:[],gguf:['gguf'],text:['text-generation'],code:['text-generation'],image:['text-to-image'],speech:['automatic-speech-recognition']}[chip]||[]}
function renderChips(){$('chipRow').replaceChildren(...CHIPS[S.src].map(([k,t])=>{const b=el('button',{className:'chip'+(S.chip===k?' on':''),textContent:t});b.onclick=()=>{S.chip=k;S.limit=30;renderChips();runSearch()};return b}));
  [...$('srcSeg').children].forEach(b=>b.classList.toggle('on',b.dataset.s===S.src))}
$('srcSeg').onclick=e=>{const s=e.target.dataset.s;if(!s)return;S.src=s;S.chip='all';S.limit=30;renderChips();runSearch()};
$('sortSel').onchange=e=>{S.sort=e.target.value;S.limit=30;runSearch()};
$('searchForm').onsubmit=e=>{e.preventDefault();submitQuery($('searchQ').value)};
$('moreBtn').onclick=()=>{S.limit=Math.min(S.limit+30,120);runSearch()};
function openSearch(q,{src='hf',chip='all'}={}){S.q=q;S.src=src;S.chip=chip;S.limit=30;$('searchQ').value=q;go('search');renderChips();runSearch()}
let searchSeq=0;
async function runSearch(){const seq=++searchSeq,res=$('searchRes');res.replaceChildren(el('div',{style:'text-align:center;padding:20px'},el('span',{className:'spin'})));$('moreBtn').classList.add('hidden');$('sortSel').value=S.sort;
  const t=tokens();try{let list;
    if(S.src==='hf'){const q=S.chip==='code'&&!/code|coder/i.test(S.q)?(S.q+' code').trim():S.q;list=await KiraHub.hfSearch({q,filters:hfFilters(S.chip),sort:S.sort,limit:S.limit},t.hf)}
    else list=await KiraHub.ghSearch({q:S.q,topic:S.chip,sort:S.sort,limit:S.limit},t.gh);
    if(seq!==searchSeq)return;
    $('searchInfo').textContent=list.length?`${list.length} результатов${t[S.src==='hf'?'hf':'gh']?' · с вашим аккаунтом':''}`:'';
    res.replaceChildren(...(list.length?list.map(itemRow):[el('div',{className:'note'},el('span',{textContent:'Ничего не найдено. Попробуйте другое слово или фильтр «Все».'}))]));
    $('moreBtn').classList.toggle('hidden',list.length<S.limit||S.limit>=120)}
  catch(e){if(seq!==searchSeq)return;const msg=e.message==='Failed to fetch'?'Нет связи с источником (интернет или блокировка).':e.message;
    const n=el('div',{className:'note bad'},el('span',{textContent:msg}));res.replaceChildren(n);
    if(e.status===403||e.status===401){const b=el('button',{className:'btn out sm',textContent:'Подключить аккаунт'});b.onclick=()=>go('connect',{root:true});res.append(b)}}}

/* ---------- карточка модели ---------- */
let detail={a:null,opt:0,job:null,kind:null};
async function openDetail(itemOrText){const raw=typeof itemOrText==='string'?itemOrText:(itemOrText.source==='github'?'https://github.com/'+itemOrText.id:itemOrText.id);
  go('detail');$('dTitleBar').textContent='модель';$('detailBody').replaceChildren(el('div',{style:'text-align:center;padding:60px 0'},el('span',{className:'spin'}),el('p',{className:'dim',textContent:'Анализирую репозиторий…'})));
  const t=tokens();
  try{const a=await KiraAnalyze.analyze(raw,{token:t.hf||null,ghToken:t.gh||null});detail={a,opt:Math.max(0,a.options.findIndex(o=>o.recommended)),job:null,kind:a.kind};
    pushRecent({id:a.source==='hf'?a.repo:a.repo||a.title,source:a.source,title:a.title,kind:a.kind});renderDetail()}
  catch(e){const msg=e.message==='Failed to fetch'?'Нет связи с источником (интернет или блокировка).':e.message;const n=el('div',{className:'note bad'},el('span',{textContent:msg}));
    $('detailBody').replaceChildren(n);if(e.status===401||e.status===403){const b=el('button',{className:'btn out sm',textContent:'Подключить аккаунт'});b.onclick=()=>go('connect',{root:true});$('detailBody').append(b)}}}
const KIND_RU={chat:'чат',code:'код',image:'изображения',other:'другое'};
function ring(pct){const R=56,C=2*Math.PI*R;const w=el('div',{className:'ring'});w.innerHTML=`<svg viewBox="0 0 132 132"><circle class="bg" cx="66" cy="66" r="${R}"/><circle class="fg" cx="66" cy="66" r="${R}" stroke-dasharray="${C}" stroke-dashoffset="${C*(1-pct/100)}"/></svg>`;w.append(el('b',{textContent:Math.round(pct)+'%'}));return w}
function renderDetail(){const a=detail.a,body=$('detailBody');if(!a)return;const o=a.options[detail.opt];
  $('dTitleBar').textContent=a.title.length>22?a.title.slice(0,21)+'…':a.title;
  $('dFav').firstChild.replaceWith(icon(isFav(a.repo||a.title)?'heartf':'heart'));
  $('dFav').onclick=()=>{toggleFav({id:a.repo||a.title,source:a.source,title:a.title});renderDetail()};
  const top=el('div',{className:'detail-top'});top.innerHTML=ILL[a.kind==='chat'||a.kind==='code'||a.kind==='image'?a.kind:'other'];
  top.append(el('h1',{className:'big-title',style:'font-size:24px;margin-top:8px;text-transform:none;word-break:break-word',textContent:a.title}),
    el('div',{className:'dim',textContent:[a.family&&'Семейство '+a.family,a.repo||a.source,a.taskLabel].filter(Boolean).join(' · ')}));
  const tags=el('div',{className:'chips',style:'justify-content:center;flex-wrap:wrap;margin-top:8px'},el('span',{className:'badge',textContent:KIND_RU[a.kind]}),a.license?el('span',{className:'badge',textContent:a.license}):'',a.gated?el('span',{className:'badge',textContent:'gated'}):'',a.downloads?el('span',{className:'badge',textContent:'⬇ '+num(a.downloads)}):'',a.likes?el('span',{className:'badge',textContent:(a.likesLabel||'♥')+' '+num(a.likes)}):'');
  top.append(tags);body.replaceChildren(top);
  if(a.summary)body.append(el('p',{style:'margin:12px 0 0;font-size:14px',textContent:a.summary}));
  const stats=el('div',{className:'stats'});const st=(v,l)=>stats.append(el('div',{className:'stat'},el('b',{textContent:v}),el('hr'),el('span',{textContent:l})));
  st(o&&o.size?fmt(o.size):'—','размер');st(a.params||'—','параметров');st(a.ctx?num(a.ctx):'—','контекст');body.append(stats);
  body.append(el('div',{className:'note '+(a.runnable.ok?'good':'')},icon(a.runnable.ok?'bolt':'box'),el('span',{textContent:a.runnable.text})));
  if(a.runnable.wantGguf){const g=el('button',{className:'btn out sm',style:'margin-bottom:6px'},el('span',{textContent:'Найти GGUF-версию'}),icon('search'));g.onclick=()=>openSearch(a.title.replace(/[-_ ](instruct|chat|hf)$/i,'')+' GGUF',{src:'hf',chip:'gguf'});body.append(g)}
  a.warnings.forEach(w=>body.append(el('div',{className:'note bad'},el('span',{textContent:w}))));
  if(a.options.length){body.append(el('h2',{className:'sec',textContent:a.options.length>1?'Вариант (квантизация)':'Что будет скачано'}));
    if(a.options.length>1)body.append(el('p',{className:'dim',style:'margin:-4px 0 8px',textContent:'Чем меньше число в названии — тем легче и быстрее, но качество ниже. Звёздочка — рекомендуемый.'}));
    const ob=el('div',{className:'opts'});a.options.forEach((x,i)=>{const b=el('button',{className:'opt'+(i===detail.opt?' on':'')},el('b',{textContent:x.label+(x.recommended?' ★':'')}),el('span',{textContent:(x.size?fmt(x.size):'размер неизвестен')+(x.note?' · '+x.note:'')}));b.onclick=()=>{detail.opt=i;renderDetail()};ob.append(b)});body.append(ob);
    if(o&&o.size&&status.disk_free&&o.size+2e8>status.disk_free)body.append(el('div',{className:'note bad'},icon('box'),el('span',{textContent:`Не хватит места: нужно ≈ ${fmt(o.size)}, свободно ${fmt(status.disk_free)}. Выберите вариант меньше или удалите ненужные модели.`})));
    const f=KiraAnalyze.fit(o&&o.size,navigator.deviceMemory);if(f.level!=='unknown')body.append(el('div',{className:'note '+(f.level==='ok'?'good':f.level==='no'?'bad':'')},icon('bolt'),el('span',{textContent:f.text+(navigator.deviceMemory?` (память ≈ ${navigator.deviceMemory}+ ГБ по данным браузера)`:'')})));
    const kind=el('select',{style:'margin-top:12px'},...[['chat','Тип: чат'],['code','Тип: код'],['image','Тип: изображения'],['other','Тип: другое (только хранить)']].map(([v,t])=>el('option',{value:v,textContent:t,selected:v===detail.kind})));kind.onchange=()=>detail.kind=kind.value;body.append(kind)}
  const link=el('a',{href:a.url,target:'_blank',rel:'noopener',textContent:'Открыть на сайте →',style:'display:inline-block;margin-top:12px;color:var(--ink);font-weight:700;font-size:13px'});body.append(link);
  body.append(el('div',{className:'sticky',id:'dAction'}));renderDetailAction()}
function renderDetailAction(){const box=$('dAction');if(!box||!detail.a)return;const a=detail.a,o=a.options[detail.opt];box.replaceChildren();
  const job=detail.job&&jobs.find(j=>j.id===detail.job);
  if(job){const pct=job.total?100*job.done/job.total:0;
    if(job.status==='done'){const m=models.find(x=>x.id===job.model_id);const b=el('button',{className:'btn'},el('span',{textContent:m&&m.kind==='image'?'Открыть студию':'Запустить модель'}),icon('arrow'));b.onclick=()=>m?runModel(m,b):go('library',{root:true});box.append(el('div',{className:'note good'},icon('bolt'),el('span',{textContent:'Скачано и установлено ✓'})),b)}
    else if(job.status==='error'||job.status==='cancelled'){box.append(el('div',{className:'note bad'},el('span',{textContent:job.status==='error'?job.error:'Загрузка отменена'})));detail.job=null;box.append(dlButton(o))}
    else{const card=el('div',{style:'background:var(--ink);color:var(--paper);border-radius:18px;padding:16px;text-align:center'},el('div',{style:'font-weight:700',textContent:'Загрузка «'+job.name+'»'}),el('div',{style:'background:var(--paper);color:var(--ink);border-radius:14px;margin:12px auto;padding:10px;width:170px'},ring(pct)),
      el('div',{style:'font-size:13px;opacity:.8',textContent:`${fmt(job.done)} / ${job.total?fmt(job.total):'?'}${job.speed>0?' · '+fmt(job.speed)+'/с':''}`}));
      const c=el('button',{className:'btn out sm center',style:'margin-top:10px;width:100%',textContent:'Отмена'});c.onclick=()=>api('/api/downloads/'+job.id,{method:'DELETE'});card.append(c);box.append(card)}}
  else box.append(dlButton(o))}
function dlButton(o){const a=detail.a;const b=el('button',{className:'btn'},el('span',{textContent:o?'Скачать'+(o.size?' · '+fmt(o.size):''):'Нечего скачивать'}),icon('down'));b.disabled=!o;
  b.onclick=async()=>{const t=tokens();const name=a.title+(a.options.length>1?' ('+o.label+')':'');
    const req=a.source==='hf'?{source:'hf',repo:a.repo,files:o.files.map(f=>f.name),name,kind:detail.kind,hf_token:t.hf||null}:{source:a.source,repo:a.repo||undefined,urls:o.files.map(f=>f.url),name,kind:detail.kind};
    b.disabled=true;try{const j=await post('/api/downloads',req);detail.job=j.id;pollDownloads();renderDetailAction()}catch(e){toast(e.message);b.disabled=false}};return b}

/* ---------- загрузки ---------- */
let polling=false;const speedMap={};
async function pollDownloads(){if(polling)return;polling=true;
  try{for(;;){jobs=await api('/api/downloads');const now=Date.now();
    jobs.forEach(j=>{const p=speedMap[j.id];if(j.status==='downloading'){if(p&&now>p.t){const v=(j.done-p.d)/((now-p.t)/1000);speedMap[j.id]={t:now,d:j.done,v:p.v?p.v*.6+v*.4:v}}else if(!p)speedMap[j.id]={t:now,d:j.done,v:0};j.speed=speedMap[j.id].v}});
    if(current==='detail')renderDetailAction();if(current==='library')renderLibrary();
    if(!jobs.some(j=>j.status==='downloading'||j.status==='queued')){await refresh();if(current==='detail')renderDetailAction();break}
    await new Promise(r=>setTimeout(r,1000))}}finally{polling=false}}

/* ---------- профиль / библиотека ---------- */
function renderLibrary(){const p=displayProfile();const av=$('profAvatar');av.replaceChildren(p&&p.avatar?el('img',{src:p.avatar,alt:''}):document.createTextNode(initials(p?p.fullname:'Гость')));$('profName').textContent=p?p.fullname:'Гость';
  const body=$('libBody');const keepScroll=body.parentElement.scrollTop;body.replaceChildren();
  const total=models.reduce((a,m)=>a+(m.size||0),0);
  body.append(el('div',{className:'cardx',style:'text-align:center;margin-top:8px'},el('b',{style:'font-size:16px',textContent:`${models.length} ${models.length%10===1&&models.length!==11?'модель':'моделей'} установлено`}),el('div',{className:'dim',textContent:'занято '+fmt(total)+(status.disk_free?' · свободно '+fmt(status.disk_free):'')})));
  const active=jobs.filter(j=>j.status==='downloading'||j.status==='queued');
  if(active.length){body.append(section('В процессе'));active.forEach(j=>{const pr=el('progress',{max:j.total||1,value:j.done||0});const c=el('button',{className:'playc',title:'Отмена'},icon('x'));c.onclick=()=>api('/api/downloads/'+j.id,{method:'DELETE'});
    body.append(el('div',{className:'cardx'},el('div',{className:'rowx'},famTile(KiraAnalyze.guessFamily(j.name)||j.name,true),el('div',{className:'grow'},el('div',{className:'t',textContent:j.name}),el('div',{className:'s',textContent:`${fmt(j.done)} / ${j.total?fmt(j.total):'?'}${j.speed>0?' · '+fmt(j.speed)+'/с':''}`})),c),pr))})}
  const failed=jobs.filter(j=>j.status==='error');failed.slice(-2).forEach(j=>body.append(el('div',{className:'note bad'},el('span',{textContent:j.name+': '+j.error}))));
  body.append(section('Установленные'));
  if(!models.length)body.append(el('div',{className:'note'},el('span',{textContent:'Пока пусто. Найдите модель на главной или вставьте ссылку.'})));
  const benchs=store.get('kira-bench',{});
  models.forEach(m=>{const on=isLoaded(m);const card=el('div',{className:'cardx'});
    card.append(el('div',{className:'rowx'},famTile(KiraAnalyze.guessFamily(m.name)||m.name,true),el('div',{className:'grow'},el('div',{className:'t',textContent:m.name}),el('div',{className:'s',textContent:[on?'● запущена':'',m.size?fmt(m.size):'',m.format,benchs[m.id]?benchs[m.id]+' ток/с':''].filter(Boolean).join(' · ')})),el('span',{className:'badge',textContent:KIND_RU[m.kind]||m.kind})));
    const acts=el('div',{className:'rowx',style:'margin-top:9px;flex-wrap:wrap'});
    const run=el('button',{className:'btn sm'},el('span',{textContent:on?'Открыть':m.kind==='image'?'Студия':'Запустить'}));run.onclick=()=>on?go(loaded('code')===m.id?'code':'chat',{root:true}):runModel(m,run);acts.append(run);
    if(on){const u=el('button',{className:'btn out sm',textContent:'Выгрузить'});u.onclick=()=>unloadModel(m);acts.append(u);const bb=el('button',{className:'btn out sm'},icon('bolt'),el('span',{textContent:'Тест'}));bb.onclick=()=>bench(m,bb);acts.append(bb)}
    const d=el('button',{className:'btn danger sm'},icon('trash'));d.onclick=async()=>{if(confirm('Удалить '+m.name+'?')){await api('/api/models/'+m.id,{method:'DELETE'});refresh()}};acts.append(el('span',{className:'grow'}),d);card.append(acts);body.append(card)});
  const fv=favs();if(fv.length){body.append(section('Избранное'));fv.forEach(r=>body.append(row(famTile(KiraAnalyze.guessFamily(r.id)||r.title,true),r.title,r.id,el('span',{className:'playc'},icon('heartf')),()=>openDetail(r))))}
  body.append(section('Аккаунты'));const hub=el('button',{className:'btn out'},el('span',{textContent:p?'Управление аккаунтами':'Подключить Hugging Face / GitHub'}),icon('arrow'));hub.onclick=()=>go('connect',{root:true});body.append(hub);
  body.append(section('Статистика'));const sp=store.get('kira-stats',{msgs:0,imgs:0});body.append(el('div',{className:'stats',style:'margin-top:0'},...[[sp.msgs,'сообщений'],[sp.imgs,'картинок'],[Object.keys(benchs).length,'тестов']].map(([v,l])=>el('div',{className:'stat'},el('b',{textContent:v}),el('hr'),el('span',{textContent:l})))));
  body.append(section('Оформление'));const cur=store.get('kira-theme','auto');const seg=el('div',{className:'seg'},...[['auto','Авто'],['light','Светлая'],['dark','Тёмная']].map(([k,t])=>{const b=el('button',{className:cur===k?'on':'',textContent:t});b.onclick=()=>{store.set('kira-theme',k);applyTheme();renderLibrary()};return b}));body.append(seg);
  body.parentElement.scrollTop=keepScroll}
onShow.library=()=>{renderLibrary();pollDownloads()};
function applyTheme(){const m=store.get('kira-theme','auto'),r=document.documentElement;m==='auto'?r.removeAttribute('data-theme'):r.setAttribute('data-theme',m)}
applyTheme();

/* ---------- запуск ---------- */
(async function boot(){
  try{await refresh()}catch{}
  jobs=await api('/api/downloads').catch(()=>[]);if(jobs.some(j=>j.status==='downloading'))pollDownloads();
  if(!store.get('kira-onboarded',0)){stack=['onboard'];renderOnboard();show('onboard')}else go('home',{root:true});
  renderAvatarBtns()})();
