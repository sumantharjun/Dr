import { clsx } from "clsx";

/** A single shimmering placeholder block. Compose these to mirror real layout. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-md bg-gray-200/70", className)} />;
}

/** A card-shaped placeholder used while list/grid data loads. */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={clsx("bg-white rounded-xl border border-gray-200 p-4", className)}>
      <Skeleton className="w-full h-32 mb-3" />
      <Skeleton className="h-4 w-3/4 mb-2" />
      <Skeleton className="h-3 w-1/2 mb-4" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-7 w-20 rounded-full" />
      </div>
    </div>
  );
}

/** A stat/panel placeholder (rounded box with a couple of lines). */
export function PanelSkeleton({ className }: { className?: string }) {
  return (
    <div className={clsx("bg-white rounded-xl border border-gray-200 p-5", className)}>
      <Skeleton className="h-4 w-1/3 mb-4" />
      <Skeleton className="h-8 w-1/2 mb-2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}
