import { Suspense } from "react";
import { MarketWorkspace } from "./MarketWorkspace";

export default function MarketPage() {
  return (
    <Suspense>
      <MarketWorkspace />
    </Suspense>
  );
}
