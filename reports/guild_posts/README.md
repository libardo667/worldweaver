# Guild Posts

Archive of Substack drafts and source digests for **The Guild of the Humane Arts**.

Suggested layout:

- `YYYY-MM-DD/post.md`
- `YYYY-MM-DD/daily_digest.md`

Recommended workflow:

1. Generate the digest:
   ```bash
   python3 worldweaver_engine/scripts/daily_world_digest.py --all-cities --conversation-themes --format publication_markdown --output reports/daily_digest.md
   ```
2. Copy the digest into that day's folder as `daily_digest.md`.
3. Start the post from [`TEMPLATE.md`](/home/levibanks/personal_projects/worldweaver/reports/guild_posts/TEMPLATE.md).
4. Write the opening reflection and `Today's Signal` in your own voice.
5. Keep the digest mostly intact so each post remains grounded in the same daily instrumentation.

Practical rule:

- treat the post as interpretation
- treat the digest as evidence
