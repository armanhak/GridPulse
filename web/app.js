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
    "nav.exchange": "Բորսա",
    "nav.present": "Ներկայացում",
    "nav.back": "Բոլոր մուտքերը",
    "gate.lede": "Ընտրեք մուտքը։ Յուրաքանչյուր կողմ տեսնում է իր թվերը։",
    "gate.grid": "Մուտք որպես էլեկտրացանց",
    "gate.gridText": "Որքան էներգիա մարտկոցները չեն թողել ցանց կեսօրին, և որքան են վերադարձրել այն ժամին, երբ ցանցը գնում է։",
    "gate.solar": "Մուտք որպես արևային կայան",
    "gate.solarText": "Վաճառված էներգիան, եկամուտը միջնորդավճարից հետո և լրացուցիչ գումարը մարտկոցի շնորհիվ։",
    "gate.exchange": "Մուտք որպես բորսա",
    "gate.exchangeText": "Բոլոր կայանների արդյունքը, ծառայության 10%-ը և արտադրության կանխատեսման ճշտությունը։",
    "ml.title": "Ինչ է անում մոդելը",
    "ml.q": "Պատասխանում է մեկ հարցի. քանի կիլովատ-ժամ կարտադրի կայանը մոտակա ժամերին։",
    "ml.not": "Գինը չի դնում։ Գնման ժամն ու սակագինը հայտարարում է ցանցը։",
    "ml.use": "Այդ թվով երևում է, արդյոք մարտկոցը կհասցնի լիցքավորվել մինչև վաճառքի ժամը։ Գրաֆիկում հոծ գիծը փաստն է, կետագիծը՝ կանխատեսումը։",
    "ml.global": "2025 թվականի ստուգման վրա, որը մոդելը չի տեսել, լուսավոր ժամերին սխալը {mae} կՎտ·ժ է։ Առանց մոդելի նույն ամիսը և նույն ժամը սխալվում են {profile} կՎտ·ժ-ով։",
    "pill.loading": "մոդելը բեռնվում է",
    "pill.ready": "2025 թ. ստուգում · սխալ {mae} կՎտ·ժ",
    "filter.from": "Սկսած",
    "filter.to": "Մինչև",
    "filter.station": "Կայան",
    "filter.day": "Կանխատեսման օր",
    "s.sold": "Վաճառվել է ցանցին",
    "s.revenue": "Եկամուտ կայանի",
    "s.extra": "Լրացուցիչ՝ մարտկոցից",
    "s.delay": "Մինչև վաճառք",
    "solar.lede": "{id}, {city}։ Վահանակը՝ {pv} կՎտ, մարտկոցը՝ {battery} կՎտ·ժ։ Եկամուտը ցույց է տրված միջնորդավճարից հետո։ Լրացուցիչ եկամուտն այն գումարն է, որ կայանը ստացել է մարտկոցի շնորհիվ։",
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
    "grid.lede": "Երբ պահանջարկը հեռու է օրվա գագաթից, ցանցը արևային էներգիա չի գնում։ Այն մնում է մարտկոցներում կամ կտրվում է։ Ընդունման ժամին կայանները վաճառում են անմիջապես։",
    "g.refused": "Չի ընդունվել, երբ պետք չէր",
    "g.battery": "Եկել է մարտկոցներից",
    "g.bought": "Գնվել է կայաններից",
    "g.delay": "Մինչև վաճառք",
    "grid.hourTitle": "Ինչպես են մարտկոցները թեթևացնում ցանցը",
    "grid.hourNote": "Դեղին սյունը՝ ինչ կլցվեր ցանց, եթե մարտկոց չլիներ. գագաթը կեսօրին է։ Կանաչ սյունը՝ ինչ իրականում է մտել։ Մուգ մասը մարտկոցից է։ Կեսօրին կանաչը դեղինից ցածր է. այդ էներգիան ցանց չի ծանրաբեռնել, մնացել է մարտկոցում։ Երեկոյան մուգ մասը գալիս է այն ժամին, երբ ցանցը գնում է։",
    "grid.shift": "Ժամը 10:00–15:00 առանց մարտկոցի ցանց կմտներ {would}։ Չի մտել {held}. այդքանով կեսօրվա լրացուցիչ ծանրաբեռնում չի եղել։ Ժամը 17:00–21:00 մարտկոցները տվել են {eve}։",
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
    "exchange.lede": "Այստեղ երևում են կայանների լրացուցիչ եկամուտը, ծառայության 10% միջնորդավճարը և այն, թե որքան ճշգրիտ է արտադրության կանխատեսումը։",
    "e.extra": "Բոլոր կայանների լրացուցիչ եկամուտ",
    "e.commission": "Միջնորդավճար, 10%",
    "e.sold": "Վաճառվել է ցանցին",
    "e.mae": "Մոդելի սխալ, ժամը 7–18",
    "e.maeNote": "առանց մոդելի սխալը՝ {profile} կՎտ·ժ, մոդելն ավելի ճշգրիտ է {lift}%-ով",
    "exchange.regionTitle": "Լրացուցիչ եկամուտ ըստ մարզի",
    "exchange.modelTitle": "Ինչպես է աշխատում մոդելը",
    "exchange.modelBlurb": "Մոդելը կանխատեսում է արտադրությունն ըստ եղանակի և վահանակի։ Գինը չի որոշում։ Ուսուցումը՝ մինչև {trainEnd}, ստուգումը՝ {testYear} թվականը։",
    "fact.train": "Ուսուցման ժամեր՝ {n}",
    "fact.test": "Ստուգման ժամեր՝ {n}",
    "fact.features": "Տվյալներ՝ ժամ, ամիս, տարվա օր, ջերմաստիճան, ամպամածություն, հզորություն, թեքություն, ազիմուտ, վահանակի գործակից, GHI, DNI, DHI",
    "fact.commission": "10% միջնորդավճարը հաշվվում է ցանցի վճարումից։ Արտադրության կանխատեսման մեջ այն չկա։",
    "exchange.stationsTitle": "Կայաններ",
    "exchange.tableNote": "Սեղմեք տողի վրա, որպեսզի բացվի այդ կայանի կաբինետը։",
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
    "nav.exchange": "Exchange",
    "nav.present": "Overview",
    "nav.back": "All entrances",
    "gate.lede": "Choose an entrance. Each side sees its own numbers.",
    "gate.grid": "Enter as the power grid",
    "gate.gridText": "How much energy the batteries kept out of the grid at noon, and how much they returned when the grid was buying.",
    "gate.solar": "Enter as a solar station",
    "gate.solarText": "Energy sold, income after the commission, and the extra amount earned because of the battery.",
    "gate.exchange": "Enter as the exchange",
    "gate.exchangeText": "The result of every station, the service’s 10%, and how accurate the generation forecast is.",
    "ml.title": "What the model does",
    "ml.q": "It answers one question: how many kilowatt-hours this station will produce in the coming hours.",
    "ml.not": "It does not set the price. The grid publishes the hours it buys and the tariff.",
    "ml.use": "That forecast shows whether the battery will be charged in time for the sale. On the chart the solid line is what happened, the dashed line is the forecast.",
    "ml.global": "On the 2025 check, which the model had not seen, the daylight error is {mae} kWh. Without the model, the same month and the same hour miss by {profile} kWh.",
    "pill.loading": "model is loading",
    "pill.ready": "2025 check · error {mae} kWh",
    "filter.from": "From",
    "filter.to": "to",
    "filter.station": "Station",
    "filter.day": "Forecast day",
    "s.sold": "Sold to the grid",
    "s.revenue": "Station income",
    "s.extra": "Extra from the battery",
    "s.delay": "Until the sale",
    "solar.lede": "{id}, {city}. Panel {pv} kW, battery {battery} kWh. Income is shown after the commission. Extra income is the amount the station earned because of the battery.",
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
    "grid.lede": "When demand is far from the day’s peak, the grid does not buy solar energy. It stays in the batteries or is curtailed. In a buying hour the stations sell at once.",
    "g.refused": "Kept out when not needed",
    "g.battery": "Delivered from batteries",
    "g.bought": "Bought from stations",
    "g.delay": "Until the sale",
    "grid.hourTitle": "How the batteries lighten the grid",
    "grid.hourNote": "The yellow bar is what would have poured into the grid with no battery: the peak is at noon. The green bar is what actually entered. The dark part comes from the battery. At noon the green bar is lower than the yellow one: that energy did not load the grid, it stayed in the battery. In the evening the dark part arrives in the hour the grid is buying.",
    "grid.shift": "From 10:00 to 15:00, {would} would have entered without batteries. {held} stayed out, so the grid did not take that midday load. From 17:00 to 21:00 the batteries delivered {eve}.",
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
    "exchange.lede": "Here you see the stations’ extra income, the service’s 10% commission, and how accurate the generation forecast is.",
    "e.extra": "Extra income of all stations",
    "e.commission": "Commission, 10%",
    "e.sold": "Sold to the grid",
    "e.mae": "Model error, hours 7–18",
    "e.maeNote": "without the model the error is {profile} kWh; the model is {lift}% more accurate",
    "exchange.regionTitle": "Extra income by region",
    "exchange.modelTitle": "What the model does",
    "exchange.modelBlurb": "The model forecasts generation from the weather and the panel. It does not set the price. Training runs through {trainEnd}; the check is {testYear}.",
    "fact.train": "Hours in training: {n}",
    "fact.test": "Hours in the check: {n}",
    "fact.features": "Inputs: hour, month, day of year, temperature, cloud cover, power, tilt, azimuth, panel factor, GHI, DNI, DHI",
    "fact.commission": "The 10% commission is taken from what the grid pays. It is not part of the generation forecast.",
    "exchange.stationsTitle": "Stations",
    "exchange.tableNote": "Click a row to open that station’s entrance.",
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
    if (node.id === "model-pill" && metrics) return;
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-set-lang]").forEach((button) => {
    const on = button.dataset.setLang === lang;
    button.classList.toggle("active", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  });
  renderPill();
}

