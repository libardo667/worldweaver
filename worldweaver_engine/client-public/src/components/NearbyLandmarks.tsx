// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { Landmark } from "../api/types";

type Props = {
  landmarks: Landmark[];
  onVisit: (name: string) => void;
};

export function NearbyLandmarks({ landmarks, onVisit }: Props) {
  if (landmarks.length === 0) return null;
  return (
    <section className="place-section">
      <h3 className="place-section-title">Nearby</h3>
      <ul className="landmark-list">
        {landmarks.slice(0, 6).map((landmark) => (
          <li key={landmark.name} className="landmark-item">
            <button className="landmark-visit" onClick={() => onVisit(landmark.name)}>
              {landmark.name}
            </button>
            {landmark.distance_km != null && <span className="landmark-distance">{landmark.distance_km.toFixed(1)} km</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
