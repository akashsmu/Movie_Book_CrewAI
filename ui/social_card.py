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
    Style: Netflix-like vertical posters in a grid.
    Returns bytes buffer of PNG.
    """
    # Dimensions
    W = 1080
    
    # Layout Config
    cols = 2
    card_gap = 40
    side_padding = 60
    
    # Calculate card size (Aspect Ratio 2:3)
    available_w = W - (side_padding * 2) - ((cols - 1) * card_gap)
    card_w = int(available_w / cols)
    card_h = int(card_w * 1.5)
    
    num_items = min(len(recommendations), 8) # Limit to 8 to match UI slider maximum
    import math
    rows = math.ceil(num_items / cols)
    
    header_height = 400
    if prompt_desc:
        header_height = 500
        
    H = header_height + (rows * (card_h + card_gap)) + 100
        
    # Aesthetic Palette
    bg_start = (20, 20, 20)
    bg_end = (5, 5, 5)
    text_main = (255, 255, 255)
    text_dim = (200, 200, 200)
    accent = (229, 9, 20)    # Netflix Red-ish
    
    # Base Image (Gradient)
    img = create_gradient(W, H, bg_start, bg_end).convert("RGBA")
    
    # Create overlay for elements
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Fonts
    title_font = safe_load_font(70)
    subtitle_font = safe_load_font(30)
    card_title_font = safe_load_font(40)
    meta_font = safe_load_font(24)
    rank_font = safe_load_font(50)
    
    # Header
    draw.text((60, 60), "AI Media Recommender", font=subtitle_font, fill=accent)
    
    wrapped_header = textwrap.fill(header_text, width=22)
    draw.text((60, 110), wrapped_header, font=title_font, fill=text_main)

    # Optional prompt/description below header
    if prompt_desc:
        prompt_desc = prompt_desc.capitalize()
        wrapped_prompt = textwrap.fill(prompt_desc, width=45)
        draw.text((60, 200), wrapped_prompt, font=subtitle_font, fill=text_dim)

    # Helper for vertical gradient (text protection)
    def create_vertical_gradient(w, h):
        base = Image.new('RGBA', (w, h), (0,0,0,0))
        for y in range(h):
            alpha = int(255 * (y / h))
            # ramping up opacity faster at the end
            alpha = int(alpha * 1.2)
            if alpha > 255: alpha = 255
            for x in range(w):
                base.putpixel((x, y), (0, 0, 0, alpha))
        return base

    # Pre-compute gradient for cards
    grad_h = int(card_h * 0.5)
    text_protection_grad = create_vertical_gradient(card_w, grad_h)

    # Draw Items (Grid)
    for i, rec in enumerate(recommendations[:num_items]):
        row = i // cols
        col = i % cols
        
        x = side_padding + (col * (card_w + card_gap))
        y = header_height + (row * (card_h + card_gap))
        
        # 1. Card Base (Placeholder if no image)
        draw.rounded_rectangle([x, y, x+card_w, y+card_h], radius=20, fill=(40,40,40,255))
        
        # 2. Cover Image Background
        cover_url = rec.get('image_url') or rec.get('cover_url')
        if cover_url:
            try:
                resp = requests.get(cover_url, timeout=5)
                resp.raise_for_status()
                cover_img = Image.open(io.BytesIO(resp.content)).convert('RGBA')
                
                # Aspect Fill
                img_ratio = cover_img.width / cover_img.height
                target_ratio = card_w / card_h
                
                if img_ratio > target_ratio:
                    # Image is wider, crop sides
                    new_h = card_h
                    new_w = int(new_h * img_ratio)
                else:
                    # Image is taller, crop top/bottom
                    new_w = card_w
                    new_h = int(new_w / img_ratio)
                    
                cover_resized = cover_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Center crop
                left = (new_w - card_w) / 2
                top = (new_h - card_h) / 2
                cover_cropped = cover_resized.crop((left, top, left + card_w, top + card_h))
                
                # Create a rounded mask
                mask = Image.new("L", (card_w, card_h), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, card_w, card_h], radius=20, fill=255)
                
                # Paste cover with mask
                # Need to paste onto a temp image first to apply mask composition if needed
                # But simple paste with mask works on existing RGBA overlay
                # Actually, 'overlay' is transparent. pasting masked image on it:
                overlay.paste(cover_cropped, (x, y), mask)
                
            except Exception:
                pass
        
        # 3. Gradient Overlay (Bottom) for Text
        grad_mask = Image.new("L", (card_w, grad_h), 0)
        grad_mask_draw = ImageDraw.Draw(grad_mask)
        grad_mask_draw.polygon([(0,0), (card_w,0), (card_w, grad_h), (0, grad_h)], fill=255)
        overlay.paste(text_protection_grad, (x, y + card_h - grad_h), text_protection_grad)

        # 4. Rank Badge (Top Left)
        draw.rounded_rectangle([x, y, x+60, y+60], radius=15, fill=accent)
        draw.text((x+20, y+5), f"{i+1}", font=rank_font, fill=text_main)

        # 5. Text Details (Vertical Stack)
        content_margin = 25
        text_bottom_y = y + card_h - content_margin
        
        # Meta line (bottom-most)
        meta = []
        if rec.get('year'): meta.append(str(rec['year']))
        if rec.get('rating'): meta.append(f"{rec['rating']}")
        if rec.get('type'): meta.append(rec['type'].upper())
        meta_str = " • ".join(meta)
        
        draw.text((x + content_margin, text_bottom_y - 30), meta_str, font=meta_font, fill=text_dim)
        
        # Title (Above meta)
        title = rec.get('title', 'Unknown')
        wrapped_title = textwrap.fill(title, width=20) # Narrower for portrait card
        
        # Calculate height of title block to position it above meta
        bbox = draw.multiline_textbbox((0,0), wrapped_title, font=card_title_font)
        title_h = bbox[3] - bbox[1]
        
        title_y = text_bottom_y - 30 - title_h - 15
        draw.multiline_text((x + content_margin, title_y), wrapped_title, font=card_title_font, fill=text_main, spacing=4)

    # Footer
    draw.text((W//2, H-50), "Generated with Movie_Book_CrewAI", font=subtitle_font, fill=text_dim, anchor="ms")
    
    # Composite layers
    out = Image.alpha_composite(img, overlay)
    
    # To Buffer
    buf = io.BytesIO()
    out.save(buf, format='PNG')
    buf.seek(0)
    return buf
