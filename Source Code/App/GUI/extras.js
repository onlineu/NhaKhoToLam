// Name suggestions, route planner map and manager benchmark. Loaded after app.js, which provides api, note, chips, S, $, $$, esc and show.

// ---------- name suggestions (the backend walks a Trie) ----------
(()=>{
  const q=$('#q'),ul=$('#sug');let seq=0,timer=null,items=[],cur=-1;
  const close=()=>{ul.hidden=true;items=[];cur=-1;q.setAttribute('aria-expanded','false');q.removeAttribute('aria-activedescendant')};
  const paint=()=>{
    ul.innerHTML=items.map((s,i)=>`<li role="option" id="sug${i}" data-i="${i}" aria-selected="${i===cur}">${esc(s)}</li>`).join('');
    ul.hidden=!items.length;q.setAttribute('aria-expanded',String(!!items.length));
    if(cur>=0)q.setAttribute('aria-activedescendant','sug'+cur);else q.removeAttribute('aria-activedescendant');
  };
  const pick=s=>{q.value=s;close();$('#f-find button').click()};
  q.addEventListener('input',()=>{
    clearTimeout(timer);
    const v=q.value.trim();
    if($('input[name=mode]:checked').value!=='name'||!v||!S.token)return close();
    timer=setTimeout(async()=>{
      const my=++seq,j=await api('GET','/api/suggest?q='+encodeURIComponent(v));
      if(my!==seq)return;
      if(!j.ok)return close();
      items=j.data.suggestions;cur=-1;paint();
    },180);
  });
  q.addEventListener('keydown',e=>{
    if(ul.hidden)return;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();cur=(cur+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;paint()}
    else if(e.key==='Enter'&&cur>=0){e.preventDefault();pick(items[cur])}
    else if(e.key==='Escape')close();
  });
  ul.addEventListener('mousedown',e=>{const li=e.target.closest('li');if(li){e.preventDefault();pick(items[+li.dataset.i])}});
  q.addEventListener('blur',()=>setTimeout(close,120));
  $('#f-find').addEventListener('submit',close);
  $$('input[name=mode]').forEach(r=>r.addEventListener('change',close));
})();

// ---------- manager benchmark ----------
if($('#p-bench'))(()=>{
  const lg=(v,max)=>Math.max(2,Math.round(100*Math.log10(1+v)/Math.log10(1+max)));
  const us=v=>v>=1000?(v/1000).toFixed(2)+' ms':v+' µs';
  const meter=(v,max)=>`<span class="meter"><i style="width:${lg(v,max)}%"></i></span>`;
  $('#run-bench').onclick=async e=>{
    const b=e.currentTarget;b.disabled=true;$('#r-bench').innerHTML='';note($('#m-bench'),'Running on the real database. This can take a few seconds…');
    const j=await api('POST','/api/benchmark');b.disabled=false;
    if(!j.ok)return note($('#m-bench'),j.error.message,'bad');
    const D=j.data,maxS=Math.max(...D.sorts.map(s=>s.ms||0)),maxQ=Math.max(...D.searches.map(s=>s.total_ms));
    chips($('#m-bench'),[['items tested',D.n],['to read every ID from DynamoDB',D.read_ms+' ms'],['search targets',D.targets],['round trip',j.ms+' ms']].concat(D.demo?[['values are samples','Demo mode']]:[]));
    $('#r-bench').innerHTML=
      '<h3>Sorting the item IDs</h3><div class="scroll"><table><thead><tr><th>Algorithm</th><th>Time</th><th>Compared (log scale)</th><th>Complexity</th></tr></thead><tbody>'+
      D.sorts.map(s=>`<tr><td class="nm">${esc(s.name)}</td><td class="num">${s.ms==null?'skipped':s.ms+' ms'}</td><td>${s.ms==null?esc(s.note):meter(s.ms,maxS)}</td><td class="cx">${esc(s.complexity)}</td></tr>`).join('')+
      '</tbody></table></div><h3>Finding one item by ID</h3><div class="scroll"><table><thead><tr><th>Method</th><th>Prepare</th><th>Per lookup</th><th>Total for one lookup</th><th>Compared (log scale)</th><th>Complexity</th></tr></thead><tbody>'+
      D.searches.map(s=>`<tr><td class="nm">${esc(s.name)}</td><td class="num">${s.prep_ms} ms</td><td class="num">${us(s.per_lookup_us)}</td><td class="num">${s.total_ms} ms</td><td>${meter(s.total_ms,maxQ)}</td><td class="cx">${esc(s.complexity)}</td></tr>`).join('')+
      '</tbody></table></div><p class="hint">Sorting is repeated on every request in the backend, so preparation counts toward one lookup. Results include network time only for the DynamoDB lookup.</p>';
  };
})();

