/* The two linear heads share exactly the char_wb TF-IDF representation from train.py. */
(function () {
  "use strict";
  const model = globalThis.LensModel;
  const translate = (text, from, to) => text.replace(new RegExp("[" + from + "]", "g"), c => to[from.indexOf(c)]);
  function mask(text) {
    let value = translate(text.normalize("NFKC"), "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789");
    value = value.replace(/[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/g, "[EMAIL]");
    return value.replace(/(?<![0-9])(?:\+?966[\s().-]*0?|00966[\s().-]*0?|0)5(?:[\s().-]*[0-9]){8}(?![0-9])/g, "[PHONE]");
  }
  function clean(text) {
    let value = mask(text).replace(/\[(?:PHONE|EMAIL)\]/g, " ").toLowerCase();
    value = translate(value, "أإآٱىة", "اااايه").replace(/[\u0610-\u061a\u064b-\u065f\u0670\u0640]/g, "");
    // Keep ordinary letter pairs and reduce expressive Arabic elongation.
    value = value.replace(/([\u0621-\u064a])\1{2,}/g, "$1");
    return (value.match(/[a-z0-9\u0621-\u064a]+/g) || []).join(" ");
  }
  function transform(text) {
    const counts = new Map();
    for (const word of text.split(" ").filter(Boolean)) {
      const padded = " " + word + " ";
      for (let n = 3; n <= 5; n++) {
        for (let i = 0; i <= Math.max(0, padded.length - n); i++) {
          const gram = padded.slice(i, i + n);
          if (Object.hasOwn(model.features, gram)) counts.set(gram, (counts.get(gram) || 0) + 1);
        }
        if (n >= padded.length) break;
      }
    }
    const weighted = Array.from(counts, ([gram, count]) => {
      const feature = model.features[gram];
      return [feature, (1 + Math.log(count)) * feature[0]];
    });
    const norm = Math.sqrt(weighted.reduce((sum, [, value]) => sum + value * value, 0));
    return weighted.map(([feature, value]) => [feature, value / norm]);
  }
  function classify(raw) {
    const normalized = clean(raw);
    const features = transform(normalized);
    const scores = model.bias.slice();
    for (const [row, weight] of features) {
      for (let j = 0; j < scores.length; j++) scores[j] += row[j + 1] * weight;
    }
    const order = model.classes.map((_, i) => i).sort((a, b) => scores[b] - scores[a]);
    const topic = model.classes[order[0]];
    const gap = scores[order[0]] - scores[order[1]];
    const offset = model.classes.length;
    const allFaq = model.faq.map((item, i) => ({item, score:scores[offset + i]}))
      .sort((a, b) => b.score - a.score);
    const choices = allFaq.filter(x => x.item.topic === topic);
    let route = "answer";
    if (!features.length || gap < model.threshold) route = "clarify_topic";
    else if (topic === "outside") route = "outside";
    else if (choices[0].score - choices[1].score < model.faqGap) route = "clarify_faq";
    return {topic, route, gap, normalized, masked:mask(raw), faq:route === "answer" ? choices[0].item : null,
      ranking:allFaq.map(x => x.item.id), scores:order.map(i => [model.classes[i], scores[i]])};
  }

  // These are explicit, editable dictionaries for common details. Dialect is an evaluation label only.
  const details = {
    service:[
      ["تصوير تخرّج","graduation photography",/تخرج|خريج|graduat/],
      ["تصوير منتجات","product photography",/منتج|عطور|منيو|اطباق|product|perfume|menu/],
      ["جلسة عائلية","a family session",/عائل|عايل|اسري|family/],
      ["تصوير زفاف","wedding photography",/زفاف|عرس|فرح|عروس|wedding|bridal/],
      ["تصوير خطوبة","engagement photography",/خطوب|ملكه|engagement/],
      ["تغطية فعالية","event coverage",/فعالي|افتتاح|مؤتمر|موتمر|corporate|event|conference|opening/],
      ["فوتوبوث","a photo booth",/فوتو ?بوث|photo ?booth/],
      ["جلسة بورتريه","a portrait session",/بورتري|portrait|headshot/],
      ["تصوير مواليد","newborn photography",/مولود|مواليد|newborn/]
    ],
    city:[
      ["الرياض","Riyadh",/الرياض|\briyadh\b/],["جدة","Jeddah",/(?:^| )[بوف]?جده(?: |$)|\bjeddah\b/],
      ["الخبر","Khobar",/الخبر|\bkhobar\b/],["الدمام","Dammam",/الدمام|\bdammam\b/],
      ["مكة","Makkah",/(?:^| )[بوف]?مكه(?: |$)|\b(?:makkah|mecca)\b/]
    ],
    day:[
      ["الخميس","Thursday",/الخميس|\bthursday\b/],["الجمعة","Friday",/الجمعه|\bfriday\b/],
      ["السبت","Saturday",/السبت|\bsaturday\b/],["الأحد","Sunday",/الاحد|\bsunday\b/],
      ["الاثنين","Monday",/الاثنين|\bmonday\b/],["الثلاثاء","Tuesday",/الثلاثاء|\btuesday\b/],
      ["الأربعاء","Wednesday",/الاربعاء|\bwednesday\b/],["غدًا","tomorrow",/بكر[ها]|باجر|غدا|\btomorrow\b/],
      ["الأسبوع القادم","next week",/الاسبوع (?:الجاي|القادم)|\bnext week\b/]
    ]
  };
  function extract(raw) {
    const normalized = clean(raw);
    const result = {};
    for (const [field, rules] of Object.entries(details)) {
      const match = rules.find(([, , pattern]) => pattern.test(normalized));
      if (match) result[field] = {ar:match[0], en:match[1]};
    }
    const date = mask(raw).match(/\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b/);
    if (date && !result.day) result.day = {ar:date[0], en:date[0]};
    return result;
  }
  function language(raw) {
    const words = clean(raw).split(" ");
    const ar = words.filter(w => /[\u0621-\u064a]/.test(w)).length;
    const en = words.filter(w => /[a-z]/.test(w)).length;
    return {reply:en > ar ? "en" : "ar", label:ar && en > 1 ? "عربي / English" : en > ar ? "English" : ar ? "العربية" : "غير محددة"};
  }
  const clarify = {
    session_booking:["هل الطلب حجز جلسة جديدة أو تغيير موعد حجز قائم؟","Are you booking a new session or changing an existing date?"],
    package_pricing:["هل تود معرفة سعر الباقة أو تكلفة إضافة مثل ساعة تصوير أو صور مطبوعة؟","Are you asking about a package price or the cost of an add-on?"],
    edit_request:["هل التعديل المطلوب في اللون والإضاءة أو في قص الصورة وإزالة عنصر منها؟","Would you like a colour or lighting adjustment, a crop, or an object removed?"],
    gallery_access:["هل المشكلة في فتح رابط المعرض أو في تنزيل الصور بعد فتحه؟","Is the problem opening the gallery or downloading photos after it opens?"]
  };
  function draft(result, slots, lang) {
    const en = lang === "en";
    if (result.route === "outside") return en ? "LensCent can help with photography bookings, packages, edits and galleries. Which photography service can we help you with?" : "نساعدك في حجوزات التصوير والباقات وتعديل الصور والوصول للمعرض. أي خدمة تصوير تحتاج؟";
    if (result.route === "clarify_topic") return en ? "Could you tell us a little more? Is this about a booking, a package price, a photo edit or your gallery?" : "ممكن توضح طلبك أكثر؟ هل تقصد حجز جلسة، أو سعر باقة، أو تعديل صورة، أو الوصول للمعرض؟";
    if (result.route === "clarify_faq") return clarify[result.topic][en ? 1 : 0];
    if (result.faq.id !== "B01") return result.faq["answer_" + lang];
    const names = {service:["نوع التصوير","the type of shoot"], city:["المدينة","the city"], day:["التاريخ المناسب","your preferred date"]};
    const missing = Object.keys(names).filter(k => !slots[k]).map(k => names[k][en ? 1 : 0]);
    const known = [slots.service?.[lang], slots.city && (en ? "in " : "في ") + slots.city[lang],
      slots.day && "· " + slots.day[lang]].filter(Boolean).join(" ");
    if (en) return (known ? "Thanks for the details (" + known + "). " : "We’d love to plan your shoot. ") +
      (missing.length ? "The team still needs " + missing.join(" and ") + " to check availability." : "The team can now check availability for your preferred date.");
    return (known ? "وصلتنا تفاصيل طلبك (" + known + "). " : "يسعدنا تصويرك! ") +
      (missing.length ? "نحتاج " + missing.join(" و") + " عشان يراجع الفريق المواعيد المتاحة." : "بيراجع الفريق التوفر في الموعد المطلوب ويرجع لك بخيارات الجلسة.");
  }
  globalThis.LensEngine = {clean, mask, classify, extract, language, draft};
}());
