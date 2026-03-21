import type { LocationGraphNode } from "../api/wwClient";
import type { EntranceMode } from "./EntryFlow";
import { LocationMap } from "./LocationMap";

type LocationChooserScreenProps = {
  entranceMode: EntranceMode;
  loading: boolean;
  joining: boolean;
  entryLoadError: string | null;
  pendingLocation: string | null;
  selectedLocation: string;
  gallerySample: string[];
  mapNodes: LocationGraphNode[];
  onPendingLocationChange: (location: string | null) => void;
  onShuffleGallery: () => void;
  onRetryEntryLoad: () => void;
  onConfirmLocation: (location?: string) => void;
};

export function LocationChooserScreen({
  entranceMode,
  loading,
  joining,
  entryLoadError,
  pendingLocation,
  selectedLocation,
  gallerySample,
  mapNodes,
  onPendingLocationChange,
  onShuffleGallery,
  onRetryEntryLoad,
  onConfirmLocation,
}: LocationChooserScreenProps) {
  const active = pendingLocation ?? selectedLocation;
  const locName = active.replace(/_/g, " ");
  const locationTitle =
    entranceMode === "observer"
      ? "Where would you like to arrive?"
      : "Where would you like to begin?";
  const locationHelper =
    entranceMode === "observer"
      ? "As an observer, you can move, watch, and listen without speaking or altering the world."
      : "You can start anywhere. The world will remember where you entered.";

  return (
    <div className="entry-overlay entry-overlay--location">
      <div className="entry-loc-header">
        <span className="entry-loc-title">{locationTitle}</span>
      </div>
      <p className="entry-alert-text" style={{ margin: "0 auto 1rem", maxWidth: "42rem", textAlign: "center" }}>
        {locationHelper}
      </p>

      {gallerySample.length > 0 && (
        <div className="entry-loc-gallery">
          {gallerySample.map((loc) => (
            <button
              key={loc}
              className={`entry-loc-chip${loc === active ? " entry-loc-chip--active" : ""}`}
              onClick={() => onPendingLocationChange(loc)}
            >
              {loc.replace(/_/g, " ")}
            </button>
          ))}
          <button
            className="entry-loc-chip entry-loc-chip--shuffle"
            onClick={onShuffleGallery}
            title="Shuffle suggestions"
          >
            {"<->"}
          </button>
        </div>
      )}

      <div className="entry-map-container">
        {loading ? (
          <div className="entry-map-loading">Loading map...</div>
        ) : entryLoadError ? (
          <div className="entry-map-error">
            <p>{entryLoadError}</p>
            <button className="entry-alert-btn" onClick={onRetryEntryLoad}>
              RETRY SHARD BOOT
            </button>
          </div>
        ) : (
          <LocationMap
            nodes={mapNodes}
            edges={[]}
            onNodeClick={(nodeName) => onPendingLocationChange(nodeName)}
            pendingDest={pendingLocation}
          />
        )}
      </div>

      {active && (
        <div className="entry-loc-confirm-bar">
          <span className="entry-loc-confirm-name">{locName}</span>
          <button
            className="entry-loc-confirm-btn"
            onClick={() => onConfirmLocation(active)}
            disabled={joining}
          >
            {joining
              ? "ENTERING..."
              : entranceMode === "observer"
                ? `Enter quietly from ${locName} ->`
                : `Enter the world from ${locName} ->`}
          </button>
        </div>
      )}
    </div>
  );
}
