import { useId, useState, type ReactNode } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { dateTime, money } from '../lib/format';
import { AirlineLogo } from '../illustrations';
import type { PricePoint } from '../lib/types';

// Bright, coordinated palette designed for the existing LIGHT page theme.
const PALETTE = ['#5577F6', '#16B8A6', '#F59E55', '#9874F5', '#E66B9A', '#36A3D9'];
const AXIS = { fill: '#8490A5', fontSize: 11, fontWeight: 500 as const };
const GRID = '#E9EDF5';

type ChartRow = Record<string, unknown>;
type TipProps = {
  active?: boolean;
  payload?: { value: number; name?: string; payload: ChartRow; color?: string }[];
  label?: string | number;
};

function ChartTip({
  active,
  payload,
  label,
  format,
}: TipProps & { format: (value: number, row: ChartRow) => string }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div
      style={{
        padding: '10px 13px',
        border: '1px solid #E5EAF3',
        borderRadius: 12,
        background: 'rgba(255,255,255,.97)',
        boxShadow: '0 10px 30px rgba(35,53,91,.14)',
        color: '#25324A',
        minWidth: 125,
      }}
    >
      <small style={{ display: 'block', color: '#8490A5', marginBottom: 4 }}>
        {String(row.tipLabel ?? label ?? '')}
      </small>
      <b style={{ fontSize: 14, color: '#25324A' }}>{format(payload[0].value, row)}</b>
    </div>
  );
}

function ChartFrame({ children, height }: { children: ReactNode; height: number }) {
  return <div className="chart-box" style={{ height, width: '100%', minWidth: 0 }}>{children}</div>;
}

/** Evenly spaced integer ticks from 0 that always end on the axis maximum (avoids 0, 3, 6, 9, 10). */
function countTicks(max: number, steps = 4) {
  const step = Math.max(1, Math.ceil(max / steps));
  return Array.from({ length: steps + 1 }, (_, i) => i * step);
}

/** Pads a price axis so flat or single-value series don't collapse into a meaningless decimal range. */
function priceDomain(values: number[]): [number, number] {
  const lo = Math.min(...values), hi = Math.max(...values);
  const pad = Math.max((hi - lo) * 0.15, hi * 0.05, 1);
  return [Math.max(0, Math.floor(lo - pad)), Math.ceil(hi + pad)];
}

