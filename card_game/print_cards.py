"""
print_cards.py — Windfall card print sheet generator.
Reads cards.json and outputs 9-up print sheets (one sheet per card type).

Card formats:
  poker  — 822×1122 px  (2.74" × 3.74" @ 300 DPI, standard poker with bleed)
  mini   — 690×1020 px  (2.30" × 3.40" @ 300 DPI, smaller playtest size)

Usage:
    pip install Pillow
    python print_cards.py                          # poker size only
    python print_cards.py --size mini              # mini size only
    python print_cards.py --size all               # both sizes
    python print_cards.py --individual             # also save individual card PNGs
"""

import json
import os
import sys
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Card Format Definitions ──────────────────────────────────────────────────

DPI    = 300
SHEET_W = 2550   # 8.5 in × 300 dpi
SHEET_H = 3300   # 11.0 in × 300 dpi
COLS   = 3
ROWS   = 3
CARDS_PER_SHEET = COLS * ROWS

# Each format: physical size @ 300 DPI, bleed in px, label for filenames
CARD_FORMATS = {
    "poker": {
        "label":   "poker",
        "desc":    "2.74\" × 3.74\" (poker card with bleed)",
        "card_w":  822,   # 2.74 in
        "card_h":  1122,  # 3.74 in
        "bleed":   27,    # 0.09 in bleed each side
        "corner":  28,
        "padding": 30,
        "fonts": {        # font sizes scale with card size
            "title":    88,
            "subtitle": 52,
            "label":    44,
            "body":     40,
            "small":    32,
            "tiny":     28,
        },
    },
    "mini": {
        "label":   "mini",
        "desc":    "2.30\" × 3.40\" (mini playtest size)",
        "card_w":  690,   # 2.30 in
        "card_h":  1020,  # 3.40 in
        "bleed":   18,    # 0.06 in bleed each side
        "corner":  22,
        "padding": 22,
        "fonts": {
            "title":    68,
            "subtitle": 40,
            "label":    34,
            "body":     30,
            "small":    24,
            "tiny":     22,
        },
    },
}

# ─── Colorblind-safe palette ──────────────────────────────────────────────────

CLR_BG       = (13,  17,  23)
CLR_CARD_BG  = (22,  30,  42)
CLR_BORDER   = (48,  61,  78)
CLR_TEXT     = (230, 237, 243)
CLR_TEXT_DIM = (125, 139, 156)
CLR_REACT    = (86,  180, 233)   # sky blue  — colorblind safe
CLR_STOCK    = (230, 159,   0)   # amber     — colorblind safe
CLR_DIVIDER  = (40,  52,  68)
CLR_NAME_BG  = (28,  38,  52)

# ─── Font loading ─────────────────────────────────────────────────────────────

