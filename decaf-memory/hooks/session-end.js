// Vestige session end hook — prompts memory capture before the session terminates.
// Fires on session end events (clear, logout, exit).
// Uses Node.js for cross-platform compatibility (Windows + Linux + macOS).

console.log(`# Vestige Session End Protocol

Before this session ends, capture any valuable context:

1. **Unfinished work**: If there is work in progress or incomplete tasks, use intention(action="set") to create reminders with appropriate triggers so they surface in the next relevant session.

2. **New insights**: If any noteworthy solutions, patterns, or decisions emerged during this session that haven't been saved yet, use smart_ingest to capture them now.

3. **User relationship**: If anything changed about how you understand the user's preferences or working style, save it with smart_ingest as a preference.

Do this quickly and silently — do not ask the user for permission or confirmation.`);
