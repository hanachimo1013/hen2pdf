import os
import sys
import re
import asyncio
import argparse
from typing import Optional, Type

# Import providers from subdirectories
try:
    from nhentai2pdf.nhentai2pdf import Nhentai2PDF
    from hitomi2pdf.hitomi2pdf import Hitomi2PDF
    from pururin2pdf.pururin2pdf import Pururin2PDF
    from loose_pdf_compiler.extractor_compiler import LoosePDFCompiler
except ImportError as e:
    print(f"[!] Error importing providers: {e}")
    sys.exit(1)

# PROVIDER REGISTRY
PROVIDERS = {
    "nhentai": Nhentai2PDF,
    "hitomi": Hitomi2PDF,
    "pururin": Pururin2PDF,
    "loose_compiler": LoosePDFCompiler
}

# REGEX FOR URL DETECTION
REGEX_NHENTAI = r"nhentai\.net/g/(\d+)"
REGEX_HITOMI = r"hitomi\.la/reader/(\d+)\.html|hitomi\.la/galleries/(\d+)\.html|hitomi\.la/.*-(\d+)\.html"
REGEX_PURURIN = r"pururin\.me/gallery/(\d+)"

def detect_provider(input_str: str) -> (Optional[str], Optional[str]):
    """Detect provider and extract ID from a URL or raw ID."""
    # Check if it's already a raw ID (all digits)
    if input_str.isdigit():
        return None, input_str
        
    # Check Nhentai URL
    match_nh = re.search(REGEX_NHENTAI, input_str)
    if match_nh:
        return "nhentai", match_nh.group(1)
        
    # Check Hitomi URL
    match_hi = re.search(REGEX_HITOMI, input_str)
    if match_hi:
        # Re.search might return multiple groups, pick the first non-None
        hi_id = next((g for g in match_hi.groups() if g is not None), None)
        return "hitomi", hi_id

    # Check Pururin URL
    match_pu = re.search(REGEX_PURURIN, input_str)
    if match_pu:
        return "pururin", match_pu.group(1)
        
    return None, input_str

async def run_launcher():
    parser = argparse.ArgumentParser(description="Unified H-Manga to PDF Downloader (hen2pdf-launcher)")
    parser.add_argument("-o", "--output", help="Optional output directory override")
    args = parser.parse_args()
    
    print("=" * 60)
    print(" HEN2PDF ARCHIVE LAUNCHER ")
    print(" Type 'quit', 'q', or 'esc' at any prompt to exit, or press Ctrl+C.")
    print("=" * 60)

    try:
        current_provider = None
        providers_list = list(PROVIDERS.keys())
        
        while True:
            # 1. Select Provider
            if not current_provider:
                print("\n[*] Please select a provider from the following options:")
                for idx, p in enumerate(providers_list, 1):
                    print(f"  {idx}. {p}")
                
                while True:
                    choice = input(f"Enter your choice (1-{len(providers_list)}): ").strip().lower()
                    if choice in ['exit', 'quit', 'q', 'esc']:
                        return
                    if choice.isdigit() and 1 <= int(choice) <= len(providers_list):
                        current_provider = providers_list[int(choice) - 1]
                        break
                    else:
                        print("[!] Invalid choice. Please try again.")
            
            # 2. Input Code
            print(f"\n[*] Current Provider: {current_provider}")
            target_input = input("Enter Gallery ID or URL (or 'back' to change provider): ").strip()
            
            if target_input.lower() in ('back', 'b'):
                current_provider = None
                continue
            if target_input.lower() in ('exit', 'quit', 'q', 'esc'):
                return
            
            if not target_input and current_provider != "loose_compiler":
                continue

            # Special handling for loose_compiler (doesn't need an ID input, but we'll accept 'start' or enter)
            if current_provider == "loose_compiler":
                gallery_id = "local_scan"
                detected_prov = "loose_compiler"
            else:
                # Parse target input
                detected_prov, gallery_id = detect_provider(target_input)
            
            # If they gave a URL to a completely different provider, we can auto-switch
            if detected_prov and detected_prov != current_provider:
                print(f"[*] Detected URL belongs to '{detected_prov}'. Switching provider automatically!")
                current_provider = detected_prov

            if not gallery_id:
                print(f"[!] Invalid ID or URL.")
                continue
                
            print(f"\n[*] Launching {current_provider} for ID: {gallery_id}...")
            
            # Instantiate provider
            provider_class = PROVIDERS.get(current_provider.lower())
            if not provider_class:
                print(f"[!] Unknown provider: {current_provider}")
                continue
                
            kwargs = {}
            if args.output:
                kwargs['output_dir'] = args.output
                
            provider_instance = provider_class(**kwargs)
            
            # Execute
            success = await provider_instance.execute(gallery_id)
            
            # 3. Post-Execution Routing
            print("\n" + "-" * 40)
            if success:
                print("[*] Task finished successfully.")
            else:
                print("[!] Task did not complete or was aborted.")
            
            print("\nWhat would you like to do next?")
            print(f"  1. Enter another code for {current_provider}")
            print(f"  2. Change provider")
            print(f"  3. Exit program")
            
            while True:
                next_action = input("Choice (1-3): ").strip()
                if next_action == '1':
                    break # Stay with current provider, loop back to code input
                elif next_action == '2':
                    current_provider = None
                    break # Loop back to provider selection
                elif next_action in ('3', 'exit', 'quit', 'q', 'esc'):
                    return
                else:
                    print("[!] Invalid choice.")

    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user. Exiting...")
    except Exception as e:
        print(f"\n[!] Launcher Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    try:
        asyncio.run(run_launcher())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
