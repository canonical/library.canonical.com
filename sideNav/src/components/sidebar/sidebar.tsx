'use client'
import { useState, useEffect } from 'react';
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
interface position {
  x: number;
  y: number;
}
export const MAX_NUMBER_LEVELS = 6

export interface sidebarProps {
  documents?: any,
}


const Sidebar: React.FC<sidebarProps> = ({
}) => {
    const root = "1QLSNL1QhMMHJmDVFyTXoQ2V6RBtc8mjx";
    const tempSoftRoot = localStorage.getItem('softRoot')=== 'null'? null: JSON.parse(localStorage.getItem('softRoot') as string);
    // ----------------------------------------------
    // ---------------  STATE MANAGEMENT ------------
    // ----------------------------------------------
    const [maxLevel, setMaxLevel] = useState(1);
    const [selected, setSelected] = useState<levelDocument|null>(null);
    const [lastInteracted, setLastInteracted] = useState<levelDocument|null>(null);
    const [softRoot, setSoftRoot] = useState<levelDocument|null>(tempSoftRoot || null);
    const [softRootChildren, setSoftRootChildren] = useState<levelDocument[]>([]);
    // Pop Up configuration to manage the position of the pop up and its visibility
    const [position, setPosition] = useState<position>({x: 0, y: 0});
    const [openPopUp, setOpenPopUp] = useState(false);
    const [hiddenOptions, setHiddenOptions] = useState<levelDocument[]>([]);

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

    // ----------------------------------------------
    // ---------------  USE EFFECTS ----------------
    // ----------------------------------------------
    useEffect(() => {
      if(softRoot && testRoot.postChildren?.find(doc => doc.id === softRoot.id)){
        setHiddenOptions(testRoot.postChildren?.filter(doc => (doc.id !== softRoot.id && doc.name !== 'index')) as levelDocument[]);
      }
    },[softRoot])

    // ----------------------------------------------
    // ---------------  RENDER FUNCTIONS ------------
    // ----------------------------------------------
    // Render the pop up with the hidden folders
    // Manages the states based on the selection of a folder
    const renderPopUp = () => {
        // Handles States so local max level, the max level, selected files, hidden, and opened children to match the selection
        const handelOptionClick = (option: levelDocument) => {
            setMaxLevel(1);
            setOpenPopUp(false);
            setSoftRoot(null);
            localStorage.setItem('softRoot', 'null');
            const newUrl = option.full_path || window.location.href;
            window.location.href = newUrl;
        }   
        // Closes the popUp when the mouse leaves
        const handleMouseLeave = () => {
            setPosition({x: 0, y: 0}); 
            setOpenPopUp(false);
        }
        if(position.y > 152){
            position.y = position.y - 152;
        }
        return (
            <div className='navigation__popup' style={{top: position.y, left: position.x}} onMouseLeave={() => handleMouseLeave()}>
                {hiddenOptions.sort((a,b) => a.level - b.level).map(option => {
                    return <div className='navigation__popup-tittle ' onClick={() => handelOptionClick(option)}>{option.name}</div>
                })}
            </div>
        )
    }

    // Render the ... and manage the lists of hidden folders 
    const renderHide = () => {
      if(softRoot){
        const HandleHiddenClick = (e: React.MouseEvent<HTMLDivElement>) => {
        setPosition({x: e.clientX - 10, y: e.clientY - 10});
        setOpenPopUp(true);
        };
        return (
          <div className="navigation__hidden-options" onClick={(e) => HandleHiddenClick(e)}>... </div>
        )
      }
      return null;
    }
    // ----------------------------------------------
    // ---------------  HANDLER FUNCTIONS -----------
    // ----------------------------------------------
    const handleAboutClick = () => {
      const newUrl = '/';
      window.location.href = newUrl;
      
    }
    console.log(testRoot)
    console.log(softRoot)
    console.log(softRootChildren)
    // ----------------------------------------------
    // ----------------  RENDERING  -----------------
    // ----------------------------------------------
    return (
        <div className="navigation">
          <div className='navigation__about-container'>
           <p className='navigation__about-tittle' onClick={() => handleAboutClick()}>About the Library</p>
          </div>
          <div>
          {(softRoot && testRoot.postChildren?.find((elem) => elem.id === softRoot.id)) && renderHide()}
          {testRoot.postChildren?.sort((a,b) => {
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
                        position={position}
                        setPosition={setPosition}
                        openPopUp={openPopUp}
                        setOpenPopUp={setOpenPopUp}
                        softRootChildren={softRootChildren}
                        setSoftRootChildren={setSoftRootChildren}
                      />;
            }
          })}
          </div>
          {openPopUp && renderPopUp()}
        </div>
    )

}
export default Sidebar;
