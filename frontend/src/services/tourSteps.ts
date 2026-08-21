/**
 * The guided tour: what to highlight, in what order, and where each step lives.
 *
 * Two kinds of transition:
 *  - Within a page — the parent uses Next / Back in the tooltip.
 *  - Between pages — the last step on a page has `advanceOn` set to the next
 *    route. The tooltip drops its Next button and instead highlights the real
 *    nav item, which stays clickable. The tour only moves on once the router
 *    actually lands on that route, so the parent learns the navigation by
 *    doing it rather than watching it happen.
 *
 * Targets are `data-tour` attributes rather than class names or DOM structure,
 * so restyling a page can't silently break the tour.
 */
export interface TourStep {
  /** `data-tour` value of the element to highlight. */
  target: string;
  title: string;
  content: string;
  /** Route this step belongs to. The tour pauses if the user wanders off it. */
  page: string;
  /**
   * Marks a hand-off step. The step targets the NAV ITEM for this route, not a
   * section of the page — the overlay blocks clicks everywhere except the
   * spotlight, so the thing the parent must click has to be the thing lit up.
   * Its presence also switches the tooltip from "Next" to "tap the tab".
   */
  advanceOn?: string;
  placement?: "top" | "bottom" | "left" | "right" | "center";
}

/** Nav labels, for the "tap X to continue" copy. Mirrors Sidebar's navItems. */
export const ROUTE_LABELS: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/feeding": "Feeding",
  "/controls": "Controls",
  "/orders": "Shopping",
  "/activity": "Activity",
  "/settings": "Settings",
};

/**
 * Copy is written for an EMPTY account. The tour runs immediately after baby
 * setup, so there is no device, no feeds and no orders yet — every section is
 * in its empty state. Describing what will appear is accurate; describing live
 * data would not be.
 *
 * EIGHT content steps, one or two per page, plus the five hand-offs between
 * them. It used to be seventeen, which was more than anyone sits through on
 * first run. The sections that lost their own step are named in the copy of the
 * step that replaced them, so nothing is left unmentioned — and the pages still
 * keep their `data-tour` anchors, so a step can be restored without re-marking
 * the markup.
 */
export const TOUR_STEPS: TourStep[] = [
  // ── Dashboard (2) ─────────────────────────────────────────────────────────
  {
    target: "dashboard-greeting",
    title: "Welcome to UNOBOT",
    content:
      "This is your home screen — your daily summary sits just below: last feed, when the next one is due, and anything needing attention. We'll take a minute to show you around, and you can skip at any point.",
    page: "/dashboard",
    placement: "bottom",
  },
  {
    // This target is the grid wrapping BOTH the device and alerts cards, so the
    // copy can name them together without the spotlight pointing at only one.
    target: "dashboard-device",
    title: "Your device and alerts",
    content:
      "Pair your UNOBOT on the left — once connected it reports washes, sterilising and feeds on its own. Overdue feeds and device problems appear on the right, and in the bell at the top of every page.",
    page: "/dashboard",
    placement: "top",
  },

  {
    target: "nav:/feeding",
    title: "Next: Feeding",
    content: "Tap Feeding in the menu to carry on.",
    page: "__any__",
    advanceOn: "/feeding",
    placement: "right",
  },

  // ── Feeding (2) ───────────────────────────────────────────────────────────
  {
    target: "feeding-log-button",
    title: "Log a feed",
    content:
      "Record a feed by hand here — amount, milk type and time. Feeds measured by the device appear on their own.",
    page: "/feeding",
    placement: "bottom",
  },
  {
    target: "feeding-schedule",
    title: "Feeding schedule",
    content:
      "How long since the last feed and when the next is due, on a three-hour interval. Further down the page you'll find daily intake charts and the full history of every feed.",
    page: "/feeding",
    placement: "bottom",
  },

  {
    target: "nav:/controls",
    title: "Next: Controls",
    content: "Tap Controls in the menu to carry on.",
    page: "__any__",
    advanceOn: "/controls",
    placement: "right",
  },

  // ── Controls (1) ──────────────────────────────────────────────────────────
  {
    target: "controls-actions",
    title: "Run the device",
    content:
      "Everything the UNOBOT does, you start from here: pick a wash mode and run a cycle, sterilise with UV on its own, or set a temperature and volume and have a bottle prepared. We'll always confirm before the UV lamp switches on.",
    page: "/controls",
    placement: "top",
  },

  {
    target: "nav:/orders",
    title: "Next: Shopping",
    content: "Tap Shopping in the menu to carry on.",
    page: "__any__",
    advanceOn: "/orders",
    placement: "right",
  },

  // ── Shopping (1) ──────────────────────────────────────────────────────────
  {
    target: "orders-tabs",
    title: "Shop and orders",
    content:
      "Buy cleaning supplies and accessories, and track anything you've ordered under My Orders. Prices are in rupees; the selector shows an approximate conversion, but orders are still charged in INR.",
    page: "/orders",
    placement: "bottom",
  },

  {
    target: "nav:/activity",
    title: "Next: Activity",
    content: "Tap Activity in the menu to carry on.",
    page: "__any__",
    advanceOn: "/activity",
    placement: "right",
  },

  // ── Activity (1) ──────────────────────────────────────────────────────────
  {
    target: "activity-feed",
    title: "Activity log",
    content:
      "A running record of everything the device has done — useful when you want to check what happened and when.",
    page: "/activity",
    placement: "bottom",
  },

  {
    target: "nav:/settings",
    title: "Next: Settings",
    content: "Tap Settings in the menu to carry on.",
    page: "__any__",
    advanceOn: "/settings",
    placement: "right",
  },

  // ── Settings (1) ──────────────────────────────────────────────────────────
  {
    target: "settings-babies",
    title: "That's the tour",
    content:
      "Update your baby's details here, or add a second — the app tracks twins separately, with their own schedules and alerts. The app's colour is just above, and you can pair your device below. Replay this tour any time from the button at the top of this page.",
    page: "/settings",
    placement: "top",
  },
];

/**
 * Position among the CONTENT steps, 1-based; null for hand-off steps.
 *
 * The tooltip counts "Step 3 of 8" rather than 3 of 13: tapping a tab is a
 * transition, not something the parent is being taught, and numbering it made
 * the tour look half again as long as it is.
 */
export const CONTENT_STEP_NUMBERS: (number | null)[] = (() => {
  let n = 0;
  return TOUR_STEPS.map((s) => (s.advanceOn ? null : (n += 1)));
})();

export const CONTENT_STEP_TOTAL = TOUR_STEPS.filter((s) => !s.advanceOn).length;

/** Pages the tour visits, in order — used to keep it on the intended route. */
export const ANY_PAGE = "__any__";

/**
 * The CSS selector Joyride should spotlight.
 *
 * Nav targets resolve differently by viewport: the full sidebar is off-canvas
 * below `lg`, where the visible navigation is the MiniSidebar rail. Both are in
 * the DOM at once, so picking the wrong one would spotlight something the
 * parent cannot see or tap.
 */
export function selectorFor(step: TourStep, isDesktop: boolean): string {
  if (step.target.startsWith("nav:")) {
    const route = step.target.slice(4).replace(/^\//, "");
    return isDesktop ? `[data-tour="nav-${route}"]` : `[data-tour="mininav-${route}"]`;
  }
  return `[data-tour="${step.target}"]`;
}
