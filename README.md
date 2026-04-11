# hen2pdf
### Part of the Doujinshi Series

**hen2pdf** is a high-performance, modular Python utility engineered to fetch digital galleries and compile them into standardized, archival-grade PDF documents. This tool is designed with a focus on image normalization, metadata integrity, and optimized delivery for high-fidelity viewing.

## 🚀 Key Features

- **Asynchronous Concurrency**: Utilizes `aiohttp` for non-blocking I/O, enabling rapid, simultaneous image fetching.
- **Canvas Normalization**: Automatically resizes and pads images to a uniform **1600x2260** canvas, ensuring a consistent reading experience across various devices.
- **Deep XMP Metadata Injection**: Injects rich metadata (including artist, tags, and language) directly into the PDF structure using `pikepdf`.
- **Fast Web View (Linearization)**: Optimizes the resulting PDF for "Fast Web View," allowing for streamable access and immediate page rendering in compatible viewers.
- **Cloudflare Bypass**: Integrated with `cloudscraper` to navigate common anti-bot protections seamlessly.

## 🛠 Prerequisites

- **Python**: 3.9 or higher
- **Dependencies**:
    - `aiohttp` (Asynchronous HTTP)
    - `cloudscraper` (CF bypass)
    - `beautifulsoup4` (DOM parsing)
    - `tqdm` (Progress visualization)
    - `img2pdf` (Lossless image-to-PDF conversion)
    - `pikepdf` (XMP/Metadata manipulation)
    - `Pillow` (Image processing)

## 📦 Installation

Clone the repository:
```bash
git clone https://github.com/hanachimo1013/hen2pdf.git
cd hen2pdf
```

Install the required environment packages:
```bash
pip install aiohttp cloudscraper beautifulsoup4 tqdm img2pdf pikepdf Pillow
```
*(Alternatively, use `uv sync` for faster dependency management.)*

## 🖥 Usage

Execute the interactive launcher to select a provider and target gallery:

```bash
python launcher.py
```

The tool will initialize the asynchronous session, parse the remote DOM for image assets, download them to a volatile temporary directory, and perform the final PDF assembly.

## 📐 Technical Specifications

| Parameter | Specification |
| :--- | :--- |
| **Output Format** | PDF/A-1b (equivalent) |
| **Canvas Size** | 1600 x 2260 pixels |
| **Image Compression** | Lossless (via img2pdf) |
| **Metadata Schema** | XMP / Dublin Core |
| **Optimization** | Linearized (Fast Web View) |

## ⚖️ License

This project is licensed under the MIT License - see the LICENSE file for details.

---
**Developed by:** [hanachimo](https://github.com/hanachimo1013)
