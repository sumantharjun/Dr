import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Joyride, { ACTIONS, CallBackProps, EVENTS, STATUS, Step } from "react-joyride";
import api from "../services/api";
import { useAuthStore } from "../store/authStore";
import {
  ANY_PAGE,
  CONTENT_STEP_NUMBERS,
  CONTENT_STEP_TOTAL,
  TOUR_STEPS,
  selectorFor,
} from "../services/tourSteps";

/**
 * How long a step's target may be absent before the step is skipped: ~2s at
 * 60fps, generous enough for a section that renders only once its request
 * resolves. Counted in frames, not milliseconds, so rAF's pause in a background
 * tab means a tour left in another window doesn't advance on its own.
 */
const MISSING_FRAMES_BEFORE_SKIP = 120;

/**
 * The first-run guided tour.
 *
 * Joyride handles the spotlight, positioning and scrolling; the routing is ours.
 * Two behaviours are worth knowing:
 *
 *  1. **Cross-page steps advance by navigation, not by a button.** A step with
 *     `advanceOn` hides its Next control and spotlights the real nav item
 *     instead. We watch the router and step forward only once the parent has
 *     actually landed on that route — so they learn where things are by going
 *     there.
 *  2. **A missing target is skipped, not fatal.** Some sections only render
 *     conditionally (the desktop cart, the "Feeding now" picker with one baby).
 *     Rather than leaving Joyride pointing at nothing, we skip past.
 */
