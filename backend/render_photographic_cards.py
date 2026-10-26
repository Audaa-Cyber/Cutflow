import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

brain_dir = Path(r"C:\Users\Nimox\.gemini\antigravity-ide\brain\206fe215-e7b1-48e5-b78d-64f26fb7b2af")
out_dir = Path("frontend/assets/captions")
out_dir.mkdir(parents=True, exist_ok=True)

# Find generated portrait files
images = {
    "focus": list(brain_dir.glob("focus_creator_*.jpg"))[0],
    "linen": list(brain_dir.glob("linen_creator_*.jpg"))[0],
    "evo": list(brain_dir.glob("evo_creator_*.jpg"))[0],
    "align": list(brain_dir.glob("align_creator_*.jpg"))[0],
    "lift": list(brain_dir.glob("lift_creator_*.jpg"))[0],
    "stack": list(brain_dir.glob("stack_creator_*.jpg"))[0],
    "prime": list(brain_dir.glob("prime_creator_*.jpg"))[0],
    "impact": list(brain_dir.glob("impact_creator_*.jpg"))[0],
    "pop": list(brain_dir.glob("pop_creator_*.jpg"))[0],
}

# Map remaining presets to matching portraits
image_map = {
    "focus": images["focus"],
    "linen": images["linen"],
    "evo": images["evo"],
    "lift": images["lift"],
    "stack": images["stack"],
    "align": images["align"],
    "prime": images["prime"],
    "impact": images["impact"],
    "paper": images["linen"],
    "elevate": images["align"],
    "pop": images["pop"],
    "y2k": images["evo"],
    "chalk": images["prime"],
    "clean": images["focus"],
    "pulse": images["pop"],
    "glow": images["evo"],
    "hormozi": images["focus"],
    "karaoke": images["prime"],
}

# Typography configs for each preset
presets_config = {
    "focus": {
        "title": "Focus",
        "tag": "FLAGSHIP",
        "headline": "To Invest in",
        "active_badge": "Invest",
        "main_badge": "FOLLOWERS",
        "main_badge_bg": (26, 86, 219, 230), # Royal blue
        "accent": "#ffffff",
    },
    "linen": {
        "title": "Linen",
        "tag": "EDITORIAL",
        "serif": True,
        "headline": "WEAR your style",
        "sub": "dress like you mean it",
        "accent": "#f5d799",
    },
    "evo": {
        "title": "Evo",
        "tag": "FROSTED PILL",
        "pill": True,
        "headline": "If your money is",
        "active_word": "JUST SITTING",
        "accent": "#00f7ff",
    },
    "lift": {
        "title": "Lift",
        "tag": "EMERALD ARCH",
        "banner": "Your Team",
        "sub": "Your team only see 20% of the data",
        "accent": "#34eeb6",
    },
    "stack": {
        "title": "Stack",
        "tag": "BRUTALIST",
        "side": "SYS // 04.9",
        "bracket": "[Building a product]",
        "sub": "Or a solution?",
        "accent": "#00f0ff",
    },
    "align": {
        "title": "Align",
        "tag": "LETTERBOX",
        "letterbox": True,
        "headline": "L E A R N I N G",
        "dialogue": "IF THERE'S ONLY",
        "accent": "#ffffff",
    },
    "prime": {
        "title": "Prime",
        "tag": "VIRAL POP",
        "headline": "UNLEASH THE POTENTIAL",
        "active_word": "reach the unlimited",
        "accent": "#ffea00",
    },
    "impact": {
        "title": "Impact II",
        "tag": "BOLD PUNCH",
        "headline": '"JOURNEY"',
        "sub": "Solo travel in a remote island",
        "accent": "#ff793f",
    },
    "paper": {
        "title": "Paper II",
        "tag": "EDITORIAL PILL",
        "pill": True,
        "headline": "CHAPTER TWO",
        "active_word": "SMART WORK",
        "accent": "#ff9f43",
    },
    "elevate": {
        "title": "Elevate",
        "tag": "LUXURY",
        "serif": True,
        "headline": "Pure Perfection",
        "sub": "Timeless Elegance",
        "accent": "#e5c07b",
    },
    "pop": {
        "title": "Pop",
        "tag": "NEON BOUNCE",
        "headline": "LEARNING",
        "active_word": "Make your own music",
        "accent": "#ff38cd",
    },
    "y2k": {
        "title": "Y2K",
        "tag": "CYBER GLOW",
        "headline": "MATRIX LEVEL",
        "active_word": "CYBER GLOW",
        "accent": "#ff38cd",
    },
    "chalk": {
        "title": "Chalk",
        "tag": "HIGHLIGHTER",
        "headline": "KEY CONCEPT",
        "active_word": "HOW TO BUILD THIS",
        "accent": "#00d2d3",
    },
    "clean": {
        "title": "Clean",
        "tag": "SUBTITLE",
        "sub": "Clear broadcast delivery standard",
        "accent": "#54a0ff",
    },
    "pulse": {
        "title": "Pulse",
        "tag": "KARAOKE MINT",
        "headline": "RHYTHMIC FLOW",
        "active_word": "PULSE CADENCE",
        "accent": "#1dd1a1",
    },
    "glow": {
        "title": "Glow",
        "tag": "NEON HALO",
        "headline": "RADIANT BEAMS",
        "active_word": "NEON LIGHT",
        "accent": "#10ac84",
    },
    "hormozi": {
        "title": "Hormozi",
        "tag": "GOLD POP",
        "headline": "MILLION DOLLAR HABIT",
        "active_word": "MONEY PRINT",
        "accent": "#ff9f1a",
    },
    "karaoke": {
        "title": "Karaoke",
        "tag": "CUTFLOW LIME",
        "pill": True,
        "headline": "PERFECT TIMING",
        "active_word": "LIME PILL",
        "accent": "#d5ff5f",
    },
}

