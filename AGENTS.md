# Project workflow

Prioritize backend stability. Launch desktop, microphone, speech services, or local models only when the user requests their use or testing.

After an important update, run the tests relevant to the change. Push the tested source to the working GitHub branch and report the commit. Preserve unrelated developer changes and inspect the current branch head before updating it.

Keep API keys, personal settings, memories, logs, model files, and device identifiers outside GitHub commits.
