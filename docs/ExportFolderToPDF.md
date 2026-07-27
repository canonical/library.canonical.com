# Export Folder to PDF: Technical Guide

This Google Apps Script performs a recursive merge of all Google Documents within a target Google Drive folder hierarchy, applies standardized Canonical Vanilla styling, optimizes web hyperlinks, and exports the merged output as a single PDF.

---

## How It Works

The script operates through a **Depth-First Search (DFS)** folder traversal and multi-stage document processing pipeline:

1. **Folder & File Navigation:**
   * In every folder level, the script fetches all native Google Docs.
   * Documents are sorted using a custom comparator (`compareFilesWithIndexFirst`) that **prioritizes any file named `index` to the top** before sorting the remaining files alphabetically.
   * The script recursively traverses into subfolders, applying the same index-first alphabetical sorting to folder names.

2. **Document Merging & Content Filtering:**
   * Every document is appended sequentially into a temporary master document.
   * **Metadata Table Removal:** The script automatically skips the **first table** of every source document (typically used for internal document metadata).
   * **Page Breaks:** A page break is inserted after each merged document.
   * **File Exclusion:** Specific files can be bypassed by name (currently set to ignore `"30-Leave booking guidance"`).

3. **Vanilla Brand Styling:**
   * Global page margins are set to 36pt (0.5 inches).
   * Paragraphs and List Items are formatted using Canonical's Vanilla typography rules:
     * **Font Family:** Ubuntu
     * **Body Text:** 10.5pt, 1.15 Line Spacing
     * **Headings (H1–H6):** Scaled from 24pt down to 13.5pt with bold toggles applied to odd-numbered headings.

4. **High-Performance Link Optimization:**
   * The script scans all hyperlinks pointing to `rootFolderPath`.
   * **In-Memory Indexing:** To prevent Google Apps Script execution timeouts (6-minute limit), the entire document's text is indexed into a local JavaScript array in a single pass.
   * If a hyperlink points to a topic or heading **that now lives directly inside this merged document**, the hyperlink is stripped (`setLinkUrl(..., null)`), leaving plain text to prevent broken external links in a self-contained PDF.
   * If the target content is not in this document, the link remains intact as an active external link.

5. **Export & Cleanup:**
   * The temporary Google Doc is compiled, saved, and converted to a `.pdf` blob.
   * The PDF is saved to the designated destination folder, and the temporary master Google Doc is moved to the trash.

---

## Configuration Reference

### 1. Key Script Variables
Located at the top of the `mergeFolderToPdf` function:

* `rootFolderId`: The Google Drive Folder ID containing the source Google Docs.
* `destFolderId`: The Google Drive Folder ID where the final PDF will be saved.
* `rootFolderPath`: The base URL prefix (e.g., `[https://library.canonical.com/working-at-canonical/benefits](https://library.canonical.com/working-at-canonical/benefits)`) used to identify internal library hyperlinks.
* `outputFileName`: The name assigned to the generated file (currently set to `'Canonical_Benefits2'`).

### 2. File Exclusion
Inside `processFolderRecursive`, you can customize which files are omitted during compilation:
```javascript
if (file.getName() != "30-Leave booking guidance") {
  appendDocToMaster(file.getId(), masterBody);
  masterBody.appendPageBreak();
}
```

---

## Technical Safeguards & Limitations

* **Timeout Protection:** The link optimization step is wrapped in a `try...catch` block. If link processing fails or hits an unexpected edge case, the script catches the warning and safely proceeds to generate the PDF anyway.
* **MIME Type Restriction:** Only native Google Docs (`MimeType.GOOGLE_DOCS`) are processed. Static files like Word (`.docx`), PDFs, or images stored in the Drive folders are skipped.
* **Supported Elements:** The script copies Paragraphs, Tables (excluding the first table), List Items, and Inline Images. Non-standard elements (e.g., Google Drawings, embedded forms, or Apps Script widgets) are not supported by the DocumentApp copy pipeline.

---

## Function Reference

| Function | Description |
| :--- | :--- |
| `mergeFolderToPdf()` | **Main Entry Point.** Controls initial setup, recursive compilation triggers, link optimization, PDF export, and temporary file deletion. |
| `compareFilesWithIndexFirst(a, b)` | Custom sorting algorithm that forces files or folders named `index` to the top of the processing list, then sorts the rest alphanumerically. |
| `processFolderRecursive(folder, masterBody)` | Hierarchical folder engine. Sorts files/folders at the current depth, appends files to the master document, and recurses into subdirectories. |
| `appendDocToMaster(sourceId, masterBody)` | Clones structural elements (Paragraphs, Tables, Lists, Images) from a source Google Doc into the master body while applying table-skipping rules. |
| `applyVanillaStyles(element)` | Applies Canonical's Ubuntu typography hierarchy (font family, line spacing, font sizes) to appended text elements. |
| `extractAndIdentifyUrls(doc, rootFolderPath)` | Indexes the merged document in memory, identifies internal library URLs, and strips hyperlinks for content already contained within the PDF. |