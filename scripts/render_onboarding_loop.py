import os
import math
import shutil
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def main():
    width = 1280
    height = 720
    fps = 30
    duration_sec = 8.0
    num_frames = int(fps * duration_sec) # 240 frames
    
    frames_dir = "temp_frames"
    output_media_dir = os.path.join("web", "public", "media")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(output_media_dir, exist_ok=True)
    
    mp4_path = os.path.join(output_media_dir, "onboarding-loop.mp4")
    webm_path = os.path.join(output_media_dir, "onboarding-loop.webm")
    poster_path = os.path.join(output_media_dir, "onboarding-poster.jpg")
    
    num_lines = 84
    # Deterministic line seeds
    np.random.seed(42)
    line_seeds = []
    for i in range(num_lines):
        y_start = np.random.uniform(50, height - 50)
        y_target = height / 2 + (i - num_lines / 2) * 2.8
        speed_phase = np.random.uniform(0, 2 * math.pi)
        amp = np.random.uniform(60, 180)
        # Pearl tint: blend between cool white, faint lavender, faint warm peach
        color_choice = np.random.uniform(0, 1)
        if color_choice < 0.4:
            base_color = (210, 225, 255) # cool white/cyan
        elif color_choice < 0.75:
            base_color = (230, 215, 255) # lavender
        else:
            base_color = (255, 230, 215) # warm peach
        
        # A central focal line is brighter
        is_focal = (i == num_lines // 2 or i == num_lines // 2 + 1)
        line_seeds.append({
            "y_start": y_start,
            "y_target": y_target,
            "speed_phase": speed_phase,
            "amp": amp,
            "color": base_color,
            "is_focal": is_focal
        })
        
    print(f"Rendering {num_frames} frames ({width}x{height} @ {fps}fps)...")
    
    # Pre-render background gradient
    y_coords, x_coords = np.mgrid[0:height, 0:width]
    # Subtle radial falloff from center-right
    cx, cy = int(width * 0.65), int(height * 0.5)
    dist = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)
    max_d = np.sqrt(width**2 + height**2)
    vignette = 1.0 - 0.45 * (dist / max_d)**1.8
    vignette = np.clip(vignette, 0.4, 1.0)
    
    base_bg = np.zeros((height, width, 3), dtype=np.float32)
    base_bg[:, :, 0] = 5.0 * vignette # R
    base_bg[:, :, 1] = 5.0 * vignette # G
    base_bg[:, :, 2] = 7.0 * vignette # B (near-black #050507)

    for f in range(num_frames):
        t = f / num_frames # 0.0 to 1.0
        tau = 2.0 * math.pi * t
        
        # Clarity factor: 0 at t=0 (chaotic), 1 at t=0.5 (perfect clarity/alignment), 0 at t=1.0
        # Uses -cos(tau)*0.5 + 0.5 so it is perfectly smooth and periodic
        clarity = 0.5 - 0.5 * math.cos(tau)
        
        # Create image for drawing lines
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw lines from left to right
        x_steps = 40
        x_vals = np.linspace(0, width, x_steps)
        
        for line in line_seeds:
            pts = []
            y_base_start = line["y_start"]
            y_target = line["y_target"]
            amp = line["amp"] * (1.0 - clarity * 0.88) # Amplitude shrinks when clarity rises
            phase = line["speed_phase"] + tau
            
            for x in x_vals:
                progress = x / width
                # Interpolate between chaotic wave and aligned straight converge
                wave = amp * math.sin(phase + progress * 4.0) * math.cos(phase * 0.5 + progress * 2.0)
                # Aligned converges to y_target on right side
                y_ordered = y_target + (y_base_start - y_target) * (1.0 - progress)**1.5
                y_chaotic = y_base_start + wave
                
                y = (1.0 - clarity) * y_chaotic + clarity * y_ordered
                pts.append((float(x), float(y)))
                
            # Line alpha & width
            if line["is_focal"]:
                alpha = int(180 + 75 * clarity)
                lw = int(2.5 + clarity * 2.0)
            else:
                alpha = int((30 + 45 * clarity))
                lw = 1
                
            col = line["color"] + (alpha,)
            for idx in range(len(pts) - 1):
                draw.line([pts[idx], pts[idx+1]], fill=col, width=lw)
        
        # Soft bloom blur on lines
        blurred = img.filter(ImageFilter.GaussianBlur(radius=3.5))
        
        # Composite on numpy canvas
        canvas = base_bg.copy()
        
        # Add glow layer
        glow_arr = np.array(blurred, dtype=np.float32) / 255.0
        glow_rgb = glow_arr[:, :, :3]
        glow_a = glow_arr[:, :, 3:4] * 0.7
        canvas = canvas * (1.0 - glow_a) + glow_rgb * 255.0 * glow_a
        
        # Add sharp lines
        sharp_arr = np.array(img, dtype=np.float32) / 255.0
        sharp_rgb = sharp_arr[:, :, :3]
        sharp_a = sharp_arr[:, :, 3:4]
        canvas = canvas * (1.0 - sharp_a) + sharp_rgb * 255.0 * sharp_a
        
        # Add 2.5% film grain
        grain = np.random.normal(0, 3.5, (height, width, 3)).astype(np.float32)
        canvas = np.clip(canvas + grain, 0, 255).astype(np.uint8)
        
        out_img = Image.fromarray(canvas, mode="RGB")
        frame_filename = os.path.join(frames_dir, f"{f:04d}.png")
        out_img.save(frame_filename)
        
        if (f + 1) % 40 == 0 or f == num_frames - 1:
            print(f"  Rendered {f+1}/{num_frames} frames...")
            
    print("Encoding MP4 video...")
    # Encode MP4 (H.264, yuv420p, crf 26, faststart)
    cmd_mp4 = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "26", "-preset", "slow", "-movflags", "+faststart",
        mp4_path
    ]
    subprocess.run(cmd_mp4, check=True)
    
    print("Encoding WebM video...")
    # Encode WebM (VP9)
    cmd_webm = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p",
        "-crf", "32", "-b:v", "0",
        webm_path
    ]
    subprocess.run(cmd_webm, check=True)
    
    print("Extracting poster...")
    # Extract frame 120 (peak clarity moment) as poster
    cmd_poster = [
        "ffmpeg", "-y", "-ss", "00:00:04.000",
        "-i", mp4_path,
        "-vframes", "1", "-q:v", "2",
        poster_path
    ]
    subprocess.run(cmd_poster, check=True)
    
    # Clean up frames
    shutil.rmtree(frames_dir)
    print("Done! Media generated at:", output_media_dir)

if __name__ == "__main__":
    main()
