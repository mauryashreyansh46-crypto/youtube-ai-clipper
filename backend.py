import os
import requests
import threading
import yt_dlp
from flask import Flask, request, jsonify

# MoviePy Import Fix (moviepy.editor ko direct moviepy se replace karein)
try:
    from moviepy.editor import VideoFileClip, CompositeVideoClip, TextClip
except ImportError:
    # Agar moviepy.editor nahi milta, toh moviepy se import karein (MoviePy 2.0+ syntax)
    from moviepy import VideoFileClip, CompositeVideoClip, TextClip

app = Flask(__name__)

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
NVIDIA_KEY = os.getenv("NVIDIA_NIM_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.environ.get("PORT", 5000))

def analyze_video(url, options):
    print(f"Analyzing {url} with OpenRouter, Gemini, NVIDIA, Groq...")
    
    # 1. OpenRouter Analysis
    openrouter_results = ""
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={
                "model": "openai/gpt-4o",
                "messages": [{"role": "user", "content": f"Analyze YouTube video {url} and give 10 best timelines for shorts. Format: [start, end, content]. Options: {options}"}],
                "temperature": 0.1
            }
        )
        openrouter_results = response.json()['choices'][0]['message']['content']
    except Exception as e: print("OpenRouter Error:", e)

    # 2. Gemini Analysis
    gemini_results = ""
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/gemini-pro-vision:generateContent?key={GEMINI_KEY}",
            json={
                "contents": [{"parts": [{"text": f"Analyze YouTube video {url} and give 10 best timelines for shorts. Options: {options}"}]}]
            }
        )
        gemini_results = response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: print("Gemini Error:", e)

    # 3. NVIDIA NIM Analysis (API Call - No Library)
    nvidia_results = ""
    try:
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"},
            json={
                "model": "meta/llama3-70b-instruct",
                "messages": [{"role": "user", "content": f"Analyze YouTube video {url} and give 10 best timelines for shorts. Options: {options}"}],
                "temperature": 0.1
            }
        )
        nvidia_results = response.json()['choices'][0]['message']['content']
    except Exception as e: print("NVIDIA Error:", e)

    # 4. Groq Analysis
    groq_results = ""
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            json={
                "model": "llama3-70b-8192",
                "messages": [{"role": "user", "content": f"Analyze YouTube video {url} and give 10 best timelines for shorts. Options: {options}"}],
                "temperature": 0.1
            }
        )
        groq_results = response.json()['choices'][0]['message']['content']
    except Exception as e: print("Groq Error:", e)

    # AUTO-BEST MODEL SELECTION (Consensus)
    final_10 = [{"start": 10, "end": 25, "content": "Best part 1"}, {"start": 45, "end": 70, "content": "Best part 2"}] # Mock
    return final_10[:10]

def generate_clips(timelines, options, video_path):
    output_dir = "./output_clips"
    os.makedirs(output_dir, exist_ok=True)
    clip_paths = []
    base_clip = VideoFileClip(video_path)
    
    for i, t in enumerate(timelines):
        subclip = base_clip.subclip(t['start'], t['end'])
        
        if options['format'] == 'Split-Screen' and options['gameplay']:
            ydl_opts = {'outtmpl': 'gameplay.mp4', 'format': 'best'}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([options['gameplay']])
            gameplay_clip = VideoFileClip("gameplay.mp4").subclip(0, int(options['length']))
            gameplay_clip = gameplay_clip.resize((base_clip.w, base_clip.h // 3))
            final_clip = CompositeVideoClip([subclip, gameplay_clip.set_position(('center', 'bottom'))])
        else:
            final_clip = subclip
            
        if options['captions']:
            txt_clip = TextClip("Caption Text", fontsize=50, color='white').set_position('bottom').set_duration(final_clip.duration)
            final_clip = CompositeVideoClip([final_clip, txt_clip])
            
        path = f"{output_dir}/clip_{i}.mp4"
        final_clip.write_videofile(path, codec="libx264", audio_codec="aac")
        clip_paths.append(path)
        
    return clip_paths

@app.route('/api/start', methods=['POST'])
def start_clipping():
    data = request.json
    url = data.get('youtube_url')
    options = {'format': data.get('format'), 'length': data.get('length'), 'gameplay': data.get('gameplay_url'), 'captions': data.get('captions') == 'Yes'}
    ydl_opts = {'outtmpl': 'video.mp4', 'format': 'best'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    def background_task():
        timelines = analyze_video(url, options)
        generate_clips(timelines, options, "video.mp4")
        print("Clips ready in ./output_clips/")
    threading.Thread(target=background_task).start()
    return jsonify({'message': 'Railway Backend Started!', 'status': 'processing'}), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({'status': 'completed', 'clips': ['./output_clips/clip_0.mp4']}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)