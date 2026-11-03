// Lightweight SVG illustrations so the UI needs no image assets.
import { useId, useState } from 'react';

export type CityTone = 'dubai' | 'istanbul' | 'london' | 'bangkok' | 'doha' | 'singapore' | 'kualalumpur' | 'jeddah' | 'generic';

export function HeroArt() {
  // Original illustration of a twin-engine wide-body airliner climbing out.
  return (
    <svg className="hero-art" viewBox="0 0 900 460" aria-hidden="true" preserveAspectRatio="xMaxYMid slice">
      <defs>
        <linearGradient id="ha-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--plane-hi)" />
          <stop offset="55%" stopColor="var(--plane-hi)" />
          <stop offset="100%" stopColor="var(--plane-lo)" />
        </linearGradient>
        <linearGradient id="ha-belly" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--plane-lo)" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--plane-shade)" stopOpacity=".9" />
        </linearGradient>
        <linearGradient id="ha-wing" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--plane-hi)" />
          <stop offset="100%" stopColor="var(--plane-shade)" />
        </linearGradient>
        <linearGradient id="ha-tail" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#3b8bff" />
          <stop offset="100%" stopColor="#0b4fd1" />
        </linearGradient>
        <linearGradient id="ha-engine" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--plane-hi)" />
          <stop offset="100%" stopColor="var(--plane-shade)" />
        </linearGradient>
        <radialGradient id="ha-glow" cx="70%" cy="20%" r="60%">
          <stop offset="0%" stopColor="var(--hero-glow)" stopOpacity=".9" />
          <stop offset="100%" stopColor="var(--hero-glow)" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ha-trail" x1="1" y1="0" x2="0" y2="0">
          <stop offset="0%" stopColor="var(--cloud)" stopOpacity=".85" />
          <stop offset="100%" stopColor="var(--cloud)" stopOpacity="0" />
        </linearGradient>
        <filter id="ha-blur" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="16" /></filter>
        <filter id="ha-soft" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="1.2" /></filter>
        <filter id="ha-shadow" x="-10%" y="-10%" width="130%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="12" floodColor="#0b2a5a" floodOpacity=".18" /></filter>
      </defs>

      <rect width="900" height="460" fill="url(#ha-glow)" />
      <g className="hero-clouds" filter="url(#ha-blur)">
        <ellipse cx="140" cy="420" rx="220" ry="54" />
        <ellipse cx="470" cy="440" rx="260" ry="58" />
        <ellipse cx="820" cy="400" rx="200" ry="66" />
        <ellipse cx="700" cy="300" rx="120" ry="26" opacity=".6" />
        <ellipse cx="300" cy="300" rx="110" ry="20" opacity=".45" />
      </g>

      {/* contrails */}
      <path d="M150 312 L520 196" stroke="url(#ha-trail)" strokeWidth="5" strokeLinecap="round" opacity=".7" filter="url(#ha-soft)" />
      <path d="M170 336 L540 220" stroke="url(#ha-trail)" strokeWidth="5" strokeLinecap="round" opacity=".55" filter="url(#ha-soft)" />

      <g transform="translate(470 118) rotate(-17)" filter="url(#ha-shadow)">
        {/* far wing and engine */}
        <path d="M232 58 L190 -18 L208 -21 L300 52 Z" fill="var(--plane-shade)" opacity=".9" />
        <rect x="196" y="12" width="46" height="17" rx="8.5" fill="var(--plane-shade)" opacity=".85" />
        {/* horizontal stabiliser (far) */}
        <path d="M44 40 L10 8 L24 6 L74 36 Z" fill="var(--plane-shade)" opacity=".85" />
        {/* vertical fin with livery */}
        <path d="M30 34 L-8 -52 C-6 -56 2 -58 8 -56 L92 30 Z" fill="url(#ha-tail)" />
        <path d="M14 -18 L56 18" stroke="#ffffff" strokeOpacity=".55" strokeWidth="3" strokeLinecap="round" />
        <path d="M2 -38 L68 22" stroke="#ffffff" strokeOpacity=".25" strokeWidth="1.5" />
        {/* fuselage */}
        <path d="M0 50 C2 32 26 26 70 26 L380 26 C420 26 448 34 466 46 C472 50 472 56 466 60 C448 70 420 76 380 76 L72 76 C28 76 2 68 0 50 Z" fill="url(#ha-body)" />
        <path d="M24 64 C60 74 120 76 200 76 L380 76 C418 76 446 70 464 60 C448 72 420 80 380 80 L72 80 C40 80 26 72 24 64 Z" fill="url(#ha-belly)" />
        {/* cheatline and windows */}
        <path d="M60 62 L452 56" stroke="var(--blue)" strokeWidth="3.2" strokeLinecap="round" opacity=".85" />
        <path d="M80 66 L440 61" stroke="#0b4fd1" strokeWidth="1.2" strokeLinecap="round" opacity=".5" />
        {Array.from({ length: 30 }, (_, i) => (
          <rect key={i} x={98 + i * 10.6} y={40 - i * 0.12} width="5.2" height="7" rx="2.6" fill="var(--plane-window)" opacity=".78" />
        ))}
        {/* doors */}
        {[86, 214, 352].map((x) => <rect key={x} x={x} y="34" width="9" height="22" rx="3" fill="none" stroke="var(--plane-shade)" strokeWidth="1.2" />)}
        {/* cockpit */}
        <path d="M430 36 C446 38 458 43 464 48 L446 48 C442 44 437 40 430 36 Z" fill="var(--plane-window)" opacity=".85" />
        <path d="M424 34 C428 36 431 38 433 41" stroke="var(--plane-window)" strokeWidth="1.4" opacity=".5" />
        {/* near wing */}
        <path d="M222 62 L150 176 L178 180 L314 70 Z" fill="url(#ha-wing)" />
        <path d="M150 176 L142 192 L156 190 L178 180 Z" fill="var(--blue)" opacity=".85" />
        <path d="M200 98 L270 76 M182 128 L246 96 M166 154 L224 116" stroke="var(--plane-shade)" strokeWidth="1" opacity=".7" />
        {/* near engine */}
        <rect x="192" y="96" width="74" height="28" rx="14" fill="url(#ha-engine)" />
        <ellipse cx="264" cy="110" rx="5" ry="13" fill="var(--plane-window)" opacity=".8" />
        <ellipse cx="264" cy="110" rx="2.4" ry="8" fill="var(--plane-shade)" />
        <path d="M200 104 L250 104" stroke="#ffffff" strokeOpacity=".6" strokeWidth="2" strokeLinecap="round" />
        <rect x="186" y="104" width="10" height="12" rx="4" fill="var(--plane-shade)" />
        {/* near horizontal stabiliser */}
        <path d="M52 60 L16 98 L32 100 L86 66 Z" fill="url(#ha-wing)" />
        {/* highlight */}
        <path d="M80 32 L400 30" stroke="#ffffff" strokeOpacity=".7" strokeWidth="2" strokeLinecap="round" />
      </g>
    </svg>
  );
}

