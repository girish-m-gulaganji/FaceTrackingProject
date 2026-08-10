import urllib.request
import json
import io
import cv2
import numpy as np

class OSINTScraper:
    """Public profile scraper and avatar fetcher for OSINT facial recognition."""

    @staticmethod
    def fetch_github_profile(username: str):
        """Fetch public profile avatar and metadata from GitHub API."""
        api_url = f"https://api.github.com/users/{username}"
        headers = {"User-Agent": "VisionTrack-OSINT-Engine"}

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    return False, f"GitHub user '{username}' not found.", None

                data = json.loads(response.read().decode())

            avatar_url = data.get("avatar_url")
            name = data.get("name") or username
            bio = data.get("bio") or "GitHub Developer"
            location = data.get("location") or "Global"
            profile_url = data.get("html_url") or f"https://github.com/{username}"

            if not avatar_url:
                return False, f"No avatar image available for GitHub user '{username}'.", None

            # Download avatar image bytes
            img_req = urllib.request.Request(avatar_url, headers=headers)
            with urllib.request.urlopen(img_req, timeout=10) as img_resp:
                img_bytes = img_resp.read()

            metadata = {
                "name": name,
                "username": username,
                "platform": "GitHub",
                "profile_url": profile_url,
                "bio": bio,
                "location": location,
                "avatar_url": avatar_url
            }
            return True, metadata, img_bytes

        except Exception as e:
            return False, f"Failed to fetch GitHub profile '{username}': {e}", None

    @staticmethod
    def fetch_url_profile(name: str, username: str, platform: str, profile_url: str, image_url: str, bio: str = "", location: str = ""):
        """Fetch avatar image bytes from public Web URL and format metadata."""
        headers = {"User-Agent": "VisionTrack-OSINT-Engine"}

        try:
            req = urllib.request.Request(image_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                img_bytes = response.read()

            metadata = {
                "name": name or username,
                "username": username or "web_user",
                "platform": platform or "Public Web",
                "profile_url": profile_url or image_url,
                "bio": bio or "Indexed Public Profile",
                "location": location or "Unknown",
                "avatar_url": image_url
            }
            return True, metadata, img_bytes
        except Exception as e:
            return False, f"Failed to download image from URL '{image_url}': {e}", None

    @staticmethod
    def decode_image_bytes(img_bytes: bytes):
        """Decode raw image bytes into BGR OpenCV numpy array."""
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

if __name__ == "__main__":
    success, meta, _ = OSINTScraper.fetch_github_profile("torvalds")
    print(f"[INFO] OSINT Scraper Test (torvalds): Success={success}, Meta={meta}")
