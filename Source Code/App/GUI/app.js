const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const demo=new URLSearchParams(location.search).has('demo');
const ROLE=document.body.dataset.role,PAGE=10,S={token:null,user:'',groups:[],page:1,tab:'find'};

// A browser cannot read a hardware ID, so each browser gets a random one that an admin can whitelist.
const deviceId=(()=>{const mk=()=>'DEV-'+Math.random().toString(36).slice(2,10).toUpperCase();
  try{let d=localStorage.getItem('vd_device');if(!d){d=mk();localStorage.setItem('vd_device',d)}return d}catch(e){return mk()}})();
$$('.dev,#dev').forEach(e=>e.textContent=deviceId);
const copy=async t=>{try{await navigator.clipboard.writeText(t)}catch(e){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove()}};
$$('[data-copy]').forEach(b=>b.onclick=async()=>{await copy(deviceId);b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1500)});

function note(el,text,kind){el.textContent=text||'';el.className='note '+(kind||'')}
function chips(el,list){el.className='chips';el.innerHTML=list.map(([k,v])=>`<span class="chip"><b>${esc(v)}</b> ${esc(k)}</span>`).join('')}

async function api(method,path,body){
  const t=performance.now(),h={'Content-Type':'application/json','X-Device-Id':deviceId};
  if(S.token)h.Authorization='Bearer '+S.token;
  let r,j;
  try{r=await (demo?mock:fetch)(path,{method,headers:h,body:body?JSON.stringify(body):undefined})}
  catch(e){return{ok:false,status:0,error:{message:'Cannot reach the server. Check your connection and try again.'}}}
  try{j=await r.json()}catch(e){j={ok:false,error:{message:'The server sent an unexpected response.'}}}
  j.status=j.status||r.status;j.ms=Math.round(performance.now()-t);
  if(j.status===423)$('#lock').hidden=false;
  else if(j.status===401&&S.token)signOut('Your session expired. Sign in again.');
  return j;
}

function table(items){
  const admin=ROLE==='admin';
  return '<div class="scroll"><table><thead><tr><th>ID</th><th>Name</th><th>Description</th><th>Shelf or aisle</th><th>Qty</th><th>Added</th>'+(admin?'<th class="act">Actions</th>':'')+'</tr></thead><tbody>'+
  items.map(i=>`<tr><td><span class="tag">${esc(i.item_id)}</span></td><td>${esc(i.name)}</td><td>${esc(i.description)}</td><td class="shelf">${esc(i.location)}</td><td class="qty${i.quantity<=5?' low':''}">${i.quantity==null?'-':esc(i.quantity)}</td><td>${esc((i.created_at||'').slice(0,10))}</td>${admin?`<td class="act"><button class="ghost danger" type="button" data-del="${esc(i.item_id)}">Delete</button></td>`:''}</tr>`).join('')+
  '</tbody></table></div>';
}

function show(tab){
  S.tab=tab;
  $$('main .panel').forEach(p=>p.hidden=p.id!=='p-'+tab);
  $$('nav button').forEach(b=>b.toggleAttribute('aria-current',b.dataset.tab===tab)||b.removeAttribute('aria-current'));
  $$('nav button').forEach(b=>{if(b.dataset.tab===tab)b.setAttribute('aria-current','page')});
  if(tab==='list')loadList(1);
  const f={find:'#q',store:'#s-name'}[tab];if(f)$(f).focus();
}
$$('nav button').forEach(b=>b.onclick=()=>show(b.dataset.tab));

function enter(){
  $('#login').hidden=true;if($('.shell'))$('.shell').hidden=false;$('#top').hidden=false;$('#app').hidden=false;
  $('#who').textContent=S.user+($('#av')?'':(ROLE==='admin'?' (manager)':''));if($('#av'))$('#av').textContent=S.user.slice(0,1).toUpperCase();
  show('find');
}
function signOut(msg){
  Object.assign(S,{token:null,user:'',groups:[]});
  if($('.shell'))$('.shell').hidden=true;$('#top').hidden=true;$('#app').hidden=true;$('#login').hidden=false;
  $('#r-find').innerHTML=$('#r-list').innerHTML='';note($('#m-find'));note($('#m-store'));
  $('#f-newpw').hidden=true;$('#f-login').hidden=false;note($('#m-login'),msg||'');$('#u').focus();
}
$('#out').onclick=()=>signOut('You are signed out.');

