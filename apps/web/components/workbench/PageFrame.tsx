import { useId, type ReactNode } from "react";
import { joinClassNames } from "../../lib/workbenchPresentation";

type PageFrameProps = {
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  contentVariant?: "default" | "flush";
  context?: ReactNode;
  status?: ReactNode;
  title: ReactNode;
};

export function PageFrame({
  actions,
  children,
  className,
  contentClassName,
  contentVariant = "default",
  context,
  status,
  title,
}: PageFrameProps) {
  const titleId = useId();

  return (
    <main aria-labelledby={titleId} className={joinClassNames("page-frame", className)}>
      <header className="page-frame__header command-bar">
        <div className="min-w-0">
          {context ? <div className="page-frame__context">{context}</div> : null}
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h1 className="page-frame__title" id={titleId}>
              {title}
            </h1>
            {status}
          </div>
        </div>
        {actions ? <div className="command-bar__actions">{actions}</div> : null}
      </header>
      <div
        className={joinClassNames(
          "page-frame__content",
          contentVariant === "flush" && "page-frame__content--flush",
          contentClassName,
        )}
      >
        {children}
      </div>
    </main>
  );
}
