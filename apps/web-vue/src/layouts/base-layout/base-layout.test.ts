// @vitest-environment jsdom

import { describe, expect, it } from 'vitest';
import { themeSettings } from '@/theme/settings';
import { getContentBottomPadding, getLayoutGeometry, getSiderGeometry } from './layoutState';

describe('base layout state', () => {
  it('reserves fixed footer space only when the footer is visible', () => {
    expect(getContentBottomPadding({ fullContent: false, footerVisible: true, fixedFooter: true, footerHeight: 48 })).toBe(
      72
    );
    expect(
      getContentBottomPadding({ fullContent: false, footerVisible: true, fixedFooter: false, footerHeight: 48 })
    ).toBe(24);
    expect(getContentBottomPadding({ fullContent: false, footerVisible: false, fixedFooter: true, footerHeight: 48 })).toBe(
      24
    );
    expect(getContentBottomPadding({ fullContent: true, footerVisible: true, fixedFooter: true, footerHeight: 48 })).toBe(
      24
    );
  });

  it('keeps configured regular sider dimensions in the consumed geometry', () => {
    const geometry = getSiderGeometry({
      isVerticalMix: false,
      isHorizontalMix: false,
      reverseHorizontalMix: false,
      hasActiveFirstLevelMenuChildren: false,
      width: 232,
      collapsedWidth: 72,
      mixWidth: 90,
      mixCollapsedWidth: 64,
      mixChildMenuWidth: 200,
      mixSiderFixed: false,
      hasChildMenus: false
    });

    expect(geometry).toEqual({ siderWidth: 232, siderCollapsedWidth: 72 });
  });

  it('passes configured tab and sider values through while honoring footer visibility', () => {
    expect(
      getLayoutGeometry({
        siderWidth: 232,
        siderCollapsedWidth: 72,
        tabHeight: 52,
        fullContent: false,
        footerVisible: false,
        fixedFooter: true,
        footerHeight: 48
      })
    ).toEqual({
      siderWidth: 232,
      siderCollapsedWidth: 72,
      tabHeight: 52,
      contentBottomPadding: 24
    });
  });

  it('keeps configured tab heights above the safe minimum and clamps smaller values', () => {
    expect(
      getLayoutGeometry({
        siderWidth: 232,
        siderCollapsedWidth: 72,
        tabHeight: 52,
        fullContent: false,
        footerVisible: true,
        fixedFooter: false,
        footerHeight: 48
      }).tabHeight
    ).toBe(52);
    expect(
      getLayoutGeometry({
        siderWidth: 232,
        siderCollapsedWidth: 72,
        tabHeight: 32,
        fullContent: false,
        footerVisible: true,
        fixedFooter: false,
        footerHeight: 48
      }).tabHeight
    ).toBe(40);
  });

  it('uses the financial workbench shell defaults', () => {
    expect(themeSettings.sider.width).toBe(208);
    expect(themeSettings.sider.collapsedWidth).toBe(64);
    expect(themeSettings.tab.height).toBe(40);
  });

});
