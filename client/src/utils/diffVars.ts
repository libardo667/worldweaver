import type { ChangeItem, VarsRecord } from "../types";

export const DEFAULT_RECEIPT_LIMIT = 5;

type ReceiptDraft = {
  key?: string;
  text: string;
  priority: number;
};

type BuildReceiptsInput = {
  previousVars: VarsRecord;
  nextVars: VarsRecord;
  choiceSet?: VarsRecord;
  stateChanges?: VarsRecord;
  eventLabel?: string;
};

function makeChangeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function isDeltaValue(value: unknown): value is { inc?: unknown; dec?: unknown } {
  return (
    !!value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    ("inc" in value || "dec" in value)
  );
}

function normalizeKeyLabel(key: string): string {
  if (key.startsWith("pref.")) {
    return key.slice("pref.".length);
  }
  if (key.startsWith("pref_")) {
    return key.slice("pref_".length);
  }
  return key;
}

function humanizeKey(key: string): string {
  const normalized = normalizeKeyLabel(key);
  const spaced = normalized
    .replace(/\./g, " ")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return spaced || key;
}

function keyPriority(key: string): number {
  let priority = 0;
  if (!key.startsWith("_")) {
    priority += 10;
  } else {
    priority -= 8;
  }
  if (key.startsWith("pref.") || key.startsWith("pref_")) {
    priority += 15;
  }
  return priority;
}

function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value === null || value === undefined) {
    return "none";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function flattenStateChanges(raw: VarsRecord): VarsRecord {
  const out: VarsRecord = {};
  for (const [key, value] of Object.entries(raw)) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      (key === "environment" || key === "variables")
    ) {
      for (const [nestedKey, nestedValue] of Object.entries(value as VarsRecord)) {
        out[`${key}.${nestedKey}`] = nestedValue;
      }
      continue;
    }
    out[key] = value;
  }
  return out;
}

function buildVarDiffDrafts(previousVars: VarsRecord, nextVars: VarsRecord): ReceiptDraft[] {
  const keys = new Set<string>([
    ...Object.keys(previousVars),
    ...Object.keys(nextVars),
  ]);
  const drafts: ReceiptDraft[] = [];

  for (const key of keys) {
    const before = previousVars[key];
    const after = nextVars[key];
    if (JSON.stringify(before) === JSON.stringify(after)) {
      continue;
    }

    const label = humanizeKey(key);
    if (before === undefined) {
      drafts.push({
        key,
        text: `${label} added: ${formatValue(after)}`,
        priority: 55 + keyPriority(key),
      });
    } else if (after === undefined) {
      drafts.push({
        key,
        text: `${label} removed`,
        priority: 54 + keyPriority(key),
      });
    } else {
      drafts.push({
        key,
        text: `${label}: ${formatValue(before)} -> ${formatValue(after)}`,
        priority: 56 + keyPriority(key),
      });
    }
  }

  return drafts;
}

function buildPayloadDrafts(
  payload: VarsRecord,
  prefix: string,
  basePriority: number,
): ReceiptDraft[] {
  const drafts: ReceiptDraft[] = [];
  for (const [key, value] of Object.entries(payload)) {
    const label = humanizeKey(key);
    if (isDeltaValue(value)) {
      const inc = Number(value.inc ?? 0);
      const dec = Number(value.dec ?? 0);
      const delta = inc - dec;
      const sign = delta >= 0 ? "+" : "";
      drafts.push({
        key,
        text: `${prefix} ${label} ${sign}${delta}`,
        priority: basePriority + keyPriority(key),
      });
      continue;
    }

    drafts.push({
      key,
      text: `${prefix} ${label} -> ${formatValue(value)}`,
      priority: basePriority + keyPriority(key),
    });
  }
  return drafts;
}

function groupPreferenceDrafts(drafts: ReceiptDraft[]): ReceiptDraft[] {
  const prefLabels = new Set<string>();
  let prefUpdates = 0;
  const remaining: ReceiptDraft[] = [];

  for (const draft of drafts) {
    const key = draft.key ?? "";
    if (key.startsWith("pref.") || key.startsWith("pref_")) {
      prefLabels.add(humanizeKey(key));
      prefUpdates += 1;
      continue;
    }
    remaining.push(draft);
  }

  if (prefUpdates > 0) {
    const labels = [...prefLabels].slice(0, 3);
    const extra = prefLabels.size > labels.length ? ` +${prefLabels.size - labels.length} more` : "";
    remaining.push({
      text: labels.length > 0
        ? `Preferences updated: ${labels.join(", ")}${extra}`
        : `Preferences updated (${prefUpdates})`,
      priority: 90,
    });
  }

  return remaining;
}

function sortAndDedupe(drafts: ReceiptDraft[]): ReceiptDraft[] {
  const sorted = [...drafts].sort((a, b) => b.priority - a.priority);
  const seen = new Set<string>();
  const output: ReceiptDraft[] = [];
  for (const draft of sorted) {
    if (seen.has(draft.text)) {
      continue;
    }
    seen.add(draft.text);
    output.push(draft);
  }
  return output;
}

export function buildWhatChangedReceipts({
  previousVars,
  nextVars,
  choiceSet,
  stateChanges,
  eventLabel,
}: BuildReceiptsInput): ChangeItem[] {
  const drafts: ReceiptDraft[] = [];

  if (eventLabel) {
    drafts.push({ text: eventLabel, priority: 30 });
  }

  drafts.push(...buildVarDiffDrafts(previousVars, nextVars));

  if (choiceSet) {
    drafts.push(...buildPayloadDrafts(choiceSet, "Choice delta:", 70));
  }

  if (stateChanges) {
    const flattened = flattenStateChanges(stateChanges);
    drafts.push(...buildPayloadDrafts(flattened, "Action impact:", 72));
  }

  const finalDrafts = sortAndDedupe(groupPreferenceDrafts(drafts));
  return finalDrafts.map((draft) => ({
    id: makeChangeId("chg"),
    text: draft.text,
  }));
}
