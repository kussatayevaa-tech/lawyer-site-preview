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
    burger.setAttribute("aria-label", open ? "Мәзірді жабу" : "Мәзірді ашу");
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
      var msg = "Сәлеметсіз бе, Айдана Ерланқызы! " + (name ? "Менің атым " + name + ". " : "") + (topic ? "Тақырып: " + topic + ". " : "") + (txt || "Кеңес алғым келеді.");
      go.href = "https://wa.me/" + WA + "?text=" + encodeURIComponent(msg);
    };
    ["input", "change"].forEach(function (ev) { qf.addEventListener(ev, upd); });
    qf.addEventListener("submit", function (e) { e.preventDefault(); });
    go.addEventListener("click", function (e) {
      if (n.value.trim().length < 2) { e.preventDefault(); er.textContent = "Сізге қалай жүгінейін, жазыңыз."; n.focus(); }
      else er.textContent = "";
    });
    upd();
  }
})();

(function () {
  document.addEventListener("click", function (e) {
    var z = e.target.closest && e.target.closest("[data-zoom]");
    if (!z) return;
    var lb = document.createElement("div"); lb.className = "lb"; lb.setAttribute("role", "dialog"); lb.setAttribute("aria-label", "Құжат");
    lb.innerHTML = '<img alt=""><button type="button" aria-label="Жабу">×</button>';
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
   [/astana|nur-sultan|nursultan|akmolinsk|tselinograd/,"Астана","Астаны","Астана"],
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
    for(var i=0;i<C.length;i++) if(C[i][0].test(s)) return C[i];
    return null;
  }
  var cached=null; try{cached=sessionStorage.getItem("geoKZ2");}catch(e){}
  if(cached!==null){ try{var c=pick(JSON.parse(cached)); if(c) apply(c);}catch(e){} return; }
  if(!window.fetch) return;
  var ctl=window.AbortController?new AbortController():null; var t=setTimeout(function(){if(ctl)ctl.abort();},2500);
  fetch("https://get.geojs.io/v1/ip/geo.json",ctl?{signal:ctl.signal}:{}).then(function(r){return r.json();}).then(function(g){
    clearTimeout(t); var lite={country_code:g.country_code,city:g.city,region:g.region};
    try{sessionStorage.setItem("geoKZ2",JSON.stringify(lite));}catch(e){}
    var c=pick(lite); if(c) apply(c);
  }).catch(function(){});
})();

/* Запись: стрелки и прокрутка к выбранному дню */
(function () {
  var box = document.getElementById("days"); if (!box) return;
  var wrap = box.parentNode, prev = wrap.querySelector(".prev"), next = wrap.querySelector(".next");
  function upd() { prev.disabled = box.scrollLeft < 4; next.disabled = box.scrollLeft + box.clientWidth >= box.scrollWidth - 4; }
  function step(dir) { box.scrollBy({ left: dir * Math.max(box.clientWidth - 80, 160), behavior: "smooth" }); }
  prev.addEventListener("click", function () { step(-1); });
  next.addEventListener("click", function () { step(1); });
  box.addEventListener("scroll", upd, { passive: true });
  window.addEventListener("resize", upd);
  new MutationObserver(function () {
    var sel = box.querySelector('[aria-pressed="true"]');
    if (sel) { var l = sel.offsetLeft - box.offsetLeft, r = l + sel.offsetWidth;
      if (l < box.scrollLeft || r > box.scrollLeft + box.clientWidth) box.scrollTo({ left: Math.max(0, l - 16), behavior: "smooth" }); }
    upd();
  }).observe(box, { childList: true });
  setTimeout(upd, 300);
})();

/* Заголовок первого экрана по словам и параллакс фото */
(function () {
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var h = document.querySelector(".hero h1");
  if (h && !reduce) {
    var i = 0;
    Array.prototype.slice.call(h.childNodes).forEach(function (n) {
      if (n.nodeType === 3) {
        var frag = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach(function (p) {
          if (!p) return;
          if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
          var s = document.createElement("span"); s.className = "w"; s.style.setProperty("--i", i++); s.textContent = p; frag.appendChild(s);
        });
        n.parentNode.replaceChild(frag, n);
      } else if (n.nodeType === 1) { n.classList.add("w"); n.style.setProperty("--i", i++); }
    });
  }
  if (!("IntersectionObserver" in window)) document.documentElement.classList.add("no-io");
  var ph = document.querySelector(".hero-photo");
  if (ph && !reduce && window.matchMedia("(min-width: 861px)").matches) {
    var tick = false;
    window.addEventListener("scroll", function () {
      if (tick) return; tick = true;
      requestAnimationFrame(function () { var y = Math.min(window.scrollY, 700); ph.style.transform = "translateY(" + (y * 0.08).toFixed(1) + "px)"; tick = false; });
    }, { passive: true });
  }
})();
(function () { Array.prototype.forEach.call(document.querySelectorAll(".eyebrow"), function (e) { if (!e.closest(".rv")) e.classList.add("in"); }); })();

/* Калькулятор неустойки */
(function () {
  var form = document.getElementById("calc"); if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var pays = $("cPays"), res = $("cRes"), err = $("cErr");
  function num(v) { v = String(v || "").replace(/\s/g, "").replace(",", "."); var n = parseFloat(v); return isFinite(n) ? n : NaN; }
  function day(v) { if (!v) return NaN; var p = v.split("-"); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / 864e5; }
  function fmtD(d) { var x = new Date(d * 864e5); return ("0" + x.getUTCDate()).slice(-2) + "." + ("0" + (x.getUTCMonth() + 1)).slice(-2) + "." + x.getUTCFullYear(); }
  function money(n) { return n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/ /g, " "); }
  function mode() { var r = form.querySelector("input[name=mode]:checked"); return r ? r.value : "contract"; }
  function sync() {
    var law = mode() === "law";
    form.querySelectorAll(".m-law").forEach(function (e) { e.hidden = !law; });
    form.querySelectorAll(".m-contract").forEach(function (e) { e.hidden = law; });
  }
  form.querySelectorAll("input[name=mode]").forEach(function (r) { r.addEventListener("change", function () { sync(); res.hidden = true; }); });
  $("cAdd").addEventListener("click", function () {
    var row = document.createElement("div"); row.className = "calc-pay";
    row.innerHTML = '<label>Төлем күні<input type="date" class="pD"></label><label>Сомасы, теңге<input type="text" inputmode="decimal" class="pA"></label><button type="button" class="calc-del" aria-label="Жою">×</button>';
    row.querySelector(".calc-del").addEventListener("click", function () { row.remove(); });
    pays.appendChild(row);
  });
  function period() {
    var E = day($("cDue").value), F = day($("cTo").value), p = $("cPeriod");
    if (isNaN(E) || isNaN(F)) { p.hidden = true; return; }
    if (F <= E) { p.textContent = "Есеп күні төлемнің соңғы күнінен кейін болуы керек."; p.hidden = false; return; }
    p.textContent = "Тұрақсыздық айыбы " + fmtD(E + 1) + " бастап " + fmtD(F) + " дейін (қоса алғанда) есептеледі: мерзімі өткен " + (F - E) + " күн.";
    p.hidden = false;
  }
  ["cDue", "cTo"].forEach(function (id) { $(id).addEventListener("change", period); $(id).addEventListener("input", period); });
  var t = new Date(); $("cTo").value = t.getFullYear() + "-" + ("0" + (t.getMonth() + 1)).slice(-2) + "-" + ("0" + t.getDate()).slice(-2);
  function fail(m) { err.textContent = m; err.hidden = false; res.hidden = true; }
  form.addEventListener("submit", function (e) {
    e.preventDefault(); err.hidden = true;
    var D = num($("cDebt").value), E = day($("cDue").value), F = day($("cTo").value), law = mode() === "law";
    if (!(D > 0)) return fail("Борыш сомасын көрсетіңіз.");
    if (isNaN(E) || isNaN(F)) return fail("Төлемнің соңғы күнін және есеп күнін көрсетіңіз.");
    if (F <= E) return fail("Есеп күні төлемнің соңғы күнінен кейін болуы керек.");
    var rate, cap = NaN, yd = 365;
    if (law) { rate = num($("cBase").value); yd = +$("cYear").value; if (!(rate > 0)) return fail("Ұлттық Банктің базалық мөлшерлемесін көрсетіңіз."); }
    else { rate = num($("cRate").value); cap = num($("cCap").value); if (!(rate > 0)) return fail("Шарт бойынша тұрақсыздық айыбының мөлшерін күніне пайызбен көрсетіңіз."); }
    var list = [];
    var bad = false;
    pays.querySelectorAll(".calc-pay").forEach(function (r) {
      var d = day(r.querySelector(".pD").value), a = num(r.querySelector(".pA").value);
      if (isNaN(d) && isNaN(a)) return;
      if (isNaN(d) || !(a > 0)) { bad = true; return; }
      list.push({ d: d, a: a });
    });
    if (bad) return fail("Ішінара төлемдердің күндері мен сомаларын тексеріңіз.");
    list.sort(function (x, y) { return x.d - y.d; });
    var base = D, cur = E, rows = [], total = 0, i;
    for (i = 0; i < list.length && list[i].d <= E; i++) base -= list[i].a;
    function add(to) {
      var days = to - cur; if (days <= 0 || base <= 0) { cur = to; return; }
      var s = law ? base * rate / 100 / yd * days : base * rate / 100 * days;
      rows.push([fmtD(cur + 1), fmtD(to), days, base, s]); total += s; cur = to;
    }
    for (; i < list.length && list[i].d <= F; i++) { add(list[i].d); base -= list[i].a; }
    add(F);
    var capSum = (!law && cap > 0) ? D * cap / 100 : NaN, final = total;
    if (capSum === capSum && total > capSum) final = capSum;
    var h = '<h2>Есептеу нәтижесі</h2><div class="tbl"><table><thead><tr><th>Кезең</th><th>Күн</th><th>Борыш сомасы, теңге</th><th>Тұрақсыздық айыбы, теңге</th></tr></thead><tbody>';
    rows.forEach(function (r) { h += "<tr><td>" + r[0] + " – " + r[1] + "</td><td>" + r[2] + "</td><td>" + money(r[3]) + "</td><td>" + money(r[4]) + "</td></tr>"; });
    h += "</tbody></table></div>";
    h += "<p>Мерзімі өткен кезең: " + fmtD(E + 1) + " бастап " + fmtD(F) + ", " + (F - E) + " күн.</p>";
    h += "<p>" + (law ? "Мөлшерлеме: " + String(rate).replace(".", ",") + "% жылдық, " + yd + " күн жылына (АК-нің 353-бабы)." : "Шарт бойынша мөлшерлеме: " + String(rate).replace(".", ",") + "% күніне.") + "</p>";
    h += '<p class="calc-total">Барлығы тұрақсыздық айыбы: <b>' + money(final) + " теңге</b></p>";
    if (final !== total) h += "<p>Есептік сома " + money(total) + " теңге шарт бойынша шектен асады, сондықтан нәтиже шекпен шектелді: " + money(capSum) + " теңге.</p>";
    if (base <= 0) h += "<p>Борыш толық өтелді, тұрақсыздық айыбы соңғы төлем күніне дейін есептелді.</p>";
    h += '<p class="fine">Тұрақсыздық айыбы кредитордың залалымен салыстырғанда тым жоғары болса, сот борышкердің талабы бойынша оны азайтуға құқылы (АК-нің 297-бабы). <a href="#umenshenie-neustojki" data-calc-anchor>Азайту туралы қалай мәлімдеуге болады</a></p>';
    res.innerHTML = h; res.hidden = false;
    var an = res.querySelector("[data-calc-anchor]"); if (an) an.addEventListener("click", function (ev) { ev.preventDefault(); var t = document.getElementById("umenshenie-neustojki"); if (t) t.scrollIntoView({ behavior: "smooth" }); }); res.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  sync();
})();