function finish(j){
  if(ROLE==='admin'&&!(j.data.groups||[]).includes('admin'))return note($('#m-login'),'This account does not have manager access. Use the staff site instead.','bad');
  Object.assign(S,{token:j.data.token,user:j.data.username,groups:j.data.groups||[]});
  $('#f-newpw').hidden=true;$('#f-login').hidden=false;note($('#m-login'));enter();
}
$('#f-login').onsubmit=async e=>{
  e.preventDefault();const b=e.submitter;b.disabled=true;note($('#m-login'),'Signing in…');
  const j=await api('POST','/api/login',{username:$('#u').value.trim(),password:$('#pw').value});
  b.disabled=false;$('#pw').value='';
  if(!j.ok)return note($('#m-login'),j.status===423?'':j.error.message,'bad');
  if(j.data.challenge){S.ch=j.data;$('#f-login').hidden=true;$('#f-newpw').hidden=false;note($('#m-login'),'Choose a new password to finish signing in.');$('#np1').focus();return}
  finish(j);
};
$('#f-newpw').onsubmit=async e=>{
  e.preventDefault();const b=e.submitter,p=$('#np1').value;
  if(p!==$('#np2').value)return note($('#m-login'),'The two passwords do not match.','bad');
  b.disabled=true;note($('#m-login'),'Saving…');
  const j=await api('POST','/api/new-password',{username:S.ch.username,session:S.ch.session,password:p});
  b.disabled=false;
  if(!j.ok)return note($('#m-login'),j.error.message,'bad');
  $('#np1').value=$('#np2').value='';finish(j);
};
$('#relock').onclick=()=>location.reload();

$$('input[name=mode]').forEach(r=>r.onchange=()=>{
  const id=r.value==='id';
  if(!r.checked)return;
  $('#method').hidden=!id;if($('#name-hint'))$('#name-hint').hidden=id;
  $('#q-label').textContent=id?'Item ID':'Item name';$('#q').placeholder=id?'9030':'Life jacket';$('#q').focus();
});
$('#f-find').onsubmit=async e=>{
  e.preventDefault();
  const id=$('input[name=mode]:checked').value==='id',q=$('#q').value.trim(),b=e.submitter;
  $('#r-find').innerHTML='';
  if(!q)return note($('#m-find'),id?'Enter an item ID.':'Enter an item name.','bad');
  b.disabled=true;note($('#m-find'),'Searching…');
  const bin=id&&$('input[name=method]:checked').value==='binary';
  const j=await api('GET',id?'/api/items/'+encodeURIComponent(q)+(bin?'?method=binary':''):'/api/search?name='+encodeURIComponent(q));
  b.disabled=false;
  if(!j.ok)return note($('#m-find'),j.error.message,'bad');
  const items=j.data.items||[j.data.item];
  const D=j.data,n=D.count||items.length;
  note($('#m-find'),D.method==='binary_search'
    ?`Found in ${j.ms} ms with binary search: ${D.steps} ${D.steps===1?'step':'steps'} over ${D.total} sorted IDs, number ${D.position} in the sorted list. Quick Sort took ${D.sort_ms} ms and the search ${D.search_ms} ms.`
    :`Found ${n} ${n===1?'item':'items'} in ${j.ms} ms.`+(D.truncated?` Showing the first ${items.length}, type more letters to narrow it down.`:'')+(D.sort_ms!=null?` Sorted by ID in ${D.sort_ms} ms.`:''),'ok');
  $('#r-find').innerHTML=table(items);
};

$$('input[name=idmode]').forEach(r=>r.onchange=syncId);
function syncId(){const m=$('input[name=idmode]:checked').value==='manual';$('#manual').hidden=!m;if(m)$('#s-id').focus()}
$('#f-store').onsubmit=async e=>{
  e.preventDefault();const b=e.submitter,manual=$('input[name=idmode]:checked').value==='manual';
  const body={name:$('#s-name').value,description:$('#s-desc').value,location:$('#s-loc').value,quantity:$('#s-qty').value};
  if(manual)body.item_id=$('#s-id').value;
  b.disabled=true;note($('#m-store'),'Saving…');
  const j=await api('POST','/api/items',body);b.disabled=false;
  if(!j.ok)return note($('#m-store'),j.error.message,'bad');
  const it=j.data.item;
  note($('#m-store'),`Saved ${it.quantity} of ${it.name} with ID ${it.item_id}${j.data.id_source==='auto'?' (assigned automatically)':''} in ${j.ms} ms.`,'ok');
  e.target.reset();syncId();$('#s-name').focus();
};

