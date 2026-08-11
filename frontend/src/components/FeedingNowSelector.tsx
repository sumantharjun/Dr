import { useEffect, useState } from "react";
import { clsx } from "clsx";
import { Baby as BabyIcon } from "lucide-react";
import api from "../services/api";
import { useBabyStore } from "../store/babyStore";
import { useToastStore } from "../store/toastStore";
import { Device } from "../types";

/**
 * "Feeding now" — tells the device which baby its next scale report belongs to.
 *
 * The scale measures a weight difference and has no way to know which twin it
 * weighed. Without this, a device-reported feed would either be guessed onto
 * the wrong baby or left unattributed. One tap before feeding solves it.
 *
 * Renders nothing with fewer than two babies (there's nothing to disambiguate)
 * or with no device (nothing reports).
 */
export default function FeedingNowSelector({
  device,
  onChange,
}: {
  device: Device | null;
  onChange?: (device: Device) => void;
}) {
  const babies = useBabyStore((s) => s.babies);
  const { addToast } = useToastStore();
  const [activeId, setActiveId] = useState<number | null>(device?.active_baby_id ?? null);
  const [saving, setSaving] = useState(false);

  // Devices load asynchronously, so `device` is null on first render and
  // useState captures that null forever. Without this sync the control looks
  // unset after every reload even though the choice was saved server-side.
  useEffect(() => {
    setActiveId(device?.active_baby_id ?? null);
  }, [device?.id, device?.active_baby_id]);

  if (!device || babies.length < 2) return null;

  async function select(babyId: number) {
    if (!device || saving) return;
    // Optimistic: the point of this control is that it's instant before a feed.
    const previous = activeId;
    const next = activeId === babyId ? null : babyId; // tapping again clears it
    setActiveId(next);
    setSaving(true);
    try {
      const { data } = await api.patch(`/devices/${device.id}/active-baby`, {
        baby_id: next,
      });
      onChange?.(data);
    } catch {
      setActiveId(previous);
      addToast("Couldn't update who's feeding", "error");
    } finally {
      setSaving(false);
    }
  }

  const active = babies.find((b) => b.id === activeId);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <BabyIcon className="w-4 h-4 text-primary-600" />
        <h2 className="text-sm font-semibold text-gray-900">Feeding now</h2>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        {active
          ? `The scale will record feeds for ${active.name}.`
          : "Pick who's being fed so the scale records it against the right baby."}
      </p>
      <div className="flex flex-wrap gap-2">
        {babies.map((b) => {
          const on = b.id === activeId;
          return (
            <button
              key={b.id}
              type="button"
              onClick={() => select(b.id)}
              disabled={saving}
              aria-pressed={on}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-50",
                on
                  ? "bg-primary-600 border-primary-600 text-white"
                  : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50",
              )}
            >
              {b.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}
