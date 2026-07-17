export const WORKBENCH_SIDER_WIDTH = 208;
export const WORKBENCH_SIDER_COLLAPSED_WIDTH = 64;

interface ContentBottomPaddingOptions {
  fixedFooter: boolean;
  footerHeight: number;
}

export function getContentBottomPadding({ fixedFooter, footerHeight }: ContentBottomPaddingOptions) {
  return fixedFooter ? footerHeight + 24 : 24;
}
