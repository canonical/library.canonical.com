'use client'
import { useState, useEffect } from 'react';
import { Document, levelDocument, MAX_NUMBER_LEVELS, sortChildren, position } from '../utils';
import { Icon } from '@canonical/react-components';
import  Folder  from '../folder/folder';
import './folder.scss';

interface ParentFolderProps {
    document: Document;
    selected: levelDocument|null;
    setSelected: (selected: levelDocument|null) => void;
    maxLevel: number;
    setMaxLevel: (maxLevel: number) => void;
    softRoot: levelDocument|null;
    setSoftRoot: (softRoot: levelDocument|null) => void;
    lastInteracted: levelDocument|null;
    setLastInteracted: (lastInteracted: levelDocument|null) => void;
}
  
const ParentFolder: React.FC<ParentFolderProps> = ({ 
    document,
    selected, 
    setSelected,
    maxLevel, 
    setMaxLevel,
    softRoot,
    setSoftRoot, 
    lastInteracted,
    setLastInteracted,
    }) => {
    // ----------------------------------------------
    // ---------------  STATE MANAGEMENT ------------
    // ----------------------------------------------
    const [open, setOpen] = useState(document.expanded);
    const [mouseHover, setMouseHover] = useState(false);
    let level = 1;
    const parentId = document.id;
    // Manage and stores the hidden folders based on maximum level shown
    const [hiddenOptions, setHiddenOptions] = useState<levelDocument[]>([]);
    // Help separate the max level currently open per parent folder
    const [localMaxLevel, setLocalMaxLevel] = useState(1);
    // Manage and stores the opened children of the parent folder
    // so navigation is independant pero child 
    const [openedChildren, setOpenedChildren] = useState<levelDocument[]>([]);  
        // Pop Up configuration to manage the position of the pop up and its visibility
    const [position, setPosition] = useState<position>({x: 0, y: 0});
    const [openPopUp, setOpenPopUp] = useState(false);
    // ----------------------------------------------
    // ---------------  RENDER FUNCTIONS ------------
    // ----------------------------------------------
    // Render the children depending on the tipe of document (folder or file)
    const renderChildren = (doc: Document) => {
        const processChildren = Object.keys(doc.children).map((key) => doc.children[key]);
        doc.postChildren = processChildren;
        return doc.postChildren.sort((a,b) => {
            return sortChildren(a,b);
        }).map((doc) => {
            if(doc.name !== 'index'){
                return <Folder 
                        document={doc}
                        level={level+1}
                        maxLevel={maxLevel}
                        setmaxLevel={setMaxLevel}
                        selected={selected}
                        setSelected={setSelected}
                        hiddenOptions={hiddenOptions}
                        setHiddenOptions={setHiddenOptions}
                        parentId={parentId}
                        softRoot={softRoot}
                        setSoftRoot={setSoftRoot}
                        localMaxLevel={localMaxLevel}
                        setLocalMaxLevel={setLocalMaxLevel}
                        lastInteracted={lastInteracted}
                        setLastInteracted={setLastInteracted}
                        openedChildren={openedChildren}
                        setOpenedChildren={setOpenedChildren}
                        />;
            }
          });
    }

    // Render the ... and manage the lists of hidden folders 
    const renderHide = () => {
        if(selected){
            if(hiddenOptions.find(option => option.id === document.id) === undefined 
                && selected?.full_path.includes(document.slug)){
                const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
                setHiddenOptions([...hiddenOptions, levelDoc].sort((a,b) => a.level - b.level))
            }
        } else {

            if(hiddenOptions.find(option => option.id === document.id) === undefined 
                && lastInteracted && lastInteracted.full_path.includes(document.slug)){  
                const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
                setHiddenOptions([...hiddenOptions, levelDoc].sort((a,b) => a.level - b.level))
            }
        }
        if(softRoot){
            if (level === 1 && softRoot?.parentId === document.id) {
                const HandleHiddenClick = (e: React.MouseEvent<HTMLDivElement>) => {
                    setPosition({x: e.clientX -10, y: e.clientY -10});
                    setOpenPopUp(true);
                };
                return (
                <div className="navigation__hidden-options" onClick={(e) => HandleHiddenClick(e)}>... </div>
                )
            }
        }
        if (level === 1 && lastInteracted && lastInteracted.parentId === document.id) {
            const HandleHiddenClick = (e: React.MouseEvent<HTMLDivElement>) => {
                setPosition({x: e.clientX, y: e.clientY});
                setOpenPopUp(true);
            };
            return (
            <div className="navigation__hidden-options" onClick={(e) => HandleHiddenClick(e)}>... </div>
            )
        }
        
        return null;
    }

    // Render the pop up with the hidden folders
    // Manages the states based on the selection of a folder
    const renderPopUp = () => {
        // Handles States so local max level, the max level, selected files, hidden, and opened children to match the selection
        const handelOptionClick = (option: levelDocument) => {
            setLocalMaxLevel(option.level+1 );
            setMaxLevel(1);
            setHiddenOptions([]);
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
    // Render the tittle of a selected Child that is no longer visible by navigation
    // E.G selected document is level 7 but navigation is only up to level 3 
    // This will shoe ... Tittle (selected document)
    const renderHiddenChild = () => {
        const padding = localMaxLevel*2;
        const handleClick = () => {
            setLocalMaxLevel(selected ? selected.level: 1);
            setMaxLevel(selected ? selected.level: 1);
            const newUrl = selected?.full_path || window.location.href;
            window.location.href = newUrl;
        }
        return (
            <div className="navigation__slected-hidden-option" onClick={() => handleClick()} style={{paddingLeft: selected ? padding + "rem" : "0px"}}>... ({selected?.name}) </div>
        )
    }
    // ----------------------------------------------
    // ---------------  USE EFFECTS ----------------
    // ----------------------------------------------
    useEffect(() => {
        if(document.active){
            setSelected({...document, 'level': level, 'parentId': parentId});
            if(localMaxLevel<level){
                setLocalMaxLevel(level);
            }
            if(document.isSoftRoot){
                if(localMaxLevel<level){
                    setLocalMaxLevel(level);
                }
                setSoftRoot({...document, 'level': level, 'parentId': parentId});
            }
        }
    },[])

    // ----------------------------------------------
    // ---------------  HANDLER FUNCTIONS -----------
    // ----------------------------------------------
    // On click of the folder tittle, the folder is selected and it is open to show its children
    // If the folder is not in the opened children, it is added to the list
    const handleFolderClick = (doc : Document) => {
        if(document.isSoftRoot){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setSoftRoot(levelDoc);
            localStorage.setItem('softRoot', JSON.stringify(levelDoc));
        }
        if(level< localMaxLevel){
            const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
            setSelected({...levelDoc});
        } else {
            const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
            setSelected({...levelDoc});
            setLocalMaxLevel(localMaxLevel + 1)
        }
        if(openedChildren.find(option => option.id === doc.id) === undefined){
            setOpenedChildren([...openedChildren, {...doc, 'level': level, 'parentId': parentId}])
        }
        setLastInteracted({...doc, 'level': level, 'parentId': parentId});
        const newUrl = doc.full_path || window.location.href;
        window.location.href = newUrl;
        setOpen(true);
    }

    // On click of the chevron, if the folder is closed,it will open and show its children
    // If the folder is open, it will close and remove its children from the opened
    // children list
    // The click in the chevron updates the max level shown but does not select the current folder
    const handleChevronClick = () => {
        if(open){
            setLocalMaxLevel(level);
            const idxOC = openedChildren.findIndex(opt => opt.name === document.name);
            const tempOpenedChildren = [...openedChildren].slice(0,idxOC);
            setOpenedChildren(tempOpenedChildren);
        }else if(level >= maxLevel){
            setLocalMaxLevel(localMaxLevel + 1)
        }
        if(!open){
            if(openedChildren.find(option => option.id === document.id) === undefined){
                setOpenedChildren([...openedChildren, {...document, 'level': level, 'parentId': parentId}])
            }
        }
        setOpen(!open);
        setLastInteracted({...document, 'level': level, 'parentId': parentId});
    } 

    // ----------------------------------------------
    // -------  MANAGE HIDDING CONDITIONS -----------
    // ----------------------------------------------
    if(maxLevel !== localMaxLevel && localMaxLevel - level >= MAX_NUMBER_LEVELS){
        setMaxLevel(localMaxLevel);
    } 
    const levelcondition = maxLevel - level >= MAX_NUMBER_LEVELS;
    const hideLevel = levelcondition ||(softRoot !== null && document.id !== softRoot.id);
    const hiddenChild =  selected &&selected.level > localMaxLevel && selected.parentId === parentId && selected.id !== lastInteracted?.id; 
    const backgroundColor = document.active || mouseHover ?'#c4c4c4': '#EBEBEB';

    return (
        <>
        { hideLevel  ?
        renderHide()
        :
        <div 
            className="navigation__folder" 
            onMouseEnter={() =>setMouseHover(true)} 
            onMouseLeave={() => setMouseHover(false)}
            style={{backgroundColor: backgroundColor, paddingLeft:"1.69rem"}}
            >
            {( Object.keys(document.children).length > 1) ? 
            <div onClick={() => handleChevronClick()}>{open ?
            <Icon name='chevron-down'/>
            : <Icon name='chevron-right'/>}
            </div> 
            : null}
            <a href={document.full_path} className='navigation__link' style={{textDecoration: 'none'}}>
                <span className='navigation__folder-tittle'  style={{paddingLeft: document.mimeType === 'folder' && Object.keys(document.children).length > 1 ? "0.5rem" : "1.5rem" }} onClick={() => handleFolderClick(document)}>{document.name}</span>
            </a>
        </div>
        }
        <div style={{paddingLeft: hideLevel? '0' : '2rem'}}>
            {open && renderChildren(document)
            } 
        </div>
        {openPopUp && renderPopUp()}
        {(hiddenChild) 
            &&
            <div id='hiddenContainer' style={{paddingLeft:'1.2rem'}}>
                {renderHiddenChild()}
            </div>
        } 
        </>
    )

}
export default ParentFolder;