TARGET_W = 400
TARGET_H = 712

# Fonts fallback
def get_font(size, bold=True, serif=False):
    win_fonts = Path(r"C:\Windows\Fonts")
    if serif:
        font_path = win_fonts / ("georgiab.ttf" if bold else "georgia.ttf")
    else:
        font_path = win_fonts / ("arialbd.ttf" if bold else "arial.ttf")
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()

print("Rendering 18 high-definition photographic creator caption cards...")

for key, cfg in presets_config.items():
    src_img = Image.open(image_map[key]).convert("RGBA")
    
    # Scale & crop to 400x712
    src_w, src_h = src_img.size
    target_ratio = TARGET_W / TARGET_H
    src_ratio = src_w / src_h
    
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        src_img = src_img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        src_img = src_img.crop((0, top, src_w, top + new_h))
        
    img = src_img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    
    # Overlay canvas
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Bottom vignette gradient
    for y in range(TARGET_H - 180, TARGET_H):
        alpha = int(180 * ((y - (TARGET_H - 180)) / 180) ** 1.3)
        draw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))
        
    # Top status tag
    tag_text = cfg.get("tag", "PRESET")
    font_tag = get_font(10, bold=True)
    draw.rounded_rectangle([18, 18, 18 + draw.textlength(tag_text, font_tag) + 16, 38], radius=10, fill=(0, 0, 0, 160), outline=(255, 255, 255, 60), width=1)
    draw.text((26, 23), tag_text, font=font_tag, fill=cfg["accent"])
    
    # Custom Preset Elements
    if key == "focus":
        # Upper Hook Headline
        f_head = get_font(22, bold=True)
        draw.text((TARGET_W//2 - 70, 410), "To ", font=f_head, fill=(255, 255, 255, 255))
        draw.rounded_rectangle([TARGET_W//2 - 40, 404, TARGET_W//2 + 50, 442], radius=4, fill=(255, 255, 255, 255))
        draw.text((TARGET_W//2 - 34, 410), "Invest", font=f_head, fill=(0, 0, 0, 255))
        draw.text((TARGET_W//2 + 56, 410), "in", font=f_head, fill=(255, 255, 255, 255))
        # Big Blue Followers Banner
        draw.rounded_rectangle([24, 460, TARGET_W - 24, 540], radius=8, fill=(26, 86, 219, 240))
        f_main = get_font(34, bold=True)
        main_t = "FOLLOWERS"
        draw.text(((TARGET_W - draw.textlength(main_t, f_main))//2, 472), main_t, font=f_main, fill=(255, 255, 255, 255))
        f_sub = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength("Focus", f_sub))//2, 510), "Focus", font=f_sub, fill=(255, 255, 255, 220))
        
    elif key == "linen":
        f_top = get_font(38, bold=True, serif=True)
        t_top = "WEAR"
        draw.text(((TARGET_W - draw.textlength(t_top, f_top))//2, 100), t_top, font=f_top, fill=(245, 240, 230, 240))
        f_top_sub = get_font(24, bold=False, serif=True)
        t_top_sub = "your style"
        draw.text(((TARGET_W - draw.textlength(t_top_sub, f_top_sub))//2, 142), t_top_sub, font=f_top_sub, fill=(255, 255, 255, 220))
        
        # Bottom subtitle
        f_bot = get_font(18, bold=False, serif=True)
        t_bot = "dress like you mean it"
        draw.text(((TARGET_W - draw.textlength(t_bot, f_bot))//2, 480), t_bot, font=f_bot, fill=(255, 255, 255, 240))
        f_name = get_font(18, bold=True, serif=True)
        draw.text(((TARGET_W - draw.textlength("Linen", f_name))//2, 514), "Linen", font=f_name, fill=(245, 215, 153, 255))

    elif key == "evo":
        # Frosted glass pill with cyan
        f_pre = get_font(16, bold=False)
        t_pre = "If your money is"
        draw.text(((TARGET_W - draw.textlength(t_pre, f_pre))//2, 440), t_pre, font=f_pre, fill=(240, 240, 255, 240))
        
        draw.rounded_rectangle([34, 470, TARGET_W - 34, 530], radius=30, fill=(30, 24, 50, 180), outline=(0, 247, 255, 220), width=2)
        f_act = get_font(24, bold=True)
        t_act = "JUST SITTING"
        draw.text(((TARGET_W - draw.textlength(t_act, f_act))//2, 482), t_act, font=f_act, fill=(0, 247, 255, 255))
        f_name = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength("Evo", f_name))//2, 544), "Evo", font=f_name, fill=(255, 255, 255, 230))

    elif key == "lift":
        # Emerald curved banner
        draw.rounded_rectangle([20, 80, 220, 140], radius=16, fill=(52, 238, 182, 240))
        f_banner = get_font(28, bold=True, serif=True)
        draw.text((36, 92), "Your Team", font=f_banner, fill=(10, 30, 20, 255))
        
        # Bottom subtitle
        f_sub = get_font(16, bold=False)
        draw.text((30, 480), "Your", font=f_sub, fill=(255, 255, 255, 240))
        draw.rounded_rectangle([72, 478, 126, 502], radius=6, fill=(52, 238, 182, 220))
        draw.text((78, 480), "team", font=f_sub, fill=(10, 30, 20, 255))
        draw.text((134, 480), "only see", font=f_sub, fill=(255, 255, 255, 240))
        draw.text((30, 508), "20% of the data", font=f_sub, fill=(255, 255, 255, 220))
        f_name = get_font(20, bold=True)
        draw.text(((TARGET_W - draw.textlength("Lift", f_name))//2, 544), "Lift", font=f_name, fill=(52, 238, 182, 255))

    elif key == "stack":
        # Technical side text
        f_side = get_font(14, bold=True)
        draw.text((20, 140), "JUNE // 04.9", font=f_side, fill=(0, 240, 255, 200))
        
        # Monospace brackets
        f_brk = get_font(20, bold=True)
        draw.rounded_rectangle([30, 460, TARGET_W - 30, 510], radius=4, fill=(0, 0, 0, 220), outline=(0, 240, 255, 240), width=2)
        t_brk = "[Building a product]"
        draw.text(((TARGET_W - draw.textlength(t_brk, f_brk))//2, 472), t_brk, font=f_brk, fill=(0, 240, 255, 255))
        f_sub = get_font(16, bold=False)
        t_sub = "Or a solution?"
        draw.text(((TARGET_W - draw.textlength(t_sub, f_sub))//2, 518), t_sub, font=f_sub, fill=(255, 120, 100, 240))
        f_name = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength("Stack", f_name))//2, 546), "Stack", font=f_name, fill=(255, 255, 255, 230))

    elif key == "align":
        # Polaroid letterbox frame
        draw.rectangle([20, 60, TARGET_W - 20, TARGET_H - 100], outline=(255, 255, 255, 240), width=3)
        f_head = get_font(13, bold=True)
        t_head = "L  E  A  R  N  I  N  G"
        draw.text(((TARGET_W - draw.textlength(t_head, f_head))//2, 78), t_head, font=f_head, fill=(255, 255, 255, 240))
        
        draw.rectangle([60, 480, TARGET_W - 60, 520], fill=(255, 255, 255, 240))
        f_dia = get_font(13, bold=True)
        t_dia = "IF THERE'S ONLY"
        draw.text(((TARGET_W - draw.textlength(t_dia, f_dia))//2, 492), t_dia, font=f_dia, fill=(0, 0, 0, 255))
        f_name = get_font(20, bold=True)
        draw.text(((TARGET_W - draw.textlength("Align", f_name))//2, 544), "Align", font=f_name, fill=(255, 255, 255, 240))

    elif key == "prime":
        f_head = get_font(20, bold=True)
        t_head = "UNLEASH THE POTENTIAL"
        draw.text(((TARGET_W - draw.textlength(t_head, f_head))//2, 100), t_head, font=f_head, fill=(255, 255, 255, 240))
        
        f_act = get_font(26, bold=True)
        t_act = "reach the unlimited"
        # Shadow
        draw.text(((TARGET_W - draw.textlength(t_act, f_act))//2 + 2, 492), t_act, font=f_act, fill=(0, 0, 0, 255))
        draw.text(((TARGET_W - draw.textlength(t_act, f_act))//2, 490), t_act, font=f_act, fill=(255, 234, 0, 255))
        f_name = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength("Prime", f_name))//2, 544), "Prime", font=f_name, fill=(255, 255, 255, 230))

    elif key == "impact":
        f_main = get_font(34, bold=True)
        t_main = '"JOURNEY"'
        draw.text(((TARGET_W - draw.textlength(t_main, f_main))//2 + 2, 472), t_main, font=f_main, fill=(0, 0, 0, 255))
        draw.text(((TARGET_W - draw.textlength(t_main, f_main))//2, 470), t_main, font=f_main, fill=(255, 121, 63, 255))
        f_sub = get_font(14, bold=False)
        t_sub = "Solo travel in a remote island"
        draw.text(((TARGET_W - draw.textlength(t_sub, f_sub))//2, 514), t_sub, font=f_sub, fill=(240, 240, 240, 240))
        f_name = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength("Impact II", f_name))//2, 546), "Impact II", font=f_name, fill=(255, 255, 255, 230))

    elif key == "pop":
        f_top = get_font(32, bold=True)
        t_top = "LEARNING"
        draw.text(((TARGET_W - draw.textlength(t_top, f_top))//2 + 2, 102), t_top, font=f_top, fill=(0, 0, 0, 255))
        draw.text(((TARGET_W - draw.textlength(t_top, f_top))//2, 100), t_top, font=f_top, fill=(50, 255, 80, 255))
        
        # Speech bubble
        draw.rounded_rectangle([70, 475, TARGET_W - 70, 525], radius=16, fill=(40, 40, 40, 230), outline=(255, 255, 255, 120), width=2)
        f_sp = get_font(16, bold=True)
        draw.text((86, 488), "Make", font=f_sp, fill=(255, 255, 255, 255))
        draw.rounded_rectangle([134, 484, 180, 514], radius=4, fill=(255, 234, 0, 255))
        draw.text((138, 488), "your", font=f_sp, fill=(0, 0, 0, 255))
        draw.text((188, 488), "own music", font=f_sp, fill=(255, 255, 255, 255))
        f_name = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength("Pop", f_name))//2, 546), "Pop", font=f_name, fill=(255, 56, 205, 255))

    else:
        # Standard clean typography overlay for remaining presets
        headline = cfg.get("headline", cfg["title"].upper())
        act = cfg.get("active_word", cfg.get("sub", "DYNAMIC ACCENT"))
        f_head = get_font(18, bold=True, serif=cfg.get("serif", False))
        draw.text(((TARGET_W - draw.textlength(headline, f_head))//2, 120), headline, font=f_head, fill=(255, 255, 255, 240))
        
        if cfg.get("pill"):
            draw.rounded_rectangle([40, 475, TARGET_W - 40, 530], radius=28, fill=(15, 20, 25, 200), outline=ImageColor.getrgb(cfg["accent"]) if "ImageColor" in globals() else (255, 255, 255, 180), width=2)
            f_act = get_font(20, bold=True)
            draw.text(((TARGET_W - draw.textlength(act, f_act))//2, 488), act, font=f_act, fill=(255, 255, 255, 255))
        else:
            f_act = get_font(24, bold=True)
            draw.text(((TARGET_W - draw.textlength(act, f_act))//2 + 2, 488), act, font=f_act, fill=(0, 0, 0, 255))
            draw.text(((TARGET_W - draw.textlength(act, f_act))//2, 486), act, font=f_act, fill=(255, 255, 255, 255))
            
        f_name = get_font(18, bold=True)
        draw.text(((TARGET_W - draw.textlength(cfg["title"], f_name))//2, 546), cfg["title"], font=f_name, fill=(255, 255, 255, 230))

    # Composite & save as crisp, lightweight WebP
    final = Image.alpha_composite(img, overlay).convert("RGB")
    final.save(out_dir / f"{key}.webp", "WEBP", quality=92, method=6)

print(f"Successfully rendered 18 high-definition creator WebP cards to {out_dir}")
