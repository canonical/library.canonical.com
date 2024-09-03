'use client'
import { useEffect, useState } from 'react';
import { ExpandMore, ChevronRight} from '@mui/icons-material';
import { Document, MAX_NUMBER_LEVELS, selectedDocument } from '../sidebar/sidebar';
import File from '../file/file';

import './folder.css';
import { levelDocument } from '../sidebar/sidebar';

interface FolderProps {
    document: Document;
    level: number;
    hidden: number[];
    maxLevel: number;
    setmaxLevel: (maxLevel: number) => void;
    selected: selectedDocument|null;
    setSelected: (selected: selectedDocument|null) => void;
    hiddenOptions: levelDocument[];
    setHiddenOptions: (hiddenOptions: levelDocument[]) => void;
    parentId: string;
    softRoot: levelDocument|null;
    setSoftRoot: (softRoot: levelDocument|null) => void;
    localMaxLevel: number;
    setLocalMaxLevel: (maxLevel: number) => void;
    breadcrumb: levelDocument[];
    setBreadcrumb: (breadcrumb: levelDocument[]) => void;
    openedChildren: levelDocument[];
    setOpenedChildren: (openedChildren: levelDocument[]) => void;
  }

const Folder: React.FC<FolderProps> = ({ 
    document,
    level,
    hidden,
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
    breadcrumb, 
    setBreadcrumb,
    openedChildren,
    setOpenedChildren,
    }) => {
    // ----------------------------------------------
    // ---------------  STATE MANAGEMENT ------------
    // ----------------------------------------------
    const [open, setOpen] = useState(false);

    // ----------------------------------------------
    // ---------------  RENDER FUNCTIONS ------------
    // ----------------------------------------------
    // Render the children depending on the tipe of document (folder or file)
    const renderChildren = (doc: Document) => {
        
        return doc.children.map((doc) => {
            if(doc.type === 'document') {
                return <File
                document={doc}
                selected={selected}
                setSelected={setSelected}
                level={level+1}
                parentId={parentId}
                breadcrumb={breadcrumb}
                setBreadcrumb={setBreadcrumb}
                />;
            }

            return <Folder
                    document={doc}
                    level={level+1}
                    hidden={hidden}
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
                    breadcrumb={breadcrumb}
                    setBreadcrumb={setBreadcrumb}
                    openedChildren={openedChildren}
                    setOpenedChildren={setOpenedChildren}  
                    />;
          });
    }
    // Manage the lists of hidden folders 
    const renderHide = () => {
        
        if(hiddenOptions.find(option => option.id === document.id) === undefined){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setHiddenOptions([...hiddenOptions, levelDoc])
        }
        return null;
    }
    // ----------------------------------------------
    // ---------------  USE EFFECTS ----------------
    // ----------------------------------------------
    // used to check if the folder should be open or closed based on the max level
    useEffect(() => {
        if (openedChildren.find(option => option.id === document.parent) === undefined){   
            if(level >= localMaxLevel) {
                setOpen(false);
            }
            else {
                setOpen(true);
            }
        }
        if (selected?.breadcrumb.find(option => option.id === document.id) !== undefined){
            if(level >= localMaxLevel) {
                setOpen(false);
            }
            else {
                setOpen(true);
            }
        } 
    },[localMaxLevel, breadcrumb, openedChildren]);

    // ----------------------------------------------
    // ---------------  HANDLER FUNCTIONS -----------
    // ----------------------------------------------
    // On click of the folder tittle, the folder is selected and it is open to show its children
    // If the folder is not in the opened children, it is added to the list
    const handleFolderClick = (doc: Document) => {
        if(document.isSoftRoot){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setSoftRoot(levelDoc);
        }
        if(level< maxLevel){
            const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
            setSelected({...levelDoc, 'breadcrumb': breadcrumb});
        } else {
            const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
            setSelected({...levelDoc, 'breadcrumb': breadcrumb});
            if(!open){
                setLocalMaxLevel(localMaxLevel + 1)
            }
        }
        if(breadcrumb.length > level && selected !== null){
            const tempBreadcrums = breadcrumb.filter(opt => opt.level <= level);
            setBreadcrumb(tempBreadcrums);
        }
        if(breadcrumb.find(option => option.id === document.id) === undefined){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setBreadcrumb([...breadcrumb, levelDoc])
        }
        if(openedChildren.find(option => option.id === doc.id) === undefined){
            setOpenedChildren([...openedChildren, {...doc, 'level': level, 'parentId': parentId}])
        }
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
            const index = breadcrumb.findIndex(opt => opt.name === document.name);
            let tempBreadcrums =[...breadcrumb]
            tempBreadcrums.splice(index,1);
            if(tempBreadcrums.length > level && selected && selected.level <= level){
                tempBreadcrums = tempBreadcrums.filter(opt => opt.level <= level);
            }
            setBreadcrumb(tempBreadcrums);
        }else if(level >= localMaxLevel){
            setLocalMaxLevel(localMaxLevel + 1)
        }
        if(!open){
            if(breadcrumb.length > level && selected !== null){
                const tempBreadcrums = breadcrumb.filter(opt => opt.level <= level);
                setBreadcrumb(tempBreadcrums);
            }
            if(openedChildren.find(option => option.id === document.id) === undefined){
                setOpenedChildren([...openedChildren, {...document, 'level': level, 'parentId': parentId}])
            }
            if(breadcrumb.find(option => option.id === document.id) === undefined){
                const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
                setBreadcrumb([...breadcrumb, levelDoc])
            }
        }
        setOpen(!open);
    }
    // ----------------------------------------------
    // -------  MANAGE HIDDING CONDITIONS -----------
    // ---------------------------------------------- 
    const levelcondition = maxLevel - level >= MAX_NUMBER_LEVELS || hidden.indexOf(level)>0;
    const isChildSoft = softRoot !== null && level > softRoot.level && parentId === softRoot.parentId;
    let hideLevel = levelcondition ||(softRoot !== null && document.id !== softRoot.id);
    if(isChildSoft){ 
        hideLevel = false;
    }

    return (
        <>
        { hideLevel ?
        renderHide()
        :
        <div className="folder" >
            <div onClick={() => handleChevronClick()}>{open ?
            <ExpandMore/>
            : <ChevronRight/>}
            </div>
            <p className='folderTittle' onClick={() => handleFolderClick(document)}>{document.name}</p>
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