import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchShards, getApiBase, setApiBase } from "../api/wwClient";
import {
  clearJwt,
  clearOnboardedSession,
  clearSelectedShardUrl,
  getSelectedShardUrl,
  setSelectedShardUrl,
} from "../state/sessionStore";
import type { ShardInfo, ToastItem } from "../types";

type PushToast = (title: string, detail?: string, kind?: ToastItem["kind"]) => void;

export function useShardSession(pushToast: PushToast) {
  const [shards, setShards] = useState<ShardInfo[]>([]);
  const [shardsLoaded, setShardsLoaded] = useState(false);
  const [selectedShardUrl, setSelectedShardUrlState] = useState<string>(
    () => getSelectedShardUrl() ?? "",
  );

  useEffect(() => {
    fetchShards().then((fetched) => {
      setShards(fetched);
      const stored = getSelectedShardUrl();
      const resolved =
        (stored && fetched.find((s) => s.shard_url === stored)) ||
        (selectedShardUrl && fetched.find((s) => s.shard_url === selectedShardUrl)) ||
        null;

      if (resolved) {
        setSelectedShardUrlState(resolved.shard_url);
        setApiBase(resolved.shard_url);
        setShardsLoaded(true);
        return;
      }

      if (fetched.length === 1) {
        const only = fetched[0];
        setSelectedShardUrlState(only.shard_url);
        setSelectedShardUrl(only.shard_url);
        setApiBase(only.shard_url);
        setShardsLoaded(true);
        return;
      }

      if (fetched.length > 1) {
        clearSelectedShardUrl();
        setSelectedShardUrlState("");
      }
      setShardsLoaded(true);
    }).catch(() => {
      pushToast(
        "Shard registry unavailable",
        "Could not load the federation shard list. Falling back to the current backend only.",
        "info",
      );
      setShardsLoaded(true);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCitySwitch = useCallback((shardUrl: string) => {
    if (shardUrl === selectedShardUrl) return;
    setSelectedShardUrl(shardUrl);
    clearJwt();
    clearOnboardedSession();
    window.location.reload();
  }, [selectedShardUrl]);

  const handleSelectShard = useCallback((shardUrl: string) => {
    setSelectedShardUrlState(shardUrl);
    setSelectedShardUrl(shardUrl);
    setApiBase(shardUrl);
  }, []);

  const startupShardSelectionRequired = shardsLoaded && shards.length > 1 && !selectedShardUrl;
  const standaloneShardMode = shardsLoaded && shards.length === 0;
  const apiBaseReady =
    standaloneShardMode ||
    (shardsLoaded &&
      !startupShardSelectionRequired &&
      Boolean(selectedShardUrl || getApiBase()));
  const selectedShard = useMemo(
    () => shards.find((shard) => shard.shard_url === selectedShardUrl) ?? null,
    [selectedShardUrl, shards],
  );

  return {
    shards,
    shardsLoaded,
    selectedShardUrl,
    startupShardSelectionRequired,
    standaloneShardMode,
    apiBaseReady,
    selectedShard,
    handleCitySwitch,
    handleSelectShard,
  };
}
