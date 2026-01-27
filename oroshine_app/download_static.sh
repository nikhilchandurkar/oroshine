#!/bin/bash
# Save as: download_static.sh
# Run with: chmod +x download_static_libs.sh && ./download_static.sh

STATIC_DIR="oroshine_webapp/static/lib"
cd "$(dirname "$0")"

echo "📦 Downloading static libraries..."

# Create directories
mkdir -p "$STATIC_DIR"/{jquery,owlcarousel/assets,wow,animate,bootstrap-icons,fontawesome/css,easing,waypoints,tempusdominus/{css,js},twentytwenty}

# jQuery
echo "⬇️  Downloading jQuery..."
curl -sL https://code.jquery.com/jquery-3.6.4.min.js -o "$STATIC_DIR/jquery/jquery.min.js"

# Owl Carousel
echo "⬇️  Downloading Owl Carousel..."
curl -sL https://cdnjs.cloudflare.com/ajax/libs/OwlCarousel2/2.3.4/owl.carousel.min.js -o "$STATIC_DIR/owlcarousel/owl.carousel.min.js"
curl -sL https://cdnjs.cloudflare.com/ajax/libs/OwlCarousel2/2.3.4/assets/owl.carousel.min.css -o "$STATIC_DIR/owlcarousel/assets/owl.carousel.min.css"
curl -sL https://cdnjs.cloudflare.com/ajax/libs/OwlCarousel2/2.3.4/assets/owl.theme.default.min.css -o "$STATIC_DIR/owlcarousel/assets/owl.theme.default.min.css"

# WOW.js
echo "⬇️  Downloading WOW.js..."
curl -sL https://cdnjs.cloudflare.com/ajax/libs/wow/1.1.2/wow.min.js -o "$STATIC_DIR/wow/wow.min.js"

# Animate.css
echo "⬇️  Downloading Animate.css..."
curl -sL https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css -o "$STATIC_DIR/animate/animate.min.css"

# Bootstrap Icons
echo "⬇️  Downloading Bootstrap Icons..."
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css -o "$STATIC_DIR/bootstrap-icons/bootstrap-icons.css"
mkdir -p "$STATIC_DIR/bootstrap-icons/fonts"
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/fonts/bootstrap-icons.woff2 -o "$STATIC_DIR/bootstrap-icons/fonts/bootstrap-icons.woff2"
curl -sL https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/fonts/bootstrap-icons.woff -o "$STATIC_DIR/bootstrap-icons/fonts/bootstrap-icons.woff"

# Font Awesome
echo "⬇️  Downloading Font Awesome..."
curl -sL https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css -o "$STATIC_DIR/fontawesome/css/all.min.css"
mkdir -p "$STATIC_DIR/fontawesome/webfonts"
curl -sL https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/webfonts/fa-solid-900.woff2 -o "$STATIC_DIR/fontawesome/webfonts/fa-solid-900.woff2"
curl -sL https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/webfonts/fa-brands-400.woff2 -o "$STATIC_DIR/fontawesome/webfonts/fa-brands-400.woff2"

# jQuery Easing
echo "⬇️  Downloading jQuery Easing..."
curl -sL https://cdnjs.cloudflare.com/ajax/libs/jquery-easing/1.4.1/jquery.easing.min.js -o "$STATIC_DIR/easing/jquery.easing.min.js"

# Waypoints
echo "⬇️  Downloading Waypoints..."
curl -sL https://cdnjs.cloudflare.com/ajax/libs/waypoints/4.0.1/jquery.waypoints.min.js -o "$STATIC_DIR/waypoints/waypoints.min.js"

echo "✅ All libraries downloaded successfully!"
echo ""
echo "Next steps:"
echo "1. Run: python manage.py check_static"
echo "2. Run: python manage.py collectstatic --clear --noinput"
echo "3. Restart your Django server"