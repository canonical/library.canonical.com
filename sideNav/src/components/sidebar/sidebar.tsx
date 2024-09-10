'use client'
import { useState } from 'react';
import { doclist } from './Lists/doclist';
import './sidebar.css';
import ParentFolder from '../folder/parentFolder';
export interface Document {
    type: string;
    name: string;
    id: string;
    parent: string|null;
    children: Document[];
    isSoftRoot: boolean;
}
export interface levelDocument extends Document{
  level: number;
  parentId: string
}
export interface selectedDocument extends levelDocument{
  breadcrumb: levelDocument[];
}
export const MAX_NUMBER_LEVELS = 6

export interface sidebarProps {
  documents?: any,
}


const Sidebar: React.FC<sidebarProps> = ({
}) => {
    const root = "1QLSNL1QhMMHJmDVFyTXoQ2V6RBtc8mjx";
    // ----------------------------------------------
    // ---------------  STATE MANAGEMENT ------------
    // ----------------------------------------------
    const [maxLevel, setMaxLevel] = useState(1);
    const [selected, setSelected] = useState<selectedDocument|null>(null);
    const [softRoot, setSoftRoot] = useState<levelDocument|null>(null);

    const navItems = window.__NAV_ITEMS__;
    const previousSlug = window.__PREVIOUS_SLUG__;
    console.log(navItems);
    console.log(previousSlug);
    // ----------------------------------------------
    // ------------  HIERARCHY CREATION  ------------
    // ----------------------------------------------
    const dict:Document[] = [];
    const hierarchy: Document = {
      type: "folder",
      name: "root",
      id: root,
      parent: null,
      children: [],
      isSoftRoot: false,
    }
    const testRoot: Document = {
      type: "folder",
      name: "root",
      id: root,
      parent: null,
      children: [],
      isSoftRoot: false,
    }
    const hidden: number[] = [];
    const processList = () => {
      doclist.map((doc) => {
            let document = {
              isSoftRoot: doc.name.includes('!'),
              type: doc.mimeType.split('google-apps.')[1],
              name: doc.name.includes('!')? doc.name.replace('!','') : doc.name,
              id: doc.id,
              parent: doc.parents[0], 
              children: [],
            };
            dict.push(document);
        });
    }
    const generateHierarchy = () => {
      processList();
      dict.forEach(document => {
        let parent = document.parent;
        if (parent === root) {
          hierarchy.children.push(document);
        } else {
          dict.find(doc => doc.id === parent)?.children.push(document);
        }
      });
    }
    if(navItems !== undefined){
      Object.keys(navItems).forEach((key) => {
        let item = navItems[key];
        testRoot.children.push(item);
      });
    }
    generateHierarchy();
    console.log(hierarchy);
    console.log(testRoot);
    // ----------------------------------------------
    // ----------------  RENDERING  -----------------
    // ----------------------------------------------
    return (
        <div className="mainSidebar">
          {hierarchy.children.map((doc) => {
            return <ParentFolder 
                      document={doc}
                      selected={selected}
                      setSelected={setSelected}
                      hidden={hidden}
                      maxLevel={maxLevel}
                      setMaxLevel={setMaxLevel} 
                      softRoot={softRoot}
                      setSoftRoot={setSoftRoot} 
                    />;
          }) }
        </div>
    )

}
export default Sidebar;
