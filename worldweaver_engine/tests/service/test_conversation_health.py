from datetime import datetime, timedelta, timezone
import json

from src.services.conversation_health import PublicConversationMessage, analyze_public_conversation

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _messages(bodies_by_speaker: dict[str, list[str]], *, locations: dict[str, str] | None = None) -> list[PublicConversationMessage]:
    rows: list[PublicConversationMessage] = []
    offset = 0
    for message_index in range(max(map(len, bodies_by_speaker.values()))):
        for speaker, bodies in bodies_by_speaker.items():
            if message_index >= len(bodies):
                continue
            rows.append(
                PublicConversationMessage(
                    speaker_key=speaker,
                    body=bodies[message_index],
                    created_at=START + timedelta(minutes=offset),
                    location_key=(locations or {}).get(speaker, "square"),
                )
            )
            offset += 1
    return rows


def test_report_refuses_population_language_metrics_below_three_speakers():
    report = analyze_public_conversation(_messages({"one": ["hello"], "two": ["hello"]}))

    assert report == {
        "schema": "worldweaver.public-conversation-health",
        "schema_version": 1,
        "input_scope": "public_location_chat",
        "privacy": "aggregate_no_source_text",
        "message_count": 2,
        "speaker_count": 2,
        "minimum_speakers": 3,
        "status": "insufficient_population",
    }


def test_converged_population_scores_as_less_distinct_than_divergent_population():
    converged = _messages(
        {
            "one": ["inspect the drainage fault", "repair the municipal grid"],
            "two": ["inspect the drainage fault", "repair the municipal grid"],
            "three": ["inspect the drainage fault", "repair the municipal grid"],
        }
    )
    divergent = _messages(
        {
            "one": ["paint ochre pigment", "mix violet pigment"],
            "two": ["knead cardamom bread", "taste seeded bread"],
            "three": ["practice cello melody", "hum a quiet melody"],
        }
    )

    converged_report = analyze_public_conversation(converged)
    divergent_report = analyze_public_conversation(divergent)

    assert converged_report["lexical"]["speaker_convergence"] > divergent_report["lexical"]["speaker_convergence"]
    assert converged_report["lexical"]["distinctiveness_gap"] < divergent_report["lexical"]["distinctiveness_gap"]
    assert converged_report["topic_shape"]["civic_message_fraction"] == 1.0
    assert divergent_report["topic_shape"]["civic_message_fraction"] == 0.0


def test_report_never_emits_source_text_names_locations_or_sentinel():
    sentinel = "ultraviolet-capybara-sentinel"
    rows = _messages(
        {
            "private-looking-name-one": [f"paint a mural {sentinel}", "fold paper birds"],
            "private-looking-name-two": ["bake apricot bread", "share a warm meal"],
            "private-looking-name-three": ["tune the violin", "practice a dance"],
        },
        locations={
            "private-looking-name-one": "secret-looking-location-one",
            "private-looking-name-two": "secret-looking-location-two",
            "private-looking-name-three": "secret-looking-location-three",
        },
    )

    serialized = json.dumps(analyze_public_conversation(rows), sort_keys=True)

    assert sentinel not in serialized
    assert "private-looking-name" not in serialized
    assert "secret-looking-location" not in serialized
    assert "mural" not in serialized
    assert "apricot" not in serialized


def test_closed_pair_conversation_has_high_interaction_concentration():
    rows = [
        PublicConversationMessage(
            speaker_key=speaker,
            body=f"synthetic message {index}",
            created_at=START + timedelta(minutes=index),
            location_key="square",
        )
        for index, speaker in enumerate(("one", "two", "one", "two", "one", "two", "three"))
    ]

    report = analyze_public_conversation(rows)

    assert report["interaction"]["adjacent_reply_transitions"] == 6
    assert report["interaction"]["unique_pairs"] == 2
    assert report["interaction"]["top_pair_share"] > 0.8
    assert report["interaction"]["pair_concentration"] > 0.7


def test_repetition_and_anonymous_topic_entropy_are_numeric_only():
    rows = _messages(
        {
            "one": ["same phrase again", "same phrase again", "same phrase again"],
            "two": ["garden tomatoes", "garden tomatoes", "garden tomatoes"],
            "three": ["quiet guitar", "quiet guitar", "quiet guitar"],
        }
    )

    report = analyze_public_conversation(rows)

    assert report["lexical"]["exact_repeat_fraction"] == 1.0
    assert 0.0 <= report["topic_shape"]["normalized_cluster_entropy"] <= 1.0
    assert isinstance(report["topic_shape"]["anonymous_cluster_count"], int)
