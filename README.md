# 🏛️ hen2pdf: The Connoisseur's Archive

### *A Refined Suite for the Distinguished Scholar*

**hen2pdf** is not merely a utility; it is a grand architect for your digital library. Engineered for the "Man of Culture," this suite high-performance, asynchronous Python tools is designed to fetch, normalize, and curate digital galleries into standardized, archival-grade PDF documents. Every page is treated with the reverence it deserves, ensuring your collection remains as exquisite as the day it was published.

---

## 🏛️ Project Architecture (The Grand Map)

For those who appreciate the structural integrity of a well-organized library, here is the full layout of the estate:

| Component | Absolute Path / Description |
| :--- | :--- |
| **The Grand Launcher** | `launcher.py` — The unified interface for all exquisite acquisitions. |
| **The Gallery** | `outputs/` — Where your finalized masterpieces are displayed. |
| **nHentai Wing** | `nhentai2pdf/nhentai2pdf.py` — Specialized v2 API integration for precise metadata. |
| **Hitomi Wing** | `hitomi2pdf/hitomi2pdf.py` — Playwright-powered engine for dynamic DOM resolution. |
| **Pururin Wing** | `pururin2pdf/pururin2pdf.py` — Dedicated scraper for the Pururin repository. |
| **E-Hentai Wing** | `ehen2pdf_ext/e_hentai2pdf.py` — High-performance scraper for the E-Hentai archives. |
| **The Salvage Yard** | `loose_pdf_compiler/extractor_compiler.py` — Compiles your existing local image archives (.zip) into normalized PDFs. |

---

## 🚀 Exquisite Features

- **🍷 Asynchronous Concurrency**: Utilizes `aiohttp` for non-blocking I/O—because a gentleman should never wait.
- **🎨 Aesthetic Normalization**: Every image is centered upon a uniform **1600x2260** canvas. No "jumping" pages; only smooth, consistent viewing.
- **📜 Deep XMP Metadata**: Artist, Tags, and Language are baked directly into the PDF structure using `pikepdf`.
- **⚡ Linearized Delivery**: Optimized for "Fast Web View," allowing for immediate rendering in premium PDF viewers.
- **🛡️ Elite Navigational Tools**: Integrated with `cloudscraper` and `Playwright` to navigate anti-bot protections with ease.

---

## 🛠 Prerequisites for the Study

Before you begin your curation, ensure your study is equipped with:

- **Python**: 3.9 or higher
- **Modern Tools**: [uv](https://docs.astral.sh/uv/) (Highly recommended for rapid dependency management)

---

## 📦 Installation & Setup

Clone the master repository and prepare the environment:

```powershell
git clone https://github.com/hanachimo1013/hen2pdf.git
cd hen2pdf
uv sync
```
*(Alternatively, use `pip install -r requirements.txt` if you prefer traditional methods.)*

---

## 🖥 The Curation Process (Usage)

### 1. The Main Collection (Online Acquisition)
To begin acquiring new additions to your library, execute the Grand Launcher:

```powershell
python launcher.py
```
From here, simply select your provider of choice and provide the Gallery ID or URL. The launcher will handle the rest with the grace of a head butler.

### 2. The Loose Archive Compiler (Local Salvage)
For those who possess "orphaned" archives—local `.zip` files containing precious images—this tool will normalize, curate, and bake metadata into them.

- Simply place your `.zip` files in the root directory.
- Run the `launcher.py` and select **`loose_compiler`** from the menu.
- Follow the prompts to process either individual archives or the entire collection.
- Finisher PDFs are automatically delivered to the `outputs/` gallery.

---

## 📐 Intellectual Specifications

| Parameter | Specification |
| :--- | :--- |
| **Output Format** | PDF (Optimized for high-fidelity tablets) |
| **Canvas Size** | 1600 x 2260 pixels (Uniform Padding) |
| **Compression** | JPEG 90% (Perfect balance of size and clarity) |
| **Metadata** | XMP / Dublin Core Standard |
| **Linearization** | Enabled (Stream-ready) |

---

## ⚖️ A Scholar's Agreement (License)

This project is licensed under the MIT License—use it with integrity and a refined palate.

---
**Curated by:** [hanachimo](https://github.com/hanachimo1013)
*Dedicated to the pursuit of the Luxurious Chest Collection.* 🥂
