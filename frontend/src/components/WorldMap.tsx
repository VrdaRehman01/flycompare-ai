// Interactive world map built with MapLibre GL.
// Basemap: Natural Earth country shapes (public domain) rendered locally, so no
// third-party tile service or API key is needed and colours follow the theme.
import { useEffect, useMemo, useRef, useState } from 'react';
import { LngLatBounds, Map as MlMap, Marker, NavigationControl, Popup, setWorkerUrl, type GeoJSONSource, type MapLayerMouseEvent } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { feature } from 'topojson-client';
import type { Topology } from 'topojson-specification';
import countriesUrl from 'world-atlas/countries-50m.json?url';
import { api } from '../lib/api';
import { fixAntimeridian, greatCircle } from '../lib/geo';
import type { AirportRef } from '../lib/types';
import { usePrefs } from '../state';

setWorkerUrl(workerUrl);

export type MapDestination = { code: string; city: string; country: string; lat: number; lon: number; status: 'seen' | 'suggestion'; direct?: boolean; label?: string };
export type MapRoute = { stops: AirportRef[] }; // origin, connection hubs…, destination

type Props = {
  origin?: AirportRef | null;
  destinations?: MapDestination[];
  selected?: string | null;
  route?: MapRoute | null;
  onSelect?: (code: string) => void;
  showAirports?: boolean;
  height?: number;
  caption?: string;
};

let countriesCache: Promise<GeoJSON.FeatureCollection> | null = null;
const loadCountries = () => (countriesCache ??= fetch(countriesUrl).then((r) => r.json()).then((topo: Topology) =>
  fixAntimeridian(feature(topo, topo.objects.countries) as unknown as GeoJSON.FeatureCollection)));
let airportsCache: Promise<GeoJSON.FeatureCollection> | null = null;
const loadAirports = () => (airportsCache ??= api<{ airports: [string, string, string, number, number][] }>('/api/airports/map').then((d) => ({
  type: 'FeatureCollection',
  features: d.airports.map(([code, city, country, lat, lon]) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: { code, city, country } })),
}) as GeoJSON.FeatureCollection).catch(() => { airportsCache = null; return { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection; }));

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const palette = () => ({
  water: css('--map-water'), land: css('--map-land'), border: css('--map-border'), blue: css('--blue'), accent: css('--map-accent'),
  muted: css('--muted'), surface: css('--surface'), ink: css('--ink'),
});
const fc = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });
const pt = (a: { lat?: number; lon?: number }): [number, number] => [a.lon ?? 0, a.lat ?? 0];
const escapeHtml = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

