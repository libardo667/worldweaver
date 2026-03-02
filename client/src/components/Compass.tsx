const GRID: Array<{ key: string; label: string }> = [
  { key: "northwest", label: "NW" },
  { key: "north", label: "N" },
  { key: "northeast", label: "NE" },
  { key: "west", label: "W" },
  { key: "center", label: "•" },
  { key: "east", label: "E" },
  { key: "southwest", label: "SW" },
  { key: "south", label: "S" },
  { key: "southeast", label: "SE" },
];

type CompassProps = {
  availableDirections: string[];
  pending?: boolean;
  onMove: (direction: string) => void;
};

export function Compass({
  availableDirections,
  pending = false,
  onMove,
}: CompassProps) {
  const enabled = new Set(availableDirections.map((item) => item.toLowerCase()));
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

        const canMove = enabled.has(cell.key);
        return (
          <button
            key={cell.key}
            type="button"
            className="compass-btn"
            disabled={pending || !canMove}
            onClick={() => onMove(cell.key)}
            aria-label={`Move ${cell.key}`}
          >
            {cell.label}
          </button>
        );
      })}
    </div>
  );
}