const skylines: Record<CityTone, JSX.Element> = {
  generic: (
    <>
      <rect x="18" y="82" width="24" height="38" rx="2" opacity=".45" />
      <rect x="48" y="58" width="20" height="62" rx="2" opacity=".7" />
      <rect x="74" y="72" width="26" height="48" rx="2" opacity=".55" />
      <path d="M106 120 V44 L118 30 L130 44 V120 Z" />
      <rect x="138" y="64" width="22" height="56" rx="2" opacity=".75" />
      <path d="M166 120 V80 Q178 64 190 80 V120 Z" opacity=".55" />
      <rect x="196" y="88" width="30" height="32" rx="2" opacity=".4" />
    </>
  ),
  dubai: (
    <>
      <rect x="20" y="78" width="22" height="42" rx="2" opacity=".55" />
      <rect x="46" y="62" width="18" height="58" rx="2" opacity=".7" />
      <path d="M70 120 V70 Q78 52 86 70 V120 Z" opacity=".6" />
      <polygon points="104,120 109,70 114,46 117,10 120,46 125,70 130,120" />
      <rect x="138" y="58" width="16" height="62" rx="2" opacity=".75" />
      <path d="M160 120 V60 Q172 40 184 60 V120 Z" opacity=".6" />
      <rect x="190" y="74" width="22" height="46" rx="2" opacity=".5" />
      <rect x="216" y="86" width="16" height="34" rx="2" opacity=".4" />
    </>
  ),
  istanbul: (
    <>
      <rect x="14" y="88" width="30" height="32" opacity=".45" />
      <rect x="54" y="40" width="5" height="80" opacity=".85" />
      <polygon points="53,40 56.5,22 60,40" />
      <path d="M72 120 V92 A48 34 0 0 1 168 92 V120 Z" />
      <path d="M66 120 V100 A18 14 0 0 1 102 100 V120 Z" opacity=".7" />
      <path d="M138 120 V100 A18 14 0 0 1 174 100 V120 Z" opacity=".7" />
      <rect x="117" y="48" width="6" height="12" opacity=".9" />
      <rect x="182" y="40" width="5" height="80" opacity=".85" />
      <polygon points="181,40 184.5,22 188,40" />
      <rect x="198" y="82" width="28" height="38" opacity=".45" />
    </>
  ),
  london: (
    <>
      <rect x="18" y="80" width="26" height="40" opacity=".45" />
      <rect x="50" y="40" width="16" height="80" />
      <polygon points="48,40 58,14 68,40" />
      <circle cx="58" cy="50" r="5" fill="var(--art-bg)" />
      <rect x="72" y="86" width="30" height="34" opacity=".55" />
      <g fill="none" stroke="currentColor" strokeWidth="3" opacity=".9">
        <circle cx="160" cy="66" r="40" />
        <path d="M160 26 V106 M120 66 H200 M132 38 L188 94 M188 38 L132 94" strokeWidth="1.5" />
      </g>
      <path d="M150 120 L160 66 L170 120 Z" opacity=".8" />
      <rect x="206" y="78" width="22" height="42" opacity=".5" />
    </>
  ),
  bangkok: (
    <>
      <rect x="14" y="90" width="34" height="30" opacity=".4" />
      <polygon points="70,120 82,80 94,120" opacity=".6" />
      <polygon points="96,120 102,96 138,96 144,120" />
      <polygon points="104,96 110,74 130,74 136,96" opacity=".92" />
      <polygon points="112,74 116,52 124,52 128,74" opacity=".85" />
      <polygon points="117,52 120,14 123,52" />
      <polygon points="146,120 158,82 170,120" opacity=".6" />
      <rect x="186" y="88" width="40" height="32" opacity=".4" />
    </>
  ),
  doha: (
    <>
      <rect x="18" y="72" width="20" height="48" rx="3" opacity=".5" />
      <path d="M46 120 V50 Q56 30 66 50 V120 Z" opacity=".75" />
      <path d="M76 120 V30 Q90 6 104 30 V120 Z" />
      <rect x="112" y="56" width="18" height="64" rx="9" opacity=".7" />
      <polygon points="138,120 146,42 162,42 170,120" opacity=".85" />
      <rect x="178" y="66" width="18" height="54" rx="2" opacity=".6" />
      <path d="M202 120 V78 Q212 66 222 78 V120 Z" opacity=".45" />
    </>
  ),
  singapore: (
    <>
      <rect x="40" y="46" width="22" height="74" />
      <rect x="82" y="46" width="22" height="74" />
      <rect x="124" y="46" width="22" height="74" />
      <path d="M30 40 H160 Q166 40 162 46 H30 Z" />
      <g opacity=".7">
        <rect x="186" y="78" width="4" height="42" />
        <path d="M176 78 Q188 62 200 78 Z" />
        <rect x="212" y="88" width="4" height="32" />
        <path d="M203 88 Q214 74 225 88 Z" />
      </g>
      <rect x="10" y="90" width="22" height="30" opacity=".4" />
    </>
  ),
  kualalumpur: (
    <>
      <rect x="20" y="84" width="26" height="36" opacity=".45" />
      <path d="M84 120 V40 L94 28 L104 40 V120 Z" />
      <rect x="93" y="8" width="2" height="22" />
      <path d="M136 120 V40 L146 28 L156 40 V120 Z" />
      <rect x="145" y="8" width="2" height="22" />
      <rect x="104" y="62" width="32" height="5" opacity=".9" />
      <rect x="176" y="70" width="20" height="50" opacity=".55" />
      <rect x="202" y="88" width="24" height="32" opacity=".4" />
    </>
  ),
  jeddah: (
    <>
      <rect x="20" y="80" width="30" height="40" opacity=".45" />
      <rect x="62" y="34" width="22" height="86" opacity=".8" />
      <path d="M150 120 V60" stroke="currentColor" strokeWidth="3" />
      <path d="M150 60 Q130 20 156 6 Q140 36 150 60 Z" opacity=".7" />
      <rect x="170" y="64" width="24" height="56" opacity=".6" />
      <rect x="100" y="86" width="30" height="34" opacity=".5" />
    </>
  ),
};

