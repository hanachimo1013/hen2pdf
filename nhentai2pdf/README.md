# 🏛️ nhentai2pdf: Luxurious Archive

A high-performance, asynchronous Python utility designed to fetch, normalize, and archive galleries into a structured PDF format. Optimized for local Google Drive synchronization, high-fidelity viewing, and memory efficiency across extremely large multi-hundred page archives.

## ✨ Key Features
* **Official V2 API Integration:** Uses the nhentai API for accurate metadata and precise image extension handling (no more probing).
* **Asynchronous Downloads:** Utilizes `aiohttp` and `asyncio` for high-speed concurrent fetching.
* **Resilient Connectivity:** Automatically catches and retries failed downloads caused by intermittently timeouts or client drops.
* **Universal Format Support:** Correctly handles JPG, PNG, and WebP pages without trial-and-error.
* **Aspect Ratio Normalization:** Every page is centered on a uniform 1600x2260 canvas to prevent "jumping" during reading.
* **Metadata Injection:** Bakes Artist, Title, Language, and Tags directly into the PDF metadata via `pikepdf`.
* **Smart Storage Management:** Automatically checks for your `G:\` Google Drive availability and write-access, seamlessly falling back to a local `outputs` folder if needed.
* **Reliable Metadata Injection:** Handles race conditions with cloud/network drives, ensuring metadata is successfully baked even if the drive lags during the save process.
* **Strict Integrity Check:** Aborts compilation if a page critically fails to download, ensuring 100% complete archives.

## 🛠️ Prerequisites

Ensure you have [uv](https://docs.astral.sh/uv/) installed. You can set up the environment with:

```powershell
uv sync
```

## 🚀 Usage

Run the tool directly through `uv run`:

```powershell
uv run nh2pdf <6-digit-code>
```

Alternatively, run as a standard Python script:

```powershell
python nhentai2pdf.py <6-digit-code>
```

### Execution Flow:
1. **Metadata Fetch:** Connects to the V2 API and displays Title, Artist, Language, and Page Count.
2. **Handshake:** Confirms the download via `[Enter to Continue / n to Cancel]`.
3. **Download:** Pages are fetched asynchronously into a temporary directory with retry logic.
4. **Processing & Export:** Images are normalized to a uniform `1600x2260` canvas and compiled into a high-quality PDF.
5. **Finalization:** Metadata is injected and the PDF is linearized for fast web viewing.

## 📁 Project Structure
* `nhentai2pdf.py`: The core architect script.
* `pyproject.toml`:uv-ready project configuration.
* `temp_XXXXXX/`: Temporary storage for raw images (auto-cleaned).
* **Outputs:** Defaults to `./outputs`.

---
*Created for the Luxurious Chest Collection. 😏*
