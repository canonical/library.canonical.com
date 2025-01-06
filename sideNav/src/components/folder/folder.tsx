'use client'
import { useEffect, useState } from 'react';
import { ExpandMore, ChevronRight} from '@mui/icons-material';
import { Document, MAX_NUMBER_LEVELS, levelDocument, sortChildren } from '../utils';
import './folder.css';

interface FolderProps {
    document: Document;
    level: number;
    maxLevel: number;
    setmaxLevel: (maxLevel: number) => void;
    selected: levelDocument|null;
    setSelected: (selected: levelDocument|null) => void;
    hiddenOptions: levelDocument[];
    setHiddenOptions: (hiddenOptions: levelDocument[]) => void;
    parentId: string;
    softRoot: levelDocument|null;
    setSoftRoot: (softRoot: levelDocument|null) => void;
    localMaxLevel: number;
    setLocalMaxLevel: (maxLevel: number) => void;
    lastInteracted: levelDocument|null;
    setLastInteracted: (lastInteracted: levelDocument|null) => void;
    openedChildren: levelDocument[];
    setOpenedChildren: (openedChildren: levelDocument[]) => void;
}

const Folder: React.FC<FolderProps> = ({ 
    document,
    level,
    maxLevel,
    setmaxLevel, 
    selected, 
    setSelected,
    hiddenOptions, 
    setHiddenOptions, 
    parentId, 
    softRoot, 
    setSoftRoot, 
    setLocalMaxLevel, 
    localMaxLevel, 
    lastInteracted, 
    setLastInteracted,
    openedChildren,
    setOpenedChildren,
    }) => {
    // ----------------------------------------------
    // ---------------  STATE MANAGEMENT ------------
    // ----------------------------------------------
    const [open, setOpen] = useState(document.expanded);
    const [mouseHover, setMouseHover] = useState(false);

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
                        setmaxLevel={setmaxLevel}
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
    // Manage the lists of hidden folders 
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
        
        return null;
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
    const handleFolderClick = (doc: Document) => {
        if(softRoot){
            localStorage.setItem('softRoot', JSON.stringify(softRoot));
        }
        if(document.isSoftRoot){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setSoftRoot(levelDoc);
            localStorage.setItem('softRoot', JSON.stringify(levelDoc));
        }
        if(level< maxLevel){
            const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
            setSelected({...levelDoc});
        } else {
            const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
            setSelected({...levelDoc});
            if(!open){
                setLocalMaxLevel(localMaxLevel + 1)
            }
        }
        if(openedChildren.find(option => option.id === doc.id) === undefined){
            setOpenedChildren([...openedChildren, {...doc, 'level': level, 'parentId': parentId}])
        }
        setLastInteracted({...doc, 'level': level, 'parentId': parentId});
        const newUrl = doc.full_path || window.location.href;
        window.location.href = newUrl;
        setOpen(true)
    }
    // On click of the chevron, if the folder is closed,it will open and show its children
    // If the folder is open, it will close and remove its children from the opened
    // children list
    // The click in the chevron updates the max level shown but does not select the current folder
    const handleChevronClick = () => {
        if(open){
            setLocalMaxLevel(level);
            setmaxLevel(1);
            const idxOC = openedChildren.findIndex(opt => opt.name === document.name);
            const tempOpenedChildren = [...openedChildren].slice(0,idxOC);
            setOpenedChildren(tempOpenedChildren);
        }else if(level >= localMaxLevel){
            setLocalMaxLevel(localMaxLevel + 1)
        }
        if(!open){
            if(openedChildren.find(option => option.id === document.id) === undefined){
                setOpenedChildren([...openedChildren, {...document, 'level': level, 'parentId': parentId}])
            }
        }
        setLastInteracted({...document, 'level': level, 'parentId': parentId});
        setOpen(!open);
    }
    // ----------------------------------------------
    // -------  MANAGE HIDDING CONDITIONS -----------
    // ---------------------------------------------- 
    const levelcondition = maxLevel - level >= MAX_NUMBER_LEVELS;
    const isChildSoft = softRoot !== null && level > softRoot.level && parentId === softRoot.parentId;
    let hideLevel = levelcondition ||(softRoot !== null && document.id !== softRoot.id);
    if(isChildSoft){ 
        hideLevel = false;
    }

    const backgroundColor = document.active || mouseHover ?'#c4c4c4': '#EBEBEB'
    return (
        <>
        { hideLevel ?
        renderHide()
        :
        <div 
            className="navigation__folder"
            onMouseEnter={() =>setMouseHover(true)} 
            onMouseLeave={() => setMouseHover(false)}
            style={{backgroundColor: backgroundColor, paddingLeft:document.mimeType === 'folder' &&  Object.keys(document.children).length > 1 ? '2%': '5%'}} 
            >
            {(document.mimeType === 'folder' &&  Object.keys(document.children).length > 1) ? 
            <div onClick={() => handleChevronClick()}>{open ?
            <ExpandMore/>
            : <ChevronRight/>}
            </div>
            :null}
            <a href={document.full_path} className='navigation__link'>
                <span className='navigation__folder-tittle' onClick={() => handleFolderClick(document)}>{document.name}</span>
            </a>
        </div>
        }
        <div style={{paddingLeft: hideLevel? '0' : '5%'}}>
            {open && renderChildren(document)
            }
        </div>
        </>
    )

}
export default Folder;