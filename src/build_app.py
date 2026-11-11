"""Builds the standalone installable app from roadbound.html (the shared page source).

Usage: python3 build_app.py <path to roadbound.html> <output folder>
Writes index.html, manifest.webmanifest and sw.js. Quests live in <output>/quests/.
"""
import sys

src_path, out = sys.argv[1], sys.argv[2].rstrip("/")
src = open(src_path, encoding="utf-8").read()


def swap(text, old, new):
    assert text.count(old) == 1, "expected exactly one match for: " + old[:60]
    return text.replace(old, new)


head_part, body_part = src.split('<div class="wrap">', 1)
body_part = '<div class="wrap">' + body_part
head_part = swap(head_part, '<meta name="claude:viewport-fit-sides" content="cover">\n', "")

STORE = r"""<script src="config.js"></script>
<script>
/* Local journal: every document is kept in this phone's IndexedDB. Quests are read from the quests/ folder beside the app.
   When a shared-journal code is set, party, runs and photos are also mirrored to the database named in config.js. */
window.RQ=(function(){
  var docs={},subs=[],idb=null;
  var cfg=window.RQ_CONFIG||{},party="",outbox=[],flushing=false,cursor="",lastOk=0,offline=false,rejected=0,questsAt=0,SKIP={},statusSubs=[];
  try{party=window.localStorage.getItem("rq.party")||"";cursor=window.localStorage.getItem("rq.cursor")||""}catch(e){}
  function canSync(){return !!(cfg.url&&cfg.key&&party)}
  function synced(path){return /^(party|runs|photos)\//.test(path)}
  function note(){statusSubs.forEach(function(f){try{f()}catch(e){}})}
  function saveOutbox(){if(!idb)return;try{idb.transaction("docs","readwrite").objectStore("docs").put(outbox,"_outbox")}catch(e){}}
  function queue(op){if(!canSync()||!synced(op.path))return;outbox.push(op);saveOutbox();flush()}
  function rest(method,query,body,prefer){
    var h={apikey:cfg.key,Authorization:"Bearer "+cfg.key,"x-party":party,"Content-Type":"application/json"};if(prefer)h.Prefer=prefer;
    return fetch(cfg.url.replace(/\/+$/,"")+"/rest/v1/docs"+query,{method:method,headers:h,body:body?JSON.stringify(body):undefined,cache:"no-store"})
      .then(function(r){if(!r.ok)throw{status:r.status};return method==="GET"?r.json():null})}
  function rpc(name,args){
    return fetch(cfg.url.replace(/\/+$/,"")+"/rest/v1/rpc/"+name,{method:"POST",headers:{apikey:cfg.key,Authorization:"Bearer "+cfg.key,"x-party":party,"Content-Type":"application/json"},body:JSON.stringify(args),cache:"no-store"})
      .then(function(r){if(!r.ok)throw{status:r.status}})}
  function upsert(path,body){return rest("POST","?on_conflict=party,path",[{party:party,path:path,body:body}],"resolution=merge-duplicates,return=minimal")}
  function ok(){lastOk=Date.now();if(offline){offline=false}note()}
  function flush(){
    if(flushing||!outbox.length||!canSync())return Promise.resolve();
    flushing=true;var op=outbox[0],job;
    if(op.op==="update")job=rpc("merge_doc",{p_party:party,p_path:op.path,p_patch:op.data});
    else job=upsert(op.path,op.op==="delete"?null:op.data);
    return job.then(function(){outbox.shift();saveOutbox();flushing=false;rejected=0;ok();return outbox.length?flush():pull()},
      function(e){flushing=false;var c=e&&e.status;if(c>=400&&c<500&&c!==408&&c!==429)rejected=c;else offline=true;note()});
  }
  function same(a,b){
    if(a===b)return true;if(!a||!b||typeof a!=="object"||typeof b!=="object")return false;
    var ka=Object.keys(a),kb=Object.keys(b);if(ka.length!==kb.length)return false;
    for(var i=0;i<ka.length;i++){if(!same(a[ka[i]],b[ka[i]]))return false}return true}
  /* wide: also look a minute back, to catch a change that landed out of order */
  function pull(wide){
    if(!canSync()||outbox.length||flushing)return Promise.resolve(SKIP);
    var since=cursor,asked=party;if(wide&&cursor){var t=Date.parse(cursor);if(!isNaN(t))since=new Date(t-60000).toISOString()}
    var q="?party=eq."+encodeURIComponent(party)+"&select=path,body,updated_at&order=updated_at.asc"+(since?"&updated_at=gt."+encodeURIComponent(since):"");
    return rest("GET",q).then(function(rows){
      if(asked!==party)return SKIP;
      if(outbox.length||flushing)return SKIP; /* something changed here meanwhile: send that first, then look again */
      var changed=false,seen=[];
      rows.forEach(function(r){seen.push(r.path);
        if(synced(r.path)){
          if(r.body===null){if(docs[r.path]){delete docs[r.path];persist(r.path);changed=true}}
          else if(!same(docs[r.path],r.body)){docs[r.path]=r.body;persist(r.path);changed=true}}
        if(!cursor||r.updated_at>cursor)cursor=r.updated_at});
      try{window.localStorage.setItem("rq.cursor",cursor)}catch(e){}
      if(rejected&&!outbox.length)rejected=0;
      ok();if(changed)fire();return seen;
    },function(e){var c=e&&e.status;if(c>=400&&c<500&&c!==408&&c!==429)rejected=c;else offline=true;note();return null});
  }
  function firstPull(n){return pull().then(function(seen){
    if(seen===SKIP&&n>0)return new Promise(function(r){setTimeout(r,700)}).then(function(){return firstPull(n-1)});return seen})}
  function link(code){
    party=code;cursor="";outbox=[];rejected=0;saveOutbox();
    try{window.localStorage.setItem("rq.party",code);window.localStorage.removeItem("rq.cursor")}catch(e){}
    note();
    return firstPull(6).then(function(seen){
      if(seen===null||seen===SKIP)return false;
      Object.keys(docs).forEach(function(k){if(synced(k)&&seen.indexOf(k)<0)queue({op:"set",path:k,data:docs[k]})});
      return true});
  }
  function unlink(){party="";cursor="";outbox=[];rejected=0;saveOutbox();try{window.localStorage.removeItem("rq.party");window.localStorage.removeItem("rq.cursor")}catch(e){}note()}
  function newCode(){var a="ABCDEFGHJKMNPQRSTUVWXYZ23456789",b=new Uint8Array(20),s="";window.crypto.getRandomValues(b);
    for(var i=0;i<20;i++){s+=a[b[i]%a.length];if(i%5===4&&i<19)s+="-"}return s}
  function tick(ev){
    if(document.visibilityState!=="visible")return;
    if(Date.now()-questsAt>1800000)loadQuests().then(fire);
    if(outbox.length)flush();else pull(!!ev)}
  function clone(x){return JSON.parse(JSON.stringify(x))}
  function fire(){subs.forEach(function(f){try{f()}catch(e){}})}
  function persist(path){if(!idb)return;try{var s=idb.transaction("docs","readwrite").objectStore("docs");if(docs[path])s.put(docs[path],path);else s.delete(path)}catch(e){}}
  function snap(path){var d=docs[path];return{id:path.split("/").pop(),exists:!!d,data:function(){return d}}}
  function merge(a,b){for(var k in b){if(b[k]&&typeof b[k]==="object"&&!Array.isArray(b[k])&&a[k]&&typeof a[k]==="object"&&!Array.isArray(a[k]))merge(a[k],b[k]);else a[k]=b[k]}}
  function docRef(path){return{id:path.split("/").pop(),path:path,
    get:function(){return Promise.resolve(snap(path))},
    set:function(d){docs[path]=clone(d);persist(path);fire();queue({op:/^runs\//.test(path)?"update":"set",path:path,data:clone(d)});return Promise.resolve()},
    update:function(d){if(!docs[path])return Promise.reject({code:"missing"});var c=clone(docs[path]);merge(c,clone(d));docs[path]=c;persist(path);fire();queue({op:"update",path:path,data:clone(d)});return Promise.resolve()},
    "delete":function(){delete docs[path];persist(path);fire();queue({op:"delete",path:path});return Promise.resolve()},
    onSnapshot:function(n){var f=function(){n(snap(path))};subs.push(f);setTimeout(f,0);return function(){}}}}
  function coll(path,filt){
    var depth=path.split("/").length+1;
    function q(){var ds=Object.keys(docs).filter(function(k){return k.indexOf(path+"/")===0&&k.split("/").length===depth}).sort().map(snap);
      if(filt)ds=ds.filter(function(s){return s.data()[filt[0]]===filt[1]});return{docs:ds,size:ds.length,empty:!ds.length}}
    return{path:path,where:function(a,op,c){return coll(path,[a,c])},get:function(){return Promise.resolve(q())},
      onSnapshot:function(n){var f=function(){n(q())};subs.push(f);setTimeout(f,0);return function(){}},
      doc:function(id){return docRef(path+"/"+(id||("x"+Date.now().toString(36)+Math.random().toString(36).slice(2,8))))},
      add:function(d){var r=this.doc();return r.set(d).then(function(){return r})}}}
  function openIdb(){return new Promise(function(res){try{
    var r=window.indexedDB.open("roadbound",1);
    r.onupgradeneeded=function(){r.result.createObjectStore("docs")};
    r.onerror=function(){res()};
    r.onsuccess=function(){idb=r.result;var c=idb.transaction("docs").objectStore("docs").openCursor();
      c.onerror=function(){res()};
      c.onsuccess=function(){var cur=c.result;if(cur){if(cur.key==="_outbox")outbox=cur.value||[];else docs[cur.key]=cur.value;cur["continue"]()}else res()}};
  }catch(e){res()}})}
  function loadQuests(){
    questsAt=Date.now();
    return fetch("quests/index.json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(ix){
      return Promise.all((ix.quests||[]).map(function(id){return fetch("quests/"+id+".json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(q){return[id,q]})}))
    }).then(function(list){
      Object.keys(docs).forEach(function(k){if(k.indexOf("quests/")===0){delete docs[k];persist(k)}});
      list.forEach(function(p){docs["quests/"+p[0]]=p[1];persist("quests/"+p[0])});
    })["catch"](function(){questsAt=Date.now()-1500000 /* offline: keep the quests saved from last time, try again in five minutes */});
  }
  var api={doc:docRef,collection:function(p){return coll(p)}};
  return{open:function(){return openIdb().then(loadQuests).then(function(){
    try{if(navigator.storage&&navigator.storage.persist)navigator.storage.persist()}catch(e){}
    setInterval(tick,8000);document.addEventListener("visibilitychange",tick);window.addEventListener("online",tick);setTimeout(function(){tick(1)},300);
    return{db:api,saved:!!idb}})},
    saved:function(){return !!idb},
    stats:function(){var n={quests:0,runs:0,photos:0};Object.keys(docs).forEach(function(k){var t=k.split("/")[0];if(n[t]!=null)n[t]++});return n},
    dump:function(){var o={};Object.keys(docs).forEach(function(k){if(synced(k))o[k]=clone(docs[k])});return o},
    restore:function(o){var n=0;Object.keys(o||{}).forEach(function(k){if(synced(k)&&o[k]&&typeof o[k]==="object"){docRef(k).set(o[k]);n++}});return n},
    sync:{rejected:function(){return rejected},
      test:function(){
        if(!cfg.url||!cfg.key)return Promise.resolve({ready:false});
        var code=party||"CHECK-CHECK-CHECK-CHECK",t0=Date.now(),base=cfg.url.replace(/\/+$/,""),out={ready:true,linked:!!party},
          h={apikey:cfg.key,Authorization:"Bearer "+cfg.key,"x-party":code,"Content-Type":"application/json"};
        return fetch(base+"/rest/v1/docs?party=eq."+encodeURIComponent(code)+"&select=path&limit=1",{headers:h,cache:"no-store"}).then(function(r){
          out.read=r.status;out.ms=Date.now()-t0;if(!party||!r.ok)return out;
          return fetch(base+"/rest/v1/rpc/merge_doc",{method:"POST",headers:h,cache:"no-store",body:JSON.stringify({p_party:code,p_path:"check/ping",p_patch:{at:Date.now()}})}).then(function(w){out.write=w.status;return out})
        })["catch"](function(){if(out.read)out.write=0;else out.read=0;return out})},
      ready:function(){return !!(cfg.url&&cfg.key)},code:function(){return party},pending:function(){return outbox.length},offline:function(){return offline},lastOk:function(){return lastOk},
      link:link,unlink:unlink,newCode:newCode,onChange:function(f){statusSubs.push(f)}}};
})();
</script>
"""