async function loadList(p){
  S.page=p;note($('#m-list'),'Loading…');
  const j=await api('GET',`/api/items?page=${p}&page_size=${PAGE}`);
  if(!j.ok)return note($('#m-list'),j.error.message,'bad');
  const d=j.data,pages=Math.max(1,Math.ceil(d.total/d.page_size));
  if(!d.items.length&&p>1)return loadList(p-1);
  note($('#m-list'),d.total?`${d.total} items, sorted by ID in ${d.sort_ms} ms. Loaded in ${j.ms} ms.`:'No items yet. Use Store to add the first one.');
  $('#r-list').innerHTML=d.items.length?table(d.items):'';
  $('#pg').textContent=`Page ${d.page} of ${pages}`;$('#prev').disabled=p<=1;$('#next').disabled=p>=pages;
}
$('#prev').onclick=()=>loadList(S.page-1);$('#next').onclick=()=>loadList(S.page+1);

document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-del]');if(!b||ROLE!=='admin')return;
  if(!confirm('Delete item '+b.dataset.del+'? This cannot be undone.'))return;
  b.disabled=true;
  const j=await api('DELETE','/api/items/'+encodeURIComponent(b.dataset.del));
  if(!j.ok){b.disabled=false;return note($(S.tab==='list'?'#m-list':'#m-find'),j.error.message,'bad')}
  if(S.tab==='list')loadList(S.page);
  else{$('#r-find').innerHTML='';note($('#m-find'),`Deleted item ${j.data.deleted}.`,'ok')}
});

