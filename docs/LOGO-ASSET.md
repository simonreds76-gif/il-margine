# Logo / favicon – getting rid of white edges

The nav and some pages use **logo.png** (navbar) and **favicon.png** (contact/cookies “back to home” icon). If you see white edges or a light box around them, it’s because the image file itself has white or light pixels (or padding) in the asset.

**What you need for a clean logo:**

1. **Replace the image file** with a version that has:
   - **Transparent background** (PNG with alpha), or  
   - **Background colour that matches the site** (`#0f1117`), so there are no white or light pixels at the edges.

2. **Where the files live:**
   - **Navbar logo:** `public/logo.png`
   - **Favicon / small icon (e.g. contact page):** `public/favicon.png`

3. **Current workaround in code:** The UI uses a dark background + ring the same colour as the nav (`#0f1117`) to hide slight edges. That only hides a thin rim; if the asset has a big white border, the only reliable fix is to swap in a new image (transparent or dark-backed) as above.