function renderPill() {
  const node = document.getElementById("model-pill");
  if (!metrics) {
    node.textContent = t("pill.loading");
    return;
  }
  node.textContent = fill("pill.ready", { mae: num(metrics.mae_daylight, 3) });
  const accuracy = fill("ml.global", {
    mae: num(metrics.mae_daylight, 3),
    profile: num(metrics.mae_profile, 3),
  });
  const globalNote = document.getElementById("ml-global");
  if (globalNote) globalNote.textContent = accuracy;
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
  const userLegend = (user.plugins && user.plugins.legend) || {};
  charts[id] = new Chart(document.getElementById(id), {
    type: config.type,
    data: config.data,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      indexAxis: user.indexAxis,
      plugins: {
        legend: {
          labels: { color: ink, boxWidth: 12, font: { size: 12, family: fontFamily } },
          ...userLegend,
        },
      },
      scales: user.scales,
    },
  });
}

function axis(title) {
  return {
    ticks: { color: muted, maxTicksLimit: 8, font: { family: fontFamily, size: 11 } },
    grid: { color: "rgba(227, 216, 198, 0.8)" },
    title: title
      ? { display: true, text: title, color: muted, font: { family: fontFamily, size: 12 } }
      : undefined,
  };
}

function showGate() {
  state.role = "gate";
  document.getElementById("view-gate").hidden = false;
  document.getElementById("view-solar").hidden = true;
  document.getElementById("view-grid").hidden = true;
  document.getElementById("view-exchange").hidden = true;
  document.getElementById("workspace").hidden = true;
  document.getElementById("back-gate").hidden = true;
}

