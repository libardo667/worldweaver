// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import type { MapNode } from "../api/types";

/** URL slug for a place name: "Mill Reach" -> "mill-reach". */
export function slugifyPlace(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function findNodeBySlug(nodes: MapNode[], slug: string): MapNode | undefined {
  return nodes.find((node) => slugifyPlace(node.name) === slug);
}

/** Places a spectator can look at: georeferenced and not a system channel.
    Landmarks count — they are real places people stand at and talk in. */
export function isVisitablePlace(node: MapNode): boolean {
  return node.lat != null && node.lon != null && !node.name.startsWith("__");
}