export function CityArt({ tone }: { tone: CityTone }) {
  return (
    <svg className={`city-art tone-${tone}`} viewBox="0 0 240 130" aria-hidden="true" preserveAspectRatio="xMidYMax slice">
      <rect width="240" height="130" fill="var(--art-bg)" />
      <circle cx="186" cy="36" r="18" className="city-sun" />
      <g fill="currentColor">{skylines[tone]}</g>
      <rect y="120" width="240" height="10" fill="currentColor" opacity=".25" />
    </svg>
  );
}

// Deterministic pseudo-random numbers so each city always gets the same skyline.
function seeded(seed: string) {
  let a = [...seed].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) | 0, 0x9e3779b9);
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function skylineRow(rand: () => number, base: number, minH: number, maxH: number) {
  const shapes: JSX.Element[] = [];
  for (let x = -6; x < 246;) {
    const w = 10 + Math.round(rand() * 22);
    const h = minH + Math.round(rand() * (maxH - minH));
    const top = base - h;
    const kind = rand();
    if (kind < 0.12) {
      // dome
      shapes.push(<path key={x} d={`M${x} ${base} V${top + w / 2} A${w / 2} ${w / 2} 0 0 1 ${x + w} ${top + w / 2} V${base} Z`} />);
    } else if (kind < 0.22) {
      // spire
      shapes.push(<path key={x} d={`M${x} ${base} V${top + 10} L${x + w / 2} ${top - 8} L${x + w} ${top + 10} V${base} Z`} />);
    } else if (kind < 0.34) {
      // stepped tower with antenna
      shapes.push(<path key={x} d={`M${x} ${base} V${top + 12} H${x + 3} V${top} H${x + w - 3} V${top + 12} H${x + w} V${base} Z M${x + w / 2 - 0.8} ${top} v-9 h1.6 v9 Z`} />);
    } else {
      shapes.push(<rect key={x} x={x} y={top} width={w} height={h} rx="1.5" />);
    }
    x += w + Math.round(rand() * 4);
  }
  return shapes;
}

