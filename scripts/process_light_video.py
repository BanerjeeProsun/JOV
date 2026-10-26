import subprocess
import os

print("Processing hero-video-light.mp4...")

# Filter chain for light video:
# 1. Crop to focus on keyboard + hand, excluding black iPad and headphones
# 2. Slight curves/levels so the desk background lifts to ~#f8f8fa matching light theme
# 3. Crossfade 0.6s between the end and start to produce an imperceptible, seamless loop
#
# Original duration = 4.36s.
# Split into:
# Part A: [0.6s to 4.36s] (3.76s long)
# Part B: [0:00 to 0.6s] (0.6s long)
# xfade transition of 0.6s: Part A ends at 3.76s, overlapping Part B by 0.6s -> final length = 3.76s.

filter_graph = (
    "[0:v]crop=960:860:960:220,scale=1280:720,"
    "eq=brightness=0.03:contrast=1.03:saturation=0.96[vbase];"
    "[vbase]split=2[main][head];"
    "[main]trim=start=0.6:end=4.36,setpts=PTS-STARTPTS[vmain];"
    "[head]trim=start=0:end=0.6,setpts=PTS-STARTPTS[vhead];"
    "[vmain][vhead]xfade=transition=fade:duration=0.55:offset=3.21,format=yuv420p[v]"
)

out_video_light = "web/public/media/hero-video-light.mp4"
out_poster_light = "web/public/media/hero-poster-light.jpg"

cmd_light = [
    "ffmpeg", "-y", "-i", "herovidlight.mp4",
    "-filter_complex", filter_graph,
    "-map", "[v]",
    "-c:v", "libx264", "-crf", "19", "-preset", "slow",
    "-movflags", "+faststart",
    out_video_light
]

subprocess.run(cmd_light, check=True)
print(f"Generated {out_video_light}")

# Extract poster for light mode at t=1.0s
subprocess.run([
    "ffmpeg", "-y", "-ss", "00:00:01", "-i", out_video_light,
    "-vframes", "1", "-q:v", "2",
    out_poster_light
], check=True)
print(f"Generated {out_poster_light}")
