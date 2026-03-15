import type { ToastItem } from "../types";

type ErrorToastStackProps = {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
};

export function ErrorToastStack({ toasts, onDismiss }: ErrorToastStackProps) {
  const shorten = (detail: string): string => {
    const singleLine = detail.replace(/\s+/g, " ").trim();
    return singleLine.length > 280 ? `${singleLine.slice(0, 277)}...` : singleLine;
  };

  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <article
          key={toast.id}
          className={`toast ${toast.kind === "error" ? "toast-error" : "toast-info"}`}
        >
          <header>
            <strong>{toast.title}</strong>
            <button type="button" onClick={() => onDismiss(toast.id)}>
              Dismiss
            </button>
          </header>
          {toast.detail ? <p title={toast.detail}>{shorten(toast.detail)}</p> : null}
        </article>
      ))}
    </div>
  );
}
