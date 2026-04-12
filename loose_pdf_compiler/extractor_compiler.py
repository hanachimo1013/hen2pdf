import os
import re
import zipfile
import shutil
import pikepdf
import asyncio
import img2pdf
import concurrent.futures
from PIL import Image, UnidentifiedImageError
from pathlib import Path
from tqdm.asyncio import tqdm

def process_image(img_path, target_w=1600, target_h=2260):
    try:
        with Image.open(img_path) as img:
            img = img.convert('RGB')
            ratio = min(target_w / img.width, target_h / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            canvas = Image.new('RGB', (target_w, target_h), (255, 255, 255))
            canvas.paste(resized_img, ((target_w - new_size[0]) // 2, (target_h - new_size[1]) // 2))
            
            # Use original extension's path but make it .jpg.proc for safety
            proc_path = img_path + ".proc.jpg"
            canvas.save(proc_path, "JPEG", quality=90)
            
            img.close()
            resized_img.close()
            canvas.close()
            return proc_path
    except Exception as e:
        print(f"[!] Error processing {img_path}: {e}")
        return None

class LoosePDFCompiler:
    def __init__(self, output_dir="outputs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip()

    def _natural_sort_key(self, text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

    async def execute(self, dummy_id=None):
        """
        Scans root for .zip files and compiles them into PDFs.
        """
        # 1. Detect zip files in root
        zip_files = [f for f in os.listdir('.') if f.lower().endswith('.zip')]
        if not zip_files:
            print("[!] No ZIP archives detected in the project root.")
            print(f"[*] Ensure your .zip files are placed in: {os.getcwd()}")
            return False
        
        print("\n" + "="*60)
        print("  LOOSE PDF COMPILER: STAGING AREA")
        print("="*60)
        for idx, f in enumerate(zip_files, 1):
            print(f"  {idx:2d}. {f}")
        print("="*60)
        
        choice = input(f"Selection (1-{len(zip_files)} or 'a' for all, 'q' to quit): ").strip().lower()
        
        if choice in ('q', 'quit', 'exit'):
            return False
            
        targets = []
        if choice == 'a':
            targets = zip_files
        elif choice.isdigit() and 1 <= int(choice) <= len(zip_files):
            targets = [zip_files[int(choice) - 1]]
        else:
            print("[!] Invalid selection.")
            return False

        any_success = False
        for zip_name in targets:
            if await self._process_zip(zip_name):
                any_success = True
        
        return any_success

    async def _process_zip(self, zip_name):
        zip_path = os.path.abspath(zip_name)
        base_name = os.path.splitext(zip_name)[0]
        
        print(f"\n[*] Commencing extraction: {zip_name}")

        artist = "Unknown"
        title = base_name
        
        # Regex to match [Artist] Title
        match = re.search(r'^\[(.*?)\]\s*(.*)', base_name)
        if match:
            artist = match.group(1).strip()
            title = match.group(2).strip()
        
        safe_title = self._sanitize(title)
        safe_artist = self._sanitize(artist)
        
        temp_dir = f"temp_loose_{safe_title[:20].replace(' ', '_')}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find all image files recursively
            img_files = []
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        img_files.append(os.path.join(root, f))
            
            if not img_files:
                print(f"[!] Warning: No images found in {zip_name}. Skipping.")
                shutil.rmtree(temp_dir)
                return False

            # Sort files naturally
            img_files.sort(key=lambda x: self._natural_sort_key(os.path.basename(x)))

            final_filename = os.path.join(self.output_dir, f"[{safe_artist}] {safe_title}.pdf")
            
            # MODERN PROCESSING PIPELINE
            print(f"[*] Processing {len(img_files)} images for '{safe_title}'...")
            TARGET_W, TARGET_H = 1600, 2260 
            
            loop = asyncio.get_running_loop()
            with concurrent.futures.ProcessPoolExecutor() as executor:
                tasks = [
                    loop.run_in_executor(executor, process_image, img_path, TARGET_W, TARGET_H)
                    for img_path in img_files
                ]
                results = await tqdm.gather(*tasks, desc="Normalization", unit="pg")
                processed_img_files = [res for res in results if res]

            if not processed_img_files:
                print(f"[!] Error: No images were successfully processed.")
                return False

            # PDF Compilation using img2pdf
            print(f"[*] Compiling PDF architecture...")
            try:
                with open(final_filename, "wb") as f:
                    f.write(img2pdf.convert(processed_img_files))
            except Exception as e:
                print(f"[!] PDF Conversion Error: {e}")
                shutil.rmtree(temp_path)
                return False
                
            # Metadata Injection and Linearization
            print(f"[*] Injecting archival metadata...")
            try:
                with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                    with pdf.open_metadata() as meta:
                        meta['dc:title'] = title
                        meta['dc:creator'] = [artist]
                    pdf.save(final_filename, linearize=True)
            except Exception as e:
                print(f"[!] Metadata Warning: {e}")
            
            print(f"[+] Finalized: {os.path.basename(final_filename)}")
            
            # Post-processing cleanup
            print(f"[*] Cleaning up temporary stage and archive...")
            shutil.rmtree(temp_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            
            return True

        except Exception as e:
            print(f"[!] Critical Error: {e}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False

if __name__ == "__main__":
    # Integration test stub
    asyncio.run(LoosePDFCompiler().execute())
