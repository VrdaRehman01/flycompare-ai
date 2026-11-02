import { Component, lazy, Suspense, type ComponentProps, type ReactNode } from 'react';

const WorldMap = lazy(() => import('./WorldMap'));

class MapBoundary extends Component<{ height: number; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div className="world-map map-fallback" style={{ height: this.props.height }}><p>The map could not be loaded. Everything else on this page still works.</p></div>;
    return this.props.children;
  }
}

export function LazyWorldMap(props: ComponentProps<typeof WorldMap>) {
  const height = props.height ?? 420;
  return (
    <MapBoundary height={height}>
      <Suspense fallback={<div className="world-map" style={{ height }}><div className="map-loading"><span className="spinner dark" /> Loading map…</div></div>}>
        <WorldMap {...props} />
      </Suspense>
    </MapBoundary>
  );
}
