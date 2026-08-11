import { Baby as BabyIcon, Trash2 } from "lucide-react";
import Mascot from "./Mascot";
import { Baby } from "../store/babyStore";
import { ageDaysFromISO, describeAge, earliestDobISO, todayISO } from "../services/age";

export interface BabyForm {
  name: string;
  gender: "male" | "female";
  dob: string;
  weight: string;
}

/** Form values for a baby as currently stored. */
export function formFor(baby: Baby): BabyForm {
  return {
    name: baby.name,
    gender: baby.gender,
    dob: baby.date_of_birth ?? "",
    weight: String(baby.weight_kg),
  };
}

/** Whether the user has actually altered anything — used to skip no-op saves. */
export function isDirty(baby: Baby, form: BabyForm): boolean {
  const original = formFor(baby);
  return (
    original.name !== form.name ||
    original.gender !== form.gender ||
    original.dob !== form.dob ||
    Number(original.weight) !== Number(form.weight)
  );
}

/**
 * One baby's fields, fully controlled.
 *
 * Deliberately has no <form>, no Save and no card chrome: every baby sits
 * inside one shared section with a single Save at the bottom, so the parent
 * owns the state and the submit. Remove stays here because deleting a profile
 * is a per-baby action, not part of saving edits.
 */
export default function BabyProfileFields({
  baby,
  value,
  onChange,
  onRemove,
  canRemove,
  removing,
  compact,
}: {
  baby: Baby;
  value: BabyForm;
  onChange: (next: BabyForm) => void;
  onRemove: () => void;
  canRemove: boolean;
  removing: boolean;
  /** True when babies sit two-across, where the full-size mascot crowds the fields. */
  compact?: boolean;
}) {
  const age = describeAge(ageDaysFromISO(value.dob));
  const id = (f: string) => `baby-${baby.id}-${f}`;
  const set = (patch: Partial<BabyForm>) => onChange({ ...value, ...patch });

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <BabyIcon className="w-4 h-4 text-primary-600 flex-shrink-0" />
        {/* The stored name, not the edited one — this labels which record the
            fields belong to, so it shouldn't shift while you're typing. */}
        <h3 className="text-sm font-semibold text-gray-900 truncate">{baby.name}</h3>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            disabled={removing}
            className="ml-auto flex items-center gap-1.5 text-xs font-medium text-red-600 border border-red-200 hover:bg-red-50 rounded-lg px-2.5 py-1 disabled:opacity-50 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {removing ? "Removing…" : "Remove"}
          </button>
        )}
      </div>

      <div className="flex items-start gap-4">
        <Mascot
          variant={value.gender === "male" ? "boy" : "girl"}
          size={compact ? 72 : 120}
          className="flex-shrink-0 hidden sm:block"
        />
        <div className="flex-1 min-w-0 space-y-4">
          <div>
            <label htmlFor={id("name")} className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              id={id("name")}
              type="text"
              value={value.name}
              onChange={(e) => set({ name: e.target.value })}
              required
              maxLength={255}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
            />
          </div>

          <div>
            <label htmlFor={id("dob")} className="block text-sm font-medium text-gray-700 mb-1">
              Date of birth
            </label>
            <input
              id={id("dob")}
              type="date"
              value={value.dob}
              onChange={(e) => set({ dob: e.target.value })}
              max={todayISO()}
              min={earliestDobISO()}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
            />
            {age ? (
              <p className="text-xs text-gray-400 mt-1">{age}.</p>
            ) : (
              // Profiles created before this field existed land here. Say what
              // it unlocks rather than just flagging it as empty.
              <p className="text-xs text-amber-600 mt-1">
                Add a date of birth to enable age-based feeding guidance.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor={id("gender")} className="block text-sm font-medium text-gray-700 mb-1">
                Gender
              </label>
              <select
                id={id("gender")}
                value={value.gender}
                onChange={(e) => set({ gender: e.target.value as "male" | "female" })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              >
                <option value="male">Boy</option>
                <option value="female">Girl</option>
              </select>
            </div>
            <div>
              <label htmlFor={id("weight")} className="block text-sm font-medium text-gray-700 mb-1">
                Weight (kg)
              </label>
              <input
                id={id("weight")}
                type="number"
                min="0.5"
                max="30"
                step="0.1"
                value={value.weight}
                onChange={(e) => set({ weight: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
