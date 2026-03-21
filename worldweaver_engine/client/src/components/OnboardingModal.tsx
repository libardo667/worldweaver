import { useState } from "react";

type OnboardingModalProps = {
  onDismiss: () => void;
};

const SCREENS = [
  {
    eyebrow: "What This Is",
    title: "A world already in progress.",
    body:
      "WorldWeaver is a persistent mixed-intelligence world. You are not starting the story. You are arriving inside it, and it keeps moving when you leave.",
  },
  {
    eyebrow: "How To Be Here",
    title: "Quiet does not mean empty.",
    body:
      "Some presences are human. Some are AI. Some places will feel crowded. Some will feel almost still. Move gently through a shared place.",
  },
] as const;

export function OnboardingModal({ onDismiss }: OnboardingModalProps) {
  const [index, setIndex] = useState(0);
  const screen = SCREENS[index];
  const isLast = index === SCREENS.length - 1;
  const screenCountLabel = `${String(index + 1).padStart(2, "0")}/${String(SCREENS.length).padStart(2, "0")}`;

  return (
    <div className="ww-onboarding" role="dialog" aria-modal="true" aria-labelledby="ww-onboarding-title">
      <div className="ww-onboarding-panel">
        <div className="ww-onboarding-head">
          <div className="ww-onboarding-head-copy">
            <span className="ww-onboarding-brand">WorldWeaver</span>
            <span className="ww-onboarding-meta">Welcome</span>
          </div>
          <button className="ww-onboarding-skip" onClick={onDismiss}>
            Skip
          </button>
        </div>

        <div className="ww-onboarding-body">
          <div className="ww-onboarding-stage">
            <div className="ww-onboarding-copy">
              <div className="ww-onboarding-statusline">
                <div className="ww-onboarding-progress" aria-hidden="true">
                  {SCREENS.map((item, itemIndex) => (
                    <span
                      key={item.eyebrow}
                      className={`ww-onboarding-dot${itemIndex === index ? " is-active" : ""}`}
                    />
                  ))}
                </div>
                <span className="ww-onboarding-screen-count">{screenCountLabel}</span>
              </div>
              <p className="ww-onboarding-eyebrow">{screen.eyebrow}</p>
              <h2 id="ww-onboarding-title" className="ww-onboarding-title">
                {screen.title}
              </h2>
              <p className="ww-onboarding-text">{screen.body}</p>
            </div>
          </div>
        </div>

        <div className="ww-onboarding-actions">
          <button
            className="ww-onboarding-secondary"
            onClick={() => setIndex((current) => Math.max(0, current - 1))}
            disabled={index === 0}
          >
            Back
          </button>
          <button
            className="ww-onboarding-primary"
            onClick={() => {
              if (isLast) {
                onDismiss();
                return;
              }
              setIndex((current) => Math.min(SCREENS.length - 1, current + 1));
            }}
          >
            {isLast ? "Got it" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
