import {
  AlertTriangle,
  Info,
  Zap,
  Thermometer,
  Wrench,
  Droplet,
  AlertOctagon,
} from "lucide-react";

const TYPE_ICON: Record<string, React.FC<{ className?: string }>> = {
  overheating: Thermometer,
  malfunction: Wrench,
  washing_error: AlertOctagon,
  low_detergent: Droplet,
};

export function AlertTypeIcon({
  alertType,
  severity,
  className = "w-5 h-5",
}: {
  alertType: string;
  severity: string;
  className?: string;
}) {
  const TypeIcon = TYPE_ICON[alertType];
  if (TypeIcon) return <TypeIcon className={className} />;
  if (severity === "info") return <Info className={className} />;
  if (severity === "critical") return <Zap className={className} />;
  return <AlertTriangle className={className} />;
}

export function severityIconColor(severity: string) {
  return (
    { info: "text-blue-500", warning: "text-yellow-500", error: "text-red-500", critical: "text-red-700" }[
      severity
    ] || "text-gray-400"
  );
}

export function severityBadge(severity: string) {
  return (
    {
      info: "bg-blue-100 text-blue-700",
      warning: "bg-yellow-100 text-yellow-700",
      error: "bg-red-100 text-red-700",
      critical: "bg-red-200 text-red-800",
    }[severity] || "bg-gray-100 text-gray-600"
  );
}
