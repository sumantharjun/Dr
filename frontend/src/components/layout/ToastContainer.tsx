import { X, CheckCircle, AlertTriangle, Info, XCircle } from "lucide-react";
import { useToastStore, ToastType } from "../../store/toastStore";
import { clsx } from "clsx";

const styles: Record<ToastType, string> = {
  info: "bg-blue-600",
  success: "bg-green-600",
  warning: "bg-yellow-500",
  error: "bg-red-600",
};

const Icons: Record<ToastType, React.FC<{ className?: string }>> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: XCircle,
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => {
        const Icon = Icons[t.type];
        return (
          <div
            key={t.id}
            className={clsx(
              "flex items-start gap-3 px-4 py-3 rounded-xl text-white shadow-lg pointer-events-auto",
              styles[t.type]
            )}
          >
            <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <p className="text-sm flex-1">{t.message}</p>
            <button
              onClick={() => removeToast(t.id)}
              className="flex-shrink-0 opacity-70 hover:opacity-100"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
