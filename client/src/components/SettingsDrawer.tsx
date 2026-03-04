import { useState, useEffect } from "react";
import type { ModelSummary, CurrentModelResponse } from "../types";
import { getAvailableModels, getCurrentModel, postSettingsKey, putCurrentModel } from "../api/wwClient";

type SettingsDrawerProps = {
    isOpen: boolean;
    onClose: () => void;
    onModelChanged?: (model: CurrentModelResponse) => void;
};

export function SettingsDrawer({ isOpen, onClose, onModelChanged }: SettingsDrawerProps) {
    const [apiKey, setApiKey] = useState("");
    const [currentModel, setCurrentModel] = useState<CurrentModelResponse | null>(null);
    const [availableModels, setAvailableModels] = useState<ModelSummary[]>([]);
    const [pending, setPending] = useState(false);
    const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

    useEffect(() => {
        if (isOpen) {
            refreshData();
        }
    }, [isOpen]);

    async function refreshData() {
        try {
            const [models, active] = await Promise.all([
                getAvailableModels(),
                getCurrentModel()
            ]);
            setAvailableModels(models);
            setCurrentModel(active);
        } catch (err) {
            console.error("Failed to refresh settings data", err);
        }
    }

    async function handleKeyUpdate(e: React.FormEvent) {
        e.preventDefault();
        if (!apiKey.trim()) return;
        setPending(true);
        setMessage(null);
        try {
            await postSettingsKey(apiKey);
            setApiKey("");
            setMessage({ text: "API key updated successfully.", type: "success" });
            refreshData();
        } catch (err) {
            setMessage({ text: err instanceof Error ? err.message : "Failed to update key.", type: "error" });
        } finally {
            setPending(false);
        }
    }

    async function handleModelChange(modelId: string) {
        if (modelId === currentModel?.model_id) return;
        setPending(true);
        setMessage(null);
        try {
            await putCurrentModel(modelId);
            const refreshed = await getCurrentModel();
            setCurrentModel(refreshed);
            if (onModelChanged) onModelChanged(refreshed);
            setMessage({ text: `Switched to ${refreshed.label}.`, type: "success" });
        } catch (err) {
            setMessage({ text: err instanceof Error ? err.message : "Failed to switch model.", type: "error" });
        } finally {
            setPending(false);
        }
    }

    if (!isOpen) return null;

    return (
        <div className="modal-overlay settings-drawer-overlay" onClick={onClose}>
            <div className="panel settings-drawer" onClick={(e) => e.stopPropagation()} role="dialog">
                <header className="panel-header">
                    <h2>Global Settings</h2>
                    <button className="close-btn" onClick={onClose} aria-label="Close settings">×</button>
                </header>

                <section className="settings-section">
                    <h3>OpenRouter Configuration</h3>
                    <div className="readiness-chip">
                        {currentModel?.api_key_configured ? (
                            <span className="status-ready">✓ API Key Configured</span>
                        ) : (
                            <span className="status-missing">⚠ API Key Missing</span>
                        )}
                    </div>

                    <form onSubmit={handleKeyUpdate} className="settings-key-form">
                        <input
                            type="password"
                            value={apiKey}
                            placeholder="Update API Key (sk-or-v1-...)"
                            onChange={(e) => setApiKey(e.target.value)}
                            disabled={pending}
                            autoComplete="off"
                        />
                        <button type="submit" className="choice-btn" disabled={pending || !apiKey.trim()}>
                            Update Key
                        </button>
                    </form>
                </section>

                <section className="settings-section">
                    <h3>Active Model</h3>
                    <select
                        value={currentModel?.model_id || ""}
                        onChange={(e) => handleModelChange(e.target.value)}
                        disabled={pending}
                    >
                        {availableModels.map((m) => (
                            <option key={m.model_id} value={m.model_id}>
                                {m.label} ({m.tier})
                            </option>
                        ))}
                    </select>
                    {currentModel && (
                        <div className="model-details muted">
                            <p>Tier: {currentModel.tier}</p>
                            <p>Quality: {currentModel.creative_quality}/10</p>
                            <p>Cost/10 turns: ${currentModel.estimated_session_cost.total_cost_usd.toFixed(2)}</p>
                        </div>
                    )}
                </section>

                {message && (
                    <p className={message.type === "success" ? "success-text" : "error-text"}>
                        {message.text}
                    </p>
                )}

                <footer className="settings-footer">
                    <p className="muted small">Runtime settings are persistent for this session.</p>
                </footer>
            </div>
        </div>
    );
}
