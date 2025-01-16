'use client'
import { useState, useEffect } from 'react';
import { testlist } from './Lists/testlist';
import './sidebar.scss';
import ParentFolder from '../folder-components/parentFolder';
import { sortChildren, levelDocument, position, Document } from '../utils';

interface sidebarProps {
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
    // Pop Up configuration to manage the position of the pop up and its visibility
    const [positionRoot, setPositionRoot] = useState<position>({x: 0, y: 0});
    const [openPopUpRoot, setOpenPopUpRoot] = useState(false);
    // Pop up options specific for the softRoot
    const [hiddenOptionsRoot, setHiddenOptionsRoot] = useState<levelDocument[]>([]);

    //Hover for about the library
    const [mouseHover,setMouseHover] = useState<boolean>(false);

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
        setHiddenOptionsRoot(testRoot.postChildren?.filter(doc => (doc.id !== softRoot.id && doc.name !== 'index')) as levelDocument[]);
      }
    },[softRoot])

    useEffect(() => {
      if(localStorage.getItem('softRoot') === null || localStorage.getItem('softRoot') === '' || localStorage.getItem('softRoot') === undefined){
        localStorage.setItem('softRoot', 'null');
        setSoftRoot(null);
      }
    },[])

    // ----------------------------------------------
    // ---------------  RENDER FUNCTIONS ------------
    // ----------------------------------------------
    // Render the pop up with the hidden folders
    // Manages the states based on the selection of a folder
    const renderPopUp = () => {
        // Handles States so local max level, the max level, selected files, hidden, and opened children to match the selection
        const handelOptionClick = (option: levelDocument) => {
            setMaxLevel(1);
            setOpenPopUpRoot(false);
            setSoftRoot(null);
            localStorage.setItem('softRoot', 'null');
            const newUrl = option.full_path || window.location.href;
            window.location.href = newUrl;
        }   
        // Closes the popUp when the mouse leaves
        const handleMouseLeave = () => {
            setPositionRoot({x: 0, y: 0}); 
            setOpenPopUpRoot(false);
        }
        if(positionRoot.y > 152){
            positionRoot.y = positionRoot.y - 152;
        }
        return (
            <div className='navigation__popup' style={{top: positionRoot.y, left: positionRoot.x}} onMouseLeave={() => handleMouseLeave()}>
                {hiddenOptionsRoot.sort((a,b) => a.level - b.level).map(option => {
                    return <div className='navigation__popup-tittle ' onClick={() => handelOptionClick(option)}>{option.name}</div>
                })}
            </div>
        )
    }

    // Render the ... and manage the lists of hidden folders 
    const renderHide = () => {
      if(softRoot){
        const HandleHiddenClick = (e: React.MouseEvent<HTMLDivElement>) => {
        setPositionRoot({x: e.clientX - 10, y: e.clientY - 10});
        setOpenPopUpRoot(true);
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
      localStorage.setItem('softRoot', 'null');
      const newUrl = '/';
      window.location.href = newUrl;
      
    }

    // Show the hidden folders when the softRoot is selected
    // from one of the parent folders
    const showHidden = softRoot && testRoot.postChildren?.find((elem) => elem.id === softRoot.id) !== undefined;
    const activeChild = testRoot.postChildren?.find((elem) => elem.active);

    if(activeChild && activeChild.name === 'index' && localStorage.getItem('softRoot') !== 'null'){
      localStorage.setItem('softRoot', 'null');
      setSoftRoot(null);
    }
    // ----------------------------------------------
    // ----------------  RENDERING  -----------------
    // ----------------------------------------------
    const aboutSelected = window.location.pathname === "/";
    const backgroundColor = aboutSelected || mouseHover ?'#c4c4c4': '#EBEBEB';
    return (
        <div className="navigation">
          <div className='navigation__about-container'
          onMouseEnter={() => setMouseHover(true)}
          onMouseLeave={() => setMouseHover(false)}
          style = {{
            backgroundColor: backgroundColor,
            borderLeftColor: "black",
            borderLeftStyle:'solid',
            borderLeftWidth: aboutSelected? '2px': "0px"
          }} 
          >
           <p className='navigation__about-tittle' 
           onClick={() => handleAboutClick()}
           >About the Library</p>
          </div>
          <div>
          {showHidden && renderHide()}
          {testRoot.postChildren?.sort((a,b) => {
            return sortChildren(a,b);
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
          })}
          </div>
          {openPopUpRoot && renderPopUp()}
        </div>
    )

}
export default Sidebar;
