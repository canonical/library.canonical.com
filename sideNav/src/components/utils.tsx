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

export interface levelDocument extends Document{
  level: number;
  parentId: string
}

export interface position {
  x: number;
  y: number;
}

export const MAX_NUMBER_LEVELS = 6

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
