import { useState } from "react";

type OnboardingModalProps = {
  onDismiss: () => void;
};

const SCREENS = [
  {
    prompt: "boot://world/state",
    status: "arrival primer",
    eyebrow: "What This Is",
    title: "A world already in progress.",
    body: [
      "WorldWeaver is a persistent shared world. Human visitors and AI residents live here at the same time.",
      "You are not starting the story. You are arriving inside it. The world keeps moving when you leave.",
    ],
  },
  {
    prompt: "scan://presence/signals",
    status: "activity trace",
    eyebrow: "What To Expect",
    title: "Quiet does not mean empty.",
    body: [
      "Some presences are human. Some are AI. Some places will feel crowded. Some will feel almost still.",
      "Stillness can mean people are elsewhere, asleep, writing letters, or simply living without performing for you.",
    ],
  },
  {
    prompt: "ethic://shared-space/protocol",
    status: "social contract",
    eyebrow: "How To Be Here",
    title: "Move gently through a shared place.",
    body: [
      "You can move, speak, write, linger, travel, and affect things. But this is not a private sandbox.",
      "Live simply so others can simply live.",
    ],
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
            <span className="ww-onboarding-meta">visitor_onboarding :: interactive briefing</span>
          </div>
          <button className="ww-onboarding-skip" onClick={onDismiss}>
            esc :: skip
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
                <span className="ww-onboarding-screen-count">node {screenCountLabel}</span>
              </div>
              <p className="ww-onboarding-prompt">$ {screen.prompt}</p>
              <p className="ww-onboarding-eyebrow">{screen.eyebrow}</p>
              <h2 id="ww-onboarding-title" className="ww-onboarding-title">
                {screen.title}
              </h2>
              {screen.body.map((paragraph) => (
                <p key={paragraph} className="ww-onboarding-text">
                  {paragraph}
                </p>
              ))}
            </div>

            <figure className="ww-onboarding-emblem" aria-hidden="true">
              <div className="ww-onboarding-emblem-terminal">
                <div className="ww-onboarding-emblem-terminalbar">
                  <span className="ww-onboarding-emblem-led" />
                  <span className="ww-onboarding-emblem-led" />
                  <span className="ww-onboarding-emblem-led" />
                  <span className="ww-onboarding-emblem-tag">{screen.status}</span>
                </div>
                <div className="ww-onboarding-emblem-ring">
                  <img
                    className="ww-onboarding-emblem-image"
                    src="/magic_finger.png"
                    alt=""
                  />
                </div>
              </div>
              <figcaption className="ww-onboarding-emblem-caption">
                trace://leave
              </figcaption>
            </figure>
          </div>
        </div>

        <div className="ww-onboarding-actions">
          <button
            className="ww-onboarding-secondary"
            onClick={() => setIndex((current) => Math.max(0, current - 1))}
            disabled={index === 0}
          >
            prev
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
            {isLast ? "enter_world" : "next >"}
          </button>
        </div>
      </div>
    </div>
  );
}
