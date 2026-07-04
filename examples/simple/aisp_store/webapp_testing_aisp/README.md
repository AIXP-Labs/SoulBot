<!-- generated_from_aisp: true -->
<!-- source: aisp.aisop.json -->
<!-- generator: tools/aisp_readme.py -->

# Webapp Testing

This README is a deterministic projection of `aisp.aisop.json`. The contract remains the source of truth.

## Identity

| Field | Value |
| --- | --- |
| Skill ID | `webapp_testing_aisp` |
| Version | `1.3.0` |
| Protocol | `AISP V1.0.0` |
| License | `Apache-2.0` |
| Risk Level | `medium` |
| Category | testing |
| Tags | webapp-testing, playwright, browser-automation, frontend-verification, ui-debugging, screenshot, console-logs, headless, local-only, selectors, static-html, dynamic-webapp, accessibility-audit, axe-core, wcag-2.2-aa, playwright-tracing, trace-viewer, visual-regression, network-har, har-capture, video-recording, route-stubbing, request-interception |

## Purpose

Local-only AISP V1.0.0 Playwright skill that tests a LOCAL web app: verify frontend, debug UI, audit accessibility (axe-core WCAG 2.2 AA, data-only), capture screenshots/console logs, visual-regression diffs, trace.zip, network HAR, and debug video; isolates external deps via local egress-preserving route-stubbing. Reconnaissance-Then-Action, web-first readiness-wait before inspect (domcontentloaded + expect(getByRole).toBeVisible; networkidle demoted to optional auxiliary), expect auto-wait. Red lines: headless-only, always-close-browser, local-only host, no egress.

## When To Use

- The user asks to test or verify the frontend of a LOCAL web app (a dev server on localhost or a static .html file) — does the page render, do the buttons/forms work.
- The user wants to debug UI behavior of a local web app and needs to inspect the rendered DOM, discover selectors, or click/fill/submit elements.
- The user wants a full_page screenshot of a local page as a visual reference or regression artifact.
- The user wants to read/capture the browser console logs of a local page to diagnose a JavaScript/UI problem.
- The user has a dynamic local webapp whose dev server may or may not be running and wants it started (via the bundled with_server.py helper) and then driven with Playwright.
- The user hands over a path to a local static HTML file and wants it loaded via file:// and interacted with.
- The user wants an accessibility audit of a local page (axe-core WCAG 2.2 AA scan) reported as raw findings/violations data — not a pass/fail compliance certification.
- The user wants a Playwright trace (trace.zip viewable in Trace Viewer) of a local test run to debug flaky steps, slow loads, or failed actions.
- The user wants a visual-regression check of a local page — compare the current full_page screenshot against a stored baseline (toHaveScreenshot) to catch unintended UI/pixel changes.
- The user wants a network HAR of a local test run (record_har_path -> network.har) to inspect the HTTP requests/responses the local app made while it was driven — for debugging failing API calls, slow requests, or missing resources.
- The user wants a recorded debug video of a local Playwright run (record_video_dir) to watch what happened during a flaky or failing test.
- The user wants to isolate a local app from its external dependencies during a test by stubbing routes — abort specific requests or fulfill them with a canned local response (e.g. mock a flaky upstream API) WITHOUT forwarding anything to a remote origin.

## When Not To Use

