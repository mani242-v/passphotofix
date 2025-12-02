import os
import io
from flask import Flask, render_template_string, request, send_file
from PIL import Image
from supabase import create_client, Client

app = Flask(__name__)

# --- CONFIGURATION: Exam Dimensions & Sizes ---
EXAM_SPECS = {
    'ssc_photo': {'name': 'SSC Photo', 'w': 132, 'h': 170, 'min_kb': 20, 'max_kb': 50},
    'ssc_sig':   {'name': 'SSC Signature', 'w': 151, 'h': 75, 'min_kb': 10, 'max_kb': 20},
    'upsc_photo':{'name': 'UPSC Photo', 'w': 550, 'h': 550, 'min_kb': 20, 'max_kb': 300},
    'upsc_sig':  {'name': 'UPSC Signature', 'w': 350, 'h': 350, 'min_kb': 20, 'max_kb': 300},
    'ibps_photo':{'name': 'IBPS PO/Clerk Photo', 'w': 200, 'h': 230, 'min_kb': 20, 'max_kb': 50},
    'ibps_sig':  {'name': 'IBPS PO/Clerk Signature', 'w': 140, 'h': 60, 'min_kb': 10, 'max_kb': 20},
    'rrb_photo': {'name': 'RRB NTPC Photo', 'w': 320, 'h': 240, 'min_kb': 30, 'max_kb': 70},
}

# --- DATABASE SETUP (Supabase) ---
# We use environment variables so your keys are safe
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def compress_image(image, min_kb, max_kb):
    """
    Smart function to resize and compress image to fit specific KB size.
    """
    img_io = io.BytesIO()
    quality = 95
    
    # First save to see size
    image.save(img_io, format='JPEG', quality=quality)
    size_kb = img_io.tell() / 1024
    
    # If too big, lower quality until it fits
    while size_kb > max_kb and quality > 10:
        img_io = io.BytesIO()
        quality -= 5
        image.save(img_io, format='JPEG', quality=quality)
        size_kb = img_io.tell() / 1024
        
    img_io.seek(0)
    return img_io

# --- WEBSITE HTML ---
HTML_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PassPhotoFix - Free Govt Exam Photo Resizer</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f4f4f9; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        select, input[type=file], button { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }
        button { background: #28a745; color: white; border: none; cursor: pointer; font-size: 16px; }
        button:hover { background: #218838; }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>PassPhotoFix 🇮🇳</h1>
        <p style="text-align:center;">Resize photos for SSC, UPSC, IBPS instantly.</p>
        
        <form method="post" enctype="multipart/form-data">
            <label><strong>1. Select Exam Type:</strong></label>
            <select name="exam_type">
                {% for key, val in specs.items() %}
                <option value="{{ key }}">{{ val.name }} ({{val.min_kb}}-{{val.max_kb}} KB)</option>
                {% endfor %}
            </select>
            
            <label><strong>2. Upload Photo:</strong></label>
            <input type="file" name="file" required>
            
            <button type="submit">Convert & Download</button>
        </form>
    </div>
    <div class="footer">Built automatically. No data stored on server.</div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        exam_type = request.form['exam_type']
        
        if file and exam_type in EXAM_SPECS:
            spec = EXAM_SPECS[exam_type]
            
            # 1. Open Image
            img = Image.open(file.stream).convert('RGB')
            
            # 2. Resize
            img = img.resize((spec['w'], spec['h']), Image.Resampling.LANCZOS)
            
            # 3. Compress to target Size
            processed_img_io = compress_image(img, spec['min_kb'], spec['max_kb'])
            
            # 4. Log to Database (Optional: Track usage)
            if supabase:
                try:
                    supabase.table("usage_logs").insert({"exam": exam_type}).execute()
                except:
                    pass # Don't break app if DB fails

            return send_file(processed_img_io, mimetype='image/jpeg', as_attachment=True, download_name=f"{exam_type}_fixed.jpg")

    return render_template_string(HTML_TEMPLATE, specs=EXAM_SPECS)

if __name__ == '__main__':
    app.run(debug=True)