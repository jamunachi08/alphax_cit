/* Arabic strings are authored, not machine-translated, and follow the wording
   already used in alphax_cit/translations/ar.csv so the app and the desk agree. */
(function (w) {
  const AR = {
    signin_title: "سجّل الدخول لبدء الوردية",
    signin_help: "يتم تنزيل رحلاتك مرة واحدة وتبقى متاحة بدون شبكة.",
    site_url: "عنوان الموقع",
    user: "المستخدم",
    password: "كلمة المرور",
    signin: "تسجيل الدخول",
    try_demo: "فتح وردية تجريبية",
    trips: "الرحلات",
    outbox: "الصادر",
    settings: "الإعدادات",
    no_trips: "لا توجد رحلات مسندة",
    no_trips_help: "حدّث القائمة عند توفر الشبكة، أو اطلب من غرفة العمليات إسناد رحلة.",
    stops: "المحطات",
    declared: "القيمة المعلنة",
    vault: "الخزنة",
    pretrip: "فحوصات ما قبل الرحلة",
    route: "خط السير",
    panic: "استغاثة",
    bags: "أكياس",
    pod_title: "إثبات التسليم",
    bags_seals: "الأكياس والأختام",
    add_bag: "إضافة كيس",
    receiver: "المستلم",
    receiver_name: "الاسم",
    receiver_id: "رقم الهوية",
    signature: "التوقيع",
    clear: "مسح",
    photos: "الصور",
    add_photo: "إضافة صورة",
    cancel: "إلغاء",
    confirm_pod: "تأكيد وإضافة للصادر",
    report_incident: "تسجيل حادثة",
    category: "التصنيف",
    severity: "الخطورة",
    what_happened: "ماذا حدث",
    queue_report: "إضافة البلاغ للصادر",
    outbox_clear: "تمت مزامنة كل شيء",
    outbox_clear_help: "ما تسجّله بدون شبكة ينتظر هنا حتى يعود الاتصال.",
    shift: "الوردية",
    employee: "الموظف",
    device: "الجهاز",
    last_pull: "آخر تنزيل",
    direction: "اتجاه القراءة",
    auto: "تلقائي",
    download_again: "تنزيل الرحلات مرة أخرى",
    end_shift: "إنهاء الوردية وتسجيل الخروج",
    wipe_note: "تسجيل الخروج يمسح الرحلات المخزّنة. ما تبقى في الصادر يُرسل أولاً.",
    online: "متصل",
    offline: "غير متصل",
    syncing: "جاري المزامنة",
    sync_now: "مزامنة الآن",
    start_trip: "بدء الرحلة",
    complete_trip: "إنهاء الرحلة وتسليم الخزنة",
    trip_closed: "الرحلة مغلقة",
    arrive: "تسجيل الوصول",
    collect: "تأكيد الاستلام",
    deliver: "تأكيد التسليم",
    report: "تسجيل حادثة",
    queued: "في الانتظار",
    sending: "جاري الإرسال",
    quarantined: "مرفوض",
    seal_no: "رقم الختم",
    amount: "المبلغ",
    seal_intact: "الختم سليم",
    authorised_receivers: "المخوّلون بالاستلام",
    access: "إجراءات الدخول",
    instructions: "تعليمات خاصة",
    window: "نافذة الخدمة",
    need_name: "أدخل اسم المستلم.",
    need_sig: "التوقيع مطلوب.",
    queued_ok: "تمت الإضافة للصادر.",
    panic_confirm: "إرسال إشارة استغاثة؟",
    panic_body: "سيتم تنبيه غرفة العمليات فوراً مع موقعك.",
    send: "إرسال",
    logout_confirm: "إنهاء الوردية؟",
    bad_login: "تعذر تسجيل الدخول. تحقق من العنوان واسم المستخدم وكلمة المرور.",
    device_blocked: "هذا الجهاز غير مسجّل. راجع غرفة العمليات.",
    no_conn: "لا يوجد اتصال. سيتم الإرسال لاحقاً."
  };

  let lang = localStorage.getItem("cit.lang") || "en";
  let dirPref = localStorage.getItem("cit.dir") || "auto";

  function t(k, fallback) {
    if (lang === "ar" && AR[k]) return AR[k];
    return fallback !== undefined ? fallback : k;
  }

  function resolveDir() {
    if (dirPref === "ltr" || dirPref === "rtl") return dirPref;
    return lang === "ar" ? "rtl" : "ltr";
  }

  function apply(root) {
    (root || document).querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = t(el.dataset.i18n, el.textContent);
    });
    document.documentElement.lang = lang;
    document.documentElement.dir = resolveDir();
    document.body.dir = resolveDir();
  }

  w.I18N = {
    get lang() { return lang; },
    get dirPref() { return dirPref; },
    setLang(l) { lang = l; localStorage.setItem("cit.lang", l); apply(); },
    toggle() { this.setLang(lang === "ar" ? "en" : "ar"); },
    setDir(d) { dirPref = d; localStorage.setItem("cit.dir", d); apply(); },
    t: t,
    apply: apply,
    dir: resolveDir
  };
})(window);
