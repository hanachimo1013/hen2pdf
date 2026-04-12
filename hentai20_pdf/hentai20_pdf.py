import os
import re
import asyncio
import random
import aiohttp
import cloudscraper
import pikepdf
import shutil
import img2pdf
import concurrent.futures
import unicodedata
from tqdm.asyncio import tqdm
from functools import wraps
from PIL import Image, UnidentifiedImageError
from bs4 import BeautifulSoup

def process_image(img_path, target_w=1600, target_h=2260):
    try:
        with Image.open(img_path) as img:
            img = img.convert('RGB')
            ratio = min(target_w / img.width, target_h / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            canvas = Image.new('RGB', (target_w, target_h), (255, 255, 255))
            canvas.paste(resized_img, ((target_w - new_size[0]) // 2, (target_h - new_size[1]) // 2))

            proc_path = img_path + ".jpg"
            canvas.save(proc_path, "JPEG", quality=90)

            img.close()
            resized_img.close()
            canvas.close()
            return proc_path
    except (UnidentifiedImageError, OSError, ValueError) as e:
        print(f"[!] Error processing {img_path}: {e}")
        return None

# --- RETRY DECORATOR ---
def retry_on_failure(max_retries=5, base_delay=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                    if attempt == max_retries - 1: 
                        return None
                    await asyncio.sleep((base_delay * (2 ** attempt)) + random.uniform(0, 1))
            return None
        return wrapper
    return decorator

class Hentai20PDF:
    def __init__(self, output_dir="outputs", concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|=\.]', "", text).strip().replace(" ", "_")

    def _slugify(self, text):
        text = unicodedata.normalize("NFKD", text)
        text = re.sub(r"[’']", "-", text)              
        text = re.sub(r"[^a-z0-9]+", "-", text.lower())  
        return text.strip("-")

    def fetch_metadata(self, identifier):
        """
        Identifier can be a slug or a full URL.
        """
        if "hentai20.io" in identifier:
            if "/manga/" in identifier:
                slug = identifier.split("/manga/")[-1].strip("/")
            else:
                # Handle chapter URL directly?
                slug = identifier.split("hentai20.io/")[-1].split("-chapter-")[0].strip("/")
        else:
            slug = self._slugify(identifier)
        
        manga_url = f"https://hentai20.io/manga/{slug}/"
        print(f"[*] Querying Hentai20 metadata: {manga_url}")
        
        resp = self.scraper.get(manga_url)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: Could not find manga info for '{slug}'.")

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.find('h1', class_='entry-title').text if soup.find('h1', class_='entry-title') else slug
        
        # Get total chapters
        chapters_span = soup.find('span', class_='epcur epcurlast')
        total_chapters = 1
        if chapters_span:
            try:
                total_chapters = int(chapters_span.text.split(' ')[1])
            except:
                pass
        
        # Tags and Artists if available (Hentai20 usually has them)
        tags = [a.text for a in soup.find_all('a', rel='tag')]
        artist = "Unknown"
        # Hentai20 metadata is often in a specific div
        # For now, we'll keep it simple or look for 'Artist' label
        
        return {
            "title": title,
            "safe_title": self._sanitize(title),
            "slug": slug,
            "total_chapters": total_chapters,
            "artist": artist,
            "tags": tags
        }

    @retry_on_failure(max_retries=3, base_delay=1)
    async def _download_file(self, session, url, path):
        async with self.semaphore:
            async with session.get(url, timeout=20) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    await asyncio.to_thread(self._write_file, path, content)
                    return True
                return False

    def _write_file(self, path, content):
        with open(path, "wb") as f:
            f.write(content)

    async def execute(self, identifier):
        print(f"\n[*] Initiating Hentai20 Acquisition for: {identifier}")
        try:
            data = self.fetch_metadata(identifier)
        except Exception as e:
            print(f"[!] Metadata Error: {e}")
            return False

        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  SLUG     : {data['slug']}")
        print(f"  CHAPTERS : {data['total_chapters']} Available")
        print("=" * 60)
        
        choice = input(f"Select Chapter to download (1-{data['total_chapters']}) or 'n' to Cancel: ").strip()
        if choice.lower() == 'n':
            return False
            
        try:
            chapter_num = int(choice)
        except ValueError:
            print("[!] Invalid choice.")
            return False

        chapter_url = f"https://hentai20.io/{data['slug']}-chapter-{chapter_num}/"
        print(f"[*] Accessing Chapter {chapter_num}: {chapter_url}")
        
        resp = await asyncio.to_thread(self.scraper.get, chapter_url)
        if resp.status_code != 200:
            print(f"[!] Error: Could not access chapter {chapter_num}.")
            return False
            
        soup = BeautifulSoup(resp.text, "html.parser")
        img_urls = [img['src'] for img in soup.find_all('img', decoding='async')]
        
        if not img_urls:
            print("[!] No images found in this chapter.")
            return False

        print(f"[*] Collected {len(img_urls)} image pointers. Starting download...")
        
        temp_path = f"temp_h20_{data['slug']}_ch{chapter_num}"
        os.makedirs(temp_path, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, url in enumerate(img_urls, 1):
                ext = url.split('.')[-1].split('?')[0] if '.' in url else 'jpg'
                path = os.path.join(temp_path, f"{i:04d}.{ext}")
                tasks.append(self._download_file(session, url, path))
            
            results = await tqdm.gather(*tasks, desc=f"Progress [Ch.{chapter_num}]", unit="pg")

        if not all(results):
            failed = len([r for r in results if not r])
            print(f"\n[!] Warning: {failed} pages failed to download.")

        # Prepare final filename
        final_filename = os.path.join(self.output_dir, f"[H20]_[Ch.{chapter_num}]_{data['safe_title']}.pdf")
        
        img_files = []
        for f in os.listdir(temp_path):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                img_files.append(os.path.join(temp_path, f))
        
        # Strict integer sorting
        try:
            img_files.sort(key=lambda x: int(re.search(r'(\d+)\.', os.path.basename(x)).group(1)))
        except:
            img_files.sort()

        if not img_files:
            print("[!] Aborting: No images to compile.")
            shutil.rmtree(temp_path)
            return False

        print(f"[*] Normalizing and Compiling (1600x2260)...")
        TARGET_W, TARGET_H = 1600, 2260 
        processed_img_files = []

        loop = asyncio.get_running_loop()
        with concurrent.futures.ProcessPoolExecutor() as executor:
            tasks = [
                loop.run_in_executor(executor, process_image, img_path, TARGET_W, TARGET_H)
                for img_path in img_files
            ]
            results = await tqdm.gather(*tasks, desc="Processing images", unit="img")
            processed_img_files = [res for res in results if res]

        if processed_img_files:
            try:
                with open(final_filename, "wb") as f:
                    f.write(img2pdf.convert(processed_img_files))
            except Exception as e:
                print(f"[!] PDF Compilation Error: {e}")
                shutil.rmtree(temp_path)
                return False
        
        # Inject Metadata
        print(f"[*] Finalizing metadata and linearization...")
        try:
            with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                with pdf.open_metadata() as meta:
                    meta['dc:title'] = f"{data['title']} - Chapter {chapter_num}"
                    meta['dc:creator'] = [data['artist']]
                    meta['dc:subject'] = data['tags']
                pdf.save(final_filename, linearize=True)
        except Exception as e:
            print(f"[!] Metadata Warning: {e}")
        
        shutil.rmtree(temp_path)
        print("=" * 60)
        print(f"   -> Success: {os.path.basename(final_filename)}")
        print("=" * 60)
        return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        asyncio.run(Hentai20PDF().execute(sys.argv[1]))
    else:
        print("Usage: python hentai20_pdf.py <slug or URL>")
