'use client'
import { useState } from 'react';
import { doclist } from './Lists/doclist';
import { testlist } from './Lists/testlist';
import './sidebar.css';
import ParentFolder from '../folder/parentFolder';
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
    const [selected, setSelected] = useState<levelDocument|null>(null);
    const [lastInteracted, setLastInteracted] = useState<levelDocument|null>(null);
    const [softRoot, setSoftRoot] = useState<levelDocument|null>(null);

    const navItems = window.__NAV_ITEMS__||testlist;
    console.log(navItems);
    // ----------------------------------------------
    // ------------  HIERARCHY CREATION  ------------
    // ----------------------------------------------
    const dict:Document[] = [];
    const hierarchy: Document = {
      mimeType: "folder",
      name: "root",
      id: root,
      parent: null,
      children: [],
      postChildren: [], // Initialize as an empty array
      isSoftRoot: false,
      position:null,
      active: false,
      expanded: false,  
      full_path: "",
      slug: "",
    }
    const testRoot: Document = {
      mimeType: "folder",
      name: "root",
      id: root,
      parent: null,
      children: [],
      postChildren: [],
      isSoftRoot: false,
      position:null,
      active: false,
      expanded: false,  
      full_path: "",
      slug: "",
    }
    const hidden: number[] = [];
    const processList = () => {
      doclist.map((doc) => {
            let document = {
              isSoftRoot: doc.name.includes('!'),
              mimeType: doc.mimeType.split('google-apps.')[1],
              name: doc.name.includes('!')? doc.name.replace('!','') : doc.name,
              id: doc.id,
              parent: doc.parents[0], 
              children: [],
              postChildren: [],
              position:  null,
              active: false,
              expanded: false,  
              full_path: "",
              slug: "",
            };
            dict.push(document);
        });
    }
    const generateHierarchy = () => {
      processList();
      dict.forEach(document => {
        let parent = document.parent;
        if (parent === root) {
          hierarchy.postChildren?.push(document);
        } else {
          dict.find(doc => doc.id === parent)?.postChildren?.push(document);
        }
      });
    }
    if(navItems !== undefined){
      if(testRoot.postChildren === null){
        testRoot.postChildren = [];
      }
      Object.keys(navItems).forEach((key) => {
        let item = navItems[key];
        testRoot.postChildren!.push(item);
      });
    }
    generateHierarchy();
    const documents = testRoot.postChildren?.length! > 0 ? testRoot : hierarchy;
    
    
    const handleAboutClick = () => {
      const newUrl = '/' || window.location.href;
      window.location.href = newUrl;
      
    }
    
    // ----------------------------------------------
    // ----------------  RENDERING  -----------------
    // ----------------------------------------------
    return (
        <div className="mainSidebar">
          <div className='about'>
           <p className='aboutTittle' onClick={() => handleAboutClick()}>About the Library</p>
          </div>
          {documents.postChildren?.sort((a,b) => {
            if (a.position === null || b.position === null) {
              return 1;
            }
            return a.position - b.position;
          }).map((doc) => {
            if(doc.name !== 'index'){
              const processChildren = Object.keys(doc.children).map((key) => doc.children[key]);
              doc.postChildren = processChildren;
              return <ParentFolder 
                        document={doc}
                        selected={selected}
                        setSelected={setSelected}
                        hidden={hidden}
                        maxLevel={maxLevel}
                        setMaxLevel={setMaxLevel} 
                        softRoot={softRoot}
                        setSoftRoot={setSoftRoot} 
                        lastInteracted={lastInteracted}
                        setLastInteracted={setLastInteracted}
                      />;
            }
          }) }
        </div>
    )

}
export default Sidebar;