- The user wants to test a REMOTE or PRODUCTION website (any non-localhost / non-file:// URL) — this skill is local-only and never targets remote/production hosts.
- The user wants load/performance/stress testing or large-scale crawling rather than functional UI verification of a single local app.
- The user wants to scrape or exfiltrate data from external sites or upload the app's data anywhere (no network egress is permitted).
- The user wants to drive an untrusted third-party page or a page hosting hostile content — a malicious page could attempt indirect prompt injection through DOM/console text, so only local, trusted apps-under-test are in scope.
- The user wants native mobile-app or desktop-GUI automation (this skill drives a headless chromium browser only).
- The user wants a headed/visible browser session for manual interactive clicking (this skill always runs headless).
- The user wants unit/integration tests at the code level (pytest/jest) rather than browser-driven end-to-end UI checks.
- The user wants a formal accessibility CONFORMANCE certification or legal WCAG/ADA/Section-508 sign-off — this skill reports axe-core findings as raw data only and renders no pass/fail compliance verdict.
- The user wants cross-browser/cross-device visual baselines hosted on a remote visual-testing cloud service — the visual-regression diff here is local-only against a local baseline, with no remote upload.
- The user wants route-stubbing that FORWARDS or PROXIES intercepted requests to a remote/production origin (route.continue / route.fetch to an external host) — this skill's route-stubbing is egress-preserving and supports abort or LOCAL fulfill ONLY, never remote forwarding.
- The user wants to capture a HAR or video of a REMOTE/PRODUCTION site, or to upload the HAR/video anywhere — these are local-only debug artifacts written under output_dir and never transmitted.

## How To Run

With an AISOP runtime:

1. Load `aisp.aisop.json`.
2. Read `user.content.aisp_contract` before execution.
3. Run `user.content.aisop.main` exactly as declared.
4. Enforce every `non_negotiable` rule and every referenced `sys.*` mechanism.
5. Treat `sys.io.confirm` and other human-confirmation gates as blocking controls.

With a generic AI or non-AISOP agent:

- Treat this README as bootstrap guidance only.
- Verify external provenance or obtain explicit human approval before executing an untrusted package.
- Load the contract from `aisp.aisop.json`; do not treat this README as authoritative.
- Follow `RUN aisop.main` and the non-negotiable rules on a best-effort basis.
- Hard guarantees such as `sys.assert`, tool gating, and `sys.io.confirm` exist only in a conforming AISOP runtime.

## Non-Negotiable Rules

| Rule | Enforced By |
| --- | --- |
| Headless launch: the browser MUST be launched in headless mode (chromium.launch(headless=True)); no visible/headed browser window is ever opened. | `LaunchBrowser.step2:sys.assert` |
| Wait-before-inspect (Reconnaissance-Then-Action): for a dynamic webapp the skill MUST wait until a role-based readiness signal is visible BEFORE inspecting the DOM, deriving selectors, or taking a screenshot (the source's documented Common Pitfall: inspecting too early) — the web-first readiness contract is page.wait_for_load_state('domcontentloaded') followed by a web-first assertion on a user-facing locator, expect(page.getByRole(<role>, name=<name>)).toBeVisible() (or .toBeEnabled()), which auto-waits for the actual element the test depends on. networkidle is DISCOURAGED (an anti-pattern per playwright.dev — background-polling/websocket/SSE pages may never reach it) and is at most demoted to an OPTIONAL auxiliary technique, no longer a mandatory red line. Inspect -> identify -> act ordering is mandatory. | `Reconnaissance.step3:sys.assert` |
| Browser close on completion: the browser MUST be closed on every completion path; no leaked browser process or resource remains. | `Teardown.step2:sys.assert` |
| Local-only target: every navigation host MUST be localhost / 127.0.0.1 / file://; remote or production sites are never targeted. | `ClassifyTarget.step2:sys.assert` |
| No exfiltration: data is processed purely locally; nothing is uploaded or sent over any network. The skill declares no open-world/network capability — its tools allow-list (browser, code, filesystem) carries open_world=false on every tool. | `tools` |

## Resources

| ID | Path | Kind | Mode | Scope | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| with_server_helper | scripts/with_server.py | script | execute_only | skill | b0dcf4918935b795f4eda9821579b9902119235ff4447f687a30286e7d0925fd |
| example_element_discovery | examples/element_discovery.py | example | read_only | skill | d63c89604a22f8845d724e95dda45db49b1bf57c25ce0a83afbb7b8da3d402f0 |
| example_static_html_automation | examples/static_html_automation.py | example | read_only | skill | 9d533aafb875ee3ab8b8ebf8f5b9003ac8d999da3d09b285cce252e623140064 |
| example_console_logging | examples/console_logging.py | example | read_only | skill | ea46877289acb82da7e7ce59d0bc37c8977cd57e2a006d0c88d7a1c625bf95da |

## Integrity

| Hash | Value | Meaning |
| --- | --- | --- |
| `contract_sha256` | `3f05989d093ef12399599862fb9212ccdff3364278bafc4e90e2419ff229cae9` | Recomputable hash of `user.content.aisp_contract` |
| `resources_sha256` | `dcf7692370aaf65d93f9c1d0caac2a9c6bc271750d27e643de6a6bb736a925c4` | Recomputable hash of declared resource records |

`package_sha256` is intentionally not embedded here because a README is part of the distributed package and package-level hashes belong in external registry/provenance artifacts. Recompute it with `tools/aisp_hash.py` at publication time.

These hashes show local integrity only. They do not prove trust, safety, or registry approval.

## Source Of Truth

`aisp.aisop.json` is authoritative. A successful README check proves only that this file matches the contract-derived projection; it does not prove that the skill is safe or trustworthy.
