/* Run locally in a browser. No analytics, storage, network calls or external APIs. */
(() => {
  "use strict";
  const M = globalThis.LensModel, R = globalThis.LensMetrics, E = globalThis.LensEngine;
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const pct = value => (100 * value).toFixed(1).replace(/\.0$/, "") + "%";
  const pill = (text, kind) => { $("badge").textContent = text; $("badge").className = "status " + kind; };
  const samples = [
    ["حجز تخرّج","أبغى أحجز جلسة تصوير تخرج في الرياض يوم الخميس، عندكم وقت؟"],
    ["باقات بالمصري","عايزة أعرف باقة تصوير المنتجات بكام؟"],
    ["تعديل صورة","ممكن تفتحون إضاءة الصورة شوي؟"],
    ["English","My gallery link has expired and I can’t open my album."],
    ["تكرار الأحرف","غيرررروا موعد الحجززززز!"],
    ["خارج النطاق","كيف أجدد جواز السفر؟"]
  ];
  const box = $("message");
  let lastResult;
  function inputState() {
    const hasText = box.value.trim().length > 0;
    $("length").textContent = box.value.length + " / 800";
    $("form").querySelector(".primary").disabled = !hasText;
    document.querySelectorAll("#samples button").forEach((b, i) => {
      b.setAttribute("aria-pressed", String(box.value === samples[i][1]));
    });
    return hasText;
  }
  function pending() {
    const hasText = inputState(); lastResult = null;
    pill("بانتظار التحليل","neutral");
    $("result").innerHTML = '<p class="empty">' + (hasText ? "الرسالة الحالية جاهزة للتحليل." : "تظهر النتيجة هنا بعد تحليل رسالة أو اختيار مثال.") + "</p>";
    $("announcement").textContent = "";
  }
  function showSource(id) {
    const item = M.faq.find(f => f.id === id);
    if (!item) return;
    $("source-body").innerHTML = sourceMarkup(item);
    const d = $("source-dialog");
    if (!d.open) d.showModal();
  }
  function sourceMarkup(item) {
    return '<div class="guide-meta"><bdi class="guide-id">' + esc(item.id) + '</bdi><span>' + esc(M.names[item.topic]) + '</span></div><h3>' + esc(item.ar) + '</h3><p>' + esc(item.answer_ar) + '</p><p dir="ltr" lang="en">' + esc(item.answer_en) + "</p>" +
      (item.id === "B01" ? '<p class="note">تُخصّص مسودة الحجز حسب نوع التصوير والمدينة والتاريخ المذكور في الرسالة.</p>' : "");
  }
  async function copyDraft() {
    if (!lastResult) return;
    const button = $("copy-draft"), draft = lastResult.draft;
    let success = false;
    try {
      await navigator.clipboard.writeText(draft);
      success = true;
    } catch {
      const el = document.createElement("textarea"); el.value = draft;
      el.style.position = "fixed"; el.style.opacity = "0";
      document.body.append(el); el.select();
      try { success = document.execCommand("copy"); } finally { el.remove(); button.focus(); }
    }
    button.textContent = success ? "تم النسخ ✓" : "النسخ اليدوي متاح";
    $("announcement").textContent = button.textContent;
  }
  function analyze() {
    if (!inputState()) { pending(); return; }
    const raw = box.value, r = E.classify(raw), lang = E.language(raw);
    const slots = E.extract(raw), draft = E.draft(r, slots, lang.reply);
    lastResult = {draft};
    const answer = r.route === "answer";
    const title = r.route === "clarify_topic" ? "الطلب يحتاج توضيحًا" : M.names[r.topic];
    const badge = {answer:"مسوّدة للمراجعة", clarify_topic:"طلب توضيح", clarify_faq:"تفاصيل ناقصة", outside:"إحالة للفريق"};
    pill(badge[r.route], answer ? "" : "review");
    const fields = [["اللغة",lang.label]];
    if (r.route !== "outside") {
      for (const [key, label] of [["service","التصوير"],["city","المدينة"],["day","الموعد"]]) {
        if (slots[key]) fields.push([label, slots[key].ar]);
      }
    }
    const facts = fields.map(([k,v]) => '<span>' + esc(k) + ' <strong>' + esc(v) + "</strong></span>").join("");
    const source = answer ? '<button type="button" class="text-link" id="source">مرجع الدليل <bdi>' + esc(r.faq.id) + '</bdi> ↗</button>' : '<span class="info-label">صياغة توضيحية للفريق</span>';
    $("result").innerHTML = '<h3 class="result-title">' + esc(title) + '</h3><div class="fields">' + facts +
      '</div><div class="reply-block"><div class="reply-label">الردّ المقترح' + (answer ? " · " + esc(r.faq.ar) : "") +
      '</div><p class="draft" dir="' + (lang.reply === "en" ? "ltr" : "rtl") + '" lang="' + lang.reply + '">' + esc(draft) +
      '</p></div><div class="reply-tools"><button type="button" id="copy-draft" class="copy">نسخ الردّ</button>' + source +
      '</div><details class="trace"><summary>كيف قُرئت الرسالة؟</summary><dl><dt>بعد حجب بيانات التواصل</dt><dd dir="auto">' + esc(r.masked) +
      '</dd><dt>النص بعد التوحيد</dt><dd dir="auto">' + esc(r.normalized || "—") +
      '</dd><dt>فارق أعلى تصنيفين</dt><dd><bdi class="mono">' + r.gap.toFixed(2) + '</bdi> نقطة في دالة القرار. حدّ طلب التوضيح <bdi class="mono">' + M.threshold.toFixed(2) +
      '</bdi>.</dd><dt>تفاصيل الجلسة</dt><dd>تُستخرج بمطابقة عبارات صريحة في النص.</dd></dl></details>';
    $("copy-draft").onclick = copyDraft;
    if (answer) $("source").onclick = () => showSource(r.faq.id);
    $("announcement").textContent = title + "، " + badge[r.route];
  }
  for (const [label, text] of samples) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = label;
    b.onclick = () => { box.value = text; analyze(); }; $("samples").append(b);
  }
  $("form").onsubmit = event => { event.preventDefault(); analyze(); };
  $("clear").onclick = () => { box.value = ""; pending(); box.focus(); };
  box.oninput = pending;
  box.onkeydown = event => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); analyze(); } };
  $("close-dialog").onclick = () => $("source-dialog").close();
  $("source-dialog").onclick = e => { if (e.target === e.currentTarget) e.currentTarget.close(); };

  function bar(label, value, detail, tone = "") {
    return '<div class="bar-item"><div class="metric-line"><span>' + esc(label) + ' <small>' + esc(detail) +
      '</small></span><bdi class="pct">' + pct(value) + '</bdi></div><div class="track" aria-hidden="true"><div class="fill ' +
      tone + '" style="width:' + 100*value + '%"></div></div></div>';
  }
  function renderClassScores() {
    const key = $("score-choice").value;
    $("class-chart").innerHTML = R.per_class.map(x => bar(M.names[x.key], x[key], "· " + "عدد الرسائل " + x.n)).join("");
    const notes = {f1:"يجمع F1 بين دقّة التوقع واسترجاع رسائل الفئة الصحيحة.", recall:"من الرسائل التابعة للفئة، كم رسالة اكتشفها المصنّف؟", precision:"من الرسائل التي توقّعها المصنّف ضمن الفئة، كم رسالة تنتمي إليها؟"};
    $("score-note").textContent = notes[key];
  }
  function renderSlices() {
    const key = $("slice-choice").value;
    const name = x => ({ar:"العربية",en:"الإنجليزية",English:"الإنجليزية"})[x] || x;
    $("slice-chart").innerHTML = R.slices[key].map(x => bar(name(x.name), x.accuracy, "· " + "عدد الرسائل " + x.n,"gold")).join("");
    $("slice-note").textContent = {language:"النسبة هي عدد التوقعات الصحيحة مقسومًا على عدد رسائل الشريحة في الاختبار.",dialect:"اللهجات وسوم أُضيفت عند كتابة الأمثلة. بعض الشرائح فيها رسالتان فقط.",length:"الرسالة القصيرة تتكوّن من ست كلمات أو أقل بعد توحيد الكتابة."}[key];
  }
  function matrixDetail(row, col) {
    const a = R.labels[row], p = R.labels[col];
    const subset = R.test_rows.filter(item => item.topic === a && item.prediction === p);
    const list = subset.map(item => '<li dir="auto">' + esc(item.masked_text) + '</li>').join("");
    $("matrix-detail").innerHTML = '<b>الصحيح</b> ' + esc(M.names[a]) + ' · <b>التوقّع</b> ' + esc(M.names[p]) +
      (list ? '<ul>' + list + '</ul>' : '<p>ما فيه رسائل اختبار في هذه الخانة.</p>');
    $("matrix").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.r === row && +b.dataset.c === col)));
  }
  function renderMatrix() {
    const high = Math.max(...R.confusion.flat());
    let html = '<table class="matrix"><caption class="sr">عدد رسائل الاختبار حسب الصحيح والمتوقّع</caption><thead><tr><th scope="col">صحيح ↓<br>توقّع ←</th>';
    for (const k of R.labels) html += '<th scope="col">' + esc(M.names[k]) + '</th>';
    html += '</tr></thead><tbody>';
    R.confusion.forEach((cells, row) => {
      html += '<tr><th scope="row">' + esc(M.names[R.labels[row]]) + '</th>';
      cells.forEach((n, col) => {
        const frac = n/high, shade = n ? (95-72*frac) : 95;
        const color = shade < 47 ? "white" : "#39222a";
        const style = "background:hsl(348 24% " + shade + "%);color:" + color;
        const label = M.names[R.labels[row]] + "، التوقّع " + M.names[R.labels[col]] + "، " + n + " رسالة";
        html += '<td><button class="cell" type="button" aria-pressed="false" aria-label="' + esc(label) + '" data-r="' + row + '" data-c="' + col + '" style="' + style + '">' + n + '</button></td>';
      });
      html += '</tr>';
    });
    $("matrix").innerHTML = html + '</tbody></table>';
    $("matrix").onclick = e => { const b = e.target.closest(".cell"); if (b) matrixDetail(+b.dataset.r, +b.dataset.c); };
    const mistake = R.test_rows.find(x => x.topic !== x.prediction);
    if (mistake) matrixDetail(R.labels.indexOf(mistake.topic), R.labels.indexOf(mistake.prediction));
  }
  function fillEvaluation() {
    const split = R.split;
    const stats = [
      ["دقّة التصنيف",pct(R.accuracy),R.correct + " توقّعًا صحيحًا من " + split.test.messages],
      ["متوسط F1 للفئات",R.macro_f1.toFixed(3),"وزن متساوٍ للفئات الخمس"],
      ["فاصل الدقّة 95٪",R.accuracy_ci.map(pct).join(" – "),"إعادة أخذ العينة على مستوى العميل"],
      ["رسائل الاختبار",String(split.test.messages),"من " + split.test.customers + " عميلًا افتراضيًا"]
    ];
    $("metrics-intro").innerHTML = stats.map(([k,v,d]) => '<div class="stat"><span>' + k + '</span><bdi dir="ltr" class="metric-num">' + v + '</bdi><small>' + d + '</small></div>').join("");
    const q = R.retrieval;
    $("retrieval").innerHTML = '<p class="note">قورِن الترتيب بمرجع صحيح لكل واحد من ' + q.n + ' سؤالًا مستقلًا. تعرض الأعمدة نسبة ظهور المرجع الصحيح في المركز الأول بين ثمانية مراجع.</p>' +
      bar("البحث المباشر بـ MiniLM + FAISS",q.teacher.top1,"مرحلة التحضير") + bar("النموذج الخفيف",q.student.top1,"يعمل في الموقع","gold") +
      '<p class="note">ظهر المرجع الصحيح ضمن أول ثلاثة خيارات للنموذج الخفيف في <bdi>' + pct(q.student.recall3) + '</bdi> من الأسئلة. يضيّق الديمو الخيارات بعد ذلك حسب نوع الطلب.</p>';
    $("method-body").innerHTML = '<p>استخدمنا ' + R.count + ' رسالة من ' + R.customers + ' عملاء افتراضيين. وزّعناهم حسب العميل مع تمثيل اللهجات في كل جزء. للتدريب ' + split.train.messages + ' رسالة، ولضبط حدّ القرار ' + split.validation.messages + '، وللاختبار ' + split.test.messages + '. عدد العملاء المشتركين بين الأجزاء صفر.</p>' +
      '<p>مصنّف <bdi>TF-IDF + LinearSVC</bdi> يقرأ مقاطع من 3 إلى 5 أحرف. حقّق خط الأساس المبني على الكلمات <bdi>Macro-F1 ' + R.word_f1.toFixed(3) + '</bdi> على الرسائل نفسها. يقيس الرسم التصنيف قبل طلب التوضيح أو الإحالة.</p>' +
      '<p>تعلّم نموذج <bdi>Ridge</bdi> ترتيب مراجع الدليل من درجات <bdi>MiniLM + FAISS</bdi> المحسوبة مسبقًا. من رسائل الاختبار اقترح الديمو ردًا من الدليل لـ ' + R.accepted + ' رسالة، وصحّ نوع الطلب لـ ' + R.accepted_correct + ' منها. قِيس اختيار المرجع نفسه في اختبار الاسترجاع المستقل.</p>' +
      '<p>البيانات أمثلة تعليمية مكتوبة، وتشمل العربية بلهجات مختلفة والإنجليزية. يصف فاصل الدقّة تباين هذه العينة باستخدام 2000 إعادة سحب للعملاء. أسعار الخدمات والمواعيد الفعلية يراجعها فريق التصوير.</p>';
    const models = [["TF-IDF بالكلمات",R.word_f1,"خط الأساس"],["TF-IDF بالأحرف",R.macro_f1,"المصنّف المستخدم في الموقع"]];
    if (typeof R.camelbert_f1 === "number") models.push(["CAMeLBERT-Mix",R.camelbert_f1,"بعد الضبط الدقيق"]);
    $("comparison").innerHTML = '<p class="note">قَسنا Macro-F1 على نفس التقسيم. تمثيل الأحرف يتيح تنفيذ التصنيف في المتصفح من ملف أوزان صغير.</p><div class="compare-bars">' +
      models.map(([name,score,kind]) => bar(name,score,kind)).join("") + '</div>';
    renderClassScores(); renderSlices(); renderMatrix();
  }
  $("score-choice").onchange = renderClassScores; $("slice-choice").onchange = renderSlices;
  for (const k of Object.keys(M.names).filter(k => k !== "outside")) $("guide-filter").add(new Option(M.names[k],k));
  function renderGuide() {
    const selected = $("guide-filter").value;
    $("guide-list").innerHTML = M.faq.filter(f => selected === "all" || f.topic === selected).map(item =>
      '<article class="guide-card"><div class="guide-meta"><bdi class="guide-id">' + esc(item.id) + '</bdi> · ' + esc(M.names[item.topic]) +
      '</div><h2>' + esc(item.ar) + '</h2><p>' + esc(item.answer_ar) + '</p><details><summary>الصياغة الإنجليزية</summary><p lang="en" dir="ltr">' + esc(item.answer_en) + '</p></details></article>').join("");
  }
  $("guide-filter").onchange = renderGuide;
  let evaluated = false;
  function navigate() {
    const id = ["studio","evaluation","guide"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "studio";
    document.querySelectorAll(".page").forEach(el => {el.hidden = el.id !== id;});
    document.querySelectorAll("nav a").forEach(a => {if (a.dataset.page === id) a.setAttribute("aria-current","page"); else a.removeAttribute("aria-current");});
    if (id === "evaluation" && !evaluated) {fillEvaluation(); evaluated = true;}
    if (id === "guide") renderGuide();
    document.title = {studio:"مكتب الاستفسارات",evaluation:"أداء النموذج",guide:"دليل الردود"}[id] + " | LensCent";
  }
  window.addEventListener("hashchange", () => {navigate(); window.scrollTo(0,0);});
  box.value = samples[0][1]; analyze(); navigate();
})();