export default function TourGuide() {
  const { user, setUser } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const [running, setRunning] = useState(false);
  // Which navigation is actually on screen decides which element a hand-off
  // step spotlights; both sidebars exist in the DOM simultaneously.
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== "undefined" && window.innerWidth >= 1024,
  );
  useEffect(() => {
    const onResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const step = TOUR_STEPS[index];

  // Start for accounts that have never finished it.
  useEffect(() => {
    if (!user) return;
    if (user.tour_completed_at) {
      setRunning(false);
      return;
    }
    // `running` guard: this effect also fires on every navigation (it has to —
    // "Replay tour" clears the flag while still on /settings, then routes to
    // the dashboard, so the flag change alone can't be the trigger). Without
    // the guard, walking back onto the dashboard mid-tour would reset it to
    // step one.
    if (running) return;
    // Only begin on the page the first step lives on; a parent who lands
    // somewhere else deep-linked shouldn't be yanked into a tour mid-task.
    if (location.pathname === TOUR_STEPS[0].page) {
      setIndex(0);
      setRunning(true);
    }
  }, [user?.id, user?.tour_completed_at, location.pathname, running]); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = useCallback(
    async (markSeen: boolean) => {
      setRunning(false);
      if (!markSeen) return;
      // Mark it seen LOCALLY before the request, not just after it.
      //
      // The start effect above re-runs the moment `running` flips, and on the
      // dashboard — the page the first step lives on — its start condition is
      // satisfied all over again. With only the server's response to go on, the
      // tour flashes back open for as long as the POST is in flight and then
      // shuts once more when it lands. Setting the flag now closes that window;
      // the POST is only persistence. Read from the store rather than the render
      // closure so this callback stays stable.
      const current = useAuthStore.getState().user;
      if (current) {
        setUser({ ...current, tour_completed_at: new Date().toISOString() });
      }
      try {
        const { data } = await api.post("/auth/me/tour?completed=true");
        setUser(data); // authoritative timestamp, replacing the local one
      } catch {
        // Deliberately stays marked seen: re-opening a tour someone just
        // dismissed is worse than it reappearing on their next sign-in.
      }
    },
    [setUser],
  );

  // Cross-page advance: the parent clicked the real nav item.
  useEffect(() => {
    if (!running || !step) return;
    if (step.advanceOn && location.pathname === step.advanceOn) {
      setIndex((i) => Math.min(i + 1, TOUR_STEPS.length - 1));
    }
  }, [location.pathname, running, step]);

  // Wandering off mid-tour pauses rather than ends it; coming back resumes.
  const onExpectedPage =
    !!step && (step.page === ANY_PAGE || location.pathname === step.page);

  // Pin the overlay's pointer behaviour from CSS rather than leaving it to
  // Joyride. Its own value comes from a `mouseOverSpotlight` flag driven by a
  // mousemove listener, and that flag sticks: if the cursor is over the
  // spotlight when the step changes — which it always is right after tapping a
  // nav item — the overlay stays click-through for every step that follows, and
  // the whole rest of the tour becomes freely clickable.
  const tourActive = running && onExpectedPage;
  const handingOff = tourActive && !!step?.advanceOn;
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("tour-active", tourActive);
    root.classList.toggle("tour-handoff", handingOff);
    return () => {
      root.classList.remove("tour-active");
      root.classList.remove("tour-handoff");
    };
  }, [tourActive, handingOff]);

  // During a hand-off the overlay has to let clicks through (touch devices get
  // no other opening), but that would also expose every other tab. Restrict it
  // to the one element the step is pointing at — anything else is swallowed, so
  // the tour can't be derailed by a stray tap on a different tab.
  useEffect(() => {
    if (!handingOff || !step) return;
    const allowed = selectorFor(step, isDesktop);
    const guard = (event: Event) => {
      const el = event.target as Element | null;
      if (el?.closest?.(allowed)) return;              // the nav item we're pointing at
      if (el?.closest?.("#react-joyride-portal")) return; // Skip / close controls
      event.preventDefault();
      event.stopPropagation();
    };
    const opts = { capture: true };
    document.addEventListener("pointerdown", guard, opts);
    document.addEventListener("click", guard, opts);
    return () => {
      document.removeEventListener("pointerdown", guard, opts);
      document.removeEventListener("click", guard, opts);
    };
  }, [handingOff, step, isDesktop]);

  // Two jobs, both decided by the target's rect, so they share one rAF loop:
  //
  //  1. **Keep the spotlight aligned.** Joyride measures the target once, when
  //     the step opens, and afterwards only re-reads it on a window resize. Our
  //     pages fetch after mount, so a card can be a two-row skeleton at
  //     measurement time and a five-item list a moment later — the spotlight
  //     keeps the shorter rect and frames half the card. Most visible arriving
  //     via Back, which remounts the page and restarts its fetches.
  //  2. **Skip a step whose target never shows up.** Some sections render
  //     conditionally, and leaving Joyride pointing at nothing strands the tour.
  //
  // The skip waits on frames rather than a fixed timer, because a timer raced
  // the very sections it was meant to protect: `feeding-schedule` only renders
  // once its request resolves, so a slow reply skipped a real step. At eight
  // steps, losing one to a slow network costs an eighth of the tour.
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    if (!running || !step || !onExpectedPage) {
      setSettled(false);
      return;
    }
    setSettled(false);
    const selector = selectorFor(step, isDesktop);
    let previous = "";
    let stableFrames = 0;
    let missingFrames = 0;
    let opened = false;
    let frame = 0;

    const tick = () => {
      const rect = document.querySelector(selector)?.getBoundingClientRect();
      const key = rect
        ? [rect.top, rect.left, rect.width, rect.height].map(Math.round).join(":")
        : "";

      if (!key) {
        missingFrames += 1;
        // Only before the step opens. If a target vanishes from under a step the
        // parent is already reading, leaving it be beats yanking them forward.
        if (!opened && missingFrames > MISSING_FRAMES_BEFORE_SKIP) {
          if (index >= TOUR_STEPS.length - 1) finish(true);
          else setIndex((i) => i + 1);
          return;
        }
      } else if (!opened) {
        missingFrames = 0;
        stableFrames = key === previous ? stableFrames + 1 : 0;
        // Three identical frames clears the first paint. It does NOT outlast a
        // fetch — a card that is stably *loading* measures the same as one that
        // is stably *finished* — which is why the watch continues below rather
        // than this being a one-shot gate.
        if (stableFrames >= 3) {
          opened = true;
          setSettled(true);
        }
      } else if (key !== previous) {
        // Joyride re-reads the target's rect on window resize (debounced, so a
        // burst coalesces) and offers no imperative way to ask for it.
        window.dispatchEvent(new Event("resize"));
      }

      previous = key;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [index, running, step, onExpectedPage, isDesktop, location.pathname, finish]);

  const steps: Step[] = useMemo(
    () =>
      TOUR_STEPS.map((s, i) => ({
        target: selectorFor(s, isDesktop),
        // Progress goes above the title rather than through Joyride's
        // `showProgress`, which appends "(3/8)" inside the Next button and read
        // as part of the label. Hand-off steps get no number — see
        // CONTENT_STEP_NUMBERS.
        title: (
          <>
            {CONTENT_STEP_NUMBERS[i] !== null && (
              <span className="block text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Step {CONTENT_STEP_NUMBERS[i]} of {CONTENT_STEP_TOTAL}
              </span>
            )}
            {s.title}
          </>
        ),
        content: s.content,
        placement: s.placement ?? "auto",
        disableBeacon: true,
        // Hand-off steps: the parent must be able to click the real nav item.
        //
        // `spotlightClicks` alone isn't enough. Joyride only opens the hole from
        // a mousemove listener — it sets the spotlight to pointer-events:none
        // and drops the overlay's pointer-events once the cursor is over it.
        // Touch devices never fire mousemove, so on a phone the tab would be
        // unclickable and the tour would dead-end. Making the overlay itself
        // click-through keeps the dimming and the spotlight while guaranteeing
        // the tap lands, pointer or finger.
        spotlightClicks: !!s.advanceOn,
        hideFooter: !!s.advanceOn,
      })),
    [isDesktop],
  );

  const handleCallback = useCallback(
    (data: CallBackProps) => {
      const { action, index: i, status, type } = data;

      if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
        finish(true);
        return;
      }
      if (action === ACTIONS.CLOSE) {
        // Closing counts as seen — re-offering a tour someone dismissed is
        // exactly the sort of thing that makes people distrust an app.
        finish(true);
        return;
      }
      if (type === EVENTS.STEP_AFTER) {
        if (action === ACTIONS.PREV) {
          // Step back OVER hand-off steps. They're forward-only: landing on one
          // while already on its destination route makes the advance effect fire
          // instantly and bounce you forward again, which reads as Back being
          // broken. Going back also has to navigate — the previous explanation
          // lives on the previous page. (Only Next requires tapping the real
          // tab; that's the teaching mechanic, and it shouldn't apply in
          // reverse.)
          let prev = i - 1;
          while (prev > 0 && TOUR_STEPS[prev].advanceOn) prev -= 1;
          prev = Math.max(prev, 0);
          setIndex(prev);
          const target = TOUR_STEPS[prev];
          if (target.page !== ANY_PAGE && location.pathname !== target.page) {
            navigate(target.page);
          }
        } else if (i >= TOUR_STEPS.length - 1) {
          // Finishing has to be handled here, not via STATUS.FINISHED. Because
          // we drive `stepIndex` ourselves, advancing past the last step makes
          // `step` undefined and unmounts Joyride before it ever emits that
          // status — so the completion was never recorded and the tour came
          // back on the next login.
          finish(true);
        } else {
          setIndex(i + 1);
        }
      }
    },
    [finish, location.pathname, navigate],
  );

  if (!running || !step) return null;

  return (
    <Joyride
      steps={steps}
      stepIndex={index}
      // Paused rather than stopped while off-route: Joyride unmounts its
      // overlay but our index survives, so returning resumes where we were.
      run={running && onExpectedPage && settled}
      continuous
      showSkipButton
      disableOverlayClose
      scrollOffset={100}
      callback={handleCallback}
      locale={{ back: "Back", close: "Close", last: "Finish", next: "Next", skip: "Skip tour" }}
      styles={{
        options: {
          zIndex: 10_000,
          // Read from the live palette so the tour follows the parent's chosen
          // theme instead of hard-coding a brand colour.
          primaryColor: getComputedStyle(document.documentElement)
            .getPropertyValue("--p-600")
            .trim()
            ? `rgb(${getComputedStyle(document.documentElement).getPropertyValue("--p-600").trim()})`
            : "#1e7e52",
          arrowColor: "#ffffff",
          backgroundColor: "#ffffff",
          textColor: "#111827",
          overlayColor: "rgba(0, 0, 0, 0.55)",
        },
        tooltip: { borderRadius: 16, padding: 20 },
        tooltipTitle: { fontSize: 16, fontWeight: 700, marginBottom: 6 },
        // padding 0 overrides Joyride's default "20px 10px", which put a blank
        // line's worth of space under the title and inset the body text further
        // than the title. The 6px below the title is the whole gap now.
        tooltipContent: { fontSize: 14, lineHeight: 1.5, whiteSpace: "pre-line", padding: 5 },
        buttonNext: { borderRadius: 8, padding: "8px 16px", fontSize: 14, fontWeight: 600 },
        buttonBack: { fontSize: 14 },
        buttonSkip: { fontSize: 13 },
      }}
    />
  );
}
