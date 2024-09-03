'use client'
import { Document, levelDocument, selectedDocument } from '../sidebar/sidebar';

import './file.css';

interface FileProps {
    document: Document;
    selected: selectedDocument|null;
    setSelected: (selected: selectedDocument|null) => void;
    level: number;
    parentId: string;
    breadcrumb: levelDocument[];
    setBreadcrumb: (breadcrumb: levelDocument[]) => void;
  }
  
const File: React.FC<FileProps> = ({ 
    document,
    selected,
    setSelected,
    level,
    parentId,
    breadcrumb,
    setBreadcrumb,
    }) => {
    // ----------------------------------------------
    // ---------------  HANDLER FUNCTIONS -----------
    // ----------------------------------------------   
    // When clicking on a file, set the selected document
    const handleClick = (doc: Document) => {
        const levelDoc: levelDocument= {...doc, 'level': level, 'parentId': parentId};
        setSelected({...levelDoc, 'breadcrumb': breadcrumb});
        if(breadcrumb.length > level && selected !== null){
            const tempBreadcrums = breadcrumb.filter(opt => opt.level <= level);
            setBreadcrumb(tempBreadcrums);
        }
        if(breadcrumb.find(option => option.id === document.id) === undefined){
            const levelDoc: levelDocument= {...document, 'level': level, 'parentId': parentId};
            setBreadcrumb([...breadcrumb, levelDoc])
        }
    }
    return (
        <div className="file" onClick={() => handleClick(document)}>
            <p className='fileTittle'>{document.name}</p>
        </div>
    )

}
export default File;