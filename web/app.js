const state = {
  role: "gate",
  start: "2025-04-01",
  end: "2025-04-30",
  station: "YE-01",
  day: "2025-04-15",
};

const charts = {};
let stations = [];
let metrics = null;

let lang = "hy";
try {
  const saved = localStorage.getItem("voltsynch-lang");
  if (saved === "ru") localStorage.setItem("voltsynch-lang", "hy");
  if (saved === "en") lang = "en";
} catch (_err) {
  /* storage unavailable */
}

const ink = "#1d2430";
const muted = "#5e675c";
const sun = "#e39b2b";
const leaf = "#1f6b4a";
const blue = "#2f5f98";
const fontFamily = '"Noto Sans Armenian", "Noto Sans", "Segoe UI", sans-serif';

const PLACES = {
  "Ереван": "Երևան",
  "Ширак": "Շիրակ",
  "Гюмри": "Գյումրի",
  "Лори": "Լոռի",
  "Ванадзор": "Վանաձոր",
  "Гегаркуник": "Գեղարքունիք",
  "Севан": "Սևան",
  "Сюник": "Սյունիք",
  "Капан": "Կապան",
};

const COPY = {
  hy: {
    docTitle: "VoltSynch — արևային էներգիայի բորսա",
    sub: "արևային էներգիայի բորսա",
    "nav.solar": "Արևային կայան",
    "nav.grid": "Էլեկտրացանց",
    "nav.exchange": "Համակարգող",
    "nav.present": "Ներկայացում",
    "nav.back": "Բոլոր մուտքերը",
    "gate.lede": "Ընտրեք կողմը։",
    "gate.grid": "Էլեկտրացանց",
    "gate.gridText": "Որքան էներգիա չի մտել ցանց, երբ այն պետք չէր, և որքան են վերադարձրել մարտկոցները պիկին։",
    "gate.solar": "Արևային կայան",
    "gate.solarText": "Վաճառքը, եկամուտը և լրացուցիչ գումարը մարտկոցից։",
    "gate.exchange": "Համակարգող",
    "gate.exchangeText": "Բոլոր կայանները միասին և ծառայության 10%-ը։",
    "preset.april": "Ապրիլ 2025",
    "preset.july": "Հուլիս 2025",
    "preset.year": "2025",
    "price.note": "Գումարները սցենարային գին են. ՀԾԿՀ սակագինը այստեղ չի կիրառվում։",
    "ml.title": "Ինչ է անում մոդելը",
    "ml.q": "Պատասխանում է մեկ հարցի. քանի կիլովատ-ժամ կարտադրի կայանը մոտակա ժամերին։",
    "ml.not": "Գինը չի դնում։ Գնման ժամն ու սակագինը հայտարարում է ցանցը։",
    "ml.use": "Այդ թվով երևում է, արդյոք մարտկոցը կհասցնի լիցքավորվել մինչև վաճառքի ժամը։ Գրաֆիկում հոծ գիծը փաստն է, կետագիծը՝ կանխատեսումը։",
    "ml.global": "2025 թվականի ստուգման վրա, որը մոդելը չի տեսել, լուսավոր ժամերին սխալը {mae} կՎտ·ժ է։ Առանց մոդելի նույն ամիսը և նույն ժամը սխալվում են {profile} կՎտ·ժ-ով։",
    "pill.loading": "",
    "pill.ready": "",
    "filter.from": "Սկսած",
    "filter.to": "Մինչև",
    "filter.station": "Կայան",
    "filter.day": "Կանխատեսման օր",
    "s.sold": "Վաճառվել է ցանցին",
    "s.revenue": "Եկամուտ կայանի",
    "s.extra": "Լրացուցիչ՝ մարտկոցից",
    "s.delay": "Մինչև վաճառք",
    "solar.lede": "{id}, {city}։ Վահանակ՝ {pv} կՎտ, մարտկոց՝ {battery} կՎտ·ժ։ Լրացուցիչ եկամուտը մարտկոցից է։",
    "solar.extraPct": "{pct}՝ առանց մարտկոցի համեմատ",
    "solar.dailyTitle": "Վաճառք և լրացուցիչ եկամուտ ըստ օրվա",
    "solar.dailyNote": "Կանաչ սյունը՝ լրացուցիչ դրամը մարտկոցի շնորհիվ։ Դեղին գիծը՝ այդ օրը վաճառված էներգիան։",
    "solar.pvTitle": "Արտադրության կանխատեսում",
    "solar.battTitle": "Մարտկոցից ցանց",
    "solar.battNote": "Կանաչը՝ ինչ մարտկոցն իրականում տվել է ցանց։ Կապույտը՝ ինչ մոդելն սպասել է կանխատեսված արտադրությունից և հայտարարված գնից։",
    "chart.extra": "Լրացուցիչ եկամուտ, դրամ",
    "chart.sold": "Վաճառված, կՎտ·ժ",
    "unit.dram": "դրամ",
    "unit.kwh": "կՎտ·ժ",
    "unit.mwh": "ՄՎտ·ժ",
    "unit.kw": "կՎտ",
    "unit.hour": "ժամ",
    "unit.kwhPeriod": "կՎտ·ժ ամբողջ ժամանակահատվածում",
    "hours": "{value} ժ",
    "chart.actual": "Փաստ",
    "chart.forecast": "Կանխատեսում",
    "chart.battActual": "Փաստ՝ մարտկոցից",
    "chart.battPred": "Կանխատեսում",
    "forecast.note": "Այս օրվա արդյունքը. սխալը {mae} կՎտ·ժ է։ Մարտկոցից ցանց սպասվել է {pred}, եղել է {actual}։ {train}",
    "forecast.seen": "Այս օրը եղել է ուսուցման մեջ։",
    "forecast.unseen": "Այս օրը մոդելը ուսուցման ժամանակ չի տեսել։",
    "grid.lede": "{period}. Ժամը\u00a010:00–15:00 ցանց չի մտել {held}։ Ժամը\u00a017:00–21:00 մարտկոցները տվել են {eve}։",
    "grid.markNoon": "12:00 · չի մտել {value}",
    "grid.markEve": "18:00 · մարտկոցից {value}",
    "g.refused": "Չի ընդունվել, երբ պետք չէր",
    "g.battery": "Եկել է մարտկոցներից",
    "g.bought": "Գնվել է կայաններից",
    "g.delay": "Մինչև վաճառք",
    "grid.hourTitle": "Արևային էներգիան ցանցում, ըստ ժամի",
    "grid.hourNote": "Դեղին շերտը կեսօրն է. ավելցուկը մնում է մարտկոցում։ Կանաչ շերտը պիկն է. մարտկոցը այդ էներգիան տալիս է ցանց։",
    "grid.shift": "Ժամը 10:00–15:00 առանց մարտկոցի կմտներ {would}։ Մարտկոցով ցանց չի մտել {held}։ Ժամը 17:00–21:00 մարտկոցները տվել են {eve}։",
    "chart.with": "Մարտկոցով մտել է ցանց",
    "chart.without": "Առանց մարտկոցի կմտներ ցանց",
    "chart.direct": "Վահանակից, երբ ցանցը գնում է",
    "chart.fromBatt": "Մարտկոցից, երբ ցանցը գնում է",
    "grid.dailyTitle": "Մարտկոցներից՝ ըստ օրվա",
    "grid.dailyNote": "Յուրաքանչյուր սյունը էներգիան է, որ մարտկոցները տվել են ցանց այն ժամերին, երբ ցանցը գնում էր։",
    "chart.battDaily": "Մարտկոցներից գնման ժամին, կՎտ·ժ",
    "grid.modelTitle": "Ընտրված օրվա մոդել",
    "grid.modelNote": "Մոդելը կանխատեսում է արտադրությունը, ապա հաշվում է, թե որքան կգա մարտկոցներից։ Կանաչը փաստն է, կապույտը՝ կանխատեսումը։ Այս օրը սպասվել է {pred}, եղել է {actual}։ {train}",
    "forecast.seenShort": "Օրը եղել է ուսուցման մեջ։",
    "forecast.unseenShort": "Օրը ուսուցման մեջ չի եղել։",
    "exchange.lede": "{period}. 30 կայան միասին. լրացուցիչը մարտկոցներից՝ {extra}, ծառայության 10%-ը՝ {fee}։",
    "exchange.regionNote": "Լրացուցիչ դրամը՝ մեկ կՎտ վահանակի հաշվով, որպեսզի մարզերը համեմատելի լինեն։",
    "chart.perKw": "Լրացուցիչ, դրամ/կՎտ",
    "e.revenue": "Բոլոր կայանների եկամուտ",
    "e.extra": "Լրացուցիչ՝ մարտկոցներից",
    "exchange.dailyTitle": "Բոլոր կայանները միասին, ըստ օրվա",
    "exchange.dailyNote": "Կանաչ սյունը՝ լրացուցիչ դրամը բոլոր կայաններից։ Դեղին գիծը՝ այդ օրը վաճառված էներգիան։",
    "exchange.allTitle": "Յուրաքանչյուր կայան",
    "exchange.allNote": "Սյունը կայանի վաճառքն է ընտրված ժամանակահատվածում։ Միասին սա ամբողջ ցանցն է։",
    "th.total": "Բոլորը",
    "e.commission": "Միջնորդավճար, 10%",
    "e.sold": "Վաճառվել է ցանցին",
    "e.mae": "Մոդելի սխալ, ժամը 7–18",
    "e.maeNote": "առանց մոդելի սխալը՝ {profile} կՎտ·ժ, մոդելն ավելի ճշգրիտ է {lift}%-ով",
    "exchange.regionTitle": "Լրացուցիչ եկամուտ ըստ մարզի",
    "exchange.modelTitle": "Ինչպես է աշխատում մոդելը",
    "exchange.modelBlurb": "Մոդելը կանխատեսում է արտադրությունն ըստ եղանակի և վահանակի։ Ուսուցումը՝ մինչև {trainEnd}, ստուգումը՝ {testYear} թվականը։",
    "fact.train": "Ուսուցման ժամեր՝ {n}",
    "fact.test": "Ստուգման ժամեր՝ {n}",
    "fact.features": "Տվյալներ՝ ժամ, ամիս, տարվա օր, ջերմաստիճան, ամպամածություն, հզորություն, թեքություն, ազիմուտ, վահանակի գործակից, GHI, DNI, DHI",
    "fact.commission": "10% միջնորդավճարը հաշվվում է ցանցի վճարումից։ Արտադրության կանխատեսման մեջ այն չկա։",
    "exchange.stationsTitle": "Կայաններ",
    "exchange.tableNote": "Տողը բացում է այդ կայանի մուտքը։",
    "th.station": "Կայան",
    "th.region": "Մարզ",
    "th.kw": "կՎտ",
    "th.sold": "Վաճառք, կՎտ·ժ",
    "th.revenue": "Եկամուտ, դրամ",
    "th.extra": "Լրացուցիչ, դրամ",
    "th.pct": "Լրացուցիչ %",
    "th.battery": "Մարտկոցից, կՎտ·ժ",
    "exchange.forecastTitle": "Ընտրված կայանի կանխատեսում",
    "option": "{id} · {region} · {pv} կՎտ",
    "error.load": "Տվյալները բեռնել չհաջողվեց",
    "err.date": "Ամսաթիվը պետք է լինի ՏՏՏՏ-ԱԱ-ՕՕ ձևաչափով",
    "err.range": "Ժամանակահատվածի սկիզբը ավարտից ուշ է",
    "err.station": "Կայանը չի գտնվել",
    "err.telemetry": "Այս ամսաթվի համար չափում չկա",
    "err.weather": "Այս ամսաթվի համար եղանակը բավարար չէ",
    "err.price": "Այս ամսաթվի համար գնման գին չկա",
    "err.hours": "Այս օրվա մեջ 24 ժամ չկա",
    "err.period": "Այս ժամանակահատվածում տվյալ չկա",
  },
  en: {
    docTitle: "VoltSynch — solar energy exchange",
    sub: "solar energy exchange",
    "nav.solar": "Solar station",
    "nav.grid": "Power grid",
    "nav.exchange": "Coordinator",
    "nav.present": "Overview",
    "nav.back": "All entrances",
    "gate.lede": "Choose a side.",
    "gate.grid": "Power grid",
    "gate.gridText": "How much energy stayed out when it was not needed, and how much the batteries returned at the peak.",
    "gate.solar": "Solar station",
    "gate.solarText": "Sales, income, and the extra amount from the battery.",
    "gate.exchange": "Coordinator",
    "gate.exchangeText": "All stations together, and the service’s 10%.",
    "preset.april": "April 2025",
    "preset.july": "July 2025",
    "preset.year": "2025",
    "price.note": "These amounts use a scenario price. The regulator’s tariff is not applied here.",
    "ml.title": "What the model does",
    "ml.q": "It answers one question: how many kilowatt-hours this station will produce in the coming hours.",
    "ml.not": "It does not set the price. The grid publishes the hours it buys and the tariff.",
    "ml.use": "That forecast shows whether the battery will be charged in time for the sale. On the chart the solid line is what happened, the dashed line is the forecast.",
    "ml.global": "On the 2025 check, which the model had not seen, the daylight error is {mae} kWh. Without the model, the same month and the same hour miss by {profile} kWh.",
    "pill.loading": "",
    "pill.ready": "",
    "filter.from": "From",
    "filter.to": "to",
    "filter.station": "Station",
    "filter.day": "Forecast day",
    "s.sold": "Sold to the grid",
    "s.revenue": "Station income",
    "s.extra": "Extra from the battery",
    "s.delay": "Until the sale",
    "solar.lede": "{id}, {city}. Panel {pv} kW, battery {battery} kWh. The extra income comes from the battery.",
    "solar.extraPct": "{pct} compared with selling without a battery",
    "solar.dailyTitle": "Sales and extra income by day",
    "solar.dailyNote": "The green bar is the extra dram earned because of the battery. The yellow line is the energy sold that day.",
    "solar.pvTitle": "Generation forecast",
    "solar.battTitle": "From the battery to the grid",
    "solar.battNote": "Green is what the battery actually delivered. Blue is what the model expected from the forecast and the published price.",
    "chart.extra": "Extra income, dram",
    "chart.sold": "Sold, kWh",
    "unit.dram": "dram",
    "unit.kwh": "kWh",
    "unit.mwh": "MWh",
    "unit.kw": "kW",
    "unit.hour": "hour",
    "unit.kwhPeriod": "kWh over the whole period",
    "hours": "{value} h",
    "chart.actual": "Actual",
    "chart.forecast": "Forecast",
    "chart.battActual": "Actual from the battery",
    "chart.battPred": "Forecast",
    "forecast.note": "This day’s result: the error is {mae} kWh. From the battery the model expected {pred}; the actual delivery was {actual}. {train}",
    "forecast.seen": "This day was part of training.",
    "forecast.unseen": "The model had not seen this day during training.",
    "grid.lede": "{period}. From 10:00 to 15:00, {held} stayed out of the grid. From 17:00 to 21:00 the batteries delivered {eve}.",
    "grid.markNoon": "12:00 · kept out {value}",
    "grid.markEve": "18:00 · from batteries {value}",
    "g.refused": "Kept out when not needed",
    "g.battery": "Delivered from batteries",
    "g.bought": "Bought from stations",
    "g.delay": "Until the sale",
    "grid.hourTitle": "Solar energy in the grid, by hour",
    "grid.hourNote": "The yellow band is midday: the surplus stays in the batteries. The green band is the peak: the batteries deliver that energy to the grid.",
    "grid.shift": "From 10:00 to 15:00, {would} would have entered without batteries. With batteries, {held} stayed out. From 17:00 to 21:00 the batteries delivered {eve}.",
    "chart.with": "Entered with batteries",
    "chart.without": "Would enter with no battery",
    "chart.direct": "From the panel, when the grid is buying",
    "chart.fromBatt": "From the battery, when the grid is buying",
    "grid.dailyTitle": "From batteries, by day",
    "grid.dailyNote": "Each bar is energy the batteries delivered in hours when the grid was buying.",
    "chart.battDaily": "From batteries in buying hours, kWh",
    "grid.modelTitle": "Model for the selected day",
    "grid.modelNote": "The model forecasts generation, then calculates how much will come from the batteries. Green is what happened, blue is the forecast. This day it expected {pred}; the actual delivery was {actual}. {train}",
    "forecast.seenShort": "The day was part of training.",
    "forecast.unseenShort": "The day was not part of training.",
    "exchange.lede": "{period}. All 30 stations. Extra from the batteries: {extra}. The service’s 10%: {fee}.",
    "exchange.regionNote": "Extra dram per kilowatt of panel, so the regions can be compared.",
    "chart.perKw": "Extra, dram/kW",
    "e.revenue": "Income of all stations",
    "e.extra": "Extra from the batteries",
    "exchange.dailyTitle": "All stations together, by day",
    "exchange.dailyNote": "The green bar is extra dram from every station. The yellow line is the energy sold that day.",
    "exchange.allTitle": "Each station",
    "exchange.allNote": "Each bar is that station’s sales in the selected period. Together they are the whole fleet.",
    "th.total": "All",
    "e.commission": "Commission, 10%",
    "e.sold": "Sold to the grid",
    "e.mae": "Model error, hours 7–18",
    "e.maeNote": "without the model the error is {profile} kWh; the model is {lift}% more accurate",
    "exchange.regionTitle": "Extra income by region",
    "exchange.modelTitle": "What the model does",
    "exchange.modelBlurb": "The model forecasts generation from the weather and the panel. Training runs through {trainEnd}; the check is {testYear}.",
    "fact.train": "Hours in training: {n}",
    "fact.test": "Hours in the check: {n}",
    "fact.features": "Inputs: hour, month, day of year, temperature, cloud cover, power, tilt, azimuth, panel factor, GHI, DNI, DHI",
    "fact.commission": "The 10% commission is taken from what the grid pays. It is not part of the generation forecast.",
    "exchange.stationsTitle": "Stations",
    "exchange.tableNote": "A row opens that station’s entrance.",
    "th.station": "Station",
    "th.region": "Region",
    "th.kw": "kW",
    "th.sold": "Sold, kWh",
    "th.revenue": "Income, dram",
    "th.extra": "Extra, dram",
    "th.pct": "Extra %",
    "th.battery": "From battery, kWh",
    "exchange.forecastTitle": "Forecast for the selected station",
    "option": "{id} · {region} · {pv} kW",
    "error.load": "Could not load the data",
    "err.date": "The date must look like YYYY-MM-DD",
    "err.range": "The period starts after it ends",
    "err.station": "Station not found",
    "err.telemetry": "There is no measurement for this date",
    "err.weather": "Weather is missing for this date",
    "err.price": "There is no purchase price for this date",
    "err.hours": "This day does not have 24 hours",
    "err.period": "There is no data in this period",
  },
};