body_part = swap(body_part, "<script>\n(function(){", STORE + "<script>\n(function(){")

body_part = swap(
    body_part,
    """  if(!window.claude||!window.claude.use){S.dead=true;render();return}
  window.claude.use("db").then(function(db){
    if(!db){S.dead=true;clearTimeout(slowT);render();return}
    S.db=db;""",
    """  window.RQ.open().then(function(o){
    var db=o.db;
    if(!o.saved)S.err="This browser isn't letting the app save to the phone, so this visit won't be remembered. Private or incognito windows do this.";
    S.db=db;""",
)
body_part = swap(body_part, """  window.claude.use("sample").then(function(f){S.sample=f||null});\n""", "")
body_part = swap(
    body_part,
    """<strong>The shared log can\\'t be reached from here.</strong> Open this page from its claude.ai link while signed in. Nothing on this page can be saved until then.""",
    """<strong>The journal couldn\\'t be opened.</strong> Close the app and open it again.""",
)
body_part = swap(body_part, "once the shared log answers.</p></section>';\n  else if(S.tab===\"party\")", "in a moment.</p></section>';\n  else if(S.tab===\"party\")")
body_part = swap(body_part, "will appear here once the shared log answers.</p></section>\n  </main>", "will appear here in a moment.</p></section>\n  </main>")
body_part = swap(body_part, "Still trying to reach the shared log. What you see may be out of date.", "Still opening the journal.")
body_part = swap(body_part, "It reaches the shared log when you reveal it at home.", "It joins the journal when you reveal it at home.")
body_part = swap(body_part, "Have it written from what you marked above, then change anything you like.", "Tap the button for a first draft made from what you marked above, then make it yours.")