def load_fonts(sizes: dict) -> dict:
    regular = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    bold = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    # Segoe UI Symbol supports \u26a1 \u2726 \u25c6 \u25ce and most Misc Symbols
    symbol = [
        "C:/Windows/Fonts/seguisym.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    def first(paths, size):
        for p in paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    return {
        "title":     first(bold,    sizes["title"]),
        "subtitle":  first(bold,    sizes["subtitle"]),
        "label":     first(bold,    sizes["label"]),
        "body":      first(regular, sizes["body"]),
        "small":     first(regular, sizes["small"]),
        "tiny":      first(regular, sizes["tiny"]),
        # Symbol font at two sizes for glyphs (⚡ ✦ ◆ ◎)
        "sym_label": first(symbol,  sizes["label"]),
        "sym_tiny":  first(symbol,  sizes["tiny"]),
    }

# ─── Drawing helpers ──────────────────────────────────────────────────────────

def rrect(draw, xy, r, fill=None, outline=None, width=2):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

def wrap_text(draw, text, x, y, max_w, font, fill, gap=4):
    """Word-wrap text, return y after last line."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bb = draw.textbbox((0, 0), line, font=font)
        y += (bb[3] - bb[1]) + gap
    return y

def cost_badge(draw, x, y, text, bg, fg, sym_font, text_font):
    """Draw a cost badge with \u25c6 symbol glyph. Returns total width used."""
    sym   = "\u25c6 "   # \u25c6 BLACK DIAMOND
    ph, pv = 12, 4
    sym_w = int(draw.textlength(sym,  font=sym_font))
    txt_w = int(draw.textlength(text, font=text_font))
    pw = sym_w + txt_w + 2 * ph
    bh = int(text_font.size * 1.5)
    draw.rounded_rectangle([x, y, x + pw, y + bh], radius=8, fill=bg, outline=fg, width=2)
    draw.text((x + ph, y + pv), sym,  font=sym_font,  fill=fg)
    draw.text((x + ph + sym_w, y + pv), text, font=text_font, fill=fg)
    return pw + 8

def draw_sym_label(draw, x, y, sym, label, sym_font, text_font, fill):
    """Draw a symbol glyph + bold text side by side."""
    draw.text((x, y), sym, font=sym_font, fill=fill)
    sym_w = int(draw.textlength(sym, font=sym_font))
    draw.text((x + sym_w + 2, y), label, font=text_font, fill=fill)

def tags_to_cost(tags: list, section_type: str):
    """Return a cost string for React, or None for Stock (no badge shown)."""
    if section_type == "React":
        parts = []
        if "Pitch" in tags:
            parts.append("Pitch 1")
        if "Burn" in tags:
            parts.append("Burn 1")
        return " + ".join(parts) if parts else "Free"
    return None  # Stock abilities show no cost badge

# Target requirement labels (plain text — symbol drawn separately by draw_targets)
TARGET_LABELS = {
    "PLAYER":         "Player",
    "OPPONENT_STOCK": "Opp. Stock",
    "ANY_STOCK":      "Any Stock",
    "POT_CARD":       "Stack Card",
    "GRAVEYARD":      "Graveyard",
}

def draw_targets(draw, x, section_bottom_y, requirements: list,
                fg, text_font, sym_font, pad_bottom=10):
    """Draw \u25ce-prefixed target badges pinned to the bottom of a section div."""
    if not requirements:
        return
    sym   = "\u25ce "   # \u25ce BULLSEYE
    sym_w = int(draw.textlength(sym, font=sym_font))
    bh    = int(text_font.size * 1.5)
    ph, pv = 8, 3
    gap   = 6
    ty    = section_bottom_y - bh - pad_bottom
    cx    = x
    for req in requirements:
        label = TARGET_LABELS.get(req, req.replace("_", " ").title())
        tw    = int(draw.textlength(label, font=text_font))
        pw    = sym_w + tw + 2 * ph
        draw.rounded_rectangle([cx, ty, cx + pw, ty + bh], radius=6,
                               fill=None, outline=fg, width=1)
        draw.text((cx + ph, ty + pv),          sym,   font=sym_font,  fill=fg)
        draw.text((cx + ph + sym_w, ty + pv),  label, font=text_font, fill=fg)
        cx += pw + gap

# ─── Card rendering ───────────────────────────────────────────────────────────

def render_card(card_data: dict, abilities: dict, fmt: dict, fonts: dict) -> Image.Image:
    """Render one card image at the dimensions specified by fmt."""
    W, H      = fmt["card_w"], fmt["card_h"]
    BLEED     = fmt["bleed"]
    CORNER    = fmt["corner"]
    PAD       = fmt["padding"]

    # Safe area
    SX, SY    = BLEED, BLEED
    SW, SH    = W - 2 * BLEED, H - 2 * BLEED
    CX        = SX + PAD          # content left
    CW        = SW - 2 * PAD      # content width

    react_name = card_data["react_name"]
    stock_name = card_data["stock_name"]

    ra = abilities[react_name]
    sa = abilities[stock_name]

    img  = Image.new("RGB", (W, H), CLR_BG)
    draw = ImageDraw.Draw(img)

    # Card background
    rrect(draw, [SX, SY, SX + SW, SY + SH], CORNER,
          fill=CLR_CARD_BG, outline=CLR_BORDER, width=2)

    # Bleed guide
    draw.rectangle([BLEED, BLEED, W - BLEED, H - BLEED],
                   outline=(40, 30, 30), width=1)

    # ── Title bar ──
    title_h = int(fonts["title"].size * 1.8)
    rrect(draw, [SX, SY, SX + SW, SY + title_h], CORNER, fill=CLR_NAME_BG)
    draw.text((CX, SY + int(title_h * 0.18)),
              f"{react_name} / {stock_name}",
              font=fonts["title"], fill=CLR_TEXT)

    wm = "WINDFALL"
    wm_w = draw.textlength(wm, font=fonts["tiny"])
    draw.text((SX + SW - int(wm_w) - 4, SY + 3), wm,
              font=fonts["tiny"], fill=CLR_BORDER)

    cy = SY + title_h + 6

    # ── Art area placeholder ──
    art_h = int(SH * 0.12)   # 12% of safe height — smaller to give sections more room
    draw.rectangle([SX, cy, SX + SW, cy + art_h],
                   fill=(18, 24, 34), outline=CLR_DIVIDER, width=1)
    for i in range(0, SW + art_h, 28):
        x1 = SX + max(0, i - art_h); y1 = cy + min(art_h, i)
        x2 = SX + min(SW, i);        y2 = cy + max(0, i - SW)
        draw.line([(x1, y1), (x2, y2)], fill=(30, 38, 50), width=1)
    lbl = "[ ART AREA ]"
    lw  = draw.textlength(lbl, font=fonts["small"])
    draw.text((SX + (SW - lw) // 2, cy + art_h // 2 - int(fonts["small"].size // 2)),
              lbl, font=fonts["small"], fill=CLR_DIVIDER)
    cy += art_h + 8

    # ── Split remaining space equally for REACT + STOCK ──
    bot_h   = int(fonts["tiny"].size * 2.2)  # bottom bar
    remain  = (SY + SH) - cy - bot_h - 4
    sec_h   = remain // 2 - 5
    sp      = 10   # section inner top padding

    # ── REACT section ──
    rrect(draw, [SX, cy, SX + SW, cy + sec_h], 10,
          fill=(20, 30, 44), outline=CLR_REACT, width=2)
    ny = cy + sp
    draw.text((CX, ny), react_name, font=fonts["subtitle"], fill=CLR_TEXT)
    react_cost = tags_to_cost(ra.get("tags", []), "React")
    if react_cost:
        badge_x = CX + int(draw.textlength(react_name, font=fonts["subtitle"])) + 12
        cost_badge(draw, badge_x, ny + 2, react_cost, (20, 30, 44), CLR_REACT, fonts["sym_tiny"], fonts["tiny"])
    ny += int(fonts["subtitle"].size * 1.4)
    draw.text((CX, ny), "⚡ REACT", font=fonts["label"], fill=CLR_REACT)
    dy = ny + int(fonts["label"].size * 1.5)
    dy = wrap_text(draw, ra.get("description", ""), CX, dy, CW,
                   fonts["body"], CLR_TEXT, gap=4)
    draw_targets(draw, CX, dy + 4, ra.get("target_requirements", []),
                 CLR_REACT, fonts["tiny"], fonts["sym_tiny"])

    cy += sec_h + 6

    # ── STOCK section ──
    rrect(draw, [SX, cy, SX + SW, cy + sec_h], 10,
          fill=(32, 24, 10), outline=CLR_STOCK, width=2)
    ny = cy + sp
    draw.text((CX, ny), stock_name, font=fonts["subtitle"], fill=CLR_TEXT)
    # No cost badge for Stock
    ny += int(fonts["subtitle"].size * 1.4)
    draw.text((CX, ny), "✦ STOCK", font=fonts["label"], fill=CLR_STOCK)
    dy = ny + int(fonts["label"].size * 1.5)
    dy = wrap_text(draw, sa.get("description", ""), CX, dy, CW,
                   fonts["body"], CLR_TEXT, gap=4)
    draw_targets(draw, CX, cy + sec_h,
                 sa.get("target_requirements", []),
                 CLR_STOCK, fonts["tiny"], fonts["sym_tiny"])

    # ── Bottom bar ──
    by = H - BLEED - bot_h
    draw.line([(SX + 8, by - 3), (SX + SW - 8, by - 3)],
              fill=CLR_DIVIDER, width=1)
    draw.text((CX, by),
              f"×{card_data['count']} in deck  ·  {fmt['label'].upper()}",
              font=fonts["tiny"], fill=CLR_TEXT_DIM)

    return img

# ─── Sheet builder ────────────────────────────────────────────────────────────

def build_sheet(card_img: Image.Image, fmt: dict) -> Image.Image:
    """Return a 9-up 8.5×11 sheet of one card type."""
    W, H = fmt["card_w"], fmt["card_h"]
    cell_w = SHEET_W // COLS
    cell_h = SHEET_H // ROWS
    scale  = min(cell_w / W, cell_h / H)
    pw     = int(W * scale)
    ph     = int(H * scale)
    scaled = card_img.resize((pw, ph), Image.LANCZOS)

    sheet  = Image.new("RGB", (SHEET_W, SHEET_H), (240, 240, 235))
    draw   = ImageDraw.Draw(sheet)

    # Cut guides
    for r in range(1, ROWS):
        draw.line([(0, r * cell_h), (SHEET_W, r * cell_h)],
                  fill=(180, 180, 180), width=1)
    for c in range(1, COLS):
        draw.line([(c * cell_w, 0), (c * cell_w, SHEET_H)],
                  fill=(180, 180, 180), width=1)

    for idx in range(CARDS_PER_SHEET):
        row, col = idx // COLS, idx % COLS
        px = col * cell_w + (cell_w - pw) // 2
        py = row * cell_h + (cell_h - ph) // 2
        sheet.paste(scaled, (px, py))

    return sheet

def build_sampler_sheet(card_images: list, fmt: dict) -> Image.Image:
    """Return a sheet with 1 of each unique card type (up to 9 slots)."""
    W, H = fmt["card_w"], fmt["card_h"]
    cell_w = SHEET_W // COLS
    cell_h = SHEET_H // ROWS
    scale  = min(cell_w / W, cell_h / H)
    pw     = int(W * scale)
    ph     = int(H * scale)

    sheet  = Image.new("RGB", (SHEET_W, SHEET_H), (240, 240, 235))
    draw   = ImageDraw.Draw(sheet)

    # Cut guides only around filled cells
    for r in range(1, ROWS):
        draw.line([(0, r * cell_h), (SHEET_W, r * cell_h)],
                  fill=(180, 180, 180), width=1)
    for c in range(1, COLS):
        draw.line([(c * cell_w, 0), (c * cell_w, SHEET_H)],
                  fill=(180, 180, 180), width=1)

    for idx, card_img in enumerate(card_images[:CARDS_PER_SHEET]):
        scaled = card_img.resize((pw, ph), Image.LANCZOS)
        row, col = idx // COLS, idx % COLS
        px = col * cell_w + (cell_w - pw) // 2
        py = row * cell_h + (cell_h - ph) // 2
        sheet.paste(scaled, (px, py))

    return sheet

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate Windfall 9-up print sheets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sizes:
  poker  - 2.74\" × 3.74\" @ 300 DPI (standard poker card with bleed)  [default]
  mini   - 2.30\" × 3.40\" @ 300 DPI (smaller playtest size)
  all    - generate both sizes
        """,
    )
    parser.add_argument("--cards-json", default="cards.json")
    parser.add_argument("--output",     default="./print_output")
    parser.add_argument("--size",       default="poker",
                        choices=["poker", "mini", "all"],
                        help="Card format to generate (default: poker)")
    parser.add_argument("--individual", action="store_true",
                        help="Also save individual card PNG files")
    parser.add_argument("--sampler", action="store_true",
                        help="Also output a sampler sheet with 1 of each card")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading cards from {args.cards_json}...")
    with open(args.cards_json, "r") as f:
        data = json.load(f)
    abilities = data["abilities"]
    roster    = data["roster"]

    # Determine which formats to run
    if args.size == "all":
        formats_to_run = list(CARD_FORMATS.values())
    else:
        formats_to_run = [CARD_FORMATS[args.size]]

    for fmt in formats_to_run:
        lbl = fmt["label"]
        print(f"\n{'─'*50}")
        print(f"  Format: {lbl.upper()}  ({fmt['desc']})")
        print(f"{'─'*50}")

        fonts = load_fonts(fmt["fonts"])
        all_card_images = []

        for card_def in roster:
            rn = card_def["react_name"]
            sn = card_def["stock_name"]
            name      = f"{rn}/{sn}"
            safe_name = f"{rn}_{sn}"

            print(f"  Rendering: {name}")
            card_img = render_card(card_def, abilities, fmt, fonts)

            if args.individual:
                ind_path = output_dir / f"{safe_name}_{lbl}.png"
                card_img.save(ind_path, dpi=(DPI, DPI))
                print(f"    → Individual: {ind_path.name}")

            sheet     = build_sheet(card_img, fmt)
            sheet_path = output_dir / f"{safe_name}_{lbl}_sheet.png"
            sheet.save(sheet_path, dpi=(DPI, DPI))
            print(f"    -> Sheet:      {sheet_path.name}")

            # Collect for sampler
            all_card_images.append(card_img)

        if args.sampler:
            sampler = build_sampler_sheet(all_card_images, fmt)
            sampler_path = output_dir / f"sampler_{lbl}.png"
            sampler.save(sampler_path, dpi=(DPI, DPI))
            print(f"\n  -> Sampler:    {sampler_path.name}")

    print(f"\n✓ Done. Output in: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
