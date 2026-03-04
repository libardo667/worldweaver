import { useState, useEffect } from "react";
import type { ModelSummary } from "../types";
import { getAvailableModels, postSettingsKey, putCurrentModel } from "../api/wwClient";

type SetupModalProps = {
    missing: string[];
    onComplete: () => void;
};

export function SetupModal({ missing, onComplete }: SetupModalProps) {
    const [apiKey, setApiKey] = useState("");
    const [selectedModel, setSelectedModel] = useState("");
    const [availableModels, setAvailableModels] = useState<ModelSummary[]>([]);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState("");

    const needsKey = missing.includes("api_key");
    const needsModel = missing.includes("model");

    useEffect(() => {
        async function fetchModels() {
            try {
                const models = await getAvailableModels();
                setAvailableModels(models);
                // Default to first available model if we need one
                if (needsModel && models.length > 0 && !selectedModel) {
                    setSelectedModel(models[0].model_id);
                }
            } catch (err) {
                console.error("Failed to fetch models for setup", err);
            }
        }
        fetchModels();
    }, [needsModel, selectedModel]);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setPending(true);
        setError("");

        try {
            if (needsKey) {
                if (!apiKey.trim()) {
                    throw new Error("API key is required.");
                }
                await postSettingsKey(apiKey);
            }

            if (needsModel) {
                if (!selectedModel) {
                    throw new Error("Please select a model.");
                }
                await putCurrentModel(selectedModel);
            }

            onComplete();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Setup failed.");
        } finally {
            setPending(false);
        }
    }

    return (
        <div className="modal-overlay setup-modal-overlay">
            <div className="panel setup-modal" role="dialog" aria-labelledby="setup-title">
                <header className="panel-header">
                    <h2 id="setup-title">System Readiness Required</h2>
                    <span className="panel-meta">First-run configuration</span>
                </header>

                <p className="muted">
                    WorldWeaver needs a few more details to start generating your story.
                    These settings are stored in memory for this session.
                </p>

                <form onSubmit={handleSubmit} className="setup-form">
                    {needsKey && (
                        <label className="setup-field">
                            OpenRouter API Key
                            <input
                                type="password"
                                value={apiKey}
                                placeholder="sk-or-v1-..."
                                onChange={(e) => setApiKey(e.target.value)}
                                disabled={pending}
                                autoComplete="off"
                            />
                            <span className="field-hint">Required for LLM generation.</span>
                        </label>
                    )}

                    {needsModel && (
                        <label className="setup-field">
                            Primary Model
                            <select
                                value={selectedModel}
                                onChange={(e) => setSelectedModel(e.target.value)}
                                disabled={pending}
                            >
                                <option value="" disabled>Select a model...</option>
                                {availableModels.map((m) => (
                                    <option key={m.model_id} value={m.model_id}>
                                        {m.label} ({m.tier})
                                    </option>
                                ))}
                            </select>
                            <span className="field-hint">The model used for world weaving.</span>
                        </label>
                    )}

                    {error && <p className="error-text">{error}</p>}

                    <button
                        type="submit"
                        className="choice-btn setup-submit"
                        disabled={pending || (needsKey && !apiKey.trim()) || (needsModel && !selectedModel)}
                    >
                        {pending ? "Saving..." : "Initialize Runtime"}
                    </button>
                </form>
            </div>
        </div>
    );
}
