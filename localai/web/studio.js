'use strict';
/* Kira Local — чат, код и изображения. */
const genCfg=()=>({temp:0.7,max:0,ctx:0,...store.get('kira-gen',{})});
const bumpStat=k=>{const s=store.get('kira-stats',{msgs:0,imgs:0});s[k]=(s[k]||0)+1;store.set('kira-stats',s)};

/* ---------- стриминг ---------- */
async function stream(slot,messages,onText,onStats,signal,extra={}){
  const g=genCfg();const body={slot,messages,temperature:g.temp,...(g.max?{max_tokens:g.max}:{}),...extra};
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
  if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||r.statusText)}
  const rd=r.body.getReader(),dec=new TextDecoder();let buf='',full='',n=0;const t0=performance.now();
  for(;;){const{done,value}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});
    let i;while((i=buf.indexOf('\n'))>=0){const line=buf.slice(0,i).trim();buf=buf.slice(i+1);
      if(!line.startsWith('data:'))continue;const d=line.slice(5).trim();if(d==='[DONE]')continue;
      let j;try{j=JSON.parse(d)}catch{continue}if(j.error)throw new Error(j.error);const t=j.choices?.[0]?.delta?.content;
      if(t){full+=t;n++;onText(full);if(onStats)onStats(n/((performance.now()-t0)/1000||1))}}}
  return full}
function renderRich(node,text,md=true){node.replaceChildren();text.split(/(```[\s\S]*?(?:```|$))/g).forEach(part=>{
  if(part.startsWith('```')){const body=part.replace(/^```[^\n]*\n?/,'').replace(/```$/,'');const pre=el('pre',{},el('code',{textContent:body}));
    const b=el('button',{className:'copy',textContent:'Копировать'});b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(body);b.textContent='✓'};pre.append(b);node.append(pre)}
  else if(part){if(md&&window.KiraMd)KiraMd.render(node,part);else node.append(document.createTextNode(part))}})}
const typing=()=>el('span',{className:'typing'},el('i'),el('i'),el('i'));

/* ---------- выбор моделей ---------- */
function fillSelect(id,list,sel){const s=$(id),prev=s.value,last=s.dataset.sel||'';
  s.replaceChildren(...(list.length?list.map(m=>el('option',{value:m.id,textContent:(m.id===sel?'● ':'')+m.name})):[el('option',{value:'',textContent:'— нет моделей —'})]));
  // Если запущенная модель сменилась — показываем её; иначе не сбрасываем выбор пользователя.
  s.value=(sel&&sel!==last)?sel:(prev&&list.some(m=>m.id===prev)?prev:(sel||(list[0]&&list[0].id)||''));s.dataset.sel=sel||''}
function onRefresh(){fillSelect('chatModel',models.filter(m=>m.kind==='chat'||m.kind==='code'),loaded('chat'));
  fillSelect('codeModel',[...models.filter(m=>m.kind==='code'),...models.filter(m=>m.kind==='chat')],loaded('code'));
  fillSelect('imgModel',models.filter(m=>m.kind==='image'));
  $('chatLoad').textContent=loaded('chat')&&$('chatModel').value===loaded('chat')?'Выгрузить':'Запустить';
  $('codeLoad').textContent=loaded('code')&&$('codeModel').value===loaded('code')?'Выгрузить':'Запустить';
  imgModelChanged()}
async function slotAction(slot,sel,btn){const id=$(sel).value,m=models.find(x=>x.id===id);if(!m){toast('Нет моделей — скачайте на главной');return go('home',{root:true})}
  if(loaded(slot)===id){await post(`/api/slots/${slot}/unload`);return refresh()}
  btn.disabled=true;btn.textContent='Запуск…';try{await post(`/api/slots/${slot}/load`,{model_id:id,ctx:ctxValue()});toast('Модель запущена ✓')}catch(e){toast(e.message)}btn.disabled=false;await refresh()}
$('chatLoad').onclick=e=>slotAction('chat','chatModel',e.target);$('codeLoad').onclick=e=>slotAction('code','codeModel',e.target);
$('chatModel').onchange=onRefresh;$('codeModel').onchange=onRefresh;
$('chatUnload').onclick=async()=>{await post('/api/slots/chat/unload');refresh();toast('Модель выгружена')};

