/* Сайт юриста Айданы Кусатаевой: навигация по разделам, меню, вкладки, анимации. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var body = document.body;
  var WA = body.getAttribute("data-wa") || "";
  var views = $$(".view"), byRoute = {};
  views.forEach(function (v) { byRoute[v.getAttribute("data-route")] = v; });
  var META = {};
  try { META = JSON.parse($("#meta-json").textContent); } catch (e) {}
  var metaDesc = $('meta[name="description"]');
  var ogT = $('meta[property="og:title"]'), ogD = $('meta[property="og:description"]');
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ----- разбор адреса: #name, #/a/b (старый вид) ----- */
  function parseRoute() {
    var h = "";
    try { h = decodeURIComponent((location.hash || "").replace(/^#/, "")); } catch (e) { h = (location.hash || "").replace(/^#/, ""); }
    h = h.replace(/^\/+/, "").replace(/\/+/g, "-").replace(/[^a-zA-Z0-9\-_]/g, "").toLowerCase();
    if (!h || h === "home" || h === "top") return { route: "home" };
    if (h === "biznes" || h === "uslugi-biznes") return { route: "uslugi", tab: "biz" };
    if (h === "rezultaty") return { route: "otzyvy" };
    if (byRoute[h]) return { route: h };
    return { route: "home" };
  }

  /* ----- меню ----- */
  var megaBtn = $("#megaBtn"), mega = $("#mega"), burger = $("#burger"), mnav = $("#mnav");
  function setMega(open) {
    if (!mega) return;
    mega.hidden = !open;
    megaBtn.setAttribute("aria-expanded", String(open));
    megaBtn.parentNode.classList.toggle("open", open);
  }
  function setMnav(open) {
    if (!mnav) return;
    mnav.hidden = !open;
    burger.setAttribute("aria-expanded", String(open));
    burger.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    document.body.classList.toggle("menu-open", open);
  }
  if (megaBtn) {
    megaBtn.addEventListener("click", function () {
      var hov = window.matchMedia && matchMedia("(hover:hover)").matches && window.innerWidth > 860;
      setMega(hov ? true : mega.hidden);
    });
    var holder = megaBtn.parentNode, timer = null;
    holder.addEventListener("mouseenter", function () { if (window.innerWidth > 860 && matchMedia("(hover:hover)").matches) { clearTimeout(timer); setMega(true); } });
    holder.addEventListener("mouseleave", function () { if (window.innerWidth > 860 && matchMedia("(hover:hover)").matches) { timer = setTimeout(function () { setMega(false); }, 160); } });
  }
  if (burger) burger.addEventListener("click", function () { setMnav(mnav.hidden); });
  document.addEventListener("click", function (e) {
    if (mega && !mega.hidden && !e.target.closest(".has-mega")) setMega(false);
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { setMega(false); setMnav(false); } });

  /* ----- вкладки «Частным лицам / Бизнесу» ----- */
  function setTab(box, aud) {
    $$(".seg button", box).forEach(function (b) { b.setAttribute("aria-selected", String(b.getAttribute("data-aud") === aud)); });
    $$("[data-pane]", box).forEach(function (p) { p.hidden = p.getAttribute("data-pane") !== aud; });
    $$("[data-pane] .rv:not(.in)", box).forEach(function (x) { if (!x.closest("[hidden]")) observe(x); });
  }
  $$("[data-tabs]").forEach(function (box) {
    $$(".seg button", box).forEach(function (b) {
      b.addEventListener("click", function () { setTab(box, b.getAttribute("data-aud")); });
    });
  });

  /* ----- фильтр статей ----- */
  var filters = $$(".afilters button");
  filters.forEach(function (b) {
    b.addEventListener("click", function () {
      var f = b.getAttribute("data-f");
      filters.forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      $$("#artGrid .acard").forEach(function (c) { c.hidden = !(f === "all" || c.getAttribute("data-cat") === f); });
    });
  });

  /* ----- появление блоков и счётчики ----- */
  $$(".stagger").forEach(function (g) {
    Array.prototype.forEach.call(g.children, function (c, i) { c.classList.add("rv"); c.style.setProperty("--d", (i * 70) + "ms"); });
  });
  var io = null;
  if ("IntersectionObserver" in window && !reduce) {
    io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target; io.unobserve(el);
        el.classList.add("in");
        $$("[data-count]", el).forEach(countUp);
        if (el.matches("[data-count]")) countUp(el);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
  }
  function observe(el) { if (io) io.observe(el); else { el.classList.add("in"); } }
  function countUp(el) {
    if (el.__done) return; el.__done = true;
    var end = parseFloat(el.getAttribute("data-count")), dec = parseInt(el.getAttribute("data-dec") || "0", 10);
    var suf = el.getAttribute("data-suffix") || "";
    var fmt = function (v) { return (dec ? v.toFixed(dec).replace(".", ",") : String(Math.round(v))) + suf; };
    if (reduce || isNaN(end)) { el.textContent = fmt(end); return; }
    var t0 = null, dur = 1100;
    function step(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(end * e);
      if (k < 1) requestAnimationFrame(step); else el.textContent = fmt(end);
    }
    requestAnimationFrame(step);
  }
  function revealView(v) {
    $$(".rv:not(.in)", v).forEach(function (x) { if (!x.closest("[hidden]")) observe(x); });
    $$(".steps:not(.in)", v).forEach(function (x) { observe(x); });
    $$(".stat strong[data-count]", v).forEach(function (x) { if (!io) countUp(x); });
  }
  $$(".steps").forEach(function (s) { s.classList.add("rv"); });

  /* ----- переключение раздела ----- */
  var navItems = $$("[data-nav]");
  function show() {
    var r = parseRoute(), v = byRoute[r.route] || byRoute.home;
    views.forEach(function (x) { x.hidden = x !== v; });
    var m = META[r.route];
    if (m) {
      document.title = m[0];
      if (metaDesc) metaDesc.setAttribute("content", m[1]);
      if (ogT) ogT.setAttribute("content", m[0]);
      if (ogD) ogD.setAttribute("content", m[1]);
    }
    var key = r.route.split("-")[0];
    navItems.forEach(function (n) { n.classList.toggle("on", n.getAttribute("data-nav") === key); });
    if (r.route === "uslugi" && r.tab) { var box = $("[data-tabs]", v); if (box) setTab(box, r.tab); }
    setMega(false); setMnav(false);
    window.scrollTo(0, 0);
    revealView(v);
  }
  window.addEventListener("hashchange", show);
  show();

  /* ----- быстрая форма в WhatsApp ----- */
  var qf = $("#qf");
  if (qf) {
    var n = $("#qfName"), tp = $("#qfTopic"), tx = $("#qfText"), go = $("#qfGo"), er = $("#qfErr");
    var upd = function () {
      var name = n.value.trim(), topic = tp.value, txt = tx.value.trim();
      var msg = "Здравствуйте, Айдана Ерлановна! " + (name ? "Меня зовут " + name + ". " : "") + (topic ? "Тема: " + topic + ". " : "") + (txt || "Хочу получить консультацию.");
      go.href = "https://wa.me/" + WA + "?text=" + encodeURIComponent(msg);
    };
    ["input", "change"].forEach(function (ev) { qf.addEventListener(ev, upd); });
    qf.addEventListener("submit", function (e) { e.preventDefault(); });
    go.addEventListener("click", function (e) {
      if (n.value.trim().length < 2) { e.preventDefault(); er.textContent = "Напишите, как к вам обращаться."; n.focus(); }
      else er.textContent = "";
    });
    upd();
  }
})();

(function () {
  document.addEventListener("click", function (e) {
    var z = e.target.closest && e.target.closest("[data-zoom]");
    if (!z) return;
    var lb = document.createElement("div"); lb.className = "lb"; lb.setAttribute("role", "dialog"); lb.setAttribute("aria-label", "Документ");
    lb.innerHTML = '<img alt=""><button type="button" aria-label="Закрыть">\u00d7</button>';
    lb.querySelector("img").src = z.getAttribute("data-zoom");
    var close = function () { lb.remove(); document.removeEventListener("keydown", esc); };
    var esc = function (ev) { if (ev.key === "Escape") close(); };
    lb.addEventListener("click", close); document.addEventListener("keydown", esc);
    document.body.appendChild(lb);
  });
})();

/* Переключатель языка: сохраняет текущий раздел */
document.querySelectorAll('a.lang,a.lang-m').forEach(function(a){a.addEventListener('click',function(){var h=a.getAttribute('href').split('#')[0];a.setAttribute('href',h+(location.hash||''));});});

/* Чат из мобильного меню */
document.querySelectorAll('[data-open-chat]').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();document.body.classList.remove('menu-open');var m=document.querySelector('.mnav');var b=document.querySelector('.burger');if(b&&b.getAttribute('aria-expanded')==='true')b.click();var c=document.getElementById('chatBtn');if(c)c.click();});});

