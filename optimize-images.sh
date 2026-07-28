#!/bin/bash
# Image optimization script for On-Wheels Detailing
# Converts all images to WebP, generates responsive sizes for gallery
set -e

REPO="/home/sainpaii/onwheels-crm"
IMG_DIR="$REPO/images"
LOG="/tmp/webp-convert.log"

echo "=== Image Optimization ===" | tee "$LOG"
echo "Started: $(date)" | tee -a "$LOG"

cd "$IMG_DIR"

# Quality settings
QUALITY=82
GALLERY_QUALITY=78

total_before=0
total_after=0

convert_one() {
    local input="$1"
    local output="$2"
    local quality="$3"
    local max_width="${4:-0}"
    
    local before=$(stat -c%s "$input" 2>/dev/null || echo 0)
    total_before=$((total_before + before))
    
    local resize_flag=""
    if [ "$max_width" -gt 0 ]; then
        resize_flag="-resize $max_width 0"
    fi
    
    cwebp -q "$quality" $resize_flag "$input" -o "$output" 2>/dev/null
    
    local after=$(stat -c%s "$output" 2>/dev/null || echo 0)
    total_after=$((total_after + after))
    
    local reduction=$(( 100 - (after * 100 / (before + 1)) ))
    printf "  %-35s %7d KB → %7d KB  (-%d%%)\n" \
        "$(basename "$output")" $((before/1024)) $((after/1024)) $reduction | tee -a "$LOG"
}

echo "" | tee -a "$LOG"
echo "--- Gallery images (responsive WebP: 400w, 800w, 1200w) ---" | tee -a "$LOG"

# Gallery images — generate 3 responsive sizes
for img in IMG_*.jpg IMG_*.jpeg IMG_*.JPG IMG_*.JPEG; do
    [ -f "$img" ] || continue
    base="${img%.*}"
    
    # 400w thumbnail
    convert_one "$img" "${base}-400w.webp" $GALLERY_QUALITY 400
    
    # 800w medium
    convert_one "$img" "${base}-800w.webp" $GALLERY_QUALITY 800
    
    # 1200w large
    convert_one "$img" "${base}-1200w.webp" $GALLERY_QUALITY 1200
    
    # Also create a default WebP (full size, for <picture> fallback)
    convert_one "$img" "${base}.webp" $QUALITY 0
done

echo "" | tee -a "$LOG"
echo "--- PNG assets (WebP) ---" | tee -a "$LOG"

# Logo files
for img in onwheelsLogo.png onwheelsLogoMark.png onwheelsSecondaryLogo-03.png onwheelsSecondaryOption.png; do
    [ -f "$img" ] || continue
    base="${img%.*}"
    convert_one "$img" "${base}.webp" 90 0
done

# Hero image — critical for LCP
echo "" | tee -a "$LOG"
echo "--- Hero image ---" | tee -a "$LOG"
if [ -f "hero-car.png" ]; then
    convert_one "hero-car.png" "hero-car.webp" 80 1920
    # Also a mobile-optimized version
    convert_one "hero-car.png" "hero-car-mobile.webp" 75 768
fi

# Favicon
echo "" | tee -a "$LOG"
echo "--- Favicon ---" | tee -a "$LOG"
if [ -f "onwheelsLogo.png" ]; then
    convert onwheelsLogo.png -resize 32x32 favicon-32.png 2>/dev/null || \
        python3 -c "
from PIL import Image
img = Image.open('onwheelsLogo.png')
img = img.resize((32, 32), Image.LANCZOS)
img.save('favicon-32.png')
" 2>/dev/null || echo "  (favicon generation requires ImageMagick or Pillow)"
    
    if [ -f "favicon-32.png" ]; then
        echo "  Created favicon-32.png" | tee -a "$LOG"
    else
        echo "  Could not create favicon — will use logo directly" | tee -a "$LOG"
    fi
fi

echo "" | tee -a "$LOG"
echo "=== Summary ===" | tee -a "$LOG"
printf "Total before: %d KB (%.1f MB)\n" $((total_before/1024)) $(echo "scale=1; $total_before/1024/1024" | bc 2>/dev/null || echo "?")
printf "Total after:  %d KB (%.1f MB)\n" $((total_after/1024)) $(echo "scale=1; $total_after/1024/1024" | bc 2>/dev/null || echo "?")
echo "Done: $(date)" | tee -a "$LOG"
