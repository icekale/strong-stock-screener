import type {
  AuctionModelBucket,
  AuctionModelCacheStatus,
  AuctionModelPredictionItem,
  AuctionModelTop3Response,
  AuctionTop3LiveConfirmation,
} from "@/service/types";

export const AUCTION_MODEL_PREVIEW_LIMIT = 3;

const BUCKET_ORDER: Record<AuctionModelBucket, number> = {
  selected: 0,
  attack: 1,
  watch: 2,
  avoid: 3,
};

export function selectAuctionModelPreviewItems(
  items: AuctionModelPredictionItem[],
  limit = AUCTION_MODEL_PREVIEW_LIMIT,
): AuctionModelPredictionItem[] {
  return [...items]
    .sort((left, right) => {
      const bucketDiff = BUCKET_ORDER[left.bucket] - BUCKET_ORDER[right.bucket];
      if (bucketDiff !== 0) {
        return bucketDiff;
      }
      const leftRank = left.rank ?? 9999;
      const rightRank = right.rank ?? 9999;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return right.prob_3pct - left.prob_3pct;
    })
    .slice(0, limit);
}

export function auctionModelBucketLabel(bucket: AuctionModelBucket): string {
  if (bucket === "selected") {
    return "Top3试运行";
  }
  if (bucket === "attack") {
    return "攻击观察";
  }
  if (bucket === "watch") {
    return "候选观察";
  }
  return "回避";
}

export function auctionModelCacheStatusLabel(status: AuctionModelCacheStatus): string {
  return status === "cached" ? "缓存结果" : "刚生成";
}

export function auctionModelLiveConfirmationLabel(status: AuctionTop3LiveConfirmation): string {
  if (status === "buyable") {
    return "可买";
  }
  if (status === "watch") {
    return "观察";
  }
  return "放弃";
}

export function auctionModelLiveConfirmationColor(status: AuctionTop3LiveConfirmation): string {
  if (status === "buyable") {
    return "red";
  }
  if (status === "watch") {
    return "orange";
  }
  return "default";
}

export function auctionModelRunStatusText(
  run: Pick<AuctionModelTop3Response, "feature_end_date" | "items"> | null | undefined,
): string {
  if (!run) {
    return "未运行 · 运行后显示Top3候选";
  }
  const previewCount = selectAuctionModelPreviewItems(run.items).length;
  if (previewCount === 0) {
    return `已生成 · 暂无可展示候选 · 特征日 ${run.feature_end_date}`;
  }
  return `已生成 · 预览${previewCount}只 · 特征日 ${run.feature_end_date}`;
}
