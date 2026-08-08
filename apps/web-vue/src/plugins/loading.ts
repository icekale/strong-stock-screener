// @unocss-include
import { getRgb } from '@sa/color';
import { localStg } from '@/utils/storage';
import { $t } from '@/locales';

export function setupLoading() {
  const themeColor = localStg.get('themeColor') || '#646cff';

  const { r, g, b } = getRgb(themeColor);

  const primaryColor = `--primary-color: ${r} ${g} ${b}`;

  const cssVars = primaryColor;

  const loadingClasses = [
    'left-0 top-0',
    'left-0 bottom-0 animate-delay-500',
    'right-0 top-0 animate-delay-1000',
    'right-0 bottom-0 animate-delay-1500'
  ];

  const dot = loadingClasses
    .map(item => {
      return `<div class="absolute w-16px h-16px bg-primary rounded-8px animate-pulse ${item}"></div>`;
    })
    .join('\n');

  const loading = `
<div class="fixed-center flex-col bg-layout" style="${cssVars}">
  <div class="w-128px h-128px">
    ${getLogoSvg()}
  </div>
  <div class="w-56px h-56px my-36px">
    <div class="relative h-full animate-spin">
      ${dot}
    </div>
  </div>
  <h2 class="text-28px font-500 text-primary">${$t('system.title')}</h2>
</div>`;

  const app = document.getElementById('app');

  if (app) {
    app.innerHTML = loading;
  }
}

function getLogoSvg() {
  const logoSvg = `<svg
        width="100%"
        height="100%"
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="sm-loading-bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#3a6ea5" />
            <stop offset="1" stop-color="#245b8a" />
          </linearGradient>
        </defs>
        <rect x="10" y="10" width="180" height="180" rx="44" fill="url(#sm-loading-bg)" />
        <path
          d="M 54 152 L 86 122 L 100 130 L 130 82"
          fill="none"
          stroke="#ffffff"
          stroke-width="10"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.92"
        />
        <path
          d="M 130 82 L 122 72 L 146 56 L 160 82 L 146 76"
          fill="none"
          stroke="#ffffff"
          stroke-width="10"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.92"
        />
        <line x1="86" y1="156" x2="86" y2="118" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
        <line x1="118" y1="126" x2="118" y2="88" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
        <rect x="74" y="124" width="24" height="30" rx="5" fill="#43cf7c" />
        <rect x="106" y="92" width="24" height="34" rx="5" fill="#ff4d4f" />
      </svg>
  `;

  return logoSvg;
}
