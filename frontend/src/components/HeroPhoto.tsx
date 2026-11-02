// Hero photograph, self-hosted in /public/media so it loads without an API call.
// "Sunset on plane" by Jacky Lo, CC0 (public domain dedication), via Wikimedia Commons / Unsplash.
const SIZES = [960, 1600, 2400];
const srcset = (ext: string) => SIZES.map((w) => `/media/hero-wing-${w}.${ext} ${w}w`).join(', ');

export const HERO_CREDIT = {
  title: 'Sunset on plane',
  author: 'Jacky Lo',
  licence: 'CC0',
  url: 'https://commons.wikimedia.org/wiki/File:Sunset_on_plane_(Unsplash).jpg',
};

export function HeroPhoto() {
  return (
    <div className="hero-photo" aria-hidden="true">
      <picture>
        <source type="image/webp" srcSet={srcset('webp')} sizes="100vw" />
        <img src="/media/hero-wing-1600.jpg" srcSet={srcset('jpg')} sizes="100vw" width={2400} height={1600} alt=""
          fetchPriority="high" loading="eager" decoding="async" />
      </picture>
    </div>
  );
}

export function HeroCredit() {
  return (
    <a className="hero-credit" href={HERO_CREDIT.url} target="_blank" rel="noreferrer noopener">
      Photo: {HERO_CREDIT.author} · {HERO_CREDIT.licence}
    </a>
  );
}