function enterRole(role) {
  state.role = role;
  document.getElementById("view-gate").hidden = true;
  document.getElementById("view-solar").hidden = role !== "solar";
  document.getElementById("view-grid").hidden = role !== "grid";
  document.getElementById("view-exchange").hidden = role !== "exchange";
  document.getElementById("workspace").hidden = false;
  document.getElementById("back-gate").hidden = false;
  document.getElementById("station-wrap").hidden = role === "grid";
  loadRole();
}

function setLang(next) {
  lang = next === "en" ? "en" : "hy";
  try { localStorage.setItem("voltsynch-lang", lang); } catch (_err) { /* ignore */ }
  applyStatic();
  if (stations.length) fillStations();
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
  document.getElementById("g-share").textContent = formatHours(data.sale_delay_h);

  const noon = data.hourly.filter((row) => row.hour >= 10 && row.hour <= 15);
  const evening = data.hourly.filter((row) => row.hour >= 17 && row.hour <= 21);
  const sumOf = (rows, key) => rows.reduce((total, row) => total + Number(row[key] || 0), 0);
  const would = sumOf(noon, "immediate_kwh");
  const noonSold = sumOf(noon, "sold_kwh");
  document.getElementById("grid-shift-note").textContent = fill("grid.shift", {
    would: formatEnergy(would),
    held: formatEnergy(Math.max(0, would - noonSold)),
    eve: formatEnergy(sumOf(evening, "battery_kwh")),
  });

  putChart("chart-grid-hour", {
    type: "bar",
    data: {
      labels: data.hourly.map((row) => String(row.hour).padStart(2, "0")),
      datasets: [
        {
          label: t("chart.without"),
          data: data.hourly.map((row) => row.immediate_kwh),
          backgroundColor: "rgba(227,155,43,0.85)",
          stack: "without",
        },
        {
          label: t("chart.direct"),
          data: data.hourly.map((row) => Math.max(0, row.sold_kwh - row.battery_kwh)),
          backgroundColor: "#c5e0d2",
          stack: "with",
        },
        {
          label: t("chart.fromBatt"),
          data: data.hourly.map((row) => row.battery_kwh),
          backgroundColor: leaf,
          stack: "with",
        },
      ],
    },
    options: { scales: { x: axis(t("unit.hour")), y: axis(t("unit.kwhPeriod")) } },
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
  const model = data.metrics;
  document.getElementById("e-mae").textContent = `${num(model.mae_daylight, 3)} ${t("unit.kwh")}`;
  const lift = Math.round(100 * (model.mae_profile - model.mae_daylight) / model.mae_profile);
  document.getElementById("e-mae-note").textContent = fill("e.maeNote", {
    profile: num(model.mae_profile, 3),
    lift,
  });
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

  putChart("chart-regions", {
    type: "bar",
    data: {
      labels: data.regions.map((row) => place(row.region)),
      datasets: [{ label: t("chart.extra"), data: data.regions.map((row) => row.extra_amd), backgroundColor: leaf }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: axis(t("unit.dram")), y: axis() },
    },
  });

  const body = document.getElementById("station-rows");
  body.innerHTML = data.stations.map((row) => `
    <tr data-station="${row.id}">
      <td>${row.id}</td>
      <td>${place(row.region)}</td>
      <td>${row.pv_kw}</td>
      <td>${num(row.sold_kwh, 0)}</td>
      <td>${num(Math.round(row.revenue_amd), 0)}</td>
      <td>${num(Math.round(row.extra_amd), 0)}</td>
      <td>${formatPct(row.extra_pct)}</td>
      <td>${num(row.battery_peak_kwh, 1)}</td>
    </tr>
  `).join("");
  body.querySelectorAll("tr").forEach((row) => {
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
  document.querySelectorAll(".filters input, .filters select").forEach((node) => {
    node.addEventListener("change", () => {
      readFilters();
      loadRole();
    });
  });
  showGate();
}

boot().catch((err) => showError(err.message));
