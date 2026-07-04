#!/usr/bin/env python3
"""draw.py — equal-probability random draw for the random_draw_aisp skill.

This is an `execute_only` script resource declared in aisp_contract.resources with
requires_tools: ["shell"]. It is invoked by the `draw` node via `sys.run`, not
injected in full into the model context (mode gating). It emits a JSON summary on
stdout. Zero third-party deps (stdlib only).

It generalizes coin_flip_aisp (fixed two sides) to a user-supplied list of N
equal-weight options, drawing one option per pick with equal probability
1/len(options).

Randomness (NN1 LOCAL CSPRNG):
  - Uses `secrets.randbelow(len(options))` (a cryptographically-secure RNG), never
    the `random` module. Each pick is an independent, equal-probability draw over
    the option list.
  - Stamps rng="secrets" in the output so the draw node can assert the source.

Security boundary (NN2 NO NETWORK):
  - Writes stdout only. No file writes, no network, no subprocess. stdlib only.

Input guard (NN4):
  - --n must be an integer in 1..100.
  - --options is a comma- and/or newline-delimited list; after stripping it must
    contain >= 2 options, all non-empty, and all DISTINCT. Repeated --option args
    are also accepted and appended to the list.
    Any violation prints a JSON error to stderr and exits with a nonzero code.

Disclaimer (NN3):
  - The stdout payload carries a `disclaimer` string marking the result as a
    random, not-serious, not-advice outcome, so the report node can assert it.
"""
import argparse
import json
import secrets
import sys

DISCLAIMER = (
    "本结果由密码学安全随机(secrets)生成, 仅供娱乐/打破僵局, "
    "不作为医疗/法律/财务等严肃决策依据 (random result, not advice)."
)


def parse_options(options_str, extra_options):
    """Split a comma/newline-delimited string into a stripped option list, then
    append any repeated --option args. Empty fragments are dropped so trailing
    delimiters do not create phantom empty options."""
    parts = []
    if options_str:
        normalized = options_str.replace("\r\n", "\n").replace("\r", "\n")
        for chunk in normalized.replace("\n", ",").split(","):
            stripped = chunk.strip()
            if stripped:
                parts.append(stripped)
    for opt in extra_options or []:
        stripped = opt.strip()
        if stripped:
            parts.append(stripped)
    return parts


def draw(n, options):
    """Draw n options from `options` using a local CSPRNG, equal probability
    1/len(options) per option. 0..len(options)-1 index via secrets.randbelow."""
    bound = len(options)
    picks = [options[secrets.randbelow(bound)] for _ in range(n)]
    counts = {opt: picks.count(opt) for opt in options}
    return {
        "rng": "secrets",
        "n": n,
        "options": options,
        "picks": picks,
        "counts": counts,
        "disclaimer": DISCLAIMER,
    }


def fail(message):
    json.dump({"error": message}, sys.stderr, ensure_ascii=False)
    sys.stderr.write("\n")
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Equal-probability random draw from N options using a local CSPRNG (secrets)."
    )
    parser.add_argument("--n", type=int, default=1, help="Number of draws (1..100).")
    parser.add_argument(
        "--options",
        type=str,
        default="",
        help="Comma- and/or newline-delimited option list, e.g. \"苹果,香蕉,橙子\".",
    )
    parser.add_argument(
        "--option",
        action="append",
        default=[],
        dest="option",
        help="Repeatable single option; appended to the list from --options.",
    )
    args = parser.parse_args(argv)

    n = args.n
    options = parse_options(args.options, args.option)

    if not isinstance(n, int) or n < 1 or n > 100:
        return fail("n must be an integer in 1..100")
    if len(options) < 2:
        return fail("options must contain at least 2 non-empty entries")
    if not all(o for o in options):
        return fail("every option must be non-empty")
    if len(set(options)) != len(options):
        return fail("all options must be distinct")

    json.dump(draw(n, options), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