const API_ERRORS = {
  "Дата должна быть в формате ГГГГ-ММ-ДД": "err.date",
  "Начало периода позже конца": "err.range",
  "Станция не найдена": "err.station",
  "На эту дату нет телеметрии": "err.telemetry",
  "Для этой даты не хватает погоды": "err.weather",
  "На эту дату нет цены выкупа": "err.price",
  "В этих сутках не 24 часа": "err.hours",
  "В этом периоде нет данных": "err.period",
};

function t(key) {
  const pack = COPY[lang] || COPY.hy;
  return pack[key] || COPY.hy[key] || key;
}

function fill(key, vars) {
  return t(key).replace(/\{(\w+)\}/g, (_, name) => (vars[name] == null ? "" : String(vars[name])));
}

const PLACES_EN = {
  "Ереван": "Yerevan",
  "Ширак": "Shirak",
  "Гюмри": "Gyumri",
  "Лори": "Lori",
  "Ванадзор": "Vanadzor",
  "Гегаркуник": "Gegharkunik",
  "Севан": "Sevan",
  "Сюник": "Syunik",
  "Капан": "Kapan",
};

function locale() {
  return lang === "en" ? "en-US" : "ru-RU";
}

function place(name) {
  if (lang === "en") return PLACES_EN[name] || name;
  return PLACES[name] || name;
}

