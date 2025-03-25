// ----------------------------------------------
// ---------------  UTILS  ----------------------
// ----------------------------------------------

// Document is the basic type for the google docs 
// received from the API
export interface Document {
    mimeType: string;
    name: string;
    id: string;
    parent: string|null;
    children: any;
    postChildren: Document[]|null;
    isSoftRoot: boolean;
    position: number|null;
    active?: boolean;
    expanded?: boolean;
    full_path: string;
    slug: string;
}

// levelDocument is a Document with the level and the parentId
export interface levelDocument extends Document{
  level: number;
  parentId: string
}

// position is the x and y coordinates of the pop up
// for the soft root menu
export interface position {
  x: number;
  y: number;
}

// Max levels of the hierarchy before levels get hidden
export const MAX_NUMBER_LEVELS = 6;

export const PADDING_CONSTANT = 2;

export const MOBILE_VIEW_WIDTH = 1035;

// Function to sort the children of a document
export function sortChildren(a: Document, b: Document): number {
    if (a.position === null && b.position === null) {
        return a.name.localeCompare(b.name);
    }
    if (a.position === null && b.position !== null) {
        return 1;
    }
    if (a.position !== null && b.position === null) {
        return -1;
    }
    return (a.position ?? 0) - (b.position ?? 0);
}
