#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cast_hexagram.py — 易经三枚铜钱法起卦数字生成器 (Yijing three-coin caster)

PURPOSE
    Generate the six line values (初爻 -> 上爻) for a Yijing (I-Ching) hexagram
    using the traditional three-coin method (三枚铜钱法). Six casts; each cast
    tosses three coins. Each coin is secrets.choice([2, 3]) where 3 = 正面/阳
    (heads/yang) and 2 = 反面/阴 (tails/yin). The sum of the three coins is the
    line value 6/7/8/9. This naturally reproduces the traditional probability
    distribution P(6)=1/8, P(7)=3/8, P(8)=3/8, P(9)=1/8.

    Line value mapping:
        6 = 老阴 (old yin)   -> yin, changing (变爻)
        7 = 少阳 (young yang)-> yang, static
        8 = 少阴 (young yin) -> yin, static
        9 = 老阳 (old yang)  -> yang, changing (变爻)
    A line is a changing line (变爻) iff its value is in {6, 9}.

INTERFACE
    Reads no input files. Writes no files. Performs no network access.
    Outputs a single JSON object to stdout:
        {
            "lines":          [6 ints, 初爻 -> 上爻],
            "yin_yang":       [6 strings "阳"/"阴", 初爻 -> 上爻],
            "changing_lines": [positions 1..6 of changing lines],
            "coins_detail":   [[3 coin values] per cast, 初爻 -> 上爻],
            "method":         "three_coins",
            "rng":            "secrets_csprng"   (or "seeded_prng" when --seed given)
        }

SECURITY CONSTRAINTS
    - Pure standard library only: secrets, json, argparse, sys (+ random for --seed).
    - secrets = cryptographically secure CSPRNG (default randomness source).
    - READ-ONLY: emits numbers to stdout only. Zero file writes, zero network,
      no access to yijing_history or any other program data.
    - exit 0 on success; exit non-zero only on argument/internal error.

OPTIONS
    --seed INT   Reproducible casting for SimulateStep tests only. Uses
                 random.Random(seed) instead of secrets. Default: no seed
                 -> secrets true randomness. NOT for production divination.
    --pretty     Pretty-print the JSON (2-space indent) instead of compact.
"""

import argparse
import json
import secrets
import sys

# Coin faces: 3 = 正面/阳 (heads/yang), 2 = 反面/阴 (tails/yin)
COIN_FACES = [2, 3]

# Line value -> (阴阳, is_changing). 变爻 = value in {6, 9}.
LINE_MAP = {
    6: ("阴", True),   # 老阴 old yin (changing)
    7: ("阳", False),  # 少阳 young yang (static)
    8: ("阴", False),  # 少阴 young yin (static)
    9: ("阳", True),   # 老阳 old yang (changing)
}


def _toss_three_coins(picker):
    """Toss three coins using the supplied picker callable.

    picker() must return one element of COIN_FACES. Returns (line_value, [coins]).
    line_value is the sum of three coins -> one of 6/7/8/9.
    """
    coins = [picker(COIN_FACES) for _ in range(3)]
    return sum(coins), coins


def cast(seed=None):
    """Cast a full hexagram (six lines, 初爻 -> 上爻).

    seed=None -> secrets CSPRNG (default, cryptographically secure true random).
    seed=int  -> random.Random(seed) deterministic sequence (reproducible test).
    """
    if seed is None:
        picker = secrets.choice
        rng_label = "secrets_csprng"
    else:
        import random  # local import: only when reproducible mode requested
        rng = random.Random(seed)
        picker = rng.choice
        rng_label = "seeded_prng"

    lines = []
    yin_yang = []
    changing_lines = []
    coins_detail = []

    # Six casts: cast 1 = 初爻 (bottom line) ... cast 6 = 上爻 (top line).
    for position in range(1, 7):
        value, coins = _toss_three_coins(picker)
        polarity, is_changing = LINE_MAP[value]
        lines.append(value)
        yin_yang.append(polarity)
        coins_detail.append(coins)
        if is_changing:
            changing_lines.append(position)

    return {
        "lines": lines,
        "yin_yang": yin_yang,
        "changing_lines": changing_lines,
        "coins_detail": coins_detail,
        "method": "three_coins",
        "rng": rng_label,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Yijing three-coin hexagram caster (secrets CSPRNG true random)."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Reproducible PRNG seed for SimulateStep tests only; default uses secrets true randomness.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output with 2-space indentation.",
    )
    args = parser.parse_args(argv)

    result = cast(seed=args.seed)

    if args.pretty:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