export default function WorldMap({ origin, destinations = [], selected, route, onSelect, showAirports = true, height = 420, caption }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const { theme } = usePrefs();
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Create the map once.
  useEffect(() => {
    if (!box.current) return;
    let cancelled = false;
    const p = palette();
    let m: MlMap;
    try {
      m = new MlMap({
        container: box.current,
        style: { version: 8, sources: {}, layers: [{ id: 'water', type: 'background', paint: { 'background-color': p.water } }] },
        center: [40, 20], zoom: 1.2, minZoom: 0.6, maxZoom: 9, renderWorldCopies: false, attributionControl: false,
        cooperativeGestures: true, dragRotate: false, pitchWithRotate: false,
      });
    } catch {
      setFailed(true);
      return;
    }
    map.current = m;
    m.touchZoomRotate.disableRotation();
    m.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    m.on('error', () => { /* tile-free style: ignore transient errors */ });
    m.on('load', async () => {
      const [countries, airports] = await Promise.all([loadCountries(), showAirports ? loadAirports() : Promise.resolve(fc([]))]);
      if (cancelled) return;
      m.addSource('countries', { type: 'geojson', data: countries });
      m.addLayer({ id: 'land', type: 'fill', source: 'countries', paint: { 'fill-color': p.land } });
      m.addLayer({ id: 'borders', type: 'line', source: 'countries', paint: { 'line-color': p.border, 'line-width': 0.6 } });
      m.addSource('airports', { type: 'geojson', data: airports });
      m.addLayer({ id: 'airports', type: 'circle', source: 'airports', paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, 1.4, 5, 3.5], 'circle-color': p.blue, 'circle-opacity': 0.55,
      } });
      m.addSource('routes', { type: 'geojson', data: fc([]) });
      m.addLayer({ id: 'routes-suggested', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'suggestion'], layout: { 'line-cap': 'round' },
        paint: { 'line-color': p.blue, 'line-width': 1, 'line-opacity': 0.35, 'line-dasharray': [2, 3] } });
      m.addLayer({ id: 'routes-seen', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'seen'], layout: { 'line-cap': 'round' },
        paint: { 'line-color': p.blue, 'line-width': 1.6, 'line-opacity': 0.8 } });
      m.addLayer({ id: 'routes-selected-glow', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'selected'], layout: { 'line-cap': 'round' },
        paint: { 'line-color': p.accent, 'line-width': 9, 'line-opacity': 0.22, 'line-blur': 6 } });
      m.addLayer({ id: 'routes-selected', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'selected'], layout: { 'line-cap': 'round' },
        paint: { 'line-color': p.accent, 'line-width': 2.6 } });
      m.addSource('dests', { type: 'geojson', data: fc([]) });
      m.addLayer({ id: 'dests-halo', type: 'circle', source: 'dests', paint: { 'circle-radius': 9, 'circle-color': p.blue, 'circle-opacity': 0.15 } });
      m.addLayer({ id: 'dests', type: 'circle', source: 'dests', paint: {
        'circle-radius': ['case', ['==', ['get', 'status'], 'seen'], 5, 4], 'circle-color': ['case', ['==', ['get', 'status'], 'seen'], p.blue, p.surface],
        'circle-stroke-color': p.blue, 'circle-stroke-width': 2,
      } });

      const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 10, className: 'map-popup' });
      const hover = (layer: string, html: (props: Record<string, string>) => string) => {
        m.on('mouseenter', layer, (e: MapLayerMouseEvent) => {
          m.getCanvas().style.cursor = 'pointer';
          const f = e.features?.[0];
          if (f) popup.setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number]).setHTML(html(f.properties as Record<string, string>)).addTo(m);
        });
        m.on('mouseleave', layer, () => { m.getCanvas().style.cursor = ''; popup.remove(); });
      };
      hover('airports', (pr) => `<b>${escapeHtml(pr.city)}, ${escapeHtml(pr.country)}</b><span>Airport ${escapeHtml(pr.code)}</span>`);
      hover('dests', (pr) => `<b>${escapeHtml(pr.city)}, ${escapeHtml(pr.country)} · ${escapeHtml(pr.code)}</b><span>${escapeHtml(pr.label)}</span>`);
      m.on('mousemove', 'routes-seen', (e) => {
        const f = e.features?.[0];
        if (f) popup.setLngLat(e.lngLat).setHTML(`<b>${escapeHtml(String(f.properties?.title))}</b><span>${escapeHtml(String(f.properties?.label))}</span>`).addTo(m);
      });
      m.on('mouseleave', 'routes-seen', () => popup.remove());
      const click = (e: MapLayerMouseEvent) => { const code = e.features?.[0]?.properties?.code; if (code) onSelectRef.current?.(String(code)); };
      m.on('click', 'dests', click);
      m.on('click', 'airports', click);
      setReady(true);
    });
    return () => { cancelled = true; markers.current.forEach((mk) => mk.remove()); m.remove(); map.current = null; };
  }, [showAirports]);

  // Recolour when the theme changes. Wait a frame: the theme provider updates
  // <html data-theme> in its own effect, which runs after this component's.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const frame = requestAnimationFrame(() => {
    const p = palette();
    m.setPaintProperty('water', 'background-color', p.water);
    m.setPaintProperty('land', 'fill-color', p.land);
    m.setPaintProperty('borders', 'line-color', p.border);
    m.setPaintProperty('airports', 'circle-color', p.blue);
    ['routes-suggested', 'routes-seen'].forEach((l) => m.setPaintProperty(l, 'line-color', p.blue));
    ['routes-selected', 'routes-selected-glow'].forEach((l) => m.setPaintProperty(l, 'line-color', p.accent));
    m.setPaintProperty('dests', 'circle-stroke-color', p.blue);
    m.setPaintProperty('dests', 'circle-color', ['case', ['==', ['get', 'status'], 'seen'], p.blue, p.surface]);
    m.setPaintProperty('dests-halo', 'circle-color', p.blue);
    });
    return () => cancelAnimationFrame(frame);
  }, [theme, ready]);

  const data = useMemo(() => {
    const routes: GeoJSON.Feature[] = [];
    if (origin?.lat != null) {
      for (const d of destinations) {
        if (d.code === selected && route) continue;
        routes.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: greatCircle(pt(origin), [d.lon, d.lat], 48) },
          properties: { kind: d.status === 'seen' ? 'seen' : 'suggestion', title: `${origin.code} → ${d.code}`, label: d.label ?? '' } });
      }
    }
    const stops = route?.stops.filter((s) => s.lat != null) ?? [];
    for (let i = 0; i < stops.length - 1; i++) {
      routes.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: greatCircle(pt(stops[i]), pt(stops[i + 1]), 64) }, properties: { kind: 'selected' } });
    }
    const dests: GeoJSON.Feature[] = destinations.map((d) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [d.lon, d.lat] },
      properties: { code: d.code, city: d.city, country: d.country, status: d.status, label: d.label ?? (d.status === 'seen' ? 'Seen in FlyCompare searches' : 'Suggestion — availability not checked') } }));
    return { routes: fc(routes), dests: fc(dests), stops };
  }, [origin, destinations, route, selected]);

  // Update data, markers and camera.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    (m.getSource('routes') as GeoJSONSource).setData(data.routes);
    (m.getSource('dests') as GeoJSONSource).setData(data.dests);
    markers.current.forEach((mk) => mk.remove());
    markers.current = [];
    const addMarker = (a: AirportRef, kind: string, text: string) => {
      const el = document.createElement('div');
      el.className = `map-marker ${kind}`;
      el.innerHTML = `<span class="map-marker-dot"></span><span class="map-marker-label">${escapeHtml(text)}</span>`;
      markers.current.push(new Marker({ element: el, anchor: 'left', offset: [-7, 0] }).setLngLat(pt(a)).addTo(m));
    };
    const stops = data.stops;
    if (stops.length) {
      // Later stops that repeat the origin (round trips) are not labelled twice.
      stops.forEach((s, i) => { if (i > 0 && s.code === stops[0].code) return; addMarker(s, i === 0 ? 'origin' : i === stops.length - 1 ? 'destination' : 'hub', `${s.city} · ${s.code}`); });
    } else if (origin?.lat != null) {
      addMarker(origin, 'origin', `${origin.city} · ${origin.code}`);
    }
    const sel = destinations.find((d) => d.code === selected);
    if (sel && !stops.length) addMarker({ code: sel.code, city: sel.city, country: sel.country, name: '', lat: sel.lat, lon: sel.lon }, 'destination', `${sel.city} · ${sel.code}`);

    const pts: [number, number][] = [...stops.map(pt), ...(origin?.lat != null ? [pt(origin)] : []), ...(stops.length ? [] : destinations.slice(0, 40).map((d) => [d.lon, d.lat] as [number, number]))];
    if (pts.length >= 2) {
      const b = new LngLatBounds(pts[0], pts[0]);
      pts.forEach((p) => b.extend(p));
      m.fitBounds(b, { padding: { top: 50, bottom: 40, left: 40, right: 60 }, maxZoom: 5, duration: 700 });
    } else if (pts.length === 1) {
      m.easeTo({ center: pts[0], zoom: 2.4, duration: 700 });
    }
  }, [data, ready, origin, destinations, selected]);

  if (failed) {
    return <div className="world-map map-fallback" style={{ height }}><p>The interactive map needs WebGL, which is unavailable in this browser.</p></div>;
  }
  return (
    <figure className="world-map" style={{ height }}>
      <div ref={box} className="world-map-canvas" role="region" aria-label={caption ?? 'Interactive world map'} />
      {!ready && <div className="map-loading"><span className="spinner dark" /> Loading map…</div>}
      <figcaption className="map-legend">
        {route ? <span><i className="lg selected" /> Selected route</span> : null}
        {destinations.some((d) => d.status === 'seen') && <span><i className="lg seen" /> Seen in searches</span>}
        {destinations.some((d) => d.status === 'suggestion') && <span><i className="lg suggestion" /> Suggestion · not checked</span>}
        <span className="map-credit">Natural Earth · OurAirports</span>
      </figcaption>
    </figure>
  );
}
