import os
import re
import asyncio
import random
import aiohttp
import cloudscraper
import pikepdf
import shutil
import unicodedata
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm
from tqdm import tqdm as tqdm_sync
from functools import wraps
from PIL import Image
from pathlib import Path


# --- RETRY DECORATOR ---
def retry_on_failure(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt == max_retries - 1:
                        return None
                    await asyncio.sleep((base_delay * (2 ** attempt)) + random.uniform(0, 1))
            return None
        return wrapper
    return decorator


class Hentai2ReadPDF:
    def __init__(self, output_dir="outputs", concurrency_limit=5):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)

        final_dir = Path(output_dir)
        fallback = False

        try:
            drive = os.path.splitdrive(os.path.abspath(final_dir))[0]
            if drive and not os.path.exists(drive + os.sep):
                fallback = True
            else:
                final_dir.mkdir(parents=True, exist_ok=True)
                test_file = final_dir / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
        except Exception:
            fallback = True

        if fallback:
            self.output_dir = Path("outputs")
            self.output_dir.mkdir(exist_ok=True)
            if final_dir != self.output_dir:
                print(f"[*] Target directory '{final_dir}' inaccessible. Falling back to '{self.output_dir}'.")
        else:
            self.output_dir = final_dir

    def _slugify(self, text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        text = re.sub(r"['']", "_", text)
        text = re.sub(r"[^a-z0-9]+", "_", text.lower())
        return text.strip("_")

    def _sanitize(self, text: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")

    def fetch_metadata(self, identifier: str) -> dict:
        """Identifier can be a slug, title query, or full URL."""
        if "hentai2read.com" in identifier:
            slug = identifier.rstrip("/").split("/")[-1]
            url = f"https://hentai2read.com/{slug}/"
            return self._get_metadata(url)

        slug = self._slugify(identifier)
        search_url = f"https://hentai2read.com/hentai-list/search/{slug}"
        r = self.scraper.get(search_url)

        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: Could not search for '{slug}'.")

        soup = BeautifulSoup(r.text, "html.parser")
        choices = [a["href"] for a in soup.find_all("a", class_="title")]

        if not choices:
            raise Exception(f"BAD IDENTIFIER: No results found for '{slug}'.")

        if len(choices) > 1:
            print(f"\n[*] Found {len(choices)} matching entries:")
            for i, href in enumerate(choices, 1):
                name = href.rstrip("/").split("/")[-1]
                print(f"    {i}. {name}")
            user_choice = int(input(f"\n[?] Select entry (1-{len(choices)}): "))
            return self._get_metadata(choices[user_choice - 1])

        return self._get_metadata(choices[0])

    def _get_metadata(self, url: str) -> dict:
        """Fetch metadata and chapter list from a doujin page."""
        r = self.scraper.get(url)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: Could not load '{url}'.")

        soup = BeautifulSoup(r.text, "html.parser")
        slug = url.rstrip("/").split("/")[-1]

        title_anchor = soup.find("a", href=url) or soup.find("a", href=url.rstrip("/"))
        title = title_anchor.get_text(strip=True) if title_anchor else slug

        tag_buttons = soup.find_all("a", class_="tagButton")
        artist = tag_buttons[7].text.strip() if len(tag_buttons) > 7 else "Unknown"

        pages = 0
        chapters = 1
        if len(tag_buttons) > 5:
            pg = re.search(r"(\d+)\s*pages", tag_buttons[5].text, re.I)
            if pg:
                pages = int(pg.group(1))
            chp = re.search(r"(\d+)\s*chapters", tag_buttons[5].text, re.I)
            if chp:
                chapters = int(chp.group(1))

        tags = ", ".join(tag_buttons[i].text.strip() for i in range(13, len(tag_buttons) - 2))
        chapter_links = [f"https://hentai2read.com/{slug}/{i}" for i in range(1, chapters + 1)]

        return {
            "title": title,
            "slug": slug,
            "safe_title": self._sanitize(title),
            "total_chapters": chapters,
            "total_pages": pages,
            "artist": artist,
            "tags": tags,
            "chapter_links": chapter_links,
        }

    def _collect_chapter_image_urls(self, chapter_url: str, page_offset: int, chapter_label: str = "") -> list:
        """
        Synchronously scrape one chapter page-by-page and return a flat list of
        (global_page_num, cdn_url, file_ext) tuples.

        This is intentionally synchronous and must complete fully before
        tqdm.gather runs — that way tqdm tracks actual image downloads,
        not the scraping phase that precedes them.
        """
        results = []
        counter = 1
        desc = f"  Scanning {chapter_label}" if chapter_label else "  Scanning"

        with tqdm_sync(desc=desc, unit="pg", leave=False) as pbar:
            while True:
                page_url = f"{chapter_url}/{counter}"
                try:
                    resp = self.scraper.get(page_url)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    img_elem = soup.find("img", id="arf-reader")

                    if not img_elem or img_elem.get("src", "").rstrip("/") == "https://static.hentai.direct/hentai":
                        break

                    img_url = img_elem["src"]
                    url_parts = img_url.split("/")

                    if len(url_parts) >= 7:
                        cdn_url = (
                            f"https://static.hentaicdn.com/hentai"
                            f"/{url_parts[4]}/{url_parts[5]}/{url_parts[6]}"
                        )
                        ext = url_parts[6].split(".")[-1] if "." in url_parts[6] else "jpg"
                        results.append((page_offset + counter, cdn_url, ext))
                        pbar.update(1)

                except Exception as e:
                    print(f"\n[!] Error scraping page {counter} of {chapter_url}: {e}")

                counter += 1

        return results

    @retry_on_failure(max_retries=3, base_delay=1)
    async def _fetch_image(self, session: aiohttp.ClientSession, url: str, path: str) -> bool:
        """Fetch a single image and write it to disk."""
        async with self.semaphore:
            async with session.get(url, timeout=12) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(path, "wb") as f:
                        f.write(content)
                    return True
                return False

    async def execute(self, identifier: str):
        """Main execution flow."""
        print(f"\n[*] Querying Hentai2Read for: {identifier}")
        try:
            data = self.fetch_metadata(identifier)
        except Exception as e:
            print(f"[!] Metadata Error: {e}")
            return

        print("=" * 60)
        print(f"  TARGET   : {data['title']}")
        print(f"  ARTIST   : {data['artist']}")
        print(f"  CHAPTERS : {data['total_chapters']}")
        print(f"  PAGES    : {data['total_pages']} Pages")
        print("=" * 60)

        confirm = input("\n[?] Compile this entry? [Enter to Continue / n to Cancel]: ").lower()
        if confirm == "n":
            print("[!] Operation scrubbed.")
            return

        temp_path = f"temp_{data['slug']}"
        os.makedirs(temp_path, exist_ok=True)

        # --- PHASE 1: Scrape all chapters synchronously to build the full URL list ---
        # Must be completely done before tqdm.gather so the bar tracks real downloads.
        all_image_urls = []
        page_offset = 0

        for i, chapter_url in enumerate(data["chapter_links"], 1):
            label = f"ch {i}/{len(data['chapter_links'])}"
            entries = self._collect_chapter_image_urls(chapter_url, page_offset, label)
            if not entries:
                print(f"[!] WARNING: No images found in chapter {i}.")
            all_image_urls.extend(entries)
            page_offset += len(entries)

        if not all_image_urls:
            print("[!] ERROR: No pages found across all chapters.")
            shutil.rmtree(temp_path)
            return

        print(f"\n[*] Total pages to download: {len(all_image_urls)}")

        # --- PHASE 2: Download all images concurrently with live tqdm progress ---
        headers = {
            "User-Agent": self.scraper.headers.get("User-Agent"),
            "Referer": "https://hentai2read.com/",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = [
                self._fetch_image(
                    session,
                    cdn_url,
                    os.path.join(temp_path, f"{page_num:04d}.{ext}")
                )
                for page_num, cdn_url, ext in all_image_urls
            ]
            results = await tqdm.gather(*tasks, desc=f"Downloading [{data['slug']}]", unit="pg")

        if not all(results):
            failed = sum(1 for r in results if not r)
            print(f"\n[!] ERROR: Integrity check failed. {failed} page(s) failed to download.")
            shutil.rmtree(temp_path)
            return

        # --- PHASE 3: Normalize and compile PDF ---
        img_files = sorted(
            os.path.join(temp_path, f)
            for f in os.listdir(temp_path)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
        )

        final_filename = str(self.output_dir / f"[{data['artist']}]_{data['safe_title']}.pdf")

        print(f"[*] Normalizing and Compiling (1600x2260)...")
        TARGET_W, TARGET_H = 1600, 2260
        processed_img_files = []

        for img_path in img_files:
            try:
                with Image.open(img_path) as img:
                    img = img.convert("RGB")
                    ratio = min(TARGET_W / img.width, TARGET_H / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    resized = img.resize(new_size, Image.Resampling.LANCZOS)
                    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (255, 255, 255))
                    canvas.paste(resized, ((TARGET_W - new_size[0]) // 2, (TARGET_H - new_size[1]) // 2))
                    proc_path = img_path + ".jpg"
                    canvas.save(proc_path, "JPEG", quality=90)
                    processed_img_files.append(proc_path)
            except Exception as e:
                print(f"[!] Error processing {img_path}: {e}")

        if not processed_img_files:
            print("[!] ERROR: No images could be processed.")
            shutil.rmtree(temp_path)
            return

        first_img = Image.open(processed_img_files[0])
        first_img.save(
            final_filename,
            save_all=True,
            append_images=(Image.open(p) for p in processed_img_files[1:]),
            resolution=100.0,
            quality=90,
        )
        first_img.close()

        # --- PHASE 4: Inject metadata ---
        print("[*] Finalizing metadata and linearization...")
        for attempt in range(5):
            if os.path.exists(final_filename):
                try:
                    with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                        with pdf.open_metadata() as meta:
                            meta["dc:title"] = data["title"]
                            meta["dc:creator"] = [data["artist"]]
                            meta["dc:subject"] = data["tags"].split(", ")
                        pdf.save(final_filename, linearize=True)
                    break
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


if __name__ == '__main__':
    """Entry point for command-line usage."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: h2rpdf <query_here>")
        query = input("[?] Enter doujin name or URL: ")
    else:
        query = sys.argv[1]

    try:
        asyncio.run(Hentai2ReadPDF().execute(query))
    except KeyboardInterrupt:
        print("\n[!] Emergency Stop.")
    except Exception as e:
        print(f"\n[!] Critical System Error: {e}")
