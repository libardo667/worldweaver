// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useEffect, useState } from "react";
import { getMakingCatalog, postMake } from "../api/ww";
import type { MakingCatalog } from "../api/types";

type Props = {
  location: string;
  sessionId: string;
  /** Called after something is made so carried-object views can refresh. */
  onMade: () => void;
};

/**
 * The making bench: recipes available at this exact place, drawn from its
 * replenishing materials. Hidden entirely on shards without the capability.
 */
export function MakeHere({ location, sessionId, onMade }: Props) {
  const [catalog, setCatalog] = useState<MakingCatalog | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);
  const [makingRecipeId, setMakingRecipeId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    getMakingCatalog(sessionId)
      .then((result) => {
        if (live) setCatalog(result);
      })
      .catch(() => {
        if (live) setCatalog(null);
      });
    return () => {
      live = false;
    };
  }, [sessionId, location, refreshCount]);

  if (!catalog || catalog.recipes.length === 0) return null;

  async function make(recipeId: string) {
    if (makingRecipeId) return;
    setMakingRecipeId(recipeId);
    setError("");
    try {
      await postMake(sessionId, recipeId);
      setRefreshCount((n) => n + 1);
      onMade();
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "The making didn't take.");
      setRefreshCount((n) => n + 1);
    } finally {
      setMakingRecipeId(null);
    }
  }

  const availability = new Map(catalog.materials.map((m) => [m.material_id, m.available_units]));

  return (
    <section className="place-section">
      <h3 className="place-section-title">Things you could make here</h3>
      {catalog.materials.length > 0 && (
        <p className="make-materials">
          {catalog.materials.map((m) => `${m.material_id.replace(/[_-]+/g, " ")}: ${m.available_units}`).join(" · ")}
        </p>
      )}
      {error && <p className="join-error" role="alert">{error}</p>}
      {catalog.recipes.map((recipe) => (
        <div key={recipe.recipe_id} className="make-recipe">
          <div className="make-recipe-info">
            <span className="make-recipe-title">{recipe.title}</span>
            {recipe.description && <span className="make-recipe-desc">{recipe.description}</span>}
            <span className="make-recipe-inputs">
              needs{" "}
              {Object.entries(recipe.inputs)
                .map(([materialId, units]) => {
                  const short = materialId.replace(/[_-]+/g, " ");
                  const have = availability.get(materialId) ?? 0;
                  return `${units} ${short}${have < units ? ` (only ${have} here)` : ""}`;
                })
                .join(", ")}
            </span>
          </div>
          <button className="stoop-take" onClick={() => make(recipe.recipe_id)} disabled={!recipe.can_make || makingRecipeId != null}>
            {makingRecipeId === recipe.recipe_id ? "Making…" : "Make it"}
          </button>
        </div>
      ))}
    </section>
  );
}