/* ---------- чаты ---------- */
const PERSONAS={default:['Обычный ассистент','Ты дружелюбный и точный ассистент. Отвечай на языке пользователя, кратко и по делу.'],
  tutor:['Репетитор','Ты терпеливый репетитор. Объясняй пошагово, простыми словами, приводи примеры и проверяй понимание вопросом в конце.'],
  translator:['Переводчик','Ты профессиональный переводчик. Переводи текст пользователя между русским и английским, сохраняя стиль. Выводи только перевод.'],
  editor:['Редактор текста','Ты редактор. Исправляй ошибки, улучшай стиль и ясность, сохраняя смысл. Покажи исправленный текст и кратко перечисли правки.'],
  summarizer:['Конспект','Ты делаешь краткие структурированные конспекты: главные мысли списком, затем вывод в одно предложение.'],
  coder:['Программист','Ты старший программист. Давай рабочий код в блоках ``` и короткие пояснения. Учитывай крайние случаи.'],
  custom:['Своя инструкция…','']};
$('persona').replaceChildren(...Object.entries(PERSONAS).map(([k,v])=>el('option',{value:k,textContent:v[0]})));
let chats=store.get('kira-chats',[]),cur=store.get('kira-cur',null);
if(!chats.length){chats=[{id:Date.now(),title:'Новый чат',persona:'default',custom:'',messages:[]}];cur=chats[0].id}
const chat=()=>chats.find(c=>c.id===cur)||chats[0];
const save=()=>{store.set('kira-chats',chats);store.set('kira-cur',cur)};
const sys=c=>c.persona==='custom'?c.custom:PERSONAS[c.persona]?.[1]||'';
function renderChatList(){$('chatSel').replaceChildren(...chats.map(c=>el('option',{value:c.id,textContent:c.title,selected:c.id===cur})))}
function bubble(role,text,meta){const user=role==='user';const b=el('div',{className:'bub'});const col=el('div',{className:'col'},b);const n=el('div',{className:'msg '+(user?'user':'')},col);
  if(text)renderRich(b,text,!user);else b.append(typing());if(meta)col.append(el('div',{className:'meta',textContent:meta}));$('chatLog').append(n);$('chatLog').scrollTop=1e9;return{b,col}}
function renderChat(){const c=chat();$('persona').value=c.persona;$('customPrompt').classList.toggle('hidden',c.persona!=='custom');$('customPrompt').value=c.custom||'';
  const log=$('chatLog');log.replaceChildren();
  if(!c.messages.length){const e=el('div',{className:'hero-empty'});e.innerHTML=ILL.robot;e.append(el('h3',{textContent:'чем помочь?'}),el('div',{textContent:'Запустите модель и начните диалог. Всё работает локально.'}));
    const chips=el('div',{className:'chips',style:'justify-content:center;flex-wrap:wrap;margin-top:12px'});['Объясни, как работает нейросеть','Придумай идею для pet-проекта','Составь план тренировок на неделю'].forEach(t=>{const b=el('button',{className:'chip',textContent:t});b.onclick=()=>{$('chatInput').value=t;$('chatInput').focus()};chips.append(b)});e.append(chips);log.append(e)}
  c.messages.forEach((m,i)=>{const b=bubble(m.role,m.content,m.meta);if(m.role==='assistant')actions(b.col,c,i)})}