// ---------- demo mode (?demo): in-memory stand-in for the real API, for screenshots and design review ----------
const DB=[67,9030,9293,150,4410].map((n,i)=>({item_id:n,name:['Plush toy','Pallet jack','Safety vest','Plush toy','Life Jacket'][i],description:['Soft toy, boxed','Manual, 2 tonne','High visibility, size L','Seasonal stock','Adult, orange'][i],location:['Aisle 2, shelf B','Aisle 7, bay 3','Aisle 1, shelf A','Aisle 2, shelf C','Aisle 5, shelf D'][i],quantity:[40,6,120,3,15][i],created_by:'jake',created_at:'2026-11-0'+(i+2)+'T09:00:00+00:00'}));
let nextId=1;
const validId=x=>/^[0-9]+$/.test(x)||/^[0-9]{1,3}(,[0-9]{3})+$/.test(x);
function mock(path,o){
  const u=new URL(path,location.href),m=o.method,b=o.body?JSON.parse(o.body):{},p=u.pathname;
  const R=(s,d)=>Promise.resolve({status:s,json:async()=>s<300?{ok:true,status:s,data:d}:{ok:false,status:s,error:{message:d}}});
  const bad='The ID is invalid. Use digits only, for example 9030 or 9,030.',miss='The item does not exist.';
  const pid=x=>validId(String(x))?+String(x).replace(/,/g,''):null;
  const sorted=a=>[...a].sort((x,y)=>x.item_id-y.item_id);
  if(p==='/api/suggest'){const tk=u.searchParams.get('q').trim().toLowerCase().split(/\s+/);return R(200,{suggestions:[...new Set(DB.map(i=>i.name))].filter(n=>{const w=n.toLowerCase().split(/[\s-]+/);return tk.every(t=>w.some(x=>x.startsWith(t)))}).sort((a,c)=>a.toLowerCase()<c.toLowerCase()?-1:1).slice(0,8)})}
  if(p==='/api/benchmark'){const s=(name,ms,complexity)=>({name,ms,complexity,note:''}),q=(name,prep,us,complexity)=>({name,prep_ms:prep,per_lookup_us:us,total_ms:+(prep+us/1000).toFixed(3),complexity,note:''});
    return R(200,{demo:true,n:DB.length,read_ms:40,targets:DB.length,sorts:[s('Quick Sort (ours)',19.2,'O(n log n) average, O(n²) worst'),s('Merge Sort',24.1,'O(n log n) always'),s('Heap Sort',46.5,'O(n log n) always'),s('Insertion Sort',1918,'O(n²)'),s('Python sorted (Timsort)',0.8,'O(n log n), built in')],
      searches:[q('Binary search (ours)',19.2,1.4,'O(log n) after sorting'),q('Interpolation search',19.2,2.1,'O(log log n) if IDs are evenly spread'),q('Linear search',0,160,'O(n)'),q('Hash set (Python set)',0.4,0.06,'O(1) average after building'),q('DynamoDB direct lookup',0,9000,'O(1) key lookup, one network call')]})}
  if(p==='/api/route'){const P=b.points,n=P.length,rad=x=>x*Math.PI/180,hv=(a,c)=>{const h=Math.sin(rad(c.lat-a.lat)/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(c.lat))*Math.sin(rad(c.lng-a.lng)/2)**2;return 12742017.6*Math.asin(Math.sqrt(h))};
    const D=b.matrix||P.map(a=>P.map(c=>hv(a,c))),cost=r=>r.slice(1).reduce((t,x,i)=>t+D[r[i]][x],0)+(b.round_trip?D[r[r.length-1]][0]:0);
    if(b.algorithm==='brute_force'&&n>10)return R(400,'Brute force supports at most 9 client stops. Pick another algorithm or remove stops.');
    let best=null,chk=0;
    if(b.algorithm==='nearest_neighbour'||n>9){const r=[0],left=new Set(P.map((_,i)=>i).slice(1));while(left.size){const l=r[r.length-1],nx=[...left].sort((x,y)=>D[l][x]-D[l][y])[0];r.push(nx);left.delete(nx)}best=r;chk=n*n}
    else{const rec=(r,left)=>{if(!left.length){chk++;if(!best||cost(r)<cost(best))best=r;return}left.forEach((x,i)=>rec([...r,x],left.filter((_,j)=>j!==i)))};rec([0],P.map((_,i)=>i).slice(1))}
    return R(200,{algorithm:b.algorithm,order:best,distance_m:Math.round(cost(best)*10)/10,checked:chk,elapsed_ms:1.5,round_trip:b.round_trip,distance_source:b.matrix?'road':'straight-line'})}
  if(p==='/api/new-password')return R(200,{token:'demo',username:b.username,groups:['staff']});
  if(p==='/api/login'&&b.username==='newuser'&&b.password==='demo')return R(200,{challenge:'NEW_PASSWORD_REQUIRED',session:'s',username:b.username});
  if(p==='/api/login')return b.password==='lockdown'?R(423,'Access restricted.'):b.password!=='demo'?R(401,'Incorrect username or password.'):R(200,{token:'demo',username:b.username,groups:[/^admin/i.test(b.username)?'admin':'staff']});
  if(m==='GET'&&p==='/api/search'){const tk=u.searchParams.get('name').trim().toLowerCase().split(/\s+/);const r=sorted(DB.filter(i=>{const n=i.name.toLowerCase();return tk.every(t=>n.startsWith(t)||n.includes(' '+t)||n.includes('-'+t))}));return r.length?R(200,{count:r.length,items:r,sort_ms:0.1}):R(404,miss)}
  if(m==='GET'&&p==='/api/items'){const pg=+u.searchParams.get('page')||1,sz=+u.searchParams.get('page_size')||10;return R(200,{total:DB.length,page:pg,page_size:sz,items:sorted(DB).slice((pg-1)*sz,pg*sz),sort_ms:0.4})}
  if(m==='POST'&&p==='/api/items'){let n=null;if(b.item_id){n=pid(b.item_id);if(!n)return R(400,bad);if(DB.some(x=>x.item_id===n))return R(409,'That ID already exists.')}
    else{while(DB.some(x=>x.item_id===nextId))nextId++;n=nextId++}
    const qs=String(b.quantity??'').trim(),qn=qs===''?1:/^[0-9]+$/.test(qs)?+qs:-1;if(qn<0||qn>1000000)return R(400,'Quantity must be a whole number from 0 to 1,000,000.');
    const it={item_id:n,quantity:qn,name:b.name.trim(),description:b.description.trim(),location:b.location.trim(),created_by:S.user,created_at:new Date().toISOString()};DB.push(it);return R(201,{item:it,id_source:b.item_id?'manual':'auto'})}
  const mt=p.match(/^\/api\/items\/(.*)$/);
  if(mt){const n=pid(decodeURIComponent(mt[1]));if(!n)return R(400,bad);const i=DB.findIndex(x=>x.item_id===n);if(i<0)return R(404,miss);
    if(m==='DELETE'){DB.splice(i,1);return R(200,{deleted:n})}if(u.searchParams.get('method')==='binary'){const ids=DB.map(x=>x.item_id).sort((a,b)=>a-b);let lo=0,hi=ids.length-1,st=0,pos=-1;while(lo<=hi){const md=(lo+hi)>>1;st++;if(ids[md]===n){pos=md;break}ids[md]<n?lo=md+1:hi=md-1}return R(200,{item:DB[i],method:'binary_search',total:ids.length,position:pos+1,steps:st,sort_ms:0.2,search_ms:0.01})}
    return R(200,{item:DB[i]})}
  return R(400,'Unknown request.');
}
if(demo)$('#demo-hint').hidden=false;
$$('a[data-link]').forEach(a=>a.href+=location.search);