from PIL import Image, ImageDraw, ImageFont
import requests
import io
import textwrap
import os

def create_gradient(width, height, start_color, end_color):
    base = Image.new('RGB', (width, height), start_color)
    top = Image.new('RGB', (width, height), end_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

def safe_load_font(size):
    """Try to load a nice font, fallback to default"""
    possible_fonts = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arial.ttf"
    ]
    for font_path in possible_fonts:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
    return ImageFont.load_default()

def generate_social_card(recommendations: list, header_text: str = "AI Recommendations", prompt_desc: str = "") -> io.BytesIO:
    """
    Generate a social share image card from recommendations.
    Returns bytes buffer of PNG.
    """
    # Dimensions
    W = 1080
    start_y = 350
    item_height = 220
    spacing = 30
    
    num_items = min(len(recommendations), 10) 
    
    if num_items <= 3:
        H = 1080 
    else:
        H = start_y + (num_items * (item_height + spacing)) + 100
        
    # Aesthetic Palette (Cyberpunk / Modern Dark)
    bg_start = (25, 20, 45)   # Deep Purple
    bg_end = (10, 10, 15)     # Almost Black
    text_main = (255, 255, 255)
    text_dim = (180, 180, 200)
    accent = (0, 240, 255)    # Cyan Neon
    
    # Glassmorphism Card Style (White at 10% opacity)
    card_fill = (255, 255, 255, 25)
    card_outline = (255, 255, 255, 40)

    # Base Image (Gradient)
    img = create_gradient(W, H, bg_start, bg_end).convert("RGBA")
    
    # Create overlay for glass effect elements
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Fonts
    title_font = safe_load_font(70)
    subtitle_font = safe_load_font(30)
    rank_font = safe_load_font(60)
    item_title_font = safe_load_font(45)
    meta_font = safe_load_font(28)
    
    # Header
    draw.text((60, 60), "AI Media Recommender", font=subtitle_font, fill=accent)
    
    wrapped_header = textwrap.fill(header_text, width=22)
    draw.text((60, 110), wrapped_header, font=title_font, fill=text_main)

    # Optional prompt/description below header
    if prompt_desc:
        wrapped_prompt = textwrap.fill(prompt_desc, width=40)
        draw.text((60, 190), wrapped_prompt, font=subtitle_font, fill=text_dim)

    # Draw Items
    for i, rec in enumerate(recommendations[:num_items]):
        y = start_y + (i * (item_height + spacing))
        
        # Rounded Glass Card background
        draw.rounded_rectangle(
            [40, y, W-40, y+item_height], 
            radius=30, 
            fill=card_fill, 
            outline=card_outline, 
            width=2
        )

        # Load cover image (image_url or cover_url) and paste as portrait overlay on the left side of the card
        cover_url = rec.get('image_url') or rec.get('cover_url')
        if cover_url:
            try:
                resp = requests.get(cover_url, timeout=5)
                resp.raise_for_status()
                cover_img = Image.open(io.BytesIO(resp.content)).convert('RGBA')
                # Resize to a portrait size (narrow width, full card height with padding)
                portrait_w = 80
                portrait_h = item_height - 20
                cover_resized = cover_img.resize((portrait_w, portrait_h))
                # Apply slight opacity for glass effect
                overlay_alpha = Image.new('RGBA', cover_resized.size, (255,255,255,30))
                cover_resized = Image.alpha_composite(cover_resized, overlay_alpha)
                # Paste onto overlay; position so it overlaps the rank circle
                overlay.paste(cover_resized, (40, y + 10), cover_resized)
            except Exception:
                pass
        
        # Rank Circle
        # draw.ellipse([70, y+60, 170, y+160], fill=(0,0,0,50))
        draw.text((80, y+75), f"{i+1}", font=rank_font, fill=accent)
        
        # Determine Title Layout
        title = rec.get('title', 'Unknown')
        # Truncate title if too long to prevent overlap
        if len(title) > 55:
            title = title[:52] + "..."
        wrapped_title = textwrap.fill(title, width=28)
        lines = wrapped_title.count('\n') + 1
        
        # Title Text
        draw.multiline_text((200, y+45), wrapped_title, font=item_title_font, fill=text_main, spacing=8)
        
        # Metadata
        meta = []
        if rec.get('rating'): meta.append(f"{rec['rating']}")
        if rec.get('type'): meta.append(rec['type'].upper())
        if rec.get('year'): meta.append(str(rec['year']))
        # Add short description / why_recommended if space permits

        meta_str = "  |  ".join(meta)
        
        # Adjust meta Y position to stick to bottom of card
        # Fixed position from bottom of card
        meta_y = y + item_height - 60
            
        draw.text((200, meta_y), meta_str, font=meta_font, fill=text_dim)
        
    # Footer
    #draw.text((W//2, H-60), "Generated with Movie_Book_CrewAI", font=subtitle_font, fill=text_dim, anchor="ms")
    
    # Composite layers (background gradient + overlay with cards & covers)
    out = Image.alpha_composite(img, overlay)
    
    # To Buffer
    buf = io.BytesIO()
    out.save(buf, format='PNG')
    buf.seek(0)
    return buf