$('chatSel').onchange=e=>{cur=+e.target.value;save();renderChat()};
$('chatNew').onclick=()=>{const c={id:Date.now(),title:'Новый чат',persona:chat().persona,custom:chat().custom,messages:[]};chats.unshift(c);cur=c.id;save();renderChatList();renderChat()};
$('persona').onchange=e=>{chat().persona=e.target.value;save();renderChat()};$('customPrompt').oninput=e=>{chat().custom=e.target.value;save()};
$('chatMenu').onclick=e=>{e.stopPropagation();$('chatPop').classList.toggle('hidden');const g=genCfg();$('temp').value=g.temp;$('tempVal').textContent=g.temp;$('maxTok').value=String(g.max||0);$('ctxSel').value=String(g.ctx||ctxValue())};
const saveGen=()=>store.set('kira-gen',{temp:+$('temp').value,max:+$('maxTok').value,ctx:+$('ctxSel').value});
$('temp').oninput=()=>{$('tempVal').textContent=$('temp').value;saveGen()};$('maxTok').onchange=saveGen;$('ctxSel').onchange=()=>{saveGen();toast('Контекст применится при следующем запуске модели')};
$('chatExport').onclick=()=>{const c=chat();navigator.clipboard&&navigator.clipboard.writeText(c.messages.map(m=>`**${m.role==='user'?'Вы':'Модель'}:**\n\n${m.content}`).join('\n\n---\n\n'));toast('Чат скопирован в Markdown')};
$('chatDel').onclick=()=>{if(!confirm('Удалить этот чат?'))return;chats=chats.filter(x=>x.id!==cur);if(!chats.length)chats.push({id:Date.now(),title:'Новый чат',persona:'default',custom:'',messages:[]});cur=chats[0].id;save();renderChatList();renderChat();$('chatPop').classList.add('hidden')};
/* библиотека промптов */
$('promptSave').onclick=()=>{const t=$('chatInput').value.trim();if(!t)return toast('Сначала напишите текст в поле ввода');const p=store.get('kira-prompts',[]);if(!p.includes(t))p.unshift(t);store.set('kira-prompts',p.slice(0,30));toast('Промпт сохранён')};
function promptLibrary(){const p=store.get('kira-prompts',[]),lb=$('lightbox');lb.classList.remove('hidden');
  const list=el('div',{style:'width:100%;max-width:480px;max-height:60vh;overflow:auto'});
  if(!p.length)list.append(el('div',{className:'dim',style:'color:#ccc',textContent:'Пока нет сохранённых промптов. Напишите текст в поле ввода и нажмите «Сохранить ввод».'}));
  p.forEach((t,i)=>{const use=el('button',{className:'btn sm',style:'flex:1;text-align:left;justify-content:flex-start;overflow:hidden',textContent:t.length>70?t.slice(0,70)+'…':t});use.onclick=()=>{$('chatInput').value=t;lb.classList.add('hidden');$('chatPop').classList.add('hidden');go('chat',{root:true});$('chatInput').focus()};
    const d=el('button',{className:'btn sm danger'},icon('x'));d.onclick=()=>{p.splice(i,1);store.set('kira-prompts',p);promptLibrary()};list.append(el('div',{className:'rowx',style:'margin:6px 0'},use,d))});
  const c=el('button',{className:'btn sm',textContent:'Закрыть'});c.onclick=()=>lb.classList.add('hidden');lb.replaceChildren(el('h3',{style:'color:#fff;font-size:20px',textContent:'мои промпты'}),list,c)}
$('promptList').onclick=promptLibrary;
/* вложение файла и голос */
$('attachBtn').onclick=()=>$('attachFile').click();
$('attachFile').onchange=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;if(f.size>200000)return toast('Файл слишком большой (до 200 КБ)');
  const t=await f.text();$('chatInput').value=($('chatInput').value.trim()?$('chatInput').value.trim()+'\n\n':'')+`Файл «${f.name}»:\n\`\`\`\n${t}\n\`\`\`\n`;autosize();toast('Файл добавлен в сообщение')};
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SR){$('micBtn').classList.remove('hidden');let rec=null;$('micBtn').onclick=()=>{if(rec){rec.stop();return}rec=new SR();rec.lang='ru-RU';rec.interimResults=true;const base=$('chatInput').value;
  rec.onresult=ev=>{$('chatInput').value=(base?base+' ':'')+[...ev.results].map(r=>r[0].transcript).join('');autosize()};rec.onend=()=>{rec=null;$('micBtn').style.opacity=1};rec.onerror=()=>{rec=null};$('micBtn').style.opacity=.5;try{rec.start()}catch{rec=null}}}
/* отправка / стоп / повтор */
let abortCtl=null;
function setBusy(on){$('chatSend').replaceChildren(icon(on?'stop':'send'));$('chatSend').title=on?'Остановить':'Отправить'}
function actions(col,c,idx){const row=el('div',{className:'acts'});const cp=el('button',{textContent:'Копировать'});cp.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(c.messages[idx].content);cp.textContent='✓'};row.append(cp);
  if(idx===c.messages.length-1){const rg=el('button',{textContent:'↻ Повторить'});rg.onclick=()=>{if(abortCtl)return;c.messages.pop();save();renderChat();generate(c)};row.append(rg)}col.append(row)}
