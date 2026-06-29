export type DraftItem = {
  symbol: string;
  name: string;
  industry: string;
  group: string;
  tagsText: string;
  note: string;
};

export function emptyDraft(): DraftItem {
  return {
    group: "自选",
    industry: "",
    name: "",
    note: "",
    symbol: "",
    tagsText: "",
  };
}
