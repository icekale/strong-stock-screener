import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

test("standalone strong stock workbench is wired without daily-report modules", () => {
  const typesSource = readFileSync(new URL("./types.ts", import.meta.url), "utf8");
  const apiSource = readFileSync(new URL("./api.ts", import.meta.url), "utf8");
  const componentSource = readFileSync(new URL("../components/ScreenerWorkbench.tsx", import.meta.url), "utf8");
  const nestedScreenerSupportSource = componentSource.slice(componentSource.indexOf("function HomepageMarketSupportPanel"));
  const marketPanelsUrl = new URL("../components/screener/MarketOverviewPanels.tsx", import.meta.url);
  const marketPanelsSource = existsSync(marketPanelsUrl) ? readFileSync(marketPanelsUrl, "utf8") : "";
  const filterRailUrl = new URL("../components/screener/FilterLogicRail.tsx", import.meta.url);
  const filterRailSource = existsSync(filterRailUrl) ? readFileSync(filterRailUrl, "utf8") : "";
  const candidateResultsUrl = new URL("../components/screener/CandidateResults.tsx", import.meta.url);
  const candidateResultsSource = existsSync(candidateResultsUrl) ? readFileSync(candidateResultsUrl, "utf8") : "";
  const gsgfPanelsUrl = new URL("../components/screener/GsgfWorkflowPanels.tsx", import.meta.url);
  const gsgfPanelsSource = existsSync(gsgfPanelsUrl) ? readFileSync(gsgfPanelsUrl, "utf8") : "";
  const gsgfFunnelUrl = new URL("../components/screener/GsgfFunnelPanel.tsx", import.meta.url);
  const gsgfFunnelSource = existsSync(gsgfFunnelUrl) ? readFileSync(gsgfFunnelUrl, "utf8") : "";
  const screenerUtilsUrl = new URL("../components/screener/screenerUtils.ts", import.meta.url);
  const screenerUtilsSource = existsSync(screenerUtilsUrl) ? readFileSync(screenerUtilsUrl, "utf8") : "";
  const screenerTypesUrl = new URL("../components/screener/types.ts", import.meta.url);
  const screenerTypesSource = existsSync(screenerTypesUrl) ? readFileSync(screenerTypesUrl, "utf8") : "";
  const pageSource = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
  const navigationSource = readFileSync(new URL("./appNavigation.ts", import.meta.url), "utf8");
  const homeWorkspaceUrl = new URL("../app/HomeWorkbench.tsx", import.meta.url);
  const homeWorkspaceSource = existsSync(homeWorkspaceUrl) ? readFileSync(homeWorkspaceUrl, "utf8") : "";
  const screenerPageUrl = new URL("../app/screener/page.tsx", import.meta.url);
  const screenerPageSource = existsSync(screenerPageUrl) ? readFileSync(screenerPageUrl, "utf8") : "";
  const homeFeatureSource = [pageSource, homeWorkspaceSource].join("\n");
  const layoutSource = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
  const antdProviderSource = readFileSync(new URL("../components/AntdAppProvider.tsx", import.meta.url), "utf8");
  const watchlistPageSource = readFileSync(new URL("../app/watchlist/page.tsx", import.meta.url), "utf8");
  const watchlistWorkspaceUrl = new URL("../app/watchlist/WatchlistWorkspace.tsx", import.meta.url);
  const watchlistWorkspaceSource = existsSync(watchlistWorkspaceUrl) ? readFileSync(watchlistWorkspaceUrl, "utf8") : "";
  const watchlistEditorUrl = new URL("../app/watchlist/WatchlistEditorPanel.tsx", import.meta.url);
  const watchlistEditorSource = existsSync(watchlistEditorUrl) ? readFileSync(watchlistEditorUrl, "utf8") : "";
  const watchlistManagerUrl = new URL("../app/watchlist/WatchlistManagerPanel.tsx", import.meta.url);
  const watchlistManagerSource = existsSync(watchlistManagerUrl) ? readFileSync(watchlistManagerUrl, "utf8") : "";
  const watchlistTypesUrl = new URL("../app/watchlist/types.ts", import.meta.url);
  const watchlistTypesSource = existsSync(watchlistTypesUrl) ? readFileSync(watchlistTypesUrl, "utf8") : "";
  const watchlistFeatureSource = [
    watchlistPageSource,
    watchlistWorkspaceSource,
    watchlistEditorSource,
    watchlistManagerSource,
    watchlistTypesSource,
  ].join("\n");
  const stockPageUrl = new URL("../app/stock/[symbol]/page.tsx", import.meta.url);
  const stockPageSource = existsSync(stockPageUrl) ? readFileSync(stockPageUrl, "utf8") : "";
  const stockWorkspaceUrl = new URL("../app/stock/[symbol]/StockKlineWorkspace.tsx", import.meta.url);
  const stockWorkspaceSource = existsSync(stockWorkspaceUrl) ? readFileSync(stockWorkspaceUrl, "utf8") : "";
  const stockFeatureSource = [stockPageSource, stockWorkspaceSource].join("\n");
  const stockChartSource = readFileSync(new URL("../components/TickFlowKlineChart.tsx", import.meta.url), "utf8");
  const settingsPageSource = readFileSync(new URL("../app/settings/page.tsx", import.meta.url), "utf8");
  const settingsWorkspaceUrl = new URL("../app/settings/SettingsWorkspace.tsx", import.meta.url);
  const settingsWorkspaceSource = existsSync(settingsWorkspaceUrl) ? readFileSync(settingsWorkspaceUrl, "utf8") : "";
  const settingsFeatureSource = [settingsPageSource, settingsWorkspaceSource].join("\n");
  const systemPageUrl = new URL("../app/system/page.tsx", import.meta.url);
  const systemPageSource = existsSync(systemPageUrl) ? readFileSync(systemPageUrl, "utf8") : "";
  const systemWorkspaceUrl = new URL("../app/system/SystemWorkspace.tsx", import.meta.url);
  const systemWorkspaceSource = existsSync(systemWorkspaceUrl) ? readFileSync(systemWorkspaceUrl, "utf8") : "";
  const systemFeatureSource = [systemPageSource, systemWorkspaceSource].join("\n");
  const marketPageUrl = new URL("../app/market/page.tsx", import.meta.url);
  const marketPageSource = existsSync(marketPageUrl) ? readFileSync(marketPageUrl, "utf8") : "";
  const marketWorkspaceUrl = new URL("../app/market/MarketWorkspace.tsx", import.meta.url);
  const marketWorkspaceSource = existsSync(marketWorkspaceUrl) ? readFileSync(marketWorkspaceUrl, "utf8") : "";
  const sectorsPageUrl = new URL("../app/sectors/page.tsx", import.meta.url);
  const sectorsPageSource = existsSync(sectorsPageUrl) ? readFileSync(sectorsPageUrl, "utf8") : "";
  const sectorsWorkspaceUrl = new URL("../app/sectors/SectorPageWorkspace.tsx", import.meta.url);
  const sectorsWorkspaceSource = existsSync(sectorsWorkspaceUrl) ? readFileSync(sectorsWorkspaceUrl, "utf8") : "";
  const sectorsReplicaWorkspaceUrl = new URL("../app/sectors/SectorReplicaWorkspace.tsx", import.meta.url);
  const sectorsReplicaWorkspaceSource = existsSync(sectorsReplicaWorkspaceUrl)
    ? readFileSync(sectorsReplicaWorkspaceUrl, "utf8")
    : "";
  const sectorsReplicaPanelUrl = new URL("../app/sectors/SectorReplicaPanel.tsx", import.meta.url);
  const sectorsReplicaPanelSource = existsSync(sectorsReplicaPanelUrl)
    ? readFileSync(sectorsReplicaPanelUrl, "utf8")
    : "";
  const sectorsReplicaUtilsUrl = new URL("./sectorReplica.ts", import.meta.url);
  const sectorsReplicaUtilsSource = existsSync(sectorsReplicaUtilsUrl)
    ? readFileSync(sectorsReplicaUtilsUrl, "utf8")
    : "";
  const sectorsReplicaChartUrl = new URL("./sectorReplicaChartOption.ts", import.meta.url);
  const sectorsReplicaChartSource = existsSync(sectorsReplicaChartUrl)
    ? readFileSync(sectorsReplicaChartUrl, "utf8")
    : "";
  const sectorsFeatureSource = [
    sectorsPageSource,
    sectorsWorkspaceSource,
    sectorsReplicaWorkspaceSource,
    sectorsReplicaPanelSource,
    sectorsReplicaUtilsSource,
    sectorsReplicaChartSource,
  ].join("\n");
  const heatmapPageUrl = new URL("../app/heatmap/page.tsx", import.meta.url);
  const heatmapPageSource = existsSync(heatmapPageUrl) ? readFileSync(heatmapPageUrl, "utf8") : "";
  const auctionPageUrl = new URL("../app/auction/page.tsx", import.meta.url);
  const auctionPageSource = existsSync(auctionPageUrl) ? readFileSync(auctionPageUrl, "utf8") : "";
  const auctionWorkspaceUrl = new URL("../app/auction/AuctionWorkspace.tsx", import.meta.url);
  const auctionWorkspaceSource = existsSync(auctionWorkspaceUrl) ? readFileSync(auctionWorkspaceUrl, "utf8") : "";
  const auctionFeatureSource = [auctionPageSource, auctionWorkspaceSource].join("\n");
  const sentimentPageUrl = new URL("../app/sentiment/page.tsx", import.meta.url);
  const sentimentPageSource = existsSync(sentimentPageUrl) ? readFileSync(sentimentPageUrl, "utf8") : "";
  const sentimentWorkspaceUrl = new URL("../app/sentiment/SentimentWorkspace.tsx", import.meta.url);
  const sentimentWorkspaceSource = existsSync(sentimentWorkspaceUrl) ? readFileSync(sentimentWorkspaceUrl, "utf8") : "";
  const sentimentIntradayUrl = new URL("../app/sentiment/IntradaySentimentPanel.tsx", import.meta.url);
  const sentimentIntradaySource = existsSync(sentimentIntradayUrl) ? readFileSync(sentimentIntradayUrl, "utf8") : "";
  const sentimentStockPoolsUrl = new URL("../app/sentiment/StockPoolTables.tsx", import.meta.url);
  const sentimentStockPoolsSource = existsSync(sentimentStockPoolsUrl) ? readFileSync(sentimentStockPoolsUrl, "utf8") : "";
  const sentimentFeatureSource = [
    sentimentPageSource,
    sentimentWorkspaceSource,
    sentimentIntradaySource,
    sentimentStockPoolsSource,
  ].join("\n");
  const modelMaintenancePageUrl = new URL("../app/model-maintenance/page.tsx", import.meta.url);
  const modelMaintenancePageSource = existsSync(modelMaintenancePageUrl)
    ? readFileSync(modelMaintenancePageUrl, "utf8")
    : "";
  const modelMaintenanceWorkspaceUrl = new URL(
    "../app/model-maintenance/ModelMaintenanceWorkspace.tsx",
    import.meta.url,
  );
  const modelMaintenanceWorkspaceSource = existsSync(modelMaintenanceWorkspaceUrl)
    ? readFileSync(modelMaintenanceWorkspaceUrl, "utf8")
    : "";
  const modelMaintenancePacketPageUrl = new URL(
    "../app/model-maintenance/packets/[packetId]/page.tsx",
    import.meta.url,
  );
  const modelMaintenancePacketPageSource = existsSync(modelMaintenancePacketPageUrl)
    ? readFileSync(modelMaintenancePacketPageUrl, "utf8")
    : "";
  const modelMaintenanceFeatureSource = [
    modelMaintenancePageSource,
    modelMaintenanceWorkspaceSource,
    modelMaintenancePacketPageSource,
  ].join("\n");
  const screenerFeatureSource = [
    componentSource,
    marketPanelsSource,
    filterRailSource,
    candidateResultsSource,
    gsgfPanelsSource,
    gsgfFunnelSource,
    screenerUtilsSource,
    screenerTypesSource,
  ].join("\n");
  const appShellSource = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");
  const globalsSource = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const sectorReplicaCssSource = globalsSource.slice(globalsSource.indexOf(".market-radar-page-content"));
  const composeSource = readFileSync(new URL("../../../docker-compose.yml", import.meta.url), "utf8");
  const rootDockerfileSource = readFileSync(new URL("../../../Dockerfile", import.meta.url), "utf8");
  const dockerignoreSource = readFileSync(new URL("../../../.dockerignore", import.meta.url), "utf8");
  const singleStartSource = readFileSync(new URL("../../../scripts/start-single-container.sh", import.meta.url), "utf8");
  const nextConfigSource = readFileSync(new URL("../next.config.ts", import.meta.url), "utf8");
  const webPackageSource = readFileSync(new URL("../package.json", import.meta.url), "utf8");
  const smokeUiSource = readFileSync(new URL("../../../scripts/smoke-ui.mjs", import.meta.url), "utf8");
  const localWebStartSource = readFileSync(new URL("../../../scripts/start-local-web.py", import.meta.url), "utf8");
  const dualComposeSource = readFileSync(new URL("../../../docker-compose.dual.yml", import.meta.url), "utf8");
  const envExampleSource = readFileSync(new URL("../../../.env.example", import.meta.url), "utf8");

  assert.match(typesSource, /StrongStockScreeningResponse/);
  assert.match(typesSource, /GsgfAnalysis/);
  assert.match(typesSource, /GsgfFinalStatus/);
  assert.match(typesSource, /final_status: GsgfFinalStatus/);
  assert.match(typesSource, /setup_type: string \| null/);
  assert.match(typesSource, /confirm_type: string \| null/);
  assert.match(typesSource, /evidence_refs: string\[\]/);
  assert.match(typesSource, /diagnostics: Record<string, \{ score: number \| null; flags: string\[\] \}>/);
  assert.match(typesSource, /GsgfBacktestSummary/);
  assert.match(typesSource, /GsgfBacktestBucket/);
  assert.match(typesSource, /GsgfBacktestWindowStat/);
  assert.match(typesSource, /GsgfFunnelDiagnostics/);
  assert.match(typesSource, /gsgf_funnel: GsgfFunnelDiagnostics/);
  assert.match(typesSource, /gsgf_observation_items: StrongStockScreeningItem\[\]/);
  assert.match(typesSource, /GsgfTradePlan/);
  assert.match(typesSource, /holder_guidance: string\[\]/);
  assert.match(typesSource, /empty_position_guidance: string\[\]/);
  assert.match(typesSource, /risk_invalidation: string\[\]/);
  assert.match(typesSource, /trade_plan: GsgfTradePlan \| null/);
  assert.match(typesSource, /GsgfReviewSummary/);
  assert.match(typesSource, /GsgfReviewSnapshotResponse/);
  assert.match(typesSource, /realized_return_pct: number \| null/);
  assert.match(typesSource, /GsgfRealCalibrationSummary/);
  assert.match(typesSource, /GsgfCalibrationBucket/);
  assert.match(typesSource, /composite_score: number \| null/);
  assert.match(typesSource, /calibration_rating: string/);
  assert.match(typesSource, /unique_symbol_buckets: GsgfCalibrationBucket\[\]/);
  assert.match(typesSource, /GsgfCalibrationDiagnosticGroup/);
  assert.match(typesSource, /diagnostic_groups: GsgfCalibrationDiagnosticGroup\[\]/);
  assert.match(typesSource, /BackgroundJobState/);
  assert.match(typesSource, /GsgfModelHealth/);
  assert.match(typesSource, /GsgfAutoReviewConfig/);
  assert.match(typesSource, /GsgfChartAnnotation/);
  assert.match(typesSource, /ScreenStrategy = "strong_stock" \| "gsgf" \| "combined"/);
  assert.match(typesSource, /ScreenRunFilters/);
  assert.match(typesSource, /StrongStockIntradaySnapshot/);
  assert.match(typesSource, /GsgfIntradayConfirmation/);
  assert.match(typesSource, /gsgf_intraday_confirmation: GsgfIntradayConfirmation/);
  assert.match(typesSource, /industry: string \| null/);
  assert.match(typesSource, /industry_strength: "strong" \| "neutral" \| "weak" \| null/);
  assert.match(typesSource, /industry_score: number/);
  assert.match(typesSource, /status: "focus" \| "wait_pullback" \| "reduce_risk" \| "data_incomplete"/);
  assert.match(
    typesSource,
    /action: "watch" \| "low_buy_watch" \| "reduce" \| "avoid_chase" \| "data_incomplete"/,
  );
  assert.match(typesSource, /risk_action: "hold_watch" \| "reduce" \| "empty"/);
  assert.match(typesSource, /RiskCheckStatus = "triggered" \| "clear" \| "unknown"/);
  assert.match(typesSource, /severe_abnormal_warning: RiskCheckStatus/);
  assert.match(typesSource, /negative_news_status: RiskCheckStatus/);
  assert.match(typesSource, /negative_news_flags: string\[\]/);
  assert.doesNotMatch(typesSource, /status: .*"empty"/);
  assert.doesNotMatch(
    typesSource.slice(typesSource.indexOf("export type StrongStockIntradayItem")),
    /action: .*"empty"/,
  );
  assert.match(apiSource, /createScreenRun/);
  assert.match(apiSource, /createScreenRunJob/);
  assert.match(apiSource, /getScreenRunJob/);
  assert.match(homeFeatureSource, /pollScreenRunJob/);
  assert.match(screenerFeatureSource, /screenJob/);
  assert.match(screenerFeatureSource, /筛选任务/);
  assert.match(apiSource, /createIntradaySnapshot/);
  assert.match(apiSource, /watchlist_text/);
  assert.match(apiSource, /use_watchlist_pool/);
  assert.match(apiSource, /gsgf_context/);
  assert.match(apiSource, /getWatchlistPool/);
  assert.match(apiSource, /saveWatchlistPool/);
  assert.match(apiSource, /addWatchlistPoolItem/);
  assert.match(apiSource, /getStockKline/);
  assert.match(apiSource, /getStockResearch/);
  assert.match(composeSource, /image: icekale\/strong-stock-screener:\$\{STRONG_STOCK_IMAGE_TAG:-latest\}/);
  assert.doesNotMatch(composeSource, /build:/);
  assert.match(composeSource, /TZ: \$\{TZ:-Asia\/Shanghai\}/);
  assert.match(dualComposeSource, /TZ: \$\{TZ:-Asia\/Shanghai\}/);
  assert.match(envExampleSource, /TZ=Asia\/Shanghai/);
  assert.match(rootDockerfileSource, /apps\/api/);
  assert.match(rootDockerfileSource, /apps\/web/);
  assert.match(rootDockerfileSource, /start-single-container\.sh/);
  assert.match(rootDockerfileSource, /TZ=Asia\/Shanghai/);
  assert.match(rootDockerfileSource, /ARG PIP_INDEX_URL=/);
  assert.match(rootDockerfileSource, /PIP_INDEX_URL=\$PIP_INDEX_URL/);
  assert.match(dockerignoreSource, /apps\/api\/\.venv/);
  assert.match(dockerignoreSource, /apps\/web\/node_modules/);
  assert.match(dockerignoreSource, /apps\/web\/\.next/);
  assert.match(singleStartSource, /uvicorn app\.main:app/);
  assert.match(singleStartSource, /node server\.js/);
  assert.doesNotMatch(singleStartSource, /next.*start/);
  assert.match(nextConfigSource, /\/api\/:path\*/);
  assert.match(nextConfigSource, /http:\/\/127\.0\.0\.1:8010\/api\/:path\*/);
  assert.match(
    nextConfigSource,
    /distDir: process\.env\.NEXT_DIST_DIR \|\| \(process\.env\.NODE_ENV === "development" \? "\.next-dev" : "\.next"\)/,
  );
  assert.match(nextConfigSource, /output: "standalone"/);
  assert.match(nextConfigSource, /proxyTimeout: 240_000/);
  assert.match(webPackageSource, /NEXT_DIST_DIR=\.next-dev next dev/);
  assert.match(localWebStartSource, /\.next-dev/);
  assert.match(localWebStartSource, /lsof/);
  assert.match(typesSource, /StockResearchResponse/);
  assert.match(typesSource, /ifind_api_key_configured: boolean/);
  assert.match(typesSource, /ifind_service_id: "hexin-ifind-ds-stock-mcp" \| "hexin-ifind-ds-news-mcp" \| "hexin-ifind-ds-index-mcp"/);
  assert.match(apiSource, /ifind_api_key\?: string \| null/);
  assert.match(apiSource, /ifind_base_url: string/);
  assert.match(apiSource, /ifind_service_id: "hexin-ifind-ds-stock-mcp" \| "hexin-ifind-ds-news-mcp" \| "hexin-ifind-ds-index-mcp"/);
  assert.match(typesSource, /note: string \| null/);
  assert.match(typesSource, /note\?: string \| null/);
  assert.match(typesSource, /ma60: number \| null/);
  assert.match(typesSource, /gsgf_annotations: GsgfChartAnnotation\[\]/);
  assert.match(apiSource, /scan_limit: scanLimit/);
  assert.match(apiSource, /scanLimit = 160/);
  assert.match(apiSource, /filters/);
  assert.match(apiSource, /strategy\?: ScreenStrategy/);
  assert.match(apiSource, /getWatchlistGsgfStatus/);
  assert.match(apiSource, /runGsgfBacktest/);
  assert.match(apiSource, /\/api\/gsgf\/backtest/);
  assert.match(apiSource, /buildGsgfTradePlan/);
  assert.match(apiSource, /\/api\/gsgf\/trade-plan/);
  assert.match(apiSource, /saveLatestGsgfReviewSnapshot/);
  assert.match(apiSource, /recheckGsgfReview/);
  assert.match(apiSource, /\/api\/gsgf\/review\/snapshots\/latest/);
  assert.match(apiSource, /\/api\/gsgf\/review\/recheck/);
  assert.match(apiSource, /runGsgfCalibration/);
  assert.match(apiSource, /\/api\/gsgf\/calibration/);
  assert.match(apiSource, /createAuctionSnapshotJob/);
  assert.match(apiSource, /getAuctionSnapshotJob/);
  assert.match(apiSource, /\/api\/auction\/snapshot\/jobs/);
  assert.match(apiSource, /createAuctionModelTop3Job/);
  assert.match(apiSource, /getAuctionModelTop3Job/);
  assert.match(apiSource, /\/api\/auction\/model\/top3\/jobs/);
  assert.match(apiSource, /getLatestGsgfReview/);
  assert.match(apiSource, /createGsgfCalibrationJob/);
  assert.match(apiSource, /getGsgfCalibrationJob/);
  assert.match(apiSource, /cancelGsgfCalibrationJob/);
  assert.match(apiSource, /getLatestGsgfCalibration/);
  assert.match(apiSource, /getGsgfModelHealth/);
  assert.match(screenerFeatureSource, /scanLimit/);
  assert.match(screenerFeatureSource, /strategy/);
  assert.match(screenerFeatureSource, /股是股非模型/);
  assert.match(screenerFeatureSource, /综合模型/);
  assert.match(screenerFeatureSource, /确认信号/);
  assert.match(screenerFeatureSource, /setup_type/);
  assert.match(screenerFeatureSource, /confirm_type/);
  assert.match(screenerFeatureSource, /evidence_refs/);
  assert.match(screenerFeatureSource, /diagnostics/);
  assert.match(screenerFeatureSource, /证据链/);
  assert.match(screenerFeatureSource, /诊断/);
  assert.match(screenerFeatureSource, /gsgfLabel/);
  assert.match(screenerFeatureSource, /扫描候选数/);
  assert.match(screenerFeatureSource, /高级筛选/);
  assert.match(screenerFeatureSource, /最小市值/);
  assert.match(screenerFeatureSource, /KDJ-J值/);
  assert.match(screenerFeatureSource, /市场类型/);
  assert.match(screenerFeatureSource, /保存筛选参数/);
  assert.match(screenerFeatureSource, /筛选参数已保存到本机/);
  assert.match(screenerFeatureSource, /screenFiltersSaved/);
  assert.match(homeFeatureSource, /localStorage/);
  assert.match(homeFeatureSource, /onSaveScreenFilters/);
  assert.match(homeFeatureSource, /setScreenFiltersSaved/);
  assert.match(navigationSource, /市场总览/);
  assert.match(navigationSource, /强势选股/);
  assert.match(navigationSource, /竞价雷达/);
  assert.match(navigationSource, /自选与风险/);
  assert.match(apiSource, /getDataSourceStatus/);
  assert.match(typesSource, /MarketOverviewResponse/);
  assert.match(typesSource, /MarketIndexSnapshot/);
  assert.match(typesSource, /indices: MarketIndexSnapshot\[\]/);
  assert.match(typesSource, /MarketRankingItem/);
  assert.match(typesSource, /MarketRankingsResponse/);
  assert.match(typesSource, /AuctionSnapshotResponse/);
  assert.match(typesSource, /themes: string\[\]/);
  assert.match(typesSource, /hot_theme_rank: number \| null/);
  assert.match(typesSource, /hot_theme_score: number \| null/);
  assert.match(typesSource, /theme_auction_rank: number \| null/);
  assert.match(typesSource, /theme_resonance: boolean/);
  assert.match(typesSource, /AuctionReviewSummary/);
  assert.match(typesSource, /AuctionReviewRecord/);
  assert.match(typesSource, /AuctionRuleBucket/);
  assert.match(typesSource, /SectorRadarResponse/);
  assert.match(typesSource, /ShortTermSentimentResponse/);
  assert.match(typesSource, /ShortTermSentimentStockItem/);
  assert.match(typesSource, /ShortTermSentimentLadderGroup/);
  assert.match(typesSource, /ShortTermSentimentIndustryItem/);
  assert.match(typesSource, /MarketEmotionSnapshotResponse/);
  assert.match(typesSource, /MarketEmotionMetrics/);
  assert.match(typesSource, /MarketEmotionBucket/);
  assert.match(typesSource, /MarketEmotionSample/);
  assert.match(typesSource, /ShortTermIntradaySentimentResponse/);
  assert.match(typesSource, /ShortTermIntradaySentimentItem/);
  assert.match(typesSource, /ShortTermIntradaySignalDigest/);
  assert.match(typesSource, /ShortTermIntradaySignalAlert/);
  assert.match(typesSource, /NotificationChannelConfig/);
  assert.match(typesSource, /NotificationSendResult/);
  assert.match(typesSource, /SentimentDecisionResponse/);
  assert.match(typesSource, /SentimentDecisionOutcome/);
  assert.match(typesSource, /SentimentReviewSummary/);
  assert.match(typesSource, /SentimentWatchlistAlert/);
  assert.match(typesSource, /SentimentWatchlistAlertsResponse/);
  assert.match(typesSource, /ModelMaintenanceReport/);
  assert.match(typesSource, /ModelMaintenancePacket/);
  assert.match(typesSource, /ModelMaintenanceSuggestion/);
  assert.match(typesSource, /AuctionTop3TrainingSettings/);
  assert.match(typesSource, /AuctionTop3TrainingSummary/);
  assert.match(typesSource, /AuctionTop3PerformanceResponse/);
  assert.match(typesSource, /packet_url: string \| null/);
  assert.match(typesSource, /model_sections: Record<string, unknown>/);
  assert.match(typesSource, /auction_top3_training: AuctionTop3TrainingSettings/);
  assert.match(typesSource, /snapshot_status/);
  assert.match(typesSource, /cache_age_seconds/);
  assert.match(typesSource, /AuctionTimelineResponse/);
  assert.match(apiSource, /getMarketOverview/);
  assert.match(apiSource, /getMarketRankings/);
  assert.match(apiSource, /getAuctionSnapshot/);
  assert.match(apiSource, /getAuctionLatest/);
  assert.match(apiSource, /getAuctionTimeline/);
  assert.match(apiSource, /getAuctionReviewLatest/);
  assert.match(apiSource, /getAuctionReview/);
  assert.match(apiSource, /finalizeAuctionReview/);
  assert.match(apiSource, /getAuctionRuleSummary/);
  assert.match(apiSource, /getSectorRadar/);
  assert.match(apiSource, /getShortTermSentiment/);
  assert.match(apiSource, /getSentimentDecision/);
  assert.match(apiSource, /archiveSentimentDecision/);
  assert.match(apiSource, /getSentimentWatchlistAlerts/);
  assert.match(apiSource, /getMarketEmotionSnapshot/);
  assert.match(apiSource, /getShortTermIntradaySentiment/);
  assert.match(apiSource, /getShortTermIntradaySignalDigest/);
  assert.match(apiSource, /sendNotificationMessage/);
  assert.match(apiSource, /generateModelMaintenancePacket/);
  assert.match(apiSource, /getLatestModelMaintenancePacket/);
  assert.match(apiSource, /getModelMaintenancePacket/);
  assert.match(apiSource, /getLatestModelMaintenanceReport/);
  assert.match(apiSource, /analyzeModelMaintenance/);
  assert.match(apiSource, /updateModelMaintenanceSuggestion/);
  assert.match(apiSource, /getAuctionTop3TrainingSummary/);
  assert.match(apiSource, /getAuctionTop3TrainingPerformance/);
  assert.match(apiSource, /generateAuctionTop3TrainingSamples/);
  assert.match(apiSource, /\/api\/short-term\/sentiment/);
  assert.match(apiSource, /\/api\/short-term\/sentiment\/decision/);
  assert.match(apiSource, /\/api\/short-term\/sentiment\/review\/archive/);
  assert.match(apiSource, /\/api\/short-term\/sentiment\/watchlist-alerts/);
  assert.match(apiSource, /\/api\/short-term\/market-emotion/);
  assert.match(apiSource, /\/api\/short-term\/sentiment\/intraday/);
  assert.match(apiSource, /\/api\/short-term\/sentiment\/intraday\/digest/);
  assert.match(apiSource, /\/api\/market\/rankings/);
  assert.match(apiSource, /\/api\/auction\/latest/);
  assert.match(apiSource, /\/api\/auction\/timeline/);
  assert.match(apiSource, /\/api\/auction\/snapshot/);
  assert.match(apiSource, /\/api\/auction\/review\/latest/);
  assert.match(apiSource, /\/api\/auction\/review\/finalize/);
  assert.match(apiSource, /\/api\/auction\/rules\/summary/);
  assert.match(apiSource, /\/api\/notifications\/send/);
  assert.match(apiSource, /\/api\/model-maintenance\/packets\/latest/);
  assert.match(apiSource, /\/api\/model-maintenance\/auction-top3\/training\/performance/);
  assert.match(homeFeatureSource, /marketOverview/);
  assert.match(homeFeatureSource, /refreshMarketOverview/);
  assert.match(homeFeatureSource, /sectorRadar/);
  assert.match(homeFeatureSource, /refreshSectorRadar/);
  assert.match(homeFeatureSource, /getSectorRadar/);
  assert.match(homeFeatureSource, /sentimentSummary/);
  assert.match(homeFeatureSource, /refreshSentimentSummary/);
  assert.match(homeFeatureSource, /getSentimentSummary/);
  assert.match(marketPanelsSource, /sentimentSummary/);
  assert.doesNotMatch(marketPanelsSource, /const sectorSentiment = buildSectorRadarSentiment\(sectorRadar\)/);
  assert.match(homeFeatureSource, /watchlistPoolItems/);
  assert.match(homeFeatureSource, /setWatchlistPoolItems\(response\.items\)/);
  assert.doesNotMatch(apiSource + screenerFeatureSource + homeFeatureSource, /x-api-key|TICKFLOW_API_KEY/);
  assert.match(screenerFeatureSource, /StockMaster/);
  assert.match(screenerFeatureSource, /dynamic[<(]/);
  assert.match(screenerFeatureSource, /查看模型维护/);
  assert.doesNotMatch(componentSource, /<GsgfReviewPanel/);
  assert.doesNotMatch(componentSource, /<GsgfCalibrationPanel/);
  assert.doesNotMatch(componentSource, /<GsgfFunnelPanel/);
  assert.match(marketPanelsSource, /MarketOverviewPanels/);
  assert.match(marketPanelsSource, /SectorFlowHeatmapPanel/);
  assert.match(filterRailSource, /FilterLogicRail/);
  assert.match(filterRailSource, /AdvancedScreenFilters/);
  assert.match(filterRailSource, /var\(--app-/);
  assert.match(candidateResultsSource, /CandidateResults/);
  assert.match(candidateResultsSource, /CandidateTable/);
  assert.match(gsgfPanelsSource, /GsgfReviewPanel/);
  assert.match(gsgfPanelsSource, /GsgfCalibrationPanel/);
  assert.match(gsgfFunnelSource, /var\(--app-/);
  assert.match(marketPanelsSource, /var\(--app-/);
  assert.match(nestedScreenerSupportSource, /var\(--app-/);
  assert.match(screenerUtilsSource, /export function formatCnyCompact/);
  assert.match(screenerUtilsSource, /export function exportCandidatesCsv/);
  assert.match(screenerTypesSource, /export type CandidateStatusFilter/);
  assert.match(screenerTypesSource, /export type MarketDashboardStats/);
  assert.match(screenerFeatureSource, /aria-label="打开自选股管理页"/);
  assert.match(screenerFeatureSource, /严重异动/);
  assert.match(screenerFeatureSource, /负面新闻待核验/);
  assert.match(screenerFeatureSource, /primaryRiskSummary/);
  assert.match(screenerFeatureSource, /行业/);
  assert.match(screenerFeatureSource, /板块强度/);
  assert.match(screenerFeatureSource, /选股结果/);
  assert.doesNotMatch(screenerFeatureSource, /Screener Results/);
  assert.match(componentSource, /HomepageModelMaintenancePanel/);
  assert.match(screenerFeatureSource, /数据源：/);
  assert.match(screenerFeatureSource, /CandidateTable/);
  assert.match(screenerFeatureSource, /from "antd"/);
  assert.match(screenerFeatureSource, /<Table/);
  assert.match(screenerFeatureSource, /<Segmented/);
  assert.match(screenerFeatureSource, /<Alert/);
  assert.match(screenerFeatureSource, /message\.success/);
  assert.match(screenerFeatureSource, /buildStockDetailHref\(item\.symbol, \{ from: "screener" \}\)/);
  assert.match(screenerFeatureSource, /block font-black text-\[var\(--app-ink\)\] transition hover:text-\[var\(--market-rise\)\]/);
  assert.match(screenerFeatureSource, /selectedSymbol/);
  assert.match(screenerFeatureSource, /selectedCandidateSymbols/);
  assert.match(screenerFeatureSource, /candidateStatusFilter/);
  assert.match(screenerFeatureSource, /gsgfSignalFilter/);
  assert.match(screenerFeatureSource, /filterStockListByGsgf/);
  assert.match(screenerFeatureSource, /排除全局阴量压制/);
  assert.match(screenerFeatureSource, /放量突破/);
  assert.match(screenerFeatureSource, /B区A点/);
  assert.doesNotMatch(screenerFeatureSource, /CandidateDetailPanel/);
  assert.doesNotMatch(screenerFeatureSource, /详情抽屉/);
  assert.doesNotMatch(screenerFeatureSource, /GsgfTradePlanPanel/);
  assert.doesNotMatch(screenerFeatureSource, /analysis\.trade_plan/);
  assert.doesNotMatch(screenerFeatureSource, /function buildLocalGsgfTradePlan/);
  assert.match(screenerFeatureSource, /GsgfReviewPanel/);
  assert.match(screenerFeatureSource, /信号复盘/);
  assert.match(screenerFeatureSource, /保存复盘快照/);
  assert.match(screenerFeatureSource, /复查信号/);
  assert.match(screenerFeatureSource, /reviewSummary/);
  assert.match(screenerFeatureSource, /GsgfCalibrationPanel/);
  assert.match(screenerFeatureSource, /真实样本校准/);
  assert.match(screenerFeatureSource, /运行校准/);
  assert.match(screenerFeatureSource, /综合分/);
  assert.match(screenerFeatureSource, /评级/);
  assert.match(screenerFeatureSource, /诊断分桶/);
  assert.match(screenerFeatureSource, /确认信号/);
  assert.match(screenerFeatureSource, /准备形态/);
  assert.match(screenerFeatureSource, /结构区间/);
  assert.match(screenerFeatureSource, /评分段/);
  assert.match(screenerFeatureSource, /信号后T\+演化/);
  assert.match(screenerFeatureSource, /最大回撤/);
  assert.match(screenerFeatureSource, /GsgfFunnelPanel/);
  assert.match(screenerFeatureSource, /漏斗诊断/);
  assert.match(screenerFeatureSource, /扫描覆盖/);
  assert.match(screenerFeatureSource, /早期观察池/);
  assert.match(screenerFeatureSource, /gsgf_observation_items/);
  assert.match(screenerFeatureSource, /去重股票/);
  assert.match(screenerFeatureSource, /hit_rate/);
  assert.doesNotMatch(homeFeatureSource, /calibrationSummary/);
  assert.doesNotMatch(homeFeatureSource, /createGsgfCalibrationJob/);
  assert.doesNotMatch(homeFeatureSource, /handleRunGsgfCalibration/);
  assert.match(homeWorkspaceSource, /handleLoadMarketSupport/);
  assert.doesNotMatch(homeWorkspaceSource, /void refreshSectorRadar\(\);/);
  assert.doesNotMatch(homeFeatureSource, /refreshGsgfLatest/);
  assert.doesNotMatch(homeWorkspaceSource, /handleLoadDiagnostics/);
  assert.doesNotMatch(homeWorkspaceSource, /void refreshGsgfLatest\(\);/);
  assert.doesNotMatch(homeFeatureSource, /calibrationJob/);
  assert.match(gsgfPanelsSource, /校准任务/);
  assert.match(gsgfPanelsSource, /模型健康/);
  assert.match(screenerFeatureSource, /strongIndustryOnly/);
  assert.match(screenerFeatureSource, /visibleCandidates/);
  assert.match(screenerFeatureSource, /候选筛选/);
  assert.match(screenerFeatureSource, /全部/);
  assert.match(screenerFeatureSource, /强板块/);
  assert.match(screenerFeatureSource, /当前筛选暂无候选/);
  assert.match(screenerFeatureSource, /批量加入自选/);
  assert.match(screenerFeatureSource, /已选/);
  assert.match(screenerFeatureSource, /清空选择/);
  assert.doesNotMatch(screenerFeatureSource, /operationTabs/);
  assert.doesNotMatch(screenerFeatureSource, /activePanel/);
  assert.match(screenerFeatureSource, /结构化自选池/);
  assert.match(screenerFeatureSource, /watchlistPoolItems/);
  assert.doesNotMatch(screenerFeatureSource, /高级文本模式/);
  assert.doesNotMatch(screenerFeatureSource, /保存股票池/);
  assert.match(screenerFeatureSource, /加入自选/);
  assert.match(screenerFeatureSource, /watchlistMessage/);
  assert.match(screenerFeatureSource, /已在自选/);
  assert.match(homeFeatureSource, /已加入自选/);
  assert.match(screenerFeatureSource, /onAddToWatchlist/);
  assert.match(screenerFeatureSource, /placeholder="批量分组"/);
  assert.match(screenerFeatureSource, /placeholder="批量标签，逗号分隔"/);
  assert.match(screenerFeatureSource, /splitTags/);
  assert.match(screenerFeatureSource, /分组/);
  assert.match(screenerFeatureSource, /标签/);
  assert.match(screenerFeatureSource, /TickFlow/);
  assert.match(screenerFeatureSource, /运行筛选/);
  assert.match(screenerFeatureSource, /MarketTickerBar/);
  assert.match(screenerFeatureSource, /findMarketIndex\(indices, "399006\.SZ", "创业板"\)/);
  assert.match(screenerFeatureSource, /findMarketIndex\(indices, "000688\.SH", "科创50"\)/);
  assert.match(screenerFeatureSource, /formatSignedPercent\(changePct\)/);
  assert.match(screenerFeatureSource, /MarketEnvironmentPanel/);
  assert.match(screenerFeatureSource, /FilterLogicRail/);
  assert.match(screenerFeatureSource, /SectorStrengthPanel/);
  assert.match(screenerFeatureSource, /sectorRadar/);
  assert.match(screenerFeatureSource, /SectorRadarResponse/);
  assert.match(screenerFeatureSource, /SectorRadarItem/);
  assert.match(screenerFeatureSource, /SectorFlowHeatmapPanel/);
  assert.match(screenerFeatureSource, /板块资金流热力/);
  assert.match(screenerFeatureSource, /净流入 Top5/);
  assert.match(screenerFeatureSource, /净流出 Top5/);
  assert.match(screenerFeatureSource, /板块强度待接入/);
  assert.match(screenerFeatureSource, /后续将接入非资金流口径的板块强度模型/);
  assert.doesNotMatch(screenerFeatureSource, /<SectorRadarGroup/);
  assert.doesNotMatch(screenerFeatureSource, /<SectorStrengthRow/);
  assert.doesNotMatch(screenerFeatureSource, /buildSectorStrengthItems/);
  assert.match(screenerFeatureSource, /MarketMetric/);
  assert.doesNotMatch(screenerFeatureSource, /TurnoverTrendPanel/);
  assert.match(screenerFeatureSource, /DesignScreenerResultsTable/);
  assert.match(screenerFeatureSource, /StockMaster/);
  assert.match(screenerFeatureSource, /选股结果/);
  assert.doesNotMatch(screenerFeatureSource, /Screener Results/);
  assert.doesNotMatch(screenerFeatureSource, /趋势 TREND/);
  assert.doesNotMatch(screenerFeatureSource, /MiniTrendSparkline/);
  assert.doesNotMatch(screenerFeatureSource, /全A成交额趋势 · A-share Turnover/);
  assert.match(screenerFeatureSource, /iFinD 实时口径 · 今日相对昨日/);
  assert.match(screenerFeatureSource, /TickFlow 实时口径 · 今日相对昨日/);
  assert.match(screenerFeatureSource, /realtimeTurnoverSourceLabel/);
  assert.match(screenerFeatureSource, /全A市场口径/);
  assert.match(screenerFeatureSource, /label="总成交额"/);
  assert.doesNotMatch(screenerFeatureSource, /北向资金流入趋势 · Northbound Flow Trend/);
  assert.doesNotMatch(screenerFeatureSource, /北向资金/);
  assert.match(screenerFeatureSource, /情绪指数/);
  assert.match(screenerFeatureSource, /上涨 \/ 下跌/);
  assert.match(screenerFeatureSource, /运行筛选/);
  assert.match(screenerFeatureSource, /导出 CSV/);
  assert.doesNotMatch(screenerFeatureSource, /function IntradayPanel/);
  assert.doesNotMatch(screenerFeatureSource, />2\. 盘中监控</);
  assert.doesNotMatch(screenerFeatureSource, /运行盘中监控/);
  assert.match(screenerFeatureSource, /CandidateCardList/);
  assert.match(screenerFeatureSource, /lg:hidden/);
  assert.match(screenerFeatureSource, /hidden overflow-x-auto lg:block/);
  for (const source of [
    auctionWorkspaceSource,
    componentSource,
    watchlistWorkspaceSource,
    sentimentWorkspaceSource,
    stockWorkspaceSource,
  ]) {
    assert.doesNotMatch(source, /WorkbenchPage/);
    assert.match(source, /<PageFrame\b/);
  }
  for (const source of [auctionPageSource, watchlistPageSource, sentimentPageSource, stockPageSource]) {
    assert.doesNotMatch(source, /WorkbenchPage/);
    assert.match(source, /<PageFrame\b/);
    assert.match(source, /aria-busy/);
    assert.match(source, /Skeleton/);
  }
  assert.match(screenerFeatureSource, /grid items-stretch gap-4 xl:grid-cols-\[minmax\(0,2fr\)_minmax\(360px,1fr\)\]/);
  assert.match(componentSource, /HomepageMarketSupportPanel/);
  assert.match(componentSource, /onLoadMarketSupport/);
  assert.match(componentSource, /marketSupportOpen/);
  assert.match(componentSource, /HomepageModelMaintenancePanel/);
  assert.match(componentSource, /查看模型维护/);
  assert.doesNotMatch(componentSource, /HomepageDiagnosticsPanel/);
  assert.doesNotMatch(componentSource, /模型诊断/);
  assert.doesNotMatch(componentSource, /onLoadDiagnostics/);
  assert.doesNotMatch(componentSource, /diagnosticsOpen/);
  assert.doesNotMatch(componentSource, /CoreWorkflowNav/);
  assert.match(screenerFeatureSource, /screener-metrics/);
  assert.doesNotMatch(screenerFeatureSource, /xl:grid-cols-\[280px_minmax\(0,1fr\)_320px\]/);
  assert.match(screenerFeatureSource, /点击股票名称查看 K 线详情/);
  assert.match(pageSource, /dynamic[<(]/);
  assert.match(pageSource, /MarketOverviewWorkbench/);
  assert.doesNotMatch(pageSource, /HomeWorkbench/);
  assert.ok(screenerPageSource);
  assert.match(screenerPageSource, /import \{ HomeWorkbench \} from "\.\.\/HomeWorkbench"/);
  assert.match(screenerPageSource, /return <HomeWorkbench \/>;/);
  assert.doesNotMatch(screenerPageSource, /useState|useEffect|createScreenRunJob|pollScreenRunJob|screenFilters/);
  assert.match(homeFeatureSource, /ScreenerWorkbench/);
  assert.match(homeFeatureSource, /const \[scanLimit, setScanLimit\] = useState\(160\)/);
  assert.doesNotMatch(homeFeatureSource, /createIntradaySnapshot/);
  assert.doesNotMatch(homeFeatureSource + screenerFeatureSource, /onRunIntraday|intradaySymbolsText|useWatchlistPool/);
  assert.match(homeFeatureSource, /addWatchlistPoolItem/);
  assert.match(homeFeatureSource, /handleAddManyToWatchlist/);
  assert.match(homeFeatureSource, /onAddManyToWatchlist/);
  assert.match(screenerFeatureSource, /管理自选股/);
  assert.match(componentSource, /title="强势选股"/);
  assert.match(componentSource, /context=\{/);
  assert.match(watchlistFeatureSource, /自选股管理/);
  assert.match(watchlistWorkspaceSource, /<Button href="\/screener">返回选股<\/Button>/);
  assert.match(watchlistPageSource, /WatchlistWorkspace/);
  assert.match(watchlistFeatureSource, /dynamic[<(]/);
  assert.match(watchlistFeatureSource, /WatchlistEditorPanel/);
  assert.match(watchlistFeatureSource, /WatchlistManagerPanel/);
  assert.doesNotMatch(watchlistFeatureSource, /WorkbenchPage/);
  assert.match(watchlistFeatureSource, /workbench-panel/);
  assert.match(watchlistFeatureSource, /from "antd"/);
  assert.match(watchlistFeatureSource, /<Table/);
  assert.match(watchlistFeatureSource, /<Form/);
  assert.match(watchlistFeatureSource, /<Segmented/);
  assert.match(watchlistFeatureSource, /<Alert/);
  assert.match(watchlistFeatureSource, /message\.success/);
  assert.match(watchlistFeatureSource, /分组/);
  assert.match(watchlistFeatureSource, /标签/);
  assert.match(watchlistFeatureSource, /备注/);
  assert.match(watchlistFeatureSource, /批量移动/);
  assert.match(watchlistFeatureSource, /删除/);
  assert.match(watchlistFeatureSource, /saveWatchlistPool/);
  assert.match(watchlistFeatureSource, /addWatchlistPoolItem/);
  assert.match(watchlistFeatureSource, /getWatchlistGsgfStatus/);
  assert.match(watchlistFeatureSource, /结构触发/);
  assert.match(watchlistFeatureSource, /机会触发/);
  assert.match(watchlistFeatureSource, /C区\/回避/);
  assert.match(settingsPageSource, /redirect\("\/system\?tab=data"\)/);
  assert.match(settingsFeatureSource, /loading && !config/);
  assert.match(settingsWorkspaceSource, /export function SettingsContent/);
  assert.match(typesSource, /SectorWorkbenchResponse/);
  assert.match(typesSource, /SectorWorkbenchStatusResponse/);
  assert.match(typesSource, /SectorWorkbenchCacheSummary/);
  assert.match(typesSource, /SectorWorkbenchTheme/);
  assert.match(typesSource, /SectorWorkbenchStock/);
  assert.match(typesSource, /PlateRotationReferenceResponse/);
  assert.match(typesSource, /PlateRotationThemeItem/);
  assert.match(typesSource, /SectorReplicaRadarResponse/);
  assert.match(typesSource, /SectorReplicaStocksResponse/);
  assert.match(typesSource, /SectorReplicaStockRow/);
  assert.match(apiSource, /getSectorWorkbench/);
  assert.match(apiSource, /getSectorWorkbenchStatus/);
  assert.match(apiSource, /getPlateRotationReference/);
  assert.match(apiSource, /\/api\/sectors\/plate-reference/);
  assert.match(apiSource, /getSectorReplicaRadar/);
  assert.match(apiSource, /getSectorReplicaBoardStocks/);
  assert.match(apiSource, /getSectorReplicaBoardStocks[\s\S]{0,900}boardName/);
  assert.doesNotMatch(apiSource, /getSectorReplicaRadar[\s\S]{0,700}boardName/);
  assert.match(apiSource, /\/api\/sectors\/replica\/radar/);
  assert.match(apiSource, /\/api\/sectors\/replica\/boards/);
  assert.match(sectorsFeatureSource, /SectorReplicaWorkspace/);
  assert.match(sectorsFeatureSource, /SectorReplicaPanel/);
  assert.match(sectorsFeatureSource, /market-radar-shell/);
  assert.match(sectorsFeatureSource, /情绪指标/);
  assert.match(sectorsFeatureSource, /涨停家数/);
  assert.match(sectorsFeatureSource, /今日封板率/);
  assert.match(sectorsFeatureSource, /getSectorReplicaRadar/);
  assert.match(sectorsFeatureSource, /getSectorReplicaBoardStocks/);
  assert.match(sectorsFeatureSource, /boardName/);
  assert.match(sectorsFeatureSource, /sessionStorage/);
  assert.match(sectorsFeatureSource, /15_000/);
  assert.match(sectorsFeatureSource, /8_000/);
  assert.match(sectorsFeatureSource, /板块强度/);
  assert.match(sectorsFeatureSource, /主力流入/);
  assert.match(sectorsFeatureSource, /名称/);
  assert.match(sectorsFeatureSource, /代码/);
  assert.match(sectorsFeatureSource, /涨幅/);
  assert.match(sectorsFeatureSource, /成交/);
  assert.match(sectorsFeatureSource, /流通/);
  assert.match(sectorsFeatureSource, /板数/);
  assert.match(sectorsFeatureSource, /竞涨/);
  assert.match(sectorsFeatureSource, /竞额/);
  assert.match(sectorsFeatureSource, /竞量/);
  assert.match(sectorsFeatureSource, /买成比/);
  assert.match(sectorsFeatureSource, /封单/);
  assert.match(sectorsFeatureSource, /buildSectorReplicaChartOption/);
  assert.match(sectorsFeatureSource, /axisPointer/);
  assert.match(sectorsFeatureSource, /09:15/);
  assert.match(sectorsFeatureSource, /15:00/);
  assert.match(sectorsFeatureSource, /connectNulls/);
  assert.match(sectorsFeatureSource, /ResizeObserver/);
  assert.match(sectorReplicaCssSource, /var\(--app-surface\)/);
  assert.match(sectorReplicaCssSource, /var\(--app-border\)/);
  assert.match(sectorReplicaCssSource, /font: inherit/);
  assert.doesNotMatch(sectorReplicaCssSource, /font-family:\s*Arial/);
  assert.doesNotMatch(sectorReplicaCssSource, /#d9534f|#d43f3a|#f0ad4e|#5cb85c/);
  assert.doesNotMatch(sectorReplicaCssSource, /#fff(?:fff)?\b/);
  assert.match(sectorsReplicaChartSource, /backgroundColor: APP_RAISED/);
  assert.doesNotMatch(sectorsReplicaChartSource, /WORKBENCH_/);
  assert.match(sectorsReplicaChartSource, /smooth: item\.smooth \? 0\.32 : false/);
  assert.doesNotMatch(sectorsReplicaChartSource, /backgroundColor:\s*"#ffffff"/);
  assert.doesNotMatch(sectorsFeatureSource, /max: isStrength \\? 100/);
  assert.doesNotMatch(sectorsWorkspaceSource, /PlateReferencePanel/);
  assert.doesNotMatch(sectorsWorkspaceSource, /SectorThemeWorkbench/);
  assert.doesNotMatch(sectorsFeatureSource, /行业多选/);
  assert.doesNotMatch(sectorsFeatureSource, /双模式分时/);
  assert.doesNotMatch(sectorsFeatureSource, /板块强度分时/);
  assert.doesNotMatch(sectorsFeatureSource, /行业强度工作台/);
  assert.doesNotMatch(sectorsFeatureSource, /题材多选/);
  assert.doesNotMatch(sectorsFeatureSource, /概念\/题材优先/);
  assert.doesNotMatch(sectorsFeatureSource, /trailColor/);
  assert.match(marketPageSource, /MarketWorkspace/);
  assert.match(marketWorkspaceSource, /PageFrame/);
  assert.match(marketWorkspaceSource, /Segmented/);
  assert.match(marketWorkspaceSource, /normalizeMarketView/);
  assert.match(marketWorkspaceSource, /router\.replace\("\/market\?view=" \+ next, \{ scroll: false \}\)/);
  assert.match(sectorsPageSource, /redirect\("\/market\?view=sectors"\)/);
  assert.match(heatmapPageSource, /redirect\("\/market\?view=heatmap"\)/);
  assert.doesNotMatch(sectorsPageSource, /"use client"/);
  assert.doesNotMatch(heatmapPageSource, /"use client"/);
  assert.match(auctionPageSource, /dynamic[<(]/);
  assert.match(auctionFeatureSource, /竞价雷达/);
  assert.match(auctionFeatureSource, /getAuctionLatest/);
  assert.match(auctionFeatureSource, /getAuctionTimeline/);
  assert.match(auctionFeatureSource, /竞价时间轴/);
  assert.match(auctionFeatureSource, /连续出现/);
  assert.match(auctionFeatureSource, /新晋/);
  assert.match(auctionFeatureSource, /缓存年龄/);
  assert.match(auctionFeatureSource, /竞价可信度/);
  assert.match(auctionFeatureSource, /AuctionTrustStrip/);
  assert.match(auctionFeatureSource, /自动快照/);
  assert.match(auctionFeatureSource, /createAuctionSnapshotJob/);
  assert.match(auctionFeatureSource, /getAuctionSnapshotJob/);
  assert.match(auctionFeatureSource, /refreshJob/);
  assert.match(auctionFeatureSource, /createAuctionModelTop3Job/);
  assert.match(auctionFeatureSource, /getAuctionModelTop3Job/);
  assert.match(auctionFeatureSource, /modelRefreshJob/);
  assert.match(auctionFeatureSource, /shouldShowPreviewItems = previewItems\.length > 0/);
  assert.doesNotMatch(auctionFeatureSource, /getAuctionModelTop3\\(modelTradeDate, \\{ refresh: true \\}\\)/);
  assert.doesNotMatch(auctionWorkspaceSource, /getAuctionSnapshot\(/);
  assert.match(auctionFeatureSource, /竞价强度榜/);
  assert.match(auctionFeatureSource, /热门题材/);
  assert.match(auctionFeatureSource, /题材共振/);
  assert.match(auctionFeatureSource, /theme_auction_rank/);
  assert.match(auctionFeatureSource, /风险与观察/);
  assert.match(auctionFeatureSource, /行业筛选/);
  assert.match(auctionFeatureSource, /IndustryQuickFilter/);
  assert.match(auctionFeatureSource, /auction-command-strip/);
  assert.match(auctionFeatureSource, /auction-primary-grid/);
  assert.match(auctionFeatureSource, /auction-side-rail/);
  assert.match(auctionFeatureSource, /AuctionControlBar/);
  assert.match(auctionWorkspaceSource, /<Select/);
  assert.match(auctionFeatureSource, /更多行业/);
  assert.match(auctionFeatureSource, /主线集中度/);
  assert.match(auctionFeatureSource, /高开风险阈值/);
  assert.match(auctionFeatureSource, /加入自选/);
  assert.match(auctionFeatureSource, /行业/);
  assert.match(auctionFeatureSource, /当前涨幅/);
  assert.match(auctionFeatureSource, /开盘幅度/);
  assert.match(auctionFeatureSource, /强势高开/);
  assert.match(auctionFeatureSource, /低开观察/);
  assert.match(auctionFeatureSource, /auction-status-strip/);
  assert.doesNotMatch(auctionFeatureSource, /auction-command-grid/);
  assert.match(auctionFeatureSource, /主线行业 Top/);
  assert.match(auctionFeatureSource, /阶段快照/);
  assert.match(auctionFeatureSource, /数据源状态/);
  assert.match(auctionFeatureSource, /竞价复盘/);
  assert.ok(
    auctionWorkspaceSource.indexOf("<AuctionReviewPanel") > auctionWorkspaceSource.indexOf("竞价强度榜"),
    "竞价复盘应显示在竞价强度榜下方",
  );
  assert.match(auctionFeatureSource, /规则统计/);
  assert.match(auctionFeatureSource, /失败样本/);
  assert.match(auctionFeatureSource, /生成\/刷新今日复盘/);
  assert.match(auctionFeatureSource, /message\.error/);
  assert.match(auctionFeatureSource, /Collapse/);
  assert.match(sentimentPageSource, /SentimentWorkspace/);
  assert.match(sentimentFeatureSource, /短线情绪中心/);
  assert.match(sentimentFeatureSource, /交易许可/);
  assert.match(sentimentFeatureSource, /市场状态/);
  assert.match(sentimentFeatureSource, /风险等级/);
  assert.match(sentimentFeatureSource, /自选股联动/);
  assert.match(sentimentFeatureSource, /重点盯/);
  assert.match(sentimentFeatureSource, /等确认/);
  assert.match(sentimentFeatureSource, /风险回避/);
  assert.match(sentimentFeatureSource, /getSentimentWatchlistAlerts/);
  assert.match(sentimentFeatureSource, /市场情绪仪表盘/);
  assert.match(sentimentFeatureSource, /情绪指标/);
  assert.match(sentimentFeatureSource, /亏钱效应/);
  assert.match(sentimentFeatureSource, /今日封板率/);
  assert.match(sentimentFeatureSource, /涨跌幅分布/);
  assert.match(sentimentFeatureSource, /日内情绪落点/);
  assert.match(sentimentFeatureSource, /EmotionHistoryChart/);
  assert.match(sentimentFeatureSource, /真实采样曲线/);
  assert.match(sentimentFeatureSource, /竞价定调/);
  assert.match(sentimentFeatureSource, /开盘承接/);
  assert.match(sentimentFeatureSource, /情绪确认/);
  assert.match(sentimentFeatureSource, /上午定性/);
  assert.match(sentimentFeatureSource, /尾盘风险/);
  assert.match(sentimentFeatureSource, /getSentimentSummary/);
  assert.match(sentimentFeatureSource, /getSentimentDetail/);
  assert.match(sentimentFeatureSource, /涨停池/);
  assert.match(sentimentFeatureSource, /炸板池/);
  assert.match(sentimentFeatureSource, /连板天梯/);
  assert.match(sentimentFeatureSource, /盘中情绪快照/);
  assert.match(sentimentFeatureSource, /TickFlow 实时行情/);
  assert.match(sentimentFeatureSource, /getMarketRankings/);
  assert.match(sentimentFeatureSource, /TickFlow涨幅榜/);
  assert.match(sentimentFeatureSource, /TickFlow成交额榜/);
  assert.match(sentimentFeatureSource, /MarketRankingPanel/);
  assert.match(sentimentFeatureSource, /getShortTermIntradaySentiment/);
  assert.match(sentimentFeatureSource, /getShortTermIntradaySignalDigest/);
  assert.match(sentimentFeatureSource, /提醒草稿/);
  assert.match(sentimentFeatureSource, /复制草稿/);
  assert.match(sentimentFeatureSource, /发送草稿/);
  assert.match(sentimentFeatureSource, /sendNotificationMessage/);
  assert.match(sentimentFeatureSource, /后台监控/);
  assert.match(sentimentFeatureSource, /getSentimentMonitorStatus/);
  assert.match(sentimentFeatureSource, /startSentimentMonitor/);
  assert.match(sentimentFeatureSource, /stopSentimentMonitor/);
  assert.match(sentimentFeatureSource, /runSentimentMonitorOnce/);
  assert.match(sentimentFeatureSource, /规则校准/);
  assert.match(sentimentFeatureSource, /每日归档情绪结论/);
  assert.doesNotMatch(sentimentFeatureSource, /<Alert[^>]*message=/);
  assert.doesNotMatch(sectorsFeatureSource, /<Alert[^>]*message=/);
  assert.match(modelMaintenancePageSource, /redirect\("\/system\?tab=model"\)/);
  assert.match(systemPageSource, /SystemWorkspace/);
  assert.match(systemPageSource, /fallback=\{<SystemWorkspaceFallback \/>\}/);
  assert.match(systemPageSource, /PageFrame/);
  assert.match(systemPageSource, /Skeleton/);
  assert.match(systemPageSource, /aria-busy/);
  assert.match(systemWorkspaceSource, /"use client"/);
  assert.match(systemFeatureSource, /PageFrame/);
  assert.match(systemFeatureSource, /title="模型与数据源"/);
  assert.match(systemFeatureSource, /Segmented/);
  assert.match(systemFeatureSource, /ModelMaintenanceContent/);
  assert.match(systemFeatureSource, /SettingsContent/);
  assert.match(systemFeatureSource, /normalizeSystemTab/);
  assert.match(systemFeatureSource, /createVisitedSystemTabs/);
  assert.match(systemFeatureSource, /visitSystemTab/);
  assert.match(systemWorkspaceSource, /visitedTabs\.includes\("model"\)/);
  assert.match(systemWorkspaceSource, /visitedTabs\.includes\("data"\)/);
  assert.match(systemWorkspaceSource, /hidden=\{tab !== "model"\}/);
  assert.match(systemWorkspaceSource, /hidden=\{tab !== "data"\}/);
  assert.match(systemFeatureSource, /router\.replace\(buildSystemTabHref\(next\), \{ scroll: false \}\)/);
  assert.match(modelMaintenanceWorkspaceSource, /export function ModelMaintenanceContent/);
  assert.match(modelMaintenanceWorkspaceSource, /void loadMaintenanceState\(\(\) => active\)/);
  assert.match(settingsWorkspaceSource, /void loadSettings\(\(\) => active\)/);
  assert.match(settingsWorkspaceSource, /void loadSystemStatus\(\(\) => active\)/);
  assert.match(modelMaintenanceFeatureSource, /AI 模型维护/);
  assert.match(modelMaintenanceFeatureSource, /待确认建议/);
  assert.match(modelMaintenanceFeatureSource, /生成数据包/);
  assert.match(modelMaintenanceFeatureSource, /复制给 Codex/);
  assert.match(modelMaintenanceFeatureSource, /竞价 Top3 训练/);
  assert.match(modelMaintenanceFeatureSource, /模拟收益/);
  assert.match(modelMaintenanceFeatureSource, /ModelMaintenancePacketPage/);
  assert.match(settingsFeatureSource, /竞价 Top3 训练/);
  assert.match(settingsFeatureSource, /记录 Top3 信号样本/);
  assert.match(settingsFeatureSource, /生成模拟交易样本/);
  assert.match(settingsFeatureSource, /人工交易样本进入训练/);
  assert.match(sentimentFeatureSource, /ShortTermSentimentResponse/);
  assert.match(sentimentFeatureSource, /ShortTermIntradaySentimentResponse/);
  assert.match(sentimentFeatureSource, /ShortTermIntradaySignalDigest/);
  assert.match(sentimentPageSource, /dynamic[<(]/);
  assert.match(sentimentFeatureSource, /IntradaySentimentPanel/);
  assert.match(sentimentIntradaySource, /overflow-x-auto/);
  assert.match(sentimentIntradaySource, /max-w-full/);
  assert.match(sentimentFeatureSource, /StockPoolTable/);
  assert.match(stockPageSource, /dynamic[<(]/);
  assert.match(stockPageSource, /StockKlineWorkspace/);
  assert.match(stockFeatureSource, /getStockKline/);
  assert.match(stockFeatureSource, /getStockResearch/);
  assert.match(stockFeatureSource, /shouldLoadResearch/);
  assert.match(stockFeatureSource, /StockResearchResponse/);
  assert.match(stockFeatureSource, /TickFlowKlineChart/);
  assert.match(stockPageSource, /kline-charts-react\/style\.css/);
  assert.match(stockFeatureSource, /from "antd"/);
  assert.match(stockFeatureSource, /<Card/);
  assert.match(stockFeatureSource, /<Segmented/);
  assert.match(stockFeatureSource, /<Alert/);
  assert.match(stockFeatureSource, /<Spin/);
  assert.match(stockFeatureSource, /GSGF 证据/);
  assert.match(stockFeatureSource, /showGsgfAnnotations/);
  assert.match(stockFeatureSource, /annotationCount/);
  assert.match(stockFeatureSource, /canShowGsgfAnnotations/);
  assert.match(stockFeatureSource, /GsgfEvidenceSummary/);
  assert.match(stockFeatureSource, /显示证据/);
  assert.match(stockFeatureSource, /隐藏证据/);
  assert.match(stockFeatureSource, /chartDataSource/);
  assert.doesNotMatch(stockFeatureSource, /TickFlow \/ 组件内置/);
  assert.doesNotMatch(stockFeatureSource, /组件内置源仅用于图表对照/);
  assert.match(stockChartSource, /kline-charts-react/);
  assert.doesNotMatch(layoutSource, /kline-charts-react\/style\.css/);
  assert.match(sentimentFeatureSource, /loadSentimentDetail/);
  assert.match(sentimentFeatureSource, /void loadSentimentDetail/);
  assert.match(layoutSource, /AntdRegistry/);
  assert.match(layoutSource, /AntdAppProvider/);
  assert.match(antdProviderSource, /ConfigProvider/);
  assert.match(antdProviderSource, /zhCN/);
  assert.match(antdProviderSource, /autoInsertSpace: false/);
  assert.match(stockChartSource, /dataProvider/);
  assert.match(stockChartSource, /dataSourceMode/);
  assert.match(stockChartSource, /dataSourceMode === "tickflow"/);
  assert.match(stockChartSource, /dataProvider=\{tickflowDataProvider\}/);
  assert.doesNotMatch(stockChartSource, /builtinStockSdkSymbol/);
  assert.doesNotMatch(stockChartSource, /builtinDataSourceError/);
  assert.doesNotMatch(stockChartSource, /handleChartError/);
  assert.doesNotMatch(stockChartSource, /onError=\{handleChartError\}/);
  assert.doesNotMatch(stockChartSource, /组件内置 K 线源加载失败/);
  assert.match(stockChartSource, /getKline/);
  assert.match(stockChartSource, /useCallback/);
  assert.match(stockChartSource, /handleDataLoad/);
  assert.match(stockChartSource, /requestOptions/);
  assert.match(stockFeatureSource, /StockListPanel/);
  assert.match(stockFeatureSource, /candidateListCollapsed/);
  assert.match(stockFeatureSource, /const \[candidateListCollapsed, setCandidateListCollapsed\] = useState\(false\)/);
  assert.match(stockFeatureSource, /filterStockList/);
  assert.match(stockFeatureSource, /stockListStatusOptions/);
  assert.match(stockFeatureSource, /搜索候选股票/);
  assert.match(stockFeatureSource, /候选状态筛选/);
  assert.match(stockFeatureSource, /lg:grid-cols-\[168px_minmax\(0,1fr\)\]/);
  assert.match(stockFeatureSource, /lg:grid-cols-\[248px_minmax\(0,1fr\)\]/);
  assert.match(stockFeatureSource, /紧凑列表/);
  assert.match(stockFeatureSource, /展开股票列表|收起股票列表/);
  assert.doesNotMatch(stockFeatureSource, /max-w-\[30px\]/);
  assert.doesNotMatch(stockFeatureSource, /compactStockLabel/);
  assert.match(stockFeatureSource, /ChartControlBar/);
  assert.match(stockFeatureSource, /行情摘要/);
  assert.match(apiSource, /getStockQuote/);
  assert.match(typesSource, /StockQuoteResponse/);
  assert.match(typesSource, /total_market_cap_cny/);
  assert.match(typesSource, /pe_ttm/);
  assert.match(typesSource, /pe_static/);
  assert.match(stockFeatureSource, /formatTurnoverRate\(quote\?\.turnoverRate \?\? null\)/);
  assert.doesNotMatch(stockFeatureSource, /<HeaderMetric label="换" value="--" \/>/);
  assert.match(stockFeatureSource, /formatSourceStatus/);
  assert.match(stockFeatureSource, /status === "success"/);
  assert.match(stockFeatureSource, /可用/);
  assert.doesNotMatch(stockFeatureSource, /行情摘要 · \{source\} · \{status\}/);
  assert.match(stockFeatureSource, /股票列表/);
  assert.match(stockFeatureSource, /日 K 线/);
  assert.match(stockChartSource, /volume/);
  assert.match(stockChartSource, /indicatorOptions/);
  assert.match(stockChartSource, /buildKlineIndicatorOptions/);
  assert.doesNotMatch(stockChartSource, /periods: \[5, 10, 20, 60\]/);
  assert.doesNotMatch(stockFeatureSource, /function VolumeChart/);
  assert.doesNotMatch(stockFeatureSource, /function KdjChart/);
  assert.doesNotMatch(stockFeatureSource, /MomentumChart/);
  assert.doesNotMatch(stockFeatureSource, /buildMomentumPoints/);
  assert.doesNotMatch(stockFeatureSource, /动量/);
  assert.doesNotMatch(stockFeatureSource, /FAST:/);
  assert.doesNotMatch(stockFeatureSource, /SLOW:/);
  assert.match(stockFeatureSource, /KLINE_CHART_HEIGHT/);
  assert.match(stockFeatureSource, /h-\[calc\(100vh-236px\)\]/);
  assert.doesNotMatch(stockFeatureSource, /preserveAspectRatio="none"/);
  assert.doesNotMatch(stockFeatureSource, /data\.source_status\.detail/);
  assert.match(stockFeatureSource, /MovingAverageControl/);
  assert.match(stockFeatureSource, /type MovingAverageField = "ma5" \| "ma10" \| "ma20" \| "ma60"/);
  assert.match(stockFeatureSource, /visibleMovingAverages/);
  assert.match(stockFeatureSource, /MA60/);
  assert.match(stockFeatureSource, /activeChartTab/);
  assert.match(stockFeatureSource, /overflow-x-auto border-b border-slate-200 bg-slate-50/);
  assert.match(stockFeatureSource, /grid min-w-\[520px\] grid-cols-5/);
  assert.match(stockFeatureSource, /onChange=\{\(value\) => onChange\(value as ChartTab\)\}/);
  assert.doesNotMatch(stockFeatureSource, /key: "research"/);
  assert.doesNotMatch(stockFeatureSource, /label: "研究"/);
  assert.doesNotMatch(stockFeatureSource, /activeTab === "research"/);
  assert.doesNotMatch(stockFeatureSource, /iFinD 研究/);
  assert.doesNotMatch(stockFeatureSource, /<ResearchPanel/);
  assert.doesNotMatch(stockFeatureSource, /label="K线数量"/);
  assert.doesNotMatch(stockFeatureSource, /label="MA5"/);
  assert.doesNotMatch(stockFeatureSource, /label="MA10"/);
  assert.doesNotMatch(stockFeatureSource, /label="MA20"/);
  assert.doesNotMatch(stockFeatureSource, /label="MA60"/);
  assert.match(stockFeatureSource, /总市值/);
  assert.match(stockFeatureSource, /动态市盈率/);
  assert.match(stockFeatureSource, /静态市盈率/);
  assert.match(stockFeatureSource, /formatMarketCapCny\(quote\?\.totalMarketCapCny \?\? null\)/);
  assert.match(stockFeatureSource, /formatValuationRatio\(quote\?\.peTtm \?\? null\)/);
  assert.match(stockFeatureSource, /formatValuationRatio\(quote\?\.peStatic \?\? null\)/);
  assert.match(stockFeatureSource, /股是股非模型选股条件/);
  assert.doesNotMatch(stockFeatureSource, /财务估值/);
  assert.doesNotMatch(stockFeatureSource, /公告新闻/);
  assert.doesNotMatch(stockFeatureSource, /title="板块强度"/);
  assert.match(stockFeatureSource, /setActiveChartTab/);
  assert.match(stockFeatureSource, /buildMovingAverageBars/);
  assert.match(stockFeatureSource, /buildWeeklyBars/);
  assert.match(stockChartSource, /convertBarsForKlineChart/);
  assert.doesNotMatch(stockFeatureSource, /chartWindowSize/);
  assert.doesNotMatch(stockFeatureSource, /onWheel/);
  assert.doesNotMatch(stockFeatureSource, /visibleBars/);
  assert.doesNotMatch(stockFeatureSource, /返回 \{bars\.length\} 条日K/);
  assert.doesNotMatch(stockFeatureSource, /xl:min-w-\[980px\]/);
  assert.doesNotMatch(stockFeatureSource, /xl:grid-cols-\[minmax\(0,1fr\)_270px\]/);
  assert.doesNotMatch(stockFeatureSource, /h-\[500px\]/);
  assert.doesNotMatch(watchlistFeatureSource, /盘中监控/);
  assert.doesNotMatch(screenerFeatureSource + homeFeatureSource, /报告生成|历史报告|OCR|定时生成/);
  assert.match(settingsFeatureSource, /iFinD 研究增强/);
  assert.match(settingsFeatureSource, /通知渠道/);
  assert.match(settingsFeatureSource, /AI 分析服务/);
  assert.match(settingsFeatureSource, /DeepSeek/);
  assert.match(settingsFeatureSource, /GSGF 自动复盘/);
  assert.match(settingsFeatureSource, /weekly_calibration_scan_limit/);
  assert.match(settingsFeatureSource, /notify_on_degradation/);
  assert.match(settingsFeatureSource, /企业微信/);
  assert.match(settingsFeatureSource, /飞书/);
  assert.match(settingsFeatureSource, /Telegram/);
  assert.match(settingsFeatureSource, /邮件/);
  assert.match(settingsFeatureSource, /ifind_api_key/);
  assert.match(settingsFeatureSource, /ifind_base_url/);
  assert.match(settingsFeatureSource, /hexin-ifind-ds-stock-mcp/);
  assert.match(settingsFeatureSource, /不替代 TickFlow 行情/);
  assert.equal(settingsWorkspaceSource.match(/form=\{form\}/g)?.length ?? 0, 1);
  assert.ok(webPackageSource.includes('"smoke:ui": "node ../../scripts/smoke-ui.mjs"'));
  assert.match(smokeUiSource, /hasHorizontalOverflow/);
  assert.match(smokeUiSource, /Next\.js error overlay detected/);
});

test("app shell uses grouped navigation with responsive collapse and mobile access", () => {
  const source = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");

  assert.match(source, /navigationGroups/);
  assert.match(source, /getNavigationSelection/);
  assert.match(source, /readAppShellCollapsed/);
  assert.match(source, /toggleAppShellCollapsed/);
  assert.match(source, /resolveMobileNavigationOpen/);
  assert.match(source, /Drawer/);
  assert.match(source, /window\.matchMedia\("\(min-width: 980px\)"\)/);
  assert.match(source, /addEventListener\("change", handleDesktopViewportChange\)/);
  assert.match(source, /removeEventListener\("change", handleDesktopViewportChange\)/);
  assert.match(source, /width=\{216\}/);
  assert.match(source, /collapsedWidth=\{64\}/);
  assert.match(source, /aria-label="打开导航"/);
  assert.match(source, /aria-label="主导航"/);
  assert.match(source, /StockMaster/);
  assert.doesNotMatch(source, /NAV_ITEMS/);
  assert.doesNotMatch(source, /STOCK_NAV_ITEMS/);
  assert.doesNotMatch(source, /DatabaseOutlined/);
});

test("PageFrame flush content variant overrides default padding for stock K-line surfaces", () => {
  const pageFrameSource = readFileSync(new URL("../components/workbench/PageFrame.tsx", import.meta.url), "utf8");
  const globalsSource = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const stockWorkspaceSource = readFileSync(new URL("../app/stock/[symbol]/StockKlineWorkspace.tsx", import.meta.url), "utf8");
  const stockPageSource = readFileSync(new URL("../app/stock/[symbol]/page.tsx", import.meta.url), "utf8");
  const defaultContentRule = globalsSource.indexOf(".page-frame__content {");
  const flushContentRule = globalsSource.indexOf(".page-frame__content.page-frame__content--flush {");

  assert.match(pageFrameSource, /contentVariant\?: "default" \| "flush"/);
  assert.match(pageFrameSource, /contentVariant === "flush" && "page-frame__content--flush"/);
  assert.match(globalsSource, /\.page-frame__content\.page-frame__content--flush\s*\{\s*padding:\s*0;/);
  assert.ok(defaultContentRule >= 0);
  assert.ok(flushContentRule > defaultContentRule);
  for (const source of [stockWorkspaceSource, stockPageSource]) {
    assert.match(source, /contentVariant="flush"/);
    assert.doesNotMatch(source, /contentClassName="p-0"/);
  }
});

test("merged market workspaces use product-frame presentation contracts", () => {
  const marketWorkspaceSource = readFileSync(new URL("../app/market/MarketWorkspace.tsx", import.meta.url), "utf8");
  const heatmapWorkspaceSource = readFileSync(new URL("../app/heatmap/HeatmapWorkspace.tsx", import.meta.url), "utf8");
  const sectorWorkspaceSource = readFileSync(new URL("../app/sectors/SectorPageWorkspace.tsx", import.meta.url), "utf8");
  const sectorReplicaWorkspaceSource = readFileSync(
    new URL("../app/sectors/SectorReplicaWorkspace.tsx", import.meta.url),
    "utf8",
  );
  const sectorReplicaPanelSource = readFileSync(new URL("../app/sectors/SectorReplicaPanel.tsx", import.meta.url), "utf8");
  const systemPageSource = readFileSync(new URL("../app/system/page.tsx", import.meta.url), "utf8");
  const systemWorkspaceSource = readFileSync(new URL("../app/system/SystemWorkspace.tsx", import.meta.url), "utf8");
  const systemStatusPanelSource = readFileSync(new URL("../components/system/SystemStatusPanel.tsx", import.meta.url), "utf8");
  const modelMaintenanceWorkspaceSource = readFileSync(
    new URL("../app/model-maintenance/ModelMaintenanceWorkspace.tsx", import.meta.url),
    "utf8",
  );
  const settingsWorkspaceSource = readFileSync(new URL("../app/settings/SettingsWorkspace.tsx", import.meta.url), "utf8");
  const globalsSource = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  const retiredWorkbenchPageUrl = new URL("../components/workbench/WorkbenchPage.tsx", import.meta.url);
  const retiredWorkbenchLayoutUrl = new URL("../components/workbench/workbenchLayout.ts", import.meta.url);
  const framedWorkspaceSources = [
    marketWorkspaceSource,
    systemWorkspaceSource,
    modelMaintenanceWorkspaceSource,
    settingsWorkspaceSource,
  ];
  const embeddedWorkspaceSources = [
    heatmapWorkspaceSource,
    sectorWorkspaceSource,
    sectorReplicaWorkspaceSource,
    sectorReplicaPanelSource,
  ];
  const presentationSources = [systemPageSource, systemStatusPanelSource];
  const allWorkspaceSources = [...framedWorkspaceSources, ...embeddedWorkspaceSources, ...presentationSources];

  for (const source of framedWorkspaceSources) {
    assert.match(source, /<PageFrame\b/);
  }
  assert.match(heatmapWorkspaceSource, /app-panel/);
  assert.match(sectorWorkspaceSource, /market-radar-page/);
  assert.match(sectorReplicaWorkspaceSource, /className="market-radar-workspace"/);
  assert.match(sectorReplicaPanelSource, /market-radar-/);
  for (const source of presentationSources) {
    assert.match(source, /app-panel/);
  }

  for (const source of allWorkspaceSources) {
    assert.doesNotMatch(source, /WorkbenchPage|workbenchLayout|workbench-(?:panel|page|muted|ink|panel-divider)/);
    assert.doesNotMatch(source, /(?:bg|border|text)-\[#(?:f5f3f0|eee9df|ddd8d0|11100e|7b756d|1d1b18|34302a|171512|c8bda9)\]/);
  }

  assert.doesNotMatch(sectorReplicaPanelSource, /sector-replica-/);
  assert.doesNotMatch(sectorReplicaWorkspaceSource, /className="sector-replica-workspace"/);
  assert.doesNotMatch(globalsSource, /--workbench-/);
  assert.doesNotMatch(globalsSource, /\.sector-replica-/);
  assert.equal(existsSync(retiredWorkbenchPageUrl), false);
  assert.equal(existsSync(retiredWorkbenchLayoutUrl), false);
});

test("model maintenance uses supported Ant Design Space orientation props", () => {
  const modelMaintenanceSource = readFileSync(
    new URL("../app/model-maintenance/ModelMaintenanceWorkspace.tsx", import.meta.url),
    "utf8",
  );
  const packetPageSource = readFileSync(new URL("../app/model-maintenance/packets/[packetId]/page.tsx", import.meta.url), "utf8");

  for (const source of [modelMaintenanceSource, packetPageSource]) {
    assert.doesNotMatch(source, /direction="vertical"/);
  }
});

test("operational workspaces preserve screener detail context and supported Alert props", () => {
  const candidateResultsSource = readFileSync(new URL("../components/screener/CandidateResults.tsx", import.meta.url), "utf8");
  const gsgfFunnelSource = readFileSync(new URL("../components/screener/GsgfFunnelPanel.tsx", import.meta.url), "utf8");
  const systemStatusPanelSource = readFileSync(new URL("../components/system/SystemStatusPanel.tsx", import.meta.url), "utf8");
  const auctionWorkspaceSource = readFileSync(new URL("../app/auction/AuctionWorkspace.tsx", import.meta.url), "utf8");

  assert.match(candidateResultsSource, /buildStockDetailHref\(item\.symbol, \{ from: "screener" \}\)/);
  assert.match(gsgfFunnelSource, /buildStockDetailHref\(item\.symbol, \{ from: "screener" \}\)/);
  assert.doesNotMatch(systemStatusPanelSource, /<Alert[^>]*\bmessage=/);
  assert.doesNotMatch(auctionWorkspaceSource, /<Alert[^>]*\bmessage=/);
});

test("operational workspaces no longer use the retired workbench palette", () => {
  const sources = [
    "../app/auction/AuctionWorkspace.tsx",
    "../components/ScreenerWorkbench.tsx",
    "../components/screener/FilterLogicRail.tsx",
    "../components/screener/CandidateResults.tsx",
    "../components/screener/MarketOverviewPanels.tsx",
    "../components/screener/GsgfWorkflowPanels.tsx",
    "../components/screener/GsgfFunnelPanel.tsx",
    "../app/sentiment/SentimentWorkspace.tsx",
    "../app/sentiment/IntradaySentimentPanel.tsx",
    "../app/sentiment/StockPoolTables.tsx",
    "../app/watchlist/WatchlistManagerPanel.tsx",
    "../app/model-maintenance/packets/[packetId]/page.tsx",
    "../lib/sectorReplicaChartOption.ts",
  ].map((path) => readFileSync(new URL(path, import.meta.url), "utf8"));
  const retiredPalette = /#(?:11100e|1d1b18|34312d|3b3833|433f38|5f5a53|625b52|7b756d|8a4b12|9a948c|c9bca8|d6d0c7|d9d4cb|ddd8d0|e3ddd3|e5e0d8|e6e0d7|ece7df|eee7db|eee8dc|eee9df|efe8dd|f1efea|f5f3f0|f6f2ea|f7f3ed|f8f7f4|faf7f1|fff3f0|fffdf9|f04438|d92d20|d93025|b45309|92400e|b91c1c)/i;

  for (const source of sources) {
    assert.doesNotMatch(source, retiredPalette);
  }
});

test("screener ticker gives mobile controls a full-width wrapping row", () => {
  const source = readFileSync(new URL("../components/screener/MarketOverviewPanels.tsx", import.meta.url), "utf8");

  assert.match(source, /flex w-full min-w-0 flex-wrap items-center justify-start gap-2 xl:w-auto xl:justify-end/);
  assert.match(source, /className="w-full min-w-0 xl:w-\[300px\]"/);
});

test("operational palette migration keeps hover feedback distinct from idle state", () => {
  const screenerSource = readFileSync(new URL("../components/ScreenerWorkbench.tsx", import.meta.url), "utf8");
  const auctionSource = readFileSync(new URL("../app/auction/AuctionWorkspace.tsx", import.meta.url), "utf8");
  const sentimentSource = readFileSync(new URL("../app/sentiment/SentimentWorkspace.tsx", import.meta.url), "utf8");

  assert.doesNotMatch(screenerSource, /bg-\[var\(--app-ink\)\][^"]*hover:bg-\[var\(--app-ink\)\]/);
  for (const source of [auctionSource, sentimentSource]) {
    assert.doesNotMatch(source, /border-\[var\(--app-border\)\][^"]*hover:border-\[var\(--app-border\)\]/);
  }
});
