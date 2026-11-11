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

STORE = r"""<script>
/* Local journal: every document is kept in this phone's IndexedDB. Quests are read from the quests/ folder beside the app. */
window.RQ=(function(){
  var docs={},subs=[],idb=null;
  function clone(x){return JSON.parse(JSON.stringify(x))}
  function fire(){subs.forEach(function(f){try{f()}catch(e){}})}
  function persist(path){if(!idb)return;try{var s=idb.transaction("docs","readwrite").objectStore("docs");if(docs[path])s.put(docs[path],path);else s.delete(path)}catch(e){}}
  function snap(path){var d=docs[path];return{id:path.split("/").pop(),exists:!!d,data:function(){return d}}}
  function merge(a,b){for(var k in b){if(b[k]&&typeof b[k]==="object"&&!Array.isArray(b[k])&&a[k]&&typeof a[k]==="object"&&!Array.isArray(a[k]))merge(a[k],b[k]);else a[k]=b[k]}}
  function docRef(path){return{id:path.split("/").pop(),path:path,
    get:function(){return Promise.resolve(snap(path))},
    set:function(d){docs[path]=clone(d);persist(path);fire();return Promise.resolve()},
    update:function(d){if(!docs[path])return Promise.reject({code:"missing"});var c=clone(docs[path]);merge(c,clone(d));docs[path]=c;persist(path);fire();return Promise.resolve()},
    "delete":function(){delete docs[path];persist(path);fire();return Promise.resolve()},
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
      c.onsuccess=function(){var cur=c.result;if(cur){docs[cur.key]=cur.value;cur["continue"]()}else res()}};
  }catch(e){res()}})}
  function loadQuests(){
    return fetch("quests/index.json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(ix){
      return Promise.all((ix.quests||[]).map(function(id){return fetch("quests/"+id+".json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(q){return[id,q]})}))
    }).then(function(list){
      Object.keys(docs).forEach(function(k){if(k.indexOf("quests/")===0){delete docs[k];persist(k)}});
      list.forEach(function(p){docs["quests/"+p[0]]=p[1];persist("quests/"+p[0])});
    })["catch"](function(){/* offline: keep the quests saved from last time */});
  }
  var api={doc:docRef,collection:function(p){return coll(p)}};
  return{open:function(){return openIdb().then(loadQuests).then(function(){
    try{if(navigator.storage&&navigator.storage.persist)navigator.storage.persist()}catch(e){}
    return{db:api,saved:!!idb}})}};
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
    "<p>After that it opens full screen from its own icon and keeps working with no signal.</p></section>'+"
    "'<section class=\"page\"><p class=\"eyebrow\">Where this journal lives</p>"
    "<p>Your party, progress, photos and scrapbook are saved on this phone, inside this app. Nothing is sent anywhere.</p><ul class=\"plain\">"
    "<li>For now each phone keeps its own journal, so play on one phone and choose \"Both of us\" above.</li>"
    "<li>Clearing this app\\'s site data, or removing it from an iPhone home screen, erases the journal.</li>"
    "<li>New quests arrive when the app is opened with a connection.</li></ul></section>';"
) + body_part[end:]

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
const CACHE = "roadbound-v1";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png", "quests/index.json"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match("index.html")))
  );
});
""")
print("built", out)
