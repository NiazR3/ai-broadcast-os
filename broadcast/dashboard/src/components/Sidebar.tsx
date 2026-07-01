import { type JSX, useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ */
/*  Nav item definitions                                               */
/* ------------------------------------------------------------------ */

interface NavItem {
  id: string;
  label: string;
  icon: JSX.Element;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "broadcast",
    label: "Broadcast",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="8" r="2" />
        <path d="M8 12a5 5 0 0 1 8 0" />
        <path d="M5 16a9 9 0 0 1 14 0" />
        <line x1="12" y1="18" x2="12" y2="22" />
      </svg>
    ),
  },
  {
    id: "show",
    label: "Show",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    ),
  },
  {
    id: "teleprompter",
    label: "Teleprompter",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="2" y="3" width="20" height="18" rx="2" />
        <line x1="6" y1="8" x2="18" y2="8" />
        <line x1="6" y1="12" x2="14" y2="12" />
        <line x1="6" y1="16" x2="16" y2="16" />
      </svg>
    ),
  },
  {
    id: "agents",
    label: "Agents",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="3" />
        <circle cx="4" cy="6" r="2" />
        <circle cx="20" cy="6" r="2" />
        <circle cx="4" cy="18" r="2" />
        <circle cx="20" cy="18" r="2" />
        <line x1="6" y1="7" x2="10" y2="10" />
        <line x1="14" y1="10" x2="18" y2="7" />
        <line x1="6" y1="17" x2="10" y2="14" />
        <line x1="14" y1="14" x2="18" y2="17" />
      </svg>
    ),
  },
  {
    id: "audience",
    label: "Audience",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20v-2a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v2" />
        <circle cx="17" cy="8" r="2.5" />
        <path d="M21 20v-1.5a4.5 4.5 0 0 0-3.5-4.3" />
      </svg>
    ),
  },
  {
    id: "research",
    label: "Research",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <line x1="16.5" y1="16.5" x2="21" y2="21" />
      </svg>
    ),
  },
  {
    id: "media",
    label: "Media",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <polygon points="5 3 19 12 5 21 5 3" />
      </svg>
    ),
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <line x1="4" y1="20" x2="4" y2="10" />
        <line x1="10" y1="20" x2="10" y2="4" />
        <line x1="16" y1="20" x2="16" y2="12" />
        <line x1="22" y1="20" x2="22" y2="8" />
      </svg>
    ),
  },
];

/* ------------------------------------------------------------------ */
/*  Sidebar                                                            */
/* ------------------------------------------------------------------ */

interface SidebarProps {
  /** Whether the broadcast is currently live — shows a pulsing indicator on the Broadcast nav item */
  isLive?: boolean;
}

export function Sidebar({ isLive = false }: SidebarProps) {
  const [activeSection, setActiveSection] = useState("broadcast");
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const ids = NAV_ITEMS.map((n) => `section-${n.id}`);
    const sections = ids
      .map((id) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];

    if (sections.length === 0) return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        let best: Element | null = null;
        let bestRatio = 0;

        for (const entry of entries) {
          if (entry.intersectionRatio > bestRatio) {
            best = entry.target;
            bestRatio = entry.intersectionRatio;
          }
        }

        if (best) {
          setActiveSection(best.id.replace("section-", ""));
        }
      },
      {
        rootMargin: "-64px 0px -50% 0px",
        threshold: [0, 0.1, 0.25, 0.5, 0.75, 1],
      },
    );

    for (const s of sections) {
      observerRef.current.observe(s);
    }

    return () => {
      observerRef.current?.disconnect();
    };
  }, []);

  const scrollTo = (id: string) => {
    document
      .getElementById(`section-${id}`)
      ?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <nav
      className="fixed left-0 top-0 z-50 flex h-full w-14 flex-col items-center gap-1 border-r border-border bg-bg-elevated py-3"
      aria-label="Main navigation"
    >
      {NAV_ITEMS.map((item) => {
        const isActive = activeSection === item.id;
        const isBroadcastItem = item.id === "broadcast";
        return (
          <button
            key={item.id}
            onClick={() => scrollTo(item.id)}
            title={item.label}
            aria-label={item.label}
            aria-current={isActive ? "true" : undefined}
            className={`
              relative flex h-10 w-10 items-center justify-center rounded-lg
              transition-all duration-150
              ${
                isActive
                  ? "bg-brand/10 text-brand"
                  : "text-text-secondary hover:bg-bg-hover hover:text-text"
              }
            `}
          >
            {item.icon}
            {/* Live indicator dot on Broadcast icon */}
            {isBroadcastItem && isLive && (
              <span
                className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5"
                aria-label="Broadcast is live"
              >
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-live opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-live" />
              </span>
            )}
            {isBroadcastItem && !isLive && (
              <span
                className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-text-muted"
                aria-label="Broadcast is offline"
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}
