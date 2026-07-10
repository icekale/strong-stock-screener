export type ClassNameValue = string | false | null | undefined;

export type DataStateCopyKind = "empty" | "stale";

export type DataStateCopy = {
  action?: string;
  description?: string;
  title: string;
};

export function joinClassNames(...values: ClassNameValue[]): string {
  return values.filter(Boolean).join(" ");
}

export function dataStateCopy(kind: DataStateCopyKind, subject: string): DataStateCopy {
  if (kind === "empty") {
    return {
      title: `暂无${subject}`,
      description: "当前条件下没有符合规则的标的。",
    };
  }

  return {
    title: `${subject}数据可能已过期`,
    action: "重新读取",
  };
}
