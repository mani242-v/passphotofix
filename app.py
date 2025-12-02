import os
import io
import cv2
import numpy as np
from flask import Flask, render_template_string, request, send_file
from PIL import Image
from supabase import create_client

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
    except:
        pass

def smart_resize_with_face_detection(pil_image, target_w, target_h):
    """
    PRO LOGIC:
    1. Tries to find a face using OpenCV.
    2. If found -> Crops around the face center.
    3. If NOT found -> Uses Top-Priority cropping.
    """
    # Convert PIL Image to OpenCV format (numpy array)
    img_np = np.array(pil_image)
    
    # Convert to Grayscale (needed for detection)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # Load Face Detector (Haar Cascade - built into OpenCV)
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    # Detect faces
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    
    # Calculate Target Aspect Ratio
    target_ratio = target_w / target_h
    img_w, img_h = pil_image.size
    img_ratio = img_w / img_h
    
    # Variables to determine crop box
    crop_x, crop_y = 0, 0
    crop_w, crop_h = img_w, img_h

    if len(faces) > 0:
        # --- FACE DETECTED: Center on the face ---
        (fx, fy, fw, fh) = faces[0] # Get first face
        face_center_x = fx + (fw // 2)
        face_center_y = fy + (fh // 2)
        
        if img_ratio > target_ratio:
            # Too Wide: Crop sides relative to face center
            new_width = int(target_ratio * img_h)
            crop_x = face_center_x - (new_width // 2)
            # Boundary checks
            if crop_x < 0: crop_x = 0
            if crop_x + new_width > img_w: crop_x = img_w - new_width
            crop_w = new_width
            crop_h = img_h
        else:
            # Too Tall: Crop top/bottom relative to face center
            new_height = int(img_w / target_ratio)
            crop_y = face_center_y - (new_height // 2)
            # Boundary checks
            if crop_y < 0: crop_y = 0
            if crop_y + new_height > img_h: crop_y = img_h - new_height
            crop_w = img_w
            crop_h = new_height
            
        pil_image = pil_image.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        
    else:
        # --- NO FACE FOUND: Fallback to Top-Priority Logic ---
        if img_ratio > target_ratio:
            new_width = int(target_ratio * img_h)
            offset = (img_w - new_width) // 2
            pil_image = pil_image.crop((offset, 0, offset + new_width, img_h))
        else:
            new_height = int(img_w / target_ratio)
            # Crop strictly from top (0) with small margin
            pil_image = pil_image.crop((0, 0, img_w, new_height))

    # Final Resize to exact pixels
    return pil_image.resize((target_w, target_h), Image.Resampling.LANCZOS)

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

# --- HTML WITH FAVICON ---
HTML_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PassPhotoFix - Smart Govt Photo Tool</title>
    
    <link rel="icon" href="https://fav.farm/🇮🇳" />

    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { 
            font-family: 'Poppins', sans-serif; 
            margin: 0; padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex; align-items: center; justify-content: center;
        }
        .container { 
            background: rgba(255, 255, 255, 0.95); 
            padding: 40px; border-radius: 20px; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.2); 
            text-align: center; max-width: 400px; width: 90%;
        }
        .logo {
            font-size: 24px; font-weight: 800; color: #764ba2;
            margin-bottom: 5px; display: flex; align-items: center; justify-content: center; gap: 10px;
        }
        .logo span { background: #764ba2; color: white; padding: 2px 8px; border-radius: 5px; }
        p { color: #666; font-size: 14px; margin-bottom: 25px; }
        
        label { display: block; text-align: left; font-weight: 600; margin-top: 15px; color: #444; }
        select, input[type=file] { 
            width: 100%; padding: 12px; margin-top: 5px; 
            border: 2px solid #e0e0e0; border-radius: 10px; box-sizing: border-box; font-family: inherit;
        }
        
        #submitBtn { 
            width: 100%; padding: 15px; margin-top: 25px; 
            background: #764ba2; color: white; border: none; border-radius: 10px; 
            cursor: pointer; font-size: 16px; font-weight: 600; 
            transition: transform 0.2s, background 0.2s;
            box-shadow: 0 4px 10px rgba(118, 75, 162, 0.3);
        }
        #submitBtn:hover { background: #5b3a80; transform: translateY(-2px); }
        
        #resetBtn {
            display: none; width: 100%; padding: 15px; margin-top: 15px;
            background: #28a745; color: white; border: none; border-radius: 10px;
            cursor: pointer; font-size: 16px; font-weight: 600;
        }
        #resetBtn:hover { background: #218838; }

        .loader {
            display: none; border: 3px solid #f3f3f3; border-top: 3px solid #764ba2;
            border-radius: 50%; width: 30px; height: 30px;
            animation: spin 1s linear infinite; margin: 20px auto;
        }
        .success-msg {
            display: none; color: #333; font-weight: bold; margin-top: 20px;
            padding: 15px; background: #e8f5e9; border-radius: 8px; border: 1px solid #c3e6cb;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .footer { margin-top: 20px; font-size: 11px; color: #888; }
    </style>
    
    <script>
        function handleProcess() {
            var fileInput = document.querySelector('input[type="file"]');
            if (fileInput.files.length === 0) return;

            document.getElementById('submitBtn').style.display = 'none';
            document.querySelector('.loader').style.display = 'block';

            setTimeout(function() {
                document.querySelector('.loader').style.display = 'none';
                
                var successDiv = document.querySelector('.success-msg');
                successDiv.style.display = 'block';
                successDiv.innerHTML = "✅ <b>Download Completed!</b><br><span style='font-size:13px; color:#555'>Check your downloads folder.</span>";
                
                document.getElementById('resetBtn').style.display = 'block';
                
            }, 3000); // Increased wait time slightly as CV takes 1 second more
        }

        function resetPage() {
            window.location.reload();
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="logo">PassPhoto<span>Fix</span> 🚀</div>
        <p>AI-Face Detection for Govt Exams</p>
        
        <form method="post" enctype="multipart/form-data" onsubmit="handleProcess()">
            <label>1. Select Exam Type</label>
            <select name="exam_type">
                {% for key, val in specs.items() %}
                <option value="{{ key }}">{{ val.name }}</option>
                {% endfor %}
            </select>
            
            <label>2. Upload Your Photo</label>
            <input type="file" name="file" required accept="image/*">
            
            <button type="submit" id="submitBtn">✨ Fix My Photo</button>
            
            <div class="loader"></div>
            <div class="success-msg"></div>

            <button type="button" id="resetBtn" onclick="resetPage()">🔄 Process Another Photo</button>
        </form>
        
        <div class="footer">Secure & Private. Files processed in RAM only.</div>
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
                
                # --- NEW LOGIC: DETECT FACE & CROP ---
                img = smart_resize_with_face_detection(img, spec['w'], spec['h'])
                
                processed_img_io = compress_image(img, spec['min_kb'], spec['max_kb'])
                
                if supabase:
                    try:
                        supabase.table("usage_logs").insert({"exam": exam_type}).execute()
                    except:
                        pass 

                return send_file(processed_img_io, mimetype='image/jpeg', as_attachment=True, download_name=f"{exam_type}_fixed.jpg")
            except Exception as e:
                return f"Error: {str(e)}"

    return render_template_string(HTML_TEMPLATE, specs=EXAM_SPECS)

if __name__ == '__main__':
    app.run(debug=True)
