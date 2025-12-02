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

# --- DATABASE SETUP ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase Error: {e}")

def compress_image(image, min_kb, max_kb):
    img_io = io.BytesIO()
    quality = 95
    image.save(img_io, format='JPEG', quality=quality)
    size_kb = img_io.tell() / 1024
    
    while size_kb > max_kb and quality > 10:
        img_io = io.BytesIO()
        quality -= 5
        image.save(img_io, format='JPEG', quality=quality)
        size_kb = img_io.tell() / 1024
        
    img_io.seek(0)
    return img_io

# --- UPGRADED HTML WITH LOADER ---
HTML_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PassPhotoFix - Free Govt Exam Photo Resizer</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f0f2f5; }
        .container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 30px; }
        
        select, input[type=file] { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
        
        button { 
            width: 100%; padding: 14px; margin-top: 20px; 
            background: #007bff; color: white; border: none; border-radius: 6px; 
            cursor: pointer; font-size: 16px; font-weight: bold; transition: background 0.3s;
        }
        button:hover { background: #0056b3; }
        
        /* --- LOADER CSS --- */
        .loader-container { display: none; margin-top: 20px; }
        .loader {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 30px; height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .footer { margin-top: 30px; font-size: 12px; color: #888; }
    </style>
    
    <script>
        function showLoader() {
            var fileInput = document.querySelector('input[type="file"]');
            if (fileInput.files.length === 0) {
                return; // Don't show loader if no file selected
            }
            // Show Loader and change button text
            document.getElementById('loader-box').style.display = 'block';
            var btn = document.querySelector('button');
            btn.innerText = 'Processing... Please Wait';
            btn.style.opacity = '0.7';
            btn.style.cursor = 'not-allowed';
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>PassPhotoFix 🇮🇳</h1>
        <p>Resize & Compress photos for SSC, UPSC, IBPS in 1 click.</p>
        
        <form method="post" enctype="multipart/form-data" onsubmit="showLoader()">
            <div style="text-align: left; font-weight: bold; margin-bottom: 5px;">1. Select Exam Type:</div>
            <select name="exam_type">
                {% for key, val in specs.items() %}
                <option value="{{ key }}">{{ val.name }} ({{val.min_kb}}-{{val.max_kb}} KB)</option>
                {% endfor %}
            </select>
            
            <div style="text-align: left; font-weight: bold; margin-bottom: 5px; margin-top: 15px;">2. Upload Photo:</div>
            <input type="file" name="file" required accept="image/*">
            
            <button type="submit">Convert & Download</button>
            
            <div id="loader-box" class="loader-container">
                <div class="loader"></div>
                <div style="margin-top: 10px; color: #555;">Resizing & Compressing...</div>
            </div>
        </form>
    </div>
    <div class="footer">
        🔒 Privacy Safe: Photos are processed in RAM and never stored.<br>
        Built with Python & Flask.
    </div>
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
            try:
                img = Image.open(file.stream).convert('RGB')
                img = img.resize((spec['w'], spec['h']), Image.Resampling.LANCZOS)
                processed_img_io = compress_image(img, spec['min_kb'], spec['max_kb'])
                
                # Log to DB (Silent fail if DB error)
                if supabase:
                    try:
                        supabase.table("usage_logs").insert({"exam": exam_type}).execute()
                    except:
                        pass 

                return send_file(processed_img_io, mimetype='image/jpeg', as_attachment=True, download_name=f"{exam_type}_fixed.jpg")
            except Exception as e:
                return f"Error processing image: {str(e)}"

    return render_template_string(HTML_TEMPLATE, specs=EXAM_SPECS)

if __name__ == '__main__':
    app.run(debug=True)
