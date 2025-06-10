from PIL import Image, ImageDraw, ImageFont
import requests
import os

def create_meme(file_url, text):
    # Download the image
    response = requests.get(file_url, stream=True)
    img = Image.open(response.raw).convert("RGBA")
    
    # Resize image to fit Telegram sticker requirements (512x512 max)
    img.thumbnail((512, 512))
    
    # Add text
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 30)  # Ensure arial.ttf is available or use default
    except:
        font = ImageFont.load_default()
    
    # Calculate text position
    text_width = draw.textlength(text, font=font)
    text_height = 30  # Approximate height
    img_width, img_height = img.size
    text_x = (img_width - text_width) / 2
    text_y = img_height - text_height - 10
    
    # Draw text with black outline/TEXT background
    draw.text((text_x, text_y), text, font=font, fill=(0, 0, 0))
    draw.rectangle((0, img_height - 40, img_width, img_height), fill=(255, 255, 255, 200))
    
    # Save as PNG (Telegram stickers support PNG)
    output_path = "meme.png"
    img.save(output_path, format="PNG")
    return output_path
