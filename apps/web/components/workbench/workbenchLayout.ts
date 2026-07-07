const WORKBENCH_PAGE_CLASS = "workbench-page min-h-screen";
const WORKBENCH_CONTENT_CLASS = "mx-auto flex w-full max-w-none flex-col gap-4 px-3 py-4 lg:px-5";

export function buildWorkbenchPageClassName(className?: string): string {
  return joinClassNames(WORKBENCH_PAGE_CLASS, className);
}

export function buildWorkbenchContentClassName(className?: string): string {
  return joinClassNames(WORKBENCH_CONTENT_CLASS, className);
}

export function joinClassNames(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}
