import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Camera, CheckCircle2, Heart, Search } from 'lucide-react';
import { DestinationArt, type CityTone } from '../illustrations';
import { api } from '../lib/api';
import { createImageStore } from '../lib/destinationImages';
import type { Destination, DestinationImage } from '../lib/types';
import { availabilityLabel } from './Discovery';
import { safeUrl } from '../lib/safeUrl';

const TONES: Record<string, CityTone> = {
  'Dubai|AE': 'dubai', 'Istanbul|TR': 'istanbul', 'London|GB': 'london', 'Bangkok|TH': 'bangkok', 'Doha|QA': 'doha',
  'Singapore|SG': 'singapore', 'Kuala Lumpur|MY': 'kualalumpur', 'Jeddah|SA': 'jeddah',
};

const images = createImageStore((keys) => api<DestinationImage[]>(`/api/destinations/images?keys=${encodeURIComponent(keys.join(','))}`));

/** Photo info for a destination, looked up once its element is near the viewport. */
function useDestinationImage(key: string, eager?: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [img, setImg] = useState<DestinationImage | undefined>(() => images.get(key));
  useEffect(() => {
    setImg(images.get(key));
    const unsubscribe = images.subscribe(key, setImg);
    const el = ref.current;
    if (eager || !el || typeof IntersectionObserver === 'undefined') {
      images.request(key);
      return unsubscribe;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { images.request(key); observer.disconnect(); }
    }, { rootMargin: '400px' });
    observer.observe(el);
    return () => { observer.disconnect(); unsubscribe(); };
  }, [key, eager]);
  return { ref, img };
}

export function DestinationPhoto({ dest, eager }: { dest: Pick<Destination, 'key' | 'city' | 'country'>; eager?: boolean }) {
  const { ref, img } = useDestinationImage(dest.key, eager);
  const [loaded, setLoaded] = useState(false);
  const [broken, setBroken] = useState(false);
  useEffect(() => { setLoaded(false); setBroken(false); }, [img?.url]);
  const photo = img?.available && img.url && !broken ? img : null;
  const hue = [...dest.country].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
  // loading: lookup or download in progress; art: no freely licensed photo (or it failed to load).
  const state = photo ? (loaded ? 'photo' : 'loading') : !img || img.pending ? 'loading' : 'art';
  return (
    <div ref={ref} className={`dest-photo is-${state}`} style={{ ['--art-hue' as string]: hue }}>
      {!(photo && loaded) && <DestinationArt seed={dest.key} tone={TONES[dest.key]} />}
      {photo && (
        <img src={photo.url} srcSet={photo.url_2x ? `${photo.url} 500w, ${photo.url_2x} 960w` : undefined}
          sizes="(max-width: 640px) 100vw, 400px" alt={`${dest.city}, ${dest.country}`}
          loading={eager ? 'eager' : 'lazy'} decoding="async" className={loaded ? 'loaded' : undefined}
          onLoad={() => setLoaded(true)} onError={() => setBroken(true)} />
      )}
      {state === 'loading' && <span className="photo-shimmer" aria-hidden="true" />}
      {photo && loaded && (
        <a className="photo-credit" href={safeUrl(photo.file_url)} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}
          title={`Photo: ${photo.artist} · ${photo.licence} · via ${photo.source ?? 'Wikimedia Commons'}`}>
          <Camera size={10} aria-hidden="true" /> {photo.artist?.slice(0, 28)} · {photo.licence}
        </a>
      )}
    </div>
  );
}

export function DestinationCard({ d, fav, onFav, onExplore, onSearch }: { d: Destination; fav: boolean; onFav: () => void; onExplore: () => void; onSearch?: () => void }) {
  const seen = d.availability.status === 'seen_in_searches';
  return (
    <article className="card dest-card">
      <button className="dest-art" onClick={onExplore} aria-label={`Plan flights to ${d.city}`}><DestinationPhoto dest={d} /></button>
      <button className={`heart floating ${fav ? 'on' : ''}`} onClick={onFav} aria-pressed={fav} aria-label={fav ? `Remove ${d.city} from favourites` : `Add ${d.city} to favourites`}><Heart size={15} /></button>
      <div className="dest-info">
        <span><b>{d.city}</b><small>{d.country} · {d.airports.slice(0, 3).map((a) => a.code).join(', ')}</small></span>
        <button className="dest-cta" onClick={onExplore}>Explore <ArrowUpRight size={14} /></button>
      </div>
      <div className="dest-meta">
        {d.themes.length > 0 && <span className="dest-tags">{d.themes.slice(0, 3).map((t) => <span key={t} className="tag">{t}</span>)}</span>}
        <small className={seen ? 'seen-text' : 'muted'}>{seen && <CheckCircle2 size={12} />} {availabilityLabel(d)}{d.distance_km != null ? ` · ${d.distance_km.toLocaleString()} km` : ''}</small>
        {onSearch && <button className="link-btn small" onClick={onSearch}><Search size={12} /> Search flights</button>}
      </div>
    </article>
  );
}
