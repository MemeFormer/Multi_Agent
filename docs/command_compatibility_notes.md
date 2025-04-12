# Command Compatibility & Issue Notes

This file tracks OS-specific command behaviors and other issues encountered
during testing to improve agent prompting and validation.

---

## macOS/BSD `sed -i`

* **OS:** macOS / BSD variants
* **Command:** `sed`
* **Flag:** `-i` (in-place edit)
* **Issue:** Requires a backup extension argument immediately following `-i`. Fails with `undefined label` error if missing. Standard GNU `sed` allows `-i` without an extension.
* **Solution:** Provide an empty string `''` as the backup extension argument.
* **Incorrect (macOS):** `sed -i 's/old/new/g' filename`
* **Correct (macOS):** `sed -i '' 's/old/new/g' filename`
* **Prompt Guidance:** Instruct agents (Junior generation, Senior review) to generate/validate commands ensuring **macOS/BSD compatibility**, specifically mentioning the `sed -i ''` requirement.
---