# Export Folder to PDF: Technical Guide

Folder to PDF script performs a recursive merge of Google Documents within a folder structure and exports the result as a single PDF.

## How It Works
The script follows a "Depth-First Search" logic to navigate your folders:
1. In every folder, it identifies the "index" file first (default config excludes the index pages from output).
2. It gathers all other Google Docs within the current folder level and sorts them alphabetically. (Custom numbered sorting is maintained)
3. It repeats this logic for every subfolder it finds, ensuring the folder structure is mirrored in the document order.
4. During the merge, it removes the first table (Metadata table) of every document. Because it uses the `copy()` method, your original files remain untouched.
5. Implements Vanilla styles so that the document maintains the consistent styles throughtout the new document.
6. To run, access the [script](https://script.google.com/home/projects/12d3AD3fNNel-a_5Alt07IsVBur_NUI_0fOuOx-TaKRy-6L6BF-GZkXPw/edit) and click `Run` (located in the header bar) after all the configurations have been made. 

---

## Configuration and Modification

### 1. Changing Folder Locations
To point the script to different folders, update these two IDs at the top of the script:
* **rootFolderId**: The starting point folder ID. (e.g. `1F6fsOwSS98KQOuv87zZaMNiTIWUtMfU9`)
* **destFolderId**: The folder ID where the final PDF will be saved. (e.g. `1lNbsdR3ikQsZUqd-fsgIB2XyBS22coPd`)
* **rootFolderPath**: This is the path of the folder in the library/ (e.g. `library.canonical.com/our-organization`)
* **

### 2. Changing the Index Logic
Inside the `processFolderRecursive` function, you can toggle how the "index" file is handled:
* **To include index files:** Uncomment `appendDocToMaster` and `masterBody.appendPageBreak()` inside Part A.
* **To change the trigger name:** Change the string `'index'` to your preferred filename.

### 3. Output Customization
* **Page Breaks:** To remove the gap between merged documents, comment out the `masterBody.appendPageBreak()` command with //.
* **Output Name:** Modify the variable `destinationFolderName` which has a value of `'Final_Ordered_Document'` in the `mergeFolderToPdf` function to change the filename.

---

## Technical Limitations
* **MIME Type Restriction:** The script only processes native Google Docs. PDFs or Word files (.docx) stored in the folder will be ignored unless converted to Google Docs files.
* **Element Compatibility:** The script handles Paragraphs, Tables, List Items, and Inline Images. Specialized elements like Drawings or certain Apps Script gadgets may not transfer.

---

## Function Reference

| Function | Purpose |
| :--- | :--- |
| mergeFolderToPdf | The main entry point. Handles setup, export, and cleanup of the temporary master file. |
| processFolderRecursive | The logic engine. Manages the priority of files and dives into subfolders. |
| appendDocToMaster | The extraction tool. Clones elements from source to master and applies the table-skipping rule. |
| applyVanillaStyles | This function applies the Vanilla styles used in the library to the doc to maintain the style throughout the whole document. |
|extractAndIdentifyUrls| This function applies changes to library links that got transformed into pdf, so that links show bookmarks withing pdfs. |
