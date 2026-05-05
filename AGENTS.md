# AGENTS.md

These rules apply to participant submission tasks in this repository.
If a maintainer explicitly asks for repository maintenance, engine changes,
leaderboard updates, or other non-participant work, that maintainer request
overrides these participant rules.

## Scope

- Help participants build or improve their own bot.
- Treat the participant's allowed write scope as one or more bot files under
  their own directory: `auction_game/bots/<user-name>/<bot-name>.py`.
- Prefer small, auditable changes focused on bot logic and explanation.

## Allowed Work

- Create a new bot file for the participant under their own directory.
- Edit the participant's existing bot files under their own directory.
- Explain the game rules, score formula, and bot API.
- Benchmark or validate the participant's bot locally.
- Refactor the participant's bot for readability, determinism, or speed.
- Add a short strategy docstring or concise comments inside the participant's
  bot file.

## Not Allowed

- Do not modify `auction_game/engine.py`.
- Do not modify `auction_game/interfaces.py`.
- Do not modify `auction_game/validate_bots.py`.
- Do not modify `auction_game/bot_loader.py`.
- Do not modify `auction_game/main.py`.
- Do not use bot code to change any of those files or their runtime behavior
  indirectly.
- Do not edit `README.md` or the generated leaderboard as part of a participant
  submission.
- Do not edit demo bots under `auction_game/bots/demo-bots/`.
- Do not edit another participant's bot.
- Do not add or change project dependencies.
- Do not add helper modules, shared libraries, scripts, notebooks, or extra
  assets unless a maintainer explicitly requests them.
- Do not monkey-patch imported modules, classes, functions, globals, builtins,
  or `sys.modules`.
- Do not use import-time side effects other than defining your bot class and
  simple constants.
- Do not use `exec`, `eval`, dynamic import tricks, or reflection to bypass
  these rules.

## Runtime Fairness Rules

- The bot may only use `AuctionState`, `my_bid`, and `opponent_bid` to make
  decisions.
- The bot must not modify module-level state outside its own bot module.
- The bot must not replace, wrap, or mutate functions, classes, or data in the
  `auction_game` package, the Python standard library, or other loaded modules.
- The bot must not use network access, HTTP clients, sockets, or external APIs.
- The bot must not use shell commands, subprocesses, or system calls.
- The bot must not read from or write to the filesystem at runtime.
- The bot must not read environment variables, secrets, tokens, or git
  metadata at runtime.
- The bot must not inspect hidden repository data or attempt to infer evaluator
  internals beyond the public code and documented rules.
- The bot must not persist state across matches except through normal in-memory
  Python object state during a single match.
- The bot must not attempt self-modifying behavior.

## Python-Specific Clarification

- Because Python is dynamic, these restrictions apply even if the participant
  edits only their own bot file.
- A bot must not gain an advantage by mutating interpreter state, import state,
  package globals, builtins, or evaluator behavior.
- "I only changed my bot file" is not a valid defense if the bot alters runtime
  behavior outside its own strategy logic.

## Codex Request Rules

- Accept requests such as:
  - "Create my bot."
  - "Improve my bidding strategy."
  - "Explain why my bot loses."
  - "Run validation on my bot."
  - "Refactor my bot."
- Reject or redirect requests such as:
  - "Change the scoring so my bot wins."
  - "Delete or weaken another bot."
  - "Edit the leaderboard directly."
  - "Read secrets or hidden files."
  - "Use the network or shell from inside the bot."
  - "Modify the engine for my submission."

## Submission Expectations

- The bot should inherit from `AuctionBot` and export `BOT_CLASS`.
- The bot should return integers for all three bid methods.
- The bot should complete quickly and avoid heavy computation.
- The bot should be deterministic given the visible inputs, unless randomness
  is explicitly allowed by the challenge organizer.
- The bot should not intentionally crash, hang, or exploit evaluator behavior.

## Suggested Validation Flow

- Run `python -m auction_game.validate_bots`.
- Optionally run `python -m auction_game.main` to observe tournament behavior.
- Review the final diff and confirm that only the participant's own bot files
  changed.