/** Designed fallback for destinations without a freely licensed photo: a skyline generated from the city's name. */
export function DestinationArt({ seed, tone = 'generic' }: { seed: string; tone?: CityTone }) {
  const id = useId().replace(/:/g, '');
  const rand = seeded(seed);
  const far = skylineRow(rand, 112, 18, 52);
  const near = tone === 'generic' ? skylineRow(rand, 122, 14, 66) : null;
  const sunX = 150 + Math.round(rand() * 70);
  return (
    <svg className="dest-art-fallback" viewBox="0 0 240 130" aria-hidden="true" preserveAspectRatio="xMidYMax slice">
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--sky-top)" />
          <stop offset="100%" stopColor="var(--sky-bottom)" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx=".5" cy=".5" r=".5">
          <stop offset="0%" stopColor="var(--sun)" stopOpacity=".95" />
          <stop offset="100%" stopColor="var(--sun)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="240" height="130" fill={`url(#${id}-sky)`} />
      <circle cx={sunX} cy="40" r="34" fill={`url(#${id}-glow)`} />
      <circle cx={sunX} cy="40" r="11" fill="var(--sun)" />
      <g fill="currentColor" opacity=".28">{far}</g>
      <g fill="currentColor" opacity=".78">{near ?? skylines[tone]}</g>
      <rect y="120" width="240" height="10" fill="currentColor" />
      <path d="M0 125 H240" stroke="var(--sky-top)" strokeOpacity=".35" strokeDasharray="14 10" />
    </svg>
  );
}