async function generate(c){
  const out=bubble('assistant','');abortCtl=new AbortController();setBusy(true);let part='',tps=0;
  const history=[...(sys(c)?[{role:'system',content:sys(c)}]:[]),...c.messages.map(({role,content})=>({role,content}))];
  try{part=await stream('chat',history,x=>{part=x;renderRich(out.b,x);$('chatLog').scrollTop=1e9},v=>tps=v,abortCtl.signal);c.messages.push({role:'assistant',content:part,meta:tps?`${tps.toFixed(1)} ток/с`:''})}
  catch(e){if(e.name==='AbortError'){if(part)c.messages.push({role:'assistant',content:part,meta:'остановлено'});else out.b.replaceChildren(el('span',{className:'dim',textContent:'Остановлено'}))}
    else{abortCtl=null;setBusy(false);const u=c.messages.pop();save();$('chatInput').value=u?u.content:'';autosize();renderChat();
      if(/не загружена/.test(e.message)){toast('Сначала запустите модель');go('library',{root:true})}else toast(e.message);return}}
  save();abortCtl=null;setBusy(false);renderChat()}
async function send(){if(abortCtl){abortCtl.abort();return}
  const t=$('chatInput').value.trim();if(!t)return;const c=chat();$('chatInput').value='';autosize();
  if(!c.messages.length){c.title=t.slice(0,32);renderChatList();$('chatLog').replaceChildren()}
  c.messages.push({role:'user',content:t});bubble('user',t);bumpStat('msgs');save();generate(c)}
$('chatSend').onclick=send;
const autosize=()=>{const t=$('chatInput');t.style.height='46px';t.style.height=Math.min(t.scrollHeight,140)+'px'};
$('chatInput').oninput=autosize;$('chatInput').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&window.innerWidth>700){e.preventDefault();send()}};

/* ---------- код ---------- */
[['Объяснить','Объясни, что делает этот код, по шагам.'],['Найти баг','Найди ошибки в этом коде и исправь их.'],['Рефакторинг','Сделай рефакторинг: чище, читаемее, без изменения поведения.'],['Тесты','Напиши unit-тесты для этого кода.'],['Оптимизировать','Оптимизируй этот код по скорости и памяти.'],['Комментарии','Добавь понятные комментарии и docstring.']].forEach(([t,p])=>{
  const b=el('button',{className:'chip',textContent:t});b.onclick=()=>{$('codeTask').value=p};$('codeChips').append(b)});
$('codeRun').onclick=async()=>{const task=$('codeTask').value.trim();if(!task)return;const src=$('codeSrc').value.trim(),lang=$('codeLang').value.trim()||'код';
  const sysm=`Ты опытный программист-ассистент. Язык: ${lang}. Отвечай кратко, код — в блоках \`\`\`. Отвечай на языке пользователя.`;
  const user=src?`${task}\n\n\`\`\`\n${src}\n\`\`\``:task;
  const out=$('codeOut');out.replaceChildren();const card=el('div',{className:'cardx'},typing());out.append(card);$('codeRun').disabled=true;
  try{await stream('code',[{role:'system',content:sysm},{role:'user',content:user}],x=>renderRich(card,x))}catch(e){card.replaceChildren(el('span',{style:'color:var(--bad)',textContent:e.message}))}
  $('codeRun').disabled=false};
$('codeClear').onclick=()=>{$('codeOut').replaceChildren();$('codeSrc').value='';$('codeTask').value=''};

/* ---------- изображения ---------- */
const STYLES=[['Без стиля','',''],['Фото','photorealistic, highly detailed, natural lighting, 85mm photo','cartoon, illustration, painting, deformed'],['Аниме','anime style, vibrant colors, clean lineart, studio quality','photo, realistic, blurry'],
  ['Живопись','digital painting, concept art, dramatic lighting, artstation','photo, lowres'],['3D','3d render, octane render, soft studio lighting, high detail','flat, lowres'],['Пиксель-арт','pixel art, 16-bit, limited palette, crisp pixels','blurry, smooth, photo'],
  ['Акварель','watercolor painting, soft washes, paper texture','photo, sharp digital'],['Кино','cinematic still, anamorphic lens, film grain, moody lighting','cartoon, flat lighting']];
