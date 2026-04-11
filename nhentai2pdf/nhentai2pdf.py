import os
import re
import asyncio
import random
import aiohttp
import cloudscraper
import pikepdf
import shutil
from tqdm.asyncio import tqdm
from functools import wraps
from PIL import Image, UnidentifiedImageError

# --- RETRY DECORATOR ---
def retry_on_failure(max_retries=5, base_delay=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt == max_retries - 1: return None
                    await asyncio.sleep((base_delay * (2 ** attempt)) + random.uniform(0, 1))
            return None
        return wrapper
    return decorator

class Nhentai2PDF:
    def __init__(self, output_dir="outputs", concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        
        self.output_dir = output_dir
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            print(f"[*] Target directory '{self.output_dir}' inaccessible: {e}. Falling back to 'outputs'.")
            self.output_dir = "outputs"
            os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")

    def fetch_metadata(self, code):
        """Fetch metadata using the v2 API."""
        api_url = f"https://nhentai.net/api/v2/galleries/{code}"
        resp = self.scraper.get(api_url)
        
        if resp.status_code == 403:
            raise Exception("Access Denied (Cloudflare). Try updating cloudscraper or using a VPN.")
        if resp.status_code == 404:
            raise Exception(f"Gallery {code} not found (might have been removed).")
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: Error fetching metadata.")

        try:
            data = resp.json()
        except Exception:
            raise Exception("Failed to parse API response.")

        # Mapping API fields to our structure
        title_data = data.get('title', {})
        title = title_data.get('pretty') or title_data.get('english') or title_data.get('japanese') or "Untitled"
        media_id = data.get('media_id')
        num_pages = data.get('num_pages', 0)
        
        # Tags processing
        tags = []
        artist = "Unknown"
        language = "Unknown"
        
        for t in data.get('tags', []):
            t_type = t.get('type')
            t_name = t.get('name', '')
            if t_type == 'tag':
                tags.append(t_name)
            elif t_type == 'artist':
                artist = t_name
            elif t_type == 'language' and t_name.lower() != 'translated':
                language = t_name.capitalize()

        # Image extensions mapping from 'pages' root
        # V2 structure: data['pages'] -> list of { 'path': '...', 'number': ... }
        pages_list = data.get('pages', [])
        # Fallback to images structure if root pages is empty
        if not pages_list:
            pages_list = data.get('images', {}).get('pages', [])
            
        if not pages_list and num_pages > 0:
            raise Exception("Gallery found but could not fetch image list (empty 'pages' data).")

        pages_ext = []
        for p in pages_list:
            path = p.get('path', '')
            ext = path.split('.')[-1] if '.' in path else 'jpg'
            # If path is missing but 't' is present (older API style sometimes mixed in)
            if not path and 't' in p:
                ext_map = {'j': 'jpg', 'p': 'png', 'w': 'webp'}
                ext = ext_map.get(p.get('t'), 'jpg')
            pages_ext.append(ext)

        return {
            "title": title,
            "safe_title": self._sanitize(title),
            "media_id": media_id,
            "total_pages": num_pages,
            "artist": artist,
            "tags": tags,
            "language": language,
            "pages_ext": pages_ext
        }

    @retry_on_failure(max_retries=3, base_delay=1)
    async def _fetch_image(self, session, url, path):
        async with session.get(url, timeout=12) as resp:
            if resp.status == 200:
                content = await resp.read()
                def _write_file():
                    with open(path, "wb") as f:
                        f.write(content)
                await asyncio.to_thread(_write_file)
                return True
            elif resp.status in [403, 429, 500, 502, 503, 504]:
                print(f"[~] Rate limited ({resp.status}) on {url.split('/')[-1]}, retrying...")
                resp.raise_for_status()
            return False

    async def download_page(self, session, media_id, page_num, ext, temp_path):
        async with self.semaphore:
            url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
            file_path = os.path.join(temp_path, f"{page_num:04d}.{ext}")
            try:
                return await self._fetch_image(session, url, file_path)
            except Exception:
                return False

    async def execute(self, code):
        print(f"\n[*] Querying Archive ID: {code}...")
        try:
            data = self.fetch_metadata(code)
        except Exception as e:
            print(f"[!] Metadata Fetch Error: {e}")
            return False

        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  LANGUAGE : {data['language']}")
        print(f"  VOLUME   : {data['total_pages']} Pages")
        print("=" * 60)
        
        confirm = input(f"Compile this entry? [Enter to Continue / n to Cancel]: ").lower()
        if confirm == 'n':
            print("[!] Operation scrubbed.")
            return False

        temp_path = f"temp_{code}"
        os.makedirs(temp_path, exist_ok=True)
        
        # Sync cookies and UA from cloudscraper to aiohttp
        cookies = self.scraper.cookies.get_dict()
        headers = {
            "User-Agent": self.scraper.headers.get('User-Agent'),
            "Referer": "https://nhentai.net/"
        }

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            tasks = []
            for i, ext in enumerate(data['pages_ext'], 1):
                tasks.append(self.download_page(session, data['media_id'], i, ext, temp_path))
            
            results = await tqdm.gather(*tasks, desc=f"Progress [{code}]", unit="pg")

        if not all(results):
            failed = len([r for r in results if not r])
            print(f"\n[!] ERROR: Integrity check failed. {failed} page(s) failed to download.")
            shutil.rmtree(temp_path)
            return False

        # Prepare final filename
        final_filename = os.path.join(self.output_dir, f"{code}_[{self._sanitize(data['artist'])}]_{data['safe_title']}.pdf")
        
        img_files = []
        for f in os.listdir(temp_path):
            if re.match(r'^\d+\.(jpg|png|webp|gif)$', f.lower()):
                img_files.append(os.path.join(temp_path, f))

        # Strict integer sorting based on the numeric portion of the file name
        try:
            img_files.sort(key=lambda x: int(re.search(r'(\d+)\.', os.path.basename(x)).group(1)))
        except Exception as e:
            print(f"[!] Warning: Strict sorting failed, falling back to basic sort. Error: {e}")
            img_files.sort()

        print(f"[*] Normalizing and Compiling (1600x2260)...")
        TARGET_W, TARGET_H = 1600, 2260 
        processed_img_files = []

        for img_path in img_files:
            try:
                with Image.open(img_path) as img:
                    img = img.convert('RGB')
                    ratio = min(TARGET_W / img.width, TARGET_H / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                    canvas = Image.new('RGB', (TARGET_W, TARGET_H), (255, 255, 255))
                    canvas.paste(resized_img, ((TARGET_W - new_size[0]) // 2, (TARGET_H - new_size[1]) // 2))
                    
                    proc_path = img_path + ".jpg"
                    canvas.save(proc_path, "JPEG", quality=90)
                    processed_img_files.append(proc_path)
                    
                    # Prevent memory ballooning by explicitly releasing image buffers
                    img.close()
                    resized_img.close()
                    canvas.close()
            except (UnidentifiedImageError, OSError, ValueError) as e:
                print(f"[!] Error processing {img_path}: {e}")

        if processed_img_files:
            images = []
            first_img = None
            try:
                # 'processed_img_files' is built sequentially from strictly-ordered 'img_files'
                first_img = Image.open(processed_img_files[0])
                for p in processed_img_files[1:]:
                    images.append(Image.open(p))
                
                if os.path.exists(final_filename):
                    try:
                        os.remove(final_filename)
                        print(f"[*] Overwriting existing file: {os.path.basename(final_filename)}")
                    except OSError as e:
                        print(f"[!] Target file exists but is locked/cannot be overwritten: {e}")
                        
                first_img.save(
                    final_filename, 
                    save_all=True, 
                    append_images=images, 
                    resolution=100.0, 
                    quality=90
                )
            except Exception as e:
                print(f"[!] PDF Compilation Error: {e}")
                shutil.rmtree(temp_path)
                return
            finally:
                if first_img:
                    first_img.close()
                for i in images:
                    i.close()
        
        # Inject Metadata (with race-condition retry for network drives)
        print(f"[*] Finalizing metadata and linearization...")
        for attempt in range(5):
            if os.path.exists(final_filename):
                try:
                    with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                        with pdf.open_metadata() as meta:
                            meta['dc:title'] = f"{data['title']} [{data['language']}]"
                            meta['dc:creator'] = [data['artist']]
                            meta['dc:subject'] = data['tags']
                            meta['dc:language'] = [data['language'].lower()]
                        pdf.save(final_filename, linearize=True)
                    break # Success
                except Exception as e:
                    if attempt == 4:
                        print(f"[!] Warning: Failed to inject metadata: {e}")
                    await asyncio.sleep(1)
            else:
                if attempt == 4:
                    print(f"[!] Warning: File not found for metadata injection: {final_filename}")
                await asyncio.sleep(1)
        
        shutil.rmtree(temp_path)
        print("=" * 60)
        print(f"   -> Success: [{data['title']}]")
        print(f"      Archive completed: {os.path.basename(final_filename)}")
        print(f"      Location: {self.output_dir}")
        print("=" * 60)
        return True


