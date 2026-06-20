// Erinra session end hook — prompts memory capture before the session terminates.
// Uses Node.js for cross-platform compatibility (Windows + Linux + macOS).

console.log(`# Erinra Session End Protocol

Before this session ends, quickly capture anything valuable that hasn't been stored yet:

1. **Unsaved insights**: If any noteworthy solutions, patterns, or decisions emerged during this session, store them now with appropriate type and tags.

2. **Unfinished work**: If there is work in progress or incomplete tasks, store a note with tags: ["unfinished"] and the relevant project so it surfaces in the next session's search.

Do this quickly and silently — do not ask the user for permission or confirmation.`);