export function RouteMapArt({ from, to }: { from: string; to: string }) {
  return (
    <svg className="route-map-art" viewBox="0 0 300 300" role="img" aria-label={`Route from ${from} to ${to}`}>
      <rect width="300" height="300" className="map-water" />
      <g className="map-land">
        <path d="M-10 0 H180 C170 30 150 40 140 70 C128 102 96 96 82 128 C70 158 40 150 20 178 C8 196 -4 200 -10 204 Z" />
        <path d="M200 0 H310 V140 C290 128 268 136 252 118 C236 100 246 72 228 56 C214 44 196 30 200 0 Z" />
        <path d="M150 200 C180 186 214 196 236 220 C260 246 292 236 310 250 V310 H120 C122 270 132 214 150 200 Z" />
        <path d="M30 236 C50 226 72 238 70 256 C68 274 40 280 28 266 C18 254 20 242 30 236 Z" />
      </g>
      <g className="map-grid">
        {[60, 120, 180, 240].map((v) => <path key={`h${v}`} d={`M0 ${v} H300`} />)}
        {[60, 120, 180, 240].map((v) => <path key={`v${v}`} d={`M${v} 0 V300`} />)}
      </g>
      <path className="map-route" d="M64 96 Q150 110 226 214" />
      <g transform="translate(150 132) rotate(40)" className="map-plane">
        <path d="M-9 0 L9 0 M0 -2 L-5 -9 M0 2 L-5 9 M-8 -3 L-8 3" />
      </g>
      <circle cx="64" cy="96" r="6" className="map-dot" />
      <circle cx="226" cy="214" r="6" className="map-dot" />
      <g className="map-pill">
        <rect x="34" y="62" width="60" height="24" rx="6" />
        <text x="64" y="78">{from}</text>
        <rect x="196" y="228" width="60" height="24" rx="6" />
        <text x="226" y="244">{to}</text>
      </g>
    </svg>
  );
}

const airlineColors: Record<string, string> = {
  emirates: '#d71920',
  'qatar airways': '#5c0632',
  'etihad airways': '#b8862a',
  etihad: '#b8862a',
  flydubai: '#f26b21',
  'air arabia': '#e1251b',
  'turkish airlines': '#c8102e',
  'pakistan international airlines': '#00693e',
  pia: '#00693e',
  saudia: '#00754a',
  'gulf air': '#9b7b45',
  'oman air': '#86683a',
  'british airways': '#1d4f91',
  'singapore airlines': '#1d2f6f',
  'duffel airways': '#5b4dd6',
  airblue: '#0a5aa5',
  serene: '#4b2c84',
};

export function AirlineLogo({ name, size = 40, src, fallbacks = [] }: { name: string; size?: number; src?: string | null; fallbacks?: string[] }) {
  // Try each candidate URL in turn; a clearly generic monogram only when none loads.
  // Duffel's logo set has gaps; for its URLs also try other sources for the same airline code.
  const code = src?.match(/full-color-logo\/([A-Z0-9]{2})\.svg$/)?.[1];
  const derived = code ? [`https://images.kiwi.com/airlines/64/${code}.png`, `https://pics.avs.io/120/120/${code}.png`] : [];
  const candidates = [src, ...fallbacks, ...derived].filter((u): u is string => !!u);
  const [failed, setFailed] = useState(0);
  const key = name.trim().toLowerCase();
  const current = candidates[failed];
  if (current) {
    return (
      <span className="airline-logo has-img" style={{ width: size, height: size }}>
        <img key={current} src={current} alt="" width={size} height={size} loading="lazy" decoding="async" onError={() => setFailed((n) => n + 1)} />
      </span>
    );
  }
  let color = airlineColors[key];
  if (!color) {
    let hash = 0;
    for (const ch of key) hash = (hash * 31 + ch.charCodeAt(0)) % 360;
    color = `hsl(${hash} 55% 42%)`;
  }
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '✈';
  return (
    <span className="airline-logo" style={{ background: color, width: size, height: size, fontSize: size * 0.36 }} aria-hidden="true">
      {initials}
    </span>
  );
}
