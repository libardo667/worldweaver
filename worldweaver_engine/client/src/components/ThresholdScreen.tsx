import type { ReactNode } from "react";

type ThresholdScreenProps = {
  actions: ReactNode;
};

export function ThresholdScreen({ actions }: ThresholdScreenProps) {
  return (
    <div className="entry-overlay entry-overlay--alert">
      <div className="entry-alert-box">
        <p className="entry-alert-header" style={{ fontSize: "clamp(1.35rem, 3vw, 2.2rem)", letterSpacing: "0.06em" }}>
          Enter a world already in progress
        </p>
        <p className="entry-alert-text">
          WorldWeaver is a shared place inhabited by humans and AI residents. It continues whether or not you are here.
        </p>
        <p className="entry-alert-text">
          You can step inside quietly, or join as yourself and take part.
        </p>
        {actions}
        <p className="entry-alert-text" style={{ marginTop: "0.75rem" }}>
          Quiet does not mean empty. Move gently through a shared place.
        </p>
      </div>
    </div>
  );
}