start = body_part.index("'<section class=\"page\"><p class=\"eyebrow\">Two phones, one log</p>")
end = body_part.index("</section>';", start) + len("</section>';")
body_part = body_part[:start] + (
    "'<section class=\"page\"><p class=\"eyebrow\">Put it on your home screen</p><ul class=\"plain\">"
    "<li><strong>iPhone:</strong> open this address in Safari, tap Share, then Add to Home Screen.</li>"
    "<li><strong>Android:</strong> open it in Chrome, tap the menu, then Install app or Add to Home screen.</li></ul>"
    "<p>After that it opens full screen from its own icon and keeps working with no signal.</p></section>'+syncBlock()+diagBlock()+backupBlock();"
) + body_part[end:]

body_part = swap(
    body_part,
    "/* ---------- photos ---------- */",
    r"""/* ---------- two-phone sync ---------- */
function syncBlock(){
  var y=window.RQ.sync,h='<section class="page"><p class="eyebrow">Two phones, one journal</p>';
  if(!y.ready())return h+'<p>Linking two phones isn\'t switched on yet. Until it is, this journal is saved on this phone only, so play on one phone and choose "Both of us" above.</p></section>';
  if(!y.code()){
    h+='<p>Right now this journal is saved on this phone only. Link your two phones and both will show the same party, progress, photos and scrapbook.</p>'+
      '<div class="stack"><div><button class="btn sm" data-act="syncNew">Start a shared journal on this phone</button></div>'+
      '<p class="small faded">Then, on the other phone, type the code this phone shows you:</p>'+
      '<div class="row"><input type="text" id="joinCode" class="grow" autocomplete="off" autocapitalize="characters" placeholder="XXXXX-XXXXX-XXXXX-XXXXX"><button class="btn sm ghost" data-act="syncJoin">Join</button></div>'+
      (S.syncMsg?'<p class="small" style="color:var(--oxblood)">'+esc(S.syncMsg)+'</p>':'')+'</div>';
  } else {
    var st=y.rejected()?"The shared journal turned a change away (error "+y.rejected()+"). Run the check below.":y.offline()?"Waiting for a connection. Changes are kept on this phone and sent when it returns.":(y.pending()?"Sending "+y.pending()+" change"+(y.pending()===1?"":"s")+"…":(y.lastOk()?"Linked and up to date.":"Linking…"));
    h+='<p><strong>'+esc(st)+'</strong></p><p class="small faded">Your journal code. Type it into the other phone once, and keep it between the two of you, since anyone with it could read and change your journal.</p>'+
      '<p style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:1.05rem;user-select:all;overflow-wrap:anywhere">'+esc(y.code())+'</p>'+
      '<div class="row"><button class="btn sm ghost" data-act="copyCode">'+(S.copied?"Copied":"Copy code")+'</button><button class="btn sm warn" data-act="ask" data-v="unlink">Unlink this phone</button></div>'+
      confirmBox("unlink","Unlink this phone? Its journal stays on it but stops updating.","Yes, unlink","syncOff")+
      (S.who?'':'<p class="note">Next: at the top of this page, pick who holds this phone.</p>');
  }
  return h+'<p class="small faded">Secret objectives are never shared. Each one stays on the phone that drew it until the reveal. The other phone catches up within about ten seconds.</p></section>'+
   '<section class="page"><p class="eyebrow">Where this journal lives</p><ul class="plain"><li>On this phone, inside this app'+(y.code()?', and in your shared journal online':'')+'.</li><li>Clearing this app\'s site data, or removing it from an iPhone home screen, erases the copy on this phone.</li><li>New quests arrive when the app is opened with a connection.</li></ul></section>';
}
function syncAct(act){
  var y=window.RQ.sync;
  function linked(ok){if(!ok)S.syncMsg="Couldn't reach the shared journal just now. It will keep trying.";else if(S.who==="both"){S.who="";lsSet("rq.who","")}render()}
  if(act==="syncNew"){S.syncMsg="";y.link(y.newCode()).then(linked);return true}
  if(act==="syncJoin"){var c=(($("joinCode")||{}).value||"").trim().toUpperCase().replace(/\s+/g,"");
    if(!/^[A-Z0-9]{5}(-[A-Z0-9]{5}){3}$/.test(c)){S.syncMsg="That code doesn't look right. It is four groups of five letters and numbers.";render();return true}
    S.syncMsg="";y.link(c).then(linked);return true}
  if(act==="syncOff"){S.confirm="";y.unlink();render();return true}
  if(act==="copyCode"){var done=function(){S.copied=true;render();setTimeout(function(){S.copied=false;render()},1500)};
    try{navigator.clipboard.writeText(y.code()).then(done,function(){})}catch(e){}return true}
  if(act==="diag"){runDiag();return true}
  if(act==="export"){try{
      var blob=new Blob([JSON.stringify({app:"roadbound",version:VERSION,saved:new Date().toISOString(),docs:window.RQ.dump()})],{type:"application/json"}),a=document.createElement("a");
      a.href=URL.createObjectURL(blob);a.download="roadbound-backup-"+new Date().toISOString().slice(0,10)+".json";document.body.appendChild(a);a.click();a.remove();
      setTimeout(function(){URL.revokeObjectURL(a.href)},10000);S.backupMsg="Backup file made. Look in your downloads."}catch(e){S.backupMsg="This phone wouldn't make the file."}
    render();return true}
  if(act==="doImport"){S.confirm="";var n=window.RQ.restore(S.importData);S.importData=null;S.backupMsg="Restored "+n+" entr"+(n===1?"y":"ies")+" from the backup.";render();return true}
  return false;
}
var VERSION="2026.11.11-2";
function diagBlock(){
  var h='<section class="page"><p class="eyebrow">Check this phone</p><p class="small faded">A quick health check of this phone\'s storage, the quest board and the link between your phones.</p>'+
    '<div><button class="btn sm ghost" data-act="diag" '+(S.diagBusy?"disabled":"")+'>'+(S.diagBusy?"Checking…":"Run the check")+'</button></div>';
  if(S.diag)h+='<ul class="plain">'+S.diag.map(function(d){return '<li><span class="chip '+(d[0]===true?"ok":d[0]===false?"bad":"")+'">'+(d[0]===true?"good":d[0]===false?"problem":"note")+'</span> '+esc(d[1])+'</li>'}).join("")+'</ul>';
  return h+'<p class="small faded">App version '+VERSION+'</p></section>';
}
function backupBlock(){
  return '<section class="page"><p class="eyebrow">Backup</p><p class="small faded">Save your party, progress and photos as a file, or bring a saved file back.</p>'+
    '<div class="row"><button class="btn sm ghost" data-act="export">Save a backup file</button><label class="btn sm ghost" style="display:inline-flex;align-items:center;cursor:pointer">Restore from a file<input type="file" id="importIn" accept="application/json,.json" hidden></label></div>'+
    confirmBox("import","Restore this backup? Anything in it replaces what this phone has for the same quest, and linked phones follow.","Yes, restore","doImport")+
    (S.backupMsg?'<p class="small">'+esc(S.backupMsg)+'</p>':'')+'</section>';
}
function runDiag(){
  var R=window.RQ,y=R.sync,out=[],st=R.stats(),jobs=[];S.diagBusy=true;S.diag=null;render();
  out.push(R.saved()?[true,"This phone is saving the journal."]:[false,"This browser is not saving anything, so the journal will be forgotten. Private windows do this."]);
  out.push([null,((window.matchMedia&&window.matchMedia("(display-mode: standalone)").matches)||window.navigator.standalone)?"Running as an installed app.":"Running in a browser tab. Adding it to the home screen gives it its own icon and a safer place to keep the journal."]);
  out.push((navigator.serviceWorker&&navigator.serviceWorker.controller)?[true,"Ready to work with no signal."]:[null,"The no-signal copy isn't ready yet. Open the app once more while connected."]);
  out.push([null,"The journal holds "+st.quests+" quest"+(st.quests===1?"":"s")+", "+st.runs+" started, and "+st.photos+" photo"+(st.photos===1?"":"s")+"."]);
  jobs.push(fetch("quests/index.json",{cache:"no-store"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(ix){var n=(ix.quests||[]).length;out.push([true,"Quest board reached. It lists "+n+" quest"+(n===1?"":"s")+"."])},
    function(){out.push([st.quests>0?null:false,"Couldn't reach the quest board just now"+(st.quests>0?", so the saved quests are being used.":".")])}));
  jobs.push(y.test().then(function(t){
    if(!t.ready){out.push([null,"Linking two phones isn't switched on in this copy of the app."]);return}
    if(t.read===200)out.push([true,"The shared journal answered in "+t.ms+" ms."]);
    else if(!t.read)out.push([false,"Couldn't reach the shared journal. Check the connection and try again."]);
    else out.push([false,"The shared journal answered with error "+t.read+"."]);
    if(!t.linked)out.push([null,"This phone isn't linked to a shared journal yet."]);
    else if(t.read===200)out.push(t.write>=200&&t.write<300?[true,"This phone can write to the shared journal."]:[false,"This phone could not write to the shared journal (error "+(t.write||"unknown")+")."]);
    if(y.rejected())out.push([false,"A change was turned away earlier (error "+y.rejected()+") and is still waiting."]);
    else if(t.linked&&y.pending())out.push([null,y.pending()+" change"+(y.pending()===1?" is":"s are")+" waiting to be sent."]);
  }));
  Promise.all(jobs).then(function(){S.diagBusy=false;S.diag=out;render()});
}
document.addEventListener("change",function(e){var t=e.target;if(t.id!=="importIn"||!t.files||!t.files[0])return;
  var r=new FileReader();r.onload=function(){try{var o=JSON.parse(r.result);if(!o||o.app!=="roadbound"||!o.docs)throw 0;S.importData=o.docs;S.confirm="import";S.backupMsg=""}catch(x){S.importData=null;S.backupMsg="That file isn't a Roadbound backup."}render()};
  r.readAsText(t.files[0])});
window.RQ.sync.onChange(function(){syncLine();if(S.tab==="camp")scheduleRender()});

/* ---------- photos ---------- */""",
)
body_part = swap(body_part, "  else if(!q)return;\n", "  else if(syncAct(act)){}\n  else if(!q)return;\n")
body_part = swap(
    body_part,
    "render();boot();",
    'render();boot();\nif("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("sw.js").catch(function(){})})}',
)
assert "claude" not in body_part.lower().replace("claude-fable-5-2", ""), "leftover reference"

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#ece2cb" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#191511" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Roadbound">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-192.png">
<style>:root{padding-top:env(safe-area-inset-top,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""
open(out + "/index.html", "w", encoding="utf-8").write(HEAD + head_part + "</head>\n<body>\n" + body_part + "</body>\n</html>\n")

open(out + "/manifest.webmanifest", "w", encoding="utf-8").write("""{
  "name": "Roadbound Quest Log",
  "short_name": "Roadbound",
  "description": "A co-op real-life road trip game for two.",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#ece2cb",
  "theme_color": "#ece2cb",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
""")

open(out + "/sw.js", "w", encoding="utf-8").write("""// Keeps the app working with no signal: try the network first, fall back to the last saved copy.
const CACHE = "roadbound-v3";
const SHELL = ["./", "index.html", "config.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "quests/index.json"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (u.hostname === "fonts.googleapis.com" || u.hostname === "fonts.gstatic.com") {
    e.respondWith(caches.open(CACHE).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok || r.type === "opaque") c.put(e.request, r.clone()); return r; }))));
    return;
  }
  if (u.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match("index.html")))
  );
});
""")
print("built", out)
