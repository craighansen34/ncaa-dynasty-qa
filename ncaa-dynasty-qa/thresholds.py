"""Parse and validate CI threshold settings (percentages from environment variables)."""
import math

THRESHOLDS = {
    # name: (default, description)
    "MIN_COVERAGE": (80.0, "minimum % of verify.py lines exercised by the regression suite"),
    "MIN_PARITY": (20.0, "minimum % of scenarios referenced by at least one regression test"),
    "MIN_MUTATION_SCORE": (100.0, "minimum % of verifier mutants detected by the unit suite"),
    "MIN_RULE_MUTATION_SCORE": (100.0, "minimum % of mutants detected for EACH verifier rule"),
}


def parse_threshold(name, raw, default):
    """Return (value, error). A blank/unset value uses the default.
    Valid values are numbers from 0 to 100 inclusive; a trailing % is allowed."""
    if raw is None or str(raw).strip() == "":
        return default, None
    text = str(raw).strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        value = float(text)
    except ValueError:
        return None, (f"{name}={raw!r} is not a number. Set it to a percentage between 0 and 100, "
                      f"e.g. {name}: \"{default:g}\" in .github/workflows/qa.yml (default {default:g}).")
    if math.isnan(value) or math.isinf(value):
        return None, f"{name}={raw!r} is not a finite number. Use a value between 0 and 100 (default {default:g})."
    if not 0 <= value <= 100:
        return None, (f"{name}={raw!r} is outside the allowed range 0-100. It is a percentage; "
                      f"use a whole percentage such as {name}: \"{default:g}\".")
    return value, None


def load_thresholds(env):
    """Return (values, errors) for every known threshold."""
    values, errors = {}, []
    for name, (default, _) in THRESHOLDS.items():
        v, err = parse_threshold(name, env.get(name), default)
        if err:
            errors.append(err)
        else:
            values[name] = v
    return values, errors
