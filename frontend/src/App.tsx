import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, ArrowUpRight, Bell, CalendarDays, Check, ChevronDown, Compass, Globe2, Plane, Search, ShieldCheck, Sparkles, Wallet } from "lucide-react";

// Same-origin by default: the Vite proxy forwards /api to the backend, so the
// app works on localhost, 127.0.0.1 or a LAN address without CORS problems.
// Set VITE_API_BASE_URL to call a backend on another host.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type TripType = "round-trip" | "one-way";
type Flight = { id: string; airline: string; flight_number: string; departure_time: string; arrival_time: string; duration_minutes: number; stops: number; price: number; currency: string; baggage_kg: number | null; refundable: boolean | null; data_status: string; disclaimer: string };


type SearchHistory = {
  id: number;
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string | null;
  trip_type: TripType;
  passengers: number;
  cabin: string;
  result_count: number;
  created_at: string;
};

type SearchAnalytics = {
  total_searches: number;
  unique_destinations: number;
  most_searched_destination: string | null;
  destination_counts: Record<string, number>;
  latest_search: {
    origin: string;
    destination: string;
    created_at: string;
  } | null;
};


export default function App() {
  const [tripType, setTripType] = useState<TripType>("round-trip");
  const [origin, setOrigin] = useState("Karachi (KHI)");
  const [destination, setDestination] = useState("New York (NYC)");
  const [departure, setDeparture] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [passengers, setPassengers] = useState("1 adult");
  const [cabin, setCabin] = useState("Economy");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Flight[]>([]);
  const [history, setHistory] = useState<SearchHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  
const [analytics, setAnalytics] = useState<SearchAnalytics | null>(null);
const [analyticsLoading, setAnalyticsLoading] = useState(true);
const [analyticsError, setAnalyticsError] = useState("");


async function loadHistory() {
  try {
    const response = await fetch(`${API_BASE}/api/flights/history`);

    if (!response.ok) {
      throw new Error("Could not load search history.");
    }

    const data: SearchHistory[] = await response.json();
    setHistory(data);
    setHistoryError("");
  } catch (error) {
    setHistoryError(
      error instanceof Error
        ? error.message
        : "Could not load search history."
    );
  } finally {
    setHistoryLoading(false);
  }
}

async function loadAnalytics() {
  try {
    const response = await fetch(`${API_BASE}/api/flights/analytics`);

    if (!response.ok) {
      throw new Error("Could not load flight search analytics.");
    }

    const data: SearchAnalytics = await response.json();
    setAnalytics(data);
    setAnalyticsError("");
  } catch (error) {
    setAnalyticsError(
      error instanceof Error
        ? error.message
        : "Could not load flight search analytics."
    );
  } finally {
    setAnalyticsLoading(false);
  }
}



useEffect(() => {
  void loadHistory();
  void loadAnalytics();
}, []);


  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setNotice(""); setResults([]);
    if (!origin.trim() || !destination.trim()) { setNotice("Enter both an origin and a destination."); return; }
    if (origin.trim().toLowerCase() === destination.trim().toLowerCase()) { setNotice("Origin and destination must be different."); return; }
    if (!departure) { setNotice("Please select a departure date."); return; }
    if (tripType === "round-trip" && (!returnDate || returnDate < departure)) { setNotice("Choose a return date on or after departure."); return; }
    const passengerCount = passengers.startsWith("Family") ? 5 : Number(passengers.split(" ")[0]);
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/flights/search`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin, destination, departure_date: departure, return_date: tripType === "round-trip" ? returnDate : null, trip_type: tripType, passengers: passengerCount, cabin })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Please check your search details.");
      
setResults(payload.results ?? []);
setNotice(payload.source_message ?? "Demo results loaded.");

await Promise.all([loadHistory(), loadAnalytics()]);


await loadHistory();
    } catch (error) {
      setNotice(`${error instanceof Error ? error.message : "Could not connect to the API."} Ensure the FastAPI backend is running on port 8000.`);
    } finally { setLoading(false); }
  }

  return <div className="min-h-screen bg-canvas">
    <header className="border-b border-slate-200/80 bg-white"><div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
      <a className="flex items-center gap-3" href="/" aria-label="FlyCompare AI home"><span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-ink text-white"><Plane size={21}/></span><span><span className="block text-lg font-extrabold tracking-tight text-ink">FlyCompare <span className="text-ocean">AI</span></span><span className="block text-[11px] font-medium tracking-wide text-slate-500">SMARTER TRAVEL DECISIONS</span></span></a>
      <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex" aria-label="Main navigation"><a className="text-ink" href="#search">Flights</a><a href="#how-it-works" className="transition hover:text-ink">Price insights</a><a href="#features" className="transition hover:text-ink">Why FlyCompare</a></nav>
      <button className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700" type="button" onClick={() => setNotice("Profile and authentication will be added in a later stage.")}><Bell size={16}/><span className="hidden sm:inline">My travel</span></button>
    </div></header>
    <main><section className="relative overflow-hidden bg-ink text-white"><div className="pointer-events-none absolute -right-24 -top-36 h-96 w-96 rounded-full bg-ocean/30 blur-3xl"/><div className="pointer-events-none absolute -bottom-44 left-1/4 h-80 w-80 rounded-full bg-emerald-400/10 blur-3xl"/>
      <div className="relative mx-auto grid max-w-7xl gap-10 px-5 pb-28 pt-16 lg:grid-cols-[1.05fr_.95fr] lg:px-8 lg:pb-36 lg:pt-24"><div className="max-w-2xl"><div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-emerald-200"><Sparkles size={14}/> FLIGHT INTELLIGENCE, NOT JUST SEARCH</div><h1 className="text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">Find the flight that fits <span className="text-emerald-300">your journey.</span></h1><p className="mt-5 max-w-xl text-base leading-7 text-slate-300 sm:text-lg">Compare fares, journey time, stops, baggage and flexibility. Make a clearer travel decision with transparent data and explainable insights.</p><div className="mt-8 flex flex-wrap gap-4 text-sm text-slate-300"><span className="flex items-center gap-2"><Check size={16} className="text-emerald-300"/> Multi-factor comparison</span><span className="flex items-center gap-2"><Check size={16} className="text-emerald-300"/> Historical price insights</span></div></div>
      <div className="hidden items-center justify-center lg:flex"><div className="relative flex h-64 w-64 items-center justify-center rounded-full border border-white/10 bg-white/[0.035]"><div className="absolute inset-7 rounded-full border border-dashed border-emerald-200/30"/><div className="absolute inset-14 rounded-full border border-white/10"/><Globe2 size={112} strokeWidth={0.8} className="text-emerald-100/80"/><span className="absolute right-4 top-10 rounded-xl border border-white/10 bg-white/10 p-3 backdrop-blur"><Plane size={21} className="-rotate-12 text-emerald-200"/></span><span className="absolute bottom-8 left-3 rounded-xl border border-white/10 bg-white/10 p-3 backdrop-blur"><Compass size={21} className="text-white"/></span></div></div></div></section>
    <section id="search" className="relative z-10 mx-auto -mt-16 max-w-7xl px-5 lg:px-8"><div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft sm:p-7"><div className="mb-6 flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-xl font-bold text-ink">Where would you like to go?</h2><p className="mt-1 text-sm text-slate-500">Start with your route. We’ll build the comparison around your priorities.</p></div><div className="inline-flex rounded-xl bg-slate-100 p-1" aria-label="Trip type"><button type="button" onClick={() => setTripType("round-trip")} className={`rounded-lg px-3 py-2 text-sm font-semibold ${tripType === "round-trip" ? "bg-white text-ink shadow-sm" : "text-slate-500"}`}>Round trip</button><button type="button" onClick={() => setTripType("one-way")} className={`rounded-lg px-3 py-2 text-sm font-semibold ${tripType === "one-way" ? "bg-white text-ink shadow-sm" : "text-slate-500"}`}>One way</button></div></div>
    <form onSubmit={handleSearch}><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Field label="From" icon={<Plane size={18} className="shrink-0 text-ocean"/>}><input aria-label="Origin airport or city" className="w-full min-w-0 bg-transparent text-sm font-semibold outline-none" value={origin} onChange={e=>setOrigin(e.target.value)} placeholder="City or airport"/></Field>
      <Field label="To" icon={<ArrowUpRight size={18} className="shrink-0 text-ocean"/>}><input aria-label="Destination airport or city" className="w-full min-w-0 bg-transparent text-sm font-semibold outline-none" value={destination} onChange={e=>setDestination(e.target.value)} placeholder="City or airport"/></Field>
      <Field label="Departure" icon={<CalendarDays size={18} className="shrink-0 text-ocean"/>}><input aria-label="Departure date" type="date" min={new Date().toISOString().slice(0,10)} className="w-full min-w-0 bg-transparent text-sm font-semibold text-slate-700 outline-none" value={departure} onChange={e=>setDeparture(e.target.value)}/></Field>
      <Field label="Return" icon={<CalendarDays size={18} className="shrink-0 text-ocean"/>}><input aria-label="Return date" type="date" disabled={tripType === "one-way"} min={departure || undefined} className="w-full min-w-0 bg-transparent text-sm font-semibold text-slate-700 outline-none disabled:cursor-not-allowed" value={returnDate} onChange={e=>setReturnDate(e.target.value)}/></Field>
    </div><div className="mt-4 flex flex-wrap items-end gap-3"><label className="min-w-[145px] flex-1"><span className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500">Passengers</span><span className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-3"><select aria-label="Passengers" className="w-full bg-transparent text-sm font-semibold outline-none" value={passengers} onChange={e=>setPassengers(e.target.value)}><option>1 adult</option><option>2 adults</option><option>3 adults</option><option>4 adults</option><option>Family / 5+ passengers</option></select><ChevronDown size={16} className="text-slate-400"/></span></label>
    <label className="min-w-[145px] flex-1"><span className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500">Cabin class</span><span className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-3"><select aria-label="Cabin class" className="w-full bg-transparent text-sm font-semibold outline-none" value={cabin} onChange={e=>setCabin(e.target.value)}><option>Economy</option><option>Premium economy</option><option>Business</option><option>First class</option></select><ChevronDown size={16} className="text-slate-400"/></span></label>
    <button type="submit" disabled={loading} className="flex min-h-[46px] flex-1 items-center justify-center gap-2 rounded-xl bg-ocean px-6 py-3 text-sm font-bold text-white transition hover:bg-sky-800 disabled:opacity-60 sm:flex-none"><Search size={17}/> {loading ? "Searching…" : "Search flights"} <ArrowRight size={16}/></button></div>
    {notice && <p role="status" className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">{notice}</p>}<p className="mt-4 text-xs leading-5 text-slate-400">Demo provider only: results are simulated and are not live prices, availability, or bookable tickets.</p></form>
    {results.length > 0 && <div className="mt-6 space-y-3" aria-label="Flight search results"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-lg font-bold text-ink">Demo flight options</h3><span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-900">SIMULATED · NOT LIVE</span></div>{results.map(flight=><article key={flight.id} className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-[1fr_auto] sm:items-center"><div><div className="font-bold text-ink">{flight.airline} <span className="font-medium text-slate-500">· {flight.flight_number}</span></div><div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-700"><span className="font-semibold">{flight.departure_time}</span><span className="text-slate-400">→</span><span className="font-semibold">{flight.arrival_time}</span><span className="text-slate-500">· {Math.floor(flight.duration_minutes/60)}h {flight.duration_minutes%60}m</span><span className="text-slate-500">· {flight.stops===0 ? "Nonstop" : `${flight.stops} stop${flight.stops>1 ? "s" : ""}`}</span></div><p className="mt-2 text-xs text-slate-500">{flight.baggage_kg == null ? "Baggage not specified" : `${flight.baggage_kg} kg baggage (demo)`} · {flight.refundable == null ? "Refund policy unknown" : flight.refundable ? "Demo fare marked refundable" : "Demo fare marked non-refundable"}</p></div><div className="sm:text-right"><p className="text-2xl font-extrabold text-ink">${flight.price.toFixed(0)}</p><p className="text-xs text-slate-500">USD · simulated price</p></div></article>)}</div>}
    </div></section>
    
<section
  id="analytics"
  className="mx-auto max-w-7xl px-5 pt-10 lg:px-8"
>
  <div className="mb-6">
    <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-ocean">
      Your travel activity
    </p>
    <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-ink">
      Search analytics
    </h2>
    <p className="mt-2 text-sm text-slate-500">
      Insights calculated from saved flight searches.
    </p>
  </div>

  {analyticsLoading && (
    <p role="status" className="text-sm text-slate-500">
      Loading analytics...
    </p>
  )}

  {!analyticsLoading && analyticsError && (
    <p role="status" className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
      {analyticsError}
    </p>
  )}

  {!analyticsLoading && !analyticsError && analytics && (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Total searches</p>
          <p className="mt-3 text-3xl font-extrabold text-ink">
            {analytics.total_searches}
          </p>
          <p className="mt-2 text-xs text-slate-400">
            Saved search records
          </p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-slate-500">
            Unique destinations
          </p>
          <p className="mt-3 text-3xl font-extrabold text-ink">
            {analytics.unique_destinations}
          </p>
          <p className="mt-2 text-xs text-slate-400">
            Destinations searched
          </p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:col-span-2 lg:col-span-1">
          <p className="text-sm font-medium text-slate-500">
            Most searched destination
          </p>
          <p className="mt-3 text-xl font-extrabold text-ink">
            {analytics.most_searched_destination ?? "No searches yet"}
          </p>
          <p className="mt-2 text-xs text-slate-400">
            Based on saved search history
          </p>
        </article>
      </div>

      <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-bold text-ink">
          Searches by destination
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          Number of saved searches for each destination.
        </p>

        {Object.keys(analytics.destination_counts).length === 0 ? (
          <p className="mt-5 text-sm text-slate-500">
            No destination data available yet.
          </p>
        ) : (
          <div className="mt-5 space-y-5">
            {Object.entries(analytics.destination_counts)
              .sort((a, b) => b[1] - a[1])
              .map(([destination, count]) => {
                const percentage =
                  analytics.total_searches > 0
                    ? (count / analytics.total_searches) * 100
                    : 0;

                return (
                  <div key={destination}>
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-slate-700">
                        {destination}
                      </span>
                      <span className="text-sm font-bold text-ink">
                        {count} {count === 1 ? "search" : "searches"}
                      </span>
                    </div>

                    <div
                      className="h-2.5 overflow-hidden rounded-full bg-slate-100"
                      role="progressbar"
                      aria-label={`${destination} search share`}
                      aria-valuenow={Math.round(percentage)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className="h-full rounded-full bg-ocean transition-all"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {analytics.latest_search && (
        <p className="mt-4 text-xs text-slate-400">
          Latest saved search: {analytics.latest_search.origin} to{" "}
          {analytics.latest_search.destination} ·{" "}
          {new Date(analytics.latest_search.created_at).toLocaleString()}
        </p>
      )}
    </>
  )}
</section>

    <section
  id="history"
  className="mx-auto max-w-7xl px-5 py-12 lg:px-8"
>
  <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
    <div className="mb-6">
      <h2 className="text-2xl font-extrabold text-ink">
        Recent flight searches
      </h2>
      <p className="mt-2 text-sm text-slate-500">
        Your latest searches saved by FlyCompare AI.
      </p>
    </div>

    {historyLoading && (
      <p role="status" className="text-sm text-slate-500">
        Loading search history...
      </p>
    )}

    {!historyLoading && historyError && (
      <p role="status" className="text-sm text-amber-800">
        {historyError}
      </p>
    )}

    {!historyLoading && !historyError && history.length === 0 && (
      <p className="text-sm text-slate-500">
        No saved searches yet. Search for a flight to get started.
      </p>
    )}

    {!historyLoading && !historyError && history.length > 0 && (
      <div className="space-y-3">
        {history.map((search) => (
          <article
            key={search.id}
            className="rounded-2xl border border-slate-200 p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-bold text-ink">
                {search.origin} → {search.destination}
              </h3>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {search.result_count} demo offers
              </span>
            </div>

            <p className="mt-2 text-sm text-slate-600">
              Departure: {search.departure_date}
              {search.return_date
                ? ` · Return: ${search.return_date}`
                : " · One way"}
            </p>

            <p className="mt-1 text-sm text-slate-600">
              {search.passengers} passenger(s) · {search.cabin}
            </p>

            <p className="mt-2 text-xs text-slate-400">
              Saved: {new Date(search.created_at).toLocaleString()}
            </p>
          </article>
        ))}
      </div>
    )}
  </div>
</section>
    <section id="features" className="mx-auto max-w-7xl px-5 py-16 lg:px-8 lg:py-20"><div className="max-w-2xl"><p className="text-xs font-extrabold uppercase tracking-[0.18em] text-ocean">Beyond the cheapest fare</p><h2 className="mt-3 text-3xl font-extrabold tracking-tight text-ink">A clearer way to compare flights.</h2><p className="mt-3 leading-7 text-slate-600">The platform will evaluate the trade-offs behind each journey and show why an option may suit your needs.</p></div><div className="mt-8 grid gap-4 md:grid-cols-3"><Feature icon={<Wallet size={21}/>} title="Price context" text="Compare offers with historical observations when suitable data and a validated model exist."/><Feature icon={<Compass size={21}/>} title="Your priorities" text="Balance price, duration, stops, baggage and fare flexibility with configurable preferences."/><Feature icon={<ShieldCheck size={21}/>} title="Transparent results" text="See source and freshness labels, measurable recommendation reasons, and clear limitations."/></div></section>
    <section id="how-it-works" className="border-y border-slate-200 bg-white"><div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 md:grid-cols-[.8fr_1.2fr] lg:px-8"><div><p className="text-xs font-extrabold uppercase tracking-[0.18em] text-ocean">Built on evidence</p><h2 className="mt-3 text-2xl font-extrabold tracking-tight text-ink">Historical insight is not a live fare.</h2></div><div className="max-w-2xl text-sm leading-7 text-slate-600">Historical flight records can help train price-estimation models and reveal patterns. They cannot prove that a seat is available now or guarantee today’s price. FlyCompare AI keeps historical learning data separate from current provider/test offers.</div></div></section></main>
    <footer className="bg-ink px-5 py-7 text-center text-xs text-slate-400"><p>© {new Date().getFullYear()} FlyCompare AI · Intelligent travel decision support</p><p className="mt-2">Demo-search build · No live inventory or ticket issuance is claimed.</p></footer>
  </div>;
}
function Field({label, icon, children}: {label:string; icon:ReactNode; children:ReactNode}) { return <label className="block"><span className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-500">{label}</span><span className="flex items-center gap-3 rounded-xl border border-slate-200 px-3 py-3.5 focus-within:border-ocean">{icon}{children}</span></label>; }
function Feature({icon, title, text}: {icon:ReactNode; title:string; text:string}) { return <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-mint text-ocean">{icon}</div><h3 className="mt-4 text-lg font-bold text-ink">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></article>; }