// ---------- route planner (OpenStreetMap through Leaflet, road distances from OSRM when reachable) ----------
if($('#p-route'))(()=>{
  const NAMES={brute_force:'Brute force',held_karp:'Held-Karp',nearest_neighbour:'Nearest neighbour'};
  let map=null,pts=[],marks=[],line=null;
  const pin=(txt,w)=>L.divIcon({className:'',html:`<span class="pin${w?' w':''}">${txt}</span>`,iconSize:[30,30],iconAnchor:[15,15]});
  const clearLine=()=>{if(line){line.remove();line=null}};
  function redraw(order){
    marks.forEach(m=>m.remove());marks=[];
    const visit=[];if(order)order.forEach((p,k)=>visit[p]=k);
    pts.forEach((p,i)=>marks.push(L.marker([p.lat,p.lng],{icon:pin(i===0?'W':(order?visit[i]:i),i===0),keyboard:false}).addTo(map)));
  }
  function init(){
    if(map)return setTimeout(()=>map.invalidateSize(),50);
    map=L.map('map').setView([21.0285,105.8542],12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
    map.on('click',e=>{
      if(pts.length>=13)return note($('#m-route'),'At most 12 client stops.','bad');
      pts.push({lat:+e.latlng.lat.toFixed(6),lng:+e.latlng.lng.toFixed(6)});clearLine();redraw();
      note($('#m-route'),pts.length===1?'Warehouse placed. Click the map to add client stops.':`${pts.length-1} client ${pts.length===2?'stop':'stops'} placed.`);
    });
    setTimeout(()=>map.invalidateSize(),50);
  }
  const _show=show;show=function(t){_show(t);if(t==='route')init()};

  async function roadMatrix(P){
    try{
      const c=new AbortController(),t=setTimeout(()=>c.abort(),8000);
      const r=await fetch('https://router.project-osrm.org/table/v1/driving/'+P.map(p=>p.lng+','+p.lat).join(';')+'?annotations=distance',{signal:c.signal});
      clearTimeout(t);const d=await r.json();
      if(d.code==='Ok'&&d.distances.every(row=>row.every(x=>x!==null)))return d.distances;
    }catch(e){}
    return null;
  }
  async function drawLine(order,trip,src){
    clearLine();
    const P=order.concat(trip?[0]:[]).map(i=>pts[i]);let ll=P.map(p=>[p.lat,p.lng]),dashed=true;
    if(src==='road')try{
      const r=await fetch('https://router.project-osrm.org/route/v1/driving/'+P.map(p=>p.lng+','+p.lat).join(';')+'?overview=full&geometries=geojson');
      const d=await r.json();if(d.code==='Ok'){ll=d.routes[0].geometry.coordinates.map(c=>[c[1],c[0]]);dashed=false}
    }catch(e){}
    line=L.polyline(ll,{color:'#2457d6',weight:5,opacity:.85,dashArray:dashed?'8 8':null}).addTo(map);
    map.fitBounds(line.getBounds(),{padding:[40,40]});
  }
  $('#run-route').onclick=async e=>{
    if(pts.length<2)return note($('#m-route'),'Click the map to place the warehouse, then at least one client stop.','bad');
    const b=e.currentTarget,algo=$('#algo').value,trip=$('#trip').checked;
    b.disabled=true;note($('#m-route'),'Getting road distances and finding the route…');
    const matrix=await roadMatrix(pts);
    const j=await api('POST','/api/route',{algorithm:algo,points:pts,round_trip:trip,matrix});
    b.disabled=false;
    if(!j.ok)return note($('#m-route'),j.error.message,'bad');
    const D=j.data;redraw(D.order);await drawLine(D.order,trip,D.distance_source);
    chips($('#m-route'),[['algorithm',NAMES[D.algorithm]],['shortest distance',(D.distance_m/1000).toFixed(2)+' km'],
      [D.algorithm==='brute_force'?'routes checked':'steps',D.checked.toLocaleString()],['solved in',D.elapsed_ms+' ms'],
      ['distances',D.distance_source==='road'?'by road':'straight line'],['order',D.order.map(i=>i===0?'W':i).concat(trip?['W']:[]).join(' → ')]]);
  };
  $('#undo-stop').onclick=()=>{pts.pop();clearLine();redraw();note($('#m-route'))};
  $('#clear-stops').onclick=()=>{pts=[];clearLine();redraw();note($('#m-route'))};
})();