const RATIOS=[['Квадрат',512,512],['Портрет',512,768],['Пейзаж',768,512],['Широкий',768,448],['SDXL',1024,1024]];
const IDEAS=['уютная хижина в заснеженном лесу на закате','киберпанк-город под дождём, неоновые вывески','дружелюбный робот-повар на кухне','космонавт верхом на олене в тумане','старая библиотека с парящими свечами','кот-самурай в осеннем саду'];
let styleIdx=0,ratioIdx=0,countN=1,curJob=null;
const markOne=(box,i)=>[...box.children].forEach((x,j)=>x.classList.toggle('on',j===i));
$('imgStyles').replaceChildren(...STYLES.map(([t],i)=>{const b=el('button',{className:'chip'+(i===0?' on':''),textContent:t});b.onclick=()=>{styleIdx=i;markOne($('imgStyles'),i)};return b}));
$('imgRatio').replaceChildren(...RATIOS.map(([t,w,h],i)=>{const b=el('button',{className:'chip'+(i===0?' on':''),textContent:`${t} ${w}×${h}`});b.onclick=()=>{ratioIdx=i;$('imgW').value=w;$('imgH').value=h;markOne($('imgRatio'),i)};return b}));
$('imgCount').replaceChildren(...[1,2,3,4].map(n=>{const b=el('button',{className:'chip'+(n===1?' on':''),textContent:String(n)});b.onclick=()=>{countN=n;markOne($('imgCount'),n-1)};return b}));
$('imgDice').onclick=()=>{$('imgSeed').value=Math.floor(Math.random()*2**31)};
$('imgIdea').onclick=()=>{$('imgPrompt').value=IDEAS[Math.floor(Math.random()*IDEAS.length)]};
$('imgImprove').onclick=async()=>{const t=$('imgPrompt').value.trim();if(!t)return $('imgHelp').textContent='Сначала напишите идею';
  $('imgHelp').textContent='Думаю…';$('imgImprove').disabled=true;
  try{await stream('chat',[{role:'system',content:'Ты помощник по промптам для генерации изображений (Stable Diffusion). Перепиши идею пользователя в один подробный абзац на английском: сюжет, композиция, свет, стиль, детали. Только текст промпта, без пояснений и кавычек.'},{role:'user',content:t}],x=>{$('imgPrompt').value=x});$('imgHelp').textContent='Готово ✓'}
  catch(e){$('imgHelp').textContent=e.message.includes('не загружена')?'Для улучшения запустите текстовую модель в чате':e.message}$('imgImprove').disabled=false};
function imgModelChanged(){const m=models.find(x=>x.id===$('imgModel').value);const remote=m&&m.format==='remote_image';const w=$('imgWarn');
  const bad=!m||(!remote&&!status.images);w.classList.toggle('hidden',!bad);
  w.textContent=!m?'Нет модели изображений. Вставьте ссылку на модель (для ПК) или подключите сервер A1111/Forge/OpenAI: «Профиль» → «Свой сервер» ниже. Это работает и на телефоне.':status.platform==='android'?'На телефоне такая модель не запустится. Подключите внешний сервер (A1111/Forge/OpenAI).':'Для локальной генерации: pip install diffusers torch transformers accelerate safetensors — или подключите внешний сервер.'}
$('imgModel').onchange=imgModelChanged;
function fullPrompt(){const st=STYLES[styleIdx];return{prompt:$('imgPrompt').value.trim()+(st[1]?', '+st[1]:''),negative:[$('imgNeg').value.trim(),st[2]].filter(Boolean).join(', ')}}
const imgCard=im=>{const i=el('img',{src:im.url,loading:'lazy',alt:im.prompt||''});i.onclick=()=>lightbox(im);return i};
async function pollImage(id){for(;;){const j=await api('/api/image/'+id);const pct=j.total?Math.round(100*j.step/j.total):0;
  $('imgBar').querySelector('i').style.width=(j.status==='running'&&!j.step?5:pct)+'%';
  $('imgState').textContent=j.status==='running'?`Генерация… ${pct}% (${j.images.length}/${countN})`:j.status==='queued'?'В очереди…':'';
  $('imgOut').replaceChildren(...j.images.map(imgCard));
  if(j.status==='error')throw new Error(j.error);if(['done','cancelled'].includes(j.status))return j;await new Promise(r=>setTimeout(r,700))}}
