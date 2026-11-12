# ZAE as a coding helper: plan for options 2 and 3

Grey picked these on 2026-11-01. Nothing below is built yet.

## Option 2: ZAE manages a coding tool

**What you'd do:** say or type "ZAE, make the rings blue when I'm tired" (or pick one of her own ideas from option 3).

**What she'd do:**
1. **Write the task.** Talk turns your words into a clear brief: what to change, which files are probably involved (from her code index), and how to check it worked. You see the brief and can edit it before she starts.
2. **Make a safe copy.** A separate git worktree (`C:\Projects\ZAENIA-Helper`, branch `zae/<task>`) is created. The live app and my worktree are never touched.
3. **Hand it to the coding tool.** The tool works only inside that copy. Choose which one below.
4. **Check the work herself.** She runs the test suite, the UI checks and the TypeScript build in the copy. If something fails, the tool gets one or two more tries with the error.
5. **Refuse unsafe changes.** If the change touches any locked path (security, voice check, passkey, permissions, auth, Code Doctor itself, data/), she throws it away and tells you why. This list is the same one Code Doctor already uses.
6. **Show you the result.** A new "Build requests" card in Code Doctor shows the plain-English summary, the full diff (Side by side), and the test results.
7. **You decide at the PC.** "Approve" merges it into the live app and rebuilds. "Reject" deletes the copy. Approval uses the same desktop key or near-pass check as code apply today, and never works from the phone.
8. **Undo.** Every approved change is one git commit, so "undo the last change" reverts it.

**Which coding tool (your choice):**
- **a. Aider + your local Qwen (free, offline).** Private and costs nothing, but it's only good for small changes (a setting, a colour, one function). Needs Aider installed (a Python package, so I'd need your OK).
- **b. Gemini CLI (free tier, online).** Much stronger and handles medium features. Your code is sent to Google. Needs Node (already installed) plus a Google sign-in.
- **c. Claude Code (already on your PC).** The strongest of the three, and it's what I am. It uses your Claude plan, and your code goes to Anthropic, as it already does when I work.
- My pick: **c** for real features and **a** as the offline fallback. She picks a based on size, and you can override her per task.

**What she can never do (checked in code, not just told to her):**
- Start a task by herself. Every task needs your words or your tap.
- Merge without your approval at the PC.
- Change a locked path, her own permission rules, or this helper's own code.
- Push to GitHub.
- Send secrets or data/ to an online tool. The tool works in a copy without data/, .env, or tokens.

## Option 3: self-improvement loop

**What she watches** (already logged on the PC):
- Requests that failed or that you repeated ("log my food" twice in a row).
- Errors in the server log and the uptime checks.
- Things you corrected her on.
- Tabs you open but leave immediately.
- Slow replies (from the brain timings).

**What she does with it:**
- Once a night (the nightly job, skipped while gaming), Study reads the last day of these and writes up to 3 upgrade ideas. Each idea has the evidence ("you asked to log water 4 times and it failed twice"), what she'd change, and how big it is.
- The ideas show in Suggestions and in the morning brief. You tap "Build it" (which starts option 2), "Not now", or "Never". She learns from "Never" and stops suggesting that kind of idea.
- She never builds an idea without your tap.

## Build order
1. The helper copy, the locked-path check, the test runner, and the Build requests card (the safe base; usable by hand).
2. Hooking up the coding tool you choose, with retries on failed tests.
3. Voice and chat ("ZAE, build …"), and Approve, Reject and Undo.
4. The nightly improvement ideas (option 3).

Each step gets tests, especially proving that locked paths and phone approval are refused.

## Limits to expect
- With local models (a) alone, expect about half of small requests to come out right first time. Bigger features need b or c.
- A task takes minutes, not seconds. She'll say when it's ready, and you can keep using her meanwhile. If you're gaming, she waits until you're done.
- Study and a local coding model can't both be on the graphics card, so research and coding take turns.
