/* Read-only Hypit source-table view. No network/API or edits to canonical data. */
const DATA=JSON.parse(document.getElementById('source-data').textContent);
const $=id=>document.getElementById(id), shots=DATA.shots, notes=DATA.notes;
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${(t%60).toFixed(3).padStart(6,'0')}`;
const span=s=>s.end-s.start, issueIds=new Set(notes.map(n=>n.shot_id));
const currentGroups=[['故事与观众体验',['场次段落与EX','叙事任务与知情变化','时空与在场关系','角色策略与关系变化','导演作用与体验机制']],['动作、表演与连戏',['起终状态与连续性','行动接触与物理过程','表演与同步反应']],['摄影、空间与气氛',['景别机位与透视','构图景层与焦点','运镜与注意路径','空间轴线与视线','光色材质与气氛']],['对白、音乐与声音',['逐字台词与文字依据','声音表演','同期声与环境声','音乐与有意义静默','声桥与声画同步']],['切点与效果',['转场切点与节奏','画面文字与特效过程']],['证据与未知',['证据未知与复查']],['镜号与时钟',['镜头ID','入点','出点']],['贡献索引',['制作贡献索引']]];
const legacyGroups=[['故事与观众体验',[2,3,10,11,12,26,27,40,41,44,45,46]],['动作、表演与连戏',[8,9,23,24,25,28,29]],['摄影、空间与气氛',[13,14,15,16,17,18,19,20,21,22,38,39]],['对白、音乐与声音',[30,31,32,33,34,35]],['切点、节奏与效果',[7,36,37,42,43]],['证据与未知',[48,49]],['原始镜号与时钟',[1,4,5,6]],['制作贡献索引',[47]]];
const groups=DATA.columns.includes('运镜与注意路径')?currentGroups:legacyGroups.map(([name,ns])=>[name,ns.map(n=>DATA.columns[n-1])]);
let current=shots[0],objectUrl=null;
$('title').textContent=DATA.title;$('video').src=DATA.media_url;
const total=shots.at(-1).end-shots[0].start;
$('stats').innerHTML=[['源镜头',shots.length],['源范围',`${total.toFixed(3)} s`],['平均镜长',`${(shots.reduce((n,s)=>n+span(s),0)/shots.length).toFixed(2)} s`],['复查提示',`${notes.length} · 非错误判定`]].map(([a,b])=>`<div class="stat"><span>${esc(a)}</span><b>${esc(b)}</b></div>`).join('');
$('timeline').innerHTML=shots.map((s,i)=>`<button data-index="${i}" style="flex-grow:${span(s)}" title="${esc(s.id)} · ${fmt(s.start)}" aria-label="跳到 ${esc(s.id)}"></button>`).join('');
function image(s,p){const info=s.frames[p];return info?`<img src="${esc(info.href)}" alt="${esc(s.id)} ${p}" loading="lazy">`:'<div class="missing">缺少实际帧</div>';}
function renderCards(){
 const q=$('search').value.trim().toLowerCase(),filter=$('filter').value,sort=$('sort').value;
 const exact=q?shots.find(s=>s.id.toLowerCase()===q):null;
 let rows=shots.filter(s=>(exact?s===exact:(!q||Object.values(s.row).join(' ').toLowerCase().includes(q)))&&(filter!=='notes'||issueIds.has(s.id))&&(filter!=='unknown'||Object.values(s.row).some(v=>/UNKNOWN|未知|未验证/.test(v))));
 if(sort!=='timeline')rows=[...rows].sort((a,b)=>sort==='long'?span(b)-span(a):span(a)-span(b));
 $('cards').innerHTML=rows.map(s=>`<button class="card" data-index="${shots.indexOf(s)}" aria-current="${s===current}"><div class="card-pair">${image(s,'a')}${image(s,'b')}</div><div><b>${esc(s.id)}</b><span class="time">${fmt(s.start)} · ${span(s).toFixed(2)}s</span><p>${esc(s.row['叙事任务与知情变化']??s.row['叙事任务'])}</p><div class="badges">${esc((s.row['景别机位与透视']??s.row['景别与尺度变化']??'').slice(0,60))}${issueIds.has(s.id)?'<span class="badge-warning">待复查</span>':''}</div></div></button>`).join('');
 $('count').textContent=`显示 ${rows.length} / ${shots.length} 镜 · 点击回看与展开${DATA.columns.length}列原文`;$('empty').hidden=rows.length>0;
}
function show(index,seek=false){
 if(!shots[index])return;current=shots[index];
 $('selected-id').textContent=current.id;$('selected-time').textContent=`${fmt(current.start)} — ${fmt(current.end)}`;
 $('selected-pair').innerHTML=['a','b'].map(p=>`<figure>${image(current,p)}<figcaption>${p} · 请求 ${current.frames[p]?fmt(current.frames[p].requested):'—'} / 实帧 ${current.frames[p]?fmt(current.frames[p].actual):'—'}</figcaption></figure>`).join('');
 const motion=current.motion;$('motion').textContent=motion.value===null?'运动量未测或镜内样本不足；不据此判定固定镜头。':`采样变化中位数 ${motion.value.toFixed(3)} · ${motion.samples} 个内部样本。${motion.reason||'仅反映像素变化，不能区分主体与机位运动。'}`;
 $('details').innerHTML=groups.map(([name,fields],i)=>`<details${i===0?' open':''}><summary>${name}</summary><dl>${fields.filter(field=>current.row[field]).map(field=>{const n=DATA.columns.indexOf(field)+1,value=current.row[field];let common='';for(const match of value.matchAll(/@([A-Za-z0-9_.:-]+)/g)){const record=DATA.records[match[1]];if(record!==undefined)common+=`<div class="common">@${esc(match[1])}\n${esc(typeof record==='string'?record:JSON.stringify(record,null,2))}</div>`;}return `<dt>${n}. ${esc(field)}</dt><dd>${esc(value)}</dd>${common}`;}).join('')}</dl></details>`).join('');
 document.querySelectorAll('#timeline button').forEach((b,i)=>b.setAttribute('aria-current',String(i===index)));
 if(seek){const video=$('video');video.currentTime=current.start;$('player-status').textContent=`定位 ${current.id}`;if(video.getBoundingClientRect().bottom<0)video.scrollIntoView({block:'nearest'});}
 renderCards();
}
$('cards').addEventListener('click',e=>{const row=e.target.closest('[data-index]');if(row)show(Number(row.dataset.index),true);});
$('timeline').addEventListener('click',e=>{const row=e.target.closest('[data-index]');if(row)show(Number(row.dataset.index),true);});
for(const id of ['search','filter','sort'])$(id).addEventListener(id==='search'?'input':'change',renderCards);
$('previous').onclick=()=>show(Math.max(0,shots.indexOf(current)-1),true);$('next').onclick=()=>show(Math.min(shots.length-1,shots.indexOf(current)+1),true);
$('video').addEventListener('timeupdate',()=>{const t=$('video').currentTime,index=shots.findIndex(s=>s.start<=t&&t<s.end);if(index>=0&&shots[index]!==current)show(index);});
$('video').addEventListener('loadedmetadata',()=>{const duration=$('video').duration;$('player-status').textContent=DATA.media_duration&&Math.abs(duration-DATA.media_duration)>.2?'时长与来源记录不同，请核对文件':`${objectUrl?'所选文件':'原片'} ${duration.toFixed(3)}s${objectUrl?' · 请核对来源':''}`;});
$('video').addEventListener('error',()=>{$('player-status').textContent='请选择本地原片以播放';});
$('file').onchange=()=>{const file=$('file').files[0];if(!file)return;if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=URL.createObjectURL(file);$('video').src=objectUrl;$('player-status').textContent='所选文件请与来源记录核对';};
document.addEventListener('click',e=>{const image=e.target.closest('.pair img,.sheet-panel img');if(image)window.open(image.src,'_blank','noopener');});
$('sheets').innerHTML=DATA.sheets.map(s=>`<h3>第 ${s.page} 页 · ${s.phase} · ${s.shot_ids.map(esc).join(' / ')}</h3><img src="${esc(s.href)}" alt="第${s.page}页${s.phase}联系表" loading="lazy">`).join('');
show(0);
