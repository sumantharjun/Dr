import { useBabyStore } from "../store/babyStore";

type Variant = "auto" | "sleeping" | "boy" | "girl";

interface MascotProps {
  variant?: Variant;
  size?: number;
  className?: string;
  alt?: string;
}

/**
 * Brand mascot.
 *  - "sleeping" — pre-login / pre-gender bear on a moon (universal).
 *  - "boy"      — boy theme companion (Unobear / cream cub).
 *  - "girl"     — girl theme companion (Dr. Novabear / gray doctor bear).
 *  - "auto"     — pick based on the baby's gender; falls back to sleeping
 *                 bear if no baby is set yet.
 */
export default function Mascot({
  variant = "auto",
  size = 160,
  className = "",
  alt,
}: MascotProps) {
  const baby = useBabyStore((s) => s.baby);

  let src = "/mascots/Sleeping_Bear_Mascot.png";
  let label = "Sleeping bear mascot";

  let resolved: Variant = variant;
  if (resolved === "auto") {
    if (!baby) resolved = "sleeping";
    else resolved = baby.gender === "male" ? "boy" : "girl";
  }

  if (resolved === "boy") {
    src = "/mascots/Medico_Mascot.png";
    label = "Unobear mascot";
  } else if (resolved === "girl") {
    src = "/mascots/Doctor_Mascot.png";
    label = "Dr. Novabear mascot";
  }

  return (
    <img
      src={src}
      alt={alt ?? label}
      width={size}
      height={size}
      className={className}
      style={{ width: size, height: size, objectFit: "contain" }}
    />
  );
}
