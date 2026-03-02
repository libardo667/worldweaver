import { ReactNode, useEffect, useState } from "react";

type MobileSideTab = "memory" | "place";

type AppShellProps = {
  memoryPanel: ReactNode;
  nowPanel: ReactNode;
  placePanel: ReactNode;
};

function useDesktopLayout(minWidth = 1100): boolean {
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= minWidth);

  useEffect(() => {
    const media = window.matchMedia(`(min-width: ${minWidth}px)`);
    const update = () => setIsDesktop(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [minWidth]);

  return isDesktop;
}

export function AppShell({ memoryPanel, nowPanel, placePanel }: AppShellProps) {
  const isDesktop = useDesktopLayout();
  const [mobileSideTab, setMobileSideTab] = useState<MobileSideTab>("place");
  const placeTabId = "tab-mobile-place";
  const memoryTabId = "tab-mobile-memory";
  const placePanelId = "panel-mobile-place";
  const memoryPanelId = "panel-mobile-memory";

  if (isDesktop) {
    return (
      <main className="app-main layout-grid" aria-label="Explore mode layout">
        <div className="layout-column memory-column">{memoryPanel}</div>
        <div className="layout-column center-column-shell">{nowPanel}</div>
        <div className="layout-column place-column">{placePanel}</div>
      </main>
    );
  }

  return (
    <main className="app-main mobile-layout" aria-label="Explore mode layout">
      <div className="mobile-now">{nowPanel}</div>
      <section className="mobile-side-shell">
        <div className="mobile-side-tabs" role="tablist" aria-label="Side panels">
          <button
            type="button"
            id={placeTabId}
            role="tab"
            aria-controls={placePanelId}
            aria-selected={mobileSideTab === "place"}
            className={`mobile-side-tab ${mobileSideTab === "place" ? "active" : ""}`}
            onClick={() => setMobileSideTab("place")}
          >
            Place
          </button>
          <button
            type="button"
            id={memoryTabId}
            role="tab"
            aria-controls={memoryPanelId}
            aria-selected={mobileSideTab === "memory"}
            className={`mobile-side-tab ${mobileSideTab === "memory" ? "active" : ""}`}
            onClick={() => setMobileSideTab("memory")}
          >
            Memory
          </button>
        </div>
        <div
          id={placePanelId}
          role="tabpanel"
          aria-labelledby={placeTabId}
          hidden={mobileSideTab !== "place"}
          className="mobile-side-panel"
        >
          {placePanel}
        </div>
        <div
          id={memoryPanelId}
          role="tabpanel"
          aria-labelledby={memoryTabId}
          hidden={mobileSideTab !== "memory"}
          className="mobile-side-panel"
        >
          {memoryPanel}
        </div>
      </section>
    </main>
  );
}
