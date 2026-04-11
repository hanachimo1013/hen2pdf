import os
import re
import asyncio
import aiohttp
import cloudscraper
import pikepdf
import shutil
from bs4 import BeautifulSoup
from pathlib import Path
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
                    await asyncio.sleep((base_delay * (2 ** attempt)) + (0.1 * attempt))
            return None
        return wrapper
    return decorator

class Pururin2PDF:
    def __init__(self, output_dir="outputs", concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")

    def fetch_metadata(self, code):
        """Fetch metadata by scraping the gallery page."""
        url = f"https://pururin.me/gallery/{code}/"
        resp = self.scraper.get(url)
        
        if resp.status_code == 404:
            raise Exception("[Gallery or content does not exist or was removed]")
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: Error fetching gallery page.")

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Extract basic info
        try:
            pages_span = soup.find('span', itemprop='numberOfPages')
            num_pages = int(pages_span.text) if pages_span else 0
            
            names = soup.find_all('span', itemprop='name')
            # Based on the user's original logic:
            # name[3] is usually the title
            # name[4] + name[2] + artist for thumbnail alt
            title = names[3].text if len(names) > 3 else "Untitled"
            
            author_tag = soup.find('a', itemprop='author')
            artist = author_tag.text if author_tag else "Unknown"
            
            # Find the image route data
            # The original logic used a very specific alt text for the first thumbnail
            # Let's try to be a bit more flexible or just find any image on i.pururin.me
            img_tag = soup.find('img', src=re.compile(r'https://i\.pururin\.me/'))
            if not img_tag:
                # Try the user's specific logic if the generic one fails
                # Thumbnail Page 01
                pattern = re.compile(r'Thumbnail Page 01$')
                img_tag = soup.find('img', alt=pattern)
            
            if not img_tag:
                raise Exception("Could not find image source pattern on page.")
                
            img_src = img_tag.get('src')
            match = re.search(r'https://i\.pururin\.me/([^/]+)/', img_src)
            if not match:
                raise Exception("Could not extract route data from image URL.")
            
            route_data = match.group(1)
            
            return {
                "title": title,
                "safe_title": self._sanitize(title),
                "artist": artist,
                "total_pages": num_pages,
                "route_data": route_data
            }
        except Exception as e:
            raise Exception(f"Failed to parse gallery page: {e}")

    @retry_on_failure(max_retries=3, base_delay=1)
    async def _fetch_image(self, session, url, path):
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                content = await resp.read()
                def _write_file():
                    with open(path, "wb") as f:
                        f.write(content)
                await asyncio.to_thread(_write_file)
                return True
            return False

    async def download_page(self, session, route_data, page_num, temp_path):
        async with self.semaphore:
            # Pururin seems to use 1-based indexing for images
            url = f"https://i.pururin.me/{route_data}/{page_num}.jpg"
            file_path = os.path.join(temp_path, f"{page_num:04d}.jpg")
            return await self._fetch_image(session, url, file_path)

    def _process_single_image(self, img_path, TARGET_W, TARGET_H):
        """Worker function for processing a single image. Runs in a thread."""
        try:
            with Image.open(img_path) as img_raw:
                img = img_raw.convert('RGB')
                try:
                    ratio = min(TARGET_W / img.width, TARGET_H / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))

                    # Resizing and creating canvas
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                    try:
                        canvas = Image.new('RGB', (TARGET_W, TARGET_H), (255, 255, 255))
                        try:
                            canvas.paste(resized_img, ((TARGET_W - new_size[0]) // 2, (TARGET_H - new_size[1]) // 2))

                            proc_path = img_path + ".proc.jpg"
                            if os.path.exists(proc_path): os.remove(proc_path)
                            canvas.save(proc_path, "JPEG", quality=90)
                            return proc_path
                        finally:
                            canvas.close()
                    finally:
                        resized_img.close()
                finally:
                    img.close()
        except Exception as e:
            print(f"[!] Error processing {img_path}: {e}")
            return None

    async def execute(self, code):
        print(f"\n[*] Querying Pururin Gallery ID: {code}...")
        try:
            data = await asyncio.to_thread(self.fetch_metadata, code)
        except Exception as e:
            print(f"[!] Metadata Fetch Error: {e}")
            return False

        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  VOLUME   : {data['total_pages']} Pages")
        print("=" * 60)
        
        confirm = input(f"Compile this entry? [Enter to Continue / n to Cancel]: ").lower()
        if confirm == 'n':
            print("[!] Operation scrubbed.")
            return False

        temp_path = f"temp_pururin_{code}"
        os.makedirs(temp_path, exist_ok=True)
        
        # Sync cookies and UA
        cookies = self.scraper.cookies.get_dict()
        headers = {
            "User-Agent": self.scraper.headers.get('User-Agent'),
            "Referer": f"https://pururin.me/gallery/{code}/"
        }

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            tasks = []
            # Pururin pages are usually 1 to N
            for i in range(1, data['total_pages'] + 1):
                tasks.append(self.download_page(session, data['route_data'], i, temp_path))
            
            results = await tqdm.gather(*tasks, desc=f"Progress [{code}]", unit="pg")

        if not any(results): # Check if at least some pages downloaded
            print(f"\n[!] ERROR: No pages could be downloaded.")
            shutil.rmtree(temp_path)
            return False

        # Prepare final filename
        final_filename = os.path.join(self.output_dir, f"pururin_{code}_[{self._sanitize(data['artist'])}]_{data['safe_title']}.pdf")
        
        img_files = []
        for f in os.listdir(temp_path):
            if f.lower().endswith('.jpg') and not f.lower().endswith('.proc.jpg'):
                img_files.append(os.path.join(temp_path, f))

        # Strict integer sorting based on the numeric portion of the file name
        try:
            img_files.sort(key=lambda x: int(re.search(r'(\d+)', os.path.basename(x)).group(1)))
        except Exception:
            img_files.sort()

        print(f"[*] Normalizing and Compiling (1600x2260)...")
        TARGET_W, TARGET_H = 1600, 2260 

        async def _async_proc(path):
            async with self.semaphore:
                return await asyncio.to_thread(self._process_single_image, path, TARGET_W, TARGET_H)

        proc_tasks = [_async_proc(p) for p in img_files]
        processed_img_files = await tqdm.gather(*proc_tasks, desc="Processing", unit="img")
        processed_img_files = [p for p in processed_img_files if p]

        if processed_img_files:
            images = []
            try:
                images = [Image.open(p) for p in processed_img_files[1:]]
                with Image.open(processed_img_files[0]) as first_img:
                    first_img.save(
                        final_filename, 
                        save_all=True, 
                        append_images=images, 
                        resolution=100.0, 
                        quality=90
                    )
                
                # Metadata
                print(f"[*] Finalizing metadata...")
                with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                    with pdf.open_metadata() as meta:
                        meta['dc:title'] = data['title']
                        meta['dc:creator'] = [data['artist']]
                    pdf.save(final_filename, linearize=True)
                
                print(f"[+] Success: {os.path.basename(final_filename)}")
            except Exception as e:
                print(f"[!] PDF Compilation Error: {e}")
            finally:
                for i in images: i.close()
        
        shutil.rmtree(temp_path)
        return True

async def main():
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else input("Enter Pururin ID: ")
    p = Pururin2PDF()
    await p.execute(code)

if __name__ == "__main__":
    asyncio.run(main())