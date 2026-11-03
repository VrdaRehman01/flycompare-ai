import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Camera } from 'lucide-react';
import { api } from '../lib/api';
import { safeUrl } from '../lib/safeUrl';

type Photo = {
  available: boolean; pending?: boolean; illustrative?: boolean; url?: string; url_2x?: string | null;
  artist?: string; licence?: string; file_url?: string | null; source?: string; subject?: string;
};

// One request per distinct photo, shared by every card that shows it.
const cache = new Map<string, Promise<Photo>>();
function load(kind: 'article' | 'stay', q: string, seed: string, context: string): Promise<Photo> {
  const key = `${kind}|${q}|${context}|${kind === 'stay' ? seed : ''}`;
  if (!cache.has(key)) {
    const p = api<Photo>(`/api/media/photo?${new URLSearchParams({ kind, q, seed, context })}`)
      .then((r) => { if (r.pending) cache.delete(key); return r; })
      .catch(() => { cache.delete(key); return { available: false }; });
    cache.set(key, p);
  }
  return cache.get(key)!;
}

/**
 * A freely licensed photo for a sight, car model, vehicle or property type, loaded when
 * the card nears the viewport. Shows the author and licence, marks illustrative photos,
 * and falls back to a tinted illustration with `icon` when no photo is available.
 */
export function MediaPhoto({ kind = 'article', q, seed = '', context = '', icon, alt, className = '', eager, label }: {
  kind?: 'article' | 'stay'; q: string; seed?: string; context?: string; icon: ReactNode; alt: string; className?: string; eager?: boolean; label?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [broken, setBroken] = useState(false);
  useEffect(() => {
    setPhoto(null); setLoaded(false); setBroken(false);
    let live = true;
    const start = () => load(kind, q, seed, context).then((p) => { if (live) setPhoto(p); });
    const el = ref.current;
    if (eager || !el || typeof IntersectionObserver === 'undefined') { void start(); return () => { live = false; }; }
    const io = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) { io.disconnect(); void start(); } }, { rootMargin: '300px' });
    io.observe(el);
    return () => { live = false; io.disconnect(); };
  }, [kind, q, seed, context, eager]);
  const hue = [...`${q}${seed}`].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 17);
  const show = photo?.available && photo.url && !broken;
  return (
    <div ref={ref} className={`media-photo ${show && loaded ? 'is-photo' : 'is-art'} ${className}`} style={{ ['--media-hue' as string]: hue }}>
      <span className="media-art" aria-hidden="true">{icon}</span>
      {show && (
        <img src={photo.url} srcSet={photo.url_2x ? `${photo.url} 500w, ${photo.url_2x} 960w` : undefined} sizes="(max-width: 640px) 100vw, 420px"
          alt={alt} loading={eager ? 'eager' : 'lazy'} decoding="async" className={loaded ? 'loaded' : ''} onLoad={() => setLoaded(true)} onError={() => setBroken(true)} />
      )}
      {photo === null && <span className="photo-shimmer" aria-hidden="true" />}
      {label && <span className="media-label">{label}</span>}
      {show && loaded && (
        <a className="media-credit" href={safeUrl(photo.file_url)} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}
          title={`${photo.illustrative ? 'Illustrative photo. ' : ''}Photo: ${photo.artist} · ${photo.licence} · via ${photo.source}`}>
          <Camera size={10} aria-hidden="true" />{photo.illustrative ? 'Illustrative · ' : ''}{photo.artist?.slice(0, 22)} · {photo.licence}
        </a>
      )}
    </div>
  );
}
