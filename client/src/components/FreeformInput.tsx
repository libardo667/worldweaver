import { FormEvent, useState } from "react";

type FreeformInputProps = {
  pending: boolean;
  onSubmit: (value: string) => Promise<void>;
  onTypingActivity?: () => void;
};

export function FreeformInput({
  pending,
  onSubmit,
  onTypingActivity,
}: FreeformInputProps) {
  const [value, setValue] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || pending) {
      return;
    }
    await onSubmit(trimmed);
    setValue("");
  }

  return (
    <form className="freeform" onSubmit={handleSubmit}>
      <label htmlFor="freeform-action">Freeform action</label>
      <div className="freeform-row">
        <input
          id="freeform-action"
          type="text"
          value={value}
          aria-disabled={pending}
          aria-label="Describe a freeform action"
          onChange={(event) => {
            setValue(event.target.value);
            onTypingActivity?.();
          }}
          placeholder="Try: I quietly inspect the broken bridge supports."
        />
        <button
          type="submit"
          aria-label="Submit freeform action"
          disabled={pending || !value.trim()}
          data-loading={pending ? "true" : "false"}
        >
          {pending ? "Sending..." : "Act"}
        </button>
      </div>
    </form>
  );
}