$('imgRun').onclick=async()=>{const id=$('imgModel').value;if(!id)return $('imgState').textContent='Нет модели изображений.';if(!$('imgPrompt').value.trim())return $('imgState').textContent='Напишите промпт';
  const seed=$('imgSeed').value,fp=fullPrompt();$('imgRun').disabled=true;$('imgCancel').classList.remove('hidden');$('imgBar').classList.remove('hidden');$('imgBar').querySelector('i').style.width='0';$('imgOut').replaceChildren();
  try{const job=await post('/api/image',{model_id:id,...fp,steps:+$('imgSteps').value,guidance:+$('imgCfg').value,width:+$('imgW').value,height:+$('imgH').value,count:countN,seed:seed===''?null:+seed});curJob=job.id;
    const j=await pollImage(job.id);$('imgState').textContent=j.status==='cancelled'?'Остановлено':`Готово ✓ seed: ${j.images[0]?j.images[0].seed:''}`;j.images.forEach(()=>bumpStat('imgs'));loadGallery()}
  catch(e){$('imgState').textContent=e.message}
  curJob=null;$('imgRun').disabled=false;$('imgCancel').classList.add('hidden');setTimeout(()=>$('imgBar').classList.add('hidden'),600)};
$('imgCancel').onclick=()=>{if(curJob)api('/api/image/'+curJob,{method:'DELETE'})};
async function loadGallery(){try{const g=await api('/api/gallery');$('galleryEmpty').classList.toggle('hidden',g.length>0);
  $('gallery').replaceChildren(...g.map(im=>{const t=el('div',{className:'th'},el('img',{src:im.url,loading:'lazy',alt:im.prompt||''}));t.onclick=()=>lightbox(im);return t}))}catch{}}
onShow.image=()=>{loadGallery()};
function lightbox(im){const lb=$('lightbox');lb.classList.remove('hidden');
  const info=[im.model,im.width&&im.height&&`${im.width}×${im.height}`,im.steps&&`${im.steps} шагов`,im.guidance&&`CFG ${im.guidance}`,im.seed!=null&&`seed ${im.seed}`].filter(Boolean).join(' · ');
  const use=el('button',{className:'btn sm',textContent:'Использовать настройки'});use.onclick=()=>{$('imgPrompt').value=im.prompt||'';$('imgNeg').value=im.negative||'';$('imgSteps').value=im.steps||25;$('imgCfg').value=im.guidance||7;$('imgW').value=im.width||512;$('imgH').value=im.height||512;$('imgSeed').value=im.seed??'';styleIdx=0;markOne($('imgStyles'),0);lb.classList.add('hidden');go('image',{root:true})};
  const cp=el('button',{className:'btn sm',textContent:'Копировать промпт'});cp.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(im.prompt||'');cp.textContent='✓'};
  const dl=el('a',{className:'btn sm',href:im.url,download:im.name||'image.png',textContent:'Скачать',style:'text-decoration:none;justify-content:center'});
  const del=el('button',{className:'btn sm danger',textContent:'Удалить'});del.onclick=async()=>{if(confirm('Удалить картинку?')){await api('/api/gallery/'+im.name,{method:'DELETE'});lb.classList.add('hidden');loadGallery()}};
  const close=el('button',{className:'btn sm',textContent:'Закрыть'});close.onclick=()=>lb.classList.add('hidden');
  lb.replaceChildren(el('img',{src:im.url}),el('div',{className:'info'},el('div',{textContent:im.prompt||''}),el('div',{style:'opacity:.7;margin-top:6px',textContent:info})),el('div',{className:'rowx',style:'flex-wrap:wrap;justify-content:center'},use,cp,dl,del,close))}
$('lightbox').onclick=e=>{if(e.target.id==='lightbox')$('lightbox').classList.add('hidden')};

/* ---------- старт ---------- */
onShow.chat=()=>{renderChat()};
renderChatList();renderChat();onRefresh();

