'use client'
import { useState } from 'react';
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


    // TODO: Implement a backend call to get the list of documents
    const navItems = window.__NAV_ITEMS__||testlist;
    // ----------------------------------------------
    // ------------  HIERARCHY CREATION  ------------
    // ----------------------------------------------
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
    
    if(navItems !== undefined){
      if(testRoot.postChildren === null){
        testRoot.postChildren = [];
      }
      Object.keys(navItems).forEach((key) => {
        let item = navItems[key];
        testRoot.postChildren!.push(item);
      });
    }
    
    
    const handleAboutClick = () => {
      const newUrl = '/';
      window.location.href = newUrl;
      
    }
    // ----------------------------------------------
    // ----------------  RENDERING  -----------------
    // ----------------------------------------------
    return (
        <div className="navigation">
          <div className='navigation__about-container'>
           <p className='navigation__about-tittle' onClick={() => handleAboutClick()}>About the Library</p>
          </div>
          {testRoot.postChildren?.sort((a,b) => {
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
