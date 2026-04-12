# 🏛️ The Connoisseur's Guide to Local Salvage

### *A Step-by-Step Protocol for the Loose PDF Compiler*

When a scholar finds themselves with orphaned collection of images—those "loose" archives trapped within `.zip` files—they require a tool that can transform raw data into a standardized masterpiece. This guide outlines the exact ritual for the **Loose PDF Compiler**.

---

## 📜 Stage 1: The Naming Protocol
Before the compiler can begin its work, your archives must be properly titled. The system uses a specific regex pattern to extract metadata directly from the filename.

**The Golden Rule:** Name your zip file using the following format:
`[Artist Name] The Title of the Work.zip`

*   **Result:** The compiler will automatically assign `Artist Name` as the author and `The Title of the Work` as the document title in the PDF metadata.
*   **Fallback:** If the brackets are missing, the system will use the entire filename as the title and list the artist as "Unknown."

---

## 📂 Stage 2: Placement
Ensure all `.zip` archives you wish to process are placed in the **root directory** of the project:
`c:\Users\jmont\OneDrive\Desktop\Codeproj\hen2pdf-main\`

---

## 🚀 Stage 3: The Execution
Initialize the suite and select the salvage engine:

1.  Open your terminal in the root directory.
2.  Run the Grand Launcher: `python launcher.py`
3.  Select option **5. loose_compiler** from the menu.
4.  At the prompt, simply press **Enter** to begin the scan.

---

## 🎨 Stage 4: Selection & Normalization
The system will display a list of all detected archives. You have two choices:
*   **Individual Selection**: Enter the index number (e.g., `1`) to process a single archive.
*   **The Grand Sweep**: Enter `a` (all) to process every detected `.zip` file in the sequence.

**The Process:** 
*   The system extracts the images to a volatile temporary folder.
*   Every page is normalized to the standard **1600x2260** canvas.
*   Metadata is injected, and the PDF is linearized for efficient viewing.
*   The original `.zip` is cleaned up to preserve disk space.

---

## 🏛️ Stage 5: Collection
Once the process is complete, navigate to your gallery:
`c:\Users\jmont\OneDrive\Desktop\Codeproj\hen2pdf-main\outputs\`

Your new, archival-grade PDFs will be waiting for you, perfectly formatted and ready for your preferred digital reader. 🥂
