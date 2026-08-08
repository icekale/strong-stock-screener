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
          <linearGradient id="sm-logo-bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#3a6ea5" />
            <stop offset="1" stop-color="#245b8a" />
          </linearGradient>
        </defs>
        <rect x="10" y="10" width="180" height="180" rx="42" fill="url(#sm-logo-bg)" />
        <path
          d="M 52 150 L 78 120 L 94 128 L 126 76 L 118 68 L 140 52 L 150 76 L 140 74 L 124 92"
          fill="none"
          stroke="#ffffff"
          stroke-width="9"
          stroke-linecap="round"
          stroke-linejoin="round"
          opacity="0.92"
        />
        <line x1="80" y1="150" x2="80" y2="112" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
        <line x1="112" y1="122" x2="112" y2="82" stroke="#ffffff" stroke-width="5" stroke-linecap="round" opacity="0.85" />
        <rect x="68" y="120" width="24" height="30" rx="5" fill="#43cf7c" />
        <rect x="100" y="88" width="24" height="34" rx="5" fill="#ff4d4f" />
      </svg>
  `;

  return logoSvg;
}
