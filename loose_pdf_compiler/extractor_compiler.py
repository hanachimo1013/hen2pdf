import os
import re
import zipfile
import shutil
import pikepdf
import asyncio
from PIL import Image, UnidentifiedImageError
from pathlib import Path

class LoosePDFCompiler:
    def __init__(self, output_dir="outputs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _sanitize(self, text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip()

    async def execute(self, dummy_id=None):
        """
        Executes the loose PDF compilation logic. 
        dummy_id is ignored as it scans the current directory for zips.
        """
        # 1. Detect the zip file
        zip_files = [f for f in os.listdir('.') if f.lower().endswith('.zip')]
        if not zip_files:
            print("[!] No zip files found in the current directory.")
            return False
        
        print("\n[*] Available ZIP files:")
        for idx, f in enumerate(zip_files, 1):
            print(f"  {idx}. {f}")
        
        choice = input(f"Select a ZIP to process (1-{len(zip_files)}) or 'a' for all: ").strip().lower()
        
        targets = []
        if choice == 'a':
            targets = zip_files
        elif choice.isdigit() and 1 <= int(choice) <= len(zip_files):
            targets = [zip_files[int(choice) - 1]]
        else:
            print("[!] Invalid choice.")
            return False

        success_count = 0
        for zip_name in targets:
            if await self._process_zip(zip_name):
                success_count += 1
        
        return success_count > 0

    async def _process_zip(self, zip_name):
        zip_path = os.path.abspath(zip_name)
        base_name = os.path.splitext(zip_name)[0]
        
        print(f"\n[*] Processing: {zip_name}")

        # 2. Extract Metadata from filename
        artist = "Unknown"
        title = base_name
        
        match = re.search(r'\[(.*?)\]\s*(.*)', base_name)
        if match:
            artist = match.group(1).strip()
            title = match.group(2).strip()
        
        safe_title = self._sanitize(title)
        safe_artist = self._sanitize(artist)
        
        # 3. Create temp folder
        temp_dir = f"temp_loose_{safe_title[:30].replace(' ', '_')}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            print(f"[*] Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 4. Find images
            img_files = []
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.lower().endswith(('.jpg', '.png', '.webp', '.gif', '.jpeg')):
                        img_files.append(os.path.join(root, f))
            
            if not img_files:
                print("[!] No images found in archive.")
                shutil.rmtree(temp_dir)
                return False

            def natural_keys(text):
                return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]
                
            img_files.sort(key=lambda x: natural_keys(os.path.basename(x)))

            final_filename = os.path.join(self.output_dir, f"[{safe_artist}] {safe_title}.pdf")
            
            print(f"[*] Compiling {len(img_files)} images...")
            TARGET_W, TARGET_H = 1600, 2260 
            processed_images = []
            
            proc_dir = os.path.join(temp_dir, "processed")
            os.makedirs(proc_dir, exist_ok=True)

            for i, img_path in enumerate(img_files):
                try:
                    # Run image processing in thread to avoid blocking loop
                    proc_path = await asyncio.to_thread(self._process_single_image, img_path, proc_dir, i, TARGET_W, TARGET_H)
                    if proc_path:
                        processed_images.append(proc_path)
                except Exception as e:
                    print(f"[!] Error processing {img_path}: {e}")

            if processed_images:
                # PDF Save
                await asyncio.to_thread(self._save_pdf, processed_images, final_filename)
                
                # Metadata
                print(f"[*] Injecting metadata...")
                with pikepdf.open(final_filename, allow_overwriting_input=True) as pdf:
                    with pdf.open_metadata() as meta:
                        meta['dc:title'] = title
                        meta['dc:creator'] = [artist]
                    pdf.save(final_filename, linearize=True)
                
                print(f"[+] Success: {os.path.basename(final_filename)}")
                
                # Cleanup zip
                os.remove(zip_path)
                shutil.rmtree(temp_dir)
                return True
            else:
                shutil.rmtree(temp_dir)
                return False

        except Exception as e:
            print(f"[!] Critical error processing {zip_name}: {e}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False

    def _process_single_image(self, img_path, proc_dir, index, target_w, target_h):
        try:
            with Image.open(img_path) as img:
                img = img.convert('RGB')
                ratio = min(target_w / img.width, target_h / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                canvas = Image.new('RGB', (target_w, target_h), (255, 255, 255))
                canvas.paste(resized_img, ((target_w - new_size[0]) // 2, (target_h - new_size[1]) // 2))
                
                proc_path = os.path.join(proc_dir, f"{index:04d}.jpg")
                canvas.save(proc_path, "JPEG", quality=90)
                
                resized_img.close()
                canvas.close()
                return proc_path
        except Exception:
            return None

    def _save_pdf(self, processed_images, final_filename):
        images = [Image.open(p) for p in processed_images[1:]]
        with Image.open(processed_images[0]) as first_img:
            first_img.save(
                final_filename, 
                save_all=True, 
                append_images=images, 
                resolution=100.0, 
                quality=90
            )
        for img in images:
            img.close()

if __name__ == "__main__":
    # For standalone testing
    compiler = LoosePDFCompiler(output_dir="../outputs")
    asyncio.run(compiler.execute())