function num(value, digits) {
  const options = { maximumFractionDigits: digits };
  if (digits > 0) options.minimumFractionDigits = 0;
  return Number(value || 0).toLocaleString(locale(), options);
}

function formatEnergy(kwh) {
  const value = Number(kwh) || 0;
  if (Math.abs(value) >= 1000) return `${num(value / 1000, 2)} ${t("unit.mwh")}`;
  return `${num(value, 1)} ${t("unit.kwh")}`;
}

function formatAmd(value) {
  return `${num(Math.round(Number(value) || 0), 0)} ${t("unit.dram")}`;
}

function formatPct(value) {
  return `${Number(value || 0).toLocaleString(locale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function formatHours(value) {
  return fill("hours", { value: num(value, 1) });
}

function explainError(detail) {
  const key = API_ERRORS[detail];
  return key ? t(key) : detail || t("error.load");
}

function showError(text) {
  const node = document.getElementById("error");
  node.hidden = !text;
  node.textContent = text || "";
}

function applyStatic() {
  document.documentElement.lang = lang;
  document.title = t("docTitle");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const text = t(node.dataset.i18n);
    if (text.includes("{")) return;
    node.textContent = text;
  });
  document.querySelectorAll("[data-set-lang]").forEach((button) => {
    const on = button.dataset.setLang === lang;
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  });
  renderPill();
}

function renderPill() {
  if (!metrics) return;
  const accuracy = fill("ml.global", {
    mae: num(metrics.mae_daylight, 3),
    profile: num(metrics.mae_profile, 3),
  });
  const globalNote = document.getElementById("model-blurb");
  if (globalNote && state.role !== "exchange") globalNote.textContent = accuracy;
}

const MONTHS = {
  hy: ["հունվարի", "փետրվարի", "մարտի", "ապրիլի", "մայիսի", "հունիսի", "հուլիսի", "\u0585\u0563\u0578\u057d\u057f\u0578\u057d\u056b", "սեպտեմբերի", "հոկտեմբերի", "նոյեմբերի", "դեկտեմբերի"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
};

const PRESETS = [
  ["2025-04-01", "2025-04-30", "preset.april"],
  ["2025-07-01", "2025-07-31", "preset.july"],
  ["2025-01-01", "2025-12-31", "preset.year"],
];

function formatPeriod(start, end) {
  const [ys, ms, ds] = start.split("-").map(Number);
  const [ye, me, de] = end.split("-").map(Number);
  const months = MONTHS[lang] || MONTHS.hy;
  if (ys === ye && ms === me) {
    return lang === "en"
      ? `${months[ms - 1]} ${ds}–${de}, ${ys}`
      : `${ds}–${de} ${months[ms - 1]} ${ys}`;
  }
  if (ys === ye) {
    return lang === "en"
      ? `${months[ms - 1]} ${ds} – ${months[me - 1]} ${de}, ${ys}`
      : `${ds} ${months[ms - 1]} – ${de} ${months[me - 1]} ${ys}`;
  }
  return `${start} – ${end}`;
}

function renderPresets() {
  const host = document.getElementById("presets");
  host.innerHTML = PRESETS.map(([start, end, key]) => {
    const on = state.start === start && state.end === end;
    return `<button type="button" data-range="${start}|${end}" class="${on ? "active" : ""}">${t(key)}</button>`;
  }).join("");
  host.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      const [start, end] = button.dataset.range.split("|");
      state.start = start;
      state.end = end;
      document.getElementById("start").value = start;
      document.getElementById("end").value = end;
      if (state.day < start || state.day > end) {
        state.day = start;
        document.getElementById("forecast-day").value = start;
      }
      setChrome();
      loadRole();
    });
  });
}

function fillStations() {
  const select = document.getElementById("station");
  select.innerHTML = stations.map((station) => {
    const label = fill("option", {
      id: station.id,
      region: place(station.region),
      pv: station.pv_kw,
    });
    return `<option value="${station.id}">${label}</option>`;
  }).join("");
  select.value = state.station;
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = t("error.load");
    try {
      const body = await response.json();
      detail = explainError(body.detail || detail);
    } catch (_err) {
      /* ответ без json */
    }
    throw new Error(detail);
  }
  return response.json();
}

function putChart(id, config) {
  if (charts[id]) charts[id].destroy();
  const user = config.options || {};
  const userPlugins = user.plugins || {};
  charts[id] = new Chart(document.getElementById(id), {
    type: config.type,
    data: config.data,
    plugins: config.plugins || [],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      indexAxis: user.indexAxis,
      layout: user.layout,
      plugins: {
        ...userPlugins,
        legend: {
          labels: { color: ink, boxWidth: 12, font: { size: 12, family: fontFamily } },
          ...(userPlugins.legend || {}),
        },
      },
      scales: user.scales,
    },
  });
}

const shiftMarks = {
  id: "shiftMarks",
  beforeDatasetsDraw(chart) {
    const opts = chart.options.plugins && chart.options.plugins.shiftMarks;
    if (!opts || !chart.chartArea) return;
    const { ctx, chartArea, scales } = chart;
    const points = chart.getDatasetMeta(0).data;
    if (!points.length) return;
    const step = points[1].x - points[0].x;
    ctx.save();
    opts.bands.forEach((band) => {
      if (band.from < 0 || band.to < 0 || !points[band.from] || !points[band.to]) return;
      const left = points[band.from].x - step / 2;
      const right = points[band.to].x + step / 2;
      ctx.fillStyle = band.color;
      ctx.fillRect(left, chartArea.top, Math.max(0, right - left), chartArea.bottom - chartArea.top);
    });
    ctx.restore();
  },
  afterDatasetsDraw(chart) {
    const opts = chart.options.plugins && chart.options.plugins.shiftMarks;
    if (!opts || !chart.chartArea) return;
    const { ctx, chartArea, scales } = chart;
    ctx.save();
    ctx.font = `600 12px ${fontFamily}`;
    ctx.textBaseline = "middle";
    opts.marks.forEach((mark) => {
      if (mark.index < 0) return;
      const point = chart.getDatasetMeta(0).data[mark.index];
      if (!point) return;
      const values = chart.data.datasets.map((series) => Number(series.data[mark.index]) || 0);
      const y = scales.y.getPixelForValue(Math.max(...values));
      const width = ctx.measureText(mark.text).width;
      const boxW = width + 12;
      const boxH = 22;
      let left = point.x - boxW / 2;
      left = Math.max(chartArea.left, Math.min(left, chartArea.right - boxW));
      const top = Math.max(chartArea.top + 4, y - boxH - 8);
      ctx.fillStyle = "#fffaf2";
      ctx.strokeStyle = mark.color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(left, top, boxW, boxH, 6);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = mark.color;
      ctx.textAlign = "left";
      ctx.fillText(mark.text, left + 6, top + boxH / 2);
    });
    ctx.restore();
  },
};

function axis(title) {
  return {
    ticks: { color: muted, maxTicksLimit: 8, font: { family: fontFamily, size: 11 } },
    grid: { color: "rgba(227, 216, 198, 0.8)" },
    title: title
      ? { display: true, text: title, color: muted, font: { family: fontFamily, size: 12 } }
      : undefined,
  };
}

function placeControls() {
  const day = document.getElementById("forecast-wrap");
  const station = document.getElementById("station-wrap");
  const daySlot = document.getElementById(`forecast-slot-${state.role}`);
  if (daySlot) {
    daySlot.appendChild(day);
    day.hidden = false;
  } else {
    day.hidden = true;
  }
  const stationHome = state.role === "exchange"
    ? document.getElementById("station-slot-exchange")
    : document.getElementById("filter-station-home");
  stationHome.appendChild(station);
  station.hidden = state.role === "grid" || state.role === "gate";
}

function setChrome() {
  const title = document.getElementById("role-title");
  const period = document.getElementById("period-label");
  placeControls();
  renderPresets();
  if (state.role === "gate") {
    title.hidden = true;
    document.title = t("docTitle");
    return;
  }
  const name = t(state.role === "grid" ? "nav.grid" : state.role === "solar" ? "nav.solar" : "nav.exchange");
  title.hidden = false;
  title.textContent = name;
  period.textContent = formatPeriod(state.start, state.end);
  document.title = `VoltSynch — ${name}`;
}

function showGate() {
  state.role = "gate";
  document.getElementById("view-gate").hidden = false;
  document.getElementById("view-solar").hidden = true;
  document.getElementById("view-grid").hidden = true;
  document.getElementById("view-exchange").hidden = true;
  document.getElementById("workspace").hidden = true;
  document.getElementById("back-gate").hidden = true;
  setChrome();
}

function enterRole(role) {
  state.role = role;
  document.getElementById("view-gate").hidden = true;
  document.getElementById("view-solar").hidden = role !== "solar";
  document.getElementById("view-grid").hidden = role !== "grid";
  document.getElementById("view-exchange").hidden = role !== "exchange";
  document.getElementById("workspace").hidden = false;
  document.getElementById("back-gate").hidden = false;
  setChrome();
  loadRole();
}

function setLang(next) {
  lang = next === "en" ? "en" : "hy";
  try { localStorage.setItem("voltsynch-lang", lang); } catch (_err) { /* ignore */ }
  applyStatic();
  if (stations.length) fillStations();
  setChrome();
  if (state.role !== "gate") loadRole();
}

async function loadRole() {
  showError("");
  try {
    if (state.role === "solar") await loadSolar();
    if (state.role === "grid") await loadGrid();
    if (state.role === "exchange") await loadExchange();
  } catch (err) {
    showError(err.message);
  }
}

async function loadSolar() {
  const data = await getJson(`/api/solar?station_id=${state.station}&start=${state.start}&end=${state.end}`);
  const station = data.station;
  document.getElementById("solar-lede").textContent = fill("solar.lede", {
    id: station.id,
    city: place(station.city),
    pv: station.pv_kw,
    battery: station.battery_kwh,
  });
  document.getElementById("s-sold").textContent = formatEnergy(data.sold_kwh);
  document.getElementById("s-revenue").textContent = formatAmd(data.revenue_amd);
  document.getElementById("s-extra").textContent = formatAmd(data.extra_amd);
  document.getElementById("s-extra-pct").textContent = fill("solar.extraPct", { pct: formatPct(data.extra_pct) });
  document.getElementById("s-peak").textContent = formatHours(data.sale_delay_h);

  putChart("chart-solar-daily", {
    type: "bar",
    data: {
      labels: data.daily.map((row) => row.date.slice(5)),
      datasets: [
        { type: "bar", label: t("chart.extra"), data: data.daily.map((row) => row.extra_amd), backgroundColor: leaf, yAxisID: "y" },
        { type: "line", label: t("chart.sold"), data: data.daily.map((row) => row.sold_kwh), borderColor: sun, backgroundColor: sun, pointRadius: 0, tension: 0.25, yAxisID: "y1" },
      ],
    },
    options: {
      scales: {
        x: axis(),
        y: axis(t("unit.dram")),
        y1: { ...axis(t("unit.kwh")), position: "right", grid: { drawOnChartArea: false } },
      },
    },
  });
  await loadStationForecast("chart-solar-pv", "chart-solar-batt", "solar-forecast-note");
}

async function loadStationForecast(pvCanvas, battCanvas, noteId) {
  const data = await getJson(`/api/forecast?station_id=${state.station}&date=${state.day}`);
  const training = data.seen_in_training ? t("forecast.seen") : t("forecast.unseen");
  document.getElementById(noteId).textContent = fill("forecast.note", {
    mae: num(data.mae_kwh, 3),
    pred: formatEnergy(data.predicted_peak_kwh),
    actual: formatEnergy(data.actual_peak_kwh),
    train: training,
  });
  const labels = data.hours.map((hour) => String(hour).padStart(2, "0"));
  putChart(pvCanvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: t("chart.actual"), data: data.actual_kwh, borderColor: sun, backgroundColor: sun, pointRadius: 0, tension: 0.25 },
        { label: t("chart.forecast"), data: data.predicted_kwh, borderColor: "#8a5a12", borderDash: [5, 4], pointRadius: 0, tension: 0.25 },
      ],
    },
    options: { scales: { x: axis(t("unit.hour")), y: axis(t("unit.kwh")) } },
  });
  if (!battCanvas) return;
  putChart(battCanvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: t("chart.battActual"), data: data.actual_battery_kwh, backgroundColor: leaf },
        { label: t("chart.battPred"), data: data.predicted_battery_kwh, backgroundColor: blue },
      ],
    },
    options: { scales: { x: axis(t("unit.hour")), y: axis(t("unit.kwh")) } },
  });
}

async function loadGrid() {
  const data = await getJson(`/api/grid?start=${state.start}&end=${state.end}`);
  document.getElementById("g-peak").textContent = formatEnergy(data.refused_kwh);
  document.getElementById("g-stored").textContent = formatEnergy(data.battery_peak_kwh);
  document.getElementById("g-sold").textContent = formatEnergy(data.sold_kwh);

  const noon = data.hourly.filter((row) => row.hour >= 10 && row.hour <= 15);
  const evening = data.hourly.filter((row) => row.hour >= 17 && row.hour <= 21);
  const sumOf = (rows, key) => rows.reduce((total, row) => total + Number(row[key] || 0), 0);
  const would = sumOf(noon, "immediate_kwh");
  const noonSold = sumOf(noon, "sold_kwh");
  document.getElementById("grid-lede").textContent = fill("grid.lede", {
    period: formatPeriod(state.start, state.end),
    held: formatEnergy(Math.max(0, would - noonSold)),
    eve: formatEnergy(sumOf(evening, "battery_kwh")),
  });

  const at = (hour) => data.hourly.findIndex((row) => row.hour === hour);
  const noonRow = data.hourly.find((row) => row.hour === 12) || { immediate_kwh: 0, sold_kwh: 0 };
  const eveRow = data.hourly.find((row) => row.hour === 18) || { battery_kwh: 0 };
  const marked = new Set([12, 18]);

  putChart("chart-grid-hour", {
    type: "line",
    plugins: [shiftMarks],
    data: {
      labels: data.hourly.map((row) => String(row.hour).padStart(2, "0")),
      datasets: [
        {
          label: t("chart.without"),
          data: data.hourly.map((row) => row.immediate_kwh),
          borderColor: sun,
          backgroundColor: "rgba(227,155,43,0.14)",
          fill: true,
          pointRadius: data.hourly.map((row) => (marked.has(row.hour) ? 4 : 0)),
          borderWidth: 2,
          tension: 0.35,
        },
        {
          label: t("chart.with"),
          data: data.hourly.map((row) => row.sold_kwh),
          borderColor: leaf,
          backgroundColor: leaf,
          pointRadius: data.hourly.map((row) => (marked.has(row.hour) ? 4 : 0)),
          borderWidth: 2.5,
          tension: 0.35,
        },
      ],
    },
    options: {
      layout: { padding: { top: 8 } },
      plugins: {
        shiftMarks: {
          bands: [
            { from: at(10), to: at(15), color: "rgba(227,155,43,0.14)" },
            { from: at(17), to: at(21), color: "rgba(31,107,74,0.12)" },
          ],
          marks: [
            {
              index: at(12),
              color: sun,
              text: fill("grid.markNoon", { value: formatEnergy(Math.max(0, noonRow.immediate_kwh - noonRow.sold_kwh)) }),
            },
            {
              index: at(18),
              color: leaf,
              text: fill("grid.markEve", { value: formatEnergy(eveRow.battery_kwh) }),
            },
          ],
        },
      },
      scales: { x: axis(t("unit.hour")), y: axis(t("unit.kwhPeriod")) },
    },
  });

  putChart("chart-grid-daily", {
    type: "bar",
    data: {
      labels: data.daily.map((row) => row.date.slice(5)),
      datasets: [{ label: t("chart.battDaily"), data: data.daily.map((row) => row.battery_peak_kwh), backgroundColor: leaf }],
    },
    options: { plugins: { legend: { display: false } }, scales: { x: axis(), y: axis(t("unit.kwh")) } },
  });

  const forecast = await getJson(`/api/forecast/grid?date=${state.day}`);
  const training = forecast.seen_in_training ? t("forecast.seenShort") : t("forecast.unseenShort");
  document.getElementById("grid-forecast-note").textContent = fill("grid.modelNote", {
    pred: formatEnergy(forecast.predicted_peak_kwh),
    actual: formatEnergy(forecast.actual_peak_kwh),
    train: training,
  });
  putChart("chart-grid-forecast", {
    type: "bar",
    data: {
      labels: forecast.hours.map((hour) => String(hour).padStart(2, "0")),
      datasets: [
        { label: t("chart.actual"), data: forecast.actual_battery_kwh, backgroundColor: leaf },
        { label: t("chart.forecast"), data: forecast.predicted_battery_kwh, backgroundColor: blue },
      ],
    },
    options: { scales: { x: axis(t("unit.hour")), y: axis(t("unit.kwh")) } },
  });
}

async function loadExchange() {
  const data = await getJson(`/api/exchange?start=${state.start}&end=${state.end}`);
  document.getElementById("e-extra").textContent = formatAmd(data.extra_amd);
  document.getElementById("e-extra-pct").textContent = fill("solar.extraPct", { pct: formatPct(data.extra_pct) });
  document.getElementById("e-peak").textContent = formatAmd(data.commission_amd);
  document.getElementById("e-sold").textContent = formatEnergy(data.sold_kwh);
  document.getElementById("e-revenue").textContent = formatAmd(data.revenue_amd);
  document.getElementById("exchange-lede").textContent = fill("exchange.lede", {
    period: formatPeriod(state.start, state.end),
    extra: formatAmd(data.extra_amd),
    fee: formatAmd(data.commission_amd),
  });
  const model = data.metrics;
  document.getElementById("model-blurb").textContent = fill("ml.global", {
    mae: num(model.mae_daylight, 3),
    profile: num(model.mae_profile, 3),
  });
  document.getElementById("model-facts").innerHTML = [
    fill("fact.train", { n: num(model.rows_train, 0) }),
    fill("fact.test", { n: num(model.rows_test, 0) }),
    t("fact.features"),
    t("fact.commission"),
  ].map((item) => `<li>${item}</li>`).join("");

  putChart("chart-exchange-daily", {
    type: "bar",
    data: {
      labels: (data.daily || []).map((row) => row.date.slice(5)),
      datasets: [
        { type: "bar", label: t("chart.extra"), data: data.daily.map((row) => row.extra_amd), backgroundColor: leaf, yAxisID: "y" },
        { type: "line", label: t("chart.sold"), data: data.daily.map((row) => row.sold_kwh), borderColor: sun, backgroundColor: sun, pointRadius: 0, tension: 0.25, yAxisID: "y1" },
      ],
    },
    options: {
      scales: {
        x: axis(),
        y: axis(t("unit.dram")),
        y1: { ...axis(t("unit.kwh")), position: "right", grid: { drawOnChartArea: false } },
      },
    },
  });

  const regions = [...data.regions]
    .map((row) => ({ ...row, perKw: row.pv_kw ? row.extra_amd / row.pv_kw : 0 }))
    .sort((a, b) => b.perKw - a.perKw);
  putChart("chart-regions", {
    type: "bar",
    data: {
      labels: regions.map((row) => place(row.region)),
      datasets: [{ label: t("chart.perKw"), data: regions.map((row) => Math.round(row.perKw)), backgroundColor: leaf }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: axis(t("chart.perKw")), y: axis() },
    },
  });

  const body = document.getElementById("station-rows");
  const totalRow = `
    <tr class="total">
      <td>${t("th.total")}</td>
      <td>${data.stations.length}</td>
      <td>${num(data.stations.reduce((sum, row) => sum + row.pv_kw, 0), 1)}</td>
      <td>${num(data.sold_kwh, 0)}</td>
      <td>${num(Math.round(data.revenue_amd), 0)}</td>
      <td>${num(Math.round(data.extra_amd), 0)}</td>
      <td>${formatPct(data.extra_pct)}</td>
      <td>${num(data.battery_peak_kwh, 1)}</td>
      <td></td>
    </tr>`;
  body.innerHTML = totalRow + data.stations.map((row) => `
    <tr data-station="${row.id}">
      <td>${row.id}</td>
      <td>${place(row.region)}</td>
      <td>${row.pv_kw}</td>
      <td>${num(row.sold_kwh, 0)}</td>
      <td>${num(Math.round(row.revenue_amd), 0)}</td>
      <td>${num(Math.round(row.extra_amd), 0)}</td>
      <td>${formatPct(row.extra_pct)}</td>
      <td>${num(row.battery_peak_kwh, 1)}</td>
      <td class="open-hint" aria-hidden="true">→</td>
    </tr>
  `).join("");
  body.querySelectorAll("tr[data-station]").forEach((row) => {
    row.addEventListener("click", () => {
      state.station = row.dataset.station;
      document.getElementById("station").value = state.station;
      enterRole("solar");
    });
  });

  await loadStationForecast("chart-exchange-pv", null, "exchange-forecast-note");
}

function readFilters() {
  state.start = document.getElementById("start").value;
  state.end = document.getElementById("end").value;
  state.station = document.getElementById("station").value;
  state.day = document.getElementById("forecast-day").value;
}

async function boot() {
  applyStatic();
  const data = await getJson("/api/bootstrap");
  stations = data.stations;
  metrics = data.metrics;
  fillStations();
  renderPill();
  document.querySelectorAll("[data-enter]").forEach((button) => {
    button.addEventListener("click", () => enterRole(button.dataset.enter));
  });
  document.getElementById("back-gate").addEventListener("click", showGate);
  document.querySelectorAll("[data-set-lang]").forEach((button) => {
    button.addEventListener("click", () => setLang(button.dataset.setLang));
  });
  document.querySelectorAll("#start, #end, #station, #forecast-day").forEach((node) => {
    node.addEventListener("change", () => {
      readFilters();
      setChrome();
      if (state.role !== "gate") loadRole();
    });
  });
  showGate();
}

boot().catch((err) => showError(err.message));