/* Город посетителя по IP (GeoJS): подставляется в плашку и заголовок, нигде не сохраняется */
(function(){
  var C=[ // [шаблон (город/область, англ.), именительный рус., родительный рус., каз.]
   [/almaty oblast|almaty region|konaev|kapshagay|qonaev/,"Алматы","Алматы","Алматы"],
   [/almaty|alma-ata/,"Алматы","Алматы","Алматы"],
   [/shymkent|chimkent/,"Шымкент","Шымкента","Шымкент"],
   [/karaganda|qaraghandy|karagandy|temirtau/,"Караганда","Караганды","Қарағанды"],
   [/aktobe|aqtobe|aktyubinsk/,"Актобе","Актобе","Ақтөбе"],
   [/atyrau/,"Атырау","Атырау","Атырау"],
   [/aktau|aqtau|mangystau|mangistau|zhanaozen/,"Актау","Актау","Ақтау"],
   [/pavlodar|ekibastuz/,"Павлодар","Павлодара","Павлодар"],
   [/kostanay|qostanay|kustanay|rudny/,"Костанай","Костаная","Қостанай"],
   [/semey|semipalatinsk|abai|abay/,"Семей","Семея","Семей"],
   [/ust-kamenogorsk|oskemen|öskemen|east kazakhstan|ridder/,"Усть-Каменогорск","Усть-Каменогорска","Өскемен"],
   [/uralsk|oral|west kazakhstan/,"Уральск","Уральска","Орал"],
   [/petropavl|north kazakhstan/,"Петропавловск","Петропавловска","Петропавл"],
   [/kokshetau|akmola|aqmola|shchuchinsk/,"Кокшетау","Кокшетау","Көкшетау"],
   [/taraz|jambyl|zhambyl/,"Тараз","Тараза","Тараз"],
   [/kyzylorda|qyzylorda/,"Кызылорда","Кызылорды","Қызылорда"],
   [/taldykorgan|taldyqorgan|zhetysu|jetisu/,"Талдыкорган","Талдыкоргана","Талдықорған"],
   [/turkestan|turkistan/,"Туркестан","Туркестана","Түркістан"],
   [/zhezkazgan|jezkazgan|ulytau|satpaev/,"Жезказган","Жезказгана","Жезқазған"]];
  var kk=(document.documentElement.lang==="kk");
  function apply(c){
    var p=document.getElementById("geoCity"), h=document.getElementById("geoH1");
    if(p) p.textContent=kk?c[3]:c[1];
    if(h) h.textContent=kk?c[3]:c[2];
  }
  function pick(g){
    if(!g||g.country_code!=="KZ") return null;
    var s=((g.city||"")+" | "+(g.region||"")).toLowerCase();
    if(/astana|nur-sultan|akmolinsk/.test((g.city||"").toLowerCase())) return null;
    for(var i=0;i<C.length;i++) if(C[i][0].test(s)) return C[i];
    return null;
  }
  var cached=null; try{cached=sessionStorage.getItem("geoKZ");}catch(e){}
  if(cached!==null){ try{var c=pick(JSON.parse(cached)); if(c) apply(c);}catch(e){} return; }
  if(!window.fetch) return;
  var ctl=window.AbortController?new AbortController():null; var t=setTimeout(function(){if(ctl)ctl.abort();},2500);
  fetch("https://get.geojs.io/v1/ip/geo.json",ctl?{signal:ctl.signal}:{}).then(function(r){return r.json();}).then(function(g){
    clearTimeout(t); var lite={country_code:g.country_code,city:g.city,region:g.region};
    try{sessionStorage.setItem("geoKZ",JSON.stringify(lite));}catch(e){}
    var c=pick(lite); if(c) apply(c);
  }).catch(function(){});
})();
