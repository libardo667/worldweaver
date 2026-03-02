import type { ToastItem } from "../types";

type ErrorToastStackProps = {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
};

export function ErrorToastStack({ toasts, onDismiss }: ErrorToastStackProps) {
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
          {toast.detail ? <p>{toast.detail}</p> : null}
        </article>
      ))}
    </div>
  );
}