export function ActivityChart({ data }: { data: { label: string; tipLabel: string; count: number }[] }) {
  const id = useId().replace(/:/g, '');
  const ticks = countTicks(Math.max(...data.map((d) => d.count), 1));
  return (
    <ChartFrame height={230}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 12, right: 12, bottom: 2, left: -17 }}>
          <defs>
            <linearGradient id={`activity-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5577F6" stopOpacity={0.30} />
              <stop offset="58%" stopColor="#7B8FF8" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#7B8FF8" stopOpacity={0.015} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="4 5" />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} />
          <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} domain={[0, ticks[ticks.length - 1]]} ticks={ticks} />
          <Tooltip cursor={{ stroke: '#C9D3E5', strokeDasharray: '4 4' }} content={<ChartTip format={(v) => `${v} search${v === 1 ? '' : 'es'}`} />} />
          <Area
            type="monotoneX"
            dataKey="count"
            stroke="#5577F6"
            strokeWidth={3}
            fill={`url(#activity-${id})`}
            activeDot={{ r: 6, fill: '#5577F6', stroke: '#fff', strokeWidth: 3 }}
            dot={false}
            animationDuration={850}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function PriceTrendChart({ points, currency, height = 190 }: { points: PricePoint[]; currency: string; height?: number }) {
  // Several searches on one day would all read "2 Nov"; include the time when days repeat.
  const days = points.map((p) => new Date(p.observed_at).toDateString());
  const sameDay = new Set(days).size < days.length;
  const data = points.map((p) => ({
    ...p,
    label: new Date(p.observed_at).toLocaleString('en-GB', sameDay ? { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' } : { day: 'numeric', month: 'short' }),
    tipLabel: `Observed ${dateTime(p.observed_at)} · ${p.offers} offers`,
  }));
  const domain = priceDomain(points.map((p) => p.lowest_price));
  const id = useId().replace(/:/g, '');
  return (
    <ChartFrame height={height}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 12, right: 12, bottom: 2, left: -7 }}>
          <defs>
            <linearGradient id={`fare-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5577F6" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#5577F6" stopOpacity={0.015} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="4 5" />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} minTickGap={16} padding={{ left: 12, right: 12 }} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={56} domain={domain} tickCount={5} allowDecimals={false} tickFormatter={(v: number) => Math.round(v).toLocaleString()} />
          <Tooltip content={<ChartTip format={(v) => `Lowest ${money(v, currency)}`} />} />
          <Area type="monotoneX" dataKey="lowest_price" stroke="#5577F6" strokeWidth={3} fill={`url(#fare-${id})`} dot={{ r: 4, fill: '#fff', stroke: '#5577F6', strokeWidth: 2.5 }} activeDot={{ r: 7, fill: '#5577F6', stroke: '#fff', strokeWidth: 3 }} animationDuration={850} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}



// Some older FareObservation rows pre-date airline_code being populated.
 // Resolve common carriers by their stored display name so they still receive
 // a real logo rather than a monogram. Unknown airlines use the provider code.
const AIRLINE_IATA_BY_NAME: Record<string, string> = {
  'aer lingus': 'EI',
  'air arabia': 'G9',
  'airblue': 'PA',
  'american airlines': 'AA',
  'british airways': 'BA',
  'cathay pacific': 'CX',
  'air canada': 'AC',
  'air france': 'AF',
  'air india': 'AI',
  'air new zealand': 'NZ',
  'alaska airlines': 'AS',
  'delta air lines': 'DL',
  'duffel airways': 'ZZ',
  'easyjet': 'U2',
  'egyptair': 'MS',
  'emirates': 'EK',
  'ethiopian airlines': 'ET',
  'etihad': 'EY',
  'etihad airways': 'EY',
  'finnair': 'AY',
  'flyadeal': 'F3',
  'flydubai': 'FZ',
  'flynas': 'XY',
  'iberia': 'IB',
  'jazeera airways': 'J9',
  'kenya airways': 'KQ',
  'kuwait airways': 'KU',
  'malaysia airlines': 'MH',
  'qantas': 'QF',
  'ryanair': 'FR',
  'serene air': 'ER',
  'swiss': 'LX',
  'virgin atlantic': 'VS',
  'vueling': 'VY',
  'wizz air': 'W6',
  'gulf air': 'GF',
  'gulf air bahrain': 'GF',
  'indigo': '6E',
  'indigo airlines': '6E',
  'japan airlines': 'JL',
  'klm': 'KL',
  'korean air': 'KE',
  'lufthansa': 'LH',
  'oman air': 'WY',
  'pakistan international airlines': 'PK',
  'pia': 'PK',
  'qatar airways': 'QR',
  'royal jordanian': 'RJ',
  'saudi arabian airlines': 'SV',
  'saudia': 'SV',
  'singapore airlines': 'SQ',
  'sri lankan airlines': 'UL',
  'srilankan airlines': 'UL',
  'thai airways': 'TG',
  'turkish airlines': 'TK',
  'united airlines': 'UA',
};

export type AirlineOfferRow = {
  name: string;
  value: number;
  airlineCode?: string | null;
  logoUrl?: string | null;
};

export function AirlineOffersChart({ data, limit }: { data: AirlineOfferRow[]; limit?: number }) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const max = Math.max(...sorted.map((item) => item.value), 1);
  const total = sorted.reduce((sum, item) => sum + item.value, 0);

  if (!sorted.length || total <= 0) {
    return <div className="chart-empty">No airline offer data available yet.</div>;
  }

  return (
    <div className="airline-offers-chart" role="list" aria-label="Airline offers">
      {sorted.slice(0, limit).map((item) => {
        const share = (item.value / total) * 100;
        const width = (item.value / max) * 100;
        const code = (item.airlineCode || AIRLINE_IATA_BY_NAME[item.name.trim().toLowerCase()] || '').toUpperCase();
        return (
          <div className="airline-offer-row" role="listitem" key={item.name}>
            <AirlineLogo
              name={item.name}
              src={item.logoUrl}
              fallbacks={code ? [
                `https://assets.duffel.com/img/airlines/for-light-background/full-color-logo/${code}.svg`,
                `https://images.kiwi.com/airlines/64/${code}.png`,
              ] : []}
              size={38}
            />
            <span className="airline-offer-name" title={item.name}>{item.name}</span>
            <span
              className="airline-offer-track"
              role="img"
              aria-label={`${item.name}: ${item.value.toLocaleString()} offers`}
            >
              <span style={{ width: `${width}%` }} />
            </span>
            <strong className="airline-offer-count">{item.value.toLocaleString()} offers</strong>
            <span className="airline-offer-share">{Math.round(share)}%</span>
          </div>
        );
      })}
    </div>
  );
}

export function HorizontalBars({ data, valueLabel }: { data: { name: string; value: number; tipLabel?: string }[]; valueLabel: (v: number) => string }) {
  const id = useId().replace(/:/g, '');
  return (
    <ChartFrame height={Math.max(135, data.length * 39 + 14)}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 3, right: 20, bottom: 2, left: 0 }} barCategoryGap={11}>
          <defs>
            <linearGradient id={`horizontal-bar-${id}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#2868F5" />
              <stop offset="100%" stopColor="#13A995" />
            </linearGradient>
          </defs>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey="name" tick={{ ...AXIS, fill: '#526078', fontSize: 12 }} tickLine={false} axisLine={false} width={116} />
          <Tooltip cursor={false} content={<ChartTip format={(v) => valueLabel(v)} />} />
          <Bar
            dataKey="value"
            fill={`url(#horizontal-bar-${id})`}
            radius={[7, 7, 7, 7]}
            maxBarSize={19}
            activeBar={false}
            animationDuration={750}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function Donut({ data, centerLabel }: { data: { name: string; value: number }[]; centerLabel: string }) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (!data.length || total <= 0) {
    return <div className="donut-wrap"><div className="chart-empty">No preference data available yet.</div></div>;
  }
  return (
    <div className="donut-wrap">
      <div className="chart-box donut" style={{ height: 168, width: 168, position: 'relative', flex: '0 0 168px' }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={49} outerRadius={75} paddingAngle={data.length > 1 ? 3 : 0} stroke="#fff" strokeWidth={3} isAnimationActive>
              {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
            </Pie>
            <Tooltip content={<ChartTip format={(v, row) => `${String(row.name)}: ${v} (${Math.round((v / total) * 100)}%)`} />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center"><b>{total.toLocaleString()}</b><small>{centerLabel}</small></div>
      </div>
      <ul className="legend">
        {data.map((d, i) => (
          <li key={d.name}>
            <i style={{ background: PALETTE[i % PALETTE.length], width: 9, height: 9, borderRadius: 3, boxShadow: `0 0 0 3px ${PALETTE[i % PALETTE.length]}18` }} />
            <span>{d.name}</span><b>{Math.round((d.value / total) * 100)}%</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ColumnChart({ data, valueLabel }: { data: { name: string; value: number }[]; valueLabel: (v: number) => string }) {
  const id = useId().replace(/:/g, '');
  return (
    <ChartFrame height={220}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 12, right: 8, bottom: 2, left: -18 }} barCategoryGap={13}>
          <defs>
            <linearGradient id={`column-bar-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2868F5" />
              <stop offset="100%" stopColor="#13A995" />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="4 5" />
          <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={false} interval="preserveStartEnd" />
          <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} />
          <Tooltip cursor={false} content={<ChartTip format={(v) => valueLabel(v)} />} />
          <Bar
            dataKey="value"
            fill={`url(#column-bar-${id})`}
            radius={[7, 7, 0, 0]}
            maxBarSize={38}
            activeBar={false}
            animationDuration={750}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/**
 * Lowest fare seen for each departure date around a chosen trip. The chosen date is
 * highlighted, the cheapest date is green, and dates nobody searched are left as gaps
 * rather than guessed.
 */
export function DepartureFareChart({ days, selected, currency, height = 230 }: {
  days: { date: string; price: number | null; stale?: boolean }[]; selected: string; currency: string; height?: number;
}) {
  const priced = days.filter((d) => d.price != null).map((d) => d.price!);
  const cheapest = priced.length ? Math.min(...priced) : null;
  const data = days.map((d) => {
    const dt = new Date(`${d.date}T12:00:00`);
    return {
      ...d,
      label: dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
      tipLabel: `${dt.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}${d.date === selected ? ' · your date' : ''}${d.stale ? ' · older observation' : ''}`,
    };
  });
  const [lo, hi] = priced.length ? priceDomain(priced) : [0, 1];
  return (
    <ChartFrame height={height}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 12, right: 8, bottom: 2, left: -7 }} barCategoryGap="22%">
          <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="4 5" />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={18} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={56} domain={[Math.max(0, lo), hi]} tickCount={5} allowDecimals={false} tickFormatter={(v: number) => Math.round(v).toLocaleString()} />
          <Tooltip cursor={{ fill: 'rgba(85,119,246,.06)' }} content={<ChartTip format={(v) => `Lowest ${money(v, currency)}`} />} />
          <Bar dataKey="price" radius={[6, 6, 2, 2]} maxBarSize={26} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.date} fill={d.date === selected ? '#5577F6' : d.price === cheapest ? '#16B8A6' : '#C7D3F5'} fillOpacity={d.stale ? 0.55 : 1} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/** Average daytime high per month; the best months to visit are green, the rest blue. */
export function ClimateChart({ months, best, height = 220 }: {
  months: { name: string; avg_high_c: number; avg_low_c: number | null; rainy_days: number; precip_mm: number }[]; best: string[]; height?: number;
}) {
  const data = months.map((m) => ({ ...m, tipLabel: `${m.name} · low ${m.avg_low_c ?? '–'}°C · ${m.rainy_days} rainy day${m.rainy_days === 1 ? '' : 's'} · ${m.precip_mm} mm` }));
  return (
    <ChartFrame height={height}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 12, right: 8, bottom: 2, left: -18 }} barCategoryGap="20%">
          <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="4 5" />
          <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={false} interval={0} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}°`} />
          <Tooltip cursor={{ fill: 'rgba(85,119,246,.06)' }} content={<ChartTip format={(v) => `Average high ${v}°C`} />} />
          <Bar dataKey="avg_high_c" radius={[6, 6, 2, 2]} maxBarSize={30} isAnimationActive={false}>
            {data.map((m) => <Cell key={m.name} fill={best.includes(m.name) ? '#16B8A6' : '#7B97F8'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function DailyPriceChart({ points, currency }: { points: { date: string; lowest_price: number; offers: number; searches: number }[]; currency: string }) {
  const data = points.map((p) => ({
    ...p,
    label: new Date(`${p.date}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
    tipLabel: `${p.date} · ${p.offers} offers in ${p.searches} search${p.searches === 1 ? '' : 'es'}`,
  }));
  const id = useId().replace(/:/g, '');
  return (
    <ChartFrame height={230}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 12, right: 12, bottom: 2, left: -7 }}>
          <defs>
            <linearGradient id={`daily-fare-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#9874F5" stopOpacity={0.24} />
              <stop offset="100%" stopColor="#9874F5" stopOpacity={0.015} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="4 5" />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} minTickGap={16} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={56} domain={priceDomain(points.map((p) => p.lowest_price))} tickCount={5} allowDecimals={false} tickFormatter={(v: number) => Math.round(v).toLocaleString()} />
          <Tooltip content={<ChartTip format={(v) => `Lowest ${money(v, currency)}`} />} />
          <Area type="monotoneX" dataKey="lowest_price" stroke="#2868F5" strokeWidth={3} fill={`url(#daily-fare-${id})`} dot={{ r: 4, fill: '#fff', stroke: '#2868F5', strokeWidth: 2.5 }} activeDot={{ r: 7, fill: '#2868F5', stroke: '#fff', strokeWidth: 3 }} animationDuration={850} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}


/** Departure-month share chart: one donut with a data-derived legend. */
export function DepartureMonthsChart({ data }: { data: { name: string; value: number }[] }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const [hoveredMonth, setHoveredMonth] = useState<{
    name: string;
    value: number;
    color: string;
    share: number;
  } | null>(null);
  const monthColors = ['#5278F5', '#12A995', '#F0A05A', '#9474E8', '#D96C9A', '#3D9BCB'];

  if (!data.length || total <= 0) {
    return <div className="chart-empty">No departure date data available yet.</div>;
  }

  const chartData = data.map((item, index) => ({
    ...item,
    color: monthColors[index % monthColors.length],
    share: (item.value / total) * 100,
  }));

  return (
    <div className="departure-months-chart">
      <div className="departure-months-donut">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              innerRadius={66}
              outerRadius={78}
              paddingAngle={chartData.length > 1 ? 2 : 0}
              cornerRadius={2}
              stroke="none"
              strokeWidth={0}
              isAnimationActive
              onMouseEnter={(entry: { name: string; value: number; color: string; share: number }) =>
                setHoveredMonth(entry)
              }
              onMouseLeave={() => setHoveredMonth(null)}
            >
              {chartData.map((item, index) => (
                <Cell key={`${item.name}-${index}`} fill={item.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="departure-months-center">
          <b>{(hoveredMonth?.value ?? total).toLocaleString()}</b>
          <span>
            {hoveredMonth
              ? `${hoveredMonth.name} · ${Math.round(hoveredMonth.share)}%`
              : 'Total searches'}
          </span>
        </div>
      </div>

      <div className="departure-months-legend">
        {chartData.map((item) => (
          <div className="departure-months-legend-row" key={item.name}>
            <span className="departure-months-swatch" style={{ background: item.color }} />
            <span className="departure-months-name">{item.name}</span>
            <span className="departure-months-count">{item.value.toLocaleString()}</span>
            <b className="departure-months-share">{Math.round(item.share)}%</b>
          </div>
        ))}
      </div>
    </div>
  );
}