/* ---------- поиск по чатам ---------- */
$('chatFind').onclick=()=>{const lb=$('lightbox');lb.classList.remove('hidden');
  const inp=el('input',{placeholder:'Найти в сообщениях…',style:'max-width:480px'}),list=el('div',{style:'width:100%;max-width:480px;max-height:55vh;overflow:auto'});
  const close=el('button',{className:'btn sm',textContent:'Закрыть'});close.onclick=()=>lb.classList.add('hidden');
  const draw=()=>{const q=inp.value.trim().toLowerCase();list.replaceChildren();if(q.length<2)return;let n=0;
    for(const c of chats)for(let i=0;i<c.messages.length;i++){const m=c.messages[i],k=m.content.toLowerCase().indexOf(q);if(k<0)continue;if(++n>30)break;
      const from=Math.max(0,k-30),snip=(from?'…':'')+m.content.slice(from,k+q.length+60).replace(/\s+/g,' ');
      const b=el('button',{className:'btn sm',style:'width:100%;margin:5px 0;justify-content:flex-start;text-align:left;flex-direction:column;align-items:flex-start;gap:2px'},el('b',{textContent:c.title}),el('span',{style:'font-weight:400;font-size:12px;opacity:.8',textContent:snip}));
      b.onclick=()=>{cur=c.id;save();renderChatList();renderChat();lb.classList.add('hidden');go('chat',{root:true})};list.append(b)}
    if(!n)list.append(el('div',{style:'color:#ccc',textContent:'Ничего не найдено'}))};
  inp.oninput=draw;lb.replaceChildren(el('h3',{style:'color:#fff;font-size:20px',textContent:'поиск по чатам'}),inp,list,close);inp.focus()};

/* ---------- дуэль моделей ---------- */
function duelNames(){const a=models.find(m=>m.id===loaded('chat')),b=models.find(m=>m.id===loaded('code'));$('duelA').textContent=a?a.name:'не запущена';$('duelB').textContent=b?b.name:'не запущена';return[a,b]}
function drawBoard(){const v=store.get('kira-duels',{});const rows=Object.entries(v).sort((x,y)=>y[1]-x[1]);const bd=$('duelBoard');
  bd.replaceChildren(...(rows.length?rows.map(([id,w])=>{const m=models.find(x=>x.id===id);return row(famTile(KiraAnalyze.guessFamily(m?m.name:id)||(m?m.name:id),true),m?m.name:id,'побед: '+w,el('b',{textContent:'🏆 '+w}))}):[document.createTextNode('Голосуйте за лучший ответ — здесь появится рейтинг ваших моделей.')]))}
onShow.duel=()=>{duelNames();drawBoard()};
$('duelRun').onclick=async()=>{const q=$('duelQ').value.trim();if(!q)return;const ms=duelNames();if(!ms[0]||!ms[1])return toast('Запустите по модели на экранах «Чат» и «Код»');
  const out=$('duelOut');out.replaceChildren();$('duelRun').disabled=true;const slots=['chat','code'];
  await Promise.all(ms.map(async(m,i)=>{const body=el('div',{className:'bub',style:'border:0;box-shadow:none;padding:0'},typing()),foot=el('div',{className:'meta'}),card=el('div',{className:'duel-card'},el('div',{className:'hd'},famTile(KiraAnalyze.guessFamily(m.name)||m.name,true),el('span',{textContent:m.name})),body,foot);out.append(card);
    try{let tps=0,full='';full=await stream(slots[i],[{role:'user',content:q}],x=>renderRich(body,x),v=>tps=v);foot.textContent=tps?tps.toFixed(1)+' ток/с':'';
      const vote=el('button',{className:'btn sm out',style:'margin-top:8px',textContent:'👍 Этот лучше'});vote.onclick=()=>{const d=store.get('kira-duels',{});d[m.id]=(d[m.id]||0)+1;store.set('kira-duels',d);out.querySelectorAll('.duel-card button').forEach(b=>b.disabled=true);toast('Голос засчитан: '+m.name);drawBoard()};card.append(vote)}
    catch(e){body.replaceChildren(el('span',{style:'color:var(--bad)',textContent:e.message}))}}));
  $('duelRun').disabled=false};
