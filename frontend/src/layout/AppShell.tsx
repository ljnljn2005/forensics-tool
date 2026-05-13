import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type NavItem = {
  key: string;
  label: string;
  description?: string;
  icon?: string;
  children?: NavItem[];
};

export type NavGroup = {
  title: string;
  icon?: string;
  items: NavItem[];
};

type AppShellProps = {
  title: string;
  subtitle: string;
  navGroups: NavGroup[];
  activeKey: string;
  onChange: (key: string) => void;
  children: ReactNode;
};

const MIN_SIDEBAR_WIDTH = 72;
const MAX_SIDEBAR_WIDTH = 320;
const DEFAULT_SIDEBAR_WIDTH = 248;
const ICON_ONLY_WIDTH = 76;
const COLLAPSE_THRESHOLD = 108;

function flattenItems(items: NavItem[]): NavItem[] {
  const result: NavItem[] = [];
  for (const item of items) {
    result.push(item);
    if (item.children?.length) {
      result.push(...flattenItems(item.children));
    }
  }
  return result;
}

function itemContainsActive(item: NavItem, activeKey: string): boolean {
  if (item.key === activeKey) {
    return true;
  }
  return item.children?.some((child) => itemContainsActive(child, activeKey)) ?? false;
}

export default function AppShell({
  title,
  subtitle,
  navGroups,
  activeKey,
  onChange,
  children
}: AppShellProps) {
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const [iconOnly, setIconOnly] = useState(false);
  const [zoom, setZoom] = useState(() => {
    const saved = window.localStorage.getItem("forensics-ui-zoom");
    const parsed = saved ? Number(saved) : 1;
    return Number.isFinite(parsed) && parsed >= 0.75 && parsed <= 1.5 ? parsed : 1;
  });
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(navGroups.map((group) => [group.title, false]))
  );
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const dragStateRef = useRef<{ startX: number; startWidth: number } | null>(null);

  useEffect(() => {
    setExpandedGroups((current) => {
      const next = { ...current };
      for (const group of navGroups) {
        if (!(group.title in next)) {
          next[group.title] = false;
        }
      }
      return next;
    });
  }, [navGroups]);

  useEffect(() => {
    setExpandedItems((current) => {
      const next = { ...current };
      const visit = (items: NavItem[]) => {
        for (const item of items) {
          if (item.children?.length && !(item.key in next)) {
            next[item.key] = false;
          }
          if (item.children?.length) {
            visit(item.children);
          }
        }
      };
      for (const group of navGroups) {
        visit(group.items);
      }
      return next;
    });
  }, [navGroups]);

  useEffect(() => {
    setExpandedGroups((current) => {
      const next = { ...current };
      for (const group of navGroups) {
        if (group.items.some((item) => itemContainsActive(item, activeKey))) {
          next[group.title] = true;
        }
      }
      return next;
    });
    setExpandedItems((current) => {
      const next = { ...current };
      const visit = (items: NavItem[]) => {
        for (const item of items) {
          if (item.children?.length && item.children.some((child) => itemContainsActive(child, activeKey))) {
            next[item.key] = true;
          }
          if (item.children?.length) {
            visit(item.children);
          }
        }
      };
      for (const group of navGroups) {
        visit(group.items);
      }
      return next;
    });
  }, [activeKey, navGroups]);

  useEffect(() => {
    document.documentElement.style.setProperty("--ui-zoom", String(zoom));
    window.localStorage.setItem("forensics-ui-zoom", String(zoom));
  }, [zoom]);

  useEffect(() => {
    function clampZoom(value: number) {
      return Math.min(1.5, Math.max(0.75, Number(value.toFixed(2))));
    }

    function handleWheel(event: WheelEvent) {
      if (!event.ctrlKey) {
        return;
      }
      event.preventDefault();
      setZoom((current) => clampZoom(current + (event.deltaY < 0 ? 0.05 : -0.05)));
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (!event.ctrlKey) {
        return;
      }
      if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        setZoom((current) => clampZoom(current + 0.05));
      } else if (event.key === "-") {
        event.preventDefault();
        setZoom((current) => clampZoom(current - 0.05));
      } else if (event.key === "0") {
        event.preventDefault();
        setZoom(1);
      }
    }

    window.addEventListener("wheel", handleWheel, { passive: false });
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("wheel", handleWheel);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      if (!dragStateRef.current) {
        return;
      }
      const delta = event.clientX - dragStateRef.current.startX;
      const nextWidth = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, dragStateRef.current.startWidth + delta));
      setSidebarWidth(nextWidth);
      setIconOnly(nextWidth <= COLLAPSE_THRESHOLD);
    }

    function handlePointerUp() {
      dragStateRef.current = null;
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, []);

  const effectiveWidth = iconOnly ? ICON_ONLY_WIDTH : sidebarWidth;
  const allItems = useMemo(() => navGroups.flatMap((group) => flattenItems(group.items)), [navGroups]);
  const activeItem = allItems.find((item) => item.key === activeKey);

  function toggleGroup(groupTitle: string) {
    setExpandedGroups((current) => ({
      ...current,
      [groupTitle]: !current[groupTitle]
    }));
  }

  function toggleItem(itemKey: string) {
    setExpandedItems((current) => ({
      ...current,
      [itemKey]: !current[itemKey]
    }));
  }

  function handleResizeStart(event: React.PointerEvent<HTMLDivElement>) {
    dragStateRef.current = {
      startX: event.clientX,
      startWidth: sidebarWidth
    };
  }

  function handleToggleSidebar() {
    if (iconOnly) {
      setIconOnly(false);
      setSidebarWidth(DEFAULT_SIDEBAR_WIDTH);
      return;
    }
    setIconOnly(true);
  }

  function changeZoom(delta: number) {
    setZoom((current) => Math.min(1.5, Math.max(0.75, Number((current + delta).toFixed(2)))));
  }

  function renderItems(items: NavItem[], level: number): ReactNode {
    return (
      <div className={level === 0 ? "nav-list" : "nav-sublist"}>
        {items.map((item) => {
          const hasChildren = Boolean(item.children?.length);
          const isExpanded = expandedItems[item.key] ?? false;
          const isActive = item.key === activeKey;
          const isBranchActive = itemContainsActive(item, activeKey);
          return (
            <div key={item.key} className="nav-tree-node">
              <button
                className={isActive ? `nav-item active nav-level-${level}` : `nav-item nav-level-${level}`}
                onClick={() => {
                  if (hasChildren && !iconOnly) {
                    toggleItem(item.key);
                  } else {
                    onChange(item.key);
                  }
                }}
                title={item.label}
              >
                <span className="nav-item-icon">{item.icon ?? item.label.slice(0, 1).toUpperCase()}</span>
                {!iconOnly ? (
                  <span className="nav-item-copy">
                    <span className="nav-item-row">
                      <span className="nav-item-label">{item.label}</span>
                      {hasChildren ? <span className="nav-item-caret">{isExpanded || isBranchActive ? "-" : "+"}</span> : null}
                    </span>
                    {item.description ? <span className="nav-item-description">{item.description}</span> : null}
                  </span>
                ) : null}
              </button>
              {hasChildren && !iconOnly && (isExpanded || isBranchActive) ? renderItems(item.children ?? [], level + 1) : null}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="app-shell" style={{ gridTemplateColumns: `${effectiveWidth}px 1fr` }}>
      <aside className={iconOnly ? "sidebar collapsed" : "sidebar"} style={{ width: effectiveWidth }}>
        <div className="brand">
          <div className="brand-mark">FT</div>
          {!iconOnly ? (
            <div>
              <div className="brand-title">综合取证分析工具</div>
              <div className="brand-subtitle">Flat WebUI Workbench</div>
            </div>
          ) : null}
        </div>

        <div className="sidebar-actions">
          <button className="sidebar-toggle" onClick={handleToggleSidebar} title={iconOnly ? "展开导航" : "折叠为图标栏"}>
            {iconOnly ? ">>" : "<<"}
          </button>
        </div>

        <div className="nav-groups">
          {navGroups.map((group) => {
            const isExpanded = expandedGroups[group.title] ?? false;
            return (
              <section key={group.title} className="nav-group">
                <button
                  className={iconOnly ? "nav-group-header icon-only" : "nav-group-header"}
                  onClick={() => {
                    if (!iconOnly) {
                      toggleGroup(group.title);
                    }
                  }}
                  title={group.title}
                >
                  <span className="nav-group-icon">{group.icon ?? group.title.slice(0, 1).toUpperCase()}</span>
                  {!iconOnly ? (
                    <>
                      <span className="nav-group-title">{group.title}</span>
                      <span className="nav-group-caret">{isExpanded ? "-" : "+"}</span>
                    </>
                  ) : null}
                </button>

                {(iconOnly || isExpanded) && renderItems(group.items, 0)}
              </section>
            );
          })}
        </div>

        <div className="sidebar-resizer" onPointerDown={handleResizeStart} />
      </aside>

      <main className="main-panel">
        <header className="page-header">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          {activeItem ? (
            <div className="page-badge">
              <span className="page-badge-icon">{activeItem.icon ?? activeItem.label.slice(0, 1).toUpperCase()}</span>
              <span>{activeItem.label}</span>
            </div>
          ) : null}
          <div className="page-zoom-controls">
            <button className="sidebar-toggle" onClick={() => changeZoom(-0.05)} title="缩小">
              A-
            </button>
            <button className="sidebar-toggle" onClick={() => setZoom(1)} title="重置缩放">
              {Math.round(zoom * 100)}%
            </button>
            <button className="sidebar-toggle" onClick={() => changeZoom(0.05)} title="放大">
              A+
            </button>
          </div>
        </header>
        <section className="page-body">{children}</section>
      </main>
    </div>
  );
}
