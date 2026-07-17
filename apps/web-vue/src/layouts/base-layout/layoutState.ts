interface ContentBottomPaddingOptions {
  footerVisible: boolean;
  fixedFooter: boolean;
  footerHeight: number;
}

export interface SiderGeometryOptions {
  isVerticalMix: boolean;
  isHorizontalMix: boolean;
  reverseHorizontalMix: boolean;
  hasActiveFirstLevelMenuChildren: boolean;
  width: number;
  collapsedWidth: number;
  mixWidth: number;
  mixCollapsedWidth: number;
  mixChildMenuWidth: number;
  mixSiderFixed: boolean;
  hasChildMenus: boolean;
}

export interface LayoutGeometryOptions {
  siderWidth: number;
  siderCollapsedWidth: number;
  tabHeight: number;
  footerVisible: boolean;
  fixedFooter: boolean;
  footerHeight: number;
}

export function getContentBottomPadding({ footerVisible, fixedFooter, footerHeight }: ContentBottomPaddingOptions) {
  return footerVisible && fixedFooter ? footerHeight + 24 : 24;
}

export function getSiderGeometry({
  isVerticalMix,
  isHorizontalMix,
  reverseHorizontalMix,
  hasActiveFirstLevelMenuChildren,
  width,
  collapsedWidth,
  mixWidth,
  mixCollapsedWidth,
  mixChildMenuWidth,
  mixSiderFixed,
  hasChildMenus
}: SiderGeometryOptions) {
  if (isHorizontalMix && reverseHorizontalMix) {
    return {
      siderWidth: hasActiveFirstLevelMenuChildren ? width : 0,
      siderCollapsedWidth: hasActiveFirstLevelMenuChildren ? collapsedWidth : 0
    };
  }

  let siderWidth = isVerticalMix || isHorizontalMix ? mixWidth : width;
  let siderCollapsedWidth = isVerticalMix || isHorizontalMix ? mixCollapsedWidth : collapsedWidth;

  if (isVerticalMix && mixSiderFixed && hasChildMenus) {
    siderWidth += mixChildMenuWidth;
    siderCollapsedWidth += mixChildMenuWidth;
  }

  return { siderWidth, siderCollapsedWidth };
}

export function getLayoutGeometry({
  siderWidth,
  siderCollapsedWidth,
  tabHeight,
  footerVisible,
  fixedFooter,
  footerHeight
}: LayoutGeometryOptions) {
  return {
    siderWidth,
    siderCollapsedWidth,
    tabHeight,
    contentBottomPadding: getContentBottomPadding({ footerVisible, fixedFooter, footerHeight })
  };
}
