import { useMemo } from "react";
import { useKeyboardNavigation } from "../hooks/useKeyboardNavigation";
import type { SpatialDirectionMap } from "../types";

const GRID: Array<{ key: string; label: string }> = [
  { key: "northwest", label: "NW" },
  { key: "north", label: "N" },
  { key: "northeast", label: "NE" },
  { key: "west", label: "W" },
  { key: "center", label: "o" },
  { key: "east", label: "E" },
  { key: "southwest", label: "SW" },
  { key: "south", label: "S" },
  { key: "southeast", label: "SE" },
];

const DIRECTION_LABELS: Record<string, string> = {
  north: "north",
  northeast: "north-east",
  east: "east",
  southeast: "south-east",
  south: "south",
  southwest: "south-west",
  west: "west",
  northwest: "north-west",
};

type CompassProps = {
  availableDirections: SpatialDirectionMap;
  pending?: boolean;
  onMove: (direction: string) => void;
};

export function Compass({
  availableDirections,
  pending = false,
  onMove,
}: CompassProps) {
  const directionState = useMemo(() => {
    const normalized = new Map<
      string,
      { accessible: boolean; reason: string }
    >();
    for (const [direction, target] of Object.entries(availableDirections ?? {})) {
      const key = direction.toLowerCase();
      if (!key) {
        continue;
      }
      if (!target) {
        normalized.set(key, {
          accessible: false,
          reason: "No route mapped from here.",
        });
        continue;
      }
      if (target.accessible) {
        normalized.set(key, {
          accessible: true,
          reason: "",
        });
        continue;
      }
      const reason = String(target.reason ?? "").trim() || "Requirements not met.";
      normalized.set(key, {
        accessible: false,
        reason,
      });
    }
    return normalized;
  }, [availableDirections]);

  const enabledDirections = useMemo(
    () =>
      [...directionState.entries()]
        .filter(([, value]) => value.accessible)
        .map(([direction]) => direction),
    [directionState],
  );

  useKeyboardNavigation({
    availableDirections: enabledDirections,
    pending,
    onMove,
  });

  return (
    <div className="compass-grid" role="group" aria-label="Compass movement">
      {GRID.map((cell) => {
        if (cell.key === "center") {
          return (
            <div className="compass-center" key={cell.key} aria-hidden="true">
              {cell.label}
            </div>
          );
        }

        const status = directionState.get(cell.key);
        const canMove = status?.accessible ?? false;
        const blockedReason = status?.reason || "No route mapped from here.";
        const directionLabel = DIRECTION_LABELS[cell.key] ?? cell.key;
        return (
          <button
            key={cell.key}
            type="button"
            className={`compass-btn ${canMove ? "is-suggested" : "is-uncertain"}`}
            disabled={pending || !canMove}
            data-loading={pending ? "true" : "false"}
            aria-disabled={pending || !canMove}
            onClick={() => onMove(cell.key)}
            aria-label={
              canMove
                ? `Move ${directionLabel} (suggested path)`
                : `Cannot move ${directionLabel}: ${blockedReason}`
            }
            title={
              canMove
                ? `Move ${directionLabel} (suggested)`
                : `${directionLabel} blocked: ${blockedReason}`
            }
          >
            {cell.label}
          </button>
        );
      })}
    </div>
  );
}
