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

class Ehentai2PDF:
    def __init__(self, output_dir="outputs", concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|=\.]', "", text).strip().replace(" ", "_")

    def fetch_metadata(self, identifier):
        """
        Identifier can be a full URL, 'id/token', or just 'id'.
        Example: https://e-hentai.org/g/2856012/963f03b290/
        """
        if "e-hentai.org" in identifier:
            url = identifier
        elif "/" in identifier:
            url = f"https://e-hentai.org/g/{identifier}"
        else:
            # Search fallback for just GID
            print(f"[*] Attempting to resolve hash for GID: {identifier}...")
            search_url = f"https://e-hentai.org/?f_search=gid:{identifier}"
            search_resp = self.scraper.get(search_url)
            
            if search_resp.status_code != 200:
                raise Exception(f"HTTP {search_resp.status_code}: Error searching for GID.")
            
            search_soup = BeautifulSoup(search_resp.text, "html.parser")
            # Look for the first gallery title link
            # Usually in a table with class 'itg' and titles in 'gl3c'
            gl_link = search_soup.find('td', class_='gl3c')
            if not gl_link:
                # Fallback for different search result views
                gl_link = search_soup.find('div', class_='glname')
            
            if gl_link and gl_link.find('a'):
                url = gl_link.find('a')['href']
                print(f"[*] Resolved to: {url}")
            else:
                raise Exception(f"Could not resolve hash for GID {identifier}. Please use the full URL.")
        
        if not url.endswith('/'):
            url += '/'

        print(f"[*] Fetching metadata from: {url}")
        resp = self.scraper.get(url)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: Error fetching gallery page.")

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Title
        title = soup.find('h1', id='gn').text if soup.find('h1', id='gn') else "Untitled"
        
        # Pages
        # Usually something like "Showing 1 - 20 of 115 images" or just found in metadata
        # Easier to find the .gpc count or the div with " images"
        meta_td = soup.find_all('td', class_='gdt2')
        num_pages = 0
        for td in meta_td:
            if "pages" in td.text.lower():
                num_pages = int(re.search(r'(\d+)', td.text).group(1))
                break
        
        # Tags
        tags = [a.text for a in soup.find_all('div', id=re.compile(r'td_.*'))]
        # In E-Hentai, tags are often in a different structure
        tag_elements = soup.find_all('div', class_='gt')
        tags = [t.text for t in tag_elements]

        # Artist
        artist = "Unknown"
        for t in tags:
            if t.startswith('artist:'):
                artist = t.replace('artist:', '').strip()
                break
        
        # Collect image page links (first page)
        # Note: We need to collect ALL image page links, which might span multiple gallery pages
        return {
            "title": title,
            "safe_title": self._sanitize(title),
            "total_pages": num_pages,
            "artist": artist,
            "tags": tags,
            "base_url": url
        }

    async def _get_image_page_links(self, session, base_url, total_pages):
        """Collects all 's/' links from the gallery pages."""
        gallery_page_count = (total_pages + 39) // 40 # Standard is 40 per page, but can vary. 
        # Actually E-Hentai uses 'p' parameter for gallery pages.
        # We can detect how many thumbnails are on the first page to be sure? 
        # But usually 40 is a safe bet for public. 
        # Let's just loop until we have enough links.
        
        all_image_pages = []
        p = 0
        while len(all_image_pages) < total_pages:
            url = f"{base_url}?p={p}"
            async with session.get(url) as resp:
                if resp.status != 200: break
                text = await resp.text()
                soup = BeautifulSoup(text, "html.parser")
                links = [a['href'] for a in soup.find_all('a') if '/s/' in a.get('href', '')]
                # Remove duplicates if any
                for l in links:
                    if l not in all_image_pages:
                        all_image_pages.append(l)
                
                if not links: break # No more links found
            p += 1
            if p > 100: break # Safety
            
        return all_image_pages[:total_pages]

    @retry_on_failure(max_retries=3, base_delay=1)
    async def _get_direct_image_url(self, session, image_page_url):
        async with self.semaphore:
            async with session.get(image_page_url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, "html.parser")
                    img_tag = soup.find('img', id='img')
                    if img_tag:
                        return img_tag['src']
                return None

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
        print(f"\n[*] Initiating E-Hentai Archive for: {identifier}")
        try:
            data = self.fetch_metadata(identifier)
        except Exception as e:
            print(f"[!] Metadata Fetch Error: {e}")
            return False

        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  VOLUME   : {data['total_pages']} Pages")
        print("=" * 60)
        
        confirm = input(f"Proceed with acquisition? [Enter to Continue / n to Cancel]: ").lower()
        if confirm == 'n':
            return False

        id_clean = self._sanitize(identifier.split('/')[-2] if '/' in identifier else identifier)
        temp_path = f"temp_eh_{id_clean}"
        os.makedirs(temp_path, exist_ok=True)

        cookies = self.scraper.cookies.get_dict()
        headers = {
            "User-Agent": self.scraper.headers.get('User-Agent'),
            "Referer": data['base_url']
        }

        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            print(f"[*] Mapping gallery pages...")
            image_page_urls = await self._get_image_page_links(session, data['base_url'], data['total_pages'])
            
            if not image_page_urls:
                print("[!] Failed to collect image page links.")
                shutil.rmtree(temp_path)
                return False

            print(f"[*] Resolved {len(image_page_urls)} entry points. Extracting sources...")
            
            # Step 1: Get all direct image URLs
            source_tasks = [self._get_direct_image_url(session, url) for url in image_page_urls]
            direct_urls = await tqdm.gather(*source_tasks, desc="Extracting Sources", unit="url")
            
            # Step 2: Download images
            download_tasks = []
            for i, url in enumerate(direct_urls, 1):
                if url:
                    ext = url.split('.')[-1].split('?')[0] if '.' in url else 'jpg'
                    path = os.path.join(temp_path, f"{i:04d}.{ext}")
                    download_tasks.append(self._download_file(session, url, path))
                else:
                    download_tasks.append(asyncio.sleep(0, result=False)) # Placeholder for failure
            
            results = await tqdm.gather(*download_tasks, desc="Downloading Assets", unit="img")

        if not all([r for r in results if r is not None]):
            failed = len([r for r in results if not r])
            print(f"\n[!] Warning: {failed} downloads failed. Attempting compilation anyway.")

        # Prepare final filename
        final_filename = os.path.join(self.output_dir, f"[E-H]_[{self._sanitize(data['artist'])}]_{data['safe_title']}.pdf")
        
        img_files = []
        for f in os.listdir(temp_path):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                img_files.append(os.path.join(temp_path, f))
        
        # Strict integer sorting based on the numeric portion of the file name
        try:
            img_files.sort(key=lambda x: int(re.search(r'(\d+)\.', os.path.basename(x)).group(1)))
        except Exception as e:
            print(f"[!] Warning: Strict sorting failed, falling back to basic sort. Error: {e}")
            img_files.sort()

        if not img_files:
            print("[!] No images downloaded. Aborting.")
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
                    meta['dc:title'] = data['title']
                    meta['dc:creator'] = [data['artist']]
                    meta['dc:subject'] = data['tags']
                pdf.save(final_filename, linearize=True)
        except Exception as e:
            print(f"[!] Warning: Failed to inject metadata: {e}")
        
        shutil.rmtree(temp_path)
        print("=" * 60)
        print(f"   -> Success: {os.path.basename(final_filename)}")
        print("=" * 60)
        return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        asyncio.run(Ehentai2PDF().execute(sys.argv[1]))
    else:
        print("Usage: python e-hentai2pdf.py <URL or ID>")
