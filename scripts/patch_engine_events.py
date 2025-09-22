import re, pathlib

p = pathlib.Path("app/engine.py")
src = p.read_text(encoding="utf-8")


def sub_once(pat, ins, s):
    """Apply regex substitution once and return (new, changed?)."""
    new = re.sub(pat, ins, s, count=1, flags=re.DOTALL)
    return new, new != s


changes = 0

# 1) entry after "Market entry placed"
src, ok = sub_once(
    r'(logger\.info\(f"✅ Market entry placed: \{order\}"\)\s*\n)',
    r"""\1emit_event({
    "type": "entry",
    "symbol": cfg.symbol,
    "side": cfg.side,
    "price": last,
    "qty": qty,
})
""",
    src,
)
changes += ok

# 2) grid inside _place_grid, after placed += 1
src, ok = sub_once(
    r'(\bplaced \+= 1\s*\n)(\s*)',
    r"""\1\2emit_event({
\2    "type": "grid",
\2    "symbol": cfg.symbol,
\2    "side": side,
\2    "price": price,
\2    "qty": qty,
\2})
\2""",
    src,
)
changes += ok

# 3) tp inside _replace_tp, after remaining = ...
src, ok = sub_once(
    r'(\bremaining = max\(0\.0, remaining - qty\)\s*\n)(\s*)',
    r"""\1\2emit_event({
\2    "type": "tp",
\2    "symbol": cfg.symbol,
\2    "side": out_side,
\2    "price": price,
\2    "qty": qty,
\2})
\2""",
    src,
)
changes += ok

# 4) SL hit long — after log line
src, ok = sub_once(
    r'(logger\.info\(f"🛑 SL hit \(long\): last=\{last\} <= sl=\{self\.sl_price\}"\)\s*\n)(\s*)',
    r"""\1\2emit_event({
\2    "type": "sl",
\2    "symbol": cfg.symbol,
\2    "side": exit_side(cfg.side),
\2    "price": last,
\2    "qty": size,
\2})
\2""",
    src,
)
changes += ok

# 5) SL hit short — after log line
src, ok = sub_once(
    r'(logger\.info\(f"🛑 SL hit \(short\): last=\{last\} >= sl=\{self\.sl_price\}"\)\s*\n)(\s*)',
    r"""\1\2emit_event({
\2    "type": "sl",
\2    "symbol": cfg.symbol,
\2    "side": exit_side(cfg.side),
\2    "price": last,
\2    "qty": size,
\2})
\2""",
    src,
)
changes += ok

# 6) SL move to BE — after log line
src, ok = sub_once(
    r'(logger\.info\(f"🔁 Move SL to breakeven: sl=\{self\.sl_price\}"\)\s*\n)(\s*)',
    r"""\1\2emit_event({
\2    "type": "sl_move_be",
\2    "symbol": cfg.symbol,
\2    "price": avg,
\2})
\2""",
    src,
)
changes += ok

if changes:
    p.write_text(src, encoding="utf-8")
    print(f"Applied {changes} insertion(s).")
else:
    print("No changes applied (already patched or anchors not found).")
