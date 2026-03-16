import type { SettingsReadinessResponse } from "../types";

type RuntimeDiagnosticsBannerProps = {
  readiness: SettingsReadinessResponse | null;
};

export function RuntimeDiagnosticsBanner({ readiness }: RuntimeDiagnosticsBannerProps) {
  const issues = (readiness?.checks ?? []).filter((check) => !check.ok);
  if (!readiness || issues.length === 0) return null;

  const blockingIssues = issues.filter((check) => check.severity === "error");
  const warningIssues = issues.filter((check) => check.severity !== "error");
  const shardLabel =
    readiness.shard?.city_id?.replace(/_/g, " ") ??
    readiness.shard?.shard_id ??
    "current shard";
  const hasErrors = blockingIssues.length > 0;
  const publicUrl = readiness.shard?.public_url;
  const federationUrl = readiness.shard?.federation_url;

  return (
    <section className={`ww-runtime-banner${hasErrors ? " is-error" : " is-warn"}`} aria-live="polite">
      <div className="ww-runtime-banner-copy">
        <p className="ww-runtime-banner-eyebrow">
          {hasErrors ? "Startup blocked" : "Runtime warnings"}
        </p>
        <p className="ww-runtime-banner-title">
          {shardLabel} has {issues.length} runtime issue{issues.length === 1 ? "" : "s"}.
        </p>
        <p className="ww-runtime-banner-meta">
          {readiness.shard.shard_type} shard
          {publicUrl ? ` • public ${publicUrl}` : ""}
          {federationUrl ? ` • federation ${federationUrl}` : ""}
        </p>
      </div>
      <div className="runtime-chip-row">
        {issues.map((check) => (
          <span
            key={check.code}
            className={`runtime-chip ${check.severity === "error" ? "runtime-chip-error" : "runtime-chip-warn"}`}
            title={check.message}
          >
            {check.label}
          </span>
        ))}
      </div>
      <ul className="ww-runtime-banner-list">
        {blockingIssues.map((check) => (
          <li key={`${check.code}-detail`}>
            <strong>{check.label}:</strong> {check.message}
          </li>
        ))}
        {warningIssues.map((check) => (
          <li key={`${check.code}-detail`}>
            <strong>{check.label}:</strong> {check.message}
          </li>
        ))}
      </ul>
    </section>
  );
}
