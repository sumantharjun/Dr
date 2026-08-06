import { useEffect } from "react";
import { createPortal } from "react-dom";
import { clsx } from "clsx";

type Tone = "primary" | "danger" | "warning";

const TONES: Record<Tone, { iconWrap: string; confirm: string }> = {
  primary: { iconWrap: "bg-primary-50 text-primary-600", confirm: "bg-primary-600 hover:bg-primary-700" },
  danger:  { iconWrap: "bg-red-50 text-red-600",         confirm: "bg-red-600 hover:bg-red-700"         },
  warning: { iconWrap: "bg-purple-50 text-purple-600",   confirm: "bg-purple-600 hover:bg-purple-700"   },
};

/**
 * Confirmation prompt for actions that can't be taken back — notably anything
 * that actuates the physical device.
 *
 * Portaled to <body> so a parent's `overflow`/stacking context can't clip it,
 * matching the pattern in components/layout/ProfileMenu.tsx.
 */
export default function ConfirmDialog({
  open, icon: Icon, tone = "primary", title, message, confirmLabel, onConfirm, onCancel,
}: {
  open: boolean;
  icon: React.ElementType;
  tone?: Tone;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  // Escape closes, matching what users expect of a modal.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;
  const t = TONES[tone];

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4"
      onMouseDown={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 text-center"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className={clsx("w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3", t.iconWrap)}>
          <Icon className="w-6 h-6" />
        </div>
        <h2 id="confirm-title" className="font-semibold text-gray-900 text-lg">{title}</h2>
        <p className="text-sm text-gray-500 mt-1 mb-5">{message}</p>
        <div className="flex gap-3">
          <button
            // For destructive prompts the safe button takes focus, so a stray
            // Enter dismisses rather than confirms. Focus stays inside the
            // dialog either way, so keyboard users aren't stranded.
            autoFocus={tone === "danger"}
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            autoFocus={tone !== "danger"}
            onClick={onConfirm}
            className={clsx("flex-1 px-4 py-2.5 text-sm font-semibold text-white rounded-lg transition-colors", t.confirm)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
