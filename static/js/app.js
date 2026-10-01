/* ReliefNet frontend - talks to the Flask REST API */
const $=id=>document.getElementById(id);
let inc=[],sh=[],vols=[],fs='All',fr='All',selId=null,rt;
const col={High:'var(--red)',Medium:'var(--amb)',Low:'var(--grn)'};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(u,m,b){
  try{const r=await fetch(u,{method:m||'GET',headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
    const j=await r.json();if(!r.ok)throw new Error(j.error||'Request failed');return j}
  catch(e){toast(e instanceof TypeError?'Server not reachable. Run: python app.py':e.message);throw e}}
function toast(t){const e=$('toast');e.textContent=t;e.classList.add('on');setTimeout(()=>e.classList.remove('on'),2400)}

async function stats(){const s=await api('/api/stats');
  const d=[[s.active,'Active incidents'],[s.people,'People affected'],[s.shelters,'Open shelters'],[s.volunteers,'Volunteers deployed']];
  $('stats').innerHTML=d.map(x=>`<div class="card stat"><b data-n="${x[0]}">0</b><span>${x[1]}</span></div>`).join('');
  document.querySelectorAll('[data-n]').forEach(e=>{let n=+e.dataset.n,c=0,s=Math.max(1,Math.ceil(n/30));const t=setInterval(()=>{c=Math.min(n,c+s);e.textContent=c;if(c>=n)clearInterval(t)},25)})}

async function dash(){inc=await api('/api/incidents');
  $('fsev').innerHTML=['All','High','Medium','Low'].map(s=>`<button class="chip ${s==fs?'on':''}" onclick="fs='${s}';dash()">${s}</button>`).join('');
  const L=inc.filter(i=>fs=='All'||i.sev==fs);
  $('dots').innerHTML=L.map(i=>`<circle class="dot" cx="${i.x}" cy="${i.y}" r="9" fill="${col[i.sev]}" stroke="#fff" stroke-width="2" onclick="pick(${i.id})"><title>${esc(i.type)} – ${esc(i.loc)}</title></circle>`).join('');
  $('tb').innerHTML=L.map(i=>`<tr id="r${i.id}" onclick="pick(${i.id})"><td>#${i.id}</td><td>${esc(i.type)}</td><td>${esc(i.loc)}</td><td>${i.ppl}</td><td><span class="tag ${i.sev}">${i.sev}</span></td><td>${esc(i.st)}</td></tr>`).join('')||'<tr><td colspan=6>No incidents at this priority.</td></tr>';
  if(selId)$('r'+selId)?.classList.add('sel')}
function pick(id){selId=id;const i=inc.find(x=>x.id==id);if(!i)return;
  document.querySelectorAll('tr.sel').forEach(r=>r.classList.remove('sel'));$('r'+id)?.classList.add('sel');
  $('detail').innerHTML=`<h3>${esc(i.type)} – ${esc(i.loc)}</h3><span class="tag ${i.sev}">${i.sev} priority</span><p>${esc(i.d)}</p><p><b>${i.ppl}</b> people · Status: <b>${esc(i.st)}</b></p><div class="row"><button onclick="setSt(${i.id},'Team sent')">Dispatch team</button><button class="alt" onclick="setSt(${i.id},'Resolved')">Mark resolved</button><a class="btn alt" href="#volunteer">Add volunteer</a></div>`}
async function setSt(id,s){await api('/api/incidents/'+id,'PATCH',{status:s});await dash();pick(id);toast('Incident #'+id+' → '+s)}

$('rf').onsubmit=async e=>{e.preventDefault();
  const r=await api('/api/incidents','POST',{type:$('rt').value,loc:$('rl').value,ppl:$('rp').value,d:$('rd').value});
  $('triage').innerHTML=`Last report: <span class="tag ${r.sev}">${r.sev}</span>`;e.target.reset();
  toast('Report #'+r.id+' saved · AI priority: '+r.sev);location.hash='dashboard';setTimeout(()=>pick(r.id),300)};

const S=[['rain','Rainfall (mm/24h)',0,300,120],['river','River level (% of danger mark)',0,150,70],['seis','Seismic activity (magnitude)',0,9,3],['wind','Wind speed (km/h)',0,200,60]];
$('sl').innerHTML=S.map(s=>`<label>${s[1]}: <span id="v${s[0]}">${s[4]}</span></label><input type="range" id="${s[0]}" min="${s[2]}" max="${s[3]}" step="${s[3]>20?1:.1}" value="${s[4]}">`).join('');
function risk(){const g=k=>+$(k).value;S.forEach(s=>$('v'+s[0]).textContent=g(s[0]));clearTimeout(rt);
  rt=setTimeout(async()=>{const r=await api('/api/predict','POST',{hazard:$('pt').value,rain:g('rain'),river:g('river'),seis:g('seis'),wind:g('wind')});
    $('score').textContent=r.score;$('lvl').className='tag '+r.level;$('lvl').textContent=r.level+' risk';
    $('gb').style.width=r.score+'%';$('gb').style.background=col[r.level];$('acts').innerHTML=r.actions.map(a=>'<li>'+a+'</li>').join('')},150)}
$('predict').addEventListener('input',risk);

async function res(){$('fr').innerHTML=['All','Food','Medical'].map(s=>`<button class="chip ${s==fr?'on':''}" onclick="fr='${s}';res()">${s}</button>`).join('');
  sh=await api('/api/shelters?q='+encodeURIComponent($('q').value)+'&f='+fr);
  $('sh').innerHTML=sh.map(s=>{const p=Math.round(s.occ/s.cap*100);return`<div class="card"><h3>${esc(s.n)}</h3><span style="color:var(--mut)">${esc(s.a)}</span><div class="bar"><i style="width:${p}%;background:${p>85?'var(--red)':'var(--teal)'}"></i></div>${s.occ}/${s.cap} beds · ${p>85?'Almost full':'Space available'}${s.m?' · Medical unit':''}<div class="row"><button onclick="reqS(${s.id},'${esc(s.n)}')">Request supplies</button></div></div>`}).join('')||'<p>No shelters match your search.</p>'}
async function reqS(id,n){await api('/api/shelters/'+id+'/request','POST');toast('Supply request sent to '+n)}
$('q').oninput=res;

async function fill(){inc=await api('/api/incidents');$('vi').innerHTML=inc.filter(i=>i.st!='Resolved').map(i=>`<option value="${i.id}">#${i.id} ${esc(i.type)} – ${esc(i.loc)}</option>`).join('')}
async function vl(){vols=await api('/api/volunteers');$('vc').textContent=vols.length;
  $('vl').innerHTML=vols.map(v=>`<div class="m"><b>${esc(v.n)}</b> · ${esc(v.s)}<br>Assigned to #${v.i}</div>`).join('')}
$('vf').onsubmit=async e=>{e.preventDefault();await api('/api/volunteers','POST',{n:$('vn').value,s:$('vs').value,i:$('vi').value});
  e.target.reset();await vl();toast('Thanks! You are assigned.')}

$('ci').onkeydown=async e=>{if(e.key!='Enter'||!e.target.value.trim())return;const t=e.target.value;e.target.value='';
  $('log').innerHTML+=`<div class="m u">${esc(t)}</div>`;const r=await api('/api/chat','POST',{message:t});
  $('log').innerHTML+=`<div class="m">${esc(r.reply)}</div>`;$('log').scrollTop=1e9};
$('fab').onclick=()=>$('chat').classList.toggle('on');
$('theme').onclick=()=>{const d=document.documentElement,dark=getComputedStyle(d).getPropertyValue('--bg').trim()=='#0e1620';d.dataset.theme=dark?'light':'dark'};

function route(){const h=(location.hash||'#home').slice(1),p=$(h)&&$(h).classList.contains('pg')?h:'home';
  document.querySelectorAll('.pg').forEach(s=>s.classList.toggle('on',s.id==p));
  document.querySelectorAll('#nav a').forEach(a=>a.classList.toggle('on',a.hash=='#'+p));
  if(p=='home')stats();if(p=='dashboard')dash();if(p=='volunteer'){fill();vl()}if(p=='resources')res();
  window.scrollTo(0,0);document.title='ReliefNet – '+p}
addEventListener('hashchange',route);
setInterval(()=>{if(location.hash=='#dashboard')dash()},10000); // live refresh
risk();route();
