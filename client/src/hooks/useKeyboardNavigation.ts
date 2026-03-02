import { useEffect, useMemo } from "react";

const FREEFORM_INPUT_ID = "freeform-action";

const DIRECTION_BY_KEY: Record<string, string> = {
  ArrowUp: "north",
  ArrowDown: "south",
  ArrowLeft: "west",
  ArrowRight: "east",
  w: "north",
  a: "west",
  s: "south",
  d: "east",
  q: "northwest",
  e: "northeast",
  z: "southwest",
  x: "southeast",
};

function targetIsEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    tagName === "input" ||
    tagName === "textarea" ||
    tagName === "select" ||
    tagName === "button"
  );
}

function toDirectionForKey(key: string): string | null {
  if (key in DIRECTION_BY_KEY) {
    return DIRECTION_BY_KEY[key];
  }
  const lower = key.toLowerCase();
  return DIRECTION_BY_KEY[lower] ?? null;
}

type UseKeyboardNavigationProps = {
  availableDirections: string[];
  pending: boolean;
  onMove: (direction: string) => void;
};

export function useKeyboardNavigation({
  availableDirections,
  pending,
  onMove,
}: UseKeyboardNavigationProps) {
  const enabledDirections = useMemo(
    () => new Set(availableDirections.map((item) => item.toLowerCase())),
    [availableDirections],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const key = event.key;
      const editableTarget = targetIsEditable(event.target);

      if (key === "Enter" && !editableTarget) {
        const input = document.getElementById(FREEFORM_INPUT_ID);
        if (input instanceof HTMLInputElement) {
          event.preventDefault();
          input.focus();
        }
        return;
      }

      if (pending || editableTarget || event.repeat || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }

      const direction = toDirectionForKey(key);
      if (!direction || !enabledDirections.has(direction)) {
        return;
      }

      event.preventDefault();
      onMove(direction);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabledDirections, onMove, pending]);
}
