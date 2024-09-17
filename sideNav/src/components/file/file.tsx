'use client'
import { Document, levelDocument, MAX_NUMBER_LEVELS } from '../sidebar/sidebar';

import './file.css';

interface FileProps {
    document: Document;
    selected: levelDocument|null;
    setSelected: (selected: levelDocument|null) => void;
    level: number;
    parentId: string;
    breadcrumb: levelDocument[];
    setBreadcrumb: (breadcrumb: levelDocument[]) => void;
    hiddenOptions: levelDocument[];
    setHiddenOptions: (hiddenOptions: levelDocument[]) => void;
    maxLevel: number;
    softRoot: levelDocument|null;
    hidden: number[];
  }
  
const File: React.FC<FileProps> = ({ 
    document,
    selected,
    setSelected,
    level,
    parentId,
    breadcrumb,
    setBreadcrumb,
    hiddenOptions,
    setHiddenOptions,
    maxLevel,
    softRoot,
    hidden,
    }) => {
    // ----------------------------------------------
    // ---------------  HANDLER FUNCTIONS -----------
    // ----------------------------------------------   
    // When clicking on a file, set the selected document
    const handleClick = (doc: Document) => {
        const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
        setSelected({...levelDoc});
        if(breadcrumb.length > level && selected !== null){
            const tempBreadcrums = breadcrumb.filter(opt => opt.level <= level);
            setBreadcrumb(tempBreadcrums);
        }
        if(breadcrumb.find(option => option.id === document.id) === undefined){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setBreadcrumb([...breadcrumb, levelDoc])
        }
        const newUrl = doc.full_path || window.location.href;
        console.log(newUrl);
        window.location.href = newUrl;
    }
    // Manage the lists of hidden folders 
    const renderHide = () => {
        
        if(hiddenOptions.find(option => option.id === document.id) === undefined){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setHiddenOptions([...hiddenOptions, levelDoc])
        }
        return null;
    }
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
        <div className="file" onClick={() => handleClick(document)}>
            <p className='fileTittle'>{document.name}</p>
        </div>
        }
        </>
    )

}
export